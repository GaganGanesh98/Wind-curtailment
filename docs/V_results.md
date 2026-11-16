# V — results: bias-robust bounds and breakdown points

Pre-registration `docs/V0_preregistration.md`, commit **`3277ea6`**, recorded on every raw
row. Runner `src/identification/run_v_bias_robust.py` (outer loop only), reduction
`src/identification/summarise_v.py`. Every figure below is re-derived by
`tests/test_reported_numbers.py`.

## V1 — synthetic, Q2's cells: **PASS**

Arm D's 54 cells, σ = 0, true bias b* ∈ {−0.100, −0.047, 0, +0.033, +0.100}, the robust hull
S_B for B ∈ {0, 0.05, 0.10}. Scored: λ₁, λ₂, λ₃, λ₄, λ₆, λ₇ (λ₅ left out, V0 §2), 324
cell-functionals per level. Raw rows: `artifacts/V/v1_raw_shard{0..3}of4.csv`, 70 scored
potentials per cell, run in four processes by cell.

> **Coverage is 324 of 324 at every level where B ≥ |b*|.** That includes b* = −0.047 and
> +0.033, which are not on the 0.01 grid: the hull of the neighbouring grid points bracketed
> the truth, as V0 predicted it would only if the set moves monotonically with b. **V1 PASS.**

| B | true bias b* | covered | coverage | criterion applies | result |
|---|---|---|---|---|---|
| 0.00 | -0.100 | 99/324 | 0.306 | no | — |
| 0.05 | -0.100 | 135/324 | 0.417 | no | — |
| 0.10 | -0.100 | 324/324 | 1.000 | yes | PASS |
| 0.00 | -0.047 | 108/324 | 0.333 | no | — |
| 0.05 | -0.047 | 324/324 | 1.000 | yes | PASS |
| 0.10 | -0.047 | 324/324 | 1.000 | yes | PASS |
| 0.00 | +0.000 | 324/324 | 1.000 | yes | PASS |
| 0.05 | +0.000 | 324/324 | 1.000 | yes | PASS |
| 0.10 | +0.000 | 324/324 | 1.000 | yes | PASS |
| 0.00 | +0.033 | 135/324 | 0.417 | no | — |
| 0.05 | +0.033 | 324/324 | 1.000 | yes | PASS |
| 0.10 | +0.033 | 324/324 | 1.000 | yes | PASS |
| 0.00 | +0.100 | 108/324 | 0.333 | no | — |
| 0.05 | +0.100 | 140/324 | 0.432 | no | — |
| 0.10 | +0.100 | 324/324 | 1.000 | yes | PASS |

`artifacts/V/v1_coverage.csv`. Where the budget is smaller than the bias (B < |b*|), coverage
stays as low as Q2's: the robust set only protects against the bias it is told to allow.
At B = 0 the rows reproduce Q2a without λ₅ (at b* = −0.047, Q2's 126 of 378 less λ₅'s 18
covered rows is 108 of 324).

**The width cost, at b* = 0** (`artifacts/V/v1_by_functional.csv`; the ratio in
`v1_width_cost.csv` is not quoted because S_0 is about 10⁻⁶ wide at σ = 0, which makes any
ratio enormous and uninformative):

| functional | B | median width | informative | covered |
|---|---|---|---|---|
| λ₁ | 0.00 | 7.02e-07 | 54/54 | 54/54 |
| λ₁ | 0.05 | 0.057 | 54/54 | 54/54 |
| λ₁ | 0.10 | 0.115 | 54/54 | 54/54 |
| λ₂ | 0.00 | 1.32e-06 | 54/54 | 54/54 |
| λ₂ | 0.05 | 0.014 | 54/54 | 54/54 |
| λ₂ | 0.10 | 0.037 | 54/54 | 54/54 |
| λ₃ | 0.00 | 4.7e-06 | 54/54 | 54/54 |
| λ₃ | 0.05 | 0.050 | 54/54 | 54/54 |
| λ₃ | 0.10 | 0.100 | 54/54 | 54/54 |
| λ₄ | 0.00 | 1.23e-05 | 54/54 | 54/54 |
| λ₄ | 0.05 | 0.346 | 18/54 | 54/54 |
| λ₄ | 0.10 | 0.538 | 18/54 | 54/54 |
| λ₆ | 0.00 | 1.4e-05 | 54/54 | 54/54 |
| λ₆ | 0.05 | 0.379 | 54/54 | 54/54 |
| λ₆ | 0.10 | 0.584 | 18/54 | 54/54 |
| λ₇ | 0.00 | 0.467 | 18/54 | 54/54 |
| λ₇ | 0.05 | 0.850 | 9/54 | 54/54 |
| λ₇ | 0.10 | 0.976 | 9/54 | 54/54 |

Protection costs width in the same order Q1's noise did: the fleet functionals λ₁ and λ₂
stay informative in every cell at B = 0.10, the collinear group λ₄ drops to 18 of 54 from
B = 0.05, and λ₆ from B = 0.10. λ₅'s rows are in the artifact but are not interpretable for
the reason given in V0 §2 (its synthetic truth is computed from the potential passed in).

**A process slip, disclosed.** While the V1 shards were running, `summarise_v.py` was run
once for V2 and also read the V1 shard files when only 8 of 54 cells existed, printing two
partial V1 lines. Those outputs were moved out of `artifacts/` unread for any decision, a
guard was added that refuses to summarise V1 until all 54 cells × 70 potentials exist, and
every V1 number above comes from the complete run.

## V2 — real data, full window, projection H

`run_p3_real.run_arm` on the three-area panel with H, award setting `main`, full window,
plain ĉ, every b ∈ [−0.15, 0.15] on the 0.01 grid (`artifacts/V/v2_real_raw.csv`, 31 scorings).
At b = 0 every functional reproduces the committed Q5 full-window row exactly. Hulls per
budget: `artifacts/V/v2_robust_intervals.csv`; breakdown points: `artifacts/V/v2_breakdown.csv`.

| functional | reading (C1, B = 0) | breaks when | breakdown B | S_B at B = 0 | S_B at breakdown | S_B at B = 0.15 |
|---|---|---|---|---|---|---|
| λ₁ | informative | width ≥ 0.25 | 0.04 | [0.300, 0.508] | [0.272, 0.527] | [0.187, 0.574] |
| λ₂ | at least 0.525 | lower bound < 0.5 | 0.06 | [0.525, 0.860] | [0.496, 0.867] | [0.449, 0.876] |
| λ₃ | at most 0.579 | upper bound > 0.75 | > 0.15 | [0.000, 0.579] | — | [0.000, 0.658] |
| λ₆ | at most 0.398 | upper bound > 0.5 | 0.04 | [-0.967, 0.398] | [-1.000, 0.509] | [-1.000, 0.654] |

**What it says.** λ₁'s informative full-window reading and λ₆'s one-sided bound survive a
constant bias of up to 0.03 in the projection, and break at 0.04. λ₂'s lower bound survives up
to 0.05 and breaks at 0.06. λ₃'s one-sided bound survives the whole tested range. **For scale
only** (V0 §3): the projection's measured bias on price ≥ 0 quarter-hours is −0.0472, larger
than the budget at which λ₁ and λ₆ break; its bias during negative prices is not measured.
Figure: `figures/findings/F10_bias_breakdown.png`.
