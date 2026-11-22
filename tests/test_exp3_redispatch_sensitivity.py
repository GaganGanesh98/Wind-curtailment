"""Redispatch sensitivity (docs/11, docs/11b): the summary is what the unrounded cells say, the
headline arm reproduces the committed V2 breakdowns, and the decision rule is applied as written."""

from __future__ import annotations

import polars as pl
import pytest

from src.experiments import exp3_redispatch_sensitivity as rs


def test_cells_are_complete():
    c = pl.read_csv(rs.CELLS, infer_schema_length=0)
    assert sorted(c["mask"].unique().to_list()) == ["M0", "M1"]
    assert c.height == 2 * 31 * 7 and (c["feasible"] == "True").all()


def test_summary_regenerates_from_the_cells(tmp_path):
    out = tmp_path / "s.csv"
    rs.summarise().write_csv(out)
    assert out.read_bytes() == rs.SUMMARY.read_bytes()


def test_headline_arm_matches_the_committed_v2_breakdowns():
    s = pl.read_csv(rs.SUMMARY, infer_schema_length=None).filter(pl.col("arm") == "headline")
    bd = {r["lam"]: r["breakdown_B"] for r in pl.read_csv(
        rs.E3 / "breakdown_points.csv", infer_schema_length=0).iter_rows(named=True)}
    for r in s.iter_rows(named=True):
        assert r["breakdown_B"] == (bd[r["lam"]] if bd[r["lam"]].startswith(">")
                                    else f"{float(bd[r['lam']]):.2f}"), r["lam"]


def test_decision_rule_outcomes():
    s = pl.read_csv(rs.SUMMARY, infer_schema_length=None).filter(pl.col("arm") != "headline")
    sens = {(r["lam"], r["arm"]): r["sensitive"] for r in s.iter_rows(named=True)}
    assert sens == {("L1", "M0"): True, ("L1", "M1"): True, ("L2", "M0"): True, ("L2", "M1"): True,
                    ("L3", "M0"): False, ("L3", "M1"): False, ("L6", "M0"): True, ("L6", "M1"): True}


def test_removed_shares():
    assert round(rs.removed_share("M0"), 2) == 0.64 and round(rs.removed_share("M1"), 2) == 0.54


@pytest.mark.needs_data("data/processed/panel_qh.parquet")
def test_l2_diagnosis_reproduces_the_stored_lower_bounds():
    d = pl.read_csv(rs.DIAG)
    for r in d.iter_rows(named=True):
        assert r["l2_lo_resolved"] == r["l2_lo_stored"], r["arm"]
        assert r["fit_active"]
