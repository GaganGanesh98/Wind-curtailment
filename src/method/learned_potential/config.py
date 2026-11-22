"""Experiment 4, learning available power: every pre-registered constant, in one place.

Fixed in `docs/12_learned_potential_preregistration.md` (22 Nov 2026) before any model was
fitted on real data. The note shows these values through a generated block (`design_text`),
so the number checker holds the note to this file and a change here fails the suite.
"""

from __future__ import annotations

# ------------------------------------------------------------------------ data
AREAS = ("50Hertz", "Amprion", "TransnetBW")
HISTORY_START = "2024-01-01"            # training history (panel and solar forecast start here)
EVAL_WINDOW = ("2025-10-01", "2026-09-30")   # Experiment 3's window: every score is out of fold here
CLEAN_PRICE_ABOVE = 5.0                 # clean set: price > 5 EUR/MWh and R = 0 in the area
TARGET_PRICE_BELOW = 0.0                # target set: price < 0
EMBARGO_DAYS = 7                        # gap between the end of training and the scored month

# ------------------------------------------------------------- inputs (allow-list)
#: The only columns a learned potential may see. Derived only from day-ahead forecasts
#: published before the auction and from the calendar.
ALLOWED_FEATURES = ("f_onshore_mw", "f_offshore_mw", "f_solar_mw", "qh_of_day", "day_of_week",
                    "holiday", "area")
#: Never an input, in any model, in any form.
FORBIDDEN_FEATURES = frozenset({
    "price_eur_mwh", "price", "hour_mean_price", "theta", "s", "exposure", "depth", "runlen",
    "run_length", "hr_mw", "h", "projection", "act_onshore_mw", "act_offshore_mw", "act_wind_mw",
    "g", "y", "id_onshore_mw", "id_offshore_mw", "id_wind_mw", "e_mw", "e_id_mw", "rd_mw",
    "redispatch_mw", "clean", "target", "market_value",
})
CNN_HALF_WINDOW_QH = 24                 # N1 sees the allowed forecasts from -6 h to +6 h

# ------------------------------------------------------------- domain classifier
DOMAIN_PARAMS = {"num_leaves": 31, "learning_rate": 0.05, "n_estimators": 300,
                 "min_child_samples": 100}
WEIGHT_CLIP_PERCENTILE = 99
OVERLAP_P = 0.99                        # a target quarter-hour with p above this has no overlap
OVERLAP_STOP_SHARE = 0.10               # stop if more target quarter-hours than this lack overlap
LOOKALIKE_TOP_SHARE = 0.10              # look-alike = clean quarter-hours in the top decile of p

# ------------------------------------------------------------------------- models
QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.95)
SEED = 42
GBM_FIXED = {"learning_rate": 0.03, "min_child_samples": 100, "subsample": 0.8,
             "subsample_freq": 1}
GBM_GRID = ({"num_leaves": 15, "n_estimators": 300}, {"num_leaves": 31, "n_estimators": 300},
            {"num_leaves": 15, "n_estimators": 800}, {"num_leaves": 31, "n_estimators": 800})
CNN_FIXED = {"kernel": 5, "lr": 1e-3, "batch": 512, "max_epochs": 40, "patience": 6,
             "val_days": 28}
CNN_GRID = ({"layers": 2, "channels": 16}, {"layers": 2, "channels": 32},
            {"layers": 3, "channels": 16}, {"layers": 3, "channels": 32})
#: Hyperparameters are chosen once, on this fold, before the evaluation window, then fixed.
SELECTION_TRAIN_END = "2025-08-24"      # last training day (EMBARGO_DAYS before validation)
SELECTION_VALIDATION_MONTH = "2025-09"

# ----------------------------------------------------------------- scoring, budget
N_BOOT = 5000
S2_HALF_WIDTH = 0.02                    # look-alike bias interval must lie within this
TIE_DECIMALS = 4                        # |bias| ties, broken by sigma
CANDIDATES = ("L1", "L2", "N1")         # models the selection rule chooses among
AGREE_BREAKDOWN_TOLERANCE = 0.01        # Experiment 3 arm agrees if breakdown moves less than this

