"""Scoring for E1 (spec section 7).

Reuses the event-day block bootstrap from `src/stats_boot.py` -- there is deliberately
no second bootstrap in this project, and no i.i.d. quarter-hour resampling anywhere.
The RQ1 kill test showed why: 5 of 99 event-days carried 45-60% of the error, so the
effective sample is a few dozen clustered episodes, not tens of thousands of
independent quarter-hours.

Errors are reported in **relative** terms as well as MW. The kill test also showed
that an MW-only comparison across subsamples is a scale artefact: the negative-quarter-
hour bias looked much larger in windy periods (-2,402 MW against -1,684 MW) purely
because the forecast base was 39% higher. In relative terms the two were
indistinguishable, -9.3% against -9.1%, which is what turned out to matter.
"""

from __future__ import annotations

import numpy as np

from src.stats_boot import (
    ci_excludes_zero,
    eventday_bootstrap_mean,
    eventday_bootstrap_ratio,
)

N_BOOT = 5000
SEED = 42


# ------------------------------------------------------------------ point accuracy


def mae_on(a_hat: np.ndarray, a_true: np.ndarray, mask: np.ndarray) -> float:
    if not mask.any():
        return float("nan")
    return float(np.abs(a_hat[mask] - a_true[mask]).mean())


def relative_mae_on(a_hat: np.ndarray, a_true: np.ndarray, mask: np.ndarray) -> float:
    """MAE divided by the mean true level on the same quarter-hours."""
    if not mask.any():
        return float("nan")
    base = float(np.abs(a_true[mask]).mean())
    return float("nan") if base == 0 else mae_on(a_hat, a_true, mask) / base


def bias_on(a_hat: np.ndarray, a_true: np.ndarray, mask: np.ndarray) -> float:
    """Signed mean error. Positive means the method overestimates available power."""
    if not mask.any():
        return float("nan")
    return float((a_hat[mask] - a_true[mask]).mean())


def mae_with_ci(a_hat, a_true, mask, days, n_boot=N_BOOT, seed=SEED):
    """MAE on `mask` with an event-day block-bootstrap CI, plus its relative form."""
    err = np.abs(a_hat - a_true)[mask]
    d = np.asarray(days)[mask]
    mean, lo, hi, n, n_days = eventday_bootstrap_mean(err, d, n_boot=n_boot, seed=seed)
    rel, rlo, rhi, _, _ = eventday_bootstrap_ratio(
        err, np.abs(a_true)[mask], d, n_boot=n_boot, seed=seed
    )
    return {
        "mae_mw": mean, "mae_lo": lo, "mae_hi": hi,
        "mae_rel": rel, "mae_rel_lo": rlo, "mae_rel_hi": rhi,
        "n_qh": n, "n_days": n_days,
    }


def paired_difference(err_a, err_b, mask, days, n_boot=N_BOOT, seed=SEED):
    """Mean of (err_a - err_b) with an event-day CI. Negative means A is better.

    This is the paired form the week-6 criterion asks for (spec section 7): the two
    methods are scored on the same quarter-hours and the *difference* is bootstrapped,
    which removes the day-to-day variation common to both.
    """
    d = np.asarray(days)[mask]
    diff = (np.asarray(err_a) - np.asarray(err_b))[mask]
    mean, lo, hi, n, n_days = eventday_bootstrap_mean(diff, d, n_boot=n_boot, seed=seed)
    return {
        "diff": mean, "lo": lo, "hi": hi, "n_qh": n, "n_days": n_days,
        "significant": ci_excludes_zero(lo, hi),
        "a_better": bool(np.isfinite(mean) and mean < 0 and ci_excludes_zero(lo, hi)),
    }


# ----------------------------------------------------------------- the response r


def integrated_response_error(
    r_hat: np.ndarray, r_true: np.ndarray, depth_grid: np.ndarray
) -> float:
    """Mean |r-hat - r*| over the depth grid, i.e. the integral divided by its width.

    Normalising by the width makes the number read as an average absolute error in
    response units, comparable across grids.
    """
    width = float(depth_grid[-1] - depth_grid[0])
    if width <= 0:
        return float("nan")
    return float(np.trapezoid(np.abs(r_hat - r_true), depth_grid) / width)


