"""M2 — hierarchical reservation-depth model (HRD), frequentist form.

Implements `docs/09_m2_preregistration.md` including Amendment 1. Nothing here chooses
a threshold or a criterion; the pre-registration fixed those before any M2 number.

The idea in one line
--------------------
Each cohort's response is the **CDF of a distribution over reservation depths**. A
plant switches off once the price falls `c` €/MWh below its threshold, `c` varies
across the plants in a cohort, and

    r_k(z) = sum_{j : c_j <= z} p_kj = P(c <= z)

so monotonicity in depth and confinement to [0, 1] are what the parameters *mean*,
not constraints bolted onto a flexible curve. The atom at `c = inf` is the share of
capacity that never responds at any depth; M1 could only express that as a curve that
happens to stay low.

Two stages
----------
**Stage A** (shared by every method, cross-fitted):

    log A_t = log F_t + g(x_t),  fitted on price > 5 EUR/MWh only

`x` is hour-of-day Fourier (24 h and 12 h harmonics) crossed with season. Fitted by
OLS on log(G/F) over the uncensored sample. **Cross-fitted over 5 event-day folds,
fixed assignment, seed 42**, so every quarter-hour's A-hat comes from a model that
never saw its own day (Amendment 1 A1.2).

*Implementation choice, recorded because the pre-registration left it open:* `g` is
**linear in the stated basis**. The pre-registration fixed the basis and the fitting
sample but not g's functional form, so the simplest faithful reading is taken, and it
is fixed here before any M2 number rather than chosen after seeing one.

**Stage r**:

    y_t = 1 - G_t / A_hat_t
    X[t, (k,j)] = w_k * s_kt * 1[z_kt >= c_j]
    minimise  sum_t omega_t (y_t - X_t p)^2 + lambda * sum_k ||p_k - p_bar||^2
    subject to p_k on the simplex

The `c = inf` column of X is **identically zero** — that is not a bug. It carries the
non-responding mass so that `sum_j p_kj = 1` can be imposed while still allowing
`r_k(z) < 1` at every finite depth.

What A-hat means for M2, and a problem with criterion (c)
---------------------------------------------------------
Two different A-estimates exist here and they are not interchangeable:

* `a_hat_stage_a` — stage A's prediction. **Identical for every method**, because
  stage A is shared, and identical to B2 (deletion *is* a fit on the uncensored
  sample).
* `a_hat` — the **structural recovery** `G_t / (1 - c_hat_t)`, which uses the observed
  generation together with the estimated response. This does not collapse to
  `a_hat_stage_a`: `c_hat = Xp` is the *fitted* shortfall, not the raw `y`, so
  `G/(1 - c_hat) = A_hat_stageA * (1 - y)/(1 - c_hat)`, which equals the stage-A value
  only where the response model fits `y` exactly.

**This matters for pre-registered criterion (c)** ("M2's censored-quarter-hour MAE not
significantly worse than B2"). Scored on `a_hat_stage_a` the criterion is **vacuous**:
M2 and B2 would be bit-identical and the comparison would tie by construction, testing
nothing. Scored on the structural recovery it is a real test, and it is the quantity
that carries M2's actual claim. **`a_hat` is therefore the structural recovery**, with
the stage-A value reported alongside under its own name so either can be read. This is
flagged rather than settled silently: it is an interpretation of (c), and the
supervisor may want the other one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

SEED = 42
N_FOLDS = 5
LAMBDA_GRID = (0.0,) + tuple(np.logspace(-4, 2, 13))
KNOT_STEP = 2.0            # EUR/MWh
DEPTH_PCTILE = 99.0        # knot grid runs to this percentile of positive depth
MIN_BIN = 30               # observations needed before a hour x level variance bin is used
VAR_FLOOR_PCTILE = 5.0
XCHECK_RTOL = 1e-6         # FISTA vs cvxpy agreement, Amendment 1 A1.1
RECOVERY_MIN_DENOM = 0.2   # Amendment 2 A2.3: form G/(1-c_hat) only where 1-c_hat >= 0.2


# --------------------------------------------------------------------- stage A


def season_index(dates: np.ndarray) -> np.ndarray:
    """Meteorological season, 0=DJF 1=MAM 2=JJA 3=SON, from 'YYYY-MM-DD' strings."""
    month = np.array([int(str(d)[5:7]) for d in dates])
    return ((month % 12) // 3).astype(int)


def stage_a_basis(hour: np.ndarray, dates: np.ndarray) -> np.ndarray:
    """Intercept, season dummies, and hour Fourier (24 h, 12 h) crossed with season."""
    h = np.asarray(hour, dtype=float)
    four = np.column_stack([
        np.sin(2 * np.pi * h / 24.0), np.cos(2 * np.pi * h / 24.0),
        np.sin(2 * np.pi * h / 12.0), np.cos(2 * np.pi * h / 12.0),
    ])
    sea = season_index(dates)
    cols = [np.ones((h.size, 1))]
    for s in range(1, 4):                       # season 0 is the reference
        cols.append((sea == s).astype(float).reshape(-1, 1))
    for s in range(4):
        m = (sea == s).astype(float).reshape(-1, 1)
        cols.append(four * m)
    return np.hstack(cols)


def eventday_folds(dates: np.ndarray, n_folds: int = N_FOLDS,
                   seed: int = SEED) -> np.ndarray:
    """Fold index per quarter-hour, assigned by whole event-day. Fixed and shared."""
    uniq = np.unique(dates)
    rng = np.random.default_rng(seed)
    assign = rng.permutation(len(uniq)) % n_folds
    lookup = dict(zip(uniq.tolist(), assign.tolist()))
    return np.array([lookup[d] for d in np.asarray(dates).tolist()], dtype=int)


@dataclass
class StageA:
    a_hat: np.ndarray
    residual_log: np.ndarray        # log(G/A_hat) on the fitting sample, else nan
    omega: np.ndarray
    folds: np.ndarray
    n_fit: int


def fit_stage_a(forecast: np.ndarray, g_obs: np.ndarray, price: np.ndarray,
                hour: np.ndarray, dates: np.ndarray,
                safe_floor: float = 5.0, seed: int = SEED) -> StageA:
    """Cross-fitted log A = log F + g(x), fitted on price > safe_floor only."""
    f = np.asarray(forecast, dtype=float)
    g = np.asarray(g_obs, dtype=float)
    X = stage_a_basis(hour, dates)
    folds = eventday_folds(dates, seed=seed)

    usable = (price > safe_floor) & (f > 0) & (g > 0)
    target = np.where(usable, np.log(np.maximum(g, 1e-9) / np.maximum(f, 1e-9)), 0.0)

    a_hat = np.empty_like(f)
    for k in range(folds.max() + 1):
        train = usable & (folds != k)
        if train.sum() < X.shape[1] + 1:
            beta = np.zeros(X.shape[1])
        else:
            beta, *_ = np.linalg.lstsq(X[train], target[train], rcond=None)
        held = folds == k
        a_hat[held] = f[held] * np.exp(X[held] @ beta)

    resid = np.where(usable, np.log(np.maximum(g, 1e-9) / np.maximum(a_hat, 1e-9)),
                     np.nan)
    return StageA(a_hat=a_hat, residual_log=resid,
                  omega=weights_from_residuals(a_hat, resid, hour),
                  folds=folds, n_fit=int(usable.sum()))


def weights_from_residuals(a_hat: np.ndarray, resid_log: np.ndarray,
                           hour: np.ndarray) -> np.ndarray:
    """omega_t = A_hat_t^2 / Var_hat(A_hat | hour, level), per section 6.

    The variance is taken on the MW scale: Var(A) ~ (A_hat * sd(log residual))^2, binned
    by hour-of-day x decile of A_hat, floored at the 5th percentile of the binned
    variances, falling back to the hour marginal where a bin has under 30 observations.
    """
    a = np.asarray(a_hat, dtype=float)
    ok = np.isfinite(resid_log)
    lvl = np.full(a.size, -1, dtype=int)
    if ok.any():
        edges = np.percentile(a[ok], np.linspace(0, 100, 11))
        lvl = np.clip(np.digitize(a, np.unique(edges)[1:-1]), 0, 9)
    hr = np.asarray(hour, dtype=int)

    var = np.full(a.size, np.nan)
    hour_var = {}
    for h in np.unique(hr):
        sel = ok & (hr == h)
        if sel.sum() >= 2:
            hour_var[h] = float(np.var(resid_log[sel], ddof=1))
    for h in np.unique(hr):
        for l in range(10):
            sel = (hr == h) & (lvl == l)
            fit = sel & ok
            if fit.sum() >= MIN_BIN:
                var[sel] = float(np.var(resid_log[fit], ddof=1))
            else:
                var[sel] = hour_var.get(h, np.nan)
    gl = float(np.nanvar(resid_log[ok], ddof=1)) if ok.sum() >= 2 else 1.0
    var = np.where(np.isfinite(var), var, gl)
    floor = np.percentile(var[var > 0], VAR_FLOOR_PCTILE) if (var > 0).any() else 1e-12
    var = np.maximum(var, max(floor, 1e-12))
    # Var on the MW scale, then omega = A_hat^2 / Var.
    var_mw = np.maximum((a ** 2) * var, 1e-9)
    return (a ** 2) / var_mw


# ------------------------------------------------------------------- the design


def knot_grid(depth: np.ndarray, train: np.ndarray, step: float = KNOT_STEP,
              with_atom: bool = True) -> np.ndarray:
    """c_0 = 0+ (optional), then step, 2*step, ... to the training 99th percentile."""
    pos = depth[:, train][depth[:, train] > 0] if depth.ndim == 2 else depth[train]
    top = float(np.percentile(pos, DEPTH_PCTILE)) if pos.size else step
    finite = np.arange(step, max(top, step) + step / 2, step)
    atom = np.array([0.0]) if with_atom else np.empty(0)
    return np.concatenate([atom, finite, np.array([np.inf])])


def pool_blocks(s: np.ndarray, depth: np.ndarray,
                shares: np.ndarray) -> tuple[np.ndarray, list[list[int]]]:
    """Group cohorts whose (exposure, depth) columns are identical.

    This implements section 2 exactly, and does so empirically rather than by naming
    cases. Cohorts with theta = 0 have the same exposure and the same depth, so they
    land in one block -- verified in the pre-registration's 4.3, where MP = 0 gives a
    single pattern across all eight cohorts. Cohorts with no support at all have
    all-zero columns and likewise pool together.
    """
    key_to_block: dict[bytes, int] = {}
    members: list[list[int]] = []
    block_of = np.empty(len(shares), dtype=int)
    for k in range(len(shares)):
        key = s[k].tobytes() + depth[k].tobytes()
        if key not in key_to_block:
            key_to_block[key] = len(members)
            members.append([])
        b = key_to_block[key]
        block_of[k] = b
        members[b].append(k)
    return block_of, members


def build_design(s: np.ndarray, depth: np.ndarray, shares: np.ndarray,
                 knots: np.ndarray, members: list[list[int]]) -> np.ndarray:
    """X[t, (b,j)] = (sum of w_k over block b) * s_bt * 1[z_bt >= c_j].

    The c = inf column is identically zero by construction: it holds the share that
    never responds, needed only so the simplex sums to one.
    """
    n_b, n_j = len(members), knots.size
    T = s.shape[1]
    X = np.zeros((T, n_b * n_j))
    for b, ks in enumerate(members):
        w = float(shares[ks].sum())
        sk, zk = s[ks[0]], depth[ks[0]]
        for j, c in enumerate(knots):
            if not np.isfinite(c):
                continue                      # the never-respond atom: column stays 0
            ind = (zk > 0) if c == 0.0 else (zk >= c)
            X[:, b * n_j + j] = w * sk * ind
    return X


# -------------------------------------------------------------------- the solve


def simplex_projection(v: np.ndarray) -> np.ndarray:
    """Euclidean projection of each row onto the unit simplex."""
    V = np.atleast_2d(np.asarray(v, dtype=float))
    n = V.shape[1]
    U = -np.sort(-V, axis=1)
    css = np.cumsum(U, axis=1) - 1.0
    idx = np.arange(1, n + 1)
    cond = U - css / idx > 0
    rho = n - np.argmax(cond[:, ::-1], axis=1) - 1
    theta = css[np.arange(V.shape[0]), rho] / (rho + 1)
    return np.maximum(V - theta[:, None], 0.0)


def _penalty_operator(block_shares: np.ndarray) -> np.ndarray:
    """M with (M P)_b = p_b - p_bar, p_bar the capacity-weighted mean across blocks."""
    a = block_shares / block_shares.sum()
    return np.eye(len(a)) - np.ones((len(a), 1)) @ a.reshape(1, -1)


def fista(X: np.ndarray, y: np.ndarray, omega: np.ndarray, n_b: int, n_j: int,
          lam: float, block_shares: np.ndarray, max_iter: int = 20000,
          tol: float = 1e-12) -> tuple[np.ndarray, float]:
    """Accelerated projected gradient for the same convex QP, as a cross-check."""
    M = _penalty_operator(block_shares)
    MtM = M.T @ M
    Xw = X * np.sqrt(omega)[:, None]
    yw = y * np.sqrt(omega)
    XtX = Xw.T @ Xw
    Xty = Xw.T @ yw

    def obj(P):
        p = P.reshape(-1)
        r = Xw @ p - yw
        return float(r @ r + lam * np.sum((M @ P) ** 2))

    # Lipschitz constant by power iteration on the Hessian's two blocks.
    v = np.random.default_rng(SEED).normal(size=n_b * n_j)
    for _ in range(100):
        v = XtX @ v
        nv = np.linalg.norm(v)
        if nv == 0:
            break
        v /= nv
    L = 2.0 * float(v @ (XtX @ v)) + 2.0 * lam * float(np.linalg.eigvalsh(MtM).max())
    L = max(L, 1e-12)

    P = np.full((n_b, n_j), 1.0 / n_j)
    Z, t_k, prev = P.copy(), 1.0, obj(P)
    for _ in range(max_iter):
        grad = (2.0 * (XtX @ Z.reshape(-1) - Xty)).reshape(n_b, n_j) \
            + 2.0 * lam * (MtM @ Z)
        P_new = simplex_projection(Z - grad / L)
        t_next = (1.0 + np.sqrt(1.0 + 4.0 * t_k ** 2)) / 2.0
        Z = P_new + ((t_k - 1.0) / t_next) * (P_new - P)
        P, t_k = P_new, t_next
        cur = obj(P)
        if abs(prev - cur) <= tol * max(1.0, abs(prev)):
            break
        prev = cur
    return P, obj(P)


def solve_stage_r(X: np.ndarray, y: np.ndarray, omega: np.ndarray, n_b: int,
                  n_j: int, lam: float, block_shares: np.ndarray) -> dict:
    """cvxpy with its default QP solver (OSQP), cross-checked against FISTA."""
    import cvxpy as cp

    M = _penalty_operator(block_shares)
    sw = np.sqrt(omega)
    P = cp.Variable((n_b, n_j), nonneg=True)
    resid = cp.multiply(sw, X @ cp.vec(P, order="C") - y)
    objective = cp.sum_squares(resid) + lam * cp.sum_squares(M @ P)
    prob = cp.Problem(cp.Minimize(objective), [cp.sum(P, axis=1) == 1])
    prob.solve()
    solver = prob.solver_stats.solver_name if prob.solver_stats else "unknown"
    if prob.status not in ("optimal", "optimal_inaccurate") or P.value is None:
        prob.solve(solver=cp.CLARABEL)          # pre-registered fallback
        solver = f"CLARABEL (fallback from {solver}, status was {prob.status})"

    p_cvx = np.asarray(P.value)
    f_cvx = float(prob.value)
    p_fis, f_fis = fista(X, y, omega, n_b, n_j, lam, block_shares)
    denom = max(abs(f_cvx), abs(f_fis), 1e-12)
    rel = abs(f_cvx - f_fis) / denom
    return {"p": p_cvx, "objective": f_cvx, "solver": solver,
            "status": prob.status, "fista_objective": f_fis,
            "xcheck_rel_diff": rel, "xcheck_ok": bool(rel <= XCHECK_RTOL)}


# ------------------------------------------------------------------------- fit


@dataclass
class M2Ablation:
    label: str = "M2"
    pool: bool = True            # False -> lambda = 0 (M2-noPool)
    atom: bool = True            # False -> no z>0 atom (M2-noAtom)
    note: str = ""


ABLATIONS = (
    M2Ablation("M2"),
    M2Ablation("M2-noPool", pool=False, note="lambda = 0, blocks never shrink to p_bar"),
    M2Ablation("M2-noAtom", atom=False, note="no reservation-depth atom just above 0"),
)


def response_curve(p: np.ndarray, knots: np.ndarray, block_shares: np.ndarray,
                   depth_grid: np.ndarray) -> np.ndarray:
    """Capacity-weighted pooled r-hat on a depth grid: the CDF, by construction."""
    w = block_shares / block_shares.sum()
    out = np.zeros_like(depth_grid, dtype=float)
    for b in range(p.shape[0]):
        cdf = np.array([p[b][np.isfinite(knots) & (knots <= z)].sum()
                        + (p[b][0] if (knots[0] == 0.0 and z > 0) else 0.0)
                        for z in depth_grid])
        out += w[b] * np.minimum(cdf, 1.0)
    return out


def numerical_rank(X: np.ndarray, omega: np.ndarray) -> tuple[int, int]:
    """Rank of sqrt(omega) X by SVD, with section 6's tolerance. Returns (rank, cols)."""
    Xw = X * np.sqrt(omega)[:, None]
    if Xw.size == 0:
        return 0, 0
    sv = np.linalg.svd(Xw, compute_uv=False)
    tol = max(Xw.shape) * np.finfo(float).eps * (sv[0] if sv.size else 0.0)
    return int((sv > tol).sum()), Xw.shape[1]


