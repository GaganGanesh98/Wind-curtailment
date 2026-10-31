"""The market value is resolution-invariant when the price is hourly.

Block 5 of the 1 Nov 2026 brief asks that the rule-17 recomputation use "the formula
in force for each month", and the formula basis changes on 1 Oct 2025: 60-minute
values before, 15-minute values after. These tests establish that the existing
quarter-hour code already satisfies that for both regimes, so no second code path --
and no month-dependent branch -- is needed.

The reason is that MV is a ratio of sums. With the price constant inside each hour
(which is what SMARD serves before 1 Oct 2025: the hourly price repeated into all
four quarter-hours), aggregating at hourly or quarter-hourly resolution gives the
same number exactly, not approximately.
"""

from __future__ import annotations

import numpy as np
import pytest


def mv(price: np.ndarray, quantity: np.ndarray) -> float:
    """EEG Anlage 1 no. 3.3.2: the generation-weighted average spot price."""
    return float((price * quantity).sum() / quantity.sum())


def test_hourly_and_quarterhour_market_value_agree_exactly():
    """The identity the no-branch decision rests on."""
    rng = np.random.default_rng(42)
    n_hours = 744                                    # a 31-day month
    p_hour = rng.normal(80.0, 40.0, n_hours)         # EUR/MWh, some negative
    a_qh = rng.gamma(2.0, 3000.0, n_hours * 4)       # quarter-hourly generation

    # Pre-Oct-2025 SMARD: each quarter-hour carries its hour's price.
    p_qh = np.repeat(p_hour, 4)
    # The statutory hourly quantity is the sum of its four quarter-hours.
    a_hour = a_qh.reshape(n_hours, 4).sum(axis=1)

    assert mv(p_qh, a_qh) == pytest.approx(mv(p_hour, a_hour), rel=0, abs=1e-9)


def test_the_identity_needs_the_price_to_be_constant_within_the_hour():
    """A guard, so the test above is not mistaken for a general claim.

    From 1 Oct 2025 the price genuinely varies inside the hour, and then the two
    resolutions do NOT agree -- which is exactly why the quarter-hour series has to be
    used for those months rather than an hourly average of it.
    """
    rng = np.random.default_rng(7)
    n_hours = 200
    p_qh = rng.normal(80.0, 40.0, n_hours * 4)       # varies within the hour
    a_qh = rng.gamma(2.0, 3000.0, n_hours * 4)

    p_hour = p_qh.reshape(n_hours, 4).mean(axis=1)
    a_hour = a_qh.reshape(n_hours, 4).sum(axis=1)

    assert mv(p_qh, a_qh) != pytest.approx(mv(p_hour, a_hour), rel=1e-6)


def test_mw_versus_mwh_cancels_in_the_ratio():
    """act_onshore_mw is power, not energy; the quarter-hour duration cancels."""
    rng = np.random.default_rng(1)
    p = rng.normal(80.0, 40.0, 400)
    a_mw = rng.gamma(2.0, 3000.0, 400)
    a_mwh = a_mw * 0.25                              # every QH has equal duration

    assert mv(p, a_mw) == pytest.approx(mv(p, a_mwh), rel=0, abs=1e-9)
