"""Identification diagnostics for the cohort exposure design (spec section 3, I4).

Why this module exists
----------------------
The pre-registered I4 / rule-18 check is `cohorts.exposure_differs_by_day`: count the
event-days on which at least one quarter-hour has two cohorts with different exposure,
and fall back to two cohorts below 10 days. That question is **not the one that matters**.
It asks whether cohorts differ *somewhere*; it is satisfied by a single differing pair and
cannot see that other pairs are identical. Both E1 generators pass it comfortably while
large capacity shares are exactly unidentified (docs/11).

The structural reason, which makes this predictable rather than empirical:

    s[k, t] = 1[ price_qh[t] < theta[k, t] ]

depends on the cohort **only through theta**. Two cohorts with the same theta trajectory
therefore have bit-identical exposure, for any price series whatsoever. Identification
comes from theta separation and from nothing else:

  * the gap between theta = 0 (support zeroed by section 51, or out of support) and
    theta = -MP (support intact);
  * the run-length thresholds, which decide when a cohort's theta flips from -MP to 0;
  * the spread of MP across cohorts, which comes from the award-value range.

Two diagnoses, kept separate
----------------------------
**Exact collinearity.** Identical `s` *and* identical `depth`. The two cohorts enter
`c = sum_k w_k s_k r*(depth_k)` only through `w_i r_i + w_j r_j`; the split is
unrecoverable from any amount of data. Merging them is the only honest response.

**Weak identification.** Identical `s` but *differing* `depth`. The exposure columns
coincide, so a model keyed on exposure alone cannot separate the cohorts, but a response
that is a function of depth can -- badly, in proportion to the depth contrast. This is a
precision problem, not an impossibility, and it is reported separately because the remedy
is different (report the contrast, widen it, or accept the variance).

Shape convention
----------------
`s`, `theta` and `depth` are (K, T) -- cohorts on axis 0 -- matching the output of
`cohorts.theta_and_exposure`, so these functions compose with the rest of the package
without transposing at every call site.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

__all__ = [
    "RankResult",
    "DuplicateGroup",
    "CohortCounts",
    "IdentificationReport",
    "exposure_rank",
    "condition_numbers",
    "duplicate_groups",
    "per_cohort_counts",
    "identification_diagnostics",
    "format_report",
]


# --------------------------------------------------------------------------- rank


@dataclass(frozen=True)
class RankResult:
    rank: int
    k: int
    tol: float
    singular_values: np.ndarray

    @property
    def full_rank(self) -> bool:
        return self.rank == self.k

    @property
    def deficiency(self) -> int:
        return self.k - self.rank


def _svd_tolerance(sv: np.ndarray, shape: tuple[int, int]) -> float:
    """Explicit rank tolerance, rather than relying on a library default.

    This is numpy's own rule (`largest singular value * max(dim) * eps`) written out so
    the number appears in the report and a future change to numpy cannot move the
    verdict silently. For a (K, T) binary matrix with T ~ 9e4 this sits around 1e-9,
    which is far below any singular value a genuinely distinct cohort produces (the
    smallest non-trivial value observed in the MaStR set is ~15) and far above the
    ~1e-13 numerical noise of an exactly duplicated row.
    """
    if sv.size == 0:
        return 0.0
    return float(sv[0] * max(shape) * np.finfo(float).eps)


def exposure_rank(s: np.ndarray, tol: float | None = None) -> RankResult:
    """Rank of the (K, T) exposure matrix by SVD, with an explicit tolerance."""
    s = np.asarray(s, dtype=float)
    if s.ndim != 2:
        raise ValueError(f"s must be 2-D (K, T); got shape {s.shape}")
    sv = np.linalg.svd(s, compute_uv=False)
    t = _svd_tolerance(sv, s.shape) if tol is None else float(tol)
    return RankResult(rank=int((sv > t).sum()), k=s.shape[0], tol=t,
                      singular_values=sv)


def condition_numbers(s: np.ndarray, w: Sequence[float] | None = None
                      ) -> tuple[float, float]:
    """(cond(s), cond(w * s)).

    The capacity-weighted form is the one that matters: `c` is built from
    `w_k * s_k`, so it is `w * s` a model actually has to invert to recover the
    per-cohort responses. A cohort with a tiny capacity share contributes a nearly
    zero row and is poorly identified even when `s` alone looks well conditioned --
    `pilot_exempt`, at 0.4% of capacity, is the live example.
    """
    s = np.asarray(s, dtype=float)

    def _cond(m: np.ndarray) -> float:
        sv = np.linalg.svd(m, compute_uv=False)
        if sv.size == 0 or sv[0] == 0.0:
            return float("inf")
        smallest = sv[-1]
        return float("inf") if smallest <= _svd_tolerance(sv, m.shape) else float(sv[0] / smallest)

    cond_s = _cond(s)
    if w is None:
        return cond_s, cond_s
    wv = np.asarray(w, dtype=float)
    if wv.size != s.shape[0]:
        raise ValueError(f"w has {wv.size} entries for {s.shape[0]} cohorts")
    return cond_s, _cond(wv[:, None] * s)


# ------------------------------------------------------------------- duplicates


def _row_key(row: np.ndarray) -> bytes:
    """Byte key for an exact row match, normalised so IEEE signed zero cannot split
    a genuine duplicate.

    `theta` is built as `-np.maximum(0.0, aw - ref)`, which yields **-0.0** wherever
    the premium is zero, while an out-of-support cohort's `np.zeros_like` yields
    **+0.0**. The two compare equal under `==` and `np.array_equal` but have
    different bit patterns, so a raw `tobytes()` key silently treats an exactly
    collinear pair as distinct. Adding 0.0 maps -0.0 to +0.0 and leaves every other
    value untouched. NaN is left alone: NaN rows are not duplicates of anything and
    must not be merged.
    """
    return (np.asarray(row, dtype=float) + 0.0).tobytes()


@dataclass(frozen=True)
class DuplicateGroup:
    """Cohorts whose exposure columns are bit-identical."""

    members: tuple[str, ...]
    indices: tuple[int, ...]
    capacity_share: float
    kind: str                      # "exact" | "weak"
    depth_mean_abs_diff: float     # 0.0 for "exact"
    depth_max_abs_diff: float

    @property
    def is_exact(self) -> bool:
        return self.kind == "exact"


def duplicate_groups(
    s: np.ndarray,
    cohort_ids: Sequence[str],
    w: Sequence[float] | None = None,
    depth: np.ndarray | None = None,
) -> list[DuplicateGroup]:
    """Group cohorts by identical exposure row, and diagnose each group.

    A group is "exact" when its members' `depth` rows are also identical (or when no
    depth is supplied, in which case exposure is all the information there is) and
    "weak" when the exposure coincides but the depth profiles differ.
    """
    s = np.asarray(s, dtype=float)
    ids = list(cohort_ids)
    if len(ids) != s.shape[0]:
        raise ValueError(f"cohort_ids has {len(ids)} entries for {s.shape[0]} cohorts")
    shares = (np.zeros(s.shape[0]) if w is None else np.asarray(w, dtype=float))

    by_pattern: dict[bytes, list[int]] = {}
    for i in range(s.shape[0]):
        by_pattern.setdefault(_row_key(s[i]), []).append(i)

    out: list[DuplicateGroup] = []
    for idx in by_pattern.values():
        if len(idx) < 2:
            continue
        mean_d = max_d = 0.0
        kind = "exact"
        if depth is not None:
            d = np.asarray(depth, dtype=float)
            on = s[idx[0]] > 0
            diffs = [np.abs(d[a] - d[b])[on] for a in idx for b in idx if a < b]
            if diffs:
                allv = np.concatenate(diffs) if on.any() else np.zeros(1)
                mean_d, max_d = float(allv.mean()), float(allv.max())
            if max_d > 0.0:
                kind = "weak"
        out.append(DuplicateGroup(
            members=tuple(ids[i] for i in idx),
            indices=tuple(idx),
            capacity_share=float(shares[list(idx)].sum()),
            kind=kind,
            depth_mean_abs_diff=mean_d,
            depth_max_abs_diff=max_d,
        ))
    return sorted(out, key=lambda g: -g.capacity_share)


# ----------------------------------------------------------------- per cohort


@dataclass(frozen=True)
class CohortCounts:
    cohort_id: str
    capacity_share: float
    n_exposed: int
    n_alone: int                 # exposed, every other cohort unexposed
    n_differs: int               # exposed, at least one other cohort unexposed
    n_others_differ: int         # NOT exposed while at least one other cohort is
    unique_column: bool          # no other cohort has an identical exposure row


def per_cohort_counts(
    s: np.ndarray,
    cohort_ids: Sequence[str],
    w: Sequence[float] | None = None,
) -> list[CohortCounts]:
    """Per-cohort identifying variation. Never pooled: a pooled count hides exactly
    the asymmetry that matters (docs/10 section 4.2, where 2,050 differing
    quarter-hours were 99.5% one direction)."""
    s = np.asarray(s, dtype=float)
    ids = list(cohort_ids)
    shares = (np.zeros(s.shape[0]) if w is None else np.asarray(w, dtype=float))
    any_unexposed = s.min(axis=0) == 0
    any_exposed = s.max(axis=0) > 0
    only_one = s.sum(axis=0) == 1
    out = []
    for i, cid in enumerate(ids):
        on = s[i] > 0
        dup = any(i != j and np.array_equal(s[i], s[j]) for j in range(s.shape[0]))
        out.append(CohortCounts(
            cohort_id=cid,
            capacity_share=float(shares[i]),
            n_exposed=int(on.sum()),
            n_alone=int((on & only_one).sum()),
            n_differs=int((on & any_unexposed).sum()),
            # The reverse direction. A cohort nested innermost (exposed only at the
            # deepest prices, where everyone else is exposed too) has n_differs = 0
            # yet is still identified -- through the quarter-hours where others fire
            # and it does not. Reporting only n_differs would call it unidentified.
            n_others_differ=int(((~on) & any_exposed).sum()),
            unique_column=not dup,
        ))
    return out


def pairwise_differs(s: np.ndarray) -> np.ndarray:
    """(K, K) counts: entry [i, j] is the number of quarter-hours where cohort i is
    exposed and cohort j is not. Asymmetric on purpose."""
    s = np.asarray(s, dtype=float)
    on = s > 0
    return (on.astype(int) @ (~on).astype(int).T)


# ------------------------------------------------------------------ the report


@dataclass(frozen=True)
class IdentificationReport:
    label: str
    n_qh: int
    exposure: RankResult
    depth_rank: RankResult | None
    combined_rank: RankResult | None
    cond_s: float
    cond_ws: float
    groups: list[DuplicateGroup]
    cohorts: list[CohortCounts]
    pairwise: np.ndarray = field(repr=False)

    @property
    def full_rank(self) -> bool:
        return self.exposure.full_rank

    @property
    def unique_columns(self) -> bool:
        return all(c.unique_column for c in self.cohorts)

    @property
    def collinear_capacity_share(self) -> float:
        return float(sum(g.capacity_share for g in self.groups if g.is_exact))

    @property
    def weak_capacity_share(self) -> float:
        return float(sum(g.capacity_share for g in self.groups if not g.is_exact))


def identification_diagnostics(
    s: np.ndarray,
    cohort_ids: Sequence[str],
    w: Sequence[float] | None = None,
    depth: np.ndarray | None = None,
    label: str = "",
    tol: float | None = None,
) -> IdentificationReport:
    """Everything the gate needs to judge whether K cohorts are identified."""
    s = np.asarray(s, dtype=float)
    cond_s, cond_ws = condition_numbers(s, w)
    d_rank = c_rank = None
    if depth is not None:
        d = np.asarray(depth, dtype=float)
        d_rank = exposure_rank(d, tol)
        # The full feature block: row k is cohort k's (s_k, depth_k) concatenated
        # along TIME, giving (K, 2T). Cohort k enters c only through this row, so
        # two cohorts are separable in principle iff their rows differ. Stacking
        # the features instead, as (2K, T), would inflate the rank with the
        # s-versus-depth contrast and say nothing about separability.
        c_rank = exposure_rank(np.hstack([s, d]), tol)
    return IdentificationReport(
        label=label,
        n_qh=int(s.shape[1]),
        exposure=exposure_rank(s, tol),
        depth_rank=d_rank,
        combined_rank=c_rank,
        cond_s=cond_s,
        cond_ws=cond_ws,
        groups=duplicate_groups(s, cohort_ids, w, depth),
        cohorts=per_cohort_counts(s, cohort_ids, w),
        pairwise=pairwise_differs(s),
    )


def format_report(rep: IdentificationReport) -> str:
    """Human-readable table. Numbers only -- no verdict; that is the gate's job."""
    L: list[str] = []
    a = L.append
    a(f"--- identification: {rep.label} ---")
    a(f"  quarter-hours {rep.n_qh:,}   cohorts K = {rep.exposure.k}")
    a(f"  rank(s) = {rep.exposure.rank} of {rep.exposure.k}"
      f"   (tol {rep.exposure.tol:.3e})"
      f"   {'FULL RANK' if rep.full_rank else f'DEFICIENT by {rep.exposure.deficiency}'}")
    a(f"  singular values of s      = "
      f"{np.array2string(rep.exposure.singular_values, precision=2, suppress_small=True)}")
    if rep.depth_rank is not None:
        comb = rep.combined_rank.rank
        a(f"  rank(depth) = {rep.depth_rank.rank} of {rep.depth_rank.k}"
          f"   rank([s | depth]) = {comb} of {rep.exposure.k}"
          f"   {'(depth breaks the tie)' if comb > rep.exposure.rank else '(depth does NOT break the tie)'}")
    a(f"  cond(s) = {rep.cond_s:.3g}      cond(w * s) = {rep.cond_ws:.3g}")
    a(f"  unique exposure columns: {rep.unique_columns}")
    if rep.groups:
        a(f"  duplicated exposure groups ({len(rep.groups)}):")
        for g in rep.groups:
            a(f"    [{g.kind.upper():<5}] {' == '.join(g.members)}"
              f"   capacity {100 * g.capacity_share:.1f}%")
            if not g.is_exact:
                a(f"            depth differs: mean |d| = {g.depth_mean_abs_diff:.3f}, "
                  f"max {g.depth_max_abs_diff:.3f} EUR/MWh -> weak, not impossible")
        a(f"  capacity in EXACTLY collinear groups: "
          f"{100 * rep.collinear_capacity_share:.1f}%")
        if rep.weak_capacity_share:
            a(f"  capacity in WEAKLY identified groups: "
              f"{100 * rep.weak_capacity_share:.1f}%")
    else:
        a("  duplicated exposure groups: none")
    a(f"  {'cohort':<32}{'share':>7}{'exposed':>9}{'alone':>8}{'differs':>9}"
      f"{'others':>8}{'unique':>8}")
    for c in rep.cohorts:
        a(f"  {c.cohort_id:<32}{c.capacity_share:>7.3f}{c.n_exposed:>9,}"
          f"{c.n_alone:>8,}{c.n_differs:>9,}{c.n_others_differ:>8,}"
          f"{str(c.unique_column):>8}")
    return "\n".join(L)


