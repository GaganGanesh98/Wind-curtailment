"""SUPERSEDED 8 Nov 2026 -- do not use for thesis results.

Superseded by `src/censoring/synthetic.py`, which is the production E1 path.

Reason: this generator evaluates an hourly-clock cohort's exposure against the
HOURLY MEAN price, so a quarter-hour whose own price is positive, inside a
qualifying negative hour, is treated as switched off. That misreads section 51
EEG 2023. Section 51 zeroes the anzulegender Wert; it does not mandate switch-off,
and since the 15-minute market time unit went live for delivery day 1 Oct 2025 a
plant's day-ahead revenue settles per quarter-hour. The clock decides which branch
of theta applies, never which price the plant compares against:

    theta_k,t = 0        if support is zeroed (section 51 triggered, or out of support)
              = -MP_k,t  otherwise
    s_k,t     = 1[ p_qh,t < theta_k,t ]      -- always the QUARTER-HOUR price

`src/censoring/cohorts.py:371 theta_and_exposure` implements that correctly.

`retro_run = True` here is right about the law -- the pre-2025 wording zeroes the
value "fuer den gesamten Zeitraum, in dem der Spotmarktpreis ohne Unterbrechung
negativ ist" -- but that governs the support payment, not the switch-off decision.
Conflating the two is the bug. cohorts.py applies the retroactive zeroing to theta
and still compares the quarter-hour price, which is the correct combination
(verified in docs/12 section A.2).

Kept, not deleted: docs/10 and docs/11 cite this file and its measurements.
The validation suite was ported to `src/censoring/validate_synthetic.py`, minus its
check 6, which asserted that the bug's symptom MUST be present.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field, asdict, fields
from typing import Literal, Sequence

import numpy as np
import pandas as pd

BERLIN = "Europe/Berlin"
QH_PER_HOUR = 4
C_EPS = 1e-4  # below this, a row is not counted as meaningfully censored


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PanelSpec:
    """Column names in the input panel. Change these, not the code."""

    timestamp: str = "timestamp_utc"
    area: str = "area"
    actual_mw: str = "wind_actual_mw"
    forecast_mw: str = "wind_da_forecast_mw"
    price: str = "price_eur_mwh"


def parse_panel_spec(spec: str | None) -> PanelSpec:
    """
    Build a PanelSpec from a "field=column,field=column" string, so a panel
    whose columns are named differently can be read without renaming the
    stored data or editing the defaults above.

        "timestamp=ts_utc_dt,actual_mw=act_wind_mw,forecast_mw=da_wind_mw"

    Fields left out keep their default name.
    """
    if not spec:
        return PanelSpec()
    valid = {f.name for f in fields(PanelSpec)}
    kw: dict[str, str] = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(f"--cols entry {part!r} is not field=column")
        field_name, col = (x.strip() for x in part.split("=", 1))
        if field_name not in valid:
            raise ValueError(
                f"--cols field {field_name!r} is not one of {sorted(valid)}"
            )
        kw[field_name] = col
    return PanelSpec(**kw)


@dataclass(frozen=True)
class CohortSpec:
    """
    One plant cohort from the EEG rule table.

    clock
        "qh"     -> exposure decided on the quarter-hour price
                    (post-25 Feb 2025 plants)
        "hourly" -> exposure decided on the hourly mean price plus a minimum
                    run length (older rules: 6 h, 4 h, or the staircase)
    theta_eur_mwh
        Switch-off threshold. 0 for a 51-triggered or out-of-support cohort;
        -market_premium for a cohort the rule never touches.
    min_run_hours
        Only used when clock == "hourly".
    retro_run
        True  -> once a run of negative hours reaches min_run_hours, the WHOLE
                 run counts as exposed (this is how 51 actually works).
        False -> only hours from the threshold onwards are exposed.
    """

    name: str
    capacity_share: float
    clock: Literal["qh", "hourly"] = "qh"
    theta_eur_mwh: float = 0.0
    min_run_hours: float = 0.0
    retro_run: bool = True


@dataclass(frozen=True)
class ResponseSpec:
    """
    The TRUE fleet response r*_k. This is the target the model must recover.

    shape
        "step"     -> everyone exposed switches off at once (hard, unrealistic)
        "logistic" -> smooth, monotone in how far below threshold the price is
        "half"     -> logistic capped at 50% compliance (matches Hirth's
                      "about half switch off" finding)
    depth_half
        EUR/MWh below threshold at which half of r_max has switched off.
    depth_scale
        Steepness of the logistic in EUR/MWh.
    run_saturation_hours
        If > 0, response also rises with run length, saturating here. Set to 0
        to make the response depend on price depth only.
    """

    shape: Literal["step", "logistic", "half"] = "logistic"
    r_max: float = 0.9
    depth_half: float = 15.0
    depth_scale: float = 8.0
    run_saturation_hours: float = 0.0

    def effective_r_max(self) -> float:
        return 0.5 if self.shape == "half" else self.r_max

    def evaluate(self, depth: np.ndarray, run_hours: np.ndarray) -> np.ndarray:
        """depth = theta - price, in EUR/MWh. Only meaningful where exposed."""
        depth = np.asarray(depth, dtype=float)
        run_hours = np.asarray(run_hours, dtype=float)
        rmax = self.effective_r_max()

        if self.shape == "step":
            base = np.where(depth > 0.0, 1.0, 0.0)
        else:
            base = 1.0 / (1.0 + np.exp(-(depth - self.depth_half) / self.depth_scale))

        if self.run_saturation_hours > 0:
            run_factor = np.clip(run_hours / self.run_saturation_hours, 0.0, 1.0)
            run_factor = 0.4 + 0.6 * run_factor  # never zero in the first QH
        else:
            run_factor = 1.0

        return np.clip(rmax * base * run_factor, 0.0, 1.0)


def default_cohorts() -> tuple[CohortSpec, ...]:
    """
    Two-cohort default: the pre-registered fallback structure from spec 3 I4.

    The two clocks are what make the cohorts separable at all, so even the
    simplest E1 run must contain both.
    """
    return (
        CohortSpec(name="qh_clock", capacity_share=0.45, clock="qh", theta_eur_mwh=0.0),
        CohortSpec(
            name="hourly_clock_2h",
            capacity_share=0.55,
            clock="hourly",
            theta_eur_mwh=0.0,
            min_run_hours=2.0,
        ),
    )


@dataclass
class E1Config:
    censoring_rate: float = 0.20
    gamma: float = 0.0
    response: ResponseSpec = field(default_factory=ResponseSpec)
    cohorts: Sequence[CohortSpec] = field(default_factory=default_cohorts)
    seed: int = 0

    clean_price_floor: float = 5.0
    min_qh_per_day: int = 88
    rate_definition: Literal["qh_share", "energy_share"] = "qh_share"

    # negative-price block geometry (median length is scaled by the intensity
    # control when the target rate needs more than one block per day)
    block_len_qh_min: int = 4
    block_len_qh_max: int = 92
    block_len_qh_median: int = 12
    p_second_block: float = 0.25

    # never let more than this fraction of days become event-days, so that
    # day-level confounding keeps biting at high censoring rates
    max_day_fraction: float = 0.6
    # strength of within-day confounding (block placed where F is high)
    block_gamma_scale: float = 2.5

    # price depth
    depth_log_mean: float = 2.4     # exp(2.4) ~ 11 EUR/MWh typical day amplitude
    depth_log_sigma: float = 0.9
    depth_profile_exponent: float = 0.7

    # observation noise on G, as a fraction of A
    noise_sigma: float = 0.01

    def to_json(self) -> str:
        d = asdict(self)
        d["cohorts"] = [asdict(c) for c in self.cohorts]
        d["response"] = asdict(self.response)
        return json.dumps(d, indent=2, sort_keys=True)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _consecutive_run(flag: np.ndarray, group: np.ndarray) -> np.ndarray:
    """
    Causal run length: for each position, how many consecutive True values end
    here, resetting at group boundaries. Vectorised -- no Python loop.
    """
    n = len(flag)
    if n == 0:
        return np.zeros(0, dtype=float)
    idx = np.arange(n)
    brk = np.empty(n, dtype=bool)
    brk[0] = True
    brk[1:] = group[1:] != group[:-1]

    anchor = np.where(~flag, idx, np.where(brk, idx - 1, -1))
    anchor = np.maximum.accumulate(anchor)
    run = (idx - anchor).astype(float)
    run[~flag] = 0.0
    return run


def _prepare_base(panel: pd.DataFrame, cfg: E1Config, cols: PanelSpec) -> pd.DataFrame:
    required = (cols.timestamp, cols.actual_mw, cols.forecast_mw, cols.price)
    missing = [c for c in required if c not in panel.columns]
    if missing:
        raise KeyError(f"panel is missing columns: {missing}")

    df = panel.copy()
    ts = pd.to_datetime(df[cols.timestamp], utc=True)
    df[cols.timestamp] = ts

    df = df.loc[df[cols.price] > cfg.clean_price_floor].copy()
    df = df.dropna(subset=[cols.actual_mw, cols.forecast_mw])

    local = df[cols.timestamp].dt.tz_convert(BERLIN)
    df["day_local"] = local.dt.strftime("%Y-%m-%d")
    df["__area"] = df[cols.area].astype(str) if cols.area in df.columns else "ALL"
    df["__day_key"] = df["__area"] + "|" + df["day_local"]
    df["__hour_key"] = df["__area"] + "|" + local.dt.strftime("%Y%m%d%H")

    counts = df.groupby("__day_key")[cols.actual_mw].transform("size")
    df = df.loc[counts >= cfg.min_qh_per_day].copy()
    if df.empty:
        raise ValueError(
            "no clean days survived filtering. Lower min_qh_per_day or check "
            "the price floor and input coverage."
        )

    df = df.sort_values(["__area", cols.timestamp]).reset_index(drop=True)
    df["A_true_mw"] = df[cols.actual_mw].astype(float)
    df["__price_base"] = df[cols.price].astype(float)
    return df


def _day_weights(df: pd.DataFrame, cfg: E1Config, cols: PanelSpec) -> pd.Series:
    """Confounding: tilt day selection towards high forecast wind as gamma rises."""
    day_mean_f = df.groupby("__day_key")[cols.forecast_mw].mean()
    z = (day_mean_f - day_mean_f.mean()) / (day_mean_f.std(ddof=0) + 1e-9)
    w = np.exp(cfg.gamma * np.clip(z, -4, 4))
    return w / w.sum()


def _inject_prices(
    df: pd.DataFrame,
    selected_days: set,
    cfg: E1Config,
    rng: np.random.Generator,
    length_scale: float,
    f_arr: np.ndarray,
) -> np.ndarray:
    """Return a price array: the original price, overwritten inside blocks."""
    price = df["__price_base"].to_numpy(dtype=float).copy()
    day_arr = df["__day_key"].to_numpy()

    # positions of each day, computed once
    order = np.argsort(day_arr, kind="stable")
    sorted_days = day_arr[order]
    bounds = np.r_[0, np.flatnonzero(sorted_days[1:] != sorted_days[:-1]) + 1,
                   len(sorted_days)]

    median_len = max(cfg.block_len_qh_min, cfg.block_len_qh_median * length_scale)
    # smooth, not stepped: a fractional extra block becomes a probability, so
    # the realised rate is continuous in the intensity control
    extra_raw = max(0.0, length_scale - 1.0) / 1.5

    for b in range(len(bounds) - 1):
        day = sorted_days[bounds[b]]
        if day not in selected_days:
            continue
        idx = order[bounds[b]:bounds[b + 1]]
        idx.sort()
        if idx.size < cfg.block_len_qh_min:
            continue

        extra_blocks = int(extra_raw) + int(rng.random() < (extra_raw % 1.0))
        n_blocks = 1 + int(rng.random() < cfg.p_second_block) + extra_blocks
        occupied = np.zeros(idx.size, dtype=bool)

        for _ in range(n_blocks):
            raw = rng.lognormal(mean=np.log(median_len), sigma=0.55)
            L = int(np.clip(round(raw), cfg.block_len_qh_min,
                            min(cfg.block_len_qh_max, idx.size)))
            free_starts = np.array(
                [s for s in range(0, idx.size - L + 1)
                 if not occupied[s:s + L].any()], dtype=int
            )
            if free_starts.size == 0:
                continue

            # within-day confounding: prefer windows where forecast wind is high
            if cfg.gamma > 0 and free_starts.size > 1:
                f_day = f_arr[idx]
                csum = np.r_[0.0, np.cumsum(f_day)]
                win_mean = (csum[free_starts + L] - csum[free_starts]) / L
                z = (win_mean - win_mean.mean()) / (win_mean.std(ddof=0) + 1e-9)
                w = np.exp(cfg.block_gamma_scale * cfg.gamma * np.clip(z, -4, 4))
                w = w / w.sum()
                start = int(rng.choice(free_starts, p=w))
            else:
                start = int(free_starts[rng.integers(free_starts.size)])
            occupied[start:start + L] = True

            amplitude = min(float(rng.lognormal(cfg.depth_log_mean,
                                                cfg.depth_log_sigma)), 500.0)
            if L == 1:
                profile = np.array([1.0])
            else:
                u = np.linspace(-1.0, 1.0, L)
                profile = np.maximum((1.0 - u ** 2) ** cfg.depth_profile_exponent, 0.02)

            price[idx[start:start + L]] = -amplitude * profile

    return price


def _clocks(
    df: pd.DataFrame, price: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (qh_run_hours, hourly_run_hours, hourly_mean_price)."""
    area = df["__area"].to_numpy()
    hour_key = df["__hour_key"].to_numpy()

    qh_run = _consecutive_run(price < 0.0, area) / QH_PER_HOUR

    hour_mean = pd.Series(price).groupby(hour_key, sort=False).transform("mean").to_numpy()

    # one row per hour, in time order
    _, first_pos = np.unique(hour_key, return_index=True)
    first_pos = np.sort(first_pos)
    hours = hour_key[first_pos]
    hour_neg = hour_mean[first_pos] < 0.0
    hour_area = area[first_pos]

    hr_run = _consecutive_run(hour_neg, hour_area)
    run_map = pd.Series(hr_run, index=hours)
    hourly_run = run_map.reindex(hour_key).to_numpy()

    return qh_run, hourly_run, hour_mean


