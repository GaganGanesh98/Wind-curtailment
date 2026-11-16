# Q1 — results: the variance dial

Pre-registration `docs/Q0_preregistration.md`, commit **`b261c9f`**, recorded on every row.
Runner `src/identification/run_q_dial.py` (`d0366ea`); reduction
`src/identification/summarise_q1.py`, committed (`c974c95`) before any Q1 number was
read. 54 cells × 8 potentials × 7 functionals = **3,024 rows**, complete
(`artifacts/Q1/q1_variance_dial.csv`). Summaries: `artifacts/Q1/q1_summary_by_level.csv`
and `artifacts/Q1/q1_headline.csv`. Every figure below is re-derived by
`tests/test_reported_numbers.py`.

## 1. Headline

**σ\* ≥ 0.35 — censored at the top of the pre-registered grid.** The fleet response λ₁
stays informative in at least half the cells at **every** noise level tested: 54 of 54 up
to σ = 0.25, and 50 of 54 at σ = 0.35. The grid's highest level is nearly twice Anchor T,
and the pre-registered grid did not reach the noise at which λ₁ stops being informative.
**The headline statistic is therefore a lower bound, not a value.** The grid is not
extended after the fact; doing so is a pre-registration change.

| | σ |
|---|---|
| Anchor Z, exact | 0 |
| **Anchor H**, the statutory projection — a measured potential estimator (Q0b: ADDS BACK), a lower bound on its error (Q0 Amendment 1) | 0.066 |
| **Anchor T**, the TSO day-ahead forecast | 0.180 |
| **σ\***, the largest level with λ₁ informative in ≥ half the cells | **≥ 0.35** (grid top) |

**But λ₁ is the easy case, and it is not where the thesis's claims live.** The cohort-level
quantities behave completely differently (§3).

## 2. The guard rail holds everywhere

**Coverage of the known truth is 100% at all seven i.i.d. levels, and 0.984 (372 of 378) in
the AR(1) arm** (`q1_summary_by_level.csv`, `level_coverage`). *Erratum, 16 Nov 2026: this read
100% in the AR(1) arm before λ₅ was re-scored against its true-potential truth (`docs/ERRATUM_lambda5.md`); 6 of
the AR(1) arm's 54 λ₅ intervals miss it.* No level's widths are withheld under hard rule 4;
0.984 is above the 95% floor. No solve is infeasible at any level; `optimal_inaccurate` occurs 20 times at
σ = 0 (13 lower-bound and 7 upper-bound solves, all λ₅) and once at 0.25, never
elsewhere.

### The port check failed under its own tolerance — on λ₅ only, and not as a port error

`--check-port` compared σ = 0 with P3 Arm O at a relative tolerance of 10⁻⁶ and reported
**25 mismatches. All 25 are λ₅, all on the step and half shapes.**

| | max relative difference in lo / hi | max absolute width difference |
|---|---|---|
| λ₁, λ₂, λ₃, λ₄, λ₆, λ₇ | ≤ 2.9 × 10⁻⁹ | ≤ 3.3 × 10⁻⁹ |
| **λ₅** | ≤ **2.8 × 10⁻⁶** of a level of 2,484–46,566 GWh | **0.061 GWh** |

On step and half, Arm O's ε is at numerical zero (median 2.8 × 10⁻⁷ and 2.2 × 10⁻⁷). λ₅ is
measured in GWh, so its width is the difference of two bounds of order 10⁴ GWh that agree
to the solver's precision, and the 10⁻¹⁶ difference between `c_true` and `1 − G/A` moves
them by a few hundredths of a GWh. On logistic, where ε is 6 × 10⁻³, λ₅ reproduces
exactly. **The smallest informativeness threshold for λ₅ is 2,211 GWh**, so the discrepancy
is about 3 × 10⁻⁵ of it and changes no informativeness flag.

Q0 §3's pre-registered dead-end rule — every functional uninformative at every level
including 0 — is **not** triggered. The check is reported as failed rather than re-run at
a looser tolerance chosen after seeing it.

## 3. What survives the dial, functional by functional

Cells in which each functional is informative, out of 54 (`n_informative`):

| σ | λ₁ fleet | λ₂ deep | λ₃ cohort | λ₄ group | λ₅ energy | λ₆ contrast | λ₇ member |
|---|---|---|---|---|---|---|---|
| 0 (Z) | 54 | 54 | 54 | 54 | 54 | 54 | 18 |
| 0.033 | 54 | 54 | 54 | 54 | 52 | 54 | 14 |
| **0.066 (H)** | **54** | **54** | **54** | **24** | **24** | **54** | **9** |
| 0.120 | 54 | 54 | 34 | 18 | 18 | 24 | 9 |
| **0.180 (T)** | **54** | **54** | **18** | **18** | **18** | **18** | **9** |
| 0.250 | 54 | 54 | 18 | 18 | 18 | 18 | 6 |
| 0.350 | 50 | 41 | 18 | 14 | 17 | 18 | 0 |

**18 of 54 is exactly the step shape.** At σ = 0.18, λ₃ is informative in all 18 step cells
and in none of the 18 half or 18 logistic cells. On step the true response sits on the
upper bound `r = 1`, which the box constraint pins whatever the noise. **From σ = 0.12 to
0.18 onward, every cohort-level quantity is informative only where the box does the
identifying.**

- **At Anchor H, the cohort single (λ₃) and the cohort contrast (λ₆) are still informative
  in every cell; the group (λ₄) and the policy counterfactual (λ₅) in 24 of 54.**
- **At Anchor T, none of the four cohort-level quantities is informative outside the step
  shape.**
- λ₇, the split of the exactly collinear pair, is informative only on step even at σ = 0,
  and in no cell at 0.35.

