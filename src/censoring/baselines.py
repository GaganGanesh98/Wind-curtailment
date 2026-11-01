"""Baselines B0-B4 and the oracle (spec section 5).

Every learned baseline uses the **same** multiplicative quantile network as M1's
latent head, with the same optimiser, seed, early stopping and event-day split. Only
the training objective and the training sample differ. That is deliberate: it makes
the comparison a test of *structure and objective*, not of architecture. If the
baselines used a different functional form, a win for M1 could just be the form.

| ID | What it is | Why it is here |
|----|------------|----------------|
| B0 | the TSO day-ahead forecast as-is | status quo |
| B1 | trained on observed G, all quarter-hours, no price | learns curtailment as noise |
| B2 | trained on observed G, negative-price QHs deleted | Jorgensen et al. (2025) |
| B3 | Hirth (2026): fit on the safe window, curtailment = residual, binned response | two-stage safe-period calibration |
| B4 | Wang & Wang (2026): pinball off-exposure + survival loss on exposure | closest prior censored-learning method |
| Oracle | trained on the true A | synthetic benchmark only |

B5 (quantile LightGBM with price and exposure features) and the price-free proxy
baseline are **not** in this module yet: they are listed in CLAUDE_CODE_PROMPT.md as
post-smoke-run work. Nothing here depends on them.

Deferred to the same step, and worth stating so the smoke-run numbers are read with
it in mind: B5 is the baseline that keeps the comparison honest, because it gets the
same information as M1 without the structure. The smoke run therefore cannot yet show
that structure beats information.
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn

from src.censoring.model import (
    FORBIDDEN_FEATURES,
    TAUS,
    MonotoneQuantileHead,
    TrainConfig,
    build_latent_features,
    eventday_split,
    pinball_loss,
    standardise,
)


class PlainQuantileNet(nn.Module):
    """A = F * exp(g(x)) with non-crossing quantiles and no response head.

    Identical to M1's latent head. What it predicts depends on what it is trained on:
    for B1/B2/B4 it is trained on observed G and its prediction is read as the
    estimate of available power, which is exactly the mistake those methods make.
    """

    def __init__(self, in_dim: int, hidden: int = 32, n_quantiles: int = len(TAUS)):
        super().__init__()
        self.latent = MonotoneQuantileHead(in_dim, hidden, n_quantiles)

    def forward(self, x: torch.Tensor, forecast: torch.Tensor) -> torch.Tensor:
        return forecast[:, None] * torch.exp(self.latent(x))


def _empirical_cdf_at(y: torch.Tensor, q: torch.Tensor, taus: torch.Tensor) -> torch.Tensor:
    """F-hat(y) by piecewise-linear interpolation of the predicted quantiles.

    Wang & Wang's survival term needs a CDF value at the observed point. Linear
    interpolation between adjacent predicted quantiles keeps it differentiable in q,
    which `torch.searchsorted` plus gather would not.
    """
    below_first = (y / q[:, 0].clamp(min=1e-6)).clamp(0.0, 1.0) * taus[0]
    widths = (q[:, 1:] - q[:, :-1]).clamp(min=1e-6)
    frac = ((y[:, None] - q[:, :-1]) / widths).clamp(0.0, 1.0)
    steps = (taus[1:] - taus[:-1])[None, :]
    return (below_first + (frac * steps).sum(dim=1)).clamp(1e-6, 1.0 - 1e-4)


def _fit_plain(
    data,
    target: np.ndarray,
    name: str,
    train_subset: np.ndarray | None = None,
    cfg: TrainConfig | None = None,
    task: str = "E1",
    use_weather: bool = True,
    survival_mask: np.ndarray | None = None,
    extra_features: dict[str, np.ndarray] | None = None,
) -> dict:
    """Shared trainer. `survival_mask` switches on the Wang & Wang objective.

    `extra_features` bypasses the latent-head allow-list ON PURPOSE, and only for
    baselines. A baseline is allowed to use a feature M1 is forbidden (that is what
    makes it a baseline), but nothing it is handed may be leakage, so the names are
    still checked against FORBIDDEN_FEATURES.
    """
    cfg = cfg or TrainConfig()
    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)

    x_raw, feature_names = build_latent_features(data, task=task, use_weather=use_weather)
    if extra_features:
        bad = [n for n in extra_features if n in FORBIDDEN_FEATURES]
        if bad:
            raise ValueError(f"Baseline feature(s) {bad} are leakage, not a baseline choice")
        x_raw = np.column_stack([x_raw] + [np.asarray(v, dtype=float)
                                           for v in extra_features.values()])
        feature_names = feature_names + list(extra_features)
    train_mask, val_mask = eventday_split(data.berlin_date, cfg.val_fraction, cfg.seed)
    if train_subset is not None:
        train_mask = train_mask & train_subset
        val_mask = val_mask & train_subset

    x = np.empty_like(x_raw)
    for j in range(x_raw.shape[1]):
        x[:, j], _, _ = standardise(x_raw[:, j], train_mask)

    t = lambda a: torch.as_tensor(a, dtype=torch.float32)  # noqa: E731
    x_t, f_t, y_t, taus_t = t(x), t(data.forecast_mw), t(target), t(TAUS)
    tr = torch.as_tensor(train_mask)
    va = torch.as_tensor(val_mask)
    surv_t = torch.as_tensor(survival_mask) if survival_mask is not None else None

    model = PlainQuantileNet(x.shape[1], hidden=cfg.hidden)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)

    def objective(mask: torch.Tensor) -> torch.Tensor:
        q = model(x_t, f_t)
        if surv_t is None:
            return pinball_loss(y_t[mask], q[mask], taus_t)
        # Wang & Wang: pinball where the sample is a point observation, survival
        # loss -log(1 - F(G)) where it is treated as a lower bound. Every exposed
        # quarter-hour is treated as censored, whether or not anything switched off
        # -- that assumption is the baseline, and spec section 6 H2 predicts it makes
        # B4 overestimate A when compliance is partial.
        point = mask & ~surv_t
        bound = mask & surv_t
        loss = torch.zeros((), dtype=torch.float32)
        if point.any():
            loss = loss + pinball_loss(y_t[point], q[point], taus_t)
        if bound.any():
            cdf = _empirical_cdf_at(y_t[bound], q[bound], taus_t)
            loss = loss - torch.log1p(-cdf).mean()
        return loss

    best_val, best_state, bad, epoch = float("inf"), None, 0, 0
    for epoch in range(cfg.max_epochs):
        model.train()
        opt.zero_grad()
        loss = objective(tr)
        loss.backward()
        opt.step()
        model.eval()
        with torch.no_grad():
            v = float(objective(va))
        if v < best_val - 1e-7:
            best_val, bad = v, 0
            best_state = {k: p.detach().clone() for k, p in model.state_dict().items()}
        else:
            bad += 1
            if bad >= cfg.patience:
                break
    if best_state is not None:
        model.load_state_dict(best_state)

    model.eval()
    with torch.no_grad():
        q = model(x_t, f_t).numpy()
    median = int(np.argmin(np.abs(TAUS - 0.5)))
    return {
        "name": name,
        "model": model,
        "feature_names": feature_names,
        "a_quantiles": q,
        "a_hat": q[:, median],
        "epochs_run": epoch + 1,
        "best_val_objective": best_val,
    }


# ------------------------------------------------------------------- the baselines


def fit_b0(data) -> dict:
    """The published TSO day-ahead forecast, untouched."""
    return {
        "name": "B0",
        "a_hat": data.forecast_mw.copy(),
        "a_quantiles": None,
        "epochs_run": 0,
    }


def fit_b1(data, cfg: TrainConfig | None = None, **kw) -> dict:
    """Naive: trained on observed G over every quarter-hour, with no price features.

    It cannot tell a switched-off quarter-hour from a calm one, so curtailment is
    absorbed as noise and A is biased down wherever censoring happens.
    """
    return _fit_plain(data, data.g_obs_mw, "B1", cfg=cfg, **kw)


def fit_b2(data, cfg: TrainConfig | None = None, **kw) -> dict:
    """Deletion (Jorgensen et al. 2025): negative-price quarter-hours dropped.

    Removes exactly the regime of interest from training. The model is then applied
    to it anyway at prediction time, which is what the deletion literature does.
    """
    keep = data.price_eur_mwh >= 0.0
    return _fit_plain(data, data.g_obs_mw, "B2", train_subset=keep, cfg=cfg, **kw)


# Hirth (2026, arXiv 2609.10053) Fig. 12 bins the pooled wind response on
# profit-margin bands. RESOLVED 1 Nov 2026.
#
# PROVENANCE: read from raster /Image66 p.17 of 2609.10053v1; axis ticks, not
# text-extracted; [read from figure]. The figure is a bitmap, so no text extraction
# could ever have recovered these. The x-axis ticks run
# 100, 50, 20, 10, 5, 0, -5, -10, -20, -50, -100 EUR/MWh of profit margin, giving
# twelve bands, which matches the twelve plotted wind points. Corroborated two ways:
# the negative-side edges coincide exactly with Table 3 (p. 14), and the student
# independently verified the same reading by rendering the page.
#
# These are DEPTH edges (z = -margin), i.e. the exposed side only, where the response
# is defined. The open top band is inf.
HIRTH_FIG12_MARGIN_EDGES_EUR_MWH: tuple[float, ...] = (0.0, 5.0, 10.0, 20.0, 50.0,
                                                       100.0, float("inf"))

# Hirth's own response rates for those six exposed bands, same figure, for the
# plausibility comparison in T-D(v) -- NOT used in any fit.
HIRTH_FIG12_WIND_RESPONSE = (0.25, 0.32, 0.34, 0.45, 0.61, 0.56)

# fit_b3 must NOT silently adopt the edges above. Amendment 4 keeps B3@8 and B3-CV on
# equal-count quantile bins and introduces Hirth's bands only as a SEPARATE comparator
# (B3-H), which passes them explicitly. Before this constant was filled in, fit_b3
# fell back to it whenever it was not None, so setting it would have changed every
# existing B3 fit at once and invalidated the comparison the amendment is trying to
# make. The fallback is therefore removed and the default is quantile bins, stated.
B3_DEFAULT_EDGES: tuple[float, ...] | None = None


def fit_b3(data, cfg: TrainConfig | None = None, n_bins: int = 8,
           bin_edges: tuple[float, ...] | None = None, **kw) -> dict:
    """Hirth (2026): safe-window calibration, residual curtailment, binned response.

    Stage 1 -- fit the potential model on quarter-hours above +5 EUR/MWh only.
    Stage 2 -- curtailment is the residual, max(0, A-hat - G), attributed wholly to
               exposed capacity.
    Stage 3 -- the implied response is the binned ratio of residual curtailment to
               exposed potential, by profit margin (depth below the threshold).

    Hirth states himself that curtailment is not observed by cohort and that error in
    the potential model enters curtailment one for one. That is the weakness this
    baseline is here to exhibit, not a flaw in the implementation.
    """
    safe = data.price_eur_mwh > data.config.safe_price_floor
    fit = _fit_plain(data, data.g_obs_mw, "B3", train_subset=safe, cfg=cfg, **kw)

    a_hat = fit["a_hat"]
    residual = np.maximum(0.0, a_hat - data.g_obs_mw)
    exposed_share = (data.cohorts.shares[:, None] * data.s).sum(axis=0)
    exposed_potential = a_hat * exposed_share

    # Capacity-weighted mean depth, the single profit-margin axis Hirth bins on.
    weighted_depth = (data.cohorts.shares[:, None] * data.s * data.depth).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        margin = np.where(exposed_share > 0, weighted_depth / exposed_share, 0.0)

    use = exposed_potential > 0
    edges = bin_edges if bin_edges is not None else B3_DEFAULT_EDGES
    fit["implied_response"] = _binned_response(
        margin[use], residual[use], exposed_potential[use], n_bins, edges=edges
    )
    fit["bin_source"] = "hirth_fig12" if edges is not None else "equal_count_quantile"
    fit["residual_curtailment_mw"] = residual
    return fit


def _binned_response(margin, residual, exposed_potential, n_bins: int,
                     edges: tuple[float, ...] | None = None) -> dict:
    """Ratio of residual curtailment to exposed potential, binned on profit margin.

    `edges` takes Hirth's own band edges when they are available; otherwise the bins
    are equal-count quantiles, which is an interim choice and is flagged as such on
    the returned fit.
    """
    if margin.size == 0:
        return {"bin_centre": np.array([]), "r": np.array([]), "n": np.array([])}
    if edges is not None:
        edges = np.asarray(edges, dtype=float)
    else:
        edges = np.unique(np.quantile(margin, np.linspace(0, 1, n_bins + 1)))
    if edges.size < 2:
        edges = np.array([margin.min(), margin.max() + 1e-6])
    idx = np.clip(np.digitize(margin, edges[1:-1], right=False), 0, edges.size - 2)
    centres, ratios, counts = [], [], []
    for b in range(edges.size - 1):
        m = idx == b
        if not m.any():
            continue
        centres.append(float(margin[m].mean()))
        ratios.append(float(np.clip(residual[m].sum() / exposed_potential[m].sum(), 0.0, 1.0)))
        counts.append(int(m.sum()))
    return {
        "bin_centre": np.array(centres),
        "r": np.array(ratios),
        "n": np.array(counts),
    }


def b3_response_curve(fit: dict, depth_grid: np.ndarray) -> np.ndarray:
    """B3's implied response read off on the same grid as r-hat and r*."""
    br = fit["implied_response"]
    if br["bin_centre"].size == 0:
        return np.zeros_like(depth_grid, dtype=float)
    return np.interp(depth_grid, br["bin_centre"], br["r"],
                     left=br["r"][0], right=br["r"][-1])


