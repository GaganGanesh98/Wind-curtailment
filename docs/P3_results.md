# P3 — partial identification: what aggregate data can and cannot tell

**Section 0 was written and committed on 15 November 2026 BEFORE any P3 number
existed.** It records the decisions that `docs/P0_preregistration.md` section 7 left
open, each with its reason, so that none of them can be read as having been chosen
once the answer was visible. Sections 1 onwards are filled from the runs that follow
that commit. Pre-registration commit: **`1cd4b30`**, recorded in every P3 artifact.

The question, from the Phase P brief: **what can aggregate data identify about the
cohort responses, and what does it leave as an interval?**

---

## 0. Gaps in the pre-registration, filled before any number

`docs/P0_preregistration.md` section 7 fixes the programme — the constraint set, the
six functionals, and ε as the 95th percentile of the bootstrap residual norm. Eleven
implementation decisions it does not fix are settled here. None of them relaxes a
threshold or changes a criterion; each follows the repo's practice in
`docs/09` section A3.2, where the same thing was done for T-B.

**0.1 The norm is the root mean square.** `‖v‖ = sqrt(mean(v²))`. P0 wrote
`‖X r − ĉ‖ ≤ ε` without naming one. RMS is scale-free in the number of
quarter-hours, so ε is comparable between a month with 492 of them and one with 10;
the Euclidean norm would grow as √T and make every cross-arm comparison a statement
about sample size. Because ε is a percentile of the *same* functional under the
bootstrap, the choice cancels — what matters is that the two agree, and by
construction they do.

**0.2 Only exposed quarter-hours are rows.** Where no cohort is exposed the design
row is zero and the model predicts `c = 0` identically, whatever `r` is — the
exposure-mask identity that `docs/09` Amendment 1 calls "cannot fail". Keeping those
rows would constrain nothing about `r` while inflating the residual with stage-A
noise, which would quietly loosen ε and widen every interval.

**0.3 The depth grid.** Bins on depth below each cohort's own threshold, edges at
0, then 2 €/MWh steps to 50, then 60, 75, 100, 150, ∞. The 2 €/MWh lattice to 50 is
M2's reservation-depth resolution (`docs/09` section 6), reused rather than
reinvented; beyond 50 the quarter-hours thin out and the lattice coarsens with them.

**0.4 Two run-length levels, split at the arm's own median.** The brief requires
monotonicity in run length, so run length must be a dimension of `r`. Two levels, split
at the median run length over that arm's exposed quarter-hours, so the split is a
property of the arm rather than a hand-picked hour count. Where the median does not
split the sample the design falls back to one level and says so.

**0.5 The band functionals are read on PRICE.** P0 section 7 writes λ₁ as "fleet
response at depth band (−20, −5]" and the numbers −20 and −5 are the brief's price-band
edges. On this panel θ ≤ 0, so depth and |price| nearly coincide, but "nearly" is not
a definition: λ₁ is the mean of `c` over exposed quarter-hours with **price** in
(−20, −5], and λ₂ the same at **price** ≤ −50.

**0.6 The cohort names on synthetic data.** P0's λ₃ and λ₄ name real MaStR cohorts,
which do not exist in `synthetic.py`'s placeholder set. The synthetic arms use the
placeholder analogues: λ₃ → `wind2016_2020_6h` (the largest non-collinear cohort,
30%), λ₄ → the exactly collinear group `pre2016_out_of_support` + `post_feb2025_qh`
(25%, the pair `docs/12` section B identifies as structurally indistinguishable).

**0.7 A seventh functional is added: λ₇, one member of the collinear group alone.**
P0's λ₄ is the group; λ₇ is `out_of_support` by itself (synthetic:
`pre2016_out_of_support`). Reported, and part of the coverage statistic like the
others. The reason it is worth adding: λ₄ against λ₇ is the same capacity read as a
group and as one of its two members, which turns "the combination is identified and
the split is not" from an assertion about matrix rank into two numbers. Adding a
reported quantity relaxes nothing.

**0.8 Two synthetic arms, and only the first carries the ≥ 95% target.**
**Arm O** sets `ĉ = c_true`, so the only error is the discretisation and the
geometry; this is the arm that tests the *bounds*, and the pre-registered ≥ 95%
coverage target applies to it. **Arm D** sets `ĉ = 1 − G/Â` with Â the shared
cross-fitted stage A, which is what real data gives; its coverage is reported and a
shortfall there is attributable to stage A, whose −1.19 pp offset `docs/06` already
quantifies. Arm D runs on a reduced cell grid because it needs five torch fits per
cell; the reduction is stated with its numbers.

