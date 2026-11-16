# T-B λ-grid sensitivity: the verdict does not survive

**Reported 15 November 2026, separately from Phase Q, as the student instructed.** This is
a declared **SENSITIVITY** analysis (`docs/Q_STOP_R1.md`, the student's written decision).
**The M2 pre-registration and the committed T-B PASS stay exactly as they are.** No
threshold was changed. `results/21_tb_primary.csv` and
`results/21_tb_primary_report_20261110.txt` hash identically before and after the splice:

```
a8d38855b7ea2b22...  results/21_tb_primary.csv
ed9f694d24036fc6...  results/21_tb_primary_report_20261110.txt
```

## 1. Headline

> **On the widened λ grid, T-B FAILS at n = 50.** The gating condition, M2 not significantly
> worse than B3-CV on the half shape, no longer holds. M2 now wins 15 of 45 half cells
> against B3-CV, two-sided sign test p = 0.036, and the scorer marks it LOSES.

Every other pre-registered condition still holds. The committed PASS on the pre-registered
grid stands as the pre-registered result. This sensitivity says it is **not robust** to the
λ grid.

| | pre-registered grid (committed PASS) | widened grid (sensitivity) |
|---|---|---|
| step, M2 vs B3-CV | 45 of 45, PASS | 45 of 45, PASS |
| step, M2 vs B6 | 45 of 45, PASS | 45 of 45, PASS |
| logistic, M2 vs B3-CV | 41 of 45, PASS | 42 of 45, PASS |
| logistic, M2 vs B6 | 45 of 45, PASS | 45 of 45, PASS |
| **half, M2 vs B3-CV** [gates] | **22 of 45, p = 1.000, not worse** | **15 of 45, p = 0.036, LOSES** |
| half, M2 vs B6, reported only | 36 of 45 | 32 of 45 |
| **verdict** | **PASS** | **FAIL** |

## 2. What changed

Only `LAMBDA_GRID` in `src/censoring/m2.py`, from `(0.0,) + logspace(−4, 2, 13)` to
`(0.0,) + logspace(−6, 4, 21)`, and the boundary flag in `src/censoring/tb_methods.py`,
which now reads the grid's ends instead of hard-coding 100. The diff is
`artifacts/TB_lambda/widened_grid.diff`. Both files are still uncommitted modifications in
the main checkout (sha256 first 16: `44491cd7f939d1f6`, `278e5c7594afbf3b`).

The runner is `src/censoring/tb_lambda_widening.py`, untracked in the main checkout and
copied as `artifacts/TB_lambda/tb_lambda_widening.py.txt`.

| per M2 fit, 135 in all (`41_tb_lambda_widening.csv`) | count |
|---|---|
| old selection reproduced bit-for-bit on the old grid points | **135** |
| selection changed | 108 |
| selection unchanged, existing score reused | 27 |
| **new selection at the widened grid's top, λ = 10,000** | **77** |
| new selection interior | 58 |

The splice replaced M2's score only where the selection changed, as the brief required
(`42_tb_primary_widened_lambda.csv`, 945 rows). The verdict is `run_tb.report()` on the
spliced rows, with the scorer unchanged (`42_verdict_report.txt`).

M2's mean integrated absolute error per shape:

| shape | pre-registered grid | widened grid | cells worse / better / same |
|---|---|---|---|
| step | 0.000125 | 0.000129 | 10 / 33 / 2 |
| logistic | 0.011759 | 0.011271 | 9 / 20 / 16 |
| **half** | **0.011064** | **0.011705** | **22 / 14 / 9** |

On half, B3-CV's mean is 0.010641, so the widened M2 is now behind it on average as well.

## 3. The widened search is clipped too

**77 of 135 selections sit at the new upper edge.** The 9 November run had 104 at its
edge (`results/40_m2_lambda_boundary.csv`). Widening moved the edge and reduced the
clipping, but did not remove it, so the cross-validation has not converged on this grid
either. **This sensitivity result is itself provisional.** Q6 and the student's freeze
rule apply: no further widening is run without the student's written decision.

## 4. Artifacts

`artifacts/TB_lambda/`: `41_tb_lambda_widening.csv`, `42_tb_primary_widened_lambda.csv`,
`42_verdict_report.txt`, `widened_grid.diff`, `tb_lambda_widening.py.txt`. The originals
remain in the main checkout's `results/`, untracked.
