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

The earlier analytical propositions (A1–A3) and the experiment-role table are archived in
`archive/docs/00_OBJECTIVE.md`.
