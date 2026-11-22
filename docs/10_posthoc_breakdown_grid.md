# Post-hoc: Experiment 3 breakdown points on a finer bias grid

**Post-hoc.** Written on 22 Nov 2026, after the pre-registered V2 results were known
(`archive/docs/V0_preregistration.md`, commit `3277ea6`; `archive/docs/V_results.md`). The V2
result on its 0.01 grid stays the headline. Nothing here changes it.

**Why.** On the 0.01 grid λ₁ and λ₆ hold at 0.03 and break at 0.04, so their breakdown lies
somewhere above 0.03 and at most 0.04. H's measured bias on the quality-assured series lies in
that same interval, so the pre-registered grid cannot say whether those two readings survive it.

**Design.**

<!-- generated:posthoc_grid_design -->
- Fine grid for λ₁, λ₂ and λ₆: b from −0.06 to 0.06 in steps of 0.0025 (49 refits of the V2 full-window arm), hull S_B over |b| ≤ B for B = 0 to 0.06 in steps of 0.0025.
- λ₃ unchanged: the pre-registered grid, B = 0.01 to 0.15 in steps of 0.01.
- Readings, hull, informativeness rule, ε rule, window, areas and award setting are V2's.
- Comparison values, |bias| of H at price ≥ 0:
  - 0.0324, quality-assured series, 2025-10-01 to 2026-10-28 (the brief's value). A reading survives it if it holds at B = 0.0325, the first fine-grid allowance at or above it.
  - 0.0326, quality-assured series, Experiment 3 window (the H anchor). A reading survives it if it holds at B = 0.0350, the first fine-grid allowance at or above it.
<!-- /generated -->

**Files.** Code `src/experiments/exp3_posthoc_breakdown.py`; refit through
`src/method/bias_robust.py` with its defaults unchanged, so the pre-registered artifact still
reproduces bit for bit. Output `artifacts/exp3_german_application/posthoc_breakdown_fine_grid.csv`
(cells) and `posthoc_breakdown_fine_grid_summary.csv`.

## Results (post-hoc)

The refit ran from commit `6f5443b` and wrote only the new cells file. Its b = 0 row equals the
pre-registered V2 cells bit for bit for all seven quantities. Every hull below is formed from the
unrounded lo and hi in the cells file, and each margin is in the reading's own unit.

<!-- generated:posthoc_grid_results -->
| reading tested | grid | largest B at which it holds | breakdown B | at bias 0.0324 in size: holds? (margin at the B it needs) | at bias 0.0326 in size: holds? (margin at the B it needs) |
|---|---|---|---|---|---|
| λ₁ informative (width < 0.25) | post-hoc 0.0025 | 0.0350 | 0.0375 | yes at B = 0.0325 (+0.0034916) | yes at B = 0.0350 (+0.0004961) |
| λ₂ ≥ 0.50 | post-hoc 0.0025 | 0.0500 | 0.0525 | yes at B = 0.0325 (+0.0096231) | yes at B = 0.0350 (+0.0083802) |
| λ₆ ≤ 0.50 | post-hoc 0.0025 | 0.0350 | 0.0375 | yes at B = 0.0325 (+0.0089776) | yes at B = 0.0350 (+0.0028164) |
| λ₃ ≤ 0.75 | pre-registered 0.01 | 0.1500 | > 0.15 | yes at B = 0.0400 (+0.1502201) | yes at B = 0.0400 (+0.1502201) |
<!-- /generated -->

λ₁ around the edge, unrounded:

<!-- generated:posthoc_l1_edge -->
| B | λ₁ lower | λ₁ upper | width | width < 0.25 |
|---|---|---|---|---|
| 0.0325 | 0.2769929 | 0.5235013 | 0.2465084 | yes |
| 0.0350 | 0.2751798 | 0.5246837 | 0.2495039 | yes |
| 0.0375 | 0.2733828 | 0.5258631 | 0.2524803 | no |
<!-- /generated -->

<!-- generated:posthoc_grid_note -->
At the H anchor's bias (0.0326, checked at B = 0.0350) λ₁ and λ₆ hold, with almost no margin: λ₁'s width is 0.2495039 against 0.25 and λ₆'s upper bound 0.4971836 against 0.50, and both break at the next grid step. λ₂'s lower bound holds with margin 0.0084. On the pre-registered 0.01 grid λ₁ and λ₆ are reported as breaking at 0.04 and that stays the result; this is a post-hoc refinement, and the bias during negative prices is still not measured, so no reading is unconditionally robust. The hull is formed over the grid's b values only; a bias between two grid points is not refitted.
<!-- /generated -->
