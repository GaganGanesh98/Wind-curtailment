# Q_STOP_R1 — the λ-grid change against a frozen pre-registration

**STATUS: CLOSED by the student's written decision of 15 November 2026 (§ DECISION).**
The widened grid runs as a declared sensitivity; `docs/09` and the committed T-B PASS
are untouched.

**Raised 15 November 2026 during the R1 reconciliation, before Q0.** Phase Q hard
rule 10: stop and report when a rule here conflicts with an existing pre-registration
or supervisor minute. R1 item 2 says to reconcile the two drifted working copies.
Reconciling this particular drift would have changed a quantity that `docs/09`
freezes, so it was reported rather than resolved, and the decision below settles it.

## What is uncommitted

In the main checkout, on branch `mechanism-aware-censoring-gate-and-test2`, two
tracked files are modified and have been since **10 November 18:06**, which is one
minute after that branch's HEAD commit `f2b601f` (18:05:30):

```
src/censoring/m2.py          LAMBDA_GRID = (0.0,) + logspace(-4, 2, 13)   committed
                             LAMBDA_GRID = (0.0,) + logspace(-6, 4, 21)   working tree
src/censoring/tb_methods.py  at_grid_boundary reads the grid ends from LAMBDA_GRID
                             instead of the hard-coded 0.0 and 100.0
```

The full diff is preserved at
`artifacts/R1/lambda_grid_widening_uncommitted.patch`.

The `tb_methods.py` half is unobjectionable on its own: hard-coding `100.0` as the
upper edge would silently misreport `at_grid_boundary` once the grid moved, and
reading the ends from the grid fixes that. It is only in scope here because it is
part of the same uncommitted change.

## Why it cannot simply be committed

**`LAMBDA_GRID` is a pre-registered quantity.** `docs/09_m2_preregistration.md`
section 6 fixes it: *"λ grid: logarithmic, `1e-4` to `1e2` in half-decade steps (13
values), plus 0."* Amendment 3 section A3.3 then states what invalidates the
pre-registration: *"Any criterion, grid, seed or threshold modified after Stage 0"*,
and *"A bug fixed without re-running the affected cells in full and recording the bug
and the fix in a dated minute."*

The T-B verdict (PASS, `results/21_tb_primary.csv`, 945 rows) was produced on the
committed 13-value grid. Committing the widened grid would mean the code in the
repository no longer produces the committed verdict.

**The justifying minute was never written.** The change's own comment cites
`docs/22`:

> *"Widened 10 Nov 2026 (docs/22). The 9 Nov T-B run selected the old upper edge
> (100.0) in 104 of 135 M2 fits (results/40_m2_lambda_boundary.csv), so the CV search
> was clipped, not converged."*

`docs/22` **does not exist** — not in the main checkout, not on any branch, not in
any commit (`git log --all -- 'docs/22*'` returns nothing). So the change refers to a
decision document that was never filed.

**The re-run that would justify it is incomplete.** `results/41_tb_lambda_widening.csv`
is untracked and holds **74 of the 135 rows** it needs. Hard rule 20 forbids a claim
from a provisional subset, so it cannot presently establish anything about whether
the verdict survives the widening.

## The substance, stated so it is not lost

The motivation is real and is recorded in a complete artifact.
`results/40_m2_lambda_boundary.csv` has all 135 rows and shows where the inner
cross-validation landed on the committed grid:

| boundary | fits |
|---|---|
| `lambda_max` (the top of the grid) | **104** |
| interior | 29 |
| `lambda_min` | 2 |

**The λ search was clipped in 104 of 135 fits**, which is what the `docs/06` T-B note
of 1 November already anticipated at n = 20 and treated as a limitation to record
rather than to fix. On the widened grid the partial re-run reports the selection
moving in nearly every cell it reached, usually to the new upper edge of 10,000 —
which suggests the widened grid may be clipped too.

Phase P took the only route that touches nothing: `docs/P0_preregistration.md`
section 6.3 declares a Phase-P-only grid, `(0.0,) + logspace(-6, 4, 21)`, used by
Phase P code alone, and leaves `m2.py` untouched. That is why Phase P could proceed
without this decision being made.

## DECISION — student, 15 November 2026

**Recorded verbatim from the student's written instruction. This closes the STOP.**