# ------------------------------------------------- cohorts keyed on theta, not law

@dataclass(frozen=True)
class MergeGroup:
    """One group of legal cohorts that share a theta trajectory."""

    merged_id: str
    members: tuple[str, ...]
    member_shares: tuple[float, ...]
    capacity_share: float
    dominant: str

    @property
    def is_merge(self) -> bool:
        return len(self.members) > 1


def theta_merge_map(
    theta: np.ndarray,
    cohort_ids: Sequence[str],
    w: Sequence[float],
) -> list[MergeGroup]:
    """Group cohorts by identical theta trajectory, largest group first.

    Keying on theta rather than on `s` is deliberate and slightly stronger: theta
    determines both `s` and `depth`, so identical theta means the two cohorts are
    indistinguishable in every feature a model can see, not merely in exposure.
    Identical `s` with differing depth is the weak case and is NOT merged here --
    it stays separate and is reported as weakly identified, because the depth
    contrast is real information and merging would throw it away.

    The map is data-dependent: theta depends on the award-value setting and on the
    price series, so a merge valid under one arm may not hold under another. Compute
    and report it per arm; never hard-code a pair.
    """
    th = np.asarray(theta, dtype=float)
    ids, shares = list(cohort_ids), np.asarray(w, dtype=float)
    if th.shape[0] != len(ids) or shares.size != len(ids):
        raise ValueError("theta, cohort_ids and w disagree on K")

    by_theta: dict[bytes, list[int]] = {}
    for i in range(th.shape[0]):
        by_theta.setdefault(_row_key(th[i]), []).append(i)

    groups: list[MergeGroup] = []
    for idx in by_theta.values():
        dom = int(idx[int(np.argmax(shares[idx]))])
        merged = (ids[dom] if len(idx) == 1
                  else "theta_" + "+".join(sorted(ids[i] for i in idx)))
        groups.append(MergeGroup(
            merged_id=merged,
            members=tuple(ids[i] for i in idx),
            member_shares=tuple(float(shares[i]) for i in idx),
            capacity_share=float(shares[list(idx)].sum()),
            dominant=ids[dom],
        ))
    return sorted(groups, key=lambda g: -g.capacity_share)


