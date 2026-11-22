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
(cells) and `posthoc_breakdown_fine_grid_summary.csv`. Results are added below once run.
