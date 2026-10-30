"""Tests for the E1 generator."""

from __future__ import annotations

import numpy as np
import pytest

from src.censoring.cohorts import build_clock_features, curtailed_share
from src.censoring.synthetic import SyntheticConfig, generate, true_response



def _small(**kw) -> SyntheticConfig:
    base = dict(censoring_rate=0.10, gamma=0.0, r_shape="logistic", seed=42)
    base.update(kw)
    return SyntheticConfig(**base)


def test_generator_reproduces_c_true_exactly_when_r_star_is_known():
    """The core guarantee of the benchmark: truth is recomputable, not approximate.

    Given the saved theta, s and depth, applying the known r* must return exactly the
    c_true the generator used. If this drifts, every recovery score is meaningless.
    """
    data = generate(_small())
    r = true_response(data.depth, data.config) * data.s
    c = curtailed_share(data.cohorts.shares, data.s, r)
    np.testing.assert_allclose(c, data.c_true, atol=1e-12, rtol=0)
    np.testing.assert_allclose(r, data.r_true, atol=1e-12, rtol=0)


def test_observation_model_holds_exactly_without_noise():
    data = generate(_small(observation_noise_mw=0.0))
    np.testing.assert_allclose(
        data.g_obs_mw, data.a_true_mw * (1.0 - data.c_true), atol=1e-9
    )


def test_generation_is_deterministic_in_the_seed():
    a = generate(_small(seed=42))
    b = generate(_small(seed=42))
    c = generate(_small(seed=43))
    np.testing.assert_array_equal(a.price_eur_mwh, b.price_eur_mwh)
    np.testing.assert_array_equal(a.c_true, b.c_true)
    assert not np.array_equal(a.price_eur_mwh, c.price_eur_mwh)


@pytest.mark.parametrize("rate", [0.05, 0.10, 0.20])
def test_realised_negative_rate_is_close_to_the_target(rate):
    data = generate(_small(censoring_rate=rate))
    realised = float((data.price_eur_mwh < 0).mean())
    assert abs(realised - rate) < 0.01, f"target {rate}, realised {realised}"


def test_censored_share_is_reported_not_assumed_equal_to_the_negative_rate():
    """Exposure and actual curtailment are distinct, and the diagnostics say so."""
    data = generate(_small(r_shape="half"))
    d = data.diagnostics
    assert d["censored_rate"] <= d["realised_negative_rate"] + 1e-9
    assert 0.0 < d["mean_c_on_censored"] < 1.0


def test_subhour_episodes_leave_the_hourly_mean_positive():
    """These are the quarter-hours that separate the two clocks (spec section 3, I4).

    Without them the hour-clock cohorts and the quarter-hour cohort would see the
    same signal and the K-cohort structure would not be identified.
    """
    data = generate(_small(subhour_episode_share=0.5))
    clock = build_clock_features(data.ts_utc_ns, data.price_eur_mwh)
    disagree = (data.price_eur_mwh < 0) & (clock.hour_mean_price > 0)
    assert disagree.sum() > 0, "no quarter-hour where the two clocks disagree"

    # On exactly those quarter-hours the QH-clock cohort's section 51 trigger fires
    # and the 6 h cohort's does not, which shows up in theta: 0 for the former,
    # minus the market premium for the latter.
    ids = data.cohorts.ids
    qh_i = ids.index("post_feb2025_qh")
    hour_i = ids.index("wind2016_2020_6h")
    assert np.all(data.theta[qh_i][disagree] == 0.0)
    assert np.all(data.theta[hour_i][disagree] < 0.0)
    assert data.s[qh_i][disagree].all()

    # The 6 h cohort is still exposed on the deepest of them -- not through section
    # 51 but through its market premium, AW 62 - MV 45 = 17 EUR/MWh. That is the
    # spec section 3 case of a cohort section 51 never reaches which switches off
    # anyway, and it must not be mistaken for a trigger.
    deep = disagree & (data.price_eur_mwh < -17.0)
    shallow = disagree & (data.price_eur_mwh > -17.0)
    if deep.any():
        assert data.s[hour_i][deep].all()
    if shallow.any():
        assert not data.s[hour_i][shallow].any()


def test_all_three_response_shapes_are_monotone_in_depth():
    grid = np.linspace(0.0, 80.0, 200)
    for shape in ("step", "logistic", "half"):
        r = true_response(grid, _small(r_shape=shape))
        assert np.all(np.diff(r) >= -1e-12), shape
        assert r.min() >= 0.0 and r.max() <= 1.0


def test_response_is_zero_where_not_exposed():
    data = generate(_small())
    assert np.all(data.r_true[data.s == 0] == 0.0)


def test_gamma_concentrates_censoring_on_windy_periods():
    """gamma is the weather-price confounding knob; at 0 it must do nothing."""
    f = generate(_small(gamma=0.0)).forecast_mw
    lo = generate(_small(gamma=0.0))
    hi = generate(_small(gamma=1.0))
    mean_f_lo = lo.forecast_mw[lo.price_eur_mwh < 0].mean()
    mean_f_hi = hi.forecast_mw[hi.price_eur_mwh < 0].mean()
    assert mean_f_hi > mean_f_lo
    # At gamma = 0 the censored periods look like the sample as a whole.
    assert abs(mean_f_lo - f.mean()) < 0.1 * f.std()


def test_bad_r_shape_raises():
    with pytest.raises(ValueError, match="r_shape"):
        SyntheticConfig(r_shape="exponential")
