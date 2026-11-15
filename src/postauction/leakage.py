"""Forecast-time allow-list for Phase P (hard rule 4 of the Phase P brief).

Forecast time is **12:57 CET on D-1**, the moment the SDAC day-ahead results are
published. Two closed sets are enforced:

  POSTAUCTION_ALLOWED   what any Phase P model -- (a) to (d) -- may see:
                        the TSO day-ahead forecast F, the day-ahead quarter-hour
                        price and its hourly mean, run lengths on both s.51 clocks,
                        exposure s and depth per cohort (cohorts.py), capacity
                        shares w, the month-to-date market value known by D-1,
                        and deterministic calendar terms (hour-of-day Fourier x
                        season). Nothing else.
  STAGE_A_ALLOWED       the strict subset the latent head of model (d) may see.
                        No price, no theta, no s, no depth: spec section 4, so A
                        cannot absorb curtailment.

Everything on FORBIDDEN is leakage at 12:57 CET D-1 or is excluded by the brief:
the same-quarter-hour actuals, the intraday forecast (no published vintage),
redispatch, reBAP (an evaluation weight only), the published monthly market value
(released after the month ends), ERA5 and the stitched Open-Meteo Historical
Forecast, and the Online-Hochrechnung (published after the fact; a T1 proxy for A).

`tests/test_leakage_postauction.py` asserts that every forbidden name is rejected,
that an unknown name is rejected rather than tolerated, and that theta is built from
the month-to-date series and never from the published one.
"""

from __future__ import annotations

from typing import Iterable

FORECAST_TIME = "12:57 CET D-1 (SDAC day-ahead publication)"

# Exact column names a Phase P model may receive. Cohort-indexed features are
# matched by prefix (see ALLOWED_PREFIXES) because the cohort set is data-driven.
POSTAUCTION_ALLOWED: frozenset[str] = frozenset({
    "forecast_mw",                     # F: da_onshore_mw (primary) or da_wind_mw
    "price_eur_mwh",                   # day-ahead quarter-hour price
    "hour_mean_price_eur_mwh",         # arithmetic mean of the hour's four QH prices
    "run_length_qh_clock",             # consecutive negative QHs (R09 clock)
    "run_length_hour_clock",           # consecutive negative hours (hourly-mean clock)
    "exposed_share",                   # sum_k w_k s_k
    "weighted_depth",                  # sum_k w_k s_k depth_k
    "mv_t2_known_by_d_minus_1",        # month-to-date market value, rule 17
    "mv_ytd_known_by_d_minus_1",       # year-to-date, for annual-reference cohorts
    "hour_sin_24h", "hour_cos_24h", "hour_sin_12h", "hour_cos_12h",
    "season_djf", "season_mam", "season_jja", "season_son",
})
ALLOWED_PREFIXES: tuple[str, ...] = ("s_", "depth_", "runlen_", "share_", "hour_x_season_")

STAGE_A_ALLOWED: frozenset[str] = frozenset({
    "forecast_mw",
    "hour_sin_24h", "hour_cos_24h", "hour_sin_12h", "hour_cos_12h",
    "season_djf", "season_mam", "season_jja", "season_son",
})
STAGE_A_PREFIXES: tuple[str, ...] = ("hour_x_season_",)

FORBIDDEN: frozenset[str] = frozenset({
    # same-quarter-hour actuals and the error itself
    "act_wind_mw", "act_onshore_mw", "act_offshore_mw", "g_obs_mw", "e_mw",
    # intraday forecast: no published vintage, refreshed by the TSOs
    "id_wind_mw", "id_onshore_mw", "id_offshore_mw", "e_id_mw",
    # ex post
    "redispatch_mw", "redispatch_volume", "redispatch_onshore_mw",
    # reBAP is an evaluation weight only
    "rebap_eur_mwh", "rebap", "rebap_ueberdeckt_eur_mwh", "rebap_unterdeckt_eur_mwh",
    # released after the month ends
    "market_value_published", "marktwert_published", "mv_wind_onshore",
    "mv_wind_onshore_published", "jw_published",
    # weather that contains information from after D-1
    "weather_ms_era5", "era5_ws100", "era5_ws10", "era5_air_density",
    "weather_ms_historical_forecast", "openmeteo_historical_forecast_ws100",
    # the Online-Hochrechnung (Anlage 1 Nr. 5.1): published after the fact
    "online_hochrechnung_mw", "hochrechnung_wind_onshore_mw", "hochrechnung_mw",
    # the ex-post potential of P2
    "potential_weather_mw", "p_weather_mw",
})
FORBIDDEN_PREFIXES: tuple[str, ...] = ("act_", "id_", "era5_", "rebap", "redispatch",
                                       "hochrechnung", "openmeteo_historical")

# The one admissible source of the market value that enters theta at forecast time.
THETA_MV_SOURCE_T2 = "mv_t2_known_by_d_minus_1"
THETA_MV_SOURCES_FORBIDDEN = ("read_published", "Monatsmarktwerte", "published",
                              "mv_wind_onshore")


def _is_forbidden(name: str) -> bool:
    return name in FORBIDDEN or name.startswith(FORBIDDEN_PREFIXES)


def _is_allowed(name: str, exact: frozenset[str], prefixes: tuple[str, ...]) -> bool:
    return name in exact or name.startswith(prefixes)


def check_postauction_inputs(names: Iterable[str]) -> None:
    """Raise unless every name is on the forecast-time allow-list.

    Fails loudly rather than dropping a column (hard rule 8 of the brief): a silently
    dropped feature looks exactly like a passing test.
    """
    names = list(names)
    bad = [n for n in names if _is_forbidden(n)]
    if bad:
        raise ValueError(
            f"Forbidden input(s) {bad} offered to a Phase P model. Not known at "
            f"{FORECAST_TIME}, or excluded by the Phase P brief (rule 4)."
        )
    outside = [n for n in names if not _is_allowed(n, POSTAUCTION_ALLOWED, ALLOWED_PREFIXES)]
    if outside:
        raise ValueError(
            f"Input(s) {outside} are outside the closed forecast-time set. "
            f"Allowed: {sorted(POSTAUCTION_ALLOWED)} plus prefixes {ALLOWED_PREFIXES}."
        )


def check_stage_a_inputs(names: Iterable[str]) -> None:
    """The latent head of model (d): no price, theta, s, depth or run length."""
    names = list(names)
    check_postauction_inputs(names)
    outside = [n for n in names if not _is_allowed(n, STAGE_A_ALLOWED, STAGE_A_PREFIXES)]
    if outside:
        raise ValueError(
            f"Input(s) {outside} must not reach stage A of model (d): price, exposure "
            "and depth would let A absorb the curtailment (spec section 4)."
        )


def check_theta_provenance(source: str) -> None:
    """theta at forecast time is built from the month-to-date market value only."""
    if source != THETA_MV_SOURCE_T2 or any(f in source for f in THETA_MV_SOURCES_FORBIDDEN):
        raise ValueError(
            f"theta provenance {source!r} is not {THETA_MV_SOURCE_T2!r}. The published "
            "monthly market value is released after the month ends (rule 17 / spec v1.4)."
        )


def check_frame_columns(columns: Iterable[str], *, stage_a: bool = False) -> None:
    """Convenience for a feature frame: every column is checked, index columns aside."""
    skip = {"ts_utc", "ts_utc_dt", "berlin_date", "area", "hour_berlin", "band",
            "neg", "deep", "safe", "fold", "event_day"}
    names = [c for c in columns if c not in skip]
    (check_stage_a_inputs if stage_a else check_postauction_inputs)(names)
