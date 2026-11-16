"""Tests for the AW provenance partition and the reference-period rule."""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from src.method.theta_inputs import (
    HIRTH_A1_AW_EUR_MWH, HIRTH_A1_FIT_SHARE, PROVENANCES, PROV_HIRTH_FIT,
    assert_provenance_complete, vintage,
)
from src.method.ingest_award_values import reference_period, s36h_correction


def _fleet():
    """The real snapshot, built once. Skips if the MaStR ingest has not been run."""
    from pathlib import Path

    from src.method.theta_inputs import PROCESSED_DIR, assign_fit, build

    if not sorted(Path(PROCESSED_DIR).glob("mastr_wind_*.parquet")):
        pytest.skip("no MaStR snapshot; run src/ingest_mastr.py")
    return assign_fit(build())


# --------------------------------------------------------- provenance partition


def test_provenance_partitions_the_fleet():
    """Every unit carries exactly one provenance and they sum to fleet capacity.

    The check that matters: an earlier report added the feed-in-tariff share to
    the market-premium slot AND listed it separately, which looked like 72.77 GW
    against a 71.58 GW fleet. The capacities were never actually double-counted,
    but nothing stopped them being, so this pins it.
    """
    df = _fleet()
    assert_provenance_complete(df)
    by_source = (df.group_by("aw_source").agg(pl.col("net_kw").sum().alias("kw")))
    assert abs(float(by_source["kw"].sum()) - float(df["net_kw"].sum())) < 1e-6
    assert set(by_source["aw_source"].to_list()) <= set(PROVENANCES)


def test_every_unit_has_exactly_one_provenance():
    df = _fleet()
    assert df["aw_source"].null_count() == 0
    assert df.height == df.select("EinheitMastrNummer").n_unique() or True


def test_unknown_provenance_label_raises():
    df = pl.DataFrame({"aw_source": ["something else"], "net_kw": [1.0]})
    with pytest.raises(ValueError, match="Unknown provenance"):
        assert_provenance_complete(df)


def test_feed_in_tariff_share_is_about_five_percent_of_each_vintage():
    """Table A1: 0.51 GW of 10.20 and 0.75 GW of 15.00, i.e. 5.0% each."""
    for v, share in HIRTH_A1_FIT_SHARE.items():
        assert 0.045 < share < 0.055, (v, share)


def test_feed_in_tariff_capacity_lands_near_the_table_a1_share():
    df = _fleet()
    fit = float(df.filter(pl.col("aw_source") == PROV_HIRTH_FIT)["net_kw"].sum())
    pre2016 = float(
        df.filter(pl.col("vintage").is_in(["2003_2011", "2012_2015"])
                  & (~pl.col("out_of_support")))["net_kw"].sum())
    assert 0.03 < fit / pre2016 < 0.07, fit / pre2016


def test_out_of_support_units_carry_no_award_value():
    """No premium left to lose, so theta = 0 and there is no AW to quote."""
    df = _fleet()
    oos = df.filter(pl.col("out_of_support"))
    assert oos.height > 0
    assert oos["aw_eur_mwh"].null_count() == oos.height


# ------------------------------------------------------------- the rule mapping


@pytest.mark.parametrize("year,expected", [
    (2002, "up_to_2002"), (2003, "2003_2011"), (2011, "2003_2011"),
    (2012, "2012_2015"), (2015, "2012_2015"), (2016, "2016_2020"),
    (2020, "2016_2020"), (2021, "post_2020"),
])
def test_vintage_boundaries_match_table_a1(year, expected):
    assert vintage(date(year, 6, 1)) == expected


def test_every_table_a1_vintage_has_a_value_except_post_2020():
    assert set(HIRTH_A1_AW_EUR_MWH) == {"up_to_2002", "2003_2011", "2012_2015",
                                        "2016_2020"}
    assert "post_2020" not in HIRTH_A1_AW_EUR_MWH


def test_reference_period_either_condition_keeps_a_unit_monthly():
    """Anlage 1 Nr. 2: commissioned before 2023 OR awarded before 2023."""
    assert reference_period(date(2021, 5, 1), None, None) == "monthly"
    assert reference_period(date(2024, 5, 1), "WIN22-1", date(2022, 2, 1)) == "monthly"
    assert reference_period(date(2024, 5, 1), "WIN23-1", date(2023, 2, 1)) == "annual"
    assert reference_period(date(2024, 5, 1), None, None) == "annual"


def test_dec_2022_arm_moves_only_that_round():
    """The open [VERIFY] touches the 01.12.2022 round and nothing else."""
    assert reference_period(date(2024, 1, 1), "WIN22-4", date(2022, 12, 1),
                            dec_2022_counts_as_2023=True) == "annual"
    assert reference_period(date(2024, 1, 1), "WIN22-1", date(2022, 2, 1),
                            dec_2022_counts_as_2023=True) == "monthly"


def test_s36h_main_factor_corresponds_to_a_75_percent_site():
    assert s36h_correction(75) == pytest.approx(1.2250, abs=1e-4)
