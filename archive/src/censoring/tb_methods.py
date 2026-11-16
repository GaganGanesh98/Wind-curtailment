"""Method wiring for T-B: the shared stage A, B3-CV, B3@8, B3-H, B6 and the M2 family.

Every `fit(data, fit_mask, shared_a)` here obeys **guard 3**: its inner
cross-validation sees only the quarter-hours in `fit_mask`, i.e. only the selected
event-days. If B3-CV could tune its bin count on days M2 was denied, the T-B result
would be void, and that is the one failure mode no amount of care in the runner would
catch.

Guard 3 is enforced rather than promised. `inner_cv_folds()` is the only place a fold
is built, it takes the mask and returns indices drawn from it alone, and
`tests/test_tb.py` corrupts the UNSELECTED days and asserts every method's chosen
hyperparameter is unchanged. A method that peeked would select differently and fail
that test.
"""

from __future__ import annotations

import numpy as np

from src.method.stage_a.baselines import _binned_response, b3_response_curve, fit_b3
from src.method.stage_a.reservation_depth_model import (
    ABLATIONS,
    fit_shared_stage_a,
    hour_fourier_features,
    response_curve,
)
from src.method.stage_a.latent_model import TrainConfig

B3_BIN_GRID = (4, 8, 16, 32, 64)
HIRTH_EDGES = (0.0, 5.0, 10.0, 20.0, 50.0, 100.0, float("inf"))
N_INNER_FOLDS = 5
INNER_SEED = 42


def inner_cv_folds(berlin_date: np.ndarray, fit_mask: np.ndarray,
                   n_folds: int = N_INNER_FOLDS, seed: int = INNER_SEED):
    """Event-day folds over the SELECTED days only. The single choke point for guard 3.

    Yields (train_idx, val_idx) as absolute indices into the full arrays, every one of
    which lies inside `fit_mask`. Nothing outside the mask can reach a tuning decision
    because nothing outside it is ever returned.
    """
    mask = np.asarray(fit_mask, dtype=bool)
    idx = np.flatnonzero(mask)
    if idx.size == 0:
        return
    days = np.asarray(berlin_date)[idx]
    uniq = np.unique(days)
    assign = np.random.default_rng(seed).permutation(len(uniq)) % n_folds
    fold_of_day = dict(zip(uniq.tolist(), assign.tolist()))
    fold = np.array([fold_of_day[d] for d in days.tolist()])
    for k in range(min(n_folds, len(uniq))):
        tr, va = idx[fold != k], idx[fold == k]
        if tr.size and va.size:
            yield tr, va


# ------------------------------------------------------------------ shared stage A


def make_shared_stage_a(cfg: TrainConfig | None = None):
    """One stage-A array per cell (Amendment 6), reused at every n-level."""
    def _build(data):
        return fit_shared_stage_a(data, cfg=cfg or TrainConfig())
    return _build


def _b3_inputs(data, a_hat: np.ndarray, sel: np.ndarray):
    """fit_b3's stage-3 inputs, restricted to `sel`."""
    shares = np.asarray(data.cohorts.shares, dtype=float)[:, None]
    residual = np.maximum(0.0, a_hat - data.g_obs_mw)
    exposed_share = (shares * data.s).sum(axis=0)
    exposed_potential = a_hat * exposed_share
    weighted_depth = (shares * data.s * data.depth).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        margin = np.where(exposed_share > 0, weighted_depth / exposed_share, 0.0)
    use = sel & (exposed_potential > 0)
    return margin[use], residual[use], exposed_potential[use]


def _b3_from_shared(data, fit_mask, shared_a, n_bins, edges):
    """B3's binned response on the shared A-hat, fitted on the selected days only."""
    a_hat = shared_a.a_hat
    margin, residual, pot = _b3_inputs(data, a_hat, np.asarray(fit_mask, dtype=bool))
    br = _binned_response(margin, residual, pot, n_bins, edges=edges)
    return {"name": "B3", "a_hat": a_hat, "implied_response": br,
            "n_bins": n_bins, "bin_edges": edges}


def fit_b3_fixed(n_bins: int | None = None, edges=None):
    def _fit(data, fit_mask, shared_a):
        return _b3_from_shared(data, fit_mask, shared_a, n_bins or 8, edges)
    return _fit


