# Erratum — λ₅'s truth used the estimated potential (16 November 2026)

**Found** while writing `docs/V0_preregistration.md` §2. **Corrected** by re-scoring the
stored intervals; nothing was refitted, no experiment was re-run, and every raw run output is
left exactly as written.

## What was wrong

`src/identification/run_p3_synthetic.py`, `score_cell`, computed each functional's true value
with `_truths(..., potential)`, where `potential` is the potential handed to the bounds. For
λ₁–λ₄, λ₆ and λ₇ that argument is unused: their truth is the generator's true response. For λ₅,
the counterfactual energy in GWh, the truth is `Σ potential × share × r* × 0.25 h`, so **λ₅'s
truth was computed from the estimated potential instead of the true one** wherever the two
differ: P3 Arm D (Â), Q1 at σ > 0, Q2 at σ > 0 or b ≠ 0, Q6b, and V1 at every scored bias other
than zero. Where the potential was exact (P3 Arm O; σ = 0 and b = 0 in Q1, Q2 and V1) the truth
was already right.

## The fix

1. `score_cell` now passes the generator's true potential, `data.a_true_mw`, to `_truths`.
   `tests/test_lambda5_truth.py` fails on the old behaviour: scaling the scored potential by 1.5
   must leave every truth, λ₅'s included, unchanged.
2. Stored rows are corrected when they are read (`src/identification/lambda5_truth.py`, called
   by `summarise_p3.load` and `summarise_v`): λ₅'s truth is replaced by P3 Arm O's λ₅ truth for
   the same cell — Arm O passed the true potential, and the generator, design rows and cohorts of
   a cell are identical in every synthetic arm — and `covered` is recomputed from the **stored**
   interval with P3's rule. Every λ₅ interval was stored; none had to be excluded. λ₅ never used
   the one-sided rule in these arms (`l5_coverage` = 1 throughout).
3. The summaries were regenerated from the corrected rows; the notes that quote changed figures
   carry the corrected values with an erratum marker.

## Figures that change (old → new)

Coverage of the known truth, all scored cell-functionals at a level (λ₅ and the six others):

| artifact | level | covered, as stored | covered, corrected | scored |
|---|---|---|---|---|
| Q1 | AR(1), σ = 0.18 | 378 | 372 | 378 |
| Q2a | σ = 0, b = +0.033 | 162 | 171 | 378 |
| Q2b | σ = 0.066, b = −0.10 | 193 | 174 | 378 |
| Q2b | σ = 0.066, b = +0.10 | 206 | 188 | 378 |
| Q2b | σ = 0.18, b = −0.10 | 325 | 307 | 378 |
| Q2b | σ = 0.18, b = +0.10 | 302 | 284 | 378 |

Where they are quoted:

- `docs/Q1_results.md` §2: the AR(1) arm's coverage is 0.984 (372 of 378), not 100%. It stays
  above 95%, so the AR(1) widths remain reportable under hard rule 4 and nothing in Q1 §3–5
  changes. `docs/00_START_HERE.md`'s Q1 row and F4's AR(1) point follow.
- `docs/Q2_results.md`: §2's coverage table, §3's λ₅ "missed while informative" counts, §1
  (Anchor T's bias: 171 of 378, 0.452; was 162, 0.429) and §4 (b = −0.10: 0.310 → 0.460 → 0.812
  across σ; was 0.310 → 0.511 → 0.860). The C1 table's Q2 row (171/378; was 162/378) and the
  guide's Q2 row follow.
- `artifacts/V/v1_by_functional.csv`: λ₅'s coverage rows. With the corrected truth λ₅ is covered
  in 54 of 54 cells at every level where B ≥ |b*|, like the six scored functionals. V0 left λ₅
  out of V1's criterion and that stands; the V1 verdict does not change.

## Figures that do not change

- **P3 Arm O** (1,127 of 1,127): its potential was the true one.
- **P3 Arm D** (378 of 378), **Q1 at every i.i.d. level** (378 of 378 each), **Q6b** (378 of 378
  at every level), **Q2 at b = 0 and at b = −0.10, −0.047, +0.10 with σ = 0**: re-scored, same counts.
- **Every informativeness count and verdict** (P3, Q1, Q2, Q5, C1, V): informativeness depends
  on the interval width only, never on the truth.
- **Every verdict**: Q1's σ\* ≥ 0.35; Q2's "coverage below 95% at every non-zero bias"; V1 PASS;
  C1's verdict counts; F4's "with unbiased potentials, coverage never falls below target"
  (the lowest unbiased level is now 0.984).
- Real-data results (P3 real, Q5, V2) have no truth and are untouched.

Every figure above is re-derived by `tests/test_reported_numbers.py` (`_erratum_checks`), both
the stored and the corrected count.
