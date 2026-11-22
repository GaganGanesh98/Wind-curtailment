# Redispatch sensitivity: results

Pre-registration `docs/11_redispatch_sensitivity_preregistration.md` (commit `56f81a6`). The run
started from commit `87286bf` and wrote only `artifacts/exp3_german_application/redispatch_sensitivity_cells.csv`.
Every union below is formed per B from the unrounded lo and hi in that file and in the headline
V2 cells (`src/experiments/exp3_redispatch_sensitivity.py`; summary in
`artifacts/exp3_german_application/redispatch_sensitivity_summary.csv`). ĉ = 1 − G/H throughout;
the arms only drop quarter-hours.

## Samples

<!-- generated:rd_samples -->
| arm | quarter-hours | negative-price quarter-hours | share of negative-price quarter-hours removed | event days | λ₂ band: quarter-hours / event days |
|---|---|---|---|---|---|
| headline | 34,937 | 2,052 | — | 97 | 149 / 12 |
| M0 | 26,141 | 746 | 64% | 51 | 41 / 5 |
| M1 | 26,979 | 947 | 54% | 57 | 60 / 6 |
<!-- /generated -->

Both arms keep at least 20 event days, so both are interpreted under the pre-registered rule.

## Decision rule, against the headline

<!-- generated:rd_rule -->
| reading | arm | interval at B = 0 | holds at B = 0 | breakdown B | change against headline | sensitive |
|---|---|---|---|---|---|---|
| λ₁ informative (width < 0.25) | headline | [0.3001, 0.5079] | yes | 0.04 | — | — |
| λ₂ ≥ 0.50 | headline | [0.5254, 0.8600] (12 event days) | yes | 0.06 | — | — |
| λ₃ ≤ 0.75 | headline | [0.0000, 0.5792] | yes | > 0.15 | — | — |
| λ₆ ≤ 0.50 | headline | [-0.9667, 0.3983] | yes | 0.04 | — | — |
| λ₁ informative (width < 0.25) | M0 | [0.3204, 0.5494] | yes | 0.02 | breakdown -0.02 | yes |
| λ₂ ≥ 0.50 | M0 | [0.4920, 0.9090] (5 event days) | no | 0.00 | verdict at B = 0 changes; breakdown -0.06 | yes |
| λ₃ ≤ 0.75 | M0 | [0.0000, 0.5839] | yes | > 0.15 | breakdown +0.00 | no |
| λ₆ ≤ 0.50 | M0 | [-1.0000, 0.5508] | no | 0.00 | verdict at B = 0 changes; breakdown -0.04 | yes |
| λ₁ informative (width < 0.25) | M1 | [0.3453, 0.5489] | yes | 0.05 | breakdown +0.01 | yes |
| λ₂ ≥ 0.50 | M1 | [0.5490, 0.9074] (6 event days) | yes | 0.11 | breakdown +0.05 | yes |
| λ₃ ≤ 0.75 | M1 | [0.0000, 0.5976] | yes | > 0.15 | breakdown +0.00 | no |
| λ₆ ≤ 0.50 | M1 | [-0.9979, 0.5620] | no | 0.00 | verdict at B = 0 changes; breakdown -0.04 | yes |
<!-- /generated -->

λ₁ near the informative limit, unrounded:

<!-- generated:rd_l1_widths -->
| arm | B | λ₁ lower | λ₁ upper | width | width < 0.25 |
|---|---|---|---|---|---|
| M0 | 0.01 | 0.3135694 | 0.5538445 | 0.2402751 | yes |
| M0 | 0.02 | 0.3066742 | 0.5582208 | 0.2515466 | no |
| M1 | 0.04 | 0.3185369 | 0.5666523 | 0.2481154 | yes |
| M1 | 0.05 | 0.3117346 | 0.5709512 | 0.2592166 | no |
<!-- /generated -->

## What sets λ₂'s lower bound

The minimum of λ₂ at b = 0, re-solved with the same programme and named constraints
(`artifacts/exp3_german_application/redispatch_sensitivity_l2_diagnosis.csv`). The re-solve
reproduces each stored lower bound exactly. Dropping the price ≤ −50 rows keeps the same per-row ε.

<!-- generated:rd_l2_diagnosis -->
| arm | λ₂ lower, B = 0 (event days) | without depth monotonicity | without any monotonicity | without the price ≤ −50 rows in the fit | data fit active | λ₁ upper | λ₁ at λ₂'s minimiser | max over b of the λ₂ lower to λ₁ upper gap | columns shared by the two bands |
|---|---|---|---|---|---|---|---|---|---|
| headline | 0.5254 (12) | 0.4887 | 0.4842 | 0.4136 | yes | 0.5079 | 0.4016 | 0.02080 | 1 of 101 |
| M0 | 0.4920 (5) | 0.4452 | 0.4336 | 0.4229 | yes | 0.5494 | 0.4236 | 0.06639 | 0 of 70 |
| M1 | 0.5490 (6) | 0.5123 | 0.5004 | 0.4586 | yes | 0.5489 | 0.4449 | 0.00054 | 0 of 85 |
<!-- /generated -->

## Note

<!-- generated:rd_note -->
- **Verdict under the pre-registered rule.** Sensitive to redispatch: λ₁, λ₂, λ₆. Not sensitive: λ₃. This is a sensitivity result, not a correction; the headline verdicts stay as they are.
- **The masks remove most of the evidence.** M0 removes 64% and M1 54% of the negative-price quarter-hours, and what is left is a selected subset (windy, congested days go first). A change under masking therefore cannot be attributed to grid-curtailment contamination alone.
- **λ₂ rests on very few days.** Its band keeps 5 event days under M0 and 6 under M1, against 12 in the headline.
- **What sets λ₂'s lower bound.** At its minimum the data fit is active in every arm, and so are many depth-monotonicity constraints. Removing depth monotonicity lowers M1's bound by 0.0366; removing the price ≤ −50 rows from the fit lowers it by 0.0904. So under M1 the bound is set by the deep-price data and monotonicity together, with the deep-price data the larger part, not by monotonicity alone. The same holds in M0 and the headline.
- **The M1 coincidence.** Under M1 λ₂'s lower bound equals λ₁'s upper bound to within 0.00054 at every b. No structural link was found: the two bands share no design column, the two optima are different solutions (λ₁ at λ₂'s minimiser is 0.4449), and the gap is 0.0491 or more under M0 and 0.0166 or more in the headline. It is reported as an unexplained numerical coincidence.
<!-- /generated -->
