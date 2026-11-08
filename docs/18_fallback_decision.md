# 18 — Fallback structure and drop trigger: student decision

**Decision date: 9 November 2026.**

**I am recording this decision before the merged-cohort gate has been scored. No gate
result from the merged (K = 6) design has been seen. The E1 merged grid was running when
this was written, at 22 of 81 cells, and `gate_verdict.py` has not been run against it.**

This is the written decision required by the spec v1.8 minute, "No further gate changes
without the student's written decision". It supersedes the v1.3 fallback in spec 06 §3 I4.

---

## 0. Why the existing fallback cannot be used

Spec v1.3 §3 I4 specifies collapsing to two cohorts, "QH clock vs hourly clock". That
partition rests on the assumption that the clock selects *which price a cohort compares
against*. It does not. The clock selects the branch of θ; the comparison is always against
the quarter-hour price (`docs/06:266`, `docs/06:302`, and `cohorts.py theta_and_exposure`).

Measured consequence: on the merged design the clock partition yields **M = 1** —
`post_feb2025_qh` is absorbed into a merged cohort whose θ is 0 at every quarter-hour, so no
clock is ever consulted. A one-group fallback is not a fallback. The v1.3 branch cannot be
executed as written.

## 1. DECISION A — two tiers, not three

**Adopted: Tier 1 (full merged cohorts, per-cohort r_k) and Tier 3 (single pooled r,
exposure still computed per cohort). Tier 2 is omitted.**

| | structure |
|---|---|
| **Tier 1** | K = 6 merged cohorts, per-cohort response `r_k` |
| **Tier 3** | one shared monotone response `r`, exposure `s_k` still per legal cohort, aggregated by capacity share |

Rationale: the ablation evidence shows pooling the response costs little, while removing
exposure structure costs a great deal.

| | response error |
|---|---|
| M1, full cohorts | 0.0581 |
| A3, one cohort | 0.0616 |
| A2b, no exposure structure | 0.1183 |

Pooling the response costs about 6%; removing exposure structure roughly doubles the error.
The structure that earns its place is the exposure indicator `s`, not the cohort index `k`.
An intermediate tier between these two would be machinery with no demonstrated benefit.

**Evidential limitation, stated deliberately.** These figures come from a **single arm of
three cells** (`results/12_hetero_r.csv`: logistic shape only, γ ∈ {0, 0.5, 1}, one seed,
on the unmerged 8-cohort design). They are not a robust finding and are not presented as
one.

A second consideration points the same way. The figures above were measured on the
semi-synthetic benchmark, where `mv_eur_mwh = 45.0` is a flat placeholder below every award
value, so every in-support cohort carries a positive premium and θ separation is guaranteed.
That is the most favourable possible case for cohort structure. On real data, where θ
separation is weak or absent in most months, the gap between Tier 1 and Tier 3 should be
smaller, not larger. The benchmark therefore **overstates** Tier 1's advantage.

**Consequence accepted.** Tier 3 cannot answer the "and r_k" clause of RQ2 on real data. If
Tier 1 fails the drop trigger, RQ2's cohort-heterogeneity component is answered on the
benchmark only, and the real-data claim becomes structural rather than
cohort-heterogeneous. This is accepted in advance rather than discovered later.

## 2. DECISION B — the drop trigger

**Gates (a tier is abandoned for the next if any fails):**

1. **Full rank on the cohort feature block `[s | depth]`** over the evaluation window.
2. **No cohort pair differing on fewer than 10 quarter-hours.** This floor inherits the
   pre-registered threshold of 10 from spec §3 I4.

**Reported, never gated:**

3. `cond(s)` — the condition number of the exposure matrix.
4. `cond(w·s)` — reported with the explicit note that it is **nearly blind** to
   near-collinearity: 543.6 with one differing quarter-hour against 602.2 untouched, and it
   *falls* as duplication worsens. It must not be read as a sensitivity measure.
5. `exposure_differs_by_day` — the former I4 criterion, demoted to a diagnostic. It cannot
   detect rank deficiency, because one differing pair satisfies it however many others are
   identical.

**Why no condition-number threshold.** A value such as `cond(s) ≤ 100` was derived
empirically on 8 November, after the data were seen. Adopting it as a gate would be
choosing a threshold from the data it will judge. It is therefore reported and not gated.

### Stated limitation of this trigger

The adopted gates test **exact** linear dependence (rank) and **pairwise** near-duplication
(the 10-quarter-hour floor). They do **not** test joint near-dependence among three or more
cohorts — a design in which no single pair is close, but one cohort's exposure is nearly a
combination of two others, would pass both gates while being badly identified.

`cond(s)` is the statistic that would detect this, and it is reported for exactly that
reason, but it is not gated because no threshold for it was pre-registered before the data
were seen. This blind spot is recorded here rather than left implicit.

## 3. Cohort merging

Cohorts are merged on the **realised `(s, depth)` block**, not on θ. θ equality is
sufficient but not necessary: θ need only agree on the exposed set, and may differ freely
where neither cohort is exposed. Measured: at the `high` award setting a θ-keyed merge finds
zero groups while the realised-block key finds one. Legal cohort labels are retained as
metadata on each merged cohort so rule provenance survives into the write-up.

## 4. What this does not change

No criterion, seed, λ grid, bins grid or threshold of the M2 pre-registration
(`docs/09_m2_preregistration.md`) is altered by this decision. The T-B / T-D(i) / T-E
decision chain in Amendment 3 §0.4 stands unchanged.

---

Gagan Ganesh
9 November 2026
