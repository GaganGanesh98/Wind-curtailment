# 10 — M2 verdict

**Status: OPEN. No verdict has been reached.** Every figure below marked
`[PENDING]` is a placeholder and must not be quoted, cited or carried into the
proposal or the thesis until the run that produces it has finished and this
document records its file and row.

Created 2 November 2026, while T-B PASS 1 was running. The structure is fixed now,
before the numbers exist, so that the verdict is written into a shape that was not
chosen to fit it.

---

## 1. The binding rule

Reproduced verbatim from `docs/09_m2_preregistration.md` Amendment 3 section 0.4.
It is frozen. Nothing in this document may reinterpret it.

> Decision mapping (binding; reproduce in the final report):
> - **T-B FAIL** -> STOP. Data-efficiency claim withdrawn. Do not run T-E.
>   Recommendation to student: end this topic.
> - **T-B PASS, T-D(i) placebo FAIL** -> STOP before T-E; stage A is not trustworthy on
>   real data.
> - **T-B PASS, T-D(i) PASS, T-E PASS** -> CONTINUE: this is the thesis.
> - **T-B PASS, T-D(i) PASS, T-E TIE/FAIL** -> SUPERVISOR DECISION; synthetic
>   contribution stands, real-data payoff weak.
>
> T-A, T-C and T-D(ii)-(v) inform the write-up and never change the decision.

And the T-B pass rule itself, from section 0.3:

> PASS = M2 lower than B3-CV in >= threshold of 45 cells on logistic AND step, AND M2
> not significantly worse than B3-CV on half, AND M2 lower than B6 in >= threshold of 45
> cells on logistic AND step.

The half clause names **B3-CV alone**. B6-on-half is reported and does not gate
(`run_tb.overall`, corrected 1 November 2026).

---

## 2. Inputs to the decision

| Test | Role | Runner | Output | State |
|---|---|---|---|---|
| T-B primary, n=50 | **DECIDES** | `run_tb.py --pass primary` | `results/21_tb_primary.csv` | running, `[PENDING]` |
| T-D(i) placebo | **DECIDES** (if T-B passes) | not written | — | `[PENDING]` |
| T-E / Test 2 | **DECIDES** (if T-B and T-D(i) pass) | not written | — | must not run before T-B |
| T-B sensitivity, n=50 | reports | `run_tb_sensitivity.py` | `results/25_tb_sensitivity.csv` | `[PENDING]` |
| T-B secondary, n∈{20,100,all} | reports | `run_tb.py --pass secondary` | `results/22_tb_secondary.csv` | `[PENDING]` |
| T-A main grid | reports | not written | — | `[PENDING]` |
| T-C robustness | reports | not written | — | blocked, see §5 |
| T-D(ii)–(vii) | reports | partly written | `results/26_td_iii_identification.csv` | (iii) done |

---

## 3. T-B verdict — `[PENDING]`

To be completed from the **complete** 945-row `results/21_tb_primary.csv` by
`run_tb.py --report-only`, never from a partial file. A partial read was made on
2 November for a plumbing check and is disclosed in `docs/06`; it is not
interpretable, because cells are generated with the censoring rate as the outer
loop and a partial file is a systematically incomplete stratum rather than a
random subsample.

| shape | rival | M2 mean | rival mean | wins | n_eff | threshold | p | verdict |
|---|---|---|---|---|---|---|---|---|
| logistic | B3-CV | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` |
| logistic | B6 | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` |
| step | B3-CV | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` |
| step | B6 | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` |
| half | B3-CV *(gates)* | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` |
| half | B6 *(reported)* | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` | `[PENDING]` |

**T-B VERDICT: `[PENDING]`**

### Component attribution (reports, decides nothing)

M2-noPool and M2-noAtom against B3-CV, per Amendment 3 section 0.3.
Pre-registered prediction, recorded in `docs/06` before the result: at n=20 pooling
should carry almost all of the gain, and M2-noPool should do badly. If M2-noPool
instead does well at n=20, the λ cross-validation is not behaving as intended and
the result must be investigated before it is believed.

`[PENDING]`

### Sensitivity arm (reports, decides nothing)

Whether the verdict differs on `y − offset_hat`. The pre-registered verdict stands
on the unadjusted `y` regardless of what this shows.

`[PENDING]`

---

## 4. T-D — real-data structural checks

### (iii) Identification — **done, 2 November 2026**

Source: `results/26_td_iii_identification.csv`, DE, published monthly market value
(T1, ex post), panel 2024-01-01 to 2026-09-30, 33 months, 8 cohorts.

Cohort-level responses are separable only where cohorts face **different** thresholds
and prices actually fall far enough to cross more than one of them. Where every
premium is zero, every θ collapses to 0, the design has rank ≤ 2 and only one fleet
response is recoverable.

- **Identified in 15 of 33 months.**
- Identification holds for monthly market value in **[48.00, 68.22] EUR/MWh** and
  fails for every exposed month at **≥ 68.24 EUR/MWh**.
- Award values in the cohort specification: {59, 62, 66, 71, 74} EUR/MWh.
- Three months (2025-02, 2025-11, 2025-12) have **no exposed quarter-hours at all**.

> **[VERIFY] — two open points on this result.**
> 1. An earlier figure of **18 of 33** months is in the project record. This run gives
>    **15 of 33**. The definitions, date range, area or award values may differ. Neither
>    number may be quoted until the difference is traced. The rule used here is recorded
>    in the CSV's `identified_rule` column.
> 2. The clean split at ~68.2 EUR/MWh is **not** simply "market value below the highest
>    award value". At MV = 68.24 two cohorts still carry a non-zero premium, yet the month
>    is not identified — because the realised prices never fell below those thresholds.
>    The condition is therefore joint: differentiated thresholds **and** a price process
>    that reaches them. This is the sharper statement and it is the one worth proving.

### (i) Cross-fitted placebo — **`[PENDING]`, and it gates T-E**

Derived `c_hat` on held-out price > 5 quarter-hours. Pass if the CI contains 0 and
|mean| < 1 pp. Runner not written.

### (ii), (iv), (v), (vi), (vii) — `[PENDING]`

(iv) is blocked on the award-value variants; (vi) and (vii) on the
Online-Hochrechnung gap. See §5.

---

## 5. Blockers that are not code

Recorded here so they are not mistaken for work merely undone.

1. **Award-value low / high / stress do not exist.** `MASTR_COHORT_SPEC` carries one
   `aw` per cohort {59, 62, 66, 71, 74}. T-C(i) and T-D(iv) both require fitting at
   low, main and high award values, and `docs/06` describes the main setting as the
   round's volume-weighted award times a site-correction factor of 1.226, with low and
   high ends from that factor's distribution. **These values must come from the tender
   data; they cannot be chosen.** Until they are supplied, T-C(i) and T-D(iv) cannot
   run, and the runner must refuse rather than default.
2. **Online-Hochrechnung March–August 2026 is not downloaded.** T-D(vi) validates stage
   A against it; the current export covers 2026-09 to 2026-10 only.
3. **TenneT's positive-price baseline ratio of 0.839 is undiagnosed.** T-D(vii) is a
   *precondition*, not a diagnostic: no DE-level aggregate may use that series until it
   is explained.
4. **T-E must not run before T-B's verdict.** Section 0.4: T-B FAIL → "Do not run T-E."
   Writing the runner is permitted; executing it is not.

---

## 6. Decision — `[PENDING]`

To be written only once sections 3 and 4(i) are complete, by applying section 1
verbatim. The recommendation that follows is whichever branch of section 1 the
results select, with no discretion.

**Decision: `[PENDING]`**
