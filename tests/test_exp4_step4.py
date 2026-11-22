"""Experiment 4, step 4 in reduced form (docs/12b): the descriptive bias estimate and the
Experiment 3 arm recompute from the artifacts, and no budget is ever defined."""

from __future__ import annotations

import polars as pl
import pytest

from src.method.learned_potential import bias_budget as bb
from src.method.learned_potential.data import ART


def test_no_budget_or_classification_is_written():
    assert not (ART / "readings_vs_budget.csv").exists()
    b = pl.read_csv(bb.OUT)
    assert (b["status"] == "descriptive, S2 failed").all() and (b["model"] == "L2").all()
    assert "B_hat" not in " ".join(b.columns)


def test_arm_readings_recompute_from_the_cells(tmp_path):
    out = tmp_path / "arm.csv"
    bb.arm_readings().write_csv(out)
    assert out.read_bytes() == bb.ARM_READINGS.read_bytes()


def test_arm_ran_on_experiment3_quarter_hours():
    c = pl.read_csv(bb.ARM_CELLS, infer_schema_length=0)
    h = pl.read_csv(ART.parent / "exp3_german_application" / "bias_robust_full_window_cells.csv",
                    infer_schema_length=0)
    assert c["b"].n_unique() == h["b"].n_unique() == 31
    assert (c["n_qh_period"] == h["n_qh_period"][0]).all() and (c["potential"] == "learned (L2)").all()


@pytest.mark.needs_data("data/processed/panel_qh.parquet")
def test_bias_estimate_recomputes():
    fresh, stored = bb.estimate(), pl.read_csv(bb.OUT)
    assert fresh.columns == stored.columns
    for c in ("b_hat_H", "corrected", "corrected_lo", "corrected_hi", "n_target_qh"):
        assert fresh[c].to_list() == pytest.approx(stored[c].to_list(), abs=1e-12), c