# -------------------------------------------------------------- distributional


def pinball(y: np.ndarray, q: np.ndarray, taus: np.ndarray, mask=None) -> float:
    if q is None:
        return float("nan")
    if mask is not None:
        y, q = y[mask], q[mask]
    err = y[:, None] - q
    return float(np.maximum(taus[None, :] * err, (taus[None, :] - 1.0) * err).mean())


def coverage(y: np.ndarray, q: np.ndarray, taus: np.ndarray, level: float,
             mask=None) -> float:
    """Share of observations inside the central interval at `level` (e.g. 0.8)."""
    if q is None:
        return float("nan")
    lo_t, hi_t = (1 - level) / 2, 1 - (1 - level) / 2
    i_lo = int(np.argmin(np.abs(taus - lo_t)))
    i_hi = int(np.argmin(np.abs(taus - hi_t)))
    if mask is not None:
        y, q = y[mask], q[mask]
    return float(((y >= q[:, i_lo]) & (y <= q[:, i_hi])).mean())


def crps_from_quantiles(y: np.ndarray, q: np.ndarray, taus: np.ndarray,
                        mask=None) -> float:
    """CRPS approximated from the quantile grid.

    For a quantile-based forecast the CRPS equals twice the mean pinball loss over a
    uniform tau grid in the limit of a fine grid (Gneiting & Raftery 2007). TAUS here
    is uniform on 0.05..0.95, so this is that approximation -- it is an approximation,
    and it ignores the tails beyond the outer quantiles.
    """
    return 2.0 * pinball(y, q, taus, mask=mask)


def pit_values(y: np.ndarray, q: np.ndarray, taus: np.ndarray, mask=None) -> np.ndarray:
    """PIT values by linear interpolation of the predicted quantiles.

    A calibrated forecast gives a flat PIT histogram. Values are clipped to [0, 1];
    observations outside the outer quantiles pile up at the ends, which is itself the
    diagnostic.
    """
    if q is None:
        return np.array([])
    if mask is not None:
        y, q = y[mask], q[mask]
    return np.array([np.interp(yi, qi, taus, left=0.0, right=1.0)
                     for yi, qi in zip(y, q)])


# ----------------------------------------------------------------------- assembly


def score_method(
    fit: dict,
    data,
    depth_grid: np.ndarray,
    r_hat: np.ndarray | None,
    r_true_curve: np.ndarray,
    taus: np.ndarray,
) -> dict:
    """One row of the results table for one method."""
    a_hat = fit["a_hat"]
    a_true = data.a_true_mw
    censored = data.censored
    days = data.berlin_date

    row = {
        "method": fit["name"],
        "epochs": fit.get("epochs_run", 0),
        "n_censored_qh": int(censored.sum()),
    }
    row.update({f"censored_{k}": v for k, v in
                mae_with_ci(a_hat, a_true, censored, days).items()})
    row["censored_bias_mw"] = bias_on(a_hat, a_true, censored)
    row["all_mae_mw"] = mae_on(a_hat, a_true, np.ones_like(censored, dtype=bool))
    row["all_mae_rel"] = relative_mae_on(a_hat, a_true, np.ones_like(censored, dtype=bool))
    row["uncensored_mae_mw"] = mae_on(a_hat, a_true, ~censored)

    q = fit.get("a_quantiles")
    row["pinball_a"] = pinball(a_true, q, taus)
    row["coverage80_a"] = coverage(a_true, q, taus, 0.80)
    row["coverage90_a"] = coverage(a_true, q, taus, 0.90)
    row["crps_a"] = crps_from_quantiles(a_true, q, taus)

    row["int_abs_r_error"] = (
        integrated_response_error(r_hat, r_true_curve, depth_grid)
        if r_hat is not None else float("nan")
    )
    return row
