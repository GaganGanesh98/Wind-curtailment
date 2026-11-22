"""Post-hoc fine breakdown grid (docs/10, 22 Nov 2026): the summary is what the unrounded cells
say, the refit's b = 0 row is the pre-registered V2 row, and the knife-edge is stated exactly."""

from __future__ import annotations

import polars as pl

from src.experiments import exp3_posthoc_breakdown as ph


def test_b0_row_equals_the_preregistered_v2_cells():
    fine = pl.read_csv(ph.CELLS, infer_schema_length=0).filter(pl.col("b") == "0.0")
    v2 = pl.read_csv(ph.E3 / "bias_robust_full_window_cells.csv", infer_schema_length=0).filter(
        pl.col("b") == "0.0")
    assert fine.height == v2.height == 7
    for r in fine.iter_rows(named=True):
        q = v2.filter(pl.col("lam") == r["lam"]).row(0, named=True)
        assert (r["lo"], r["hi"], r["eps"]) == (q["lo"], q["hi"], q["eps"]), r["lam"]


def test_fine_grid_is_complete():
    c = pl.read_csv(ph.CELLS, infer_schema_length=0)
    assert c["b"].n_unique() == 49 and c.height == 49 * 7
    assert (c["feasible"] == "True").all()


def test_summary_regenerates_from_the_cells(tmp_path):
    fresh = tmp_path / "s.csv"
    ph.summarise().write_csv(fresh)
    assert fresh.read_bytes() == ph.SUMMARY.read_bytes()


def test_lambda1_knife_edge_is_read_unrounded():
    lo, hi = ph._hull("L1", 0.0350)
    assert 0.2495 < hi - lo < 0.25                       # holds, by 0.0005 of width
    lo, hi = ph._hull("L1", 0.0375)
    assert hi - lo > 0.25
    lo, _ = ph._hull("L2", 0.0525)
    assert lo < 0.5                                      # breaks at 0.0525, not "on the edge"


def test_breakdowns_and_survival():
    d = {r["lam"]: r for r in pl.read_csv(ph.SUMMARY).iter_rows(named=True)}
    assert [float(d[k]["breakdown_B"]) for k in ("L1", "L2", "L6")] == [0.0375, 0.0525, 0.0375]
    for lam in ("L1", "L2", "L3", "L6"):
        assert d[lam]["compare_0_survives"] and d[lam]["compare_1_survives"], lam