def fit_b3_cv(data, fit_mask, shared_a):
    """B3 with the bin count chosen by inner event-day CV on the SELECTED days only.

    Selection criterion is held-out weighted squared error on `y = 1 - G/A_hat`, the
    same target and the same folds M2's lambda and B6's hyperparameters use, so the
    three tuned methods get an identical budget.
    """
    a_hat = shared_a.a_hat
    y = 1.0 - data.g_obs_mw / np.maximum(a_hat, 1e-9)
    folds = list(inner_cv_folds(data.berlin_date, fit_mask))
    scores = {}
    for nb in B3_BIN_GRID:
        err, n = 0.0, 0
        for tr, va in folds:
            m = np.zeros(a_hat.shape, dtype=bool); m[tr] = True
            margin, residual, pot = _b3_inputs(data, a_hat, m)
            br = _binned_response(margin, residual, pot, nb, edges=None)
            if br["bin_centre"].size == 0:
                continue
            shares = np.asarray(data.cohorts.shares, dtype=float)[:, None]
            es = (shares * data.s).sum(axis=0)
            wd = (shares * data.s * data.depth).sum(axis=0)
            with np.errstate(invalid="ignore", divide="ignore"):
                mg = np.where(es > 0, wd / es, 0.0)
            r_va = b3_response_curve({"implied_response": br}, mg[va])
            err += float(np.sum((y[va] - es[va] * r_va) ** 2)); n += va.size
        scores[nb] = err / n if n else np.inf
    best = min(scores, key=scores.get)
    out = _b3_from_shared(data, fit_mask, shared_a, best, None)
    out["cv_scores"] = scores
    out["name"] = "B3-CV"
    return out


def b3_curve(fit, data, depth_grid):
    return b3_response_curve(fit, depth_grid)


# --------------------------------------------------------------------------- B6


B6_GRID = ({"num_leaves": 7, "min_child_samples": 50},
           {"num_leaves": 15, "min_child_samples": 50},
           {"num_leaves": 31, "min_child_samples": 20},
           {"num_leaves": 15, "min_child_samples": 200},
           {"num_leaves": 63, "min_child_samples": 20})


def _b6_features(data, shared_a):
    """Depth z, cohort exposure shares, hour Fourier. Monotone increasing in z."""
    shares = np.asarray(data.cohorts.shares, dtype=float)[:, None]
    es = (shares * data.s).sum(axis=0)
    wd = (shares * data.s * data.depth).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        z = np.where(es > 0, wd / es, 0.0)
    cols = [z.reshape(-1, 1), es.reshape(-1, 1)]
    names = ["depth_z", "exposed_share"]
    for k in range(data.s.shape[0]):
        cols.append((float(data.cohorts.shares[k]) * data.s[k]).reshape(-1, 1))
        names.append(f"exposure_w{k}")
    for n, v in hour_fourier_features(data.real_hour,
                                      np.asarray(data.real_berlin_date)).items():
        cols.append(v.reshape(-1, 1)); names.append(n)
    mono = [1 if n == "depth_z" else 0 for n in names]
    return np.hstack(cols), names, mono, z, es


def fit_b6(data, fit_mask, shared_a):
    """Monotone LightGBM on the derived c-hat, tuned on the selected days only."""
    import lightgbm as lgb

    X, names, mono, z, es = _b6_features(data, shared_a)
    y = 1.0 - data.g_obs_mw / np.maximum(shared_a.a_hat, 1e-9)
    folds = list(inner_cv_folds(data.berlin_date, fit_mask))
    sel = np.flatnonzero(np.asarray(fit_mask, dtype=bool))

    def train(idx, params):
        # The sklearn API with n_jobs=1, matching fit_b5. NOT lgb.train with
        # num_threads=1: that segfaulted here (exit 139), the same libomp clash
        # baselines.py documents -- torch and scikit-learn each ship their own
        # libomp and LightGBM crashes once torch has been imported. B5's
        # configuration is the one this project has validated, so B6 uses it too.
        m = lgb.LGBMRegressor(
            objective="regression", learning_rate=0.05, n_estimators=200,
            monotone_constraints=mono, random_state=INNER_SEED, n_jobs=1,
            verbose=-1, **params)
        m.fit(X[idx], y[idx])
        return m

    scores = {}
    for i, params in enumerate(B6_GRID):
        err, n = 0.0, 0
        for tr, va in folds:
            try:
                m = train(tr, params)
            except Exception:
                continue
            err += float(np.sum((y[va] - m.predict(X[va])) ** 2)); n += va.size
        scores[i] = err / n if n else np.inf
    best = min(scores, key=scores.get)
    model = train(sel, B6_GRID[best])
    return {"name": "B6", "a_hat": shared_a.a_hat, "model": model, "names": names,
            "best_params": B6_GRID[best], "cv_scores": scores,
            "template": X, "exposed_share": es}


