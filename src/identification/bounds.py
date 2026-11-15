"""P3 -- the identified set of a linear functional of the cohort responses.

    min / max  lambda' r
    subject to ||X r - c_hat||_RMS <= eps,   0 <= r <= 1,
               r non-decreasing in depth, r non-decreasing in run length

`X` is the exposure-weighted design: row t, column (k, j, m) holds the capacity share
`w_k` when cohort k is exposed at t with its depth in bin j and its run length in level
m, and zero otherwise. So `(X r)_t = sum_k w_k s_kt r_k(z_kt, L_kt) = c_t` exactly --
the observation model of spec section 3, with the response discretised onto a grid.

WHY A SET RATHER THAN AN ESTIMATE
---------------------------------
Only the aggregate `c_t` is observed, never the per-cohort split. Where two cohorts
have identical `(s, depth)` rows -- which `docs/12` shows is structural for the
theta = 0 pair and holds for 29.3% of capacity at the live award settings -- no
estimator can separate their responses, and a point estimate of either one is an
artefact of whatever regularisation produced it. The identified set is the honest
object: every `r` inside it fits the data equally well, so a functional's range over
the set is exactly what the data can say about it.

The three constraint families are not decoration. `0 <= r <= 1` is what makes `r` a
fraction of capacity; monotonicity is assumption I3 (spec section 3), built in rather
than hoped for; and `||X r - c_hat|| <= eps` is the data. Drop any one and the set
is wider for a reason that is not about identification.

THE NORM, AND WHY RMS
---------------------
`||v||_RMS = sqrt(mean(v^2))`. The brief writes `||X r - c_hat|| <= eps` without
naming a norm, so this is a gap filled before any number existed
(`docs/P3_results.md` section 0). RMS is scale-free in the number of quarter-hours,
so `eps` is comparable between a month with 492 of them and one with 10; a plain
Euclidean norm would grow as sqrt(T) and make every cross-arm comparison a statement
about sample size. Because `eps` is defined as a percentile of the *same* functional
under the bootstrap, any monotone rescaling of the norm cancels -- what matters is
that the two are the same, and they are, by construction (`epsilon_from_bootstrap`).

ROWS: EXPOSED QUARTER-HOURS ONLY
--------------------------------
Rows where no cohort is exposed are dropped. There `X_t = 0` and the model predicts
`c_t = 0` identically, whatever `r` is -- the exposure-mask identity that
`docs/09` Amendment 1 A1.2 labels "cannot fail". Keeping them would add rows that
constrain nothing about `r` while inflating the residual with stage-A noise, which
would quietly loosen `eps` and widen every interval.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

SEED = 42
N_BOOT = 5000
EPS_PERCENTILE = 95.0

#: Depth-bin edges, EUR/MWh below the cohort's own threshold. Left-open, right-closed
#: on (edge[j], edge[j+1]], with the first bin carrying every positive depth up to the
#: first inner edge and the last bin open to infinity. The 2 EUR/MWh lattice up to 50
#: is the M2 reservation-depth resolution (`docs/09` section 6), reused rather than
#: reinvented; beyond 50 the quarter-hours thin out and the lattice coarsens with them.
DEPTH_EDGES = np.array(
    [0.0, *np.arange(2.0, 50.0 + 1e-9, 2.0), 60.0, 75.0, 100.0, 150.0, np.inf]
)
#: Run-length levels. Two, split at the median run length over exposed quarter-hours
#: of the arm, so the split is a property of the arm and not a hand-picked hour count.
N_RUN_LEVELS = 2


# --------------------------------------------------------------------- the design


@dataclass(frozen=True)
class BoundsDesign:
    """The design matrix, its column key, and the monotonicity operators."""

    X: np.ndarray                      # (T_exposed, n)
    rows: np.ndarray                   # indices into the original quarter-hours
    cohort_ids: tuple[str, ...]
    depth_edges: np.ndarray
    n_run_levels: int
    run_split: float                   # the run length the two levels split at
    col_of: dict[tuple[int, int, int], int]
    A_depth: np.ndarray                # A_depth @ r >= 0  (non-decreasing in depth)
    A_run: np.ndarray                  # A_run   @ r >= 0  (non-decreasing in run)
    col_cohort: np.ndarray             # (n,) cohort index per column
    col_depth_bin: np.ndarray
    col_run_level: np.ndarray
    diagnostics: dict = field(default_factory=dict)

    @property
    def n_cols(self) -> int:
        return self.X.shape[1]

    @property
    def n_rows(self) -> int:
        return self.X.shape[0]


def _bin_of(depth: np.ndarray, edges: np.ndarray) -> np.ndarray:
    """Index of the bin each positive depth falls in; -1 where depth <= 0."""
    d = np.asarray(depth, dtype=float)
    j = np.searchsorted(edges[1:], d, side="left")
    j = np.clip(j, 0, edges.size - 2)
    return np.where(d > 0.0, j, -1)


def build_design(
    s: np.ndarray,
    depth: np.ndarray,
    shares: np.ndarray,
    runlen: np.ndarray | None = None,
    cohort_ids=None,
    depth_edges: np.ndarray = DEPTH_EDGES,
    n_run_levels: int = N_RUN_LEVELS,
) -> BoundsDesign:
    """Build X and the monotonicity operators from (K, T) exposure and depth.

    `runlen` is the (K, T) run length in hours on each cohort's own clock; pass None
    for a single run-length level. Columns exist only for (cohort, bin, level) cells
    that actually occur, because an empty column is unconstrained by the data and
    would make every bound trivially [0, 1] through a cell nothing was observed in.
    """
    s = np.asarray(s, dtype=float)
    depth = np.asarray(depth, dtype=float)
    w = np.asarray(shares, dtype=float)
    k_n, t_n = s.shape
    ids = tuple(cohort_ids) if cohort_ids is not None else tuple(f"k{i}" for i in range(k_n))
    if len(ids) != k_n:
        raise ValueError(f"cohort_ids has {len(ids)} entries for {k_n} cohorts")

    exposed = s > 0.0
    rows = np.flatnonzero(exposed.any(axis=0))
    if rows.size == 0:
        raise ValueError("no exposed quarter-hour: there is nothing to identify")

    if runlen is None or n_run_levels <= 1:
        level = np.zeros_like(s, dtype=int)
        split, n_lev = float("nan"), 1
    else:
        rl = np.asarray(runlen, dtype=float)
        if rl.shape != s.shape:
            raise ValueError(f"runlen {rl.shape} does not match s {s.shape}")
        split = float(np.median(rl[exposed])) if exposed.any() else float("nan")
        level = (rl > split).astype(int)
        n_lev = 2
        if np.unique(level[exposed]).size == 1:      # the median did not split
            level = np.zeros_like(level)
            n_lev = 1

    jbin = _bin_of(depth, depth_edges)
    cells: dict[tuple[int, int, int], int] = {}
    for k in range(k_n):
        on = exposed[k, rows]
        if not on.any():
            continue
        for j, m in set(zip(jbin[k, rows][on].tolist(), level[k, rows][on].tolist())):
            cells.setdefault((k, int(j), int(m)), len(cells))
    if not cells:
        raise ValueError("every exposed quarter-hour has non-positive depth")
    col_of = {key: i for i, key in enumerate(sorted(cells))}
    n = len(col_of)

    X = np.zeros((rows.size, n), dtype=float)
    for k in range(k_n):
        on = exposed[k, rows]
        if not on.any():
            continue
        r_idx = np.flatnonzero(on)
        cols = np.array([col_of[(k, int(j), int(m))]
                         for j, m in zip(jbin[k, rows][on], level[k, rows][on])])
        np.add.at(X, (r_idx, cols), w[k])

    col_cohort = np.empty(n, dtype=int)
    col_bin = np.empty(n, dtype=int)
    col_lev = np.empty(n, dtype=int)
    for (k, j, m), i in col_of.items():
        col_cohort[i], col_bin[i], col_lev[i] = k, j, m

    # Monotone in depth: within a cohort and run level, the next OCCUPIED bin is
    # >= this one. Chaining over occupied bins only is what makes the constraint
    # bind: a missing bin in between has no column to carry the inequality.
    rows_d, rows_r = [], []
    for k in range(k_n):
        for m in range(n_lev):
            cols = sorted((j, col_of[(k, j, m)]) for (kk, j, mm) in col_of
                          if kk == k and mm == m)
            for (j0, c0), (j1, c1) in zip(cols, cols[1:]):
                row = np.zeros(n)
                row[c1], row[c0] = 1.0, -1.0
                rows_d.append(row)
    for k in range(k_n):
        for (kk, j, m), c0 in col_of.items():
            if kk != k or m + 1 >= n_lev:
                continue
            c1 = col_of.get((k, j, m + 1))
            if c1 is not None:
                row = np.zeros(n)
                row[c1], row[c0] = 1.0, -1.0
                rows_r.append(row)
    A_depth = np.array(rows_d) if rows_d else np.zeros((0, n))
    A_run = np.array(rows_r) if rows_r else np.zeros((0, n))

    diag = {
        "n_qh_total": int(t_n), "n_qh_exposed": int(rows.size), "n_cols": int(n),
        "n_cohorts": int(k_n), "n_cohorts_exposed": int((exposed.any(axis=1)).sum()),
        "n_run_levels": int(n_lev), "run_split_h": split,
        "n_monotone_depth": int(A_depth.shape[0]), "n_monotone_run": int(A_run.shape[0]),
        "mean_cols_per_row": float((X != 0).sum(axis=1).mean()),
    }
    return BoundsDesign(X=X, rows=rows, cohort_ids=ids, depth_edges=np.asarray(depth_edges),
                        n_run_levels=n_lev, run_split=split, col_of=col_of,
                        A_depth=A_depth, A_run=A_run, col_cohort=col_cohort,
                        col_depth_bin=col_bin, col_run_level=col_lev, diagnostics=diag)


# ------------------------------------------------------------------ the point fit


def _solve(objective_sense: str, design: BoundsDesign, c_hat: np.ndarray,
           lam: np.ndarray | None, eps: float | None) -> dict:
    """One convex programme. `lam=None` with `eps=None` is the constrained least squares."""
    import cvxpy as cp

    n = design.n_cols
    r = cp.Variable(n)
    cons = [r >= 0.0, r <= 1.0]
    if design.A_depth.shape[0]:
        cons.append(design.A_depth @ r >= 0.0)
    if design.A_run.shape[0]:
        cons.append(design.A_run @ r >= 0.0)
    resid = design.X @ r - c_hat
    if eps is not None:
        # ||resid||_2 <= eps * sqrt(T)  is  RMS(resid) <= eps
        cons.append(cp.norm(resid, 2) <= float(eps) * np.sqrt(design.n_rows))

    if lam is None:
        prob = cp.Problem(cp.Minimize(cp.sum_squares(resid)), cons)
    elif objective_sense == "min":
        prob = cp.Problem(cp.Minimize(lam @ r), cons)
    else:
        prob = cp.Problem(cp.Maximize(lam @ r), cons)

    try:
        prob.solve(solver=cp.CLARABEL)
    except Exception as exc:                                    # noqa: BLE001
        return {"status": f"error: {type(exc).__name__}", "value": float("nan"),
                "r": None, "solver": "CLARABEL"}
    if prob.status not in ("optimal", "optimal_inaccurate") or r.value is None:
        return {"status": str(prob.status), "value": float("nan"), "r": None,
                "solver": "CLARABEL"}
    return {"status": str(prob.status), "value": float(prob.value),
            "r": np.asarray(r.value, dtype=float), "solver": "CLARABEL"}


def point_fit(design: BoundsDesign, c_hat: np.ndarray) -> dict:
    """Constrained least squares: the r-hat that `eps` is measured around."""
    out = _solve("min", design, c_hat, None, None)
    if out["r"] is not None:
        out["rms_residual"] = float(np.sqrt(np.mean((design.X @ out["r"] - c_hat) ** 2)))
    else:
        out["rms_residual"] = float("nan")
    return out


def pooled_fit(design: BoundsDesign, c_hat: np.ndarray) -> dict:
    """The single common response function -- Hirth's assumption, as a comparator.

    One response shared by every cohort: `r_k(z, L) = r(z, L)` for all k. Implemented
    by summing the columns of each (bin, level) cell across cohorts, so the pooled
    design is the capacity-weighted exposed share at that cell. The fit is the same
    constrained least squares on that smaller design.
    """
    key = [(int(j), int(m)) for j, m in zip(design.col_depth_bin, design.col_run_level)]
    uniq = sorted(set(key))
    pos = {c: i for i, c in enumerate(uniq)}
    M = np.zeros((design.n_cols, len(uniq)))
    for i, c in enumerate(key):
        M[i, pos[c]] = 1.0
    pooled = BoundsDesign(
        X=design.X @ M, rows=design.rows, cohort_ids=("pooled",),
        depth_edges=design.depth_edges, n_run_levels=design.n_run_levels,
        run_split=design.run_split,
        col_of={(0, j, m): i for i, (j, m) in enumerate(uniq)},
        A_depth=np.array([[1.0 if i == b else -1.0 if i == a else 0.0
                           for i in range(len(uniq))]
                          for (a, b) in zip(range(len(uniq)), range(1, len(uniq)))
                          if uniq[a][1] == uniq[b][1]]).reshape(-1, len(uniq)),
        A_run=np.zeros((0, len(uniq))),
        col_cohort=np.zeros(len(uniq), dtype=int),
        col_depth_bin=np.array([j for j, _ in uniq]),
        col_run_level=np.array([m for _, m in uniq]),
    )
    out = _solve("min", pooled, c_hat, None, None)
    if out["r"] is None:
        return {"status": out["status"], "r_expanded": None}
    return {"status": out["status"], "r_expanded": M @ out["r"], "r_pooled": out["r"],
            "n_pooled_cols": len(uniq)}


# ------------------------------------------------------------------------ epsilon


def epsilon_from_bootstrap(design: BoundsDesign, c_hat: np.ndarray, days: np.ndarray,
                           r_hat: np.ndarray, n_boot: int = N_BOOT, seed: int = SEED,
                           percentile: float = EPS_PERCENTILE) -> dict:
    """eps = the `percentile` of RMS(X r_hat - c_hat) over event-day resamples.

    `docs/P0_preregistration.md` section 7 fixes this before any bound is computed:
    event-days are resampled with replacement, the residual of the ORIGINAL point fit
    is evaluated on the resampled rows, and eps is that distribution's 95th
    percentile. Holding `r_hat` fixed is what makes eps a statement about sampling
    noise in `c_hat` rather than about refitting.
    """
    resid = design.X @ r_hat - np.asarray(c_hat, dtype=float)
    d = np.asarray(days)[design.rows] if np.asarray(days).size != design.n_rows else np.asarray(days)
    uniq, idx = np.unique(d.astype(str), return_inverse=True)
    sq = resid ** 2
    per_day_sum = np.zeros(uniq.size)
    per_day_n = np.zeros(uniq.size)
    np.add.at(per_day_sum, idx, sq)
    np.add.at(per_day_n, idx, 1.0)

    rng = np.random.default_rng(seed)
    draws = rng.integers(0, uniq.size, size=(n_boot, uniq.size))
    tot = per_day_sum[draws].sum(axis=1)
    cnt = per_day_n[draws].sum(axis=1)
    rms = np.sqrt(tot / np.maximum(cnt, 1.0))
    return {
        "eps": float(np.percentile(rms, percentile)),
        "rms_point": float(np.sqrt(sq.mean())),
        "rms_boot_median": float(np.median(rms)),
        "n_days": int(uniq.size), "n_boot": int(n_boot), "seed": int(seed),
        "percentile": float(percentile),
    }


# ------------------------------------------------------------------- the functional


def in_row_space(X: np.ndarray, lam: np.ndarray) -> dict:
    """Is lambda in the row space of X? The algebraic point-identification test.

    lambda' r is determined by X r alone exactly when lambda lies in the row space.
    The test is run on the Gram matrix because X has up to 4e4 rows; the tolerance is
    written out (`largest eigenvalue * n * eps`) rather than left to a library
    default, following `src/censoring/identification.py`.

    A caveat that belongs with every use: being outside the row space does NOT make a
    bound wide, and being inside does NOT make it a point. The box and monotonicity
    constraints pin functionals the row space alone would leave free, and eps > 0
    leaves a width of order eps even for a functional that is in it. The algebraic
    test and the realised width are reported side by side for exactly this reason.
    """
    G = X.T @ X
    evals, evecs = np.linalg.eigh(G)
    tol = float(evals.max() * G.shape[0] * np.finfo(float).eps) if evals.size else 0.0
    null = evecs[:, evals <= tol]
    lam = np.asarray(lam, dtype=float)
    nrm = float(np.linalg.norm(lam))
    perp = float(np.linalg.norm(null.T @ lam)) if null.shape[1] else 0.0
    return {"in_row_space": bool(perp <= tol ** 0.5 * max(nrm, 1e-12) or perp <= 1e-9),
            "perp_fraction": float(perp / nrm) if nrm > 0 else float("nan"),
            "null_dim": int(null.shape[1]), "gram_tol": tol,
            "rank": int((evals > tol).sum()), "n_cols": int(G.shape[0])}


def identified_set(design: BoundsDesign, c_hat: np.ndarray, lam: np.ndarray,
                   eps: float) -> dict:
    """[min, max] of lambda' r over the identified set."""
    lo = _solve("min", design, c_hat, np.asarray(lam, dtype=float), eps)
    hi = _solve("max", design, c_hat, np.asarray(lam, dtype=float), eps)
    width = (hi["value"] - lo["value"]
             if np.isfinite(lo["value"]) and np.isfinite(hi["value"]) else float("nan"))
    return {"lo": lo["value"], "hi": hi["value"], "width": width,
            "status_lo": lo["status"], "status_hi": hi["status"],
            "feasible": bool(np.isfinite(width))}
