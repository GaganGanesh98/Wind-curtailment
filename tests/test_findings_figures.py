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

from src import make_findings_figures as mf

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
def test_f1_is_the_worst_day_and_its_error_matches():
    d = mf.f1_data()
    assert d["berlin_date"][0] == "2026-04-05"
    neg = d.filter(pl.col("price_eur_mwh") < 0)
    assert neg.height == 69                                       # results/02_worst_days_de.csv
    assert abs(float(neg["e_mw"].sum()) - (-860200.9)) <= 0.1     # sum_e_mw_qh
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
    assert d.height == 8 and set(d["estimator"]) == {"H", "F"}
    assert int(d.filter(pl.col("estimator") == "H")["n_qh"].sum()) == 2059
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
