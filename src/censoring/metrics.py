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


QH_HOURS = 0.25  # a quarter-hour, for turning MW into MWh


def curtailed_energy_error(a_hat, a_true, g_obs, mask) -> dict:
    """Error in the recovered curtailed ENERGY on censored quarter-hours.

        estimated = sum(A-hat - G) * 0.25 MWh
        true      = sum(A_true - G) * 0.25 MWh
        error     = |estimated - true| = |sum(A-hat - A_true)| * 0.25

    This is the quantity a system operator or a regulator would actually quote: how
    much generation was switched off. It is the headline E1 metric alongside the bias
    (spec v1.6).

    **It is not independent of the bias.** The G terms cancel, so the absolute error
    equals |bias| * n_censored * 0.25 exactly, and the two rank methods identically on
    the same sample. Criterion (b) of the revised gate asks for both, so it is in
    substance one test, not two. The relative form below is the part that adds
    information, because it scales the error by how much was really curtailed.
    """
    if not mask.any():
        return {"est_mwh": float("nan"), "true_mwh": float("nan"),
                "abs_error_mwh": float("nan"), "rel_error": float("nan")}
    est = float((a_hat[mask] - g_obs[mask]).sum() * QH_HOURS)
    true = float((a_true[mask] - g_obs[mask]).sum() * QH_HOURS)
    abs_err = abs(est - true)
    return {
        "est_mwh": est,
        "true_mwh": true,
        "abs_error_mwh": abs_err,
        "rel_error": abs_err / abs(true) if true != 0 else float("nan"),
    }


def bias_with_ci(a_hat, a_true, mask, days, n_boot=N_BOOT, seed=SEED):
    """Signed mean error on `mask`, with an event-day block-bootstrap CI.

    Headline E1 metric (spec v1.6). MAE cannot separate a method that is unbiased and
    noisy from one that is systematically wrong in one direction, and systematic
    direction is the whole point here: a method that treats curtailment as noise is
    biased down, one that treats every exposed quarter-hour as censored is biased up.
    """
    err = (np.asarray(a_hat) - np.asarray(a_true))[mask]
    d = np.asarray(days)[mask]
    mean, lo, hi, n, n_days = eventday_bootstrap_mean(err, d, n_boot=n_boot, seed=seed)
    return {"bias_mw": mean, "bias_lo": lo, "bias_hi": hi,
            "bias_n_qh": n, "bias_n_days": n_days,
            "bias_excludes_zero": ci_excludes_zero(lo, hi)}


def paired_abs_bias(err_a_signed, err_b_signed, mask, days, n_boot=N_BOOT, seed=SEED):
    """Is |bias of A| lower than |bias of B|? Bootstrapped on the same drawn days.

    A paired test on absolute bias cannot be done by bootstrapping a per-observation
    difference, because |mean| is not the mean of anything. The day-block resample is
    therefore done here directly: each draw recomputes both biases on the drawn days
    and takes the difference of their absolute values.
    """
    a = np.asarray(err_a_signed)[mask]
    b = np.asarray(err_b_signed)[mask]
    d = np.asarray(days)[mask]
    uniq, inv = np.unique(d, return_inverse=True)
    n_days = len(uniq)
    a_sum = np.bincount(inv, weights=a, minlength=n_days)
    b_sum = np.bincount(inv, weights=b, minlength=n_days)
    counts = np.bincount(inv, minlength=n_days).astype(float)
    point = abs(a_sum.sum() / counts.sum()) - abs(b_sum.sum() / counts.sum())
    if n_days < 2:
        return {"diff": point, "lo": np.nan, "hi": np.nan, "significant": False,
                "a_better": False}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n_days, size=(n_boot, n_days))
    n = counts[idx].sum(axis=1)
    boot = np.abs(a_sum[idx].sum(axis=1) / n) - np.abs(b_sum[idx].sum(axis=1) / n)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {"diff": float(point), "lo": float(lo), "hi": float(hi),
            "significant": ci_excludes_zero(lo, hi),
            "a_better": bool(point < 0 and ci_excludes_zero(lo, hi))}


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


# ------------------------------------------- self-contained recovery measures

def recovery_skill(mae_method: float, mae_b0: float, mae_oracle: float) -> float:
    """S = (MAE_B0 - MAE_method) / (MAE_B0 - MAE_oracle).

    How much of the *recoverable* gap a method closed. 1.0 is the oracle, which is
    trained on the true A and is therefore the information ceiling; 0.0 is the raw
    TSO day-ahead forecast, the operational status quo. Negative means worse than
    doing nothing.

    This is the measure the week-6 gate uses instead of "beat each of B1-B4"
    (spec v1.7). Two reasons. It is anchored on quantities that belong to this
    project -- the published forecast and our own oracle -- rather than on how a
    rival method happens to behave, so it cannot be failed by an accident of
    someone else's design. And it is bounded and interpretable, where a raw MW
    difference is neither: the recoverable headroom here is only 125-241 MW against
    a 1,200-1,800 MW error, which a difference in MW hides and a skill score makes
    obvious.
    """
    denominator = mae_b0 - mae_oracle
    if not np.isfinite(denominator) or abs(denominator) < 1e-9:
        return float("nan")
    return float((mae_b0 - mae_method) / denominator)


def curtailment_recovery(c_hat, c_true, mask) -> dict:
    """How well the model recovers the switched-off share c_t itself.

    This is the one quantity no baseline produces at all: B1-B4 estimate available
    power and never say what fraction of the fleet switched off in a given
    quarter-hour. There is therefore nothing to compare against and nothing to
    argue about -- the comparison is against the truth the benchmark knows.

    Returns MAE and bias on c, the correlation with the truth, and the total
    switched-off share, all on the censored quarter-hours.
    """
    if c_hat is None or not mask.any():
        return {"c_mae": float("nan"), "c_bias": float("nan"),
                "c_corr": float("nan"), "c_total_hat": float("nan"),
                "c_total_true": float("nan")}
    ch, ct = np.asarray(c_hat)[mask], np.asarray(c_true)[mask]
    corr = float(np.corrcoef(ch, ct)[0, 1]) if ch.std() > 0 and ct.std() > 0 else float("nan")
    return {
        "c_mae": float(np.abs(ch - ct).mean()),
        "c_bias": float((ch - ct).mean()),
        "c_corr": corr,
        "c_total_hat": float(ch.sum()),
        "c_total_true": float(ct.sum()),
    }


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
    # Headline metrics (spec v1.6): bias and curtailed-energy error.
    row.update(bias_with_ci(a_hat, a_true, censored, days))
    row.update({f"energy_{k}": v for k, v in
                curtailed_energy_error(a_hat, a_true, data.g_obs_mw, censored).items()})
    # Secondary: MAE.
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

    row.update(curtailment_recovery(fit.get("c_hat"), data.c_true, censored))

    row["int_abs_r_error"] = (
        integrated_response_error(r_hat, r_true_curve, depth_grid)
        if r_hat is not None else float("nan")
    )
    return row
