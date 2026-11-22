# Objective

**Objective.** Determine which conclusions about how German wind farms respond to negative
prices can be supported by public aggregated data, and how much bias in the available-power
estimate each conclusion can survive.

**Method.** Rule-structured, bias-robust partial identification, with the quality-assured
Online-Hochrechnung (H) as the estimate of available power (`docs/02_method.md`).

**Main research question.** To what extent can a rule-structured partial-identification
framework recover informative fleet-level and cohort-level wind curtailment responses from
aggregated data, and how does uncertainty in estimated available power affect the conclusions
that can be supported?

**Sub-questions, one per experiment:**

| experiment | sub-question | doc |
|---|---|---|
| available-power estimate (data) | how good, and how biased, is the best public estimate of available power? | `docs/03_available_power_estimate.md` |
| 1 — known-truth validation | where the truth is known, do the bounds contain it, and how does noise in the potential widen them? | `docs/04_exp1_known_truth_validation.md` |
| 2 — bias-robustness validation | what does a biased potential do to the bounds, and does the bias-robust set restore coverage within its budget? | `docs/05_exp2_bias_robustness_validation.md` |
| 3 — German application | on real data, which readings hold, and how much bias does each survive? | `docs/06_exp3_german_application.md` |
| 4 — learning available power | can a price-blind learned model estimate available power well enough at negative prices to bound the projection's bias? | `docs/12_learned_potential_preregistration.md`, `docs/12b_learned_potential_results.md` |

<!-- generated:exp4_subq_answer -->
**Answer to sub-question 4 (negative result).** Not with these public inputs. The best price-blind learned model's error on negative-price look-alike quarter-hours (σ 0.235) is far above the roughly 0.139 needed to pin its own bias within ±0.02, so the projection's bias at negative prices could not be bounded (S2 failed, `docs/12b_learned_potential_results.md`). In 50Hertz 25.7% of the negative-price quarter-hours have no clean look-alike at all.
<!-- /generated -->

The earlier analytical propositions (A1–A3) and the experiment-role table are archived in
`archive/docs/00_OBJECTIVE.md`.
