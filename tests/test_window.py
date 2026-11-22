"""Experiment 3's window (Phase 5, 22 Nov 2026): the per-month artifact agrees with the committed
cells, and no active doc or caption gives Experiment 3 an October 2026 end."""

from __future__ import annotations

import re
from pathlib import Path

import polars as pl
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
E3 = REPO_ROOT / "artifacts" / "exp3_german_application"


def test_monthly_arms_match_the_monthly_cells():
    w = pl.read_csv(E3 / "window_months.csv")
    cells = pl.read_csv(E3 / "monthly_bounds_cells.csv", infer_schema_length=0)
    periods = sorted(set(cells["period"].to_list()) - {"window"})
    assert w.filter(pl.col("monthly_arm"))["month"].to_list() == periods
    r0 = pl.read_csv(E3 / "bias_robust_full_window_cells.csv", infer_schema_length=0).row(0, named=True)
    assert w["kept_qh"].sum() == int(r0["n_qh_period"])
    assert w["negative_qh_kept"].sum() == int(r0["n_neg_qh"])


def test_november_and_december_2025_have_no_negative_price():
    w = {r["month"]: r for r in pl.read_csv(E3 / "window_months.csv").iter_rows(named=True)}
    for m in ("2025-11", "2025-12"):
        assert w[m]["market_value_published"] and w[m]["negative_qh_panel"] == 0
    assert not w["2026-10"]["market_value_published"] and w["2026-10"]["kept_qh"] == 0


@pytest.mark.needs_data("data/processed/panel_qh.parquet")
def test_window_months_recompute_from_the_panel():
    from src.experiments.exp3_results_table import window_months
    assert window_months().equals(pl.read_csv(E3 / "window_months.csv"))


def test_no_october_2026_end_for_experiment3():
    texts = [REPO_ROOT / "archive" / "docs" / "C1_conclusions_table.md",
             REPO_ROOT / "docs" / "06_exp3_german_application.md",
             *(REPO_ROOT / "figures").glob("0[4-9]_*caption.txt"),
             *(REPO_ROOT / "figures").glob("1[0-9]_*caption.txt")]
    for p in texts:
        t = p.read_text(encoding="utf-8")
        assert not re.search(r"2025-10 to 2026-10\b|Oct 2025 – Oct 2026", t), p.name