def feature_merge_map(
    s: np.ndarray,
    depth: np.ndarray,
    cohort_ids: Sequence[str],
    w: Sequence[float],
) -> list[MergeGroup]:
    """Group cohorts by identical REALISED (s, depth) block -- the correct key.

    Why not theta. Cohort k enters `c = sum_k w_k s_k r*(depth_k)` only through
    (s_k, depth_k), so two cohorts are indistinguishable **iff** that pair agrees at
    every quarter-hour. theta equality is *sufficient* but **not necessary**: theta
    may differ freely in quarter-hours where neither cohort is exposed, and that
    difference is invisible in the data. Both cases occur in the Phase-3 set on the
    real panel -- at the 'low', 'main' and 'stress' award settings the collinear pair
    has identical theta, while at 'high' its theta differs (only off the exposed
    set) and a theta-keyed merge misses it entirely.

    Formally, i and j are indistinguishable iff for all t
        1[p<theta_i] == 1[p<theta_j]   and   (theta_i - p) s = (theta_j - p) s,
    i.e. theta need only agree ON the exposed set.
    """
    s = np.asarray(s, dtype=float)
    d = np.asarray(depth, dtype=float)
    return theta_merge_map(np.hstack([s, d]), cohort_ids, w)


def merge_cohorts(cohorts, key: np.ndarray, theta: np.ndarray):
    """(merged CohortSet, merged theta, merge map), grouping on `key` rows.

    `key` is the matrix whose identical rows mean "indistinguishable": pass
    `np.hstack([s, depth])` for the correct criterion, or `theta` for the weaker
    sufficient one. `theta` is carried through so the merged set keeps a threshold
    trajectory for downstream use.

    Legal provenance is preserved: every merged cohort's `note` lists the legal
    cohorts and shares it absorbed, and the map is returned for the write-up. A
    group whose theta is identically zero is represented as out of support with no
    award value, which is what theta = 0 throughout actually means -- there is no
    premium left to lose, whether because support ended or because section 51
    zeroed it.
    """
    from src.censoring.cohorts import Cohort, CohortSet  # local: avoids a cycle

    cs = list(cohorts)
    ids = [c.cohort_id for c in cs]
    shares = [c.capacity_share for c in cs]
    by_id = {c.cohort_id: c for c in cs}
    groups = theta_merge_map(key, ids, shares)

    new_cohorts, rows = [], []
    for g in groups:
        dom = by_id[g.dominant]
        if not g.is_merge:
            new_cohorts.append(dom)
            rows.append(g)
            continue
        members = [by_id[m] for m in g.members]
        th_row = np.asarray(theta, dtype=float)[ids.index(g.dominant)] + 0.0
        zero_throughout = bool(np.all(th_row == 0.0))
        if zero_throughout:
            in_support, aw, s51 = False, None, False
        else:
            in_support = dom.in_support
            have = [(m.aw_eur_mwh, m.capacity_share) for m in members
                    if m.aw_eur_mwh is not None]
            aw = (sum(a * s for a, s in have) / sum(s for _, s in have)
                  if have else dom.aw_eur_mwh)
            s51 = dom.subject_to_s51
        note = ("merged on identical theta from: "
                + ", ".join(f"{m}({100 * s:.1f}% of fleet)"
                            for m, s in zip(g.members, g.member_shares))
                + f"; dominant {g.dominant}")
        new_cohorts.append(Cohort(
            cohort_id=g.merged_id,
            rule_id=dom.rule_id,
            clock=dom.clock,
            run_length_h=dom.run_length_h if s51 else None,
            subject_to_s51=s51,
            in_support=in_support,
            aw_eur_mwh=aw,
            capacity_share=g.capacity_share,
            macro=dom.macro,
            note=note,
        ))
        rows.append(g)

    keep = [ids.index(g.dominant) for g in groups]
    return CohortSet(new_cohorts), np.asarray(theta, dtype=float)[keep], rows


