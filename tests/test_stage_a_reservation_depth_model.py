"""Tests for M2 (HRD), against docs/09_m2_preregistration.md and Amendment 1.

The point of most of these is that M2's claimed advantage over M1 is *structural* —
monotonicity and [0, 1] confinement by construction rather than by penalty. A claim
like that is only worth making if it is tested, so it is tested directly: on random
parameters, on adversarial ones, and on a recovery problem where the truth is known.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.method.stage_a.reservation_depth_model import (
    ABLATIONS,
    XCHECK_RTOL,
    build_design,
    eventday_folds,
    knot_grid,
    numerical_rank,
    pool_blocks,
    response_curve,
    season_index,
    simplex_projection,
    solve_stage_r,
    stage_a_basis,
    weights_from_residuals,
)


# ------------------------------------------------------- the structural guarantees


def test_response_is_monotone_and_in_unit_interval_for_any_simplex_point():
    """The central claim: monotone and bounded BY CONSTRUCTION, not by fitting."""
    rng = np.random.default_rng(0)
    knots = np.concatenate([[0.0], np.arange(2.0, 60.0, 2.0), [np.inf]])
    grid = np.linspace(0.0, 80.0, 201)
    for _ in range(50):
        n_b = rng.integers(1, 5)
        p = rng.dirichlet(np.ones(knots.size), size=n_b)
        shares = rng.random(n_b) + 0.05
        r = response_curve(p, knots, shares, grid)
        assert np.all(np.diff(r) >= -1e-12), "response must be non-decreasing in depth"
        assert r.min() >= -1e-12 and r.max() <= 1.0 + 1e-9


def test_mass_on_the_never_atom_caps_the_response_below_one():
    """The inf atom is what lets a cohort never fully respond at any depth."""
    knots = np.concatenate([[0.0], np.arange(2.0, 40.0, 2.0), [np.inf]])
    p = np.zeros((1, knots.size))
    p[0, 1] = 0.3          # 30% switch off by 2 EUR/MWh of depth
    p[0, -1] = 0.7         # 70% never switch off
    r = response_curve(p, knots, np.array([1.0]), np.array([0.0, 5.0, 1000.0]))
    assert r[0] == pytest.approx(0.0)
    assert r[-1] == pytest.approx(0.3, abs=1e-9)


def test_never_atom_column_of_the_design_is_exactly_zero():
    """Documented as intentional, so pinned: inf contributes nothing to X."""
    s = np.array([[1.0, 1.0, 0.0]])
    depth = np.array([[10.0, 40.0, 0.0]])
    knots = np.array([0.0, 2.0, np.inf])
    X = build_design(s, depth, np.array([1.0]), knots, [[0]])
    assert np.all(X[:, 2] == 0.0)
    assert np.allclose(X[:, 0], [1.0, 1.0, 0.0])      # z > 0 atom
    assert np.allclose(X[:, 1], [1.0, 1.0, 0.0])      # z >= 2


# --------------------------------------------------------------- simplex projection


def test_simplex_projection_returns_a_point_on_the_simplex():
    rng = np.random.default_rng(1)
    V = rng.normal(size=(20, 11)) * 5.0
    P = simplex_projection(V)
    assert np.allclose(P.sum(axis=1), 1.0, atol=1e-12)
    assert P.min() >= 0.0


def test_simplex_projection_is_identity_on_the_simplex():
    rng = np.random.default_rng(2)
    P = rng.dirichlet(np.ones(7), size=5)
    assert np.allclose(simplex_projection(P), P, atol=1e-12)


def test_simplex_projection_is_the_nearest_point():
    """Checked against a brute-force search on a coarse lattice."""
    v = np.array([[0.9, -0.4, 0.2]])
    p = simplex_projection(v)[0]
    bd = np.inf
    g = np.linspace(0, 1, 101)
    for a in g:
        for b in g:
            if a + b > 1 + 1e-12:
                continue
            q = np.array([a, b, 1 - a - b])
            d = np.sum((q - v[0]) ** 2)
            if d < bd:
                bd = d
    assert np.sum((p - v[0]) ** 2) <= bd + 1e-6


# ------------------------------------------------------------------ pooling / rank


def test_identical_exposure_and_depth_cohorts_pool_into_one_block():
    """Section 2's rule, implemented by pattern rather than by naming cases."""
    s = np.array([[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
    depth = np.array([[5.0, 0.0], [5.0, 0.0], [0.0, 3.0]])
    _, members = pool_blocks(s, depth, np.array([0.2, 0.3, 0.5]))
    assert sorted(len(m) for m in members) == [1, 2]


def test_theta_zero_collapses_every_cohort_into_one_block():
    """Pre-registration 4.3: with MP = 0 the cohort dimension has rank 1."""
    K, T = 8, 50
    s = np.tile((np.arange(T) % 7 < 3).astype(float), (K, 1))
    depth = np.tile(np.linspace(0, 30, T), (K, 1))
    _, members = pool_blocks(s, depth, np.full(K, 1.0 / K))
    assert len(members) == 1 and len(members[0]) == K

    knots = np.array([0.0, 2.0, 4.0, np.inf])
    X = build_design(s, depth, np.full(K, 1.0 / K), knots, members)
    rank, cols = numerical_rank(X, np.ones(T))
    assert cols == 4                      # one block x four knots
    assert rank < cols                    # the inf column is zero, so never full rank


def test_unsupported_cohorts_pool_together():
    s = np.array([[0.0, 0.0], [0.0, 0.0], [1.0, 0.0]])
    depth = np.zeros((3, 2))
    depth[2, 0] = 4.0
    _, members = pool_blocks(s, depth, np.array([0.1, 0.2, 0.7]))
    assert [len(m) for m in sorted(members, key=len)] == [1, 2]


# ----------------------------------------------------------------------- solvers


def test_cvxpy_and_fista_agree_and_recover_a_known_response():
    """Recovery plus the Amendment 1 cross-check, on one problem."""
    rng = np.random.default_rng(42)
    T, n_b = 3000, 2
    knots = np.concatenate([[0.0], np.arange(2.0, 40.0, 2.0), [np.inf]])
    n_j = knots.size
    p_true = np.zeros((n_b, n_j))
    p_true[0, 3], p_true[0, 8], p_true[0, -1] = 0.4, 0.3, 0.3
    p_true[1, 1], p_true[1, 5], p_true[1, -1] = 0.2, 0.5, 0.3
    shares = np.array([0.6, 0.4])

    s = (rng.random((n_b, T)) < 0.4).astype(float)
    depth = rng.uniform(0.0, 50.0, (n_b, T)) * s
    members = [[0], [1]]
    X = build_design(s, depth, shares, knots, members)
    y = X @ p_true.reshape(-1) + rng.normal(0.0, 0.002, T)
    omega = np.ones(T)

    res = solve_stage_r(X, y, omega, n_b, n_j, 0.0, shares)
    assert res["status"] in ("optimal", "optimal_inaccurate")
    assert res["xcheck_ok"], (f"cvxpy/FISTA disagreed by {res['xcheck_rel_diff']:.3e} "
                              f"> {XCHECK_RTOL}")
    assert np.allclose(res["p"].sum(axis=1), 1.0, atol=1e-6)

    grid = np.linspace(0.0, 50.0, 101)
    r_true = response_curve(p_true, knots, shares, grid)
    r_hat = response_curve(res["p"], knots, shares, grid)
    assert np.abs(r_hat - r_true).mean() < 0.02


def test_fista_matches_cvxpy_with_the_pooling_penalty_on():
    rng = np.random.default_rng(7)
    T, n_b = 1200, 3
    knots = np.concatenate([[0.0], np.arange(2.0, 24.0, 2.0), [np.inf]])
    n_j = knots.size
    shares = np.array([0.5, 0.3, 0.2])
    s = (rng.random((n_b, T)) < 0.5).astype(float)
    depth = rng.uniform(0.0, 30.0, (n_b, T)) * s
    X = build_design(s, depth, shares, knots, [[0], [1], [2]])
    y = rng.random(T) * 0.3
    omega = rng.uniform(0.5, 2.0, T)
    for lam in (0.0, 0.1, 10.0):
        res = solve_stage_r(X, y, omega, n_b, n_j, lam, shares)
        assert res["xcheck_ok"], f"lambda={lam}: rel {res['xcheck_rel_diff']:.3e}"


def test_pooling_penalty_pulls_blocks_together():
    """lambda large -> blocks converge; this is what M2-noPool removes."""
    rng = np.random.default_rng(3)
    T, n_b = 800, 2
    knots = np.array([0.0, 2.0, 4.0, 6.0, np.inf])
    shares = np.array([0.5, 0.5])
    s = np.ones((n_b, T))
    depth = np.tile(rng.uniform(0, 8, T), (n_b, 1))
    X = build_design(s, depth, shares, knots, [[0], [1]])
    y = rng.random(T) * 0.2
    omega = np.ones(T)
    lo = solve_stage_r(X, y, omega, n_b, knots.size, 0.0, shares)["p"]
    hi = solve_stage_r(X, y, omega, n_b, knots.size, 1e4, shares)["p"]
    assert np.abs(hi[0] - hi[1]).sum() < np.abs(lo[0] - lo[1]).sum() + 1e-9
    assert np.abs(hi[0] - hi[1]).sum() < 1e-3


# ----------------------------------------------------------------------- stage A


def test_stage_a_basis_is_full_rank_and_season_mapping_is_right():
    dates = np.array(["2026-01-15", "2026-04-15", "2026-07-15", "2026-10-15"])
    assert season_index(dates).tolist() == [0, 1, 2, 3]
    hour = np.tile(np.arange(24), 40)
    d = np.repeat(np.array(["2026-01-15", "2026-04-15", "2026-07-15", "2026-10-15"]),
                  240)
    X = stage_a_basis(hour, d)
    assert np.linalg.matrix_rank(X) == X.shape[1]


def test_eventday_folds_never_split_a_day_and_are_deterministic():
    dates = np.repeat([f"2026-04-{d:02d}" for d in range(1, 21)], 96)
    f1 = eventday_folds(dates)
    f2 = eventday_folds(dates)
    assert np.array_equal(f1, f2)
    for d in np.unique(dates):
        assert len(np.unique(f1[dates == d])) == 1


def test_weights_are_larger_where_the_residual_variance_is_smaller():
    n = 4000
    rng = np.random.default_rng(5)
    hour = np.arange(n) % 24
    a_hat = np.full(n, 5000.0)
    noisy = hour < 12
    resid = np.where(noisy, rng.normal(0, 0.30, n), rng.normal(0, 0.03, n))
    omega = weights_from_residuals(a_hat, resid, hour)
    assert omega[~noisy].mean() > 10.0 * omega[noisy].mean()


def test_knot_grid_has_the_atom_and_the_never_atom():
    depth = np.array([[0.0, 5.0, 40.0, 100.0]])
    train = np.ones(4, dtype=bool)
    g = knot_grid(depth, train, with_atom=True)
    assert g[0] == 0.0 and np.isinf(g[-1])
    g2 = knot_grid(depth, train, with_atom=False)
    assert g2[0] == 2.0 and np.isinf(g2[-1])


def test_ablation_table_matches_the_pre_registration():
    labels = [a.label for a in ABLATIONS]
    assert labels == ["M2", "M2-noPool", "M2-noAtom"]
    byname = {a.label: a for a in ABLATIONS}
    assert byname["M2-noPool"].pool is False and byname["M2-noPool"].atom is True
    assert byname["M2-noAtom"].atom is False and byname["M2-noAtom"].pool is True


# --------------------------------------------- Amendment 2: the 0.2 stability rule


def test_structural_recovery_is_undefined_where_the_denominator_is_too_small():
    """A2.3: form G/(1 - c_hat) only where 1 - c_hat >= 0.2, never with a tiny floor.

    Flooring the denominator at 1e-6 (the earlier behaviour) does not stabilise the
    recovery -- it replaces a divergence with a value up to a million times G, which
    would then dominate any MAE it entered. Undefined is the honest answer.
    """
    from src.method.stage_a.reservation_depth_model import RECOVERY_MIN_DENOM

    assert RECOVERY_MIN_DENOM == 0.2
    g = np.array([1000.0, 1000.0, 1000.0, 1000.0])
    c_hat = np.array([0.0, 0.5, 0.80, 0.999])
    a = np.full(c_hat.shape, np.nan)
    ok = c_hat <= (1.0 - RECOVERY_MIN_DENOM)
    a[ok] = g[ok] / (1.0 - c_hat[ok])

    assert ok.tolist() == [True, True, True, False]
    assert a[0] == pytest.approx(1000.0)
    assert a[1] == pytest.approx(2000.0)
    assert a[2] == pytest.approx(5000.0)          # exactly at the 0.2 boundary
    assert np.isnan(a[3])                          # would have been 1,000,000


def test_the_boundary_is_tested_on_c_hat_not_on_one_minus_c_hat():
    """IEEE754: 1 - 0.8 is 0.19999999999999996, so the natural form excludes ĉ = 0.8.

    Pinned because the rule in Amendment 2 A2.3 is written as '1 - c_hat >= 0.2' and
    coding it that way literally gets the boundary wrong by one quarter-hour class.
    """
    from src.method.stage_a.reservation_depth_model import RECOVERY_MIN_DENOM

    assert (1.0 - 0.8) >= RECOVERY_MIN_DENOM is False or (1.0 - 0.8) < RECOVERY_MIN_DENOM
    assert 0.8 <= (1.0 - RECOVERY_MIN_DENOM)      # the form actually used


# ------------------- Amendment 2 as corrected: the SHARED stability fallback


def _c(*vals):
    return np.array(vals, dtype=float)


def test_unstable_quarter_hours_give_an_exactly_zero_paired_difference():
    """The property the whole correction rests on, asserted exactly, not approximately.

    If unstable quarter-hours did not tie exactly, a method could gain from falling
    back, and the paired event-day bootstrap would be comparing different samples.
    """
    from src.method.stage_a.reservation_depth_model import scored_recovery, shared_stability_mask

    g = np.array([1000.0, 1000.0, 1000.0, 1000.0, 1000.0])
    a_stage = np.array([1100.0, 1200.0, 1300.0, 1400.0, 1500.0])
    c_m2 = _c(0.00, 0.50, 0.95, 0.80, 0.30)     # unstable at index 2
    c_b3 = _c(0.10, 0.99, 0.40, 0.20, 0.30)     # unstable at index 1

    unstable = shared_stability_mask({"M2": c_m2, "B3": c_b3})
    assert unstable.tolist() == [False, True, True, False, False]

    a_m2 = scored_recovery(g, c_m2, a_stage, unstable)
    a_b3 = scored_recovery(g, c_b3, a_stage, unstable)

    diff = a_m2 - a_b3
    assert np.all(diff[unstable] == 0.0), "unstable QHs must tie EXACTLY"
    assert np.array_equal(a_m2[unstable], a_stage[unstable])
    assert np.array_equal(a_b3[unstable], a_stage[unstable])
    # and the stable ones are genuinely the structural recovery, not the fallback
    assert a_m2[0] == pytest.approx(1000.0)
    assert a_b3[0] == pytest.approx(1000.0 / 0.9)
    assert np.any(diff[~unstable] != 0.0)


def test_c_hat_exactly_at_the_boundary_is_stable():
    """ĉ = 0.8 is included; the IEEE754 trap would have excluded it."""
    from src.method.stage_a.reservation_depth_model import shared_stability_mask

    assert shared_stability_mask({"m": _c(0.8)}).tolist() == [False]
    assert shared_stability_mask({"m": _c(0.8000001)}).tolist() == [True]


def test_a_method_cannot_gain_by_being_unstable():
    """Falling back can never beat the rival: both land on the same stage-A value."""
    from src.method.stage_a.reservation_depth_model import scored_recovery, shared_stability_mask

    rng = np.random.default_rng(3)
    n = 500
    g = rng.uniform(100.0, 5000.0, n)
    a_stage = rng.uniform(100.0, 6000.0, n)
    a_true = rng.uniform(100.0, 6000.0, n)
    c_good = rng.uniform(0.0, 0.5, n)
    c_bad = rng.uniform(0.0, 0.999, n)          # often unstable

    unstable = shared_stability_mask({"g": c_good, "b": c_bad})
    ag = scored_recovery(g, c_good, a_stage, unstable)
    ab = scored_recovery(g, c_bad, a_stage, unstable)
    err_g = np.abs(ag - a_true)
    err_b = np.abs(ab - a_true)
    assert np.all(err_g[unstable] == err_b[unstable])   # no edge either way
    assert np.isfinite(ag).all() and np.isfinite(ab).all()


def test_recovery_report_shows_whether_the_shared_mask_binds_harder():
    from src.method.stage_a.reservation_depth_model import recovery_report

    rep = recovery_report({"M2": _c(0.1, 0.9, 0.1, 0.1),
                           "B3": _c(0.1, 0.1, 0.95, 0.1)})
    assert rep["fallback_n_shared"] == 2
    assert rep["fallback_share_shared"] == pytest.approx(0.5)
    assert rep["fallback_share_own"]["M2"] == pytest.approx(0.25)
    assert rep["fallback_share_own"]["B3"] == pytest.approx(0.25)
    assert rep["shared_binds_harder_than_any_own"] is True


# --------------------------- Amendment 6: retransformation, and the hard stage-A test


def test_duan_smearing_recovers_the_mean_of_a_lognormal():
    """exp(OLS on logs) estimates the GEOMETRIC mean; smearing recovers the arithmetic.

    For Y = exp(mu + s*Z): geometric mean exp(mu), arithmetic mean exp(mu + s^2/2).
    With s = 0.8 the naive estimator is low by a factor exp(0.32) ~ 1.38, which is the
    size of the bias that made fit_stage_a lose to the raw forecast.
    """
    from src.method.stage_a.reservation_depth_model import duan_smearing_factor

    rng = np.random.default_rng(0)
    mu, sigma, n = 2.0, 0.8, 400_000
    y = np.exp(mu + sigma * rng.normal(size=n))

    naive = np.exp(np.log(y).mean())
    smeared = naive * duan_smearing_factor(np.log(y) - np.log(y).mean())
    truth = y.mean()

    assert naive == pytest.approx(np.exp(mu), rel=0.02)          # geometric mean
    assert naive < 0.8 * truth                                    # materially biased low
    assert smeared == pytest.approx(truth, rel=0.02)              # corrected


def test_smearing_factor_is_one_when_residuals_vanish():
    from src.method.stage_a.reservation_depth_model import duan_smearing_factor

    assert duan_smearing_factor(np.zeros(100)) == pytest.approx(1.0)
    assert duan_smearing_factor(np.array([])) == 1.0


def test_stage_a_hard_check_raises_when_worse_than_the_forecast():
    """A6.3: must fail loudly. A warning in a 135-cell run is a line nobody reads."""
    from src.method.stage_a.reservation_depth_model import assert_stage_a_beats_forecast

    n = 200
    a_true = np.full(n, 1000.0)
    forecast = a_true + 10.0                       # 10 MW out
    censored = np.zeros(n, dtype=bool); censored[:50] = True

    good = a_true + 2.0
    rep = assert_stage_a_beats_forecast(good, forecast, a_true, censored)
    assert rep["passes"] and rep["mae_all"] < rep["mae_all_forecast"]

    bad = a_true + 50.0                            # worse than doing nothing
    with pytest.raises(AssertionError, match="WORSE than the raw day-ahead forecast"):
        assert_stage_a_beats_forecast(bad, forecast, a_true, censored)


def test_hour_fourier_features_are_named_and_finite():
    from src.method.stage_a.reservation_depth_model import hour_fourier_features

    hour = np.arange(960) % 24
    dates = np.repeat([f"2026-{m:02d}-15" for m in range(1, 13)], 80)
    feats = hour_fourier_features(hour, dates)
    assert len(feats) == 19                        # 3 season + 16 fourier x season
    assert all(np.isfinite(v).all() for v in feats.values())
    assert "intercept" not in feats                # the net carries its own bias


def test_smearing_is_off_by_default_because_it_worsens_mae():
    """Correct for a mean, wrong for an MAE-scored predictor. Pinned so it stays off.

    exp(OLS on logs) estimates the conditional MEDIAN, which is the MAE optimum for a
    right-skewed quantity. Smearing shifts it towards the MEAN and away from that
    optimum: measured 1,390.7 MW against 1,367.6 unsmeared on cell r10_g0.0_step_s42.
    """
    import inspect

    from src.method.stage_a.reservation_depth_model import fit_stage_a

    assert inspect.signature(fit_stage_a).parameters["smear"].default is False
