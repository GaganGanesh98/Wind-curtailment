"""Shared definitions for Phase P: window, price bands, series, bootstrap helpers.

Every constant here is pre-registered in `docs/P0_preregistration.md`; changing one
after that document is committed is a protocol violation, not a refactor.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl

from src.method.window import MTU15_FIRST_DELIVERY_DAY

REPO_ROOT = Path(__file__).resolve().parents[2]
PANEL_PATH = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"
ARTIFACTS = REPO_ROOT / "artifacts"

WINDOW_START = MTU15_FIRST_DELIVERY_DAY          # "2025-10-01", Berlin-local date
AREAS = ("DE", "50Hertz", "Amprion", "TenneT", "TransnetBW")
PRIMARY_AREAS = ("DE", "50Hertz", "Amprion")

# The two target series. "onshore" is the primary P1 target because the cohort
# structure (MaStR shares, EEG rule table) describes the onshore fleet; "total" is the
# kill-test series (onshore + offshore, results/02_*), reported as secondary.
SERIES = {
    "onshore": ("da_onshore_mw", "act_onshore_mw"),
    "total": ("da_wind_mw", "act_wind_mw"),
}

# Price bands on the quarter-hour day-ahead price, EUR/MWh. Negative means < 0.
# Band edges follow the Phase P brief: > -5, -20 to -5, -50 to -20, <= -50.
BANDS = (
    ("(-5,0)", -5.0, 0.0),        # -5 < p < 0
    ("[-20,-5]", -20.0, -5.0),    # -20 < p <= -5
    ("[-50,-20]", -50.0, -20.0),  # -50 < p <= -20
    ("<=-50", -np.inf, -50.0),    # p <= -50
)
DEEP_THRESHOLD = -20.0            # S2 test set: p <= -20
SAFE_FLOOR = 5.0                  # "safe" quarter-hours: p > 5 (spec v1.5 I1)

N_BOOT = 5000
SEED = 42
EMBARGO_DAYS = 7


def band_of(price: np.ndarray) -> np.ndarray:
    """Band label per quarter-hour; '' for non-negative prices."""
    out = np.full(price.shape, "", dtype=object)
    for label, lo, hi in BANDS:
        if label == "(-5,0)":
            m = (price > lo) & (price < hi)
        else:
            m = (price > lo) & (price <= hi)
        out[m] = label
    return out


def load_window(area: str, start: str = WINDOW_START, end: str | None = None) -> pl.DataFrame:
    """The panel for one area from the window start, sorted, with the derived columns.

    Keeps rows with a finite price; a missing forecast or actual is kept as null so the
    caller can count it rather than have it vanish.
    """
    df = (pl.scan_parquet(PANEL_PATH)
            .filter((pl.col("area") == area) & (pl.col("berlin_date") >= start))
            .sort("ts_utc").collect())
    if end is not None:
        df = df.filter(pl.col("berlin_date") <= end)
    df = df.filter(pl.col("price_eur_mwh").is_not_null())
    hour = (pl.col("ts_utc_dt").dt.replace_time_zone("UTC")
              .dt.convert_time_zone("Europe/Berlin").dt.hour())
    return df.with_columns(
        hour.alias("hour_berlin"),
        pl.Series("band", band_of(df["price_eur_mwh"].to_numpy())).cast(pl.String),
        (pl.col("price_eur_mwh") < 0).alias("neg"),
        (pl.col("price_eur_mwh") <= DEEP_THRESHOLD).alias("deep"),
        (pl.col("price_eur_mwh") > SAFE_FLOOR).alias("safe"),
    )


# ------------------------------------------------------------ event-day bootstrap


def day_index(days: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Unique Berlin dates and the integer index of each row's day."""
    uniq, idx = np.unique(np.asarray(days).astype(str), return_inverse=True)
    return uniq, idx


def bootstrap_day_sums(per_day: np.ndarray, n_boot: int = N_BOOT, seed: int = SEED
                       ) -> np.ndarray:
    """Resample event-days with replacement and return the summed sufficient statistics.

    `per_day` has shape (n_days, n_stats). Returns (n_boot, n_stats): each row is the
    column sum over one resample of n_days days. Statistics that are functions of sums
    (means, variances, correlations, RMSE) are then evaluated per resample by the
    caller, which keeps the whole bootstrap vectorised and exact.
    """
    rng = np.random.default_rng(seed)
    n = per_day.shape[0]
    if n == 0:
        return np.full((n_boot, per_day.shape[1]), np.nan)
    draws = rng.integers(0, n, size=(n_boot, n))
    return per_day[draws].sum(axis=1)


def ci95(samples: np.ndarray) -> tuple[float, float]:
    s = np.asarray(samples, dtype=float)
    s = s[np.isfinite(s)]
    if s.size == 0:
        return (float("nan"), float("nan"))
    return (float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5)))
