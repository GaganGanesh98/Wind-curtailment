# 20 — Scoring bug in `response_curve`, found after the T-B verdict

**Written 9 November 2026, ~17:00 CET, BEFORE any fix was applied.** The sequence is
deliberate: this note is committed first, together with the T-B result file and the
verdict document it concerns, so the record shows the defect was found and declared
rather than silently corrected.

---

## 1. What happened, in order

1. `run_tb.py --pass primary --resume` completed on 9 November. 945 rows, 135 cells,
   `results/21_tb_primary.csv`. No fit raised, no cell marked `failed`.
2. The verdict printed by `run_tb` was **T-B FAIL**, gated by one clause of the
   section 0.3 rule: *M2 not significantly worse than B3-CV on `half`* — False.
   M2 mean `int_abs_r` 0.42862 against B3-CV 0.00957, a factor of 45.
3. Under the binding rule (`docs/10_m2_verdict.md` section 1, from
   `docs/09_m2_preregistration.md` Amendment 3 section 0.4), T-B FAIL -> STOP.
4. While diagnosing *why* `half` failed, `m2.py::response_curve` was read directly and
   found to double-count the atom. The failure is in the **scored statistic**, not in
   the estimator.

## 2. The defect

`src/censoring/m2.py`, `response_curve`:

```python
cdf = np.array([p[b][np.isfinite(knots) & (knots <= z)].sum()
                + (p[b][0] if (knots[0] == 0.0 and z > 0) else 0.0)
                for z in depth_grid])
```

`knot_grid(..., with_atom=True)` places `0.0` at index 0 (verified). For any `z > 0`
the mask `np.isfinite(knots) & (knots <= z)` therefore **already includes index 0**,
and `+ p[b][0]` adds the same mass a second time.

Measured by running the function's own source on known inputs (9 Nov 2026):

| `p` fed in | `r_hat` at z = 0, 1, 5, 20, 60 | correct value |
|---|---|---|
| 0.5 atom + 0.5 at inf (**true `half`**) | 0.5, **1.0, 1.0, 1.0, 1.0** | 0.5 for all z > 0 |
| 1.0 atom (**true `step`**) | 1.0, 1.0, 1.0, 1.0, 1.0 | 1.0 for all z > 0 |
| 0.25 atom + 0.75 at inf | 0.25, **0.5, 0.5, 0.5, 0.5** | 0.25 for all z > 0 |
| 0.5 at finite knot 5.0 + 0.5 inf | 0, 0, 0.5, 0.5, 0.5 | correct |

## 3. Why the severity is shape-dependent — and matches the observed T-B pattern

The atom carries the mass that represents "switches off at any positive depth", so how
much mass sits there depends on the true shape being recovered.

| shape | true atom mass | effect of doubling | M2 `int_abs_r` (median) |
|---|---|---|---|
| `step` | ~1.0 | doubled to ~2, clipped to 1 by `np.minimum(cdf, 1.0)` — **correct by accident** | 0.0017 |
| `logistic` | ~0 (mass on finite knots) | small distortion | 0.0491 |
| `half` | ~0.5 | doubled to ~1.0 against a truth of 0.5 — **error ~0.5** | 0.4588 |

The `half` median of 0.4588 is what a *correct* fit scores through this function: the
curve is forced to 1.0 where the truth is 0.5 across the whole grid, except at z = 0.

`M2-noAtom` is immune: with `with_atom=False`, `knots[0] == 2.0`, the condition
`knots[0] == 0.0` is never true, and the extra term cannot fire. Its `half` median is
0.0313. **The M2 vs M2-noAtom reversal on `half`, reported in the Amendment 3
section 0.3 component attribution, is therefore an artefact of this defect and not a
statistical result about the atom.**

## 4. Affected and unaffected

**Affected.** `m2_curve` (`tb_methods.py:238`) calls `response_curve`, and `score_cell`
(`run_tb.py:215,220`) turns its output into `int_abs_r`. Every M2 and M2-noPool
`int_abs_r` in `results/21_tb_primary.csv` is affected wherever atom mass is non-zero.
`m2.py:561` returns `r_hat` from the same function.

**Not affected.**
- M1 and the merged E1 gate: these use `model.py::m1_response_curve`, a different
  function. The gate failure recorded in `docs/19_merged_gate_and_power.md` stands.
- B3-CV, B3@8, B3-H, B6: these use `baselines.py::b3_response_curve`. The rival columns
  in T-B are correct.
- T-D(iii) and the real-data identification finding (market premium = 0 fleet-wide in
  many months, `results/26_td_iii_identification.csv`): no dependence on this function.

**How the blast radius was established** (9 Nov 2026): every call site of
`response_curve` was enumerated. Two exist — `tb_methods.py:238` (`m2_curve`, which
T-B scores through) and `m2.py:561` (the `r_hat` entry of `fit_m2`'s return dict).
The latter is consumed only by `run_synthetic.py:197-199`, a plotting path that draws
M1 and B3, never M2. `run_td.py` does not call it; its single `r_hat` match is text
inside a requirement string. `results/25_tb_sensitivity.csv` does not exist, so the
sensitivity pass has nothing to invalidate. The only contaminated artefact is
therefore `results/21_tb_primary.csv`.

## 5. Why the test suite did not catch it

179 tests pass. All three tests touching `response_curve` are blind to the defect:

- `test_m2.py::test_response_is_monotone_and_in_unit_interval_for_any_simplex_point`
  asserts only monotonicity and [0, 1] bounds. Doubling preserves both, and
  `np.minimum(cdf, 1.0)` enforces the upper bound.
- `test_m2.py::test_mass_on_the_never_atom_caps_the_response_below_one` sets
  `p[0, 1] = 0.3` and `p[0, -1] = 0.7`, leaving **atom mass at zero**. The one test
  named for the atom exercises none of it.
- `test_m2.py` line 167-168 computes `r_true` and `r_hat` *both* through
  `response_curve`, so the double-count appears on both sides and cancels.

No test ever compares `response_curve` against `synthetic.py::true_response_curve`.
That is the missing assertion, and it is being added.

## 6. Still unexplained

`chosen_lambda` sits at `lambda_max = 100` in 33 of 45 M2 `half` cells. `choose_lambda`
scores on `y` through `X @ p` and never calls `response_curve`, so this defect does not
explain the pinning. It is an open item, recorded here, not resolved.

## 7. Decision

The T-B verdict of 9 November 2026 was computed from a corrupted statistic on the
clause that gated it. It is therefore **not interpretable as a statement about M2**,
and equally **is not withdrawn in favour of a better number** — nothing replaces it
until a clean re-run exists.

Sequence, binding on me:

1. This note committed, with `results/21_tb_primary.csv` and `docs/10_m2_verdict.md`,
   before any change to `m2.py`.
2. `response_curve` fixed. Minimal change only.
3. A test added asserting `response_curve(p*) == true_response_curve` for all three
   shapes, independent of the fix's wording.
4. T-B re-run with **no other change**: same seeds (45-49), same rates, same gammas,
   same shapes, same pre-registered lambda grid, same n = 50. Output to a new file so
   the original is preserved.
5. Both verdicts reported in `docs/10_m2_verdict.md` — the 9 November result, this
   defect, and the corrected result — in that order.

No criterion, threshold, seed or grid is altered. The pre-registration is not
reopened; a defect in the measuring instrument is disclosed and the measurement
repeated.
