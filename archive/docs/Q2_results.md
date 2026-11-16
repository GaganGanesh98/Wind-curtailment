# Q2 — results: the bias dial, and bias crossed with noise

Pre-registration `docs/Q0_preregistration.md` §4, commit **`b261c9f`**, recorded on every
row. Run 16 November 2026 on commit `5692b97` with the runner written alongside that
pre-registration (`src/identification/run_q_dial.py --dial q2a` and `--dial q2b`). No
design change: five bias levels at σ = 0, then σ ∈ {0, 0.066, 0.18} × b ∈ {−0.10, 0,
+0.10}, 54 cells each. Reduction: `src/identification/summarise_q2.py`, written while the
runs were in progress and before any Q2 number was read; it applies Q1's rules unchanged
and adds one count, intervals that are **informative and miss the truth**.

Artifacts: `artifacts/Q2/q2a_bias_dial.csv` (1,890 rows), `artifacts/Q2/q2b_crossed.csv`
(3,402 rows), `artifacts/Q2/q2_coverage_by_level.csv`, `artifacts/Q2/q2_summary_by_level.csv`.
Every figure below is re-derived by `tests/test_reported_numbers.py`.

> **Erratum, 16 November 2026 (`docs/ERRATUM_lambda5.md`).** λ₅'s truth was computed from the scored
> potential instead of the true one. Re-scored from the stored intervals, without refits:
> coverage at b = +0.033 is 171 of 378 (was 162, 0.429); in the crossed grid 174, 188, 307 and
> 284 of 378 (were 193, 206, 325 and 302); λ₅'s missed-while-informative counts change
> accordingly. The tables and prose below carry the corrected values. **No verdict changes:**
> every biased level is still below 95%.

## 1. Headline

> **Coverage of the known truth falls below 95% at every non-zero bias level tested,**
> at every noise level. At Anchor H's measured bias (b = −0.047, σ = 0) it is 126 of 378,
> 0.333; at Anchor T's (b = +0.033) it is 171 of 378, 0.452. Every unbiased level keeps
> 378 of 378. **Under hard rule 4 the bounds are broken at every biased level, and no width
> from those levels is reported.**

**The failure is narrow intervals in the wrong place, not wide ones.** At b = −0.047 and
σ = 0, λ₁ is informative in 54 of 54 cells and misses the truth in all 54. A bias leaves
the identified set as tight as before and moves it off the true response; the
bootstrap ε, which measures spread, has no term for a shift.

**Checks passed before reading the rest.** The three unbiased Q2 levels reproduce Q1's
σ = 0, 0.066 and 0.18 rows exactly (informative counts and median widths, all seven
functionals). The two σ = 0, b = ±0.10 levels are identical in Q2a and Q2b.

## 2. Coverage per level

| dial | σ | b | covered | coverage | informative and missed | widths |
|---|---|---|---|---|---|---|
| q2a | 0 | -0.100 | 117/378 | 0.310 | 250 | withheld |
| q2a | 0 | -0.047 | 126/378 | 0.333 | 252 | withheld |
| q2a | 0 | +0.000 | 378/378 | 1.000 | 0 | reported |
| q2a | 0 | +0.033 | 171/378 | 0.452 | 207 | withheld |
| q2a | 0 | +0.100 | 144/378 | 0.381 | 225 | withheld |
| q2b | 0.066 | -0.100 | 174/378 | 0.460 | 177 | withheld |
| q2b | 0.066 | +0.000 | 378/378 | 1.000 | 0 | reported |
| q2b | 0.066 | +0.100 | 188/378 | 0.497 | 164 | withheld |
| q2b | 0.18 | -0.100 | 307/378 | 0.812 | 59 | withheld |
| q2b | 0.18 | +0.000 | 378/378 | 1.000 | 0 | reported |
| q2b | 0.18 | +0.100 | 284/378 | 0.751 | 90 | withheld |

`q2_coverage_by_level.csv`, columns `n_covered`, `n_scored`, `level_coverage`,
`n_informative_and_missed`. The q2b rows at σ = 0 equal the q2a rows and are not repeated.
"Informative and missed" counts cell-functionals, out of 378 per level.

## 3. Per functional: informative, and missed while informative

