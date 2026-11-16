# Objective

Locked 16 November 2026 (Phase C). The table that answers it is
[`docs/C1_conclusions_table.md`](C1_conclusions_table.md), built under the rule in
[`docs/C0_preregistration.md`](C0_preregistration.md).

**Objective.** Develop and evaluate a rule-structured partial-identification framework that
uses aggregated wind generation data and estimated available power to determine which
fleet-level and cohort-level price-response quantities can be meaningfully identified, and how
their informativeness changes with uncertainty in the available-power estimate.

**Main research question.** To what extent can a rule-structured partial-identification
framework recover informative fleet-level and cohort-level wind curtailment responses from
aggregated data, and how does uncertainty in estimated available power affect the conclusions
that can be supported?

## Analytical propositions

**A1–A3 were formulated after the experiments, to organise them.** Each experiment kept its
own pre-registered test; the propositions are not tests and re-score nothing. They are named
A1–A3 so they cannot be confused with the experiments P1–P3.

| proposition | evidence |
|---|---|
| A1 — Available-power uncertainty reduces identification precision. | P3, Arm D, Q1 |
| A2 — Fleet-level quantities stay informative under uncertainty that makes cohort-level quantities uninformative. | Q1 |
| A3 — A better available-power estimate does not necessarily make real-data cohort quantities informative. | Q0, Q0b, Q5 |

Q6a and Q6b are an exploratory diagnostic, not a fourth proposition.

## Experiment roles

| role | experiments |
|---|---|
| motivation | kill test |
| method validation | P3, V (bias-robust bounds) |
| controlled uncertainty | Arm D, Q1, Q2 |
| empirical evaluation | Q0, Q0b, Q5 |
| exploratory diagnostic | Q6a, Q6b |
| supporting / appendix | E1, T-B and its λ sensitivity, P0, Q0c, R1 |

Reading limits, stated once: the kill test shows a forecast-versus-generation discrepancy at
negative prices, not a causal measure of voluntary curtailment. Arm D shows that replacing
true with estimated available power widens the bounds while coverage holds. Q0b is supporting
evidence that the Online-Hochrechnung adds back market curtailment, not ground truth. Q1
results hold on its tested grid only.