> Lambda-grid decision: the M2 pre-registration and the committed T-B PASS stay
> exactly as they are. The widened grid runs as a declared SENSITIVITY analysis in a
> new artifact. Finish the 61 missing rows of the widened re-run, report whether the
> T-B verdict survives, and do not change any pre-registered threshold or the PASS
> record.

### What that settles

- **`docs/09` is untouched.** `LAMBDA_GRID` as pre-registered — `(0.0,) +
  logspace(-4, 2, 13)` — remains the committed value in `src/censoring/m2.py` and the
  grid of record.
- **`results/21_tb_primary.csv` is untouched**, and the T-B verdict of record stays
  **PASS** at n = 50. Nothing below can change it; the sensitivity reports alongside
  it and never replaces it.
- **No threshold moves.** The sign-test thresholds of Amendment 3 A3.1 (30 of 45 per
  shape, and the ≥ 16 of 45 non-inferiority clause on `half`) are applied unchanged
  to the widened table. The widened run is scored by the **same** `run_tb.report()`
  that produced the verdict of record.
- **`docs/22` is no longer needed as a pre-registration amendment.** This section is
  the dated minute the change lacked, and it records the change as a sensitivity
  rather than as an amendment — which is why no amendment number is taken.

### How it is run, and why that is reproducible despite an uncommitted edit

The 74 rows already on disk were produced with the widened `LAMBDA_GRID` **as a
working-tree modification** of `src/censoring/m2.py` in the main checkout. The
remaining 61 are produced the same way, in the same checkout, against the same two
modified files — because a 135-row sensitivity table assembled half one way and half
another would be worthless, and homogeneity across the 135 cells matters more here
than the tidiness of where the constant lives.

Reproducibility is preserved without committing the edit:

| | |
|---|---|
| exact diff | `artifacts/R1/lambda_grid_widening_uncommitted.patch` |
| `src/censoring/m2.py` sha256 (first 16) | `44491cd7f939d1f6` |
| `src/censoring/tb_methods.py` sha256 (first 16) | `278e5c7594afbf3b` |
| widened grid | 22 points, 0.0 to 10,000; **the old 14 are an exact float subset** (verified) |
| runner | `src/censoring/tb_lambda_widening.py`, untracked in the main checkout |

**The old grid being an exact float subset is what makes the comparison meaningful**:
every λ the committed run could have chosen is still available on the widened grid,
so a changed selection is a genuinely better CV score and not a different lattice.

### The guard the runner already carries

Each cell re-runs the inner CV and then checks a determinism condition: the first
minimum of the **new** CV log, restricted to the **old** grid points in old-grid
order, must equal the λ the committed run stored. A cell that fails has not been
reproduced bit-for-bit, and its "selection unchanged, reuse the existing score"
bookkeeping would be unsound. `--splice` refuses to build the table if any cell
fails.

**On the 74 rows already complete: 74 of 74 reproduce.** Selection changed in 57 of
those 74.

### What will be reported

`results/42_tb_primary_widened_lambda.csv` — the 945-row table with M2's
`int_abs_r` replaced **only** where the selection changed, `chosen_lambda` and
`at_grid_boundary` updated for all M2 rows to state the new-grid facts — scored by
the unchanged `run_tb.report()`. The result is written up as a sensitivity note,
reporting whether the verdict survives, **beside** the PASS of record and never in
place of it.

Status at the time of writing: the 61 remaining cells are running in the background.

---

## What was needed, and from whom (superseded by the decision above)

This was the open question. It is **answered** by the decision above; the three
items are kept for the record of what was asked.

1. **File the minute.** Write the missing `docs/22` as a dated decision: that the
   committed grid was clipped in 104 of 135 fits, what is being changed, and that the
   change post-dates the T-B verdict.
2. **Decide whether T-B is re-run in full.** Amendment 3 A3.3 requires the affected
   cells to be re-run *in full* — all 135, not the 74 on disk — and the result
   compared with the committed PASS. Until then the committed verdict stands and the
   widened grid has no standing.
3. **Then commit or discard.** If the decision is to adopt it, commit the two files
   together with the completed re-run and the minute. If not, discard the working-tree
   change so the checkout matches the verdict it produced.

**Nothing was committed or discarded here.** The two files are left exactly as found,
their diff is preserved in `artifacts/R1/`, and R1 is otherwise complete. The state
is recorded rather than tidied, because tidying it either way would be making the
decision.
