"""Leakage tests (hard rules 5, 6, 6a, 16; spec section 10).

These are the tests that stop a result being quietly invalid. Two distinct failures
are covered:

1. **A feature column that must never be a model input** -- the intraday forecast,
   redispatch, same-quarter-hour actuals, price, theta, s. An allow-list catches
   these.
2. **Price reaching the latent head by any route at all.** The allow-list is a
   declaration; this file also checks the *behaviour*, because a declaration that is
   never exercised proves nothing. If A can see price, A absorbs curtailment and the
   whole separation collapses -- silently, with every other metric looking fine.
"""

from __future__ import annotations

import numpy as np
import pytest
import torch

from src.censoring.model import (
    FORBIDDEN_FEATURES,
    LATENT_ALLOWED_FEATURES,
    TrainConfig,
    build_latent_features,
    check_latent_features,
    fit_m1,
)
from src.censoring.synthetic import SyntheticConfig, generate


def _data():
    return generate(SyntheticConfig(censoring_rate=0.10, gamma=0.0, seed=42))


# ------------------------------------------------------------------- the allow-list


@pytest.mark.parametrize("bad", sorted(FORBIDDEN_FEATURES))
def test_every_forbidden_feature_is_rejected(bad):
    with pytest.raises(ValueError, match="Forbidden feature"):
        check_latent_features(["forecast_mw", bad], task="E1")


def test_feature_outside_the_closed_set_is_rejected_even_if_not_forbidden():
    """Hard rule 16 closes the set: unknown is not the same as allowed.

    `hour_of_day` is the live example -- admissible only on evidence from the I1
    placebo and the E1 ablation, so until that evidence exists it must fail here.
    """
    with pytest.raises(ValueError, match="outside the closed covariate set"):
        check_latent_features(["forecast_mw", "hour_of_day"], task="E1")


def test_t2_rejects_era5_while_t1_allows_it():
    """Hard rule 6a: two tasks, two allow-lists.

    ERA5 and the stitched Historical Forecast archive both contain information from
    after D-1, so they are leakage in the day-ahead task and legitimate in the
    ex-post one.
    """
    check_latent_features(["forecast_mw", "weather_ms_era5"], task="T1")
    with pytest.raises(ValueError, match="outside the closed covariate set"):
        check_latent_features(["forecast_mw", "weather_ms_era5"], task="T2")


def test_t1_rejects_a_t2_only_column_too():
    with pytest.raises(ValueError, match="outside the closed covariate set"):
        check_latent_features(["forecast_mw", "weather_ms_icon_d1"], task="T1")


def test_unknown_task_raises_rather_than_defaulting_to_permissive():
    with pytest.raises(ValueError, match="Unknown task"):
        check_latent_features(["forecast_mw"], task="T3")


def test_published_market_value_is_on_the_forbidden_list():
    """Spec v1.4: it reaches the model through theta, not as a feature column.

    The column-level guard here is the cheap half. The provenance of theta is the
    other half and is asserted separately, below.
    """
    assert "market_value_published" in FORBIDDEN_FEATURES
    assert "marktwert_published" in FORBIDDEN_FEATURES


def test_allow_lists_never_contain_a_forbidden_name():
    for task, allowed in LATENT_ALLOWED_FEATURES.items():
        assert not (allowed & FORBIDDEN_FEATURES), task


# --------------------------------------------------- the latent head cannot see price


def test_latent_features_actually_built_contain_no_price():
    data = _data()
    _, names = build_latent_features(data, task="E1")
    assert names == ["forecast_mw", "weather_ms"]
    assert not (set(names) & FORBIDDEN_FEATURES)


def test_latent_power_is_invariant_to_the_price_series():
    """Behavioural test: change every price, leave A unchanged.

    Fit once, then re-evaluate the latent head on data whose prices have been
    replaced. A must be bit-for-bit identical, because g is a function of the
    forecast and the weather proxy alone. c changes, A does not. This is the
    property that lets the two be told apart at all.
    """
    data = _data()
    fit = fit_m1(data, TrainConfig(max_epochs=25))
    model = fit["model"]

    x, _ = build_latent_features(data, task="E1")
    x = (x - x.mean(axis=0)) / (x.std(axis=0) + 1e-9)
    t = lambda a: torch.as_tensor(a, dtype=torch.float32)  # noqa: E731

    with torch.no_grad():
        a_before = model.latent_quantiles(t(x), t(data.forecast_mw)).numpy()

    scrambled = data.price_eur_mwh.copy()
    rng = np.random.default_rng(0)
    rng.shuffle(scrambled)
    scrambled = -np.abs(scrambled) * 3.0  # make every quarter-hour deeply negative
    data.price_eur_mwh = scrambled

    x2, _ = build_latent_features(data, task="E1")
    x2 = (x2 - x2.mean(axis=0)) / (x2.std(axis=0) + 1e-9)
    with torch.no_grad():
        a_after = model.latent_quantiles(t(x2), t(data.forecast_mw)).numpy()

    np.testing.assert_array_equal(a_before, a_after)


def test_response_head_has_no_access_to_the_latent_features():
    """The separation runs both ways: r sees depth and run length, nothing else."""
    data = _data()
    fit = fit_m1(data, TrainConfig(max_epochs=10))
    params = dict(fit["model"].response.named_parameters())
    assert set(params) == {"intercept", "depth_raw", "runlen_raw"}


def test_theta_provenance_is_recorded_so_it_can_be_checked_per_task():
    """Spec v1.4: assert theta's provenance, not only the feature set.

    In Phase 2 theta comes from a placeholder market value, which is neither the
    published Netztransparenz series nor a recomputation -- so the only correct
    assertion now is that the source is declared and is the placeholder. Phase 3
    replaces this with a real per-task check: T1 may use the published series, T2
    must use the month-to-date recomputation from SMARD data up to D-1.
    """
    data = _data()
    assert data.config.mv_eur_mwh == pytest.approx(45.0)
    saved = {c.cohort_id: c.aw_eur_mwh for c in data.cohorts}
    from src.censoring.cohorts import PLACEHOLDER_AW_EUR_MWH

    assert saved == PLACEHOLDER_AW_EUR_MWH, (
        "theta was built from award values that are not the declared Phase 2 "
        "placeholders -- say where they came from before using them"
    )
