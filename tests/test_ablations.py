"""Tests for the ablation ladder and the self-contained metrics (spec v1.7).

The ladder's whole value rests on one property: each rung must differ from the full
model in exactly one place. If two things change at once the result attributes the
effect to the wrong component, which is worse than not running it.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.censoring.metrics import curtailment_recovery, recovery_skill
from src.censoring.model import (
    ABLATION_FULL,
    Ablation,
    apply_cohort_ablation,
    apply_exposure_ablation,
    build_latent_features,
    cohort_runlength_hours,
)
from src.censoring.run_ablations import LADDER
from src.censoring.synthetic import SyntheticConfig, generate


def _data():
    return generate(SyntheticConfig(censoring_rate=0.10, gamma=0.0, seed=42))


# ------------------------------------------------------------------- the ladder


@pytest.mark.parametrize("ab", LADDER, ids=[a.label for a in LADDER])
def test_each_rung_changes_exactly_one_piece(ab):
    differs = ab.differs_from_full()
    if ab.label == "M1":
        assert differs == []
    else:
        assert len(differs) == 1, f"{ab.label} changes {differs}"


def test_ladder_labels_are_unique_and_describe_what_was_removed():
    labels = [a.label for a in LADDER]
    assert len(set(labels)) == len(labels)
    for a in LADDER:
        assert a.piece_removed, a.label


# --------------------------------------------------------------- exposure (A2)


def test_exposure_off_keeps_the_price_signal_and_drops_the_rules():
    """A2 isolates the legal structure, so the model must still see the price."""
    d = _data()
    s, depth, _ = apply_exposure_ablation(d, "always_on")
    assert (s == 1.0).all(), "every cohort should be exposed everywhere"
    # Depth is now measured below zero, not below each cohort's own threshold.
    expected = np.maximum(0.0, -d.price_eur_mwh)
    for k in range(s.shape[0]):
        np.testing.assert_allclose(depth[k], expected)
    # The price signal survives: depth is still positive exactly where price < 0.
    assert ((depth[0] > 0) == (d.price_eur_mwh < 0)).all()


def test_exposure_rules_mode_returns_the_real_rule_output():
    d = _data()
    s, depth, _ = apply_exposure_ablation(d, "rules")
    np.testing.assert_array_equal(s, d.s)
    np.testing.assert_allclose(depth, d.depth)


def test_unknown_exposure_mode_raises():
    with pytest.raises(ValueError, match="exposure_mode"):
        apply_exposure_ablation(_data(), "sometimes")


# ----------------------------------------------------------------- cohorts (A3)


def test_one_cohort_mode_preserves_total_exposed_capacity():
    """Collapsing to one cohort must not change how much capacity is exposed."""
    d = _data()
    rl = cohort_runlength_hours(d)
    w, s, depth, runlen, gi = apply_cohort_ablation(d, d.s, d.depth, rl, "one")
    assert w.shape == (1,) and np.isclose(w[0], 1.0)
    assert gi.tolist() == [0]
    expected_exposed = (d.cohorts.shares[:, None] * d.s).sum(axis=0)
    np.testing.assert_allclose(s[0], expected_exposed, atol=1e-12)


def test_one_cohort_depth_is_the_capacity_weighted_mean_where_exposed():
    d = _data()
    rl = cohort_runlength_hours(d)
    _, s, depth, _, _ = apply_cohort_ablation(d, d.s, d.depth, rl, "one")
    exposed = (d.cohorts.shares[:, None] * d.s).sum(axis=0)
    want = np.where(
        exposed > 0,
        (d.cohorts.shares[:, None] * d.s * d.depth).sum(axis=0) / np.maximum(exposed, 1e-12),
        0.0,
    )
    np.testing.assert_allclose(depth[0], want, atol=1e-9)
    assert np.all(depth[0][exposed == 0] == 0.0)


def test_k_and_two_cohort_modes_leave_exposure_untouched():
    """Rule 18 again: the two-cohort fallback pools r, never s."""
    d = _data()
    rl = cohort_runlength_hours(d)
    for mode in ("K", "two"):
        w, s, depth, _, gi = apply_cohort_ablation(d, d.s, d.depth, rl, mode)
        np.testing.assert_array_equal(s, d.s)
        np.testing.assert_allclose(depth, d.depth)
        np.testing.assert_allclose(w, d.cohorts.shares)
    _, _, _, _, gi_two = apply_cohort_ablation(d, d.s, d.depth, rl, "two")
    assert len(set(gi_two.tolist())) == 2


# -------------------------------------------------------- the leakage rung (A7)


def test_price_reaches_g_only_through_the_explicit_ablation_flag():
    """A7 is the one place price may enter g, and it must be asked for by name."""
    d = _data()
    _, names = build_latent_features(d, task="E1")
    assert "price_eur_mwh" not in names

    _, names_broken = build_latent_features(d, task="E1", allow_price=True)
    assert names_broken[-1] == "price_eur_mwh"


def test_a7_is_the_only_rung_that_turns_the_leakage_rule_off():
    broken = [a.label for a in LADDER if a.price_in_latent]
    assert broken == ["A7"]


# ------------------------------------------------------------- the new metrics


def test_recovery_skill_is_one_at_the_oracle_and_zero_at_the_raw_forecast():
    assert recovery_skill(1200.0, 1330.0, 1200.0) == pytest.approx(1.0)
    assert recovery_skill(1330.0, 1330.0, 1200.0) == pytest.approx(0.0)
    # Worse than doing nothing is negative, which is the point of the scale.
    assert recovery_skill(1500.0, 1330.0, 1200.0) < 0


def test_recovery_skill_is_nan_when_there_is_no_headroom():
    """If the oracle cannot beat the raw forecast, the score has no denominator."""
    assert np.isnan(recovery_skill(1200.0, 1330.0, 1330.0))


def test_curtailment_recovery_is_exact_on_a_perfect_estimate():
    c_true = np.array([0.0, 0.2, 0.5, 0.0, 0.3])
    mask = c_true > 0
    out = curtailment_recovery(c_true.copy(), c_true, mask)
    assert out["c_mae"] == pytest.approx(0.0)
    assert out["c_bias"] == pytest.approx(0.0)
    assert out["c_corr"] == pytest.approx(1.0)
    assert out["c_total_hat"] == pytest.approx(out["c_total_true"])


def test_curtailment_recovery_reports_nan_when_no_estimate_exists():
    """Baselines produce no c-hat at all; that must read as absent, not as zero."""
    c_true = np.array([0.0, 0.4])
    out = curtailment_recovery(None, c_true, c_true > 0)
    assert np.isnan(out["c_mae"])


def test_curtailment_recovery_detects_a_systematic_underestimate():
    c_true = np.array([0.2, 0.4, 0.6])
    out = curtailment_recovery(c_true * 0.5, c_true, np.ones(3, dtype=bool))
    assert out["c_bias"] < 0
    assert out["c_corr"] == pytest.approx(1.0)   # right shape, wrong level
