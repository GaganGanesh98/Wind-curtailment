"""Unit tests for `src/censoring/identification.py` and the gate's reported counts.

Each test pins a bug that was actually hit while building this module (docs/12), so
a regression here is a regression to a known-wrong state rather than a hypothetical.
Every matrix is hand-built so the expected answer can be read off the construction.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.censoring.cohorts import Cohort, CohortSet, mastr_cohort_set
from src.censoring.identification import (
    MIN_PAIR_DIFFER_QH,
    _row_key,
    condition_numbers,
    duplicate_groups,
    exposure_rank,
    feature_merge_map,
    gate_identification_verdict,
    identification_diagnostics,
    merge_cohorts,
    min_pair_differ,
    per_cohort_counts,
    theta_merge_map,
)


# ----------------------------------------------------- the signed-zero row key

def test_row_key_treats_negative_zero_as_zero():
    """IEEE -0.0 must not split an exactly duplicated row.

    theta is built as `-np.maximum(0.0, aw - ref)`, which yields -0.0 wherever the
    premium is zero, while an out-of-support cohort's `np.zeros_like` yields +0.0.
    They compare equal under `==` and `np.array_equal` but have different bit
    patterns, so a raw `tobytes()` key silently treated an exactly collinear pair as
    distinct and merged nothing.
    """
    pos = np.array([0.0, 0.0, 1.0])
    neg = np.array([-0.0, -0.0, 1.0])
    assert np.array_equal(pos, neg)              # numerically identical
    assert pos.tobytes() != neg.tobytes()        # but not bitwise
    assert _row_key(pos) == _row_key(neg)        # the key must not care


def test_theta_merge_map_groups_across_signed_zero():
    theta = np.array([[0.0, 0.0], [-0.0, -0.0], [-7.0, 0.0]])
    groups = theta_merge_map(theta, ["a", "b", "c"], [0.4, 0.3, 0.3])
    merged = [g for g in groups if g.is_merge]
    assert len(merged) == 1
    assert set(merged[0].members) == {"a", "b"}
    assert merged[0].capacity_share == pytest.approx(0.7)


def test_row_key_keeps_nan_rows_apart():
    """NaN is not a duplicate of anything and must never be merged."""
    a = np.array([np.nan, 1.0])
    assert _row_key(a) == _row_key(a.copy())     # a row matches itself
    groups = theta_merge_map(np.array([[np.nan, 1.0], [0.0, 1.0]]),
                             ["a", "b"], [0.5, 0.5])
    assert not any(g.is_merge for g in groups)


# -------------------------------------------------------------- rank and duplicates

def test_rank_detects_an_exactly_collinear_pair():
    s = np.array([[1, 1, 0, 0], [1, 1, 0, 0], [1, 0, 0, 0]], dtype=float)
    r = exposure_rank(s)
    assert (r.rank, r.k) == (2, 3)
    assert not r.full_rank
    assert r.deficiency == 1
    assert r.tol > 0                              # the tolerance is explicit


def test_exact_versus_weak_diagnosis_turns_on_depth():
    """Identical s with identical depth is unrecoverable; with differing depth it is
    merely weakly identified, and the two must not be reported as the same thing."""
    s = np.array([[1, 1, 0], [1, 1, 0]], dtype=float)
    same = np.array([[5.0, 5.0, 0.0], [5.0, 5.0, 0.0]])
    diff = np.array([[5.0, 5.0, 0.0], [9.0, 9.0, 0.0]])

    g_exact = duplicate_groups(s, ["a", "b"], [0.5, 0.5], same)
    assert len(g_exact) == 1 and g_exact[0].is_exact
    assert g_exact[0].depth_max_abs_diff == pytest.approx(0.0)

    g_weak = duplicate_groups(s, ["a", "b"], [0.5, 0.5], diff)
    assert len(g_weak) == 1 and not g_weak[0].is_exact
    assert g_weak[0].kind == "weak"
    assert g_weak[0].depth_max_abs_diff == pytest.approx(4.0)


def test_combined_block_is_per_cohort_not_per_feature():
    """rank([s | depth]) must be taken on (K, 2T) -- cohort rows concatenated along
    time. Stacking as (2K, T) inflates the rank with the s-versus-depth contrast and
    would report that depth breaks a tie when the depths are identical."""
    s = np.array([[1, 1, 0], [1, 1, 0]], dtype=float)
    same = np.array([[5.0, 5.0, 0.0], [5.0, 5.0, 0.0]])
    rep = identification_diagnostics(s, ["a", "b"], [0.5, 0.5], same)
    assert rep.exposure.rank == 1
    assert rep.combined_rank.rank == 1            # depth does NOT break the tie

    diff = np.array([[5.0, 5.0, 0.0], [9.0, 9.0, 0.0]])
    rep2 = identification_diagnostics(s, ["a", "b"], [0.5, 0.5], diff)
    assert rep2.combined_rank.rank == 2           # depth DOES break it


def test_condition_number_is_infinite_only_when_rank_deficient():
    collinear = np.array([[1, 1, 0], [1, 1, 0]], dtype=float)
    assert condition_numbers(collinear, [0.5, 0.5])[0] == np.inf
    distinct = np.array([[1, 1, 0], [1, 0, 0]], dtype=float)
    cond_s, cond_ws = condition_numbers(distinct, [0.5, 0.5])
    assert np.isfinite(cond_s) and np.isfinite(cond_ws)


# -------------------------------------------------------------- per-cohort counts

def test_nested_cohort_has_no_exposed_alone_but_is_still_unique():
    """A cohort exposed only where every other cohort is exposed too has
    n_differs = 0 yet is NOT unidentified: its column is unique and the identifying
    variation sits in the reverse direction, which n_others_differ reports."""
    s = np.array([[1, 1, 1], [1, 0, 0]], dtype=float)   # b nested inside a
    counts = {c.cohort_id: c for c in per_cohort_counts(s, ["a", "b"], [0.6, 0.4])}
    b = counts["b"]
    assert b.n_alone == 0
    assert b.n_differs == 0            # never exposed while another is not
    assert b.n_others_differ == 2      # but a fires twice where b does not
    assert b.unique_column


def test_min_pair_differ_finds_the_closest_pair():
    s = np.array([[1, 1, 1, 0], [1, 1, 1, 0], [1, 0, 0, 0]], dtype=float)
    n, pair = min_pair_differ(s, ["a", "b", "c"])
    assert n == 0
    assert set(pair) == {"a", "b"}


# ------------------------------------------------------------- the merge criterion

def test_feature_key_catches_a_pair_whose_theta_differs_off_the_exposed_set():
    """theta equality is SUFFICIENT but not NECESSARY.

    Two cohorts can be indistinguishable while their thetas differ, provided they
    differ only where neither is exposed. This is the real Phase-3 situation at the
    'high' award setting, where a theta-keyed merge finds nothing.
    """
    price = np.array([-10.0, -10.0, 50.0, 50.0])
    theta_i = np.array([0.0, 0.0, 0.0, 0.0])
    theta_j = np.array([0.0, 0.0, -29.0, -29.0])      # differs only where p >= 0
    theta = np.vstack([theta_i, theta_j])
    s = (price[None, :] < theta).astype(float)
    depth = np.maximum(0.0, theta - price[None, :]) * s

    assert np.array_equal(s[0], s[1])                 # exposure coincides
    assert np.array_equal(depth[0], depth[1])         # so does depth
    assert not np.array_equal(theta_i, theta_j)       # theta does not

    assert not any(g.is_merge for g in theta_merge_map(theta, ["i", "j"], [0.5, 0.5]))
    feat = feature_merge_map(s, depth, ["i", "j"], [0.5, 0.5])
    assert sum(1 for g in feat if g.is_merge) == 1


def test_merge_restores_full_rank_and_preserves_capacity():
    cohorts = mastr_cohort_set("DE")
    price = np.array([-30.0, -3.0, 10.0, 60.0, -80.0])
    # theta: two cohorts pinned at 0, the rest at distinct premiums
    theta = np.vstack([
        np.zeros_like(price) if c.cohort_id in
        ("out_of_support", "post_feb2025_qh")
        else np.full_like(price, -(10.0 + 3 * i))
        for i, c in enumerate(cohorts)
    ])
    s = (price[None, :] < theta).astype(float)
    depth = np.maximum(0.0, theta - price[None, :]) * s

    before = identification_diagnostics(s, cohorts.ids, list(cohorts.shares), depth)
    assert not before.full_rank
    assert before.collinear_capacity_share > 0.0

    merged, theta_m, gmap = merge_cohorts(cohorts, np.hstack([s, depth]), theta)
    assert len(merged) < len(cohorts)
    assert float(np.sum(merged.shares)) == pytest.approx(1.0)   # CohortSet validates
    s_m = (price[None, :] < theta_m).astype(float)
    depth_m = np.maximum(0.0, theta_m - price[None, :]) * s_m
    after = identification_diagnostics(s_m, merged.ids, list(merged.shares), depth_m)
    assert after.collinear_capacity_share == pytest.approx(0.0)
    # no EXACT duplicate survives the merge; that is what merging guarantees
    assert not any(g.is_exact for g in after.groups)

    # legal provenance survives on the merged cohort
    notes = [c.note for c in merged if c.note.startswith("merged on identical theta")]
    assert notes and "out_of_support" in notes[0]


def test_merged_group_at_theta_zero_is_marked_out_of_support():
    """theta = 0 throughout means there is no premium left to lose, so the merged
    cohort must not claim an award value it cannot act on."""
    cohorts = mastr_cohort_set("DE")
    price = np.array([-30.0, 10.0])
    theta = np.vstack([
        np.zeros_like(price) if c.cohort_id in
        ("out_of_support", "post_feb2025_qh")
        else np.full_like(price, -20.0 - i) for i, c in enumerate(cohorts)
    ])
    s = (price[None, :] < theta).astype(float)
    depth = np.maximum(0.0, theta - price[None, :]) * s
    merged, _, _ = merge_cohorts(cohorts, np.hstack([s, depth]), theta)
    z = [c for c in merged if c.cohort_id.startswith("theta_")][0]
    assert z.in_support is False
    assert z.aw_eur_mwh is None
    assert z.subject_to_s51 is False


# ------------------------------------------------------------------ the gate verdict

def test_gate_verdict_fails_on_an_exactly_collinear_pair():
    s = np.array([[1, 1, 0, 0], [1, 1, 0, 0], [1, 0, 0, 0]], dtype=float)
    v = gate_identification_verdict(s, ["a", "b", "c"], [0.5, 0.3, 0.2],
                                    exposure_differs_days=999)
    assert not v.passed
    assert not v.rank_ok and not v.unique_ok and not v.cond_ok
    assert v.min_pair_differ == 0
    assert len(v.reasons) == 3
    # the old criterion is carried through, and never changes the verdict
    assert v.exposure_differs_days == 999


def test_gate_verdict_pair_floor_binds_before_the_condition_number():
    """A design whose worst pair differs on fewer than the floor must FAIL even
    though it is full rank -- the pair floor is the binding test, not cond(s)."""
    rng = np.random.default_rng(0)
    base = (rng.random((4, 4000)) < 0.3).astype(float)
    base[1] = base[0]
    flip = rng.choice(4000, size=MIN_PAIR_DIFFER_QH - 1, replace=False)
    base[1, flip] = 1.0 - base[1, flip]           # differs on floor-1 quarter-hours
    v = gate_identification_verdict(base, list("abcd"), [0.25] * 4)
    assert v.rank_ok                              # full rank ...
    assert not v.unique_ok                        # ... but too close
    assert not v.passed
    assert v.min_pair_differ == MIN_PAIR_DIFFER_QH - 1


# ------------------------------------------- the gate's reported counts (docs/12 H)

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


def test_weak_duplicates_leave_rank_s_deficient_but_are_still_identified():
    """The reason the gate criterion keys on [s | depth] and not on s alone.

    Two cohorts with identical exposure but different depth profiles are weakly
    identified -- separable through the depth contrast -- yet rank(s) cannot see
    that and reports a deficiency. A rank test on s would fail a design that is
    actually identified, so the verdict uses the feature block.
    """
    s = np.array([[1, 1, 0], [1, 1, 0], [1, 0, 0]], dtype=float)
    depth = np.array([[5.0, 5.0, 0.0], [9.0, 9.0, 0.0], [2.0, 0.0, 0.0]])

    rep = identification_diagnostics(s, ["a", "b", "c"], [0.4, 0.4, 0.2], depth)
    assert rep.exposure.rank == 2                     # s alone is deficient
    assert rep.combined_rank.rank == 3                # the feature block is not
    assert rep.collinear_capacity_share == pytest.approx(0.0)   # nothing EXACT
    assert rep.weak_capacity_share == pytest.approx(0.8)

    v = gate_identification_verdict(s, ["a", "b", "c"], [0.4, 0.4, 0.2], depth)
    assert v.rank_ok                                  # not failed for weakness
    assert v.feature_rank == 3 and v.rank == 2
    # it still fails, but on the pair floor -- the binding test -- not on rank
    assert not v.unique_ok
    assert all("rank(" not in r for r in v.reasons)
