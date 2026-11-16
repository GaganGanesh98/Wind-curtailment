# What public German wind data can and cannot tell us about price-driven curtailment, Oct 2025 – Oct 2026

Built by `src/build_conclusions_table.py` from committed artifacts under the rule in `docs/C0_preregistration.md` (commit `a67f69a`). Machine-readable copy: `results/C1_conclusions_table.csv`. Nothing here was fitted for this table.

Real-data counts are monthly functional-months in the main award setting, 50Hertz + Amprion + TransnetBW, written informative/defined, with undefined months counted separately. Synthetic counts are Q1 cells informative out of all cells. Informative means interval width below a quarter of its logically maximal width (`docs/Q0_preregistration.md` §5).

## Quantities

| row | quantity | synthetic, Anchor T (σ 0.18) | synthetic, Anchor H (σ 0.066) | highest σ informative in ≥ half | real, forecast F | real, projection H | narrowest real interval, H | full window, H | verdict | depends on |
|---|---|---|---|---|---|---|---|---|---|---|
| λ₁ | fleet response at depth (−20, −5] €/MWh | 54/54 | 54/54 | ≥ 0.35 (top of grid) | 1/8 (2 undefined) | 2/8 (2 undefined) | [0.182, 0.330] (2025-10) | [0.300, 0.508], informative | **NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE** | Q1: already informative at Anchor H's σ in synthetic cells; real data falls short of that (Q6 explores why) |
| λ₂ | fleet response at depth ≤ −50 €/MWh | 54/54 | 54/54 | ≥ 0.35 (top of grid) | 0/3 (7 undefined) | 1/3 (7 undefined) | [0.597, 0.793] (2026-04) | [0.525, 0.860], not informative | **NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE** | Q1: already informative at Anchor H's σ in synthetic cells; real data falls short of that (Q6 explores why) |
| λ₃ | pre-2016 cohort response | 18/54 | 54/54 | 0.12 | 2/9 (1 undefined) | 0/9 (1 undefined) | [0.000, 0.269] (2026-02) | [0.000, 0.579], not informative | **NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE** | Q1: already informative at Anchor H's σ in synthetic cells; real data falls short of that (Q6 explores why) |
| λ₄ | merged θ ≡ 0 group response (collinear pair) | 18/54 | 24/54 | 0.033 | 1/10 | 0/10 | [0.184, 0.695] (2025-10) | [0.002, 0.996], not informative | **NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE**; WOULD NEED A MORE ACCURATE ESTIMATE: σ ≤ 0.033, within the tested synthetic conditions | an available-power estimate with σ ≤ 0.033 (Q1 synthetic cells) |
| λ₅ | counterfactual energy, GWh, staircase cohort's threshold moved to 0 | 18/54 | 24/54 | 0.033 | 0/10 | 0/10 | [0.0, 6.2] (2026-02) | [0.0, 533.2], not informative | **NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE**; WOULD NEED A MORE ACCURATE ESTIMATE: σ ≤ 0.033, within the tested synthetic conditions | an available-power estimate with σ ≤ 0.033 (Q1 synthetic cells) |
| λ₆ | cohort contrast λ₃ − λ₄ | 18/54 | 54/54 | 0.066 | 1/9 (1 undefined) | 0/9 (1 undefined) | [-0.569, 0.532] (2026-01) | [-0.967, 0.398], not informative | **NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE** | Q1: already informative at Anchor H's σ in synthetic cells; real data falls short of that (Q6 explores why) |
| λ₇ | one member of the collinear pair alone | 9/54 | 9/54 | not reached at σ = 0 | 1/10 | 0/10 | [0.000, 0.945] (2026-01) | [0.000, 1.000], not informative | **NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE** | collinear split: not informative in half the cells even with exact potential |

λ₅ intervals are in GWh; all others are response shares (λ₆ a difference of two).

## Evidence rows

