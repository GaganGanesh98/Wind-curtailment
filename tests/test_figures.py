"""The figures plot what the artifacts say.

Each data builder in `src/figures.py` is re-run and checked two ways:
against figures quoted in the results notes (the same values `test_reported_numbers.py`
holds), and against the committed `figures/*_data.csv`, so a stale CSV fails.
Builders whose input file is absent are skipped, as in `test_reported_numbers.py`.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from src import figures as mf

FIG = mf.OUT_DIR


def _committed(name: str) -> pl.DataFrame:
    p = FIG / f"{name}_data.csv"
    if not p.exists():
        pytest.skip(f"{p.name} not generated yet")
    return pl.read_csv(p)


def _same(fresh: pl.DataFrame, committed: pl.DataFrame) -> None:
    """Equal after a CSV round trip (dtypes are what the CSV reader infers)."""
    tmp = pl.read_csv(fresh.write_csv().encode())
    assert tmp.columns == committed.columns
    assert tmp.height == committed.height
    for c in tmp.columns:
        a, b = tmp[c], committed[c]
        if a.dtype.is_float() or b.dtype.is_float():
            assert ((a.cast(pl.Float64) - b.cast(pl.Float64)).abs().fill_null(0) <= 1e-9).all(), c
        else:
            assert a.cast(pl.String).to_list() == b.cast(pl.String).to_list(), c


@pytest.mark.skipif(not mf.PANEL.exists(), reason="processed panel not on disk")
def test_motivation_event_day_is_the_worst_day():
    assert mf.motivation_day() == "2026-04-05"                            # Easter Sunday 2026
    # The day is rank 1 on DE total wind: re-derive its error from the panel.
    de = pl.read_parquet(mf.PANEL).filter((pl.col("area") == "DE")
                                          & (pl.col("berlin_date") == "2026-04-05")
                                          & (pl.col("price_eur_mwh") < 0))
    assert de.height == 69                                        # results/02_worst_days_de.csv
    assert abs(float(de["e_mw"].sum()) - (-860200.9)) <= 0.1     # sum_e_mw_qh
    d = mf.event_day_data()
    assert d.height == 96 and d["projection_h_mw"].null_count() == 0
    assert d.filter(pl.col("price_eur_mwh") < 0).height == 69
    _same(d, _committed("01_motivation_event_day"))


def test_motivation_forecast_bias_bands():
    d = mf.forecast_bias_data()
    assert d["qhs"].sum() == 2059                                 # 2,059 negative QHs
    de = d.filter(pl.col("price_band_eur_mwh") == "<= -50")
    assert float(de["mean_e_mw"][0]) == -7641.2
    s = mf.forecast_bias_sample()
    assert sorted(s["value"].to_list()) == [99, 2059]
    _same(d, _committed("02_motivation_forecast_bias_by_band"))


def test_available_power_gap_shares():
    d = mf.gap_by_band_data()
    assert d.height == 10 and set(d["estimator"]) == {"H", "F"}
    bands = d.filter(pl.col("set").str.starts_with("band"))
    assert int(bands.filter(pl.col("estimator") == "H")["n_qh"].sum()) == 2059
    ref = d.filter((pl.col("set") == "price >= 0") & (pl.col("estimator") == "H"))
    assert ref["n_qh"][0] > 30000                                 # every price >= 0 QH
    _same(d, _committed("03_available_power_gap_by_band"))


def test_exp1_coverage():
    d = mf.exp1_coverage_data()
    exact = d.filter(pl.col("setting") == "exact potential")
    est = d.filter(pl.col("setting") == "estimated potential")
    assert (exact["n_scored"][0], exact["n_covered"][0]) == (1127, 1127)
    assert (est["n_scored"][0], est["n_covered"][0]) == (378, 378)
    assert d.height == 2 + 8                                       # 2 arms + 8 noise-dial levels
    assert float(d["coverage"].min()) >= 0.95                      # lowest: AR(1), 0.984 (erratum)
    _same(d, _committed("04_exp1_coverage"))


def test_exp2_coverage_under_bias():
    d = mf.exp2_coverage_data()
    robust = d.filter(pl.col("panel") == "bias-robust set")
    plain = d.filter(pl.col("panel") == "plain set")
    assert robust.height == 15 and plain.height == 11
    within = robust.filter(pl.col("B") + 1e-9 >= pl.col("b_true").abs())
    assert within.height == 9 and (within["n_covered"] == 324).all()          # exp 2 PASS
    biased = plain.filter(pl.col("b_true") != 0)
    assert biased.height == 8 and (biased["coverage"] < 0.95).all()
    _same(d, _committed("08_exp2_coverage_under_bias"))


def test_exp1_exact_vs_estimated_widths():
    d = mf.exact_vs_estimated_data().to_dicts()
    w = {r["lam"]: r for r in d}
    assert abs(w["L1"]["median_width_exact"] - 7.0e-7) <= 5e-8    # S2.4 Arm O seed-45
    assert abs(w["L7"]["median_width_exact"] - 0.467) <= 5e-4
    assert abs(w["L1"]["median_width_estimated"] - 0.096) <= 5e-4  # S2.4 Arm D
    assert abs(w["L6"]["median_width_estimated"] - 1.206) <= 5e-4
    _same(mf.exact_vs_estimated_data(), _committed("05_exp1_exact_vs_estimated_potential"))


def test_exp1_noise_dial_and_anchors():
    anc = mf.anchors()
    assert abs(anc["H"] - 0.0660) <= 5e-5 and abs(anc["T"] - 0.1806) <= 5e-5
    d = mf.noise_dial_data()
    l1 = d.filter(pl.col("lam") == "L1").sort("sigma")
    assert l1["n_informative"].to_list()[-1] == 50                # 50 of 54 at 0.35
    committed = _committed("06_exp1_noise_dial")
    _same(d.with_columns(pl.lit(anc["H"]).alias("anchor_h_sigma"),
                         pl.lit(anc["T"]).alias("anchor_t_sigma")), committed)


def test_every_figure_has_png_csv_and_caption():
    for name in mf.CAPTIONS:
        if name == "01_motivation_event_day" and not mf.PANEL.exists():
            continue
        for s in (".png", "_data.csv", "_caption.txt"):
            assert (FIG / f"{name}{s}").exists(), f"{name}{s} missing"


def test_exp1_widths_are_the_noise_dial_summary():
    d = mf.width_vs_noise_data()
    assert set(d["lam"]) == {"L1", "L2", "L3", "L4", "L6", "L7"}   # λ₅ (GWh) omitted
    assert d.height == 6 * 7                                       # six functionals × grid
    q1 = pl.read_csv(mf.E1 / "noise_dial_summary.csv").filter(pl.col("noise") == "iid")
    j = d.join(q1.select(["lam", "sigma", pl.col("median_width").alias("m")]), on=["lam", "sigma"])
    assert (j["median_width"] == j["m"]).all()
    assert (d["q25_width"] <= d["median_width"]).all() and (d["median_width"] <= d["q75_width"]).all()
    anc = mf.anchors()
    _same(d.with_columns(pl.lit(anc["H"]).alias("anchor_h_sigma"),
                         pl.lit(anc["T"]).alias("anchor_t_sigma")), _committed("07_exp1_width_vs_noise"))


def test_exp3_breakdown_is_the_full_window_hulls():
    if not (mf.E3 / "bias_robust_full_window_intervals.csv").exists():
        pytest.skip("Phase V artifacts not on disk")
    d = mf.bias_breakdown_data()
    assert set(d["lam"]) == {"L1", "L2", "L3", "L6"} and d.height == 4 * 16
    l1 = d.filter((pl.col("lam") == "L1") & (pl.col("B") == 0.0))
    assert abs(l1["lo"][0] - 0.300) < 5e-4 and abs(l1["hi"][0] - 0.508) < 5e-4
    assert d.filter(pl.col("lam") == "L1")["breakdown_B"][0] == "0.04"
    _same(d.with_columns(pl.lit(abs(mf.anchors_bias_h())).alias("abs_bias_h_positive_prices")),
          _committed("09_exp3_bias_breakdown"))
