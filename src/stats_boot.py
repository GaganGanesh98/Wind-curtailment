"""Event-day block bootstrap.

The effective sample is a few dozen clustered episodes, not 37,000 independent
quarter-hours, so every confidence interval here resamples *whole Berlin-local
event-days* with replacement. There is deliberately no i.i.d. quarter-hour
bootstrap in this project.
"""

from __future__ import annotations

import numpy as np

SEED = 42


def _day_aggregates(values: np.ndarray, days: np.ndarray):
    """Per-day sums and counts, dropping non-finite values."""
    ok = np.isfinite(values)
    values, days = values[ok], days[ok]
    uniq, inv = np.unique(days, return_inverse=True)
    sums = np.bincount(inv, weights=values, minlength=len(uniq))
    counts = np.bincount(inv, minlength=len(uniq)).astype(float)
    return uniq, sums, counts


def eventday_bootstrap_mean(values, days, n_boot: int = 5000, seed: int = SEED):
    """Pooled mean of `values` with a 95% CI from an event-day cluster bootstrap.

    Each draw resamples len(unique days) days with replacement and pools all
    quarter-hours of the drawn days, so days with more qualifying quarter-hours
    carry proportionally more weight -- the same weighting as the point estimate.

    Returns (mean, lo, hi, n_values, n_days). CI bounds are NaN if <2 days.
    """
    values = np.asarray(values, dtype=float)
    days = np.asarray(days)
    uniq, sums, counts = _day_aggregates(values, days)
    n_days = len(uniq)
    n_vals = int(counts.sum())
    if n_vals == 0:
        return np.nan, np.nan, np.nan, 0, 0
    mean = float(sums.sum() / counts.sum())
    if n_days < 2:
        return mean, np.nan, np.nan, n_vals, n_days

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n_days, size=(n_boot, n_days))
    boot = sums[idx].sum(axis=1) / counts[idx].sum(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return mean, float(lo), float(hi), n_vals, n_days


def eventday_bootstrap_weighted_mean(day_values, day_weights, n_boot: int = 5000,
                                     seed: int = SEED):
    """Weighted mean over days, with an event-day bootstrap CI.

    Used for the stratified excess-error test, where each day already carries a
    single value and a weight (its negative-quarter-hour count).
    """
    v = np.asarray(day_values, dtype=float)
    w = np.asarray(day_weights, dtype=float)
    ok = np.isfinite(v) & np.isfinite(w) & (w > 0)
    v, w = v[ok], w[ok]
    n_days = len(v)
    if n_days == 0:
        return np.nan, np.nan, np.nan, 0
    mean = float(np.sum(v * w) / np.sum(w))
    if n_days < 2:
        return mean, np.nan, np.nan, n_days
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n_days, size=(n_boot, n_days))
    num = (v[idx] * w[idx]).sum(axis=1)
    den = w[idx].sum(axis=1)
    boot = num / den
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return mean, float(lo), float(hi), n_days


def ci_excludes_zero(lo: float, hi: float) -> bool:
    if not (np.isfinite(lo) and np.isfinite(hi)):
        return False
    return (lo > 0 and hi > 0) or (lo < 0 and hi < 0)
