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
    fallback_identifiability,
    fallback_partition,
    macro_exposure,
    _row_key,
    condition_numbers,
    duplicate_groups,
    exposure_rank,
    MERGE_RULES,
    feature_merge_map,
    format_merge_map,
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

    merged, theta_m, gmap = merge_cohorts(cohorts, np.hstack([s, depth]), theta,
                                          rule="exposure")
    assert len(merged) < len(cohorts)
    assert float(np.sum(merged.shares)) == pytest.approx(1.0)   # CohortSet validates
    s_m = (price[None, :] < theta_m).astype(float)
    depth_m = np.maximum(0.0, theta_m - price[None, :]) * s_m
    after = identification_diagnostics(s_m, merged.ids, list(merged.shares), depth_m)
    assert after.collinear_capacity_share == pytest.approx(0.0)
    # no EXACT duplicate survives the merge; that is what merging guarantees
    assert not any(g.is_exact for g in after.groups)

    # legal provenance survives on the merged cohort
    notes = [c.note for c in merged
             if c.note.startswith("merged on identical realised (s, depth)")]
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
    merged, _, _ = merge_cohorts(cohorts, np.hstack([s, depth]), theta,
                                 rule="exposure")
    z = [c for c in merged if c.cohort_id.startswith("exposure_")][0]
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


# ------------------------------------------------- the fallback partition (docs/12 I)

def _two_cohort_set(macros):
    """A CohortSet with chosen macros, for partition tests."""
    from src.censoring.cohorts import MACRO_HOUR, MACRO_QH
    names = {MACRO_QH: "post_feb2025_qh", MACRO_HOUR: "pre2016_out_of_support"}
    out = []
    for i, mac in enumerate(macros):
        out.append(Cohort(
            cohort_id=f"c{i}", rule_id="R01",
            clock="quarterhour" if mac == MACRO_QH else "hour",
            run_length_h=None, subject_to_s51=False, in_support=False,
            aw_eur_mwh=None, capacity_share=1.0 / len(macros), macro=mac))
    return CohortSet(out)


def test_clock_partition_goes_degenerate_when_every_cohort_shares_a_macro():
    """The reason the fallback needs re-speccing: merging absorbs the only
    quarter-hour-clock cohort, every survivor carries the hour macro, and the
    "two-cohort" fallback has one group."""
    from src.censoring.cohorts import MACRO_HOUR

    cohorts = _two_cohort_set([MACRO_HOUR] * 3)
    s = np.array([[1, 1, 0], [1, 0, 0], [0, 1, 0]], dtype=float)
    part = fallback_partition(cohorts, mode="clock")
    diag = fallback_identifiability(s, list(cohorts.shares), part)
    assert part.m == 1
    assert not diag.identified          # rank == M, but M == 1 is not a fallback
    assert diag.rank == 1


def test_theta_zero_partition_separates_removable_from_intact_premium():
    from src.censoring.cohorts import MACRO_HOUR

    cohorts = _two_cohort_set([MACRO_HOUR] * 3)
    # cohort 0 reaches theta = 0 somewhere; 1 and 2 never do
    theta = np.array([[0.0, -5.0, -5.0],
                      [-20.0, -20.0, -20.0],
                      [-14.0, -14.0, -14.0]])
    part = fallback_partition(cohorts, theta, mode="theta_zero")
    assert part.m == 2
    assert part.labels == ("premium_removable", "premium_intact")
    assert part.members[0] == ("c0",)
    assert set(part.members[1]) == {"c1", "c2"}
    assert part.capacity[0] == pytest.approx(1 / 3)
    assert part.capacity[1] == pytest.approx(2 / 3)


def test_theta_zero_partition_normalises_signed_zero():
    """-0.0 is theta = 0: a cohort whose premium is exactly zero has it removable."""
    from src.censoring.cohorts import MACRO_HOUR

    cohorts = _two_cohort_set([MACRO_HOUR] * 2)
    theta = np.array([[-0.0, -0.0], [-9.0, -9.0]])
    part = fallback_partition(cohorts, theta, mode="theta_zero")
    assert part.members[0] == ("c0",)


def test_theta_regime_partition_splits_switching_from_always_and_never():
    from src.censoring.cohorts import MACRO_HOUR

    cohorts = _two_cohort_set([MACRO_HOUR] * 3)
    theta = np.array([[0.0, 0.0], [0.0, -7.0], [-7.0, -7.0]])
    part = fallback_partition(cohorts, theta, mode="theta_regime")
    assert part.m == 3
    assert part.labels == ("premium_gone", "premium_switching", "premium_intact")
    assert part.members == (("c0",), ("c1",), ("c2",))


def test_macro_exposure_is_capacity_weighted():
    """A macro-tied fit inverts the capacity-weighted sum, not the raw indicator."""
    from src.censoring.cohorts import MACRO_HOUR

    cohorts = _two_cohort_set([MACRO_HOUR] * 2)   # shares 0.5 / 0.5
    s = np.array([[1, 0], [1, 1]], dtype=float)
    theta = np.array([[0.0, -1.0], [-9.0, -9.0]])
    part = fallback_partition(cohorts, theta, mode="theta_zero")
    A = macro_exposure(s, list(cohorts.shares), part)
    assert A.shape == (2, 2)
    assert A[0].tolist() == [0.5, 0.0]
    assert A[1].tolist() == [0.5, 0.5]