def choose_lambda(X, y, omega, n_b, n_j, block_shares, dates, train,
                  grid=LAMBDA_GRID, seed=SEED) -> tuple[float, list[dict]]:
    """Inner event-day 5-fold CV, inside the training window only (section 6)."""
    folds = eventday_folds(dates[train], seed=seed + 1)
    Xt, yt, wt = X[train], y[train], omega[train]
    log = []
    for lam in grid:
        err = 0.0
        for k in range(folds.max() + 1):
            tr, va = folds != k, folds == k
            if tr.sum() < n_j or va.sum() == 0:
                continue
            res = solve_stage_r(Xt[tr], yt[tr], wt[tr], n_b, n_j, lam, block_shares)
            pred = Xt[va] @ res["p"].reshape(-1)
            err += float(np.sum(wt[va] * (yt[va] - pred) ** 2))
        log.append({"lambda": lam, "cv_weighted_sse": err})
    best = min(log, key=lambda r: r["cv_weighted_sse"])["lambda"]
    return best, log


def fit_m2(data, depth_grid: np.ndarray, ablation: M2Ablation | None = None,
           stage_a: StageA | None = None, train_mask: np.ndarray | None = None,
           lam: float | None = None) -> dict:
    """Fit M2 (or an ablation) on a SyntheticData-like object."""
    ab = ablation or ABLATIONS[0]
    hour = getattr(data, "real_hour", None)
    if hour is None:
        raise ValueError("M2's stage A needs the real hour-of-day; data has none.")
    dates = np.asarray(data.real_berlin_date)

    sa = stage_a or fit_stage_a(data.forecast_mw, data.g_obs_mw,
                                data.price_eur_mwh, hour, dates)
    train = np.ones(sa.a_hat.size, dtype=bool) if train_mask is None else train_mask

    y = 1.0 - data.g_obs_mw / np.maximum(sa.a_hat, 1e-9)
    knots = knot_grid(data.depth, train, with_atom=ab.atom)
    shares = np.asarray(data.cohorts.shares, dtype=float)
    block_of, members = pool_blocks(data.s, data.depth, shares)
    block_shares = np.array([shares[m].sum() for m in members])
    X = build_design(data.s, data.depth, shares, knots, members)
    n_b, n_j = len(members), knots.size

    if not ab.pool:
        lam_used, cv_log = 0.0, []
    elif lam is not None:
        lam_used, cv_log = lam, []
    else:
        lam_used, cv_log = choose_lambda(X, y, sa.omega, n_b, n_j, block_shares,
                                         dates, train)

    res = solve_stage_r(X[train], y[train], sa.omega[train], n_b, n_j,
                        lam_used, block_shares)
    p = res["p"]
    c_hat = np.clip(X @ p.reshape(-1), 0.0, 1.0)
    rank, ncols = numerical_rank(X[train], sa.omega[train])

    # A-hat: the STRUCTURAL RECOVERY, with stage A reported separately. See the module
    # docstring on why criterion (c) is vacuous on the stage-A value.
    #
    # Amendment 2's 0.2 stability rule: G/(1 - c_hat) diverges as c_hat -> 1, so the
    # recovery is formed ONLY where 1 - c_hat >= 0.2 and is undefined elsewhere. An
    # earlier version floored the denominator at 1e-6, which does not stabilise
    # anything -- it just replaces a divergence with a number up to 10^6 times G, which
    # would then dominate any MAE it entered. Excluded quarter-hours are NaN, and the
    # count and share are reported so a recovery result can never be read without
    # knowing how much of the sample it rests on.
    a_struct = np.full(c_hat.shape, np.nan)
    # Tested on c_hat, not on (1 - c_hat): in IEEE754 `1 - 0.8` is 0.19999999999999996,
    # so the natural form silently EXCLUDES a quarter-hour sitting exactly on the 0.2
    # boundary that the rule says to include. `1.0 - 0.2` is exactly 0.8, so this form
    # puts the boundary where Amendment 2 A2.3 puts it.
    ok = c_hat <= (1.0 - RECOVERY_MIN_DENOM)
    a_struct[ok] = data.g_obs_mw[ok] / (1.0 - c_hat[ok])
    n_excluded = int((~ok).sum())

    return {
        "name": ab.label, "ablation": ab.label, "ablation_note": ab.note,
        "a_hat": a_struct, "a_hat_stage_a": sa.a_hat, "c_hat": c_hat,
        "recovery_excluded_n": n_excluded,
        "recovery_excluded_share": float(n_excluded / c_hat.size),
        "recovery_min_denom": RECOVERY_MIN_DENOM,
        "p": p, "knots": knots, "blocks": members, "block_of": block_of,
        "block_shares": block_shares, "n_blocks": n_b, "n_knots": n_j,
        "lambda": lam_used, "cv_log": cv_log,
        "rank_X": rank, "cols_X": ncols, "rank_deficient": bool(rank < ncols),
        "solver": res["solver"], "solver_status": res["status"],
        "objective": res["objective"], "fista_objective": res["fista_objective"],
        "xcheck_rel_diff": res["xcheck_rel_diff"], "xcheck_ok": res["xcheck_ok"],
        "stage_a_n_fit": sa.n_fit, "omega": sa.omega,
        "r_hat": response_curve(p, knots, block_shares, depth_grid),
    }
