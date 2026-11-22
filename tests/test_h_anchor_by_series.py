"""Anchor H by series (Phase 2, 22 Nov 2026): the operational and quality-assured rows are
labelled, the operational rows are exactly the ones error_anchors.csv always had, and every
hard-coded copy of the quality-assured values in src/ and the demo matches the artifact.
"""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl
import pytest

from src.experiments.available_power_anchors import BY_SERIES, EXP3_WINDOW, primary_h

REPO_ROOT = Path(__file__).resolve().parents[1]
AP = REPO_ROOT / "artifacts" / "available_power_estimate"


def test_operational_rows_equal_the_error_anchors_rows():
    old = pl.read_csv(AP / "error_anchors.csv", infer_schema_length=None).filter(
        pl.col("area").str.starts_with("DE excl. TenneT"))
    new = pl.read_csv(BY_SERIES, infer_schema_length=None).filter(pl.col("series") == "operational")
    assert old.height == new.height == 4
    for r in new.iter_rows(named=True):
        o = old.filter((pl.col("anchor") == r["anchor"]) & (pl.col("sample") == r["sample"])).row(0, named=True)
        for k in ("n_qh", "n_days", "sigma", "sigma_lo", "sigma_hi", "bias", "bias_lo", "bias_hi"):
            assert float(r[k]) == float(o[k]), (r["anchor"], r["sample"], k)
        assert r["role"].startswith("operational, Sep to Oct 2026")


def test_primary_row_is_quality_assured_on_the_experiment3_window():
    q = primary_h()
    assert (q["series"], q["first_date"], q["last_date"]) == ("quality-assured", *EXP3_WINDOW)
    # the price >= 0 quarter-hours of Experiment 3's full window: 34,937 kept minus 2,052 negative
    cells = pl.read_csv(REPO_ROOT / "artifacts" / "exp3_german_application"
                        / "bias_robust_full_window_cells.csv", infer_schema_length=0)
    r0 = cells.row(0, named=True)
    assert q["n_qh"] == int(r0["n_qh_period"]) - int(r0["n_neg_qh"])


def test_redispatch_row_sits_beside_the_primary_row():
    r = primary_h(anchor="H, G+R")
    assert r["quantity"] == "log((G+R)/H)" and r["n_qh"] == primary_h()["n_qh"]


@pytest.mark.parametrize("path", ["src/method/potential_error.py", "src/method/bias_robust.py",
                                  "src/experiments/exp3_results_table.py", "src/figures.py",
                                  "demo/run_demo.sh", "archive/docs/C1_conclusions_table.md"])
def test_hard_coded_quality_assured_values_match_the_artifact(path):
    q = primary_h()
    text = (REPO_ROOT / path).read_text(encoding="utf-8")
    hits = re.findall(r"quality-assured(?: series gives|:)\s*(?:sigma|σ)?\s*([0-9.]+)?(?: and|,)?\s*"
                      r"(?:bias)?\s*([−-][0-9.]+)", text)
    assert hits, f"no quality-assured note in {path}"
    for sig, bias in hits:
        if sig:
            assert sig == f"{q['sigma']:.4f}", (path, sig)
        assert bias.replace("−", "-") == f"{q['bias']:.4f}", (path, bias)


@pytest.mark.needs_data("data/raw/netztransparenz/redispatch_2025-10-01_2026-10-28_UTC_dl2026-10-29.csv")
def test_redispatch_checks_recompute_from_the_export():
    from src.method.redispatch_checks import OUT, checks
    stored = pl.read_csv(OUT)
    fresh = pl.DataFrame(checks())
    assert stored["count"].to_list() == fresh["count"].to_list()
    assert stored["item"].to_list() == fresh["item"].to_list()
    u = stored.filter(pl.col("check") == "unit_check").row(0, named=True)
    assert (u["count"], u["of"]) == (1322, 7067)


def test_g_plus_r_row_is_kept_in_the_csv_but_not_shown_in_docs03():
    r = primary_h(anchor="H, G+R")
    assert "includes solar" in r["note"] and "offshore" in r["note"]
    doc = (REPO_ROOT / "docs" / "03_available_power_estimate.md").read_text(encoding="utf-8")
    assert "against G + R (redispatch" not in doc