| row | question | evidence | synthetic, Anchor T | synthetic, Anchor H | real, F | real, H | verdict (from the results note) | depends on |
|---|---|---|---|---|---|---|---|---|
| pooled | Does a single common response fit, as Hirth assumes? | Q1 (artifacts/Q1/q1_summary_by_level.csv, q1_headline.csv); P3 §2.3 | 0/27 | 0/27 | — | — | Synthetic only: 18 of 27 split cells reject pooling with an exact potential, none from Anchor H's σ on; the test keeps power above half only with an exact potential. Real data: not evaluated. | an exact potential; not evaluated on real data |
| Q5 | Does a better available-power estimate help? (F vs H) | Q5 (artifacts/Q5/q5_summary.csv) | — | — | 6/59 (11 undefined) | 3/59 (11 undefined) | 2 of 59 main-setting functional-months become informative when H replaces F; 5 go the other way. | H as the potential; one award setting shown (main) |
| Q0b | Does the projection behave as if market curtailment is added back? | Q0b (artifacts/Q0b/q0b_verdicts.csv) | — | — | — | — | ADDS BACK on the deciding aggregate (D = +0.2893, 95% CI [+0.2484, +0.3344]) and in every control area. Supporting evidence, not ground truth. | TenneT excluded (T-D(vii)); not every gap is voluntary curtailment |
| Q6 | Does the synthetic uncertainty model explain real data? | Q6 (artifacts/Q6/q6a_cells.csv, q6b_summary.csv) | — | — | — | — | Exploratory. Q6a: PRESENT in 8 of 8 testable cells. Q6b: NOT SUPPORTED. | exploratory diagnostic, not a proposition |
| Q2 | Do the bounds stay honest if the available-power estimate is biased? | Q2 (artifacts/Q2/q2_coverage_by_level.csv); added after C0, see note | 162/378 | 126/378 | — | — | Coverage falls below 95% at every non-zero bias level tested, at every noise level; intervals stay narrow and miss the truth. Synthetic only. | an unbiased potential; H's bias at negative prices is not measured |

For the Q2 row the synthetic columns count cell-functionals that cover the known truth at Anchor T's bias (+0.033) and Anchor H's bias (−0.047), σ = 0. The Q2 row was added on 16 November 2026, after C0, at the student's instruction; C0 fixed four evidence rows. It carries no verdict under the C0 rule and changes no other row.

For the pooled row the synthetic columns count split cells that reject a single common response (the most of any functional), not informative cells.

## What the verdicts mean

**SUPPORTED RANGE** (0 of 7 quantities). The quantity is informative in at least half of its defined real-data months with the projection as the potential. The reported interval is what the data supports; it is a range, not a point estimate.

**NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE** (7 of 7). With the best public estimate of available power, the quantity is informative in fewer than half of its defined months. The interval can still be reported, but it does not separate "most of the exposed fleet switches off" from "little of it does".

**WOULD NEED A MORE ACCURATE ESTIMATE** (2 of 7, a sub-label of the previous category). In Q1's synthetic cells the quantity is informative in at least half the cells at a noise level below Anchor H's, and not at Anchor H's. The stated level is the largest such σ on the tested grid, within the tested synthetic conditions only.

Under the literal reading of C0 §4 rule 3 (without "and not at Anchor H"), λ₁, λ₂, λ₃, λ₆ would also carry the sub-label. They are informative in synthetic cells at Anchor H's σ, so the table does not say they need a more accurate estimate.

---

## Full-window reading (descriptive, not part of the C0 verdict)

Added 16 November 2026 at the student's instruction, after C0. It changes no verdict above. Each row is the single interval for the whole window (2025-10 to 2026-10, main setting, projection H), not the monthly arms the verdict counts. **Reading rule, fixed here and applied to every row:** a response share lies in [0, 1] (λ₆ in [−1, 1]; λ₅ in [0, its logical maximum] GWh); a bound is read one-sided when it excludes at least a quarter of that range at its own end, the same quarter the informativeness rule uses.