def fit_b4(data, cfg: TrainConfig | None = None, **kw) -> dict:
    """Wang & Wang (2026): pinball off-exposure plus a survival loss on exposure.

    Their censoring indicator is *observed* (a logged grid command); here it is not,
    so the baseline has to assume one, and the natural assumption is exposure. Spec
    section 6 H2 predicts the consequence: the survival term only pushes the
    distribution upward, so B4 should overestimate A when compliance is partial, and
    worst of all under the 50%-compliance response.
    """
    exposed = data.s.max(axis=0) > 0.0
    return _fit_plain(data, data.g_obs_mw, "B4", survival_mask=exposed, cfg=cfg, **kw)


def fit_oracle(data, cfg: TrainConfig | None = None, **kw) -> dict:
    """Trained on the true available power. Synthetic benchmark only -- the floor."""
    return _fit_plain(data, data.a_true_mw, "Oracle", cfg=cfg, **kw)


# ------------------------------------------------- B5 and the price-free proxy


def _day_type(real_dates: np.ndarray) -> np.ndarray:
    """0 = working day, 1 = Saturday, 2 = Sunday. Built on the REAL calendar date.

    German public holidays are not applied: the holiday calendar is federal-state
    specific and is not in the repo. That is a known understatement of the day-type
    effect, flagged rather than guessed (hard rule 9).
    """
    import datetime as _dt

    wd = np.array([_dt.date.fromisoformat(str(d)).weekday() for d in real_dates])
    return np.where(wd == 5, 1, np.where(wd == 6, 2, 0))