**0.9 The truth is the functional's true value, not its binned projection.**
Coverage asks whether the interval contains `λ′r*` evaluated at the generator's
**per-quarter-hour** response `r*(k, t)`, not at the best representation of `r*` on
the depth grid. Discretisation error therefore counts against coverage, which is
right: it is part of the method's error, not a free pass.

**0.10 λ₅ is a lower bound where the counterfactual leaves the observed support.**
Moving a cohort's threshold to 0 makes it exposed wherever the price is negative and
deepens its depth to |p|, so the counterfactual asks about (depth, run) cells the
cohort never occupied. Those coefficients are clamped to its deepest occupied bin.
By monotonicity the true response there is at least the clamped one, so the whole
interval is a lower bound whenever coverage < 1, and the clamped share of the energy
is reported with every figure. Inventing a column for an unvisited cell would report
a number the data cannot support.

**0.11 The real-data arm is ex post (T1), and its potential is the published
forecast.** P3 on real data is a structural identification question, not a forecast,
so the published monthly Netztransparenz market value is the correct input to θ
(`docs/06` section 3; the same choice T-D makes). The forecast-time allow-list in
`src/postauction/leakage.py` governs Phase P *models* and is not in tension with it.
`ĉ = 1 − G/F` uses the published day-ahead forecast as the potential: a crude
stand-in, named as one everywhere it appears. A stage-A Â on the real panel needs the
adapter that `docs/P0_preregistration.md` section 10.3 flagged as untracked, and
Phase P has not adopted another session's uncommitted file. A sensitivity with ĉ
recalibrated by its own mean on price > 5 €/MWh quarter-hours is reported beside it.
ĉ moves where the identified set sits; it is the design X, the constraints and ε that
decide how wide it is.

## 1. Headline

**Five findings. The first two are about the method, the last three about the data.**

1. **The bounds contain the truth in 1,127 of 1,127 scored cell-functionals on the
   synthetic benchmark — 100% against a pre-registered target of 95%.**
   (`artifacts/P3/p3_synthetic_arm_o.csv`, column `covered`, with `covered_one_sided`
   for λ₅ where the counterfactual is clamped.) One cell of 162 returned an empty set
   and is reported in §2.1 rather than dropped.

2. **The algebraic point-identification test disagrees with the realised width, and
   the width is right.** λ₃, λ₄, λ₅, λ₆ and λ₇ lie outside the row space of X in
   **0 of 162** cells — "not point-identified" — yet λ₃, λ₄ and λ₆ come back with
   intervals of width 1 × 10⁻⁵ on the step and half shapes. The box constraint
   `0 ≤ r ≤ 1` and monotonicity pin quantities that rank alone leaves free. Reporting
   rank as if it answered the identification question, which is what
   `docs/P0_preregistration.md` section 7 asked for, would have been wrong in five of
   seven cases.

3. **On the benchmark only one quantity is genuinely unidentified: the split of the
   exactly collinear pair.** λ₇ has median width 0.47 on logistic and **1.00 — the
   entire range — on half**, against 1 × 10⁻⁵ for everything else on the same cells.

4. **On real data nothing is identified at all.** The narrowest interval anywhere in
   the window, across three award settings and twelve months, is **0.082**
   (`artifacts/P3/p3_real.csv`). On the full window λ₁ is [0.000, 0.310], λ₇ is
   [0.000, 0.906], λ₆ is [−0.565, 0.648] and **λ₅ is [0, 839.3] GWh against a
   logically maximal 839.3 GWh** — the counterfactual bound is the whole of its own
   support and says nothing.

5. **What binds on real data is the noise in ĉ, not cohort collinearity.** The
   within-identical-row spread of ĉ accounts for **72% to 100%** of the point fit's
   residual (`p3_real.csv`, `rms_floor` ÷ `rms_point`): quarter-hours the design
   cannot tell apart carry ĉ values differing by about 0.19 RMS. No response function
   of any shape, cohort structure or regularisation could fit better, so ε is
   essentially a measurement of how noisy a per-quarter-hour `1 − G/F` is, and every
   interval inherits it. Merging cohorts, adding cohorts or sharpening θ cannot
   narrow these intervals.

**The dead-end condition is not met, and not nearly.**
`docs/P0_preregistration.md` section 7 says that if every listed quantity is
point-identified on real data the bounds add nothing and P3 is a null result. The
opposite holds: **none** of the seven is point-identified on real data.

## 2. The synthetic study

