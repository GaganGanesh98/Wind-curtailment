"""The two tests split out of tests/test_identification.py in the consolidation: they
exercise the M1 metrics module (archived), not the identification code that stays active."""

from __future__ import annotations

import numpy as np
import pytest


def test_paired_abs_bias_reports_n_qh_and_n_days():
    """gate_verdict.criterion_b writes p["n_qh"] / p["n_days"] for BOTH statistics it
    reports, so omitting them made the gate raise KeyError and never score."""
    from src.censoring.metrics import paired_abs_bias, paired_difference

    a = np.array([10.0, -10.0, 5.0, -5.0])
    b = np.full(4, 3.0)
    days = np.array(["d1", "d1", "d2", "d2"])
    mask = np.ones(4, dtype=bool)

    p = paired_abs_bias(a, b, mask, days)
    assert p["n_qh"] == 4
    assert p["n_days"] == 2
    # same contract as its sibling in the same module
    q = paired_difference(a, b, mask, days)
    assert set(("n_qh", "n_days")) <= set(p) & set(q)


def test_paired_abs_bias_reports_counts_on_the_single_day_path():
    """The early return (n_days < 2) skips the bootstrap but must still carry the
    counts, or the gate breaks only on degenerate strata."""
    from src.censoring.metrics import paired_abs_bias

    p = paired_abs_bias(np.array([1.0, 2.0]), np.array([0.0, 0.0]),
                        np.ones(2, dtype=bool), np.array(["d1", "d1"]))
    assert p["n_qh"] == 2
    assert p["n_days"] == 1
    assert np.isnan(p["lo"]) and np.isnan(p["hi"])