def test_fallback_weakest_pair_is_chosen_by_magnitude_not_count():
    """Two profiles can differ at every quarter-hour by a trivial amount; counting
    differing quarter-hours would call that the strongest pair."""
    from src.censoring.cohorts import MACRO_HOUR

    cohorts = _two_cohort_set([MACRO_HOUR] * 3)
    # groups 0 and 1 differ everywhere but minutely; 0 and 2 differ in few places,
    # by a lot. The weakest link is the first pair.
    theta = np.array([[0.0, 0.0, 0.0],
                      [0.0, 0.0, -1.0],
                      [-5.0, -5.0, -5.0]])
    part = fallback_partition(cohorts, theta, mode="theta_regime")
    s = np.array([[1.0, 1.0, 1.0],
                  [1.0, 1.0, 0.999],
                  [0.0, 0.0, 1.0]])
    diag = fallback_identifiability(s, list(cohorts.shares), part)
    assert diag.mean_abs_contrast < 0.01     # the minute pair, not the big one


def test_fallback_partition_rejects_unknown_mode_and_missing_theta():
    from src.censoring.cohorts import MACRO_HOUR

    cohorts = _two_cohort_set([MACRO_HOUR] * 2)
    with pytest.raises(ValueError, match="not in"):
        fallback_partition(cohorts, mode="nonsense")
    with pytest.raises(ValueError, match="needs theta"):
        fallback_partition(cohorts, None, mode="theta_zero")


def test_everything_in_all_actually_exists():
    """__all__ went stale once already, when functions were appended without it."""
    import src.censoring.identification as mod
    missing = [n for n in mod.__all__ if not hasattr(mod, n)]
    assert missing == []


def test_theta_zero_is_degenerate_when_every_cohort_reaches_zero():
    """Why the default is theta_regime and not theta_zero.

    On real data MP = max(0, AW - MV) is zero in any month where the market value
    exceeds the award value, so every cohort's theta reaches 0 and "ever zero"
    partitions nothing. The benchmark hides this behind a flat placeholder market
    value. theta_regime still separates them, by ALWAYS zero against sometimes.
    """
    from src.censoring.cohorts import MACRO_HOUR
    from src.censoring.identification import DEFAULT_FALLBACK_MODE

    assert DEFAULT_FALLBACK_MODE == "theta_regime"

    cohorts = _two_cohort_set([MACRO_HOUR] * 3)
    # every cohort touches 0 somewhere; only the first is 0 throughout
    theta = np.array([[0.0, 0.0, 0.0],
                      [0.0, -6.0, -6.0],
                      [-3.0, 0.0, -3.0]])
    s = np.array([[1.0, 1.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])

    zero = fallback_partition(cohorts, theta, mode="theta_zero")
    assert zero.m == 1
    assert not fallback_identifiability(s, list(cohorts.shares), zero).identified

    regime = fallback_partition(cohorts, theta, mode="theta_regime")
    assert regime.m == 2                      # "never 0" is empty, as on real data
    assert regime.members[0] == ("c0",)
    assert set(regime.members[1]) == {"c1", "c2"}


def test_merge_map_labels_the_key_it_actually_used():
    """The bug: `feature_merge_map` delegated to `theta_merge_map`, so a merge keyed
    on the realised (s, depth) block was labelled "theta" in the merged id, in the
    cohort note and in the printed map -- a false method description, in every
    production call, headed for the write-up. The label is now built where the
    grouping happens, so it cannot disagree with the key.
    """
    price = np.array([-10.0, -10.0, 50.0, 50.0])
    # identical ON the exposed set, different off it: merged by exposure, not by theta
    theta = np.vstack([np.zeros(4), np.array([0.0, 0.0, -29.0, -29.0])])
    s = (price[None, :] < theta).astype(float)
    depth = np.maximum(0.0, theta - price[None, :]) * s

    feat = [g for g in feature_merge_map(s, depth, ["i", "j"], [0.6, 0.4])
            if g.is_merge]
    assert len(feat) == 1
    g = feat[0]
    assert g.rule == "exposure"
    assert g.rule_phrase == "identical realised (s, depth)"
    assert g.merged_id == "exposure_i+j"
    assert "theta" not in g.merged_id
    assert "identical theta" not in format_merge_map(feat)
    assert "identical realised (s, depth)" in format_merge_map(feat)

    # and the theta map, which really is theta-keyed, still says so
    same = np.vstack([np.zeros(4), np.zeros(4)])
    th = [g for g in theta_merge_map(same, ["i", "j"], [0.6, 0.4]) if g.is_merge]
    assert th and th[0].rule == "theta"
    assert th[0].merged_id == "theta_i+j"
    assert "identical theta" in format_merge_map(th)


def test_merge_cohorts_will_not_merge_without_being_told_the_rule():
    """`rule` is keyword-only and required: nothing can infer what `key` encodes, and
    guessing is what produced the mislabel."""
    cohorts = mastr_cohort_set("DE")
    theta = np.zeros((len(cohorts), 3))
    with pytest.raises(TypeError):
        merge_cohorts(cohorts, theta, theta)


def test_unknown_merge_rule_is_rejected():
    with pytest.raises(ValueError, match="unknown merge rule"):
        theta = np.zeros((2, 3))
        merge_cohorts(mastr_cohort_set("DE"), theta, theta, rule="vibes")


def test_every_merge_rule_token_has_a_phrase():
    """A token with no phrase would raise only at print time, after the run."""
    for token, phrase in MERGE_RULES.items():
        assert token and phrase
    # the one that matters: the exposure rule must not describe itself as theta
    assert "theta" not in MERGE_RULES["exposure"]
