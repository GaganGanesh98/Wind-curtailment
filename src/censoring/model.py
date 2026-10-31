"""M1 -- the mechanism-aware model (spec section 4).

    A_t      = F_t * exp(g(x^A_t))                 latent available power
    r_k(z)   = sigmoid(a_k + softplus(b)*depth + softplus(d)*runlength)
    c_t      = sum_k w_k,t * s_k,t * r_k(z_t)       switched-off share
    G_t      = A_t * (1 - c_t)                      observation model

Trained end to end by pinball loss on the **observed** G. The quantiles of A are
non-crossing by construction (cumulative softplus increments), and because
(1 - c_t) >= 0 the quantiles of G are exactly (1 - c_t) times the quantiles of A.

Why the latent head is multiplicative
-------------------------------------
The RQ1 kill test found the day-ahead over-forecast behaves as a roughly constant
proportional haircut -- -9.1% overall against -9.3% in windy quarter-hours, with
almost fully overlapping confidence intervals -- not as a fixed MW offset. A
multiplicative head encodes that directly. The additive alternative
A = F + g(x) is kept as an ablation (spec section 2 / Phase 4), not as the default.

Why the response head is monotone
---------------------------------
Assumption I3: r_k is non-decreasing in price depth. `softplus` on the depth and
run-length coefficients makes that structural rather than something the fit has to
discover, so the recovered curve cannot be non-monotone noise.

Feature discipline (hard rule 16 / spec section 4)
--------------------------------------------------
g sees the TSO day-ahead forecast and task-allowed wind only. **No calendar, no
solar, no price, no theta, no s.** Temperature and pressure are admissible only as
air density inside a power-curve transform, never as free features. Hour-of-day is
admissible only on evidence from the I1 placebo and the E1 ablation at gamma > 0.
This is enforced here by `LATENT_ALLOWED_FEATURES` and tested in
`tests/test_leakage.py`, not left to reviewer discipline: price entering g is the one
failure that would let A absorb curtailment and quietly invalidate the whole result.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import torch
from torch import nn

from src.censoring.cohorts import CohortSet

SEED = 42

# The closed covariate set of the latent head. T1 may additionally use ERA5-derived
# columns; T2 may use only D-1 vintages. Anything not listed here is a leak.
LATENT_ALLOWED_FEATURES: dict[str, set[str]] = {
    # Task T1 -- ex-post recovery. ERA5 allowed.
    "T1": {"forecast_mw", "weather_ms", "weather_ms_era5", "air_density"},
    # Task T2 -- day-ahead forecast. True D-1 vintages only.
    "T2": {"forecast_mw", "weather_ms", "weather_ms_icon_d1", "air_density"},
    # The semi-synthetic benchmark: one synthetic weather proxy, no task split.
    "E1": {"forecast_mw", "weather_ms"},
}

# Columns that must never reach any model, in any task (spec section 10, v1.4).
FORBIDDEN_FEATURES = {
    "price_eur_mwh", "price", "hour_mean_price", "depth", "theta", "s", "exposure",
    "id_wind_mw", "id_onshore_mw", "id_offshore_mw", "e_id_mw",   # intraday forecast
    "act_wind_mw", "act_onshore_mw", "act_offshore_mw",            # same-QH actuals
    "redispatch_mw", "redispatch_volume",                          # ex post
    "market_value_published", "marktwert_published",               # released after month end
}

TAUS = np.round(np.arange(0.05, 0.96, 0.05), 2)


def check_latent_features(names: Sequence[str], task: str = "E1") -> None:
    """Raise if the latent head is being handed a feature it must not see.

    Fails loudly rather than dropping the column (hard rule 12): a silently dropped
    feature looks like a passing test.
    """
    if task not in LATENT_ALLOWED_FEATURES:
        raise ValueError(f"Unknown task {task!r}; known: {sorted(LATENT_ALLOWED_FEATURES)}")
    allowed = LATENT_ALLOWED_FEATURES[task]
    forbidden = [n for n in names if n in FORBIDDEN_FEATURES]
    if forbidden:
        raise ValueError(
            f"Forbidden feature(s) {forbidden} offered to the latent head. "
            "These are leakage (spec section 10): price/theta/s would let A absorb "
            "curtailment; intraday, redispatch and same-quarter-hour actuals are not "
            "known at the forecast time."
        )
    outside = [n for n in names if n not in allowed]
    if outside:
        raise ValueError(
            f"Feature(s) {outside} are outside the closed covariate set for task "
            f"{task}: {sorted(allowed)} (hard rule 16)."
        )


# ------------------------------------------------------------------- building blocks


class MonotoneQuantileHead(nn.Module):
    """Non-crossing quantiles via cumulative softplus increments.

    The network emits one free value (the lowest quantile) and n-1 raw increments;
    softplus makes each increment positive, so the cumulative sum is increasing in
    tau by construction. No post-hoc sorting, which would break the gradient.
    """

    def __init__(self, in_dim: int, hidden: int, n_quantiles: int,
                 init_log_spread: float = 0.5):
        super().__init__()
        self.body = nn.Sequential(
            nn.Linear(in_dim, hidden), nn.Tanh(),
            nn.Linear(hidden, hidden), nn.Tanh(),
        )
        self.head = nn.Linear(hidden, n_quantiles)
        # Initialise so that A starts at roughly F, with a modest spread. Without
        # this the default bias of 0 makes every increment softplus(0) = 0.693, so
        # the top quantile starts at exp(0.693 * (n-1)) * F -- about 270,000 * F at
        # 19 quantiles. Nothing recovers from that in a few hundred full-batch steps,
        # and the symptom is subtle: every learned method, the oracle included, scores
        # far worse than the raw forecast.
        with torch.no_grad():
            nn.init.normal_(self.head.weight, std=0.01)
            self.head.bias.zero_()
            self.head.bias[0] = -init_log_spread / 2.0
            step = init_log_spread / max(1, n_quantiles - 1)
            self.head.bias[1:] = float(np.log(np.expm1(step)))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        raw = self.head(self.body(x))
        first = raw[:, :1]
        increments = nn.functional.softplus(raw[:, 1:])
        return torch.cat([first, first + torch.cumsum(increments, dim=1)], dim=1)


# Knots for the piecewise-linear response head, in EUR/MWh of depth below theta.
# Dense where the observations are -- the median exposed depth is about 1.4 EUR/MWh
# and the 90th percentile about 34 -- and sparse out to 300, which covers 99% of
# exposed cohort-quarter-hours. Fixed once, here, and never chosen per r* shape.
RESPONSE_KNOTS = (0.0, 1.0, 2.5, 5.0, 7.5, 10.0, 15.0, 20.0, 30.0, 40.0,
                  55.0, 75.0, 100.0, 150.0, 300.0)


class PiecewiseLinearResponseHead(nn.Module):
    """PRIMARY response head: monotone piecewise-linear in depth below theta.

        r_k(d, L) = clamp( base_k + sum_j inc_j * ramp_j(d) + beta * L , 0, 1 )

    with base_k = sigmoid(intercept_k) in (0, 1), every inc_j = softplus(.) >= 0,
    beta = softplus(.) >= 0, and ramp_j(d) the fraction of segment j below d. Every
    term is non-negative, so r is non-decreasing in depth and in run length by
    construction (assumption I3), exactly as the sigmoid head was -- but without
    imposing a sigmoid *shape*.

    Why this is now primary (spec v1.6)
    -----------------------------------
    The sigmoid head could not represent two of the three r* shapes in the E1 design.
    A step response needs r to jump to 1 immediately; a 50%-compliance response needs
    r flat at 0.5 at every depth. A sigmoid in depth can do neither, so the week-6
    criterion (a) failed for both shapes at *every* B3 bin count -- a failure of the
    functional form, not of the method. This head represents all three:

        step      base_k -> 1, all increments -> 0
        half      base_k -> 0.5, all increments -> 0
        logistic  increments trace the curve

    Spec section 4 offered it as the alternative from the start ("or a monotone
    piecewise-linear function with non-negative increments"). The sigmoid is retained
    as `SigmoidResponseHead` for the ablation, so the choice stays testable rather
    than asserted.

    Beyond the last knot r is flat in depth. That is a real limitation, kept
    deliberately: extrapolating a response beyond the deepest prices ever observed
    would be inventing behaviour, and 99% of exposed cohort-quarter-hours sit inside
    the knot range.
    """

    def __init__(self, group_index: np.ndarray, knots: Sequence[float] = RESPONSE_KNOTS):
        super().__init__()
        self.register_buffer("group_index", torch.as_tensor(group_index, dtype=torch.long))
        knots_t = torch.as_tensor(knots, dtype=torch.float32)
        self.register_buffer("knots", knots_t)
        self.register_buffer("widths", (knots_t[1:] - knots_t[:-1]).clamp(min=1e-6))
        n_groups = int(group_index.max()) + 1
        # Start near r = 0.27 at depth 0 with small increments, so the fit begins in
        # the interior of [0, 1] rather than saturated at either end.
        self.intercept = nn.Parameter(torch.full((n_groups,), -1.0))
        self.increment_raw = nn.Parameter(
            torch.full((len(knots) - 1,), float(np.log(np.expm1(0.02))))
        )
        self.runlen_raw = nn.Parameter(torch.tensor(float(np.log(np.expm1(0.005)))))

    def _ramps(self, depth: torch.Tensor) -> torch.Tensor:
        """Fraction of each segment lying below `depth`. Shape (..., n_segments)."""
        lo = self.knots[:-1]
        return ((depth.unsqueeze(-1) - lo) / self.widths).clamp(0.0, 1.0)

    def forward(self, depth: torch.Tensor, runlength: torch.Tensor) -> torch.Tensor:
        base = torch.sigmoid(self.intercept[self.group_index])[:, None]
        inc = nn.functional.softplus(self.increment_raw)
        shape = (self._ramps(depth) * inc).sum(dim=-1)
        beta = nn.functional.softplus(self.runlen_raw)
        return (base + shape + beta * runlength).clamp(0.0, 1.0)

    def curve(self, depth_grid: np.ndarray, runlength: float = 0.0) -> np.ndarray:
        with torch.no_grad():
            g = torch.as_tensor(depth_grid, dtype=torch.float32)
            inc = nn.functional.softplus(self.increment_raw)
            shape = (self._ramps(g) * inc).sum(dim=-1)[None, :]
            base = torch.sigmoid(self.intercept)[:, None]
            beta = nn.functional.softplus(self.runlen_raw)
            r = (base + shape + beta * runlength).clamp(0.0, 1.0)
        return r.numpy()


class SigmoidResponseHead(nn.Module):
    """ABLATION head: r_k(z) = sigmoid(a_k + softplus(b)*depth + softplus(d)*runlength).

    Was the primary head until spec v1.6. Kept so the "does the functional form
    matter?" ablation can be run rather than argued.

    `group_index` maps each legal cohort to a parameter group. In K-cohort mode that
    is the identity, so every cohort has its own intercept. In two-cohort mode it maps
    to the macro-cohort, which **pools the response parameters while leaving exposure
    and depth per legal cohort** (rule 18). The slope parameters are shared in both
    modes: a shared shape with per-group offsets, as spec section 4 specifies.
    """

    def __init__(self, group_index: np.ndarray):
        super().__init__()
        self.register_buffer("group_index", torch.as_tensor(group_index, dtype=torch.long))
        n_groups = int(group_index.max()) + 1
        self.intercept = nn.Parameter(torch.full((n_groups,), -1.0))
        # softplus(x) = s  =>  x = log(exp(s) - 1). Start the depth slope near
        # 0.03 per EUR/MWh (so a 25 EUR/MWh depth moves the logit by ~0.75) and the
        # run-length slope near 0.01 per hour. softplus(-1) = 0.31 would have
        # saturated the sigmoid at any realistic depth before the fit began.
        self.depth_raw = nn.Parameter(torch.tensor(float(np.log(np.expm1(0.03)))))
        self.runlen_raw = nn.Parameter(torch.tensor(float(np.log(np.expm1(0.01)))))

    def forward(self, depth: torch.Tensor, runlength: torch.Tensor) -> torch.Tensor:
        """depth, runlength: (K, T). Returns r of shape (K, T)."""
        a = self.intercept[self.group_index][:, None]
        b = nn.functional.softplus(self.depth_raw)
        d = nn.functional.softplus(self.runlen_raw)
        return torch.sigmoid(a + b * depth + d * runlength)

    def curve(self, depth_grid: np.ndarray, runlength: float = 0.0) -> np.ndarray:
        """r per group on a depth grid, for plotting and for the r-hat metric."""
        with torch.no_grad():
            g = torch.as_tensor(depth_grid, dtype=torch.float32)[None, :]
            n_groups = self.intercept.shape[0]
            a = self.intercept[:, None]
            b = nn.functional.softplus(self.depth_raw)
            d = nn.functional.softplus(self.runlen_raw)
            r = torch.sigmoid(a + b * g.expand(n_groups, -1) + d * runlength)
        return r.numpy()


RESPONSE_HEADS = {
    "piecewise": PiecewiseLinearResponseHead,   # primary (spec v1.6)
    "sigmoid": SigmoidResponseHead,             # ablation
}


class MechanismAwareM1(nn.Module):
    """The full observation model. `forward` returns quantiles of G, not of A."""

    def __init__(self, in_dim: int, group_index: np.ndarray, hidden: int = 32,
                 n_quantiles: int = len(TAUS), response_head: str = "piecewise",
                 latent_form: str = "multiplicative", additive_scale: float = 1000.0):
        super().__init__()
        if response_head not in RESPONSE_HEADS:
            raise ValueError(
                f"response_head {response_head!r} not in {sorted(RESPONSE_HEADS)}"
            )
        if latent_form not in ("multiplicative", "additive"):
            raise ValueError(f"latent_form {latent_form!r} unknown")
        self.latent = MonotoneQuantileHead(in_dim, hidden, n_quantiles)
        self.response = RESPONSE_HEADS[response_head](group_index)
        self.response_head_name = response_head
        self.latent_form = latent_form
        # The latent head emits a log-ratio, order 0.1-1. In additive mode that has
        # to become MW, so it is scaled to the forecast's own scale.
        self.additive_scale = float(additive_scale)

    def latent_quantiles(self, x: torch.Tensor, forecast: torch.Tensor) -> torch.Tensor:
        """A quantiles. Multiplicative F * exp(g(x)), or additive F + g(x).

        Multiplicative is the default and the spec's form, because the kill test
        found the over-forecast behaves as a roughly constant ~9% proportional
        haircut (-9.1% overall against -9.3% in windy quarter-hours) rather than a
        fixed MW offset. The additive form exists to test that claim rather than
        assert it, and is clamped at zero because negative available power is not a
        thing.
        """
        if self.latent_form == "additive":
            return (forecast[:, None] + self.latent(x) * self.additive_scale).clamp(min=0.0)
        return forecast[:, None] * torch.exp(self.latent(x))

    def curtailed(self, shares: torch.Tensor, s: torch.Tensor, depth: torch.Tensor,
                  runlength: torch.Tensor) -> torch.Tensor:
        r = self.response(depth, runlength)
        c = (shares[:, None] * s * r).sum(dim=0)
        return c.clamp(0.0, 1.0)

    def forward(self, x, forecast, shares, s, depth, runlength):
        a_q = self.latent_quantiles(x, forecast)
        c = self.curtailed(shares, s, depth, runlength)
        return a_q * (1.0 - c)[:, None], a_q, c


# ------------------------------------------------------------------------- training


def pinball_loss(y: torch.Tensor, q_pred: torch.Tensor, taus: torch.Tensor) -> torch.Tensor:
    """Mean pinball loss over quantiles. y: (T,), q_pred: (T, n_taus)."""
    err = y[:, None] - q_pred
    return torch.maximum(taus[None, :] * err, (taus[None, :] - 1.0) * err).mean()


@dataclass
class TrainConfig:
    hidden: int = 32
    lr: float = 0.01
    # Budget, corrected 30 Oct 2026. At patience 60 early stopping fired on the
    # oracle at ~195 epochs while M1 trained 400-560, and the oracle scored *worse*
    # than M1 -- an artefact of unequal optimisation budget, not of information.
    # With patience 250 the ordering is restored (oracle best, M1 second, difference
    # not significant) and M1's wins over B1-B4 grow rather than shrink. Early
    # stopping is now a safety net, not a budget cap, and is identical across methods.
    max_epochs: int = 2000
    patience: int = 250
    val_fraction: float = 0.2
    seed: int = SEED
    verbose: bool = False


def eventday_split(days: np.ndarray, val_fraction: float, seed: int = SEED):
    """Train/validation split by whole Berlin-local event-day, never by quarter-hour.

    Days are drawn at random rather than taken as a final block, because the synthetic
    timeline is a reordering of the real one and a trailing block would be a seasonal
    slice. On real data (Phase 3) the split is a rolling origin with a 7-day embargo
    instead -- this function is for E1 only.
    """
    uniq = np.unique(days)
    rng = np.random.default_rng(seed)
    val_days = set(rng.choice(uniq, size=max(1, int(round(val_fraction * len(uniq)))),
                              replace=False).tolist())
    is_val = np.array([d in val_days for d in days], dtype=bool)
    return ~is_val, is_val


def standardise(x: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, float, float]:
    mu = float(x[mask].mean())
    sd = float(x[mask].std()) or 1.0
    return (x - mu) / sd, mu, sd


def build_latent_features(
    data, task: str = "E1", use_weather: bool = True, allow_price: bool = False
) -> tuple[np.ndarray, list[str]]:
    """Assemble x^A and check it against the allow-list before anything is trained.

    `allow_price=True` deliberately puts the price into the latent head, bypassing
    hard rule 16. It exists for exactly one purpose: the A7 ablation, which shows
    what the leakage rule is protecting against. When price is visible to g, A can
    absorb the curtailment and the response head has nothing left to explain, so r̂
    collapses while G-fit looks fine -- the failure is invisible in the headline
    error and only shows up in r̂. Keeping it runnable turns the rule into evidence
    rather than an assertion. It must never be set anywhere else.
    """
    names = ["forecast_mw"]
    cols = [data.forecast_mw]
    if use_weather and data.weather_ms is not None:
        names.append("weather_ms")
        cols.append(data.weather_ms)
    if allow_price:
        names.append("price_eur_mwh")
        cols.append(data.price_eur_mwh)
    else:
        check_latent_features(names, task=task)
    return np.column_stack(cols).astype(np.float64), names


def cohort_runlength_hours(data) -> np.ndarray:
    """Run length in hours per cohort and quarter-hour, on the cohort's own clock.

    An hour-clock cohort sees the length of the run of negative *hours*; a
    quarter-hour-clock cohort sees the run of negative *quarter-hours*, expressed in
    hours so the two are on one scale and share a coefficient.
    """
    from src.censoring.cohorts import QH_CLOCK, build_clock_features

    clock = build_clock_features(data.ts_utc_ns, data.price_eur_mwh)
    rows = []
    for c in data.cohorts:
        if c.clock == QH_CLOCK:
            rows.append(clock.qh_run_length / 4.0)
        else:
            rows.append(clock.hour_run_length.astype(float))
    return np.stack(rows)


@dataclass(frozen=True)
class Ablation:
    """One rung of the ablation ladder: M1 with exactly one piece changed.

    An ablation is not a baseline. A baseline is somebody else's method, and it
    answers "is this better than what exists?". An ablation is *this* method with a
    component switched off, same code, same data, same seed, and it answers "which
    part is doing the work?" -- which is the question a method contribution has to
    answer and which no external baseline can.

    Every field defaults to the full model, so each rung differs from `FULL` in one
    place only.
    """

    label: str
    name: str
    piece_removed: str
    response_head: str = "piecewise"
    latent_form: str = "multiplicative"
    use_weather: bool = True
    exposure_mode: str = "rules"     # "rules" | "common_zero" | "always_on"
    cohort_mode: str = "K"           # "K" | "two" | "one"
    price_in_latent: bool = False

    def differs_from_full(self) -> list[str]:
        full = ABLATION_FULL
        return [f for f in ("response_head", "latent_form", "use_weather",
                            "exposure_mode", "cohort_mode", "price_in_latent")
                if getattr(self, f) != getattr(full, f)]


ABLATION_FULL = Ablation(
    label="M1", name="full model", piece_removed="nothing",
)


def apply_exposure_ablation(data, mode: str):
    """Exposure, depth and run length as the ablated model sees them.

    "rules"     -- s_k and the depth below each cohort's own theta, from the EEG
                   rule table. This is the method.
    "always_on" -- every cohort exposed in every quarter-hour, with depth measured
                   below zero instead of below theta. The model still sees that the
                   price is negative and how far; it no longer knows *who is
                   exposed*. This is what isolates the value of the legal structure
                   as opposed to the price signal.
    """
    if mode == "rules":
        return data.s, data.depth, cohort_runlength_hours(data)
    if mode == "common_zero":
        # A2b. One common threshold at zero for every cohort: the model knows the
        # price is negative and how far below zero it is, but nothing about who is
        # legally exposed. This is what a modeller without the rule table would
        # actually assume, and it is the fair measure of what the rule table buys.
        # A2 ("always_on") is the harsher version -- it asserts that everyone is
        # exposed at every price, which is not an absence of structure but a false
        # one, so A2's cost is an upper bound and A2b's is the honest number.
        k, n = data.s.shape
        neg = (data.price_eur_mwh < 0.0).astype(float)
        s_new = np.tile(neg, (k, 1))
        depth = np.tile(np.maximum(0.0, -data.price_eur_mwh), (k, 1)) * s_new
        return s_new, depth, cohort_runlength_hours(data)
    if mode == "always_on":
        k, n = data.s.shape
        s = np.ones((k, n), dtype=float)
        depth = np.tile(np.maximum(0.0, -data.price_eur_mwh), (k, 1))
        return s, depth, cohort_runlength_hours(data)
    raise ValueError(f"exposure_mode {mode!r} unknown")


def apply_cohort_ablation(data, s, depth, runlen, mode: str):
    """Cohort structure as the ablated model sees it.

    "K"   -- every legal cohort separately (the rule table).
    "two" -- the rule-18 fallback: response parameters pooled per clock, exposure
             and depth still per legal cohort.
    "one" -- a single cohort carrying the capacity-weighted exposed share and the
             capacity-weighted mean depth. This is what a modeller without the rule
             table would build: one fleet, one threshold, one response.
    """
    w = data.cohorts.shares
    if mode == "K":
        return w, s, depth, runlen, np.arange(len(w))
    if mode == "two":
        return w, s, depth, runlen, data.cohorts.macro_index()
    if mode == "one":
        exposed = (w[:, None] * s).sum(axis=0)
        with np.errstate(invalid="ignore", divide="ignore"):
            mean_depth = np.where(
                exposed > 0, (w[:, None] * s * depth).sum(axis=0) / np.maximum(exposed, 1e-12), 0.0
            )
            mean_rl = np.where(
                exposed > 0, (w[:, None] * s * runlen).sum(axis=0) / np.maximum(exposed, 1e-12), 0.0
            )
        return (np.array([1.0]), exposed[None, :], mean_depth[None, :],
                mean_rl[None, :], np.array([0]))
    raise ValueError(f"cohort_mode {mode!r} unknown")


def fit_m1(
    data,
    train_cfg: TrainConfig | None = None,
    task: str = "E1",
    use_weather: bool = True,
    two_cohort: bool = False,
    response_head: str = "piecewise",
    ablation: "Ablation | None" = None,
) -> dict:
    """Fit M1 on the observed G. Returns the model and its predictions.

    `ablation` overrides the individual switches; it is the supported way to run a
    rung of the ladder, so that every rung differs from the full model in exactly
    one recorded place.
    """
    cfg = train_cfg or TrainConfig()
    ab = ablation or ABLATION_FULL
    if ablation is not None:
        response_head = ab.response_head
        use_weather = ab.use_weather
    torch.manual_seed(cfg.seed)
    np.random.seed(cfg.seed)

    x_raw, feature_names = build_latent_features(
        data, task=task, use_weather=use_weather,
        allow_price=ab.price_in_latent,
    )
    s_in, depth_in, rl_in = apply_exposure_ablation(data, ab.exposure_mode)
    cohort_mode = ab.cohort_mode if ablation is not None else ("two" if two_cohort else "K")
    shares, s_in, depth_in, runlen, group_index = apply_cohort_ablation(
        data, s_in, depth_in, rl_in, cohort_mode
    )

    train_mask, val_mask = eventday_split(data.berlin_date, cfg.val_fraction, cfg.seed)

    x = np.empty_like(x_raw)
    for j in range(x_raw.shape[1]):
        x[:, j], _, _ = standardise(x_raw[:, j], train_mask)

    t = lambda a: torch.as_tensor(a, dtype=torch.float32)  # noqa: E731
    x_t, f_t = t(x), t(data.forecast_mw)
    g_t = t(data.g_obs_mw)
    shares_t, s_t, depth_t, rl_t = (t(shares), t(s_in), t(depth_in), t(runlen))
    taus_t = t(TAUS)
    tr, va = torch.as_tensor(train_mask), torch.as_tensor(val_mask)

    model = MechanismAwareM1(x.shape[1], group_index, hidden=cfg.hidden,
                             response_head=response_head,
                             latent_form=ab.latent_form)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lr)

    best_val, best_state, bad = float("inf"), None, 0
    for epoch in range(cfg.max_epochs):
        model.train()
        opt.zero_grad()
        g_q, _, _ = model(x_t, f_t, shares_t, s_t, depth_t, rl_t)
        loss = pinball_loss(g_t[tr], g_q[tr], taus_t)
        loss.backward()
        opt.step()

        model.eval()
        with torch.no_grad():
            g_q, _, _ = model(x_t, f_t, shares_t, s_t, depth_t, rl_t)
            v = float(pinball_loss(g_t[va], g_q[va], taus_t))
        if v < best_val - 1e-7:
            best_val, bad = v, 0
            best_state = {k: p.detach().clone() for k, p in model.state_dict().items()}
        else:
            bad += 1
            if bad >= cfg.patience:
                break
        if cfg.verbose and epoch % 50 == 0:
            print(f"  epoch {epoch:4d}  train {float(loss):.3f}  val {v:.3f}")

    if best_state is not None:
        model.load_state_dict(best_state)

    model.eval()
    with torch.no_grad():
        g_q, a_q, c = model(x_t, f_t, shares_t, s_t, depth_t, rl_t)

    median = int(np.argmin(np.abs(TAUS - 0.5)))
    return {
        "name": ab.label,
        "ablation": ab,
        "piece_removed": ab.piece_removed,
        "differs_from_full": ab.differs_from_full(),
        "response_head": response_head,
        "cohort_mode": cohort_mode,
        "shares": shares,
        "model": model,
        "feature_names": feature_names,
        "a_quantiles": a_q.numpy(),
        "g_quantiles": g_q.numpy(),
        "a_hat": a_q.numpy()[:, median],
        "g_hat": g_q.numpy()[:, median],
        "c_hat": c.numpy(),
        "epochs_run": epoch + 1,
        "best_val_pinball": best_val,
        "two_cohort": cohort_mode == "two",
        "group_index": group_index,
    }


def m1_response_curve(fit: dict, data, depth_grid: np.ndarray) -> np.ndarray:
    """Capacity-weighted pooled r-hat on a depth grid.

    r* is shared across cohorts in the generator, so the quantity comparable with it
    -- and with B3's single pooled curve -- is the capacity-weighted mean of the
    per-cohort curves.
    """
    per_group = fit["model"].response.curve(depth_grid)
    group_index = fit["group_index"]
    shares = fit.get("shares", data.cohorts.shares)
    out = np.zeros_like(depth_grid, dtype=float)
    for i, w in enumerate(shares):
        out += w * per_group[group_index[i]]
    return out / shares.sum()
