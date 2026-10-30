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
) -> dict:
    """Shared trainer. `survival_mask` switches on the Wang & Wang objective."""
    cfg = cfg or TrainConfig()
    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)

    x_raw, feature_names = build_latent_features(data, task=task, use_weather=use_weather)
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


def fit_b3(data, cfg: TrainConfig | None = None, n_bins: int = 8, **kw) -> dict:
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
    fit["implied_response"] = _binned_response(
        margin[use], residual[use], exposed_potential[use], n_bins
    )
    fit["residual_curtailment_mw"] = residual
    return fit


def _binned_response(margin, residual, exposed_potential, n_bins: int) -> dict:
    """Ratio of residual curtailment to exposed potential, in equal-count margin bins."""
    if margin.size == 0:
        return {"bin_centre": np.array([]), "r": np.array([]), "n": np.array([])}
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


ALL_BASELINES = {
    "B0": fit_b0,
    "B1": fit_b1,
    "B2": fit_b2,
    "B3": fit_b3,
    "B4": fit_b4,
    "Oracle": fit_oracle,
}
