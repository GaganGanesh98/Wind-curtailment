"""Experiment 4b, a grid-operator-style hybrid available-power model: every pre-registered
constant, in one place.

Fixed in `docs/24_exp4b_hybrid_potential_preregistration.md` (23 Nov 2026) before any model was
fitted on real data. The note shows these values through generated blocks (`design_text`), so
the number checker holds the note to this file and a change here fails the suite.

Experiment 4 (`src/method/learned_potential/`) is not changed. Where 4b copies one of its rules,
the constant is imported from there, so the two cannot drift apart.
"""

from __future__ import annotations

from pathlib import Path

from src.method.learned_potential import config as e4

REPO_ROOT = Path(__file__).resolve().parents[3]
ART = REPO_ROOT / "artifacts" / "exp4b_hybrid_potential"
ERA5_DIR = REPO_ROOT / "data" / "raw" / "era5"
DWD_DIR = REPO_ROOT / "data" / "raw" / "dwd" / "hourly_wind"
MASTR_DIR = REPO_ROOT / "data" / "raw" / "mastr" / "2026-10-31"
MASTR_PROCESSED = REPO_ROOT / "data" / "processed" / "mastr_wind_2026-10-31.parquet"

# ------------------------------------------------------------------------ data
AREAS = e4.AREAS
PERIOD = ("2024-01-01", "2026-09-30")          # training and evaluation, Berlin dates, 33 months
EVAL_WINDOW = e4.EVAL_WINDOW                   # Experiment 3's window; every score is out of fold
EMBARGO_DAYS = e4.EMBARGO_DAYS
CLEAN_PRICE_ABOVE = e4.CLEAN_PRICE_ABOVE       # every quarter-hour of a clean hour
TARGET_PRICE_BELOW = e4.TARGET_PRICE_BELOW     # a target hour has at least one such quarter-hour
REDISPATCH_TOLERANCE = 0.02                    # unit check, as redispatch_checks.TOLERANCE

# ------------------------------------------------------------------ weather inputs
ERA5_VARS = ("u100", "v100", "u10", "v10", "t2m", "sp", "i10fg")
ERA5_FIRST_MONTH_USED = "2024-01"              # earlier months are on disk and unused
DWD_MIN_COVERAGE = 0.90                        # share of PERIOD's hours with a valid wind speed

# ----------------------------------------------------------- layer 1: physics
SHEAR_CLIP = (0.0, 0.45)                       # power-law exponent from ERA5 10 m and 100 m
SHEAR_FALLBACK = 1.0 / 7.0                     # when either ERA5 speed is below SHEAR_MIN_SPEED
SHEAR_MIN_SPEED = 0.5                          # m/s
RHO0 = 1.225                                   # kg/m³, power-curve reference density
R_DRY = 287.05                                 # J/(kg K), air density = sp / (R_DRY · t2m)
CUT_IN = 3.0                                   # m/s
CUT_OUT = 25.0                                 # m/s, storm cut-out: zero output at or above
CP_DESIGN = 0.45                               # sets the rated speed from the specific power
NEW_CAPACITY_DAYS = 183                        # "installed in the last 6 months"

# --------------------------------------------------------- layer 2: correction
KAPPA = 0.01                                   # offset, share of installed capacity
QUANTILES = e4.QUANTILES
SEED = e4.SEED
GBM_FIXED = e4.GBM_FIXED
GBM_GRID = e4.GBM_GRID
SELECTION_TRAIN_END = e4.SELECTION_TRAIN_END
SELECTION_VALIDATION_MONTH = e4.SELECTION_VALIDATION_MONTH

#: The only columns Layer 2 and the domain classifier may see. Weather, the physical
#: potential computed from weather and MaStR, the fleet's age profile, and the calendar.
ALLOWED_FEATURES = ("p_phys_cf", "era5_ws100", "era5_ws_hub", "era5_dir_sin", "era5_dir_cos",
                    "era5_rho", "era5_gust", "era5_gust_ratio", "era5_shear", "era5_t2m",
                    "dwd_ws", "new_cap_share", "hour_utc", "month_of_year", "area")
