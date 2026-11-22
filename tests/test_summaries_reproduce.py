"""Every committed experiment summary regenerates byte for byte from its committed cells.

    pytest tests/test_summaries_reproduce.py -q

`artifacts/` is copied to a temporary directory, the summary files are deleted there, each
summariser is pointed at the copy (its module-level directory constants are monkeypatched) and
run, and every regenerated file must equal the committed one byte for byte. Nothing under the
real `artifacts/` or `archive/` is written. The inputs are committed cell files, so this runs on
a clean clone too; it skips only if one of them is missing.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ART = REPO_ROOT / "artifacts"
E1, E2, E3 = "exp1_known_truth_validation", "exp2_bias_robustness_validation", "exp3_german_application"

#: summary file -> the committed inputs it is built from
OUTPUTS = {
    f"{E1}/exact_potential_cells_summary.csv": [f"{E1}/exact_potential_cells.csv"],
    f"{E1}/estimated_potential_cells_summary.csv": [f"{E1}/estimated_potential_cells.csv"],
    f"{E1}/noise_dial_summary.csv": [f"{E1}/noise_dial_cells.csv"],
    f"{E1}/noise_dial_headline.csv": [f"{E1}/noise_dial_cells.csv"],
    f"{E2}/bias_dial_summary.csv": [f"{E2}/bias_dial_cells.csv", f"{E2}/bias_noise_crossed_cells.csv"],
    f"{E2}/bias_dial_coverage.csv": [f"{E2}/bias_dial_cells.csv", f"{E2}/bias_noise_crossed_cells.csv"],
    f"{E2}/bias_robust_coverage.csv": [f"{E2}/bias_robust_cells_shard{i}of4.csv" for i in range(4)],
    f"{E2}/bias_robust_by_functional.csv": [f"{E2}/bias_robust_cells_shard{i}of4.csv" for i in range(4)],
    f"{E2}/bias_robust_width_cost.csv": [f"{E2}/bias_robust_cells_shard{i}of4.csv" for i in range(4)],
    f"{E3}/bias_robust_full_window_intervals.csv": [f"{E3}/bias_robust_full_window_cells.csv"],
    f"{E3}/breakdown_points.csv": [f"{E3}/bias_robust_full_window_cells.csv"],
    f"{E3}/monthly_bounds_summary.csv": [f"{E3}/monthly_bounds_cells.csv"],
    f"{E3}/results_table.csv": [f"{E3}/monthly_bounds_cells.csv"],
}
C1 = REPO_ROOT / "archive" / "docs" / "C1_conclusions_table.md"


@pytest.fixture(scope="module")
def regenerated(tmp_path_factory):
    missing = sorted({i for v in OUTPUTS.values() for i in v if not (ART / i).exists()})
    if missing:
        pytest.skip(f"committed inputs missing: {missing}")
    tmp = tmp_path_factory.mktemp("repro") / "artifacts"
    shutil.copytree(ART, tmp)
    for out in [*OUTPUTS, f"{E3}/readings_table.csv"]:
        (tmp / out).unlink()
    c1_tmp = tmp.parent / "C1_conclusions_table.md"

    from src.experiments import exp1_noise_dial_summary as n1
    from src.experiments import exp2_bias_dial_summary as b2
    from src.experiments import exp3_real_bounds_summary as r3
    from src.experiments import exp3_results_table as t3
    from src.method import bias_robust_summary as brs
    from src.method import read_results as rr

    mp = pytest.MonkeyPatch()
    try:
        mp.setattr(n1, "Q1", tmp / E1)
        mp.setattr(b2, "Q2", tmp / E2)
        mp.setattr(brs, "V", tmp / E2)
        mp.setattr(brs, "V_REAL", tmp / E3)
        mp.setattr(r3, "Q5", tmp / E3)
        mp.setattr(t3, "ART", tmp)
        mp.setattr(t3, "CSV_OUT", tmp / E3 / "results_table.csv")
        mp.setattr(t3, "MD_OUT", c1_tmp)
        mp.setattr(t3, "READINGS_OUT", tmp / E3 / "readings_table.csv")
        mp.setattr(t3, "REPO_ROOT", tmp.parent)         # only its closing print uses it
        # the order exp1_known_truth_validation, exp2_..., exp3_german_application run them in
        for f in ("exact_potential_cells.csv", "estimated_potential_cells.csv"):
            mp.setattr(sys, "argv", ["read_results", str(tmp / E1 / f)])
            rr.main()
        mp.setattr(sys, "argv", ["summarise"])          # the other mains take no arguments
        n1.main()
        b2.main()
        brs.main()
        r3.main()
        t3.main()
    finally:
        mp.undo()
    return tmp, c1_tmp


@pytest.mark.parametrize("name", sorted(OUTPUTS))
def test_summary_regenerates_byte_for_byte(regenerated, name):
    tmp, _ = regenerated
    assert (tmp / name).exists(), f"{name} was not regenerated"
    assert (tmp / name).read_bytes() == (ART / name).read_bytes(), f"{name} differs from the committed file"


def test_c1_note_regenerates_byte_for_byte(regenerated):
    _, c1_tmp = regenerated
    assert c1_tmp.read_bytes() == C1.read_bytes()


def test_readings_table_regenerates_byte_for_byte(regenerated):
    tmp, _ = regenerated
    name = f"{E3}/readings_table.csv"
    assert (tmp / name).read_bytes() == (ART / name).read_bytes()


def test_sample_sizes_agree_with_the_cells():
    """The committed quarter-hour counts equal n_qh_lam in the cells (event days are new)."""
    import polars as pl
    ss = {r["lam"]: r for r in pl.read_csv(ART / E3 / "sample_sizes.csv").iter_rows(named=True)}
    cells = pl.read_csv(ART / E3 / "bias_robust_full_window_cells.csv", infer_schema_length=0)
    for r in cells.filter(pl.col("b") == "0.0").iter_rows(named=True):
        assert ss[r["lam"]]["n_qh"] == int(r["n_qh_lam"]), r["lam"]
        assert ss[r["lam"]]["n_event_days"] <= int(r["n_event_days"])


@pytest.mark.needs_data("data/processed/panel_qh.parquet")
def test_sample_sizes_recompute_from_the_panel():
    import polars as pl
    from src.experiments.exp3_results_table import sample_sizes
    assert sample_sizes().equals(pl.read_csv(ART / E3 / "sample_sizes.csv"))