def _exposure(
    cohort: CohortSpec,
    price_qh: np.ndarray,
    price_hourly: np.ndarray,
    hourly_run_hours: np.ndarray,
    hour_key: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Return (exposed, depth) for one cohort.

    depth = how far the relevant price sits BELOW the cohort threshold, EUR/MWh.
    """
    if cohort.clock == "qh":
        depth = cohort.theta_eur_mwh - price_qh
        exposed = depth > 0.0
        return exposed, np.where(exposed, depth, 0.0)

    depth = cohort.theta_eur_mwh - price_hourly
    below = depth > 0.0

    if cohort.retro_run:
        # a whole run qualifies once its peak length clears the threshold
        hours = pd.Series(hourly_run_hours, index=hour_key)
        peak = hours.groupby(level=0, sort=True).max()
        run_id = (peak == 0).cumsum()
        run_peak = peak.groupby(run_id).transform("max")
        qualifies = run_peak.reindex(hour_key).to_numpy() >= cohort.min_run_hours
    else:
        qualifies = hourly_run_hours >= cohort.min_run_hours

    exposed = below & qualifies
    return exposed, np.where(exposed, np.maximum(depth, 0.0), 0.0)


# --------------------------------------------------------------------------- #
# Core generation
# --------------------------------------------------------------------------- #


def _generate_once(
    base: pd.DataFrame,
    cfg: E1Config,
    cols: PanelSpec,
    weights: pd.Series,
    intensity: float,
) -> pd.DataFrame:
    """
    `intensity` is the single monotone control knob.
      0 < u <= 1  -> select a fraction u of days, normal block length
      u > 1       -> all days selected, blocks lengthened and multiplied
    """
    rng = np.random.default_rng(cfg.seed)
    df = base

    all_days = weights.index.to_numpy()
    n_days = int(round(len(all_days) * min(intensity, 1.0) * cfg.max_day_fraction))
    n_days = int(np.clip(n_days, 0, len(all_days)))

    if n_days == 0:
        selected: set = set()
    else:
        picked = rng.choice(len(all_days), size=n_days, replace=False,
                            p=weights.to_numpy())
        selected = set(all_days[picked])

    length_scale = max(1.0, intensity)
    f_arr = df[cols.forecast_mw].to_numpy(dtype=float)
    price = _inject_prices(df, selected, cfg, rng, length_scale, f_arr)
    qh_run_h, hourly_run_h, hour_mean = _clocks(df, price)
    hour_key = df["__hour_key"].to_numpy()

    c_total = np.zeros(len(df))
    extra: dict[str, np.ndarray] = {}

    for cohort in cfg.cohorts:
        exposed, depth = _exposure(cohort, price, hour_mean, hourly_run_h, hour_key)
        run_for_r = qh_run_h if cohort.clock == "qh" else hourly_run_h
        r_star = np.where(exposed, cfg.response.evaluate(depth, run_for_r), 0.0)

        c_total += cohort.capacity_share * r_star
        extra[f"s_{cohort.name}"] = exposed.astype(np.int8)
        extra[f"depth_{cohort.name}_eur_mwh"] = depth
        extra[f"r_star_{cohort.name}"] = r_star
        extra[f"w_{cohort.name}"] = np.full(len(df), cohort.capacity_share)

    c_total = np.clip(c_total, 0.0, 1.0)

    noise = (rng.normal(0.0, cfg.noise_sigma, size=len(df))
             if cfg.noise_sigma > 0 else 0.0)
    a_true = df["A_true_mw"].to_numpy()
    g_obs = np.maximum(a_true * (1.0 - c_total) * (1.0 + noise), 0.0)

    out = pd.DataFrame(
        {
            cols.timestamp: df[cols.timestamp].to_numpy(),
            "area": df["__area"].to_numpy(),
            "day_local": df["day_local"].to_numpy(),
            "F_mw": df[cols.forecast_mw].to_numpy(dtype=float),
            "A_true_mw": a_true,
            "G_obs_mw": g_obs,
            "price_eur_mwh": price,
            "price_hourly_mean_eur_mwh": hour_mean,
            "run_hours_qh_clock": qh_run_h,
            "run_hours_hourly_clock": hourly_run_h,
            "c_true": c_total,
            "censored": (c_total > C_EPS).astype(np.int8),
            "price_negative": (price < 0).astype(np.int8),
        }
    )
    for k, v in extra.items():
        out[k] = v
    return out


def _realised_rate(frame: pd.DataFrame, definition: str) -> float:
    if definition == "energy_share":
        denom = frame["A_true_mw"].sum()
        return float((frame["A_true_mw"] * frame["c_true"]).sum() / denom) if denom else 0.0
    return float(frame["censored"].mean())


def generate(
    panel: pd.DataFrame, cfg: E1Config, cols: PanelSpec | None = None
) -> tuple[pd.DataFrame, dict]:
    """
    Generate one E1 dataset.

    Returns (frame, diagnostics). The frame carries G_obs_mw (what a model may
    see) and A_true_mw / c_true / r_star_* (ground truth, scoring only).
    """
    cols = cols or PanelSpec()
    base = _prepare_base(panel, cfg, cols)
    weights = _day_weights(base, cfg, cols)
    n_available = len(weights)

    lo, hi = 0.0, 6.0
    frame = None
    rate = 0.0
    intensity = 0.0
    for _ in range(26):
        intensity = 0.5 * (lo + hi)
        frame = _generate_once(base, cfg, cols, weights, intensity)
        rate = _realised_rate(frame, cfg.rate_definition)
        if abs(rate - cfg.censoring_rate) < 0.002:
            break
        if rate < cfg.censoring_rate:
            lo = intensity
        else:
            hi = intensity

    assert frame is not None
    saturated = abs(rate - cfg.censoring_rate) > 0.02

    diagnostics = {
        "target_rate": cfg.censoring_rate,
        "realised_rate": round(rate, 4),
        "rate_definition": cfg.rate_definition,
        "rate_target_met": not saturated,
        "intensity": round(intensity, 4),
        "n_days_available": int(n_available),
        "n_rows": int(len(frame)),
        "n_censored_rows": int(frame["censored"].sum()),
        "n_negative_price_rows": int(frame["price_negative"].sum()),
        "n_event_days": int(frame.loc[frame["price_negative"] == 1, "day_local"].nunique()),
        "mean_c_on_censored": (
            round(float(frame.loc[frame["censored"] == 1, "c_true"].mean()), 4)
            if frame["censored"].any() else 0.0
        ),
        "energy_censored_share": round(
            float((frame["A_true_mw"] * frame["c_true"]).sum()
                  / frame["A_true_mw"].sum()), 4
        ),
        "gamma": cfg.gamma,
        "response_shape": cfg.response.shape,
        "seed": cfg.seed,
        "cohort_exposure_differs_days": _cohort_separability(frame, cfg),
        "confounding_corr_F_vs_c": round(
            float(np.corrcoef(frame["F_mw"], frame["c_true"])[0, 1]), 4
        ),
    }
    return frame, diagnostics


def _cohort_separability(frame: pd.DataFrame, cfg: E1Config) -> int:
    """
    Spec 3 I4 pre-registered check: on how many event-days do the cohort
    exposure vectors actually differ? Under 10 and the K-cohort model is
    abandoned for the two-cohort one.
    """
    s_cols = [f"s_{c.name}" for c in cfg.cohorts if f"s_{c.name}" in frame.columns]
    if len(s_cols) < 2:
        return 0
    arr = frame[s_cols].to_numpy()
    differs = arr.max(axis=1) != arr.min(axis=1)
    return int(frame.loc[differs, "day_local"].nunique())


# --------------------------------------------------------------------------- #
# Grid
# --------------------------------------------------------------------------- #


def generate_grid(
    panel: pd.DataFrame,
    rates: Sequence[float] = (0.05, 0.10, 0.20, 0.30, 0.40),
    gammas: Sequence[float] = (0.0, 0.5, 1.0),
    shapes: Sequence[str] = ("step", "logistic", "half"),
    seeds: Sequence[int] = (0, 1, 2, 3, 4),
    cols: PanelSpec | None = None,
    out_dir: str | None = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """Run the full E1 grid. Returns the diagnostics table, one row per cell."""
    records = []
    total = len(rates) * len(gammas) * len(shapes) * len(seeds)
    n = 0
    for rate in rates:
        for gamma in gammas:
            for shape in shapes:
                for seed in seeds:
                    cfg = E1Config(
                        censoring_rate=rate,
                        gamma=gamma,
                        response=ResponseSpec(shape=shape),  # type: ignore[arg-type]
                        seed=seed,
                    )
                    frame, diag = generate(panel, cfg, cols)
                    if out_dir:
                        os.makedirs(out_dir, exist_ok=True)
                        name = (f"e1_r{int(rate * 100):02d}_g{gamma}_"
                                f"{shape}_s{seed}.parquet")
                        frame.to_parquet(os.path.join(out_dir, name), index=False)
                    records.append(diag)
                    n += 1
                    if verbose and n % 10 == 0:
                        print(f"  {n}/{total} cells", flush=True)
    return pd.DataFrame.from_records(records)


# --------------------------------------------------------------------------- #
# Stand-in panel, for testing without the real data
# --------------------------------------------------------------------------- #


def make_standin_panel(days: int = 240, seed: int = 42) -> pd.DataFrame:
    """
    Fabricate a panel with the right SHAPE and rough statistics of the real one.
    Smoke-testing only. Never use it for a thesis result.
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-10-01", periods=days * 96, freq="15min", tz="UTC")

    t = np.arange(len(idx))
    seasonal = 1.0 + 0.35 * np.sin(2 * np.pi * t / (96 * 60))
    weather = np.exp(np.convolve(rng.normal(0, 0.12, len(idx)),
                                 np.ones(96) / 96, mode="same") * 6)
    forecast = np.clip(14000 * seasonal * weather, 500, 55000)
    actual = np.clip(forecast * (1 + rng.normal(0.01, 0.09, len(idx))), 0, None)
    price = 85 - 0.0022 * forecast + rng.normal(0, 14, len(idx))

    return pd.DataFrame(
        {
            "timestamp_utc": idx,
            "area": "DE",
            "wind_actual_mw": actual,
            "wind_da_forecast_mw": forecast,
            "price_eur_mwh": price,
        }
    )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main() -> None:
    p = argparse.ArgumentParser(description="E1 semi-synthetic censoring generator")
    p.add_argument("--panel", help="Parquet path of the clean panel")
    p.add_argument("--selftest", action="store_true",
                   help="run on a fabricated stand-in panel")
    p.add_argument("--rate", type=float, default=0.20)
    p.add_argument("--gamma", type=float, default=0.0)
    p.add_argument("--shape", default="logistic", choices=["step", "logistic", "half"])
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--rate-definition", default="qh_share",
                   choices=["qh_share", "energy_share"])
    p.add_argument("--cols", help="column mapping, e.g. "
                   "'timestamp=ts_utc_dt,actual_mw=act_wind_mw'")
    p.add_argument("--area", help="keep only this area before generating")
    p.add_argument("--out", help="write the generated frame here (Parquet)")
    p.add_argument("--grid", action="store_true", help="run the full E1 grid")
    p.add_argument("--grid-out", help="directory for grid Parquet files")
    args = p.parse_args()

    if args.selftest:
        panel = make_standin_panel()
    elif args.panel:
        panel = pd.read_parquet(args.panel)
    else:
        p.error("give --panel or --selftest")

    cols = parse_panel_spec(args.cols)
    if args.area:
        panel = panel.loc[panel[cols.area].astype(str) == args.area].copy()
        if panel.empty:
            p.error(f"no rows for area {args.area!r}")

    if args.grid:
        table = generate_grid(panel, cols=cols, out_dir=args.grid_out)
        print(table.to_string(index=False))
        return

    cfg = E1Config(
        censoring_rate=args.rate,
        gamma=args.gamma,
        response=ResponseSpec(shape=args.shape),  # type: ignore[arg-type]
        seed=args.seed,
        rate_definition=args.rate_definition,  # type: ignore[arg-type]
    )
    frame, diag = generate(panel, cfg, cols)
    print(json.dumps(diag, indent=2))
    if args.out:
        frame.to_parquet(args.out, index=False)
        print(f"\nwrote {args.out}  ({len(frame):,} rows)")


if __name__ == "__main__":
    main()
