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


# ------------------------- Amendment 4: Hirth's edges must not leak into B3's default


def test_setting_hirths_edges_does_not_change_b3s_default_binning():
    """Amendment 4 says set the constant but do NOT change B3-CV or B3@8.

    Those two instructions conflict unless the constant is decoupled from fit_b3's
    fallback. Before the constant was filled in, fit_b3 used it whenever it was not
    None, so merely recording Hirth's edges would have silently re-binned every
    existing B3 fit and invalidated the very comparison Amendment 4 sets up. This
    test is what keeps the two apart.
    """
    from src.method.stage_a.baselines import (
        B3_DEFAULT_EDGES,
        HIRTH_FIG12_MARGIN_EDGES_EUR_MWH,
    )

    assert HIRTH_FIG12_MARGIN_EDGES_EUR_MWH == (0.0, 5.0, 10.0, 20.0, 50.0, 100.0,
                                                float("inf"))
    assert B3_DEFAULT_EDGES is None, (
        "B3's default must stay equal-count quantile bins; Hirth's bands belong to "
        "B3-H only, passed explicitly")


def test_b3_quantile_bins_and_hirth_bands_give_different_responses():
    """If they agreed, B3-H would not be a distinct comparator and T-B would be moot."""
    import numpy as np

    from src.method.stage_a.baselines import (
        HIRTH_FIG12_MARGIN_EDGES_EUR_MWH,
        _binned_response,
    )

    rng = np.random.default_rng(0)
    margin = rng.uniform(0.0, 120.0, 5000)
    potential = rng.uniform(100.0, 1000.0, 5000)
    residual = potential * np.clip(margin / 150.0, 0, 1)

    quant = _binned_response(margin, residual, potential, 8, edges=None)
    hirth = _binned_response(margin, residual, potential, 8,
                             edges=HIRTH_FIG12_MARGIN_EDGES_EUR_MWH)
    assert quant["bin_centre"].size and hirth["bin_centre"].size
    assert not np.array_equal(quant["bin_centre"], hirth["bin_centre"])
