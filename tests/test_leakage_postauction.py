"""Phase P forecast-time allow-list (brief rule 4). Extends tests/test_leakage.py.

Three failures are covered: a forbidden column reaching a Phase P model; an unknown
column being tolerated instead of refused; and theta being built from the published
monthly market value instead of the month-to-date series known by D-1.
"""

from __future__ import annotations

import pytest

from src.method.stage_a.latent_model import FORBIDDEN_FEATURES as LATENT_FORBIDDEN
from src.postauction.leakage import (
    FORBIDDEN,
    POSTAUCTION_ALLOWED,
    STAGE_A_ALLOWED,
    THETA_MV_SOURCE_T2,
    check_frame_columns,
    check_postauction_inputs,
    check_stage_a_inputs,
    check_theta_provenance,
)

PANEL_ACTUAL_AND_INTRADAY = ["act_wind_mw", "act_onshore_mw", "act_offshore_mw",
                             "id_wind_mw", "id_onshore_mw", "id_offshore_mw",
                             "e_mw", "e_id_mw"]


@pytest.mark.parametrize("bad", sorted(FORBIDDEN))
def test_every_forbidden_input_is_rejected(bad):
    with pytest.raises(ValueError, match="Forbidden input"):
        check_postauction_inputs(["forecast_mw", "price_eur_mwh", bad])


@pytest.mark.parametrize("col", PANEL_ACTUAL_AND_INTRADAY)
def test_every_panel_actual_and_intraday_column_is_forbidden(col):
    """The panel's own column names, so a rename upstream cannot slip past."""
    with pytest.raises(ValueError, match="Forbidden input"):
        check_postauction_inputs([col])


@pytest.mark.parametrize("bad", ["rebap_eur_mwh", "rebap_x", "era5_ws100",
                                 "redispatch_wind_mw", "hochrechnung_anything",
                                 "openmeteo_historical_forecast_ws100"])
def test_forbidden_prefixes_catch_renamed_variants(bad):
    with pytest.raises(ValueError, match="Forbidden input"):
        check_postauction_inputs([bad])


def test_the_full_allowed_set_passes():
    check_postauction_inputs(sorted(POSTAUCTION_ALLOWED)
                             + ["s_wind2016_2020_6h", "depth_wind2016_2020_6h",
                                "runlen_wind2016_2020_6h", "share_wind2016_2020_6h"])


def test_unknown_input_is_refused_not_tolerated():
    """Closed set: an unlisted column is a leak until shown otherwise."""
    with pytest.raises(ValueError, match="outside the closed forecast-time set"):
        check_postauction_inputs(["forecast_mw", "solar_da_mw"])
    with pytest.raises(ValueError, match="outside the closed forecast-time set"):
        check_postauction_inputs(["forecast_mw", "weather_ms_icon_d1"])


def test_stage_a_rejects_price_exposure_and_depth():
    check_stage_a_inputs(sorted(STAGE_A_ALLOWED))
    for leak in ("price_eur_mwh", "s_post_feb2025_qh", "depth_post_feb2025_qh",
                 "exposed_share", "weighted_depth", "run_length_hour_clock",
                 "mv_t2_known_by_d_minus_1"):
        with pytest.raises(ValueError, match="must not reach stage A"):
            check_stage_a_inputs(["forecast_mw", leak])


def test_stage_a_set_is_a_subset_of_the_postauction_set():
    assert STAGE_A_ALLOWED <= POSTAUCTION_ALLOWED


def test_allowed_and_forbidden_are_disjoint():
    assert not (POSTAUCTION_ALLOWED & FORBIDDEN)


def test_latent_head_forbidden_list_is_still_honoured_for_stage_a():
    """Everything model.py forbids the latent head stays forbidden for stage A here,
    whether through FORBIDDEN or through the closed stage-A set."""
    for name in sorted(LATENT_FORBIDDEN):
        with pytest.raises(ValueError):
            check_stage_a_inputs(["forecast_mw", name])


def test_theta_provenance_must_be_the_month_to_date_series():
    check_theta_provenance(THETA_MV_SOURCE_T2)
    for bad in ("read_published", "Monatsmarktwerte_2026.csv", "mv_wind_onshore",
                "published", ""):
        with pytest.raises(ValueError, match="theta provenance"):
            check_theta_provenance(bad)


def test_frame_check_ignores_index_columns_and_catches_a_leak():
    check_frame_columns(["ts_utc", "berlin_date", "area", "forecast_mw", "price_eur_mwh"])
    with pytest.raises(ValueError, match="Forbidden input"):
        check_frame_columns(["ts_utc", "berlin_date", "forecast_mw", "act_onshore_mw"])
    with pytest.raises(ValueError, match="must not reach stage A"):
        check_frame_columns(["ts_utc", "forecast_mw", "price_eur_mwh"], stage_a=True)


def test_phase_k_bridge_columns_are_never_forecast_inputs():
    """Phase K (docs/K0_preregistration.md rule 7): the bias bridge reads H, which is ex
    post. Its columns must stay off the forecast-time allow-list, and no forecasting module
    may import the bridge."""
    import pathlib
    from src.potential.k_bridge_data import UNITS
    for u in UNITS:
        for col in (f"H_{u}", f"RD_{u}", f"G_{u}", "y_bias_log_ratio", "hr_mw"):
            with pytest.raises(ValueError):
                check_postauction_inputs([col])
    root = pathlib.Path(__file__).resolve().parents[1] / "src" / "postauction"
    for f in root.glob("*.py"):
        assert "k_bridge" not in f.read_text(encoding="utf-8"), f.name
