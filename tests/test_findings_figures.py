"""The findings figures plot what the artifacts say (Phase S5).

Each data builder in `src/make_findings_figures.py` is re-run and checked two ways:
against figures quoted in the results notes (the same values `test_reported_numbers.py`
holds), and against the committed `figures/findings/*_data.csv`, so a stale CSV fails.
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
def test_f1_is_the_worst_day_with_f_g_and_h():
    assert mf.f1_day() == "2026-04-05"                            # Easter Sunday 2026
    # The day is rank 1 on DE total wind: re-derive its error from the panel.
    de = pl.read_parquet(mf.PANEL).filter((pl.col("area") == "DE")
                                          & (pl.col("berlin_date") == "2026-04-05")
                                          & (pl.col("price_eur_mwh") < 0))
    assert de.height == 69                                        # results/02_worst_days_de.csv
    assert abs(float(de["e_mw"].sum()) - (-860200.9)) <= 0.1     # sum_e_mw_qh
    d = mf.f1_data()
    assert d.height == 96 and d["projection_h_mw"].null_count() == 0
    assert d.filter(pl.col("price_eur_mwh") < 0).height == 69
    _same(d, _committed("F1_problem_schematic"))


def test_f2_kill_test_bands():
    d = mf.f2_data()
    assert d["qhs"].sum() == 2059                                 # 2,059 negative QHs
    de = d.filter(pl.col("price_band_eur_mwh") == "<= -50")
    assert float(de["mean_e_mw"][0]) == -7641.2
    s = mf.f2_sample()
    assert sorted(s["value"].to_list()) == [99, 2059]
    _same(d, _committed("F2_forecast_bias_by_price_band"))


def test_f3_gap_shares():
    d = mf.f3_data()
    assert d.height == 10 and set(d["estimator"]) == {"H", "F"}
    bands = d.filter(pl.col("set").str.starts_with("band"))
    assert int(bands.filter(pl.col("estimator") == "H")["n_qh"].sum()) == 2059
    ref = d.filter((pl.col("set") == "price >= 0") & (pl.col("estimator") == "H"))
    assert ref["n_qh"][0] > 30000                                 # every price >= 0 QH
    _same(d, _committed("F3_projection_vs_forecast_gap_by_band"))


def test_f4_coverage():
    d = mf.f4_data()
    o = d.filter(pl.col("setting").str.starts_with("P3 Arm O"))
    a = d.filter(pl.col("setting").str.starts_with("P3 Arm D"))
    assert (o["n_scored"][0], o["n_covered"][0]) == (1127, 1127)  # P3 section 1
    assert (a["n_scored"][0], a["n_covered"][0]) == (378, 378)    # P3 section 2.4
    assert float(d["coverage"].min()) >= 0.95
    _same(d, _committed("F4_coverage_never_fails"))


def test_f5_widths():
    d = mf.f5_data().to_dicts()
    w = {r["lam"]: r for r in d}
    assert abs(w["L1"]["median_width_exact"] - 7.0e-7) <= 5e-8    # S2.4 Arm O seed-45
    assert abs(w["L7"]["median_width_exact"] - 0.467) <= 5e-4
    assert abs(w["L1"]["median_width_estimated"] - 0.096) <= 5e-4  # S2.4 Arm D
    assert abs(w["L6"]["median_width_estimated"] - 1.206) <= 5e-4
    _same(mf.f5_data(), _committed("F5_exact_vs_estimated_potential"))


def test_f6_noise_dial_and_anchors():
    anc = mf.anchors()
    assert abs(anc["H"] - 0.0660) <= 5e-5 and abs(anc["T"] - 0.1806) <= 5e-5
    d = mf.f6_data()
    l1 = d.filter(pl.col("lam") == "L1").sort("sigma")
    assert l1["n_informative"].to_list()[-1] == 50                # 50 of 54 at 0.35
    committed = _committed("F6_noise_dial")
    _same(d.with_columns(pl.lit(anc["H"]).alias("anchor_h_sigma"),
                         pl.lit(anc["T"]).alias("anchor_t_sigma")), committed)


def test_f7_real_matches_q5_headline():
    d = mf.f7_data()
    assert int(d["q5_n"].sum()) == 59                             # Q5: 59 functional-months
    assert int(d["q5_n_informative"].sum()) == 3                  # informative under H: 3
    assert int(d["q5_n_undefined"].sum()) == 11                   # Q5: eleven undefined pairs
    assert (d["q1_n_informative"] / d["q1_n"] - d["q1_share"]).abs().max() < 1e-12
    _same(d, _committed("F7_synthetic_vs_real"))


def test_f8_eight_testable_cells():
    d = mf.f8_data()
    assert d.height == 8                                          # Q6a: all 8 testable cells
    assert (d["v_between_ci_lo"] > d["v_meas"]).all()             # excess CI excludes zero
    _same(d, _committed("F8_day_heterogeneity"))


def test_every_figure_has_png_csv_and_caption():
    for name in mf.CAPTIONS:
        if name == "F1_problem_schematic" and not mf.PANEL.exists():
            continue
        for s in (".png", "_data.csv", "_caption.txt"):
            assert (FIG / f"{name}{s}").exists(), f"{name}{s} missing"


def test_f9_widths_are_the_q1_summary():
    d = mf.f9_data()
    assert set(d["lam"]) == {"L1", "L2", "L3", "L4", "L6", "L7"}   # λ₅ (GWh) omitted
    assert d.height == 6 * 7                                       # six functionals × grid
    q1 = pl.read_csv(mf.ART / "Q1" / "q1_summary_by_level.csv").filter(pl.col("noise") == "iid")
    j = d.join(q1.select(["lam", "sigma", pl.col("median_width").alias("m")]), on=["lam", "sigma"])
    assert (j["median_width"] == j["m"]).all()
    assert (d["q25_width"] <= d["median_width"]).all() and (d["median_width"] <= d["q75_width"]).all()
    anc = mf.anchors()
    _same(d.with_columns(pl.lit(anc["H"]).alias("anchor_h_sigma"),
                         pl.lit(anc["T"]).alias("anchor_t_sigma")), _committed("F9_width_vs_noise"))


def test_f10_is_the_v2_hulls():
    if not (mf.ART / "V" / "v2_robust_intervals.csv").exists():
        pytest.skip("Phase V artifacts not on disk")
    d = mf.f10_data()
    assert set(d["lam"]) == {"L1", "L2", "L3", "L6"} and d.height == 4 * 16
    l1 = d.filter((pl.col("lam") == "L1") & (pl.col("B") == 0.0))
    assert abs(l1["lo"][0] - 0.300) < 5e-4 and abs(l1["hi"][0] - 0.508) < 5e-4
    assert d.filter(pl.col("lam") == "L1")["breakdown_B"][0] == "0.04"
    _same(d.with_columns(pl.lit(abs(mf.anchors_bias_h())).alias("abs_bias_h_positive_prices")),
          _committed("F10_bias_breakdown"))
