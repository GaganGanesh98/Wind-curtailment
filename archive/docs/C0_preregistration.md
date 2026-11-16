# C0 — conclusions table: pre-registration of rows, columns and the verdict rule

**Written and committed 16 November 2026, before `src/build_conclusions_table.py` existed
and before any cell of the table was assembled.** Phase C runs no experiment and fits no
model. Every value in the table is read from an artifact that already exists.

**What "before" can and cannot mean here.** The inputs are not unseen. The Q1 and Q5
per-functional informative counts were already plotted in `figures/findings/F6` and `F7`
(Phase S5, 15–16 Nov 2026), and the results notes quote many of them. What this file fixes
in advance is the rule that turns those inputs into a verdict, so that the rule cannot be
chosen to fit the table it produces.

## 1. The objective the table serves (locked; not rephrased)

**Objective.** Develop and evaluate a rule-structured partial-identification framework that
uses aggregated wind generation data and estimated available power to determine which
fleet-level and cohort-level price-response quantities can be meaningfully identified, and how
their informativeness changes with uncertainty in the available-power estimate.

**Main research question.** To what extent can a rule-structured partial-identification
framework recover informative fleet-level and cohort-level wind curtailment responses from
aggregated data, and how does uncertainty in estimated available power affect the conclusions
that can be supported?

**Analytical propositions A1–A3** were formulated **after** the experiments, to organise them.
Each experiment kept its own pre-registered test; A1–A3 are not tests and nothing below
re-scores an experiment against them.
- A1 — Available-power uncertainty reduces identification precision. Evidence: P3, Arm D, Q1.
- A2 — Fleet-level quantities stay informative under uncertainty that makes cohort-level
  quantities uninformative. Evidence: Q1.
- A3 — A better available-power estimate does not necessarily make real-data cohort quantities
  informative. Evidence: Q0, Q0b, Q5.
- Q6a/Q6b are an exploratory diagnostic, not a fourth proposition.

## 2. Rows

Read from `docs/P0_preregistration.md` §7, `docs/P3_results.md` §0.6–0.7 and
`src/identification/run_p3_real.py`. All seven functionals were evaluated in P3, Q1 and Q5.

**Quantity rows (verdict by the rule in §4):**

| row | quantity | plain English |
|---|---|---|
| λ₁ | fleet response at depth band (−20, −5] €/MWh | what share of exposed fleet potential is switched off at moderately negative prices |
| λ₂ | fleet response at depth ≤ −50 €/MWh | the same at deeply negative prices |
| λ₃ | response of the pre-2016 cohort (`pre2016_in_support_no_s51`; synthetic analogue `wind2016_2020_6h`) | how one cohort of turbines responds |
| λ₄ | response of the merged θ ≡ 0 group (`out_of_support` + `post_feb2025_qh`) | how an exactly collinear pair of cohorts responds together |
| λ₅ | counterfactual curtailed energy, GWh, if `wind2023_feb2025_staircase`'s threshold moved to 0 | a policy what-if: how much more energy one cohort would hold back |
| λ₆ | λ₃ − λ₄ | whether two cohorts respond differently |
| λ₇ | response of `out_of_support` alone (synthetic `pre2016_out_of_support`) | one member of the collinear pair on its own |

**Evidence rows (one-line verdict quoted or closely paraphrased from the results note; the
rule in §4 does not apply):**

| row | question | source note |
|---|---|---|
| pooled | does a single common response fit, as Hirth assumes? | `docs/Q1_results.md` §4, `docs/P3_results.md` §2.3 |
| Q5 | does a better available-power estimate help? (F vs H) | `docs/Q5_results.md` §1 |
| Q0b | does the projection behave as if market curtailment is added back? | `docs/Q0b_results.md` §1 |
| Q6 | does the synthetic uncertainty model explain real data? | `docs/Q6_results.md` |

No expected row is missing. The pooled-response test was evaluated on synthetic data only, and
its real-data cells are marked "not evaluated".

## 3. Columns

All counts are written k/n. "not evaluated" means no artifact holds the value; "—" means the
column does not apply to that row.

| column | definition |
|---|---|
| question | plain English, from §2 |
| quantity | from §2 |
| evidence | experiments and artifact paths |
| synthetic, Anchor T | Q1, `artifacts/Q1/q1_summary_by_level.csv`, noise = iid, σ = 0.18 (the grid level for Anchor T, σ = 0.1806): `n_informative`/`n_cells` |
| synthetic, Anchor H | the same at σ = 0.066 |
| highest σ informative in ≥ half | the largest σ in the i.i.d. grid {0, 0.033, 0.066, 0.12, 0.18, 0.25, 0.35} with `n_informative` ≥ `n_cells`/2. "not reached at σ = 0" if no level qualifies; "≥ 0.35 (top of grid)" if 0.35 qualifies |
| real, forecast F | Q5, `artifacts/Q5/q5_real.csv`, setting = main, potential = F, `c_hat` not recalibrated, monthly rows (period ≠ window): informative k / defined n, plus undefined months u, written "k/n (u undefined)" |
| real, projection H | the same with potential = H |
| narrowest real interval | among the defined monthly rows with H (main, not recalibrated), the smallest `width`; written "[lo, hi] (YYYY-MM)"; ties go to the earliest month. λ₅ in GWh |
| full-window interval | the period = window row, main, H, not recalibrated, if defined; else "undefined" |
| verdict | §4 |
| depends on | one short line |

The informativeness flag is the one stored in the artifacts: width below 0.25 of the
logically maximal width (`docs/Q0_preregistration.md` §5; 1.0 for λ₁–λ₄ and λ₇, 2.0 for λ₆,
`l5_energy_full_gwh` for λ₅). No new threshold is introduced.

## 4. The verdict rule (quantity rows only), decided mechanically

With k and n the real-data counts under the projection H (§3):

1. **SUPPORTED RANGE** if n ≥ 1 and k ≥ n/2. The narrowest and full-window intervals are reported.
2. **NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE** otherwise, including n = 0
   (undefined in every month, noted in "depends on").
3. **Sub-label WOULD NEED A MORE ACCURATE ESTIMATE**, added only to category 2, when Q1 shows
   the quantity informative in ≥ half the synthetic cells at some tested σ **below** Anchor H
   (σ ∈ {0, 0.033}) **and not at Anchor H itself** (σ = 0.066). The level stated is the largest
   such σ, followed by "within the tested synthetic conditions".

**Interpretation declared for rule 3.** The brief's wording is "becomes informative … at some
tested noise level below Anchor H". Read literally without the "and not at Anchor H" clause,
it would also label quantities that are already informative at Anchor H's noise (and above),
for which Q1 says accuracy is not the binding constraint. "Becomes" and "would need a more
accurate estimate" are read as requiring that the quantity is *not* informative at Anchor H.
The results note lists every row whose label would differ under the literal reading.

## 5. What this does not do

It changes no experiment's verdict, threshold or artifact. Where a verdict from a results
note is quoted, it is not strengthened. Q1 statements are restricted to the tested grid. Q0b
is supporting evidence, not ground truth. TenneT is excluded from every projection aggregate
(T-D(vii), `docs/Q_STOP_Q0c.md`).