def fit_b5(data, cfg: TrainConfig | None = None, **kw) -> dict:
    """Quantile LightGBM on G with price and cohort-exposure features.

    The honest comparison. B5 gets exactly the information M1 gets -- the price, the
    depth below each cohort's threshold, each cohort's exposure, the run lengths --
    but as *features*, with no observation model tying them to a switched-off share.
    If M1 cannot beat B5, the structure is not earning its place and the contribution
    rests on identification and on r-hat alone.

    LightGBM fits one model per quantile, so the quantiles can cross; they are sorted
    afterwards. That is a real weakness of the baseline and is left in, because
    sorting is what a practitioner would do.
    """
    import lightgbm as lgb

    cfg = cfg or TrainConfig()
    exposed_share = (data.cohorts.shares[:, None] * data.s).sum(axis=0)
    weighted_depth = (data.cohorts.shares[:, None] * data.s * data.depth).sum(axis=0)
    from src.censoring.model import cohort_runlength_hours

    runlen = cohort_runlength_hours(data)

    cols = [data.forecast_mw, data.price_eur_mwh, exposed_share, weighted_depth]
    names = ["forecast_mw", "price_eur_mwh", "exposed_share", "weighted_depth"]
    for i, c in enumerate(data.cohorts):
        cols += [data.s[i], data.depth[i], runlen[i]]
        names += [f"s_{c.cohort_id}", f"depth_{c.cohort_id}", f"runlen_{c.cohort_id}"]
    if data.weather_ms is not None:
        cols.append(data.weather_ms)
        names.append("weather_ms")
    x = np.column_stack(cols)

    train_mask, val_mask = eventday_split(data.berlin_date, cfg.val_fraction, cfg.seed)
    y = data.g_obs_mw

    # The no-incentive counterfactual: same weather and forecast, price at the safe
    # level, every exposure, depth and run length set to zero.
    x_safe = x.copy()
    for col, value in enumerate(names):
        if value == "price_eur_mwh":
            x_safe[:, col] = float(data.config.safe_price_floor) + 35.0
        elif value.startswith(("s_", "depth_", "runlen_")) or value in (
            "exposed_share", "weighted_depth"
        ):
            x_safe[:, col] = 0.0

    preds = np.zeros((x.shape[0], len(TAUS)))
    counterfactual = np.zeros_like(preds)
    for j, tau in enumerate(TAUS):
        m = lgb.LGBMRegressor(
            objective="quantile", alpha=float(tau), n_estimators=400,
            learning_rate=0.05, num_leaves=31, min_child_samples=40,
            subsample=0.9, subsample_freq=1, colsample_bytree=0.9,
            random_state=cfg.seed, n_jobs=1, verbose=-1,
        )
        # n_jobs=1 is not a performance choice. torch and scikit-learn each ship
        # their own libomp.dylib, and on macOS LightGBM segfaults (exit 139) with
        # n_jobs > 1 once torch has been imported. Single-threaded is the safe
        # configuration; it costs seconds, and a segfault costs the run.
        m.fit(x[train_mask], y[train_mask],
              eval_X=x[val_mask], eval_y=y[val_mask],
              callbacks=[lgb.early_stopping(50, verbose=False)])
        preds[:, j] = m.predict(x)
        counterfactual[:, j] = m.predict(x_safe)
    preds = np.sort(preds, axis=1)              # LightGBM quantiles can cross
    counterfactual = np.sort(counterfactual, axis=1)

    median = int(np.argmin(np.abs(TAUS - 0.5)))
    return {
        "name": "B5",
        # B5 predicts the OBSERVED G, and with the price and exposure features it can
        # and does reproduce the censoring -- scoring its direct prediction against
        # A_true would be scoring it on a task it was not asked to do, and it lands
        # about 3,400 MW low on censored quarter-hours for exactly that reason.
        # Its estimate of available power is therefore the counterfactual: the same
        # quarter-hour with the incentive switched off (price at the safe level, every
        # exposure and depth zero). That is what a practitioner with this model would
        # actually do, and it tests whether the black box learned the mechanism well
        # enough to extrapolate off the incentive -- which is what H4 claims it cannot.
        "a_quantiles": counterfactual, "a_hat": counterfactual[:, median],
        "g_quantiles": preds, "g_hat": preds[:, median],
        "feature_names": names, "epochs_run": 0,
    }