162 cells: 3 censoring rates × 3 γ × 3 response shapes × 3 seeds (45–47) × 2
generator configurations. Placeholder cohort set, 5 cohorts, exposure rank **4 of 5**
in every cell, with `pre2016_out_of_support ≡ post_feb2025_qh` exactly collinear at
**25.0% of capacity** — the structural pair `docs/12` section C identifies. Designs
carry 300 columns and 8,938–35,763 exposed quarter-hours, compressed to 143–297
distinct rows (§0.2 and the `Compressed` docstring explain why that is exact).

The `split` configuration pushes the two collinear cohorts apart by ±0.15 and moves
no other cohort, so the aggregate the data records barely changes while the quantity
P3 is asked about changes completely.

### 2.1 Coverage of the truth, Arm O (pre-registered target ≥ 95%)

`artifacts/P3/p3_synthetic_arm_o.csv`. Truth is `λ′r*` at the generator's
per-quarter-hour response, not its projection onto the depth grid (§0.9).

| functional | covered | scored | median width |
|---|---|---|---|
| λ₁ fleet response, −20 to −5 | 161 | 161 | 7.8 × 10⁻⁷ |
| λ₂ fleet response, ≤ −50 | 161 | 161 | 1.0 × 10⁻⁶ |
| λ₃ one identified cohort | 161 | 161 | 5.0 × 10⁻⁶ |
| λ₄ the collinear group | 161 | 161 | 1.3 × 10⁻⁵ |
| λ₅ counterfactual energy, GWh | 161 | 161 | 0.28 |
| λ₆ λ₃ − λ₄ | 161 | 161 | 1.5 × 10⁻⁵ |
| λ₇ one member of the group | 161 | 161 | 0.47 |
| **all** | **1,127** | **1,127** | — |

**PASS: 100.0% against a 95% target.** Coverage allows the solver's own tolerance,
declared in the runner as `TOL_COVER = 1 × 10⁻⁶` relative, which is two orders above
CLARABEL's primal accuracy and far below every non-degenerate width.

**One cell of 162 returned an empty set** — `split`, rate 0.40, γ = 1.0, step,
seed 47 — because ε (2.0836 × 10⁻⁷) fell 0.3% below the within-identical-row floor
(2.0905 × 10⁻⁷). Both numbers are at the generator's numerical noise level. Its
seven functionals are excluded from the coverage denominator and the cell is named
here rather than quietly dropped. Of the remaining 1,127 solves, 1,096 returned
`optimal` and 31 `optimal_inaccurate`; no `optimal_inaccurate` row is a coverage
failure.

### 2.2 What is identified, by response shape

Median width, both configurations pooled:

| functional | step | logistic | half |
|---|---|---|---|
| λ₁ | 0.0000 | 0.0049 | 0.0000 |
| λ₂ | 0.0000 | 0.0083 | 0.0000 |
| λ₃ | 0.0000 | 0.0278 | 0.0000 |
| λ₄ | 0.0000 | 0.0632 | 0.0000 |
| λ₆ | 0.0000 | 0.0715 | 0.0000 |
| **λ₇** | **0.0000 / 0.2250** | **0.4681** | **1.0000** |
| λ₅ (GWh) | 0.04 | 1,541 | 0.28 |

Three things this table says.

- **The shape of the truth decides how much the box constraint does.** On `step` the
  truth sits on the boundary `r = 1`, which the box pins exactly, so every functional
  including λ₇ is determined — except in the `split` configuration, where one member
  is pushed to 0.85 and comes off the boundary, and λ₇'s width jumps to 0.225. On
  `half` the truth is interior at 0.5, the box does nothing, and **λ₇ is free over its
  entire range**.
- **λ₇ against λ₄ is the P3 result.** The same 25% of capacity, read as a group and
  read as one of its two members: 1.3 × 10⁻⁵ against 0.47 on logistic, 1 × 10⁻⁵
  against 1.00 on half. Aggregate data identifies the combination and not the split.
- **ε on logistic is discretisation, not sampling.** Arm O's ĉ is exact, so a non-zero
  ε can only come from the depth grid failing to represent a response that varies
  inside a bin: ε = 0.0062 on logistic against 2 × 10⁻⁷ on step and half. Every
  logistic width in the table is that discretisation propagated, which is why they are
  non-zero and the others are not.

### 2.3 The single common response function, and width against rate and rank

**Hirth's pooled assumption against the bounds** (`pooled_err_exceeds_width`): one
response shared by every cohort, fitted by the same constrained least squares, then
compared with the truth.

| functional | misses by more than the width, homogeneous | split |
|---|---|---|
| λ₁ | 0 of 81 | **53 of 80** |
| λ₃ | 0 of 81 | **53 of 80** |
| λ₄ | 0 of 81 | **53 of 80** |
| λ₅ | 0 of 81 | **53 of 80** |
| λ₆ | 0 of 81 | **53 of 80** |
| λ₇ | 0 of 81 | 0 of 80 |
| λ₂ | 24 of 81 | 6 of 80 |