def format_merge_map(groups: Sequence[MergeGroup]) -> str:
    L = ["  merge map (keyed on identical theta):"]
    for g in groups:
        if g.is_merge:
            L.append(f"    MERGE -> {g.merged_id}   capacity {100*g.capacity_share:.1f}%")
            for m, s in zip(g.members, g.member_shares):
                L.append(f"              {m:<32} {100*s:>5.1f}%"
                         f"{'   (dominant)' if m == g.dominant else ''}")
        else:
            L.append(f"    keep  -> {g.merged_id:<34} {100*g.capacity_share:>5.1f}%")
    return "\n".join(L)


def merge_cohorts_by_theta(cohorts, theta: np.ndarray):
    """Merge on theta equality alone. SUFFICIENT but not necessary -- prefer
    `merge_cohorts(cohorts, np.hstack([s, depth]), theta)`. Kept because the
    theta map is worth reporting beside the feature map to show the gap."""
    return merge_cohorts(cohorts, np.asarray(theta, dtype=float), theta)


# ------------------------------------------------------- the proposed gate criterion

#: Minimum number of quarter-hours on which every cohort PAIR must differ. Inherited
#: deliberately from the pre-registered I4 figure of 10, moved from "event-days on
#: which SOME pair differs" to "quarter-hours on which EVERY pair differs" -- the same
#: number, applied where it bites.
MIN_PAIR_DIFFER_QH = 10

