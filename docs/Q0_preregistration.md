# Q0 — Phase Q pre-registration: how good must the potential estimate be?

**Written and committed 15 November 2026, before any Q1 or Q2 metric existed.**
Branch `claude/phase-p-postauction-forecasting-68cc63`.

This file binds Q1–Q4. Every grid, anchor, metric and threshold below is fixed
**now**; §§2–6 may not change after the first Q1 number exists without a dated
written decision kept beside the superseded wording. **Every Q1–Q4 result file
records this file's commit hash** in a `preregistration_commit` column.

It revises nothing. `docs/P0_preregistration.md`, `docs/P3_results.md`, the v1.8
gate, `docs/09` and the committed T-B PASS all stand untouched.

**The question.** P3 Arm D showed the identified sets collapse when the curtailed
share is formed from an **estimated** potential instead of an exact one: every
interval widened by four to five orders of magnitude and the irreducible floor rose
to 99.5% of the residual. That was a switch. Phase Q makes it a dial and asks **how
accurate a potential estimator must be before the bounds say anything.**

---

## 1. The anchors, measured from this repo's own panel

Phase Q hard rule 5: the levels come from the panel, computed here, never from a
paper or from the brief. `artifacts/Q0/q0_anchors.csv`, written by
`python -m src.potential.anchors`. Every figure below is re-derived from that file by
`tests/test_reported_numbers.py` under `pytest`.

**The statistic.** For a potential estimate `P` against observed output `G`, on
quarter-hours where nothing should be switched off:

```
x_t = log(G_t / P_t)      sigma = sd(x)      b = mean(x)
```

`sigma` is the dial's unit — exactly the lognormal width Q1 injects. `b` is the bias
term Q2 uses. Both carry a 95% event-day block-bootstrap interval, 5,000 draws, seed
42, blocked on the Berlin-local date. Rows where either side is non-positive or
non-finite have no logarithm; they are dropped and counted, never filled.

### 1.1 Anchor T — the TSO day-ahead forecast

The potential every Phase P and Test 2 model actually has, and the one P3's
real-data arm used. Window from 2025-10-01, DE, onshore primary.

| sample | σ | 95% CI | bias | n QH | event-days |
|---|---|---|---|---|---|
| **price ≥ 0 (Anchor T of record)** | **0.1806** | [0.1657, 0.1952] | −0.0037 | 35,577 | 392 |
| price > 5 €/MWh | 0.1787 | [0.1647, 0.1930] | −0.0031 | 34,303 | 391 |
| price ≥ 0, in the negative-QH forecast band | 0.1603 | [0.1493, 0.1715] | −0.0051 | 32,121 | 388 |
| price ≥ 0, onshore + offshore | 0.1608 | [0.1470, 0.1754] | +0.0098 | 35,577 | 392 |

The band is `F ∈ [2,129, 36,674] MW`, the 10th–90th percentile of the day-ahead
forecast over negative-price quarter-hours, read off the data rather than chosen.
**Restricting to it lowers σ by about a tenth** (0.1806 → 0.1603), so the regime Q
cares about is, if anything, slightly easier for the forecast than the window at
large.

The price ≥ 0 and price > 5 figures differ by 0.002. They are reported separately
because Hirth (2026) Table 3 finds 4.2% wind curtailment already in the 0–5 band, so
they are not the same sample; **here the distinction does not matter**, and that is
worth knowing rather than assuming.

Per control area, onshore, price ≥ 0 — σ rises sharply as the area shrinks:

| area | σ | bias |
|---|---|---|
| DE | 0.1806 | −0.0037 |
| TenneT | 0.2313 | −0.0036 |
| Amprion | 0.3071 | +0.0216 |
| 50Hertz | 0.3165 | −0.0730 |
| TransnetBW | 0.5213 | +0.0034 |

### 1.2 Anchor H — the Online-Hochrechnung (Anlage 1 Nr. 5.1)

**A better potential that already exists, measured rather than imagined.** By statute
the projection excludes both grid curtailment and direct-marketing reductions, and
`results/39_nr51_compliance.csv` shows it passing that test in all four control
areas, so it is an official, published, quarter-hourly estimate of *uncurtailed*
potential. It is ex post and is on the Phase P leakage list as never a forecast
input; Q1 and Q2 are identification questions rather than forecasts, so that does not
bite here.