#: Never an input, in any model, in any form. Experiment 4's list, plus the day-ahead
#: forecasts F, which were Experiment 4's inputs and are now excluded as contaminated.
FORBIDDEN_FEATURES = e4.FORBIDDEN_FEATURES | frozenset({
    "f_onshore_mw", "f_offshore_mw", "f_solar_mw", "da_onshore_mw", "da_offshore_mw",
    "da_wind_mw", "f", "forecast", "g_mw", "h_mw", "rd_any", "unit_check_fail", "p",
    "weight", "lookalike", "event_day",
})

# ------------------------------------------------------------- domain, scoring, budget
DOMAIN_PARAMS = e4.DOMAIN_PARAMS
WEIGHT_CLIP_PERCENTILE = e4.WEIGHT_CLIP_PERCENTILE
OVERLAP_P = e4.OVERLAP_P
LOOKALIKE_TOP_SHARE = e4.LOOKALIKE_TOP_SHARE
N_BOOT = e4.N_BOOT
S2_HALF_WIDTH = e4.S2_HALF_WIDTH
TIE_DECIMALS = e4.TIE_DECIMALS
CANDIDATES = ("P0", "H1", "H2")
AGREE_BREAKDOWN_TOLERANCE = e4.AGREE_BREAKDOWN_TOLERANCE
PRIMARY_ESTIMAND = e4.PRIMARY_ESTIMAND         # "trimmed", Amendment 1 of docs/12


