"""`response_curve` must agree with `synthetic.true_response_curve`.

This is the assertion that was missing on 9 November 2026, and its absence let a
double-counted atom through 179 passing tests. See `docs/20_response_curve_bug.md`.

The existing tests in `test_m2.py` check that the curve is monotone, bounded, and
self-consistent — all of which a doubled atom satisfies. The one check they never
made is the one that matters: feed in the parameter vector that *is* the known truth
and require the curve to return that truth. Nothing here depends on how the fix is
worded; each test states a property of the mapping from `p` to `r_hat`.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.method.stage_a.reservation_depth_model import knot_grid, response_curve
from src.censoring.run_synthetic import DEPTH_GRID
from src.method.synthetic import (
    SyntheticConfig,
    true_response,
    true_response_curve,
)

SHARES = np.array([1.0])


def _knots() -> np.ndarray:
    """The knot grid M2 actually uses, atom included."""
    depth = np.concatenate([np.zeros(40), np.linspace(0.5, 140.0, 400)])
    train = np.ones(depth.size, dtype=bool)
    k = knot_grid(depth, train, with_atom=True)
    assert k[0] == 0.0, "this test is about the atom; knot_grid must place it first"
    assert np.isinf(k[-1]), "the never-respond atom must close the grid"
    return k


def _true_p(cfg: SyntheticConfig, knots: np.ndarray) -> np.ndarray:
    """The exact simplex point whose CDF is r* for this shape.

    p[0] is the mass at 0+ (switches off at any positive depth), p[-1] the mass that
    never responds, and p[j] the mass that first responds at finite knot c_j.
    """
    finite = knots[np.isfinite(knots)]              # finite[0] == 0.0, the atom
    at_knots = true_response(np.maximum(finite, 1e-12), cfg)   # r* just above each c_j
    p = np.zeros(knots.size)
    p[0] = at_knots[0]                              # r*(0+)
    p[1:finite.size] = np.diff(at_knots)            # increments between finite knots
    p[-1] = 1.0 - at_knots[-1]                      # the remainder never responds
    assert p.min() >= -1e-12 and abs(p.sum() - 1.0) < 1e-12
    return np.array([p])


@pytest.mark.parametrize("shape", ["step", "half"])
def test_step_and_half_are_recovered_exactly(shape):
    """Both are exactly representable on the grid, so the error must be zero."""
    cfg = SyntheticConfig(r_shape=shape)
    knots = _knots()
    r_hat = response_curve(_true_p(cfg, knots), knots, SHARES, DEPTH_GRID)
    r_true = true_response_curve(cfg, DEPTH_GRID)
    worst = np.abs(r_hat - r_true).max()
    assert worst < 1e-12, (
        f"{shape}: fed the true p, response_curve is off by {worst:.4f}. "
        f"r_hat[:4]={np.round(r_hat[:4], 4)} r_true[:4]={np.round(r_true[:4], 4)}"
    )


def test_atom_mass_is_counted_once_not_twice():
    """The defect, stated directly: p_atom = q must give r_hat = q for every z > 0."""
    knots = _knots()
    pos = DEPTH_GRID > 0
    for q in (0.0, 0.25, 0.5, 0.75, 1.0):
        p = np.zeros(knots.size)
        p[0], p[-1] = q, 1.0 - q
        r_hat = response_curve(np.array([p]), knots, SHARES, DEPTH_GRID)
        assert r_hat[pos] == pytest.approx(q, abs=1e-12), (
            f"atom mass {q} returned {r_hat[pos][0]:.4f} at positive depth"
        )


@pytest.mark.parametrize("shape", ["step", "logistic", "half"])
def test_zero_depth_is_zero_response_for_every_shape(shape):
    """`true_response` is 0 at d = 0 for all three shapes; the curve must match."""
    cfg = SyntheticConfig(r_shape=shape)
    knots = _knots()
    r_hat = response_curve(_true_p(cfg, knots), knots, SHARES, DEPTH_GRID)
    assert DEPTH_GRID[0] == 0.0
    assert r_hat[0] == pytest.approx(0.0, abs=1e-12)
    assert true_response_curve(cfg, DEPTH_GRID)[0] == pytest.approx(0.0, abs=1e-12)


def test_logistic_matches_the_truth_at_the_knots():
    """A step CDF can only match a smooth r* at its jumps, so test it there.

    Between knots the curve lags by at most one knot step of the true slope; that is
    discretisation, not error. At the knots it must be exact.
    """
    cfg = SyntheticConfig(r_shape="logistic")
    knots = _knots()
    finite = knots[np.isfinite(knots) & (knots > 0.0)]
    grid = finite[finite <= DEPTH_GRID.max()]
    r_hat = response_curve(_true_p(cfg, knots), knots, SHARES, grid)
    r_true = true_response_curve(cfg, grid)
    worst = np.abs(r_hat - r_true).max()
    assert worst < 1e-12, f"logistic is off by {worst:.4f} at its own knots"


def test_the_no_atom_grid_is_unaffected():
    """M2-noAtom has no 0.0 knot, so it was never exposed to the defect.

    Pinned so a future change to the atom branch cannot silently alter this path.
    """
    depth = np.linspace(0.5, 140.0, 400)
    knots = knot_grid(depth, np.ones(depth.size, dtype=bool), with_atom=False)
    assert knots[0] != 0.0
    p = np.zeros(knots.size)
    p[0], p[-1] = 0.5, 0.5                     # 50% respond at the first finite knot
    r_hat = response_curve(np.array([p]), knots, SHARES, DEPTH_GRID)
    assert r_hat[DEPTH_GRID < knots[0]] == pytest.approx(0.0, abs=1e-12)
    assert r_hat[DEPTH_GRID >= knots[0]] == pytest.approx(0.5, abs=1e-12)
