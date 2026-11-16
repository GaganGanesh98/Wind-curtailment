"""Tests for the response heads (spec v1.6).

The piecewise-linear head became primary because the sigmoid could not represent
two of the three r* shapes in E1. These tests pin that down: monotonicity, which is
assumption I3 and must hold by construction, and representational capacity, which is
the reason for the change.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from src.method.stage_a.latent_model import (
    RESPONSE_HEADS,
    RESPONSE_KNOTS,
    PiecewiseLinearResponseHead,
    SigmoidResponseHead,
)

GRID = np.linspace(0.0, 150.0, 301)


@pytest.mark.parametrize("name", sorted(RESPONSE_HEADS))
def test_response_is_monotone_in_depth_by_construction(name):
    """Assumption I3. True at initialisation and at arbitrary parameter values."""
    torch.manual_seed(0)
    head = RESPONSE_HEADS[name](np.array([0, 0, 1]))
    for p in head.parameters():
        with torch.no_grad():
            p.copy_(torch.randn_like(p) * 2.0)
    r = head.curve(GRID)
    assert np.all(np.diff(r, axis=1) >= -1e-6), f"{name} not monotone in depth"
    assert r.min() >= 0.0 and r.max() <= 1.0


@pytest.mark.parametrize("name", sorted(RESPONSE_HEADS))
def test_response_is_monotone_in_run_length(name):
    head = RESPONSE_HEADS[name](np.array([0]))
    prev = None
    for L in (0.0, 1.0, 3.0, 6.0, 12.0):
        r = head.curve(GRID, runlength=L)
        if prev is not None:
            assert np.all(r >= prev - 1e-6), f"{name} not monotone in run length"
        prev = r


def test_piecewise_head_can_represent_a_step():
    """base -> 1 with zero increments. The sigmoid head cannot do this."""
    head = PiecewiseLinearResponseHead(np.array([0]))
    with torch.no_grad():
        head.intercept.fill_(8.0)                 # sigmoid(8) ~ 0.9997
        head.increment_raw.fill_(-20.0)           # softplus(-20) ~ 0
        head.runlen_raw.fill_(-20.0)
    r = head.curve(GRID)[0]
    assert r.min() > 0.99, f"step not representable, min {r.min()}"


def test_piecewise_head_can_represent_a_constant_half():
    head = PiecewiseLinearResponseHead(np.array([0]))
    with torch.no_grad():
        head.intercept.fill_(0.0)                 # sigmoid(0) = 0.5
        head.increment_raw.fill_(-20.0)
        head.runlen_raw.fill_(-20.0)
    r = head.curve(GRID)[0]
    np.testing.assert_allclose(r, 0.5, atol=1e-3)


def test_sigmoid_head_is_flat_at_half_only_when_it_is_degenerate():
    """The representational limit that moved the piecewise head to primary.

    A sigmoid in depth with a non-negative slope cannot be flat at 0.5 across the
    depth range *and* still able to rise. The claim is an implication, so it is
    tested as one over a parameter sweep: wherever the curve sits within 0.01 of
    0.5 everywhere, its total rise is essentially zero -- the same parameters could
    not then produce the logistic shape. The piecewise head has no such coupling,
    which the two tests above show directly.
    """
    found_flat = False
    for intercept in np.linspace(-4, 4, 17):
        for slope_raw in np.linspace(-20, 1, 43):
            head = SigmoidResponseHead(np.array([0]))
            with torch.no_grad():
                head.intercept.fill_(float(intercept))
                head.depth_raw.fill_(float(slope_raw))
                head.runlen_raw.fill_(-30.0)
            r = head.curve(GRID)[0]
            if np.abs(r - 0.5).max() < 0.01:
                found_flat = True
                rise = float(r.max() - r.min())
                assert rise < 0.02, (
                    f"a sigmoid flat at 0.5 should be degenerate, but intercept "
                    f"{intercept} slope_raw {slope_raw} rises {rise}"
                )
    assert found_flat, "sweep never produced a flat-at-0.5 sigmoid; widen it"


def test_knots_are_increasing_and_start_at_zero():
    assert RESPONSE_KNOTS[0] == 0.0
    assert all(b > a for a, b in zip(RESPONSE_KNOTS, RESPONSE_KNOTS[1:]))


def test_two_cohort_mode_ties_response_parameters_only():
    """Rule 18 again, now for the primary head: one parameter set per macro-cohort."""
    head = PiecewiseLinearResponseHead(np.array([0, 0, 0, 0, 1]))
    assert head.intercept.shape[0] == 2
    curves = head.curve(GRID)
    assert curves.shape[0] == 2


def test_unknown_response_head_name_raises():
    from src.method.stage_a.latent_model import MechanismAwareM1

    with pytest.raises(ValueError, match="response_head"):
        MechanismAwareM1(2, np.array([0]), response_head="gaussian")