**TenneT is excluded from every aggregate and reported on its own.** `docs/09`
Amendment 4 A4.5 makes T-D(vii) a *precondition*: no DE-level aggregate may use the
projection until TenneT's 0.839 positive-price ratio is explained or TenneT is
excluded and the exclusion stated. It is not explained, so it is excluded and stated.

| area | σ | 95% CI | bias | n QH |
|---|---|---|---|---|
| **DE excl. TenneT (Anchor H of record)** | **0.0660** | [0.0511, 0.0800] | **−0.0472** | 5,131 |
| 50Hertz | 0.0865 | — | −0.0727 | 5,417 |
| Amprion | 0.0884 | — | −0.0027 | 5,422 |
| TransnetBW | 0.0885 | — | −0.0841 | 5,136 |
| *TenneT, excluded* | *0.0709* | — | *−0.0532* | *5,422* |

The projection covers **2026-09-01 onwards only**, so Anchor H rests on 55 event-days
against Anchor T's 392.

### 1.3 The like-for-like comparison, and what it sets up

Anchor H's sample is two months; Anchor T's is thirteen. Comparing them as they stand
would confound the estimator with the period, so **Anchor T is recomputed on exactly
the quarter-hours and areas Anchor H covers** — the same 5,131 rows, same 55 days:

| on the same 5,131 quarter-hours | σ | 95% CI | bias |
|---|---|---|---|
| **TSO day-ahead forecast** | **0.2270** | [0.1678, 0.2874] | **+0.0325** |
| **Online-Hochrechnung** | **0.0660** | [0.0511, 0.0800] | **−0.0472** |

**The statutory projection is 3.4× tighter than the day-ahead forecast, and carries a
bias of the opposite sign and larger magnitude.** That single comparison is why Phase
Q needs two dials and not one: the better estimator is not better on both axes, and
Q2 exists to say which of the two actually binds.

### 1.4 Anchors W and Z, and one broken module found on the way

**Anchor W — a weather-based potential: `[UNRESOLVED — needs P2]`.** No ERA5 or ICON
potential series exists in this repo (`data/processed/` holds none, no module builds
one) and there is no CDS credential (`~/.cdsapirc` absent). Q1 and Q2 do not depend
on it; the grid below leaves room where it would fall.

**Anchor Z — exact: σ = 0, b = 0** by construction. This is P3 Arm O, and Q1's zero
level must reproduce it (§3, dead-end check).

**`[VERIFY]` — `src/check_hochrechnung_onshore.py` cannot be imported.** It compiles a
regular expression at module level with no `import re`, so it raises `NameError` on
import. That is true in **every commit the file has ever appeared in** (checked across
`main`, `identification-fix`, `mechanism-aware-censoring-gate-and-test2` and HEAD), so
`results/36_hochrechnung_onshore_check.csv` cannot have been produced by the committed
version of it and its provenance is unclear. Anchor H therefore uses
`src/check_nr51_compliance.py:load_projection`, which imports `re` correctly, is
importable, and is the module behind `results/39_nr51_compliance.csv`. The defect is
recorded here and **not fixed as part of Q0**, because Q0 has a working alternative and
should not depend on a repair of its own making.

---

## 2. What Q1 and Q2 change, and what they do not

Everything that is not the dial is P3's, unchanged: the generator
(`src/censoring/synthetic.py`), the bounds (`src/identification/bounds.py`), the seven
functionals (`src/identification/functionals.py`), the depth grid, the two
run-length levels, the RMS norm, the exposed-rows-only rule, ε from the event-day
bootstrap, the CLARABEL solver and the row compression. `docs/P3_results.md` §0 governs
all of it and is not reopened.

**The one new axis** is the potential handed to the share estimator:

```
P_t = A_t * exp(e_t),    e_t ~ Normal(mu, sigma^2)  i.i.d. across quarter-hours
c_hat_t = 1 - G_t / P_t
```