Median width with interquartile range, i.i.d.:

| σ | λ₁ | λ₃ | λ₄ | λ₆ |
|---|---|---|---|---|
| 0.033 | 0.008 [0.006, 0.014] | 0.056 [0.022, 0.077] | 0.142 [0.066, 0.184] | 0.158 [0.074, 0.204] |
| 0.066 | 0.017 [0.013, 0.029] | 0.114 [0.045, 0.145] | 0.280 [0.110, 0.343] | 0.311 [0.134, 0.396] |
| 0.180 | 0.048 [0.038, 0.083] | 0.335 [0.102, 0.387] | 0.503 [0.153, 0.674] | 0.738 [0.248, 0.896] |
| 0.350 | 0.110 [0.066, 0.189] | 0.607 [0.163, 0.672] | 0.548 [0.249, 0.987] | 1.040 [0.405, 1.402] |

λ₆'s maximal width is 2, so its informativeness threshold is 0.5, not 0.25.

## 4. The pooled-response test keeps power above half only with an exact potential

The rejection rate — in the 27 `split` cells, how often a single common response function
falls outside the identified set (`q1_summary_by_level.csv`, `pooled_rejection_split`):

| σ | 0 | 0.033 | 0.066 | 0.120 | 0.180 | 0.250 | 0.350 |
|---|---|---|---|---|---|---|---|
| λ₁ fleet, λ₅ energy | **0.667** | 0 | 0 | 0 | 0 | 0 | 0 |
| λ₃ cohort | **0.667** | 0.222 | 0 | 0 | 0 | 0 | 0 |
| λ₄ group | **0.667** | 0.185 | 0 | 0 | 0 | 0 | 0 |
| λ₆ contrast | **0.667** | 0.296 | 0 | 0 | 0 | 0 | 0 |

At σ = 0, 18 of 27 `split` cells reject pooling, matching P3 Arm O's two in three. **At
σ = 0.033 — half of Anchor H — the cohort-level functionals still reject in 5 to 8 of the
27 cells**, below half, while λ₁ and λ₅ no longer reject in any. **From σ = 0.066, Anchor
H, no functional rejects in any cell.** The secondary statistic of Q0 §5, the largest σ
with rejection above half, is therefore **0** for every functional that rejects at all
(`q1_headline.csv`). λ₂ and λ₇ never reject above half.

**On this design the test of a single common response keeps power above half only with an
exact potential. At half of Anchor H's noise it keeps under a third, and at Anchor H's
noise none.** That is the answer to the question Q0 called the one that matters most for
the thesis argument.

## 5. Arm D's mechanism appears at the first step of the dial

Median ratio of the irreducible within-row floor to the total residual:

| σ | 0 | 0.033 | 0.066 | 0.120 | 0.180 | 0.250 | 0.350 |
|---|---|---|---|---|---|---|---|
| floor ÷ residual | 0.372 | **0.996** | 0.996 | 0.996 | 0.997 | 0.995 | 0.994 |

At σ = 0 the residual is discretisation, and the floor is a third of it. From the
smallest noise level onward the floor is 99.4–99.7% of the residual, which is P3 Arm D's
99.5%. **The switch P3 found is not gradual on this dial: it is fully thrown by σ = 0.033.**
What grows with σ after that is ε itself (median 0.019 at 0.033, 0.108 at 0.18, 0.226 at
0.35), and every width with it.

## 6. Correlated noise widens more, not less — Q0's prediction failed

Q0 §3 predicted that AR(1) noise at ρ = 0.989 would widen the intervals **less** than
i.i.d. noise at the same σ = 0.18. **It widens them more, for every functional:**

| | λ₁ | λ₂ | λ₃ | λ₄ | λ₆ | λ₇ |
|---|---|---|---|---|---|---|
| AR(1) − i.i.d., median width | +0.048 | +0.090 | +0.247 | +0.160 | +0.433 | +0.021 |

λ₅ widens by 3,118 GWh. ε rises from 0.108 to 0.114. λ₁ remains informative in 52 of 54
cells. The prediction rested on the floor being the binding term; the data show the
opposite direction and Q1 does not establish why. **The prediction is recorded as
failed.**

## 7. What Q1 does and does not say about the real panel

**The synthetic dial at Anchor T is far more optimistic than the real panel at the same
σ.** P3's real-data λ₁ on the window, with the forecast as the potential, is 0.310 wide
(`artifacts/P3/p3_real.csv`, `main`); Q1 at σ = 0.18 gives a median of 0.048 and
informative in every cell. Ways the real error differs from Q1's, listed and not
weighted:

- it is autocorrelated within the day — 0.989 at lag one (`artifacts/P0`) — and §6 shows
  correlation widens the intervals;
- it may be correlated with curtailment itself — Q0b found the forecast's negative-price
  gap one third of the projection's;
- the real design has eight MaStR cohorts, a monthly θ and real exposure, against the
  benchmark's five placeholder cohorts.

Q0 §8 item 5 stated in advance that σ\* is an optimistic bound for the real panel. Q5
measures the real panel directly.

## 8. Limitations

1. **σ\* is censored at the grid top.** Its value is not known, only that it exceeds 0.35.
2. **The noise seed is common across cells** at each level (Q0 §2). The spread across the
   54 cells reflects cell differences under one noise draw, not draw-to-draw variation.
3. **The 18-cell floor is a property of the step shape**, whose truth sits on the box
   boundary. It is not evidence that cohort quantities are identifiable under noise; it is
   evidence that a response pinned at 1 cannot move.
4. **i.i.d. lognormal noise is a model of estimator error**, and §6 shows one departure
   from it already changes the widths materially.
