# Q_STOP_R1 — the uncommitted λ-grid change conflicts with a frozen pre-registration

**Written 15 November 2026 during the R1 reconciliation, before Q0.** Phase Q hard
rule 10: stop and report when a rule here conflicts with an existing pre-registration
or supervisor minute. R1 item 2 says to reconcile the two drifted working copies.
Reconciling this particular drift would change a quantity that `docs/09` freezes, so
it is reported rather than resolved.

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

## What is needed, and from whom

This is a supervisor or student decision, not a code change:

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
