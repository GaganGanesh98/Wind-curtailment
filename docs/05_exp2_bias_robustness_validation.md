# Experiment 2 — Bias-robustness validation

**Question.** What does a biased potential do to the bounds, and does the bias-robust set restore
coverage within its budget?

**What was done.**
- The bias dial: the same 54 cells with the true potential multiplied by exp(b), b ∈ {−0.100,
  −0.047, 0, +0.033, +0.100} at σ = 0, then crossed with σ ∈ {0, 0.066, 0.18} at
  b ∈ {−0.10, 0, +0.10}.
- The bias-robust set (method step 5) on the bias-dial cells at σ = 0, for B ∈ {0, 0.05, 0.10}.

**Pre-registrations.** `archive/docs/Q0_preregistration.md` §4 (commit `b261c9f`);
`archive/docs/V0_preregistration.md` (commit `3277ea6`).

**Plain identified set under bias** (`artifacts/exp2_bias_robustness_validation/bias_dial_coverage.csv`;
"informative and missed" counts intervals narrow enough to be informative that miss the truth):

<!-- generated:exp2_bias_dial -->
| σ | bias b | covered | coverage | informative and missed |
|---|---|---|---|---|
| 0 | -0.100 | 117/378 | 0.310 | 250 |
| 0 | -0.047 | 126/378 | 0.333 | 252 |
| 0 | +0.000 | 378/378 | 1.000 | 0 |
| 0 | +0.033 | 171/378 | 0.452 | 207 |
| 0 | +0.100 | 144/378 | 0.381 | 225 |
| 0.066 | -0.100 | 174/378 | 0.460 | 177 |
| 0.066 | +0.000 | 378/378 | 1.000 | 0 |
| 0.066 | +0.100 | 188/378 | 0.497 | 164 |
| 0.18 | -0.100 | 307/378 | 0.812 | 59 |
| 0.18 | +0.000 | 378/378 | 1.000 | 0 |
| 0.18 | +0.100 | 284/378 | 0.751 | 90 |
<!-- /generated -->

**Bias-robust set** (`bias_robust_coverage.csv`; λ₅ left out of the criterion, as pre-registered):

<!-- generated:exp2_bias_robust -->
| budget B | true bias | covered | coverage | criterion |
|---|---|---|---|---|
| 0.00 | -0.100 | 99/324 | 0.306 | — |
| 0.05 | -0.100 | 135/324 | 0.417 | — |
| 0.10 | -0.100 | 324/324 | 1.000 | PASS |
| 0.00 | -0.047 | 108/324 | 0.333 | — |
| 0.05 | -0.047 | 324/324 | 1.000 | PASS |
| 0.10 | -0.047 | 324/324 | 1.000 | PASS |
| 0.00 | +0.000 | 324/324 | 1.000 | PASS |
| 0.05 | +0.000 | 324/324 | 1.000 | PASS |
| 0.10 | +0.000 | 324/324 | 1.000 | PASS |
| 0.00 | +0.033 | 135/324 | 0.417 | — |
| 0.05 | +0.033 | 324/324 | 1.000 | PASS |
| 0.10 | +0.033 | 324/324 | 1.000 | PASS |
| 0.00 | +0.100 | 108/324 | 0.333 | — |
| 0.05 | +0.100 | 140/324 | 0.432 | — |
| 0.10 | +0.100 | 324/324 | 1.000 | PASS |
<!-- /generated -->

**Verdicts (quoted).**
- Bias dial: "Coverage of the known truth falls below 95% at every non-zero bias level tested, at
  every noise level."
- Bias-robust set: "Coverage is 324 of 324 at every level where B ≥ |b*|." — "V1 PASS."

**Figure.** `figures/08_exp2_coverage_under_bias.png`.

**Full detail.** `archive/docs/Q2_results.md`, `archive/docs/V_results.md` (V1),
`archive/docs/ERRATUM_lambda5.md`.
