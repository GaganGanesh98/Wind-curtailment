"""Semi-synthetic censoring generator for E1 (spec section 7).

The point of E1 is a benchmark with **known truth**: we need A_true, c_true and r* to
be known so that recovery can be scored directly, which real data never allows.

Construction
------------
1. Base = quarter-hours of the real panel whose day-ahead price is above
   +5 EUR/MWh. In those the fleet had no incentive to switch off, so the observed
   actual wind is taken as the true available power: **A_true := act_wind_mw**.
   (Hirth 2026 uses the same > 5 EUR/MWh safe window to calibrate his potential
   model, and spec section 7 adopts it. I1 is not perfect there -- Hirth finds 4.2%
   curtailment already in the 0-5 band, which is why the band is excluded, not
   merely the negative one.)
2. Those base quarter-hours are laid out on a **synthetic contiguous timeline** of
   whole days. Removing the real negative-price periods would otherwise leave gaps,
   and a run length is only meaningful on a contiguous series. Within each stretch of
   kept quarter-hours the real ordering of A_true is preserved, so the diurnal and
   weather structure survives; only the joins between stretches are artificial.
   The timeline is placed in calendar year 2026 so the staircase cohort sits at its
   2 h step, matching the real sample.
3. Synthetic negative-price episodes are injected. Episode lengths are drawn from the
   real negative-run distribution measured on **both clocks** (hourly runs in hours,
   plus deliberate sub-hour episodes that leave the hourly mean positive). Depths are
   drawn from the real negative quarter-hour price distribution. Episode placement is
   confounded with the forecast through gamma: at gamma = 0 placement is uniform, and
   as gamma grows the episodes concentrate on windy periods, which is the condition
   that makes "low wind" and "high wind, switched off" hard to tell apart.
4. theta and s come from the real rule logic in `cohorts.py` with placeholder award
   values. A known response r* is applied to the depth below theta, and

       c_true = sum_k w_k s_k r*(depth_k),      G_syn = A_true * (1 - c_true) + noise.

Design choices worth stating because they bound what E1 can show
----------------------------------------------------------------
- **r* is shared across cohorts** (no per-cohort offsets) in this version. The
  identification therefore comes purely from exposure differing across cohorts, which
  is the cleanest test of the structure, and it leaves one well-defined true curve to
  compare against B3's pooled response. Cohort heterogeneity in r is a later arm.
- **r* depends on depth only, not on run length**, even though the model has a
  run-length term. That is deliberate: it tests that the model does not invent a
  run-length effect that is not there. Hirth's Table A11 suggests a real one, so a
  run-length arm belongs in the full grid.
- The censoring rate is defined as the share of quarter-hours given a **negative
  synthetic price**. The realised exposed share and the realised share with
  c_true > 0 are both lower and are reported as diagnostics, never assumed equal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from src.censoring.cohorts import (
    CohortSet,
    build_clock_features,
    curtailed_share,
    placeholder_cohort_set,
    theta_and_exposure,
)

BERLIN = ZoneInfo("Europe/Berlin")
REPO_ROOT = Path(__file__).resolve().parents[2]
PANEL_PATH = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"

QH_PER_DAY = 96
STEP_NS = 15 * 60 * 1_000_000_000
# Synthetic timeline anchor. 2026 puts the staircase cohort on its 2 h step.
SYNTH_START = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

R_SHAPES = ("step", "logistic", "half")


@dataclass(frozen=True)
class SyntheticConfig:
    """Every knob of the generator. Saved alongside each result (spec section 7)."""

    area: str = "DE"
    censoring_rate: float = 0.20
    gamma: float = 0.0
    r_shape: str = "logistic"
    seed: int = 42
    mv_eur_mwh: float = 45.0
    safe_price_floor: float = 5.0
    # Logistic r*: half the exposed capacity switches off at this depth below theta.
    r_depth_half_eur_mwh: float = 25.0
    r_depth_scale_eur_mwh: float = 12.0
    r_half_level: float = 0.5
    # Share of episodes that are sub-hour, i.e. negative quarter-hours inside an hour
    # whose mean stays positive. These are the quarter-hours that separate the two
    # clocks, so the K-cohort structure is only identified if some exist.
    subhour_episode_share: float = 0.25
    observation_noise_mw: float = 0.0
    with_weather_proxy: bool = True
    weather_noise_ms: float = 0.6
    # Fleet power curve used only to turn A_true into a plausible wind speed.
    curve_v50_ms: float = 9.0
    curve_k: float = 1.6

    def __post_init__(self) -> None:
        if self.r_shape not in R_SHAPES:
            raise ValueError(f"r_shape {self.r_shape!r} not in {R_SHAPES}")
        if not 0.0 < self.censoring_rate < 1.0:
            raise ValueError(f"censoring_rate {self.censoring_rate} must be in (0, 1)")


@dataclass
class SyntheticData:
    """One realisation of the benchmark. Everything the models and metrics need."""

    config: SyntheticConfig
    cohorts: CohortSet
    ts_utc_ns: np.ndarray        # synthetic contiguous timeline
    berlin_date: np.ndarray      # event-day label on the SYNTHETIC timeline
    real_berlin_date: np.ndarray  # the real Berlin date each base QH came from
    forecast_mw: np.ndarray      # F_t, the TSO day-ahead forecast (real)
    a_true_mw: np.ndarray        # A_t, the true available power (real actual wind)
    price_eur_mwh: np.ndarray    # synthetic day-ahead price
    theta: np.ndarray            # (K, T)
    s: np.ndarray                # (K, T) exposure
    depth: np.ndarray            # (K, T) depth below theta, 0 where unexposed
    r_true: np.ndarray           # (K, T) the true response r*
    c_true: np.ndarray           # (T,) true switched-off share
    g_obs_mw: np.ndarray         # G_t, what the model actually sees
    weather_ms: np.ndarray | None
    diagnostics: dict = field(default_factory=dict)

    @property
    def censored(self) -> np.ndarray:
        """Quarter-hours where something was actually switched off."""
        return self.c_true > 0.0

    @property
    def exposed_any(self) -> np.ndarray:
        return self.s.max(axis=0) > 0.0

    def save_config(self, path: Path) -> None:
        payload = {
            "config": asdict(self.config),
            "cohorts": [
                {
                    "cohort_id": c.cohort_id,
                    "rule_id": c.rule_id,
                    "clock": c.clock,
                    "run_length_h": c.run_length_h,
                    "subject_to_s51": c.subject_to_s51,
                    "in_support": c.in_support,
                    "aw_eur_mwh": c.aw_eur_mwh,
                    "capacity_share": c.capacity_share,
                    "macro": c.macro,
                }
                for c in self.cohorts
            ],
            "diagnostics": self.diagnostics,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


# --------------------------------------------------------------------- the response


def true_response(depth: np.ndarray, cfg: SyntheticConfig) -> np.ndarray:
    """r*(depth), the known fraction of exposed capacity that switches off.

    All three shapes are non-decreasing in depth, matching assumption I3.

    step      -- full compliance the moment the threshold is crossed.
    logistic  -- partial, smooth compliance; the realistic case.
    half      -- a constant fraction complies, whatever the depth. This is the shape
                 that should hurt B4 most (spec section 6, H2): B4 treats every
                 exposed quarter-hour as a lower bound and its survival term only
                 pushes A upward, so with half the fleet never responding it should
                 overestimate A.
    """
    d = np.asarray(depth, dtype=float)
    if cfg.r_shape == "step":
        return (d > 0.0).astype(float)
    if cfg.r_shape == "half":
        return np.where(d > 0.0, cfg.r_half_level, 0.0)
    z = (d - cfg.r_depth_half_eur_mwh) / cfg.r_depth_scale_eur_mwh
    return np.where(d > 0.0, 1.0 / (1.0 + np.exp(-z)), 0.0)


def true_response_curve(
    cfg: SyntheticConfig, depth_grid: np.ndarray
) -> np.ndarray:
    """r* evaluated on a depth grid -- the curve r-hat is scored against."""
    return true_response(depth_grid, cfg)


# ------------------------------------------------------------------- the base panel


def load_base(area: str, safe_price_floor: float) -> dict[str, np.ndarray]:
    """Real quarter-hours with price above the safe floor, in time order.

    Returns the forecast, the actual wind (which becomes A_true) and the real
    negative-price statistics the generator samples from.
    """
    if not PANEL_PATH.exists():
        raise FileNotFoundError(
            f"Panel not found at {PANEL_PATH}. Run src/build_panel.py first."
        )
    df = (
        pl.scan_parquet(PANEL_PATH)
        .filter(pl.col("area") == area)
        .sort("ts_utc")
        .select(["ts_utc", "berlin_date", "price_eur_mwh", "da_wind_mw",
                 "act_wind_mw"])
        .collect()
    )
    if df.height == 0:
        raise ValueError(f"No rows for area {area!r} in {PANEL_PATH}")

    price_all = df["price_eur_mwh"].to_numpy()
    # The kill-test panel stores ts_utc in MILLISECONDS (build_panel.py); cohorts.py
    # works in nanoseconds. Convert here, at the single boundary, and assert it, so a
    # future unit change fails loudly instead of silently shifting every timestamp.
    ts_ms = df["ts_utc"].to_numpy().astype(np.int64)
    if ts_ms.size > 1 and int(ts_ms[1] - ts_ms[0]) != 15 * 60 * 1000:
        raise ValueError(
            f"Expected panel ts_utc in milliseconds with a 15-minute step; got a step "
            f"of {int(ts_ms[1] - ts_ms[0])}. Check src/build_panel.py."
        )
    ts_all = ts_ms * 1_000_000

    # Real negative-price statistics, measured on the full contiguous series so both
    # clocks are correct, before any filtering.
    clock_real = build_clock_features(ts_all, price_all)
    neg_qh = price_all < 0.0
    neg_hour_runs = _run_lengths_of_true_blocks(clock_real.hour_mean_price < 0.0, step=4)

    keep = (
        np.isfinite(price_all)
        & np.isfinite(df["da_wind_mw"].to_numpy())
        & np.isfinite(df["act_wind_mw"].to_numpy())
        & (price_all > safe_price_floor)
    )
    n_keep = int(keep.sum())
    n_days = (n_keep // QH_PER_DAY) * QH_PER_DAY
    if n_days == 0:
        raise ValueError(f"Only {n_keep} usable base quarter-hours for {area}")

    idx = np.flatnonzero(keep)[:n_days]
    return {
        "forecast_mw": df["da_wind_mw"].to_numpy()[idx],
        "a_true_mw": df["act_wind_mw"].to_numpy()[idx],
        # The real calendar date each kept quarter-hour came from. The synthetic
        # timeline is a relabelling, so a day-type feature built on it would be
        # noise; the price-free proxy baseline needs the real one to mean anything.
        "real_berlin_date": df["berlin_date"].to_numpy()[idx],
        "real_negative_prices": price_all[neg_qh],
        "real_hour_run_lengths": neg_hour_runs,
        "n_base_available": n_keep,
        "n_base_used": n_days,
        "n_real_negative_qh": int(neg_qh.sum()),
    }


def _run_lengths_of_true_blocks(flag_qh: np.ndarray, step: int) -> np.ndarray:
    """Lengths of maximal True runs, measured every `step` elements (hour -> 4 QHs)."""
    hourly_flag = flag_qh[::step]
    out: list[int] = []
    run = 0
    for v in hourly_flag:
        if v:
            run += 1
        elif run:
            out.append(run)
            run = 0
    if run:
        out.append(run)
    return np.array(out, dtype=int) if out else np.array([1], dtype=int)


# ----------------------------------------------------------------- price injection


def _inject_prices(
    base_price_level: np.ndarray,
    forecast_mw: np.ndarray,
    cfg: SyntheticConfig,
    real_negative_prices: np.ndarray,
    real_hour_run_lengths: np.ndarray,
    rng: np.random.Generator,
) -> tuple[np.ndarray, dict]:
    """Place negative-price episodes until the target censoring rate is reached.

    Placement weight is exp(gamma * z(F)) over the episode window, where z(F) is the
    standardised day-ahead forecast. gamma = 0 gives uniform placement; larger gamma
    puts the episodes on windy periods, which is the weather-price confounding that
    makes the recovery problem hard.
    """
    n = forecast_mw.size
    price = base_price_level.copy()
    target_negative = int(round(cfg.censoring_rate * n))

    z = (forecast_mw - forecast_mw.mean()) / (forecast_mw.std() + 1e-9)
    # Episode-start weights, smoothed over a 4-quarter-hour window so the weight
    # reflects the window rather than a single quarter-hour.
    kernel = np.ones(4) / 4.0
    z_smooth = np.convolve(z, kernel, mode="same")
    weights = np.exp(cfg.gamma * z_smooth)
    weights = weights / weights.sum()

    negative_mask = np.zeros(n, dtype=bool)
    placed = 0
    attempts = 0
    max_attempts = 20 * n
    n_subhour = 0
    n_hourly = 0

    while placed < target_negative and attempts < max_attempts:
        attempts += 1
        start = int(rng.choice(n, p=weights))

        is_subhour = rng.random() < cfg.subhour_episode_share
        if is_subhour:
            # Sub-hour episode: 1-3 quarter-hours, aligned inside one calendar hour,
            # shallow enough that the hourly mean stays positive. These are the
            # quarter-hours on which the two clocks disagree (spec section 3, I4).
            hour_start = (start // 4) * 4
            length = int(rng.integers(1, 4))
            sl = slice(hour_start, min(hour_start + length, n))
            n_subhour += 1
        else:
            # Hourly-clock episode: a whole number of hours, length drawn from the
            # real distribution of negative-hour runs.
            hours = int(rng.choice(real_hour_run_lengths))
            hour_start = (start // 4) * 4
            sl = slice(hour_start, min(hour_start + 4 * hours, n))
            n_hourly += 1

        if negative_mask[sl].any():
            continue  # do not overlap an existing episode

        length = sl.stop - sl.start
        if length == 0:
            continue
        depths = rng.choice(real_negative_prices, size=length, replace=True)

        if is_subhour:
            # Keep the hourly mean positive: scale the negative quarter-hours so the
            # hour still averages above zero given its remaining positive ones.
            hour_sl = slice(sl.start, min(sl.start + 4, n))
            others = price[hour_sl].sum() - price[sl].sum()
            n_neg = sl.stop - sl.start
            max_total_negative = others - 1e-6  # mean stays > 0
            if max_total_negative <= 0:
                continue
            scale = min(1.0, max_total_negative / max(1e-9, -depths.sum()))
            depths = depths * scale
            if depths.max() >= 0:
                continue

        price[sl] = depths
        negative_mask[sl] = True
        placed = int(negative_mask.sum())

    diagnostics = {
        "target_negative_qh": target_negative,
        "placed_negative_qh": placed,
        "realised_negative_rate": placed / n,
        "episodes_hourly": n_hourly,
        "episodes_subhour": n_subhour,
        "placement_attempts": attempts,
    }
    if placed < 0.9 * target_negative:
        raise RuntimeError(
            f"Could only place {placed} of {target_negative} negative quarter-hours "
            f"after {attempts} attempts. Lower censoring_rate or check the generator."
        )
    return price, diagnostics


# --------------------------------------------------------------------- weather proxy


def _weather_proxy(a_true_mw: np.ndarray, cfg: SyntheticConfig,
                   rng: np.random.Generator) -> np.ndarray:
    """A_true passed through a noisy inverse fleet power curve, giving a wind speed.

    A weather forecast gives a speed, not a power, so the proxy is a speed and the
    model has to learn the curve. Noise is added on the speed, which is where a
    numerical weather prediction's error actually lives.
    """
    capacity = float(np.nanmax(a_true_mw)) * 1.05 + 1e-9
    cf = np.clip(a_true_mw / capacity, 1e-4, 1.0 - 1e-4)
    v = cfg.curve_v50_ms - cfg.curve_k * np.log(1.0 / cf - 1.0)
    return v + rng.normal(0.0, cfg.weather_noise_ms, size=v.shape)


# ------------------------------------------------------------------------ generator


def generate(cfg: SyntheticConfig, cohorts: CohortSet | None = None) -> SyntheticData:
    """Build one realisation of the E1 benchmark. Fully determined by cfg.seed."""
    rng = np.random.default_rng(cfg.seed)
    cohorts = cohorts if cohorts is not None else placeholder_cohort_set()

    base = load_base(cfg.area, cfg.safe_price_floor)
    forecast = base["forecast_mw"]
    a_true = base["a_true_mw"]
    n = forecast.size

    ts = int(SYNTH_START.timestamp()) * 1_000_000_000 + STEP_NS * np.arange(n, dtype=np.int64)
    berlin_date = np.array(
        [
            d.replace(tzinfo=timezone.utc).astimezone(BERLIN).strftime("%Y-%m-%d")
            for d in (ts[::QH_PER_DAY] // 1_000_000_000)
            .astype("datetime64[s]")
            .astype(object)
        ]
    ).repeat(QH_PER_DAY)[:n]

    # Baseline positive price level: a calm, clearly safe level, so that any negative
    # price in the series is one the generator put there.
    base_level = np.full(n, 40.0)
    price, price_diag = _inject_prices(
        base_level, forecast, cfg,
        base["real_negative_prices"], base["real_hour_run_lengths"], rng,
    )

    clock = build_clock_features(ts, price)
    theta, s, depth = theta_and_exposure(cohorts, clock, cfg.mv_eur_mwh)

    r_true = true_response(depth, cfg) * s
    c_true = curtailed_share(cohorts.shares, s, r_true)

    g_obs = a_true * (1.0 - c_true)
    if cfg.observation_noise_mw > 0:
        g_obs = g_obs + rng.normal(0.0, cfg.observation_noise_mw, size=n)
        g_obs = np.maximum(g_obs, 0.0)

    weather = _weather_proxy(a_true, cfg, rng) if cfg.with_weather_proxy else None

    diagnostics = {
        **price_diag,
        "n_qh": n,
        "n_days": int(len(np.unique(berlin_date))),
        "n_base_available": base["n_base_available"],
        "n_base_used": base["n_base_used"],
        "n_real_negative_qh_in_panel": base["n_real_negative_qh"],
        "exposed_rate": float((s.max(axis=0) > 0).mean()),
        "censored_rate": float((c_true > 0).mean()),
        "mean_c_on_censored": float(c_true[c_true > 0].mean()) if (c_true > 0).any() else 0.0,
        "max_c": float(c_true.max()),
        "exposed_rate_per_cohort": {
            c.cohort_id: float((s[i] > 0).mean()) for i, c in enumerate(cohorts)
        },
        "mean_a_true_mw": float(a_true.mean()),
        "mean_g_obs_mw": float(g_obs.mean()),
        "curtailed_energy_share": float(
            1.0 - g_obs.sum() / a_true.sum()
        ),
    }

    return SyntheticData(
        config=cfg,
        cohorts=cohorts,
        ts_utc_ns=ts,
        berlin_date=berlin_date,
        real_berlin_date=base["real_berlin_date"],
        forecast_mw=forecast,
        a_true_mw=a_true,
        price_eur_mwh=price,
        theta=theta,
        s=s,
        depth=depth,
        r_true=r_true,
        c_true=c_true,
        g_obs_mw=g_obs,
        weather_ms=weather,
        diagnostics=diagnostics,
    )
