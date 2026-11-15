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

## 1. Headline — `[PENDING]`

## 2. The synthetic study — `[PENDING]`

### 2.1 Coverage of the truth, Arm O (target ≥ 95% of cells) — `[PENDING]`
### 2.2 The single common response function against the bound width — `[PENDING]`
### 2.3 Bound width against censoring rate and exposure rank — `[PENDING]`
### 2.4 Arm D, derived ĉ — `[PENDING]`

## 3. Real data — `[PENDING]`

### 3.1 Which functionals are point-identified, per award setting — `[PENDING]`
### 3.2 Per month, and what happens as the market premium goes to zero — `[PENDING]`

## 4. The dead-end test — `[PENDING]`

`docs/P0_preregistration.md` section 7: if every listed quantity is point-identified
on real data, the bounds add nothing and P3 is reported as a null result.

## 5. Limitations — `[PENDING]`

## 6. Artifacts — `[PENDING]`