#: Backstop on cond(s). Justified empirically, not chosen to pass: perturbing the
#: largest-capacity pair of the merged Phase-3 design to differ on exactly n
#: quarter-hours gives cond(s) = inf (n=0), 138 (n=1), 98 (n=2), 62 (n=5), 44 (n=10),
#: 23 (n>=50), while the four real merged AW settings sit at 16.5-39.4. So 100 rejects
#: a design whose worst pair differs on 0 or 1 quarter-hours and accepts everything
#: from 2 upwards -- strictly weaker than MIN_PAIR_DIFFER_QH, which is why the pair
#: floor is the binding test and this is only a backstop against a collective
#: degeneracy that no single pair reveals.
MAX_COND_S = 100.0

#: cond(w * s) is REPORTED, never gated. The same perturbation leaves it essentially
#: flat (543.6 at n=1 against 602.2 for the untouched design, and it *falls* as
#: duplication worsens), so it does not detect near-collinearity at all. It is kept
#: because it is the quantity that scales recovery error for a small-capacity cohort,
#: which is a precision warning rather than an identification failure.


@dataclass(frozen=True)
class GateVerdict:
    passed: bool
    rank_ok: bool
    unique_ok: bool
    cond_ok: bool
    rank: int
    feature_rank: int
    k: int
    min_pair_differ: int
    worst_pair: tuple[str, str] | None
    cond_s: float
    cond_ws: float
    exposure_differs_days: int | None
    collinear_capacity_share: float
    reasons: tuple[str, ...]