- **Q1 sets `mu = 0`.** That is *median*-unbiased: `median(P) = A`. It is not
  mean-unbiased — `E[P] = A·exp(σ²/2)` — and the alternative convention
  (`mu = −σ²/2`) is deliberately **not** used, so that Q1 carries variance only and
  every bias lives in Q2's dial where it can be read off.
- **Q2 sets `mu = b`** from its own grid, crossing with σ on a reduced grid.

**Seed.** The noise draw uses `seed = 42 + 1000·round(1000·σ) + round(1000·b)`, so a
cell's noise is reproducible and independent across grid points, and the generator's
own seed is untouched.

---

## 3. Q1 — the variance dial

**Noise grid, seven levels, fixed now:**

| σ | what it is |
|---|---|
| **0.000** | **Anchor Z**, exact. Must reproduce P3 Arm O. |
| 0.033 | half of Anchor H: better than anything in this repo |
| **0.066** | **Anchor H**, the statutory projection |
| 0.120 | between H and T |
| **0.180** | **Anchor T**, the TSO day-ahead forecast |
| 0.250 | beyond T, at the matched-sample T of 0.227 |
| 0.350 | well beyond T |

Seven levels, spanning zero to beyond Anchor T, with T and H as named points, as the
brief requires. Anchor W, when P2 measures it, is expected to fall between H and T and
can be read off the curve without re-running.

**Cells.** Arm D's design exactly: 2 generator configurations (`homogeneous`, `split`)
× 3 censoring rates {0.10, 0.20, 0.40} × 3 γ {0, 0.5, 1} × 3 shapes {step, logistic,
half} × seed 45 = **54 cells per noise level, 378 cell-runs, 2,646 rows.**

**A secondary arm, reported and deciding nothing: correlated noise.** The primary
grid is i.i.d. across quarter-hours. A real potential estimator's error is not:
`artifacts/P0/p0_planning_recompute.csv` measures the within-day lag-1
autocorrelation of the day-ahead forecast error at **0.989**. Because the binding
term in P3 was the spread of ĉ *between quarter-hours the design cannot tell apart*,
i.i.d. noise should be the worst case and correlated noise should widen the intervals
less. **One extra arm runs at Anchor T's σ = 0.180 with AR(1) noise at ρ = 0.989**,
reported beside the i.i.d. result. Stated now as a prediction: correlated noise
widens less. It changes no threshold and decides nothing.

**Reported per noise level:**

1. **Coverage of the known truth** — the guard rail, hard rule 4. Below 95% at a
   level, the bounds are broken there and **no width from that level is reported**.
2. Median and interquartile interval width per functional.
3. Share of cells where each functional is **informative** (§5).
4. **Pooled-response rejection rate**: in the `split` cells, how often a single
   common response function falls outside the identified set. P3 measured 53 of 80
   with an exact share and 0 of 54 with a fitted one.
5. The ratio of the irreducible floor to the total residual, so Arm D's mechanism can
   be traced across the dial.

**Dead end.** If every functional is uninformative at every level **including σ = 0**,
the port does not reproduce Arm O and something is wrong in it. Stop and report; do
not interpret. At σ = 0 the expected result is P3 Arm O's: λ₁–λ₄ and λ₆ pinned to
about 10⁻⁵ on step and half, λ₇ wide.

---

## 4. Q2 — the bias dial, then the two crossed

**Bias grid at σ = 0, five levels, fixed now:**

| b | what it is |
|---|---|
| −0.100 | twice Anchor H's bias |
| **−0.047** | **Anchor H's measured bias** |
| 0.000 | unbiased |
| **+0.033** | **Anchor T's measured bias** on the matched sample |
| +0.100 | beyond T |

54 cells each = **270 cell-runs**.

**The crossed grid, reduced:** σ ∈ {0, 0.066, 0.180} × b ∈ {−0.10, 0, +0.10} = 9
combinations × 54 cells = **486 cell-runs**.

**The question it settles, stated before the answer.** If **variance** drives the
floor, only a better weather model or a true measured availability helps, and Q3/Q4
(ERCOT, AEMO) are the route. If **bias** drives it, a bias-corrected potential helps
and P2 is the route. Q2 reports which dominates, with the crossed grid as evidence,
**and states plainly if neither dominates or if the two are not separable on this
design** — which is a permitted outcome, not a failure.