Counts out of 54 cells, written informative / missed-while-informative
(`q2_summary_by_level.csv`, columns `n_informative`, `n_informative_and_missed`). At a
biased level the informative *share* is withheld with the widths; the counts are shown
because they are what shows how the bounds broke.

σ = 0:

| functional | b -0.100 | b -0.047 | b +0.000 | b +0.033 | b +0.100 |
|---|---|---|---|---|---|
| λ₁ | 54 / 54 | 54 / 54 | 54 / 0 | 54 / 45 | 54 / 45 |
| λ₂ | 54 / 18 | 54 / 18 | 54 / 0 | 54 / 27 | 54 / 27 |
| λ₃ | 54 / 18 | 54 / 18 | 54 / 0 | 54 / 27 | 54 / 45 |
| λ₄ | 54 / 54 | 54 / 54 | 54 / 0 | 54 / 45 | 54 / 45 |
| λ₅ | 54 / 36 | 54 / 36 | 54 / 0 | 54 / 18 | 54 / 18 |
| λ₆ | 54 / 50 | 54 / 54 | 54 / 0 | 54 / 45 | 54 / 45 |
| λ₇ | 34 / 20 | 27 / 18 | 18 / 0 | 18 / 0 | 18 / 0 |

σ = 0.066 (Anchor H's noise):

| functional | b -0.100 | b +0.000 | b +0.100 |
|---|---|---|---|
| λ₁ | 54 / 54 | 54 / 0 | 54 / 45 |
| λ₂ | 54 / 18 | 54 / 0 | 54 / 18 |
| λ₃ | 54 / 0 | 54 / 0 | 54 / 19 |
| λ₄ | 42 / 36 | 24 / 0 | 28 / 19 |
| λ₅ | 36 / 36 | 24 / 0 | 26 / 18 |
| λ₆ | 54 / 33 | 54 / 0 | 54 / 45 |
| λ₇ | 9 / 0 | 9 / 0 | 18 / 0 |

σ = 0.18 (Anchor T's noise):

| functional | b -0.100 | b +0.000 | b +0.100 |
|---|---|---|---|
| λ₁ | 54 / 36 | 54 / 0 | 54 / 36 |
| λ₂ | 54 / 3 | 54 / 0 | 54 / 18 |
| λ₃ | 18 / 0 | 18 / 0 | 18 / 0 |
| λ₄ | 24 / 1 | 18 / 0 | 18 / 9 |
| λ₅ | 25 / 18 | 18 / 0 | 18 / 18 |
| λ₆ | 24 / 1 | 18 / 0 | 18 / 9 |
| λ₇ | 0 / 0 | 9 / 0 | 18 / 0 |

## 4. Variance or bias: the question §4 asked

§4 asked which of the two drives the real-data floor, and allowed "neither dominates, or
the two are not separable on this design" as an answer. On this design **they do different
things, so they are not competing explanations of the same effect:**

- **Variance widens the intervals and keeps coverage** (Q1; every unbiased row above).
- **Bias keeps the intervals narrow and moves them off the truth.** It does not produce
  wide intervals, so it does not explain the wide real-data intervals of P3 and Q5.
- **Adding variance to a bias raises coverage** (b = −0.10: 0.310 at σ = 0, 0.460 at
  σ = 0.066, 0.812 at σ = 0.18) because the intervals widen, not because the bias is
  corrected. No crossed level reaches 95%.

**Which dominates the width floor:** variance, on this evidence; bias contributes no
width. **What bias does instead matters more for reading real data:** a biased potential
yields intervals that look informative and are wrong, and nothing in the identified set
flags it. Anchor H's measured bias, −0.0472 (`docs/Q0_preregistration.md` §1), is the
tested level b = −0.047, where coverage is 0.333.

## 5. What this does not show

- It is synthetic. The bias is a constant multiplicative shift, exp(b), applied to the true
  potential; a real estimator's bias may vary by hour, season and area.
- It does not re-score any experiment. No existing verdict changes; Q1's results stand,
  because Q1 was unbiased by design (`docs/Q0_preregistration.md` §2).
- It does not say how large the bias of the projection H is *during negative prices*: the
  −0.0472 was measured on price ≥ 0 quarter-hours.