def min_pair_differ(s: np.ndarray, cohort_ids: Sequence[str]
                    ) -> tuple[int, tuple[str, str] | None]:
    """Smallest number of quarter-hours on which any cohort pair differs, and the pair.

    This is the direct, sensitive measure of near-collinearity, and the one the old
    day-count criterion could not express: `exposure_differs_by_day` counts days on
    which *some* pair differs, which a single well-separated pair satisfies while
    every other pair is identical.
    """
    s = np.asarray(s, dtype=float)
    ids = list(cohort_ids)
    k = s.shape[0]
    if k < 2:
        return 0, None
    best, pair = None, None
    for i in range(k):
        for j in range(i + 1, k):
            n = int((s[i] != s[j]).sum())
            if best is None or n < best:
                best, pair = n, (ids[i], ids[j])
    return int(best), pair


def gate_identification_verdict(
    s: np.ndarray,
    cohort_ids: Sequence[str],
    w: Sequence[float],
    depth: np.ndarray | None = None,
    exposure_differs_days: int | None = None,
    min_pair_qh: int = MIN_PAIR_DIFFER_QH,
    max_cond_s: float = MAX_COND_S,
) -> GateVerdict:
    """The composite identification criterion proposed to replace the I4 day count.

    Three conditions, all required:
      1. full rank on the FEATURE BLOCK `[s | depth]` -- no two cohorts
         indistinguishable. `rank(s)` alone is too strict: a pair with identical `s`
         but differing `depth` is weakly identified, not unidentified, and would be
         failed by a rank test on `s`. Both ranks are reported; the verdict uses the
         feature block when depth is available and falls back to `s` when it is not.
      2. every cohort pair differs on at least `min_pair_qh` quarter-hours;
      3. `cond(s) <= max_cond_s`           -- backstop (see MAX_COND_S).

    `exposure_differs_by_day` is accepted and carried through as a REPORTED
    diagnostic so the old number stays visible beside the new verdict. It never
    affects `passed`.

    PROPOSED, not pre-registered. Spec v1.8 section 7 fixes the gate's criteria and
    `gate_verdict.py` sets none of its own; this must be pre-registered as a spec
    amendment before the week-6 gate is scored.
    """
    rep = identification_diagnostics(s, cohort_ids, w, depth, label="gate")
    n_pair, pair = min_pair_differ(s, cohort_ids)
    # The feature block is the matrix that decides separability; `s` alone fails a
    # weakly-identified pair that depth does distinguish.
    eff = rep.combined_rank if rep.combined_rank is not None else rep.exposure
    rank_ok = eff.rank == rep.exposure.k
    unique_ok = n_pair >= min_pair_qh
    cond_ok = rep.cond_s <= max_cond_s
    reasons: list[str] = []
    if not rank_ok:
        dup = "; ".join(" == ".join(g.members) for g in rep.groups if g.is_exact)
        reasons.append(
            f"rank([s | depth]) = {eff.rank} of {rep.exposure.k} "
            f"(rank(s) = {rep.exposure.rank}); exactly collinear: "
            f"{dup or 'unnamed'} carrying "
            f"{100 * rep.collinear_capacity_share:.1f}% of capacity")
    if not unique_ok:
        reasons.append(
            f"closest pair {pair[0]} / {pair[1]} differs on only {n_pair} "
            f"quarter-hours (floor {min_pair_qh})" if pair else
            f"min pair difference {n_pair} < {min_pair_qh}")
    if not cond_ok:
        reasons.append(f"cond(s) = {rep.cond_s:.1f} exceeds {max_cond_s:.0f}")
    return GateVerdict(
        passed=rank_ok and unique_ok and cond_ok,
        rank_ok=rank_ok, unique_ok=unique_ok, cond_ok=cond_ok,
        rank=rep.exposure.rank, feature_rank=eff.rank, k=rep.exposure.k,
        min_pair_differ=n_pair, worst_pair=pair,
        cond_s=rep.cond_s, cond_ws=rep.cond_ws,
        exposure_differs_days=exposure_differs_days,
        collinear_capacity_share=rep.collinear_capacity_share,
        reasons=tuple(reasons),
    )