---

## 5. The informativeness threshold and the headline statistic

**A functional is `informative` in a cell when its interval width is below 0.25 of
its logically maximal width.**

| functional | logically maximal width |
|---|---|
| λ₁, λ₂, λ₃, λ₄, λ₇ | 1.0 (a response is a fraction in [0, 1]) |
| λ₆ = λ₃ − λ₄ | 2.0 (a difference of two such) |
| λ₅ | `l5_energy_full_gwh`, the energy if the cohort responded fully |

**0.25 is a judgement, fixed before any Q1 number.** The reasoning, recorded so it is
not reconstructed later: an interval spanning a quarter of the possible range still
separates "most of the exposed fleet switches off" from "little of it does", which is
the distinction the thesis makes claims about; at a half it separates nothing worth
stating. It is not tuned to any result and must not be revisited after one.

**The headline statistic — the number this phase exists to produce:**

> **σ\*** = the largest noise level in the Q1 grid at which **λ₁**, the fleet response
> on the most populated depth band, is informative in **at least half** of the 54
> cells.

λ₁ is the fleet response in the price band (−20, −5], and it is the most populated
band by construction: median 3,347 exposed quarter-hours per cell against λ₂'s 1,132
(`artifacts/P3/p3_synthetic_arm_d.csv`, `n_qh_lam`).

σ\* is reported with Anchor T (0.180) and Anchor H (0.066) beside it, so the sentence
it supports is either "a potential as good as the TSO forecast is enough" or "it is
not, and here is what would be". If λ₁ is informative at **no** level including σ = 0,
the dead-end rule of §3 applies and σ\* is reported as undefined rather than as zero.

**A second statistic, reported, not the headline:** the largest σ at which the
pooled-response rejection rate in `split` cells stays above half. That is the
condition under which the test of a single common response — which P3 found dies with
an estimated share — becomes possible again.

---

## 6. Seeds, counts, solver rule

| | |
|---|---|
| generator seed | 45, as Arm D |
| noise seed | `42 + 1000·round(1000·σ) + round(1000·b)` |
| bootstrap | paired event-day block, 5,000 draws, seed 42, Berlin-local days, no shuffling |
| Q1 | 7 levels × 54 cells = 378 runs, plus one correlated-noise arm of 54 |
| Q2 | 5 bias levels × 54 = 270, plus 9 crossed × 54 = 486 |
| solver | CLARABEL; `optimal` and `optimal_inaccurate` accepted and counted separately; an empty set is reported as `infeasible_below_within_row_floor`, never widened |
| coverage tolerance | `1 × 10⁻⁶` relative, as P3 |
| ε | the 95th percentile of the RMS residual over event-day resamples, as P3 §0.1 |

---

## 7. What would invalidate this pre-registration

- Any change to §§2–6 after the first Q1 number exists, without a dated written
  decision kept beside the superseded wording.
- A grid level, threshold or informativeness fraction chosen or moved with sight of a
  result.
- A width reported from a noise level whose coverage fell below 95% (hard rule 4).
- A number in a Q note that `tests/test_reported_numbers.py` does not reproduce.
- A figure quoted from a partial run (hard rule 20).

## 8. What this pre-registration does not settle

1. **Anchor W does not exist**, so the dial has no measured weather point. The grid
   leaves room between H and T where one would fall.
2. **Anchor H rests on 55 event-days** and two months, against Anchor T's 392 days.
   The like-for-like comparison of §1.3 is on those 55 days and inherits their
   narrowness; its CI on σ for the forecast, [0.168, 0.287], is correspondingly wide.
3. **TenneT is excluded from Anchor H** and the exclusion is a precondition inherited
   from T-D(vii), not a finding of this phase.
4. **The noise is multiplicative and lognormal.** A real potential estimator's error
   is not exactly that; the correlated-noise arm probes one departure (time
   structure) and no arm probes dependence on wind level.
5. **Q1 and Q2 are synthetic.** They say what accuracy *would* buy on a benchmark
   whose cohort structure is fully identified. The real panel is worse on every axis
   measured in P3, so σ\* is an optimistic bound on what the same accuracy would buy
   in Germany.
