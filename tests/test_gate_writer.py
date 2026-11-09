"""Regression tests for the grid writer and the gate's pooled statistics.

The writer test exists because of a real loss. The 81-cell grid of 31 Oct 2026 ran
for 315 minutes and could not be judged on gate criteria (b) or (c): `Writer` fixed
its header from the first row, the first row written is M1, M1 carries no paired-
comparison columns because it is the thing the others are paired against, and
`extrasaction="ignore"` then dropped those columns from all 648 later rows without a
word. Four hours of compute produced a file that was missing two thirds of the gate.
"""

from __future__ import annotations

import csv

import numpy as np
import pytest

from src.censoring.gate_verdict import fleet_response_error
from src.censoring.run_reduced_grid import PAIRED_FIELDS, Writer


def test_writer_keeps_columns_absent_from_the_first_row(tmp_path):
    """The exact failure: first row short, later rows longer."""
    w = Writer(tmp_path / "out.csv", extra_fieldnames=PAIRED_FIELDS)
    w.write({"method": "M1", "mae": 1.0})
    w.write({"method": "B1", "mae": 2.0, "paired_mae_diff": -0.5,
             "paired_mae_sig": True, "m1_better_mae": True,
             "paired_absbias_diff": -0.25, "paired_absbias_sig": False,
             "m1_better_absbias": False})
    w.close()

    rows = list(csv.DictReader((tmp_path / "out.csv").read_text().splitlines()))
    assert rows[0]["paired_mae_diff"] == ""        # M1 has none, written empty
    assert rows[1]["paired_mae_diff"] == "-0.5"    # and B1's survives
    assert rows[1]["m1_better_mae"] == "True"


def test_writer_raises_on_a_column_it_was_not_told_about(tmp_path):
    """Silence was the whole problem, so an unknown column must now stop the run."""
    w = Writer(tmp_path / "out.csv")
    w.write({"method": "M1", "mae": 1.0})
    with pytest.raises(ValueError):
        w.write({"method": "B1", "mae": 2.0, "surprise": 3.0})
    w.close()


def test_fleet_response_error_is_a_capacity_weighted_mean_over_exposed_cohorts():
    """Unexposed cohorts must not dilute the error; unexposed QHs must be NaN."""
    grid = np.linspace(0.0, 10.0, 11)
    cell = {
        "shares": np.array([0.75, 0.25]),
        # QH 0: both exposed. QH 1: only cohort 1. QH 2: nothing exposed.
        "s": np.array([[1.0, 0.0, 0.0], [1.0, 1.0, 0.0]]),
        "depth": np.array([[4.0, 0.0, 0.0], [4.0, 4.0, 0.0]]),
        "depth_grid": grid,
        "r_curve_M1": np.full_like(grid, 0.6),
        "r_curve_true": np.full_like(grid, 0.5),
    }
    e = fleet_response_error(cell, "M1")
    assert e[0] == pytest.approx(0.1)   # both cohorts off by 0.1
    assert e[1] == pytest.approx(0.1)   # cohort 1 alone, same error, not 0.025
    assert np.isnan(e[2])               # nothing exposed -> no response to score


def test_paired_abs_bias_pools_the_sign_before_taking_the_absolute_value():
    """|pooled signed bias|, not the mean of per-cell |bias|.

    Two "cells" of one day each. Method A is +100 on one and -100 on the other, so
    its pooled bias is zero and it is the unbiased method. Method B is +40 on both,
    so it is genuinely biased. Averaging per-cell absolute values would score A at
    100 and B at 40 and declare B better; pooling the sign first gives 0 against 40
    and declares A better, which is correct.
    """
    from src.censoring.metrics import paired_abs_bias

    a = np.array([100.0, 100.0, -100.0, -100.0])
    b = np.full(4, 40.0)
    days = np.array(["d1", "d1", "d2", "d2"])
    mask = np.ones(4, dtype=bool)

    p = paired_abs_bias(a, b, mask, days)
    assert p["diff"] == pytest.approx(0.0 - 40.0)        # |0| - |40|
    assert np.mean(np.abs([100.0, -100.0])) == 100.0     # the wrong statistic


def _d_cell(seed, k, t=8):
    """A minimal criterion (d) cell: two cohorts whose exposure differs."""
    s = np.zeros((k, t))
    s[0, : t // 2] = 1.0          # cohort 0 exposed early
    if k > 1:
        s[1, t // 2 :] = 1.0      # cohort 1 late, so the pair differs everywhere
    return {
        "s": s, "depth": s * 5.0,
        "shares": np.full(k, 1.0 / k),
        "cohort_ids": np.array([f"c{i}" for i in range(k)], dtype=str),
        "berlin_date": np.array([f"2026-01-{1 + i // 2:02d}" for i in range(t)]),
        "censoring_rate": 0.2, "gamma": 0.5, "r_shape": "half", "seed": seed,
    }


def test_criterion_d_skips_a_bad_cell_instead_of_aborting_the_run():
    """The guard was `return {}` inside the per-cell loop, so one cell whose stored
    cohort ids disagreed with `s` discarded every cell already scored. Worse, the
    verdict line read `d_pass = bool(vd) and all(...)`, so an aborted (d) printed
    FAIL -- asserting an identification failure when nothing had been scored. A
    guard must not be reportable as a verdict.
    """
    from src.censoring.gate_verdict import criterion_d

    good = _d_cell(42, 2)
    bad = _d_cell(43, 2)
    bad["cohort_ids"] = np.array(["c0", "c1", "c2"], dtype=str)   # 3 ids, s has 2 rows

    out = criterion_d([bad, good], [])
    assert out, "a mismatching cell must not empty the result"
    assert "r20_g0.5_half_s42" in out       # the good cell survived the bad one
    assert "r20_g0.5_half_s43" not in out   # the bad one is absent, not False


def test_criterion_d_reports_no_cells_as_not_scored_not_as_fail():
    """An empty (d) is an absence of evidence. `bool({})` is False, which is why it
    printed as a failed criterion."""
    from src.censoring.gate_verdict import criterion_d

    vd = criterion_d([], [])
    assert vd == {}
    d_pass = bool(vd) and all(vd.values())
    assert d_pass is False                                  # the old label: "FAIL"
    assert (("PASS" if d_pass else "FAIL") if vd else "NOT SCORED") == "NOT SCORED"


def test_the_i4_day_threshold_is_not_the_per_pair_quarter_hour_floor():
    """Both are 10. They are different pre-registered quantities -- days vs
    quarter-hours, "some pair" vs "every pair" -- and must not share a constant."""
    from src.censoring.gate_verdict import I4_MIN_EXPOSURE_DIFFERS_DAYS
    from src.censoring.identification import MIN_PAIR_DIFFER_QH

    assert I4_MIN_EXPOSURE_DIFFERS_DAYS == MIN_PAIR_DIFFER_QH == 10

    # The QH floor must not be bound in gate_verdict's namespace at all: if it is not
    # there, no code there can compare a day count against it. Checking the source
    # text instead would trip over the comment that explains the distinction.
    import src.censoring.gate_verdict as gv
    assert not hasattr(gv, "MIN_PAIR_DIFFER_QH"), (
        "the I4 day count must not be compared against the per-pair QH floor")