# ------------------------------------------- Amendment 1 (22 Nov 2026), docs/12
OVERLAP_TRIM_P = OVERLAP_P              # primary estimand keeps target quarter-hours with p <= this
PRIMARY_ESTIMAND = "trimmed"            # b-hat_H and B-hat over target quarter-hours with overlap
V1_TOLERANCE = 0.02                     # E1's validation test: difference interval within this
V1_BOOTSTRAP_DRAWS = N_BOOT


def design_text() -> str:
    """The design block of docs/12 (generated, so the number checker holds it)."""
    q = ", ".join(f"{x:g}" for x in QUANTILES)
    g = "; ".join(f"{d['num_leaves']} leaves, {d['n_estimators']} trees" for d in GBM_GRID)
    c = "; ".join(f"{d['layers']} layers, {d['channels']} channels" for d in CNN_GRID)
    return "\n".join([
        f"- **Data.** Control areas {', '.join(AREAS)}; quarter-hours from {HISTORY_START}; every "
        f"score and the budget use the evaluation window {EVAL_WINDOW[0]} to {EVAL_WINDOW[1]}.",
        f"- **Clean set:** price above {CLEAN_PRICE_ABOVE:g} €/MWh and no renewable redispatch in the "
        f"area. **Target set:** price below {TARGET_PRICE_BELOW:g}.",
        f"- **Folds.** Rolling origin by calendar month over the evaluation window: the model for "
        f"month m is trained on clean quarter-hours from {HISTORY_START} to {EMBARGO_DAYS} days "
        f"before m starts, and predicts all of month m. Never shuffled.",
        f"- **Domain classifier.** Gradient-boosted ({DOMAIN_PARAMS['num_leaves']} leaves, learning "
        f"rate {DOMAIN_PARAMS['learning_rate']:g}, {DOMAIN_PARAMS['n_estimators']} trees, at least "
        f"{DOMAIN_PARAMS['min_child_samples']} rows per leaf), cross-fitted leaving one calendar "
        f"month out. Weights w = p/(1 − p) × n_clean/n_target, clipped at their "
        f"{WEIGHT_CLIP_PERCENTILE}th percentile. No overlap: p above {OVERLAP_P:g}; stop if more than "
        f"{OVERLAP_STOP_SHARE:.0%} of target quarter-hours lack overlap. Look-alike: clean "
        f"quarter-hours in the evaluation window in the top {LOOKALIKE_TOP_SHARE:.0%} of p.",
        f"- **L1, L2.** LightGBM quantile models at {q}; learning rate "
        f"{GBM_FIXED['learning_rate']:g}, at least {GBM_FIXED['min_child_samples']} rows per leaf, "
        f"row subsample {GBM_FIXED['subsample']:g}; grid: {g}.",
        f"- **N1.** Temporal CNN over the allowed forecasts from −{CNN_HALF_WINDOW_QH // 4} h to "
        f"+{CNN_HALF_WINDOW_QH // 4} h, kernel {CNN_FIXED['kernel']}, quantile heads at {q}, pinball "
        f"loss, Adam at {CNN_FIXED['lr']:g}, batch {CNN_FIXED['batch']}, at most "
        f"{CNN_FIXED['max_epochs']} epochs, early stopping after {CNN_FIXED['patience']} epochs "
        f"without improvement on the last {CNN_FIXED['val_days']} days of the training span; grid: "
        f"{c}; seed {SEED}, CPU, deterministic.",
        f"- **Hyperparameters** chosen once: train to {SELECTION_TRAIN_END}, validate on clean "
        f"quarter-hours of {SELECTION_VALIDATION_MONTH} (median pinball loss, importance-weighted "
        f"for L2 and N1), then fixed for every fold.",
        f"- **Intervals.** Day-block bootstrap, {N_BOOT:,} draws, seed {SEED}.",
        f"- **S2 tolerance:** ±{S2_HALF_WIDTH:g}. **Ties** in |bias| at {TIE_DECIMALS} decimals, "
        f"broken by σ. **Agreement** of the Experiment 3 arm: same verdict at B = 0 and breakdown "
        f"within {AGREE_BREAKDOWN_TOLERANCE:g}.",
    ])