def fit_proxy(data, cfg: TrainConfig | None = None, **kw) -> dict:
    """Price-free proxy baseline: day type (+ solar day-ahead, when it exists).

    `docs/02_evidence_base.md` section B3: a public-data practitioner project cut
    negative-hour onshore error by 11% using the expected solar and the day type
    alone, with no price and no plant register. Any claim for the mechanism-aware
    model has to clear that, not only the raw TSO forecast.

    Two caveats, both material for how the E1 number should be read:
      1. **The solar day-ahead series is not in the panel yet** (SMARD data_id 125,
         a Phase 3 ingest), so this is the day-type half of the proxy only. It is
         therefore weaker here than the published result it is meant to represent.
      2. Day type is built on the **real** calendar date each base quarter-hour came
         from, not on the synthetic timeline, which is a relabelling.
    """
    day_type = _day_type(data.real_berlin_date).astype(float)
    return _fit_plain(
        data, data.g_obs_mw, "Proxy", cfg=cfg,
        extra_features={"day_type": day_type}, **kw
    )


ALL_BASELINES = {
    "B0": fit_b0,
    "B1": fit_b1,
    "B2": fit_b2,
    "B3": fit_b3,
    "B4": fit_b4,
    "B5": fit_b5,
    "Proxy": fit_proxy,
    "Oracle": fit_oracle,
}