def design_text() -> str:
    """The design block of docs/24 (generated, so the number checker holds it)."""
    q = ", ".join(f"{x:g}" for x in QUANTILES)
    g = "; ".join(f"{d['num_leaves']} leaves, {d['n_estimators']} trees" for d in GBM_GRID)
    return "\n".join([
        f"- **Data.** Control areas {', '.join(AREAS)}; hours from {PERIOD[0]} to {PERIOD[1]} "
        f"(Berlin dates); every score and the budget use the evaluation window {EVAL_WINDOW[0]} "
        f"to {EVAL_WINDOW[1]}. ERA5 months from {ERA5_FIRST_MONTH_USED} on are used.",
        f"- **Clean hour:** every quarter-hour priced above {CLEAN_PRICE_ABOVE:g} €/MWh with G > 0, "
        f"no onshore-wind redispatch measure (proxy below) and no renewable reduction failing the "
        f"unit check (more than {REDISPATCH_TOLERANCE:.0%} apart) touching the hour in the area. "
        f"**Target hour:** at least one quarter-hour priced below {TARGET_PRICE_BELOW:g}.",
        f"- **Folds.** Rolling origin by calendar month over the evaluation window: the model for "
        f"month m is trained on clean hours from {PERIOD[0]} to {EMBARGO_DAYS} days before m "
        f"starts, and predicts all of month m. Never shuffled.",
        f"- **Physics (Layer 1).** Hub-height speed by the power law from ERA5's 100 m speed, "
        f"exponent from ERA5's 10 m and 100 m speeds in the same cell and hour, clipped to "
        f"[{SHEAR_CLIP[0]:g}, {SHEAR_CLIP[1]:g}], and {SHEAR_FALLBACK:.4f} when either speed is "
        f"below {SHEAR_MIN_SPEED:g} m/s. Density-equivalent speed v·(ρ/{RHO0:g})^(1/3), "
        f"ρ = sp / ({R_DRY:g} · t2m). Power curve per turbine from its specific power: zero below "
        f"{CUT_IN:g} m/s and at or above {CUT_OUT:g} m/s; rated speed (2 · specific power / "
        f"({RHO0:g} · {CP_DESIGN:g}))^(1/3); (v³ − {CUT_IN:g}³)/(v_rated³ − {CUT_IN:g}³) of rated "
        f"power in between.",
        f"- **Correction (Layer 2).** Target y = log((G + {KAPPA:g}·C) / (P_phys + {KAPPA:g}·C)), "
        f"C the installed capacity of the area and hour. LightGBM quantile models at {q}; learning "
        f"rate {GBM_FIXED['learning_rate']:g}, at least {GBM_FIXED['min_child_samples']} rows per "
        f"leaf, row subsample {GBM_FIXED['subsample']:g}; grid: {g}. Â = max((P_phys + "
        f"{KAPPA:g}·C) · exp(ŷ₀.₅) − {KAPPA:g}·C, 0).",
        f"- **New capacity input:** the share of C commissioned in the last {NEW_CAPACITY_DAYS} days.",
        f"- **DWD stations:** those with a valid hourly wind speed in at least "
        f"{DWD_MIN_COVERAGE:.0%} of the period's hours.",
        f"- **Domain classifier.** Gradient-boosted ({DOMAIN_PARAMS['num_leaves']} leaves, learning "
        f"rate {DOMAIN_PARAMS['learning_rate']:g}, {DOMAIN_PARAMS['n_estimators']} trees, at least "
        f"{DOMAIN_PARAMS['min_child_samples']} rows per leaf), on the allowed inputs, cross-fitted "
        f"leaving one calendar month out. Weights w = p/(1 − p) × n_clean/n_target, clipped at their "
        f"{WEIGHT_CLIP_PERCENTILE}th percentile. No overlap: p above {OVERLAP_P:g}. Look-alike: "
        f"clean hours in the evaluation window in the top {LOOKALIKE_TOP_SHARE:.0%} of p.",
        f"- **Hyperparameters** chosen once: train to {SELECTION_TRAIN_END}, validate on clean hours "
        f"of {SELECTION_VALIDATION_MONTH} (median pinball loss, importance-weighted for H2), then "
        f"fixed for every fold.",
        f"- **Intervals.** Day-block bootstrap, {N_BOOT:,} draws, seed {SEED}.",
        f"- **S2 tolerance:** ±{S2_HALF_WIDTH:g}. **Ties** in |bias| at {TIE_DECIMALS} decimals, "
        f"broken by σ. **Agreement** of the Experiment 3 arm: same verdict at B = 0 and breakdown "
        f"within {AGREE_BREAKDOWN_TOLERANCE:g}.",
    ])


#: What each allowed input is. Every weather value is a capacity-weighted mean over the area's
#: live turbines at their interpolated locations; the hour [h, h+1) takes the mean of ERA5's
#: instantaneous fields at h and h+1.
FEATURE_TEXT = {
    "p_phys_cf": "Layer 1's physical potential P_phys divided by installed capacity C",
    "era5_ws100": "ERA5 100 m wind speed",
    "era5_ws_hub": "hub-height wind speed (before the density correction)",
    "era5_dir_sin": "sine of the direction of the capacity-weighted 100 m wind vector",
    "era5_dir_cos": "cosine of the same direction",
    "era5_rho": "air density sp / (R · t2m)",
    "era5_gust": "ERA5 instantaneous 10 m gust",
    "era5_gust_ratio": "gust divided by the 10 m speed (turbulence proxy)",
    "era5_shear": "power-law shear exponent used for the hub-height speed",
    "era5_t2m": "2 m temperature (icing)",
    "dwd_ws": "DWD station hourly wind speed, each turbine's nearest qualifying station",
    "new_cap_share": "share of C commissioned in the last NEW_CAPACITY_DAYS days",
    "hour_utc": "hour of the day, UTC",
    "month_of_year": "calendar month",
    "area": "control area",
}


def inputs_text() -> str:
    return "\n".join(f"- `{k}`: {FEATURE_TEXT[k].replace('NEW_CAPACITY_DAYS', str(NEW_CAPACITY_DAYS))}."
                     for k in ALLOWED_FEATURES)