| row | full-window interval, H | width | logical maximum width | reading |
|---|---|---|---|---|
| λ₁ | [0.300, 0.508] | 0.208 | 1.000 | informative: between 0.300 and 0.508 |
| λ₂ | [0.525, 0.860] | 0.335 | 1.000 | one-sided: at least 0.525 |
| λ₃ | [0.000, 0.579] | 0.579 | 1.000 | one-sided: at most 0.579 |
| λ₄ | [0.002, 0.996] | 0.995 | 1.000 | no reading: neither bound excludes a quarter of the range |
| λ₅ | [0.0, 533.2] | 533.2 | 533.2 | no reading: neither bound excludes a quarter of the range |
| λ₆ | [-0.967, 0.398] | 1.365 | 2.000 | one-sided: at most 0.398 |
| λ₇ | [0.000, 1.000] | 1.000 | 1.000 | no reading: neither bound excludes a quarter of the range |

**Every reading assumes the projection H is unbiased during negative prices.** Q2 shows that a biased potential gives intervals that stay narrow and miss the truth, and H's bias at negative prices has not been measured (`docs/Q2_results.md` §5). These are readings of the bounds as computed, not supported ranges.

---

## Bias breakdown points (Phase V, descriptive, not part of the C0 verdict)

Added 16 November 2026 at the student's instruction, after C0; it changes no verdict. Each full-window reading above is recomputed with a bias-robust interval: the hull of the identified sets over every constant multiplicative bias |b| ≤ B in the projection, on a 0.01 grid (`docs/V0_preregistration.md`). The **breakdown point** is the smallest B at which the reading no longer holds. On synthetic cells this construction covers the truth whenever B ≥ |true bias| (324 of 324 at every such level, `docs/V_results.md` V1).

| row | reading | breaks when | breakdown B | interval at B = 0 | interval at B = 0.15 |
|---|---|---|---|---|---|
| λ₁ | informative | width ≥ 0.25 | 0.04 | [0.300, 0.508] | [0.187, 0.574] |
| λ₂ | lower bound at least 0.5 | lower bound < 0.5 | 0.06 | [0.525, 0.860] | [0.449, 0.876] |
| λ₃ | upper bound at most 0.75 | upper bound > 0.75 | > 0.15 | [0.000, 0.579] | [0.000, 0.658] |
| λ₆ | upper bound at most 0.5 | upper bound > 0.5 | 0.04 | [-0.967, 0.398] | [-1.000, 0.654] |

For scale only: the projection's measured bias on price ≥ 0 quarter-hours is −0.0472 (`docs/Q0_preregistration.md` §1), larger than the budget at which λ₁ and λ₆ break. Its bias during negative prices is not measured. Figure: `figures/findings/F10_bias_breakdown.png`.

---

## Limitations

> - **Synthetic vs real.** Q1 and P3 cells have a known truth and an i.i.d. or AR(1) noise model; real data has neither. A synthetic count says what the method can do under those conditions, not what real data will give.
> - **The projection is not ground truth.** Q0b shows the quality-assured Online-Hochrechnung behaves as if market curtailment is added back. That is supporting evidence; not every projected-minus-observed difference is voluntary curtailment, and Anchor H's σ is a lower bound on its error.
> - **TenneT is excluded** from every projection aggregate (supervisor minute T-D(vii), `docs/Q_STOP_Q0c.md`). Real-data rows cover 50Hertz + Amprion + TransnetBW only.
> - **Q1 holds on its tested grid only** (σ = 0, 0.033, 0.066, 0.12, 0.18, 0.25, 0.35). There is no universal threshold; "≥ 0.35" is a lower bound, not a value.
> - **The propositions A1–A3 were formulated after the experiments**, to organise them. Each experiment kept its own pre-registered test (`docs/00_OBJECTIVE.md`).