def b6_curve(fit, data, depth_grid):
    """r-hat read at FULL exposure, per Amendment 3 A3.2 item 1.

    B6 predicts c-hat, not r. At full exposure (sum_k w_k s_k = 1) the observation
    model gives c-hat = r, which is the only point where the two coincide, so the
    response is read there with the hour terms at their training means. It is an
    extrapolation of B6 into a region it may not have seen; that is a property of
    scoring a c-hat model on an r-metric and is reported as such.
    """
    X = fit["template"]
    names = fit["names"]
    row = X.mean(axis=0, keepdims=True).repeat(depth_grid.size, axis=0)
    row[:, names.index("depth_z")] = depth_grid
    row[:, names.index("exposed_share")] = 1.0
    for k, n in enumerate(names):
        if n.startswith("exposure_w"):
            row[:, k] = float(fit.get("full_exposure_w", 0.0))
    # Full exposure: put the whole fleet in the first cohort column so the weights
    # sum to one, matching sum_k w_k s_k = 1.
    first = next(i for i, n in enumerate(names) if n.startswith("exposure_w"))
    row[:, first] = 1.0
    return np.clip(fit["model"].predict(row), 0.0, 1.0)


# ---------------------------------------------------------------------- M2 family


def make_m2(ablation):
    def _fit(data, fit_mask, shared_a):
        from src.method.stage_a.reservation_depth_model import fit_m2
        return fit_m2(data, np.array([0.0]), ablation=ablation,
                      stage_a=shared_a, train_mask=np.asarray(fit_mask, dtype=bool))
    return _fit


def m2_curve(fit, data, depth_grid):
    return response_curve(fit["p"], fit["knots"], fit["block_shares"], depth_grid)


def build_specs():
    """METHOD_SPECS in the order Amendment 3 section 0.2 lists them."""
    from src.censoring.run_tb import MethodSpec

    by = {a.label: a for a in ABLATIONS}
    return [
        MethodSpec("M2", make_m2(by["M2"]), m2_curve),
        MethodSpec("B3-CV", fit_b3_cv, b3_curve),
        MethodSpec("B6", fit_b6, b6_curve),
        MethodSpec("B3@8", fit_b3_fixed(8, None), b3_curve),
        MethodSpec("B3-H", fit_b3_fixed(None, HIRTH_EDGES), b3_curve),
        MethodSpec("M2-noPool", make_m2(by["M2-noPool"]), m2_curve),
        MethodSpec("M2-noAtom", make_m2(by["M2-noAtom"]), m2_curve),
    ]


# ------------------------------------- free-parameter counts (reporting addition)


def free_params(fit: dict) -> dict:
    """How many free parameters the method actually fitted, per method.

    A reporting addition of 1 Nov 2026, not a criterion. At n = 50 the stage-r sample
    is about 681 quarter-hours while M2 can carry up to ~620 parameters and B3-CV
    between 4 and 64, so neither a win nor a loss can be read without this. The point
    cuts both ways: an M2 win on comparable counts is stronger than it looks, and an
    M2 win at 620 against 8 is weaker.
    """
    out = {"n_free_params": "", "param_detail": "",
           "chosen_lambda": "", "chosen_bins": "", "at_grid_boundary": ""}
    if "p" in fit and "knots" in fit:                      # M2 family
        n_b, n_j = fit["p"].shape
        out["n_free_params"] = int(n_b * n_j)
        lam = fit.get("lambda", "")
        out["param_detail"] = f"{n_b} blocks x {n_j} knots"
        out["chosen_lambda"] = lam
        # Boundary flags, so a reader never has to parse param_detail to see that a
        # grid bound the choice. The ends are read from LAMBDA_GRID itself: until
        # 10 Nov 2026 they were hardcoded as 0.0 and 100.0, which the docs/22 grid
        # widening would have silently falsified (100.0 is interior on the widened
        # grid). Same flag, same semantics, no literal copy of the grid to go stale.
        if isinstance(lam, float):
            from src.method.stage_a.reservation_depth_model import LAMBDA_GRID
            out["at_grid_boundary"] = ("lambda_max" if lam >= max(LAMBDA_GRID) - 1e-9
                                       else "lambda_min" if lam <= min(LAMBDA_GRID)
                                       else "")
    elif "implied_response" in fit:                        # B3 family
        used = int(fit["implied_response"]["bin_centre"].size)
        out["n_free_params"] = used
        nb = fit.get("n_bins", None)
        out["param_detail"] = (f"{used} non-empty bins of {nb} requested"
                               + ("; Hirth edges" if fit.get("bin_edges") else
                                  "; equal-count quantile"))
        out["chosen_bins"] = nb if nb is not None else ""
        if fit.get("cv_scores") and isinstance(nb, int):      # B3-CV only
            out["at_grid_boundary"] = ("bins_min" if nb == min(B3_BIN_GRID) else
                                       "bins_max" if nb == max(B3_BIN_GRID) else "")
    elif "model" in fit:                                   # B6
        b = fit["model"].booster_
        n_trees = int(b.num_trees())
        leaves = int(fit["best_params"].get("num_leaves", 0))
        out["n_free_params"] = n_trees * leaves
        out["param_detail"] = (f"{n_trees} trees x <= {leaves} leaves; "
                               f"min_child_samples="
                               f"{fit['best_params'].get('min_child_samples')}")
    return out
