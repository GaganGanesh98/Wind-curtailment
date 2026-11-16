"""Unit tests for the EEG rule logic in `src/censoring/cohorts.py`.

Every test uses a hand-built price sequence so the expected answer can be read off
the statute rather than off the code.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from src.method.exposure import (
    HOUR_CLOCK,
    MACRO_HOUR,
    MACRO_QH,
    QH_CLOCK,
    Cohort,
    CohortSet,
    build_clock_features,
    curtailed_share,
    exposure_differs_by_day,
    macro_exposed_share,
    placeholder_cohort_set,
    staircase_run_length,
    theta_and_exposure,
    trigger_active,
)

STEP_NS = 15 * 60 * 1_000_000_000


def ts_from(start: datetime, n: int) -> np.ndarray:
    """n consecutive quarter-hour UTC timestamps in nanoseconds."""
    t0 = int(start.replace(tzinfo=timezone.utc).timestamp()) * 1_000_000_000
    return t0 + STEP_NS * np.arange(n, dtype=np.int64)


def hourly(values: list[float]) -> np.ndarray:
    """Expand a list of hourly prices into four identical quarter-hour prices each."""
    return np.repeat(np.array(values, dtype=float), 4)


def make_cohort(**kw) -> Cohort:
    base = dict(
        cohort_id="c",
        rule_id="R02",
        clock=HOUR_CLOCK,
        run_length_h=6,
        subject_to_s51=True,
        in_support=True,
        aw_eur_mwh=60.0,
        capacity_share=1.0,
        macro=MACRO_HOUR,
    )
    base.update(kw)
    return Cohort(**base)


# ------------------------------------------------------------------ the two clocks


def test_hourly_mean_and_qh_clock_disagree_within_one_hour():
    """An hour that averages positive but contains a negative quarter-hour.

    This is the identifying variation of spec section 3, I4. The quarter-hour cohort
    is triggered; no hour-clock cohort is, because the hourly contract price -- the
    arithmetic mean of the four quarter-hour prices, section 100(45) EEG 2023 -- is
    positive.
    """
    # Mean of (-40, 20, 20, 20) = +5 EUR/MWh.
    prices = np.array([-40.0, 20.0, 20.0, 20.0])
    clock = build_clock_features(ts_from(datetime(2026, 6, 1, 0, 0), 4), prices)

    assert clock.hour_mean_price[0] == pytest.approx(5.0)
    assert not (clock.hour_mean_price < 0).any()
    assert clock.hour_run_length.max() == 0

    qh = make_cohort(cohort_id="qh", rule_id="R09", clock=QH_CLOCK, run_length_h=None,
                     macro=MACRO_QH)
    hour = make_cohort(cohort_id="hour", run_length_h=1)

    assert trigger_active(qh, clock).tolist() == [True, False, False, False]
    assert trigger_active(hour, clock).tolist() == [False] * 4


def test_quarter_hour_negative_inside_negative_hour_triggers_both():
    """Sanity counterpart: when the hour really is negative, both clocks fire."""
    prices = hourly([-10.0])
    clock = build_clock_features(ts_from(datetime(2026, 6, 1, 0, 0), 4), prices)
    qh = make_cohort(cohort_id="qh", rule_id="R09", clock=QH_CLOCK, run_length_h=None,
                     macro=MACRO_QH)
    hour = make_cohort(cohort_id="hour", run_length_h=1)
    assert trigger_active(qh, clock).all()
    assert trigger_active(hour, clock).all()


# ------------------------------------------------------------------- run lengths


@pytest.mark.parametrize(
    "rule_id,need,n_negative_hours,expected",
    [
        ("R02", 6, 5, False),   # section 24(1) EEG 2014 / section 51 EEG 2017: six hours
        ("R02", 6, 6, True),
        ("R02", 6, 7, True),
        ("R04", 4, 3, False),   # section 51(1) EEG 2021
        ("R04", 4, 4, True),
        ("R07", 2, 1, False),   # section 51(1) no. 3 EEG 2023, calendar year 2026
        ("R07", 2, 2, True),
    ],
)
def test_run_length_thresholds(rule_id, need, n_negative_hours, expected):
    prices = hourly([-10.0] * n_negative_hours + [50.0] * 3)
    clock = build_clock_features(
        ts_from(datetime(2026, 6, 1, 0, 0), len(prices)), prices
    )
    cohort = make_cohort(rule_id=rule_id, run_length_h=need)
    active = trigger_active(cohort, clock)
    assert bool(active[:4 * n_negative_hours].any()) is expected
    # The positive hours after the run are never triggered.
    assert not active[4 * n_negative_hours:].any()


def test_whole_uninterrupted_period_is_triggered_not_only_the_excess_hours():
    """"...fuer die gesamte Dauer des ununterbrochenen negativen Zeitraums".

    A six-hour run under a six-hour rule zeroes all six hours, including the first
    five, not just the hour at which the threshold was reached.
    """
    prices = hourly([30.0] + [-5.0] * 6 + [30.0])
    clock = build_clock_features(ts_from(datetime(2026, 6, 1, 0, 0), len(prices)), prices)
    active = trigger_active(make_cohort(run_length_h=6), clock)
    assert active[4:28].all()          # all six negative hours
    assert not active[:4].any()        # the positive hour before
    assert not active[28:].any()       # and after


def test_a_gap_breaks_the_run():
    """Two three-hour runs separated by a positive hour do not make a six-hour run."""
    prices = hourly([-5.0] * 3 + [10.0] + [-5.0] * 3)
    clock = build_clock_features(ts_from(datetime(2026, 6, 1, 0, 0), len(prices)), prices)
    assert not trigger_active(make_cohort(run_length_h=6), clock).any()
    assert trigger_active(make_cohort(run_length_h=3), clock).any()


# -------------------------------------------------------------------- the staircase


def test_staircase_steps_by_calendar_year_not_commissioning_year():
    """Section 51(1) nos. 1-4 EEG 2023: the year qualifies the price condition.

    The same cohort -- one commissioning window -- sees a different threshold in
    each calendar year. A three-hour run triggers in 2024 and 2026 but not 2023.
    """
    assert staircase_run_length(2023) == 4
    assert staircase_run_length(2024) == 3
    assert staircase_run_length(2025) == 3
    assert staircase_run_length(2026) == 2
    assert staircase_run_length(2030) == 1

    cohort = make_cohort(rule_id="R07", run_length_h="staircase")
    prices = hourly([-5.0] * 3 + [20.0])
    for year, expected in [(2023, False), (2024, True), (2025, True), (2026, True)]:
        clock = build_clock_features(
            ts_from(datetime(year, 6, 1, 0, 0), len(prices)), prices
        )
        assert bool(trigger_active(cohort, clock).any()) is expected, year


def test_staircase_year_is_berlin_local_not_utc():
    """31 Dec 23:00 Berlin is 22:00 UTC on 31 Dec; 1 Jan 00:00 Berlin is 23:00 UTC.

    The step happens at Berlin midnight, so the hour beginning 23:00 UTC on
    31 Dec 2025 is already in calendar year 2026 and gets the 2 h threshold, while
    the hour before it is still 2025 and needs 3 h.
    """
    # One two-hour negative run straddling Berlin midnight: the first negative hour is
    # 23:00 Berlin on 31 Dec 2025, the second is 00:00 Berlin on 1 Jan 2026.
    prices = hourly([20.0, -5.0, -5.0, 20.0])
    start = datetime(2025, 12, 31, 21, 0)  # 22:00 Berlin
    clock = build_clock_features(ts_from(start, len(prices)), prices)

    years = clock.berlin_year.reshape(-1, 4)[:, 0]
    assert years.tolist() == [2025, 2025, 2026, 2026]

    cohort = make_cohort(rule_id="R07", run_length_h="staircase")
    active = trigger_active(cohort, clock).reshape(-1, 4)[:, 0]
    # The run has length 2. The 2025 half needs 3 h and is not reduced; the 2026 half
    # needs 2 h and is. One physical run, split by the calendar-year clock -- which is
    # only visible if the year is Berlin-local. On UTC both hours would be 2025.
    assert active.tolist() == [False, False, True, False]


def test_unknown_staircase_year_raises_rather_than_guessing():
    with pytest.raises(ValueError, match="No staircase step recorded"):
        staircase_run_length(2022)


# ---------------------------------------------------------- exemptions and theta


def test_size_exempt_cohort_never_has_theta_forced_to_zero():
    """A cohort below its size threshold keeps the market premium as its threshold.

    Rule: "a cohort below its threshold never triggers, so theta stays at the
    market-premium value rather than dropping to 0". Here AW 60, MV 45, so the
    premium is 15 and the cohort only stops below -15 EUR/MWh -- never at -5.
    """
    prices = hourly([-5.0] * 8)  # long enough to trigger any run-length rule
    clock = build_clock_features(ts_from(datetime(2026, 6, 1, 0, 0), len(prices)), prices)

    exempt = make_cohort(cohort_id="small", rule_id="R10", subject_to_s51=False,
                         run_length_h=None)
    cs = CohortSet([exempt])
    theta, s, depth = theta_and_exposure(cs, clock, mv_eur_mwh=45.0)

    assert np.all(theta == -15.0)
    assert not s.any()           # -5 is not below -15
    assert not depth.any()

    # The same cohort, not exempt, would be zeroed for the whole run and exposed.
    cs2 = CohortSet([make_cohort(cohort_id="big", rule_id="R02", run_length_h=6)])
    theta2, s2, _ = theta_and_exposure(cs2, clock, mv_eur_mwh=45.0)
    assert np.all(theta2 == 0.0)
    assert s2.all()


def test_pilot_wind_is_exempt_before_feb_2025_and_not_after():
    """R12: exempt in every version before 25 Feb 2025, none after.

    Modelled as two cohorts because the exemption disappears with the rule version,
    which is selected by commissioning date (section 100(46)).
    """
    prices = hourly([-5.0] * 8)
    clock = build_clock_features(ts_from(datetime(2026, 6, 1, 0, 0), len(prices)), prices)
    pilot_old = make_cohort(cohort_id="pilot_pre2025", rule_id="R12",
                            subject_to_s51=False, run_length_h=None)
    pilot_new = make_cohort(cohort_id="pilot_post2025", rule_id="R09", clock=QH_CLOCK,
                            run_length_h=None, macro=MACRO_QH)
    assert not trigger_active(pilot_old, clock).any()
    assert trigger_active(pilot_new, clock).all()


def test_out_of_support_cohort_has_theta_zero_regardless():
    """No premium left to lose, so the plant stops whenever the price is below zero."""
    prices = hourly([-1.0, 1.0])
    clock = build_clock_features(ts_from(datetime(2026, 6, 1, 0, 0), 8), prices)
    cs = CohortSet([make_cohort(cohort_id="old", rule_id="R01", in_support=False,
                                aw_eur_mwh=None, subject_to_s51=False,
                                run_length_h=None)])
    theta, s, _ = theta_and_exposure(cs, clock, mv_eur_mwh=45.0)
    assert np.all(theta == 0.0)
    assert s[0, :4].all() and not s[0, 4:].any()


def test_market_premium_threshold_is_negative_premium():
    """theta = -max(0, AW - MV): exposed only below the premium, not at any negative price."""
    prices = np.array([-10.0, -20.0, -14.0, -16.0])
    clock = build_clock_features(ts_from(datetime(2026, 6, 1, 0, 0), 4), prices)
    # Hour mean is -15, a single negative hour; a 6 h rule does not trigger.
    cs = CohortSet([make_cohort(cohort_id="mp", rule_id="R02", run_length_h=6,
                                aw_eur_mwh=60.0)])
    theta, s, depth = theta_and_exposure(cs, clock, mv_eur_mwh=45.0)
    assert np.all(theta == -15.0)
    assert s[0].tolist() == [0.0, 1.0, 0.0, 1.0]
    assert depth[0].tolist() == [0.0, 5.0, 0.0, 1.0]


def test_premium_floors_at_zero_when_market_value_exceeds_award():
    cs = CohortSet([make_cohort(cohort_id="mp", aw_eur_mwh=40.0)])
    prices = hourly([5.0])
    clock = build_clock_features(ts_from(datetime(2026, 6, 1, 0, 0), 4), prices)
    theta, _, _ = theta_and_exposure(cs, clock, mv_eur_mwh=45.0)
    assert np.all(theta == 0.0)


# ------------------------------------------------------------ two-cohort collapse


def test_two_cohort_mode_matches_k_cohort_when_r_is_shared():
    """Rule 18: the collapse pools the response, not the exposure.

    With one response per macro-cohort, c_t computed from the K legal cohorts is
    identical to c_t computed with the macro-cohort's parameters applied to each of
    its legal cohorts -- because exposure and depth stay per legal cohort. This is
    what makes the fallback a switch rather than a rewrite.
    """
    rng = np.random.default_rng(42)
    n_hours = 48
    prices = hourly(rng.normal(0.0, 30.0, size=n_hours).tolist())
    clock = build_clock_features(ts_from(datetime(2026, 6, 1, 0, 0), len(prices)), prices)
    cs = placeholder_cohort_set()
    _, s, depth = theta_and_exposure(cs, clock, mv_eur_mwh=45.0)

    macro_idx = cs.macro_index()
    # One response curve per macro-cohort, evaluated at each legal cohort's own depth.
    def r_macro(m: int, d: np.ndarray) -> np.ndarray:
        a, b = (-1.0, 0.05) if m == 0 else (-0.5, 0.03)
        return 1.0 / (1.0 + np.exp(-(a + b * d)))

    r_k = np.stack([r_macro(macro_idx[i], depth[i]) for i in range(len(cs))])
    c_k = curtailed_share(cs.shares, s, r_k)

    # "Two-cohort mode": the same tied parameters, written out per macro-cohort.
    c_two = np.zeros_like(c_k)
    for m in (0, 1):
        members = np.flatnonzero(macro_idx == m)
        for i in members:
            c_two += cs.shares[i] * s[i] * r_macro(m, depth[i])
    c_two = np.clip(c_two, 0.0, 1.0)

    np.testing.assert_allclose(c_k, c_two, atol=1e-12)


def test_macro_exposed_share_sums_to_total_exposed_capacity():
    prices = hourly([-5.0] * 8)
    clock = build_clock_features(ts_from(datetime(2026, 6, 1, 0, 0), len(prices)), prices)
    cs = placeholder_cohort_set()
    _, s, _ = theta_and_exposure(cs, clock, mv_eur_mwh=45.0)
    shares = macro_exposed_share(cs, s)
    total = shares[MACRO_QH] + shares[MACRO_HOUR]
    np.testing.assert_allclose(total, (cs.shares[:, None] * s).sum(axis=0), atol=1e-12)


def test_exposure_differs_by_day_counts_days_not_quarter_hours():
    s = np.array(
        [
            [1.0, 1.0, 0.0, 0.0],
            [1.0, 0.0, 0.0, 0.0],
        ]
    )
    dates = ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-02"]
    count, mask = exposure_differs_by_day(s, dates)
    assert count == 1
    assert mask.tolist() == [True, False]


# ------------------------------------------------------------------- housekeeping


def test_unknown_rule_id_raises_instead_of_being_dropped():
    """Hard rule 12, learned from the `TenneT DE` bug: never silently drop a category."""
    with pytest.raises(ValueError, match="Unknown rule_id"):
        CohortSet([make_cohort(rule_id="R99")])


def test_capacity_shares_must_sum_to_one():
    with pytest.raises(ValueError, match="Capacity shares sum to"):
        CohortSet([make_cohort(cohort_id="a", capacity_share=0.4)])


def test_cohort_in_support_without_award_value_raises():
    with pytest.raises(ValueError, match="needs an award value"):
        make_cohort(in_support=True, aw_eur_mwh=None)


def test_non_contiguous_price_series_raises():
    ts = ts_from(datetime(2026, 6, 1, 0, 0), 8)
    ts = np.delete(ts, 3)
    with pytest.raises(ValueError, match="not contiguous"):
        build_clock_features(ts, np.zeros(7))


def test_partial_calendar_hour_raises():
    with pytest.raises(ValueError, match="do not have 4 quarter-hours"):
        build_clock_features(ts_from(datetime(2026, 6, 1, 0, 0), 6), np.zeros(6))


def test_placeholder_cohort_set_spans_both_clocks_and_all_thresholds():
    cs = placeholder_cohort_set()
    assert len(cs) == 5
    assert {c.macro for c in cs} == {MACRO_QH, MACRO_HOUR}
    hour_rules = {c.run_length_h for c in cs if c.clock == HOUR_CLOCK}
    assert hour_rules == {None, 6, 4, "staircase"}
    assert np.isclose(cs.shares.sum(), 1.0)