- Where the cohorts genuinely share a response, pooling is right and never leaves the
  interval. Where they differ **along the collinear direction**, pooling lands outside
  the identified set in **66% of cells** — on quantities the bounds themselves pin to
  1 × 10⁻⁵. That is the case for reporting an interval rather than a pooled point
  estimate, measured rather than argued.
- **λ₇ is the exception and it is not a reassurance.** The pooled estimate never
  escapes λ₇'s interval because that interval is 0.47 to 1.00 wide. A bound that
  nothing can escape is uninformative, not confirmatory.
- **λ₂ is at the solver's noise floor.** Its widths are the narrowest in the study
  (1 × 10⁻⁶) and its median pooled error is 4 × 10⁻⁷, so the comparison there is
  between two numbers at the limit of the solve and is not a finding either way.

**Width against censoring rate** (median, all shapes): λ₇ falls from 0.489 at a 10%
rate to 0.456 at 40%, λ₅ is flat at 0.27–0.31, and the pinned functionals stay at
10⁻⁶–10⁻⁵ throughout. **More censoring buys very little.** Width against exposure
rank cannot be read from this grid at all: `exposure_rank` is **4 of 5 in all 162
cells** by construction of the placeholder set, so the design offers no rank
variation. The rank of X itself moves (143–179 of 300 columns) with the censoring
rate and seed, and §1 finding 2 is the relevant statement about it — it does not
predict the width.

## 3. Real data

DE, onshore, ex post (T1). Window 2025-10-01 to 2026-09-30, **2,052 exposed
quarter-hours**, twelve months with a published monthly market value, no quarter-hour
dropped for a missing forecast or output. θ at the `low`, `main` and `high` award
settings. `ĉ = 1 − G/F`, with the recalibrated arm beside it (§0.11).
`artifacts/P3/p3_real.csv`.

### 3.1 The intervals on the full window

`main` setting, un-recalibrated. The `lo`/`hi` columns, exactly as solved:

| functional | lo | hi | width | in row space |
|---|---|---|---|---|
| λ₁ fleet response, −20 to −5 | 0.000 | 0.310 | 0.310 | yes |
| λ₂ fleet response, ≤ −50 | 0.079 | 0.857 | 0.778 | yes |
| λ₃ `pre2016_in_support_no_s51` | 0.000 | 0.648 | 0.648 | no |
| λ₄ the θ = 0 group | 0.000 | 0.566 | 0.566 | no |
| λ₅ staircase threshold → 0, GWh | 0.0 | 839.3 | 839.3 | no |
| λ₆ λ₃ − λ₄ | −0.565 | 0.648 | 1.213 | no |
| λ₇ `out_of_support` alone | 0.000 | 0.906 | 0.906 | no |

Across all three settings the widths move by at most 0.41 (λ₃: 0.524 at `low`, 0.648
at `main`, 0.938 at `high`) and no interval becomes informative. The **recalibration
sensitivity changes every width by less than 0.031**, so the crude `ĉ = 1 − G/F` is
not what produces this result.

**λ₅'s bound is the whole of its own support.** 839.3 GWh is exactly
`l5_energy_full_gwh`, the energy that would be curtailed if the cohort responded
fully at every negative-price quarter-hour. The data cannot distinguish "this cohort
never switches off" from "it always does". The same holds in nine of the ten months.

### 3.2 Why — the residual decomposition

| arm | ε | rms of the point fit | within-row floor | floor ÷ point |
|---|---|---|---|---|
| window, low | 0.234 | 0.207 | 0.194 | 0.94 |
| window, main | 0.234 | 0.206 | 0.191 | 0.93 |
| window, high | 0.232 | 0.205 | 0.182 | 0.89 |
| 2026-04 (the identifying month), main | 0.259 | 0.189 | 0.135 | 0.72 |
| 2026-01, any | 0.010 | 0.010 | 0.010 | **1.00** |

The floor is the RMS spread of ĉ **between quarter-hours whose design rows are
identical** — quarter-hours no response function can distinguish. It is 72% to 100%
of everything the point fit leaves behind. In 2026-01 the design has a single
distinct row (10 exposed quarter-hours, every θ = 0), so the floor is the entire
residual and nothing whatever can be fitted.

**The consequence is structural, not a shortcoming of this estimator.** ε is defined
from the dispersion of ĉ, ĉ is a per-quarter-hour ratio of two quantities that differ
by about 1,600 MW of forecast error on a 25 GW forecast, and the switched-off share
being estimated is of the same order. No cohort merge, no extra month and no better
θ narrows an interval whose width is set by that ratio's noise.

### 3.3 Per month, as the market premium goes to zero

Months whose exposure matrix has rank ≥ 2 — any cohort separation at all —
out of the ten months with a negative-price quarter-hour:

| award setting | months with cohort separation |
|---|---|
| low | **2 of 10** |
| main | **6 of 10** |
| high | **7 of 10** |

In the remaining months every cohort's θ is identically zero, the exactly collinear
capacity is **100% of the fleet**, and the design has exactly one cohort block: there
is one fleet response to estimate and no hierarchy of any kind. This is the same
mechanism `docs/13` section 2 reports from the distinct-θ side (θ ≡ 0 fleet-wide in 8
of 9 months at `low`, 4 of 9 at `main`, 0 of 9 at `high`); the counts differ because
that table runs over 2026-01 to 2026-09 and counts distinct θ values, while this one
runs over the MTU15 window including 2025-10 and counts the rank of the exposure
matrix. **The ordering across settings is the same and the conclusion is the same.**

April 2026 is again the identifying month: rank 7 of 8 at every setting, 492 exposed
quarter-hours, 365–398 design columns, and the lowest floor share in the study
(0.72). It is also the month `docs/09` section 4.4 and `docs/10` section 4 already
single out. **Even there, nothing is identified**: λ₃'s interval is [0, 1] at `main`.

## 4. The dead-end test

`docs/P0_preregistration.md` section 7: *"if every quantity listed in P0 is
point-identified on real data, say so; the bounds then add nothing and are reported as
a null result."*

**Not triggered.** Zero of the seven functionals is point-identified on real data at
any award setting, in any month, on any arm. The narrowest real-data interval is
0.082 and the widest spans its entire logical support. The bounds are not redundant;
they are the only honest summary available, and what they report is that the
aggregate German panel does not identify a cohort-level switch-off response.

## 5. Limitations

1. **ĉ on real data is `1 − G/F`**, not a stage-A estimate (§0.11). The recalibration
   arm shows widths moving by under 0.031, and §3.2 shows the binding term is the
   within-row spread rather than the level, so a better Â would move the intervals'
   position more than their width. It would not change finding 4.
2. **Arm O's ε is discretisation, not sampling noise.** With ĉ = c_true the bootstrap
   has nothing to resample, so §2's widths answer "what does the design determine
   exactly", and Arm D (§2.4) is the bridge to the real-data regime.
3. **The grid offers no rank variation.** `exposure_rank` is 4 of 5 in every synthetic
   cell, so the brief's "bound width against exposure-matrix rank" cannot be answered
   from it; §2.3 reports what can be said instead.
4. **The run-length dimension is thin.** Two levels split at the arm's median, and in
   the sparsest real months the median does not split the sample at all, so the design
   falls back to one level (column `run_levels`).
5. **λ₅ is a lower bound by construction wherever the counterfactual leaves the
   observed support** (§0.10). On these runs `l5_coverage` is 1.000 everywhere, so the
   clamp never binds and every λ₅ figure is exact.
6. **The real-data arm is DE and onshore only**, and covers the MTU15 window. The
   2024-01 to 2025-09 history is available and excluded by `docs/P0_preregistration.md`
   section 3.

## 6. Artifacts

| file | what |
|---|---|
| `artifacts/P3/p3_synthetic_arm_o.csv` | 162 cells × 7 functionals, oracle ĉ |
| `artifacts/P3/p3_synthetic_arm_o_summary.csv` | per-functional roll-up |
| `artifacts/P3/p3_synthetic_arm_d.csv` | derived ĉ, reduced grid |
| `artifacts/P3/p3_real.csv` | 3 settings × (window, window-recalibrated, 10 months) × 7 |
| `src/identification/bounds.py` | the SOCP, ε, row compression, the row-space test |
| `src/identification/functionals.py` | the seven coefficient vectors |
| `src/identification/run_p3_synthetic.py`, `run_p3_real.py`, `summarise_p3.py` | runners |
| `tests/test_bounds.py` | 17 tests |

Every row carries `git_head`, `run_date` and `preregistration_commit = 1cd4b30`.

---

### 2.4 Arm D — derived ĉ — `[PENDING]`

Running at the time of this commit (54 cells: both configurations × 3 rates × 3 γ ×
3 shapes, seed 45, each needing five cross-fitted torch fits for the shared stage A).
Its file is deliberately **not** committed while partial, under hard rule 20.
