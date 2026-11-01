# M2 — hierarchical reservation-depth model (HRD): pre-registration

**Written and committed 1 November 2026, before any M2 number was computed.**
Student's decisions recorded verbatim in sections 1–3 and 5; sections 4, 6 and 7 are
mine — the facts I checked before writing this down, the consequences, and the things
this document cannot settle.

**The v1.8 gate and its FAIL are untouched by this document.** E1 v2 (section 5) is a
new benchmark version, not a re-run of the v1.8 gate, and nothing here revises a v1.8
criterion, threshold or verdict.

---

## 1. What M2 is

**M2 = hierarchical reservation-depth model (HRD), frequentist form.** Two stages.

### Stage A — the latent available power

    log A_t = log F_t + g(x_t)

- Fitted on quarter-hours with **price > 5 €/MWh only** (no switch-off incentive, so
  G = A there).
- `x` = **hour-of-day Fourier terms (24 h and 12 h harmonics) × season**, within the
  T2 allow-list.
- **The same A-stage is used for ALL methods**, M2, M1 and every baseline.

### Stage r — the response

    y_t = 1 - G_t / A_hat_t

    X[t, (k,j)] = w_k * s_kt * 1[z_kt >= c_j]

- `w_k` capacity share of cohort k, `s_kt` exposure, `z_kt` depth below θ.
- Knot grid `c_j` every **2 €/MWh** up to the **training 99th percentile of depth**,
  plus an **atom at z > 0** (c = 0⁺, switches off at any positive depth) and an atom
  **"never"** (c = ∞, never switches off).
- `p_k` on the **simplex** (non-negative, sums to one) for each cohort k.

    minimise  sum_t omega_t (y_t - X_t p)^2  +  lambda * sum_k ||p_k - p_bar||^2

- `omega_t = A_hat_t^2 / Var_hat(A_hat | hour, level)`.
- `lambda` chosen by **inner event-day cross-validation inside the training window
  only**.

**Why this form is the point.** Because `p_k` is a distribution over reservation
depths and `X` accumulates indicators `1[z >= c_j]`, the fitted response

    r_k(z) = sum_{j : c_j <= z} p_kj

is the **CDF of the reservation-depth distribution** of cohort k. It is therefore
monotone non-decreasing in depth and confined to [0, 1] **by construction** — not by a
penalty, not by a parameterisation that can saturate. M1's monotone piecewise-linear
head had to be *made* monotone; here monotonicity is what the parameters mean. The
atom at ∞ is the share of capacity that does not respond at any depth, which M1 could
only represent as a curve that happens to stay low.

## 2. Identification

- **All θ = 0 cohorts are pooled into ONE block by construction.**
- Report the **rank of X** and the **per-cohort effective support** (number of
  event-days on which that cohort has exposure).
- **Cohorts without support are pooled.**

## 3. Solver, seeds, ablations, placebo

- **Solver.** cvxpy if available, else scipy SLSQP. Seed 42.
- **Ablations.** `M2-noPool` (λ = 0) and `M2-noAtom` (no z > 0 atom). **M1 is kept as
  a reference**, not as an ablation.
- **Placebo.** The implied ĉ on the 0–5 €/MWh and > 5 €/MWh price bands must be
  approximately zero; report with confidence intervals.

---

## 4. What I checked before writing this down

Four facts, verified rather than assumed, that change how sections 2 and 3 must be
implemented or read.

### 4.1 cvxpy is NOT installed — so it is scipy SLSQP

Checked: `import cvxpy` fails; scipy is 1.18.1. Section 3's conditional therefore
resolves to **scipy SLSQP, seed 42**, and that is what is pre-registered. I have not
added cvxpy: a new dependency mid-project is a decision for the supervisor, not a
silent install.

**But SLSQP is a poor fit for this problem size and that must not be discovered later.**
With a 2 €/MWh grid to a 99th-percentile depth of order 100–150 €/MWh, each cohort has
roughly 50–77 parameters; across up to 8 cohort blocks that is **400–620 variables**
under 8 equality constraints and non-negativity. SLSQP is a general-purpose
sequential-QP method, not a simplex-constrained QP solver, and at that size it can stop
at a poor point and report success.

The objective is a **convex QP with simplex constraints**, so it has an exact, cheap
alternative: accelerated projected gradient (FISTA) with Euclidean projection onto the
simplex. **Pre-registered: SLSQP is the primary solver as instructed; FISTA with exact
simplex projection is run as a cross-check on every fit, and the two must agree to a
relative objective tolerance of 1e-6.** A disagreement is reported, not resolved by
picking the better number. This guards the pre-registered choice instead of replacing
it.

### 4.2 The structural placebo in section 3 is an identity, not a test

θ is **never positive**: θ ∈ {0, −MP} with MP = max(0, AW − MV) ≥ 0. Exposure is
`s_kt = 1[price_t < θ_kt]`, so **s_kt = 0 for every cohort whenever price ≥ 0**.
Hence on both placebo bands — 0–5 €/MWh and > 5 €/MWh — every row of X is identically
zero and the structural

    c_hat_t = sum_k w_k s_kt r_k(z_kt) = 0   exactly, for all t

It cannot be anything else, for M2, for `M2-noPool`, for `M2-noAtom` or for M1. So the
placebo as written **verifies that the exposure mask is correctly zero at non-negative
prices and tests nothing about the response.** It is worth running as that identity
check, and it is pre-registered as such.

**The informative placebo is on the DERIVED ĉ = 1 − G/Â**, which is not structurally
zero and does test stage A. **Both are pre-registered**, labelled distinctly:
`placebo_structural` (an identity check, expected exactly 0) and `placebo_derived`
(the real test, expected ≈ 0 with an event-day CI).

One further limit: stage A is fitted on price > 5 €/MWh, so the **> 5 band is that
stage's own training sample**. Only the **0–5 €/MWh band is an out-of-sample placebo**,
and it is the one to read.

### 4.3 The pooling rule in section 2 is correct, and I had doubted it wrongly

My first reading was that pooling all θ = 0 cohorts would discard the run-length
separation between them. Checked against the real MaStR cohort set (8 cohorts) and
`theta_and_exposure`:

- **When MP = 0 for every cohort** (market value ≥ the highest award value, 74 €/MWh),
  all eight cohorts have θ = 0 and **exactly one distinct exposure-and-depth pattern**.
  X has rank 1 in the cohort dimension. The run-length trigger is irrelevant, because
  its only effect is to force θ to 0 where it would otherwise be −MP, and MP is already
  0. **Pooling is not a simplification here; it is the only identified specification.**
- **When MP > 0**, cohorts separate — 6 distinct θ patterns in the April 2026 regime —
  by θ level *and* by run-length trigger.

So section 2 is right as written. The concern was mine and it was wrong.

### 4.4 Cohort identification rests on 18 of 33 months — and on 1 of 9 in 2026

Computed from the real monthly market values now on disk against the cohorts' award
values (59, 62, 66, 71, 74 €/MWh):

| | months that separate cohorts |
|---|---|
| 2026 alone | **1 of 9** — April 2026 only |
| with the 2024–2025 history | **18 of 33** |

In 23 of the 33 months the market value exceeds every award value, MP = 0 throughout,
and the hierarchy collapses to a single block by 4.3. **On 2026 alone, M2's entire
cohort structure is identified by April 2026** — which is also the month with the most
negative quarter-hours (492 on 19 event-days), so the dependence is not merely nominal.

This is the strongest quantitative argument for the data extension that has been
computed so far, and it was not among the reasons given for it. It is recorded here
because it determines what M2's cohort-level results can mean: **before the extension,
M2's hierarchy is a one-month finding.**

---

## 5. E1 v2 — criteria, pre-registered

A **new benchmark version**. Reduced grid, censoring rates ≥ 10%, γ ∈ {0, 0.5, 1}, all
three r\* shapes, **fresh seeds 45–49**, and **hour-of-day Fourier terms in every
method's A-stage**. Inference is a paired event-day block bootstrap pooled over seeds,
as in v1.8.

- **(a) Integrated |r̂ − r\*|.** M2 **significantly below B3 at 8 bins on logistic**,
  and M2 **not significantly worse than B3 at 64 bins on ANY shape**.
- **(b) Structural ĉ MAE** — Σ w·s·r̂, for M2 and for B3's binned response. M2 **not
  worse than B3 on any shape**, and **better on logistic**.
- **(c) No-harm.** M2's censored-quarter-hour MAE **not significantly worse than B2**.

**M1 is reported alongside.** **The v1.8 FAIL stands** and is not revisited.

Two notes on this design, recorded now:

1. Criterion (b) compares **structural** responses on both sides. This differs from the
   v1.8 gate, which scored every method on the *derived* ĉ = 1 − G/Â for like-for-like
   comparison. Both are defensible; they are not the same test, and (b)'s result must
   not be reported as comparable with a v1.8 (b) number.
2. **Cost.** 3 rates × 3 γ × 3 shapes × 5 seeds = **135 cells**, against v1.8's 81, and
   each cell now fits M2, two M2 ablations and B3 at two bin counts in addition to the
   existing nine methods. On the measured ~170 s per 9-method cell this is of the order
   of **7–9 hours** of single-machine compute. Stated in advance so the run is scheduled
   rather than discovered.

---

## 6. Implementation details this pre-registration fixes now

Pinned before any number exists, because each could otherwise be tuned after seeing
one.

- **`Var_hat(A_hat | hour, level)`**: the residual variance of stage A on its own
  training sample (price > 5 €/MWh), binned by **hour-of-day × decile of Â**, with a
  floor at the 5th percentile of the binned variances to stop ω exploding in
  near-deterministic bins. Bins with fewer than 30 observations fall back to the
  hour-of-day marginal.
- **λ grid**: logarithmic, `1e-4` to `1e2` in half-decade steps (13 values), plus 0.
  Chosen by inner event-day 5-fold CV **within the training window only**, folds formed
  by whole Berlin-local event-days, selection on weighted squared error.
- **Knot grid**: `c_0 = 0⁺` (the z > 0 atom), then `c_j = 2, 4, 6, …` €/MWh up to the
  training 99th percentile of positive depth, then `c_∞ = ∞`. The 0⁺ atom therefore
  carries reservation depths in (0, 2).
- **`p_bar`**: the capacity-weighted mean of the `p_k` across blocks, updated within
  the fit (so the penalty shrinks blocks toward their common distribution, not toward a
  fixed prior).
- **Rank reporting**: numerical rank of the weighted design `sqrt(omega) X` by SVD with
  tolerance `max(dim) * eps * sigma_max`, reported per cell alongside the nominal column
  count.
- **Seeds**: 42 for the solver and the bootstrap; E1 v2 data seeds are 45–49 and share
  nothing with v1.8's 42–44.

## 7. What this pre-registration does not settle

1. **Whether SLSQP will converge acceptably at 400–620 variables.** The FISTA
   cross-check will reveal it. If they disagree beyond tolerance on a material fraction
   of cells, that is a finding to report and a decision to take, not something to fix by
   switching solver silently.
2. **Whether cvxpy should be added.** It would make 4.1's concern moot. Supervisor's
   call.
3. **Hirth Fig. 12 band edges remain UNRESOLVED** (`HIRTH_FIG12_MARGIN_EDGES_EUR_MWH`
   is `None`), so B3's bins at both 8 and 64 are equal-count quantile bins — my choice,
   not Hirth's, exactly as recorded in the v1.8 minute.
4. **M2 has no uncertainty quantification in this form.** It is a weighted least-squares
   fit with a ridge penalty, so it yields point estimates; the event-day bootstrap gives
   intervals for the *comparisons*, not a predictive distribution for A. M1 produced
   non-crossing quantiles and M2 as specified does not. Criterion (c) compares MAE only,
   so this does not affect the verdict, but **M2 cannot replace M1 for any
   pinball/coverage claim** and must not be presented as doing so.
5. **The real-data response shape.** 4a-response found the real contrast strongly convex
   in depth with most movement below −20 €/MWh; whether a 2 €/MWh reservation-depth grid
   resolves that adequately is an empirical question for E1 v2, not a settled one.

---

## Amendment 1 — 1 November 2026, before any M2 number

Supervisor's decisions on commit `108fef5`. Sections 1–7 stay on record unchanged;
where this amendment supersedes one, the superseded text is named.

### A1.1 Solver: cvxpy, default backend, SLSQP dropped

**cvxpy is now installed and pinned.** `cvxpy==1.9.3`, with the solver backends it
ships — `clarabel==0.11.1`, `osqp==1.1.3`, `scs==3.3.1`, `highspy==1.15.1` — all
recorded in `requirements.txt` with versions read back from `importlib.metadata`, not
guessed. Installed solvers reported by cvxpy: `CLARABEL, SCS, SCIPY, HIGHS, OSQP`.

- **Primary solver: cvxpy with its default QP solver, which is OSQP** (reported as
  instructed; confirmed by `problem.solver_stats.solver_name` on an M2-shaped problem).
- **FISTA with exact simplex projection is retained as a per-fit cross-check**, at a
  **1e-6 relative objective** tolerance. Disagreements are reported, not resolved by
  taking the better number.
- **scipy SLSQP is dropped.** Section 4.1's pre-registration of it is superseded.

**Section 4.1's concern about the 1e-6 tolerance is withdrawn.** I had flagged that
OSQP, being a first-order ADMM method, might not reach 1e-6 and so might make the
cross-check unusable. Measured on a problem of M2's shape — 6 cohort blocks × 70 knots
= 420 variables, 4,000 rows, weighted least squares plus the shrink-to-mean penalty,
block simplex constraints:

| solver | objective | relative difference vs CLARABEL | seconds |
|---|---|---|---|
| OSQP (cvxpy default) | 1.827629283 | **3.67e-09** | 0.39 |
| OSQP at eps 1e-9 | 1.827629283 | 3.67e-09 | 0.42 |
| CLARABEL (interior point) | 1.827629289 | — | 0.96 |
| SCS | 1.827629283 | 3.67e-09 | 0.35 |

OSQP agrees with an interior-point solver to **four orders of magnitude inside** the
pre-registered tolerance, with the simplex constraints satisfied to 1e-9 and exact
non-negativity. The 1e-6 cross-check is comfortably attainable. **CLARABEL is the
pre-registered fallback** if OSQP reports anything other than `optimal` on real data,
and such a substitution is reported per cell.

The 400–620 variable figure in section 4.1 stands as a statement of problem size; it
is no longer a statement of solver risk.

### A1.2 Placebo and cross-fitting

Supersedes section 4.2's scheme.

- **Structural placebo: kept, relabelled "exposure-mask identity check (cannot
  fail)".** It verifies that s = 0 at non-negative prices, which forces structural
  ĉ = 0 exactly. It is not evidence about the response and is never reported as such.
- **Stage A is cross-fitted by event-day folds.** Fixed fold assignment, **seed 42**,
  **5 folds by whole Berlin-local event-days**, the *same* assignment for every method
  and every cell, so that every quarter-hour's Â comes from a model that did not see
  its own day. Because the A-stage is shared across all methods (section 1), this
  changes Â for M1 and the baselines too, which is intended: it keeps the comparison
  like-for-like.
- **TRUE placebo:** derived **ĉ = 1 − G/Â on held-out quarter-hours with price >
  5 €/MWh**. **Pass** if the 95% event-day block-bootstrap CI contains 0 **and**
  |mean| < 1 percentage point.

  **Cross-fitting is what makes this a real test.** Section 4.2 recorded that the
  > 5 band was stage A's own training sample and therefore not an out-of-sample
  placebo. Held-out cross-fitted Â removes that objection, so the > 5 band becomes the
  primary placebo rather than a weak one. That limitation is resolved, not carried.

- **CONSISTENCY check — explicitly not a zero test.** Derived ĉ in the **0–5 €/MWh**
  band should agree, within its CI, with the model-free 4a contrast.

  From `results/15_4a_response.csv` (onshore, all F):

  | area | G/F, 0–5 band | 95% CI | implied shortfall | n QH |
  |---|---|---|---|---|
  | DE | 0.9754 | [0.9616, 0.9888] | **2.46%** [1.12%, 3.84%] | 827 |
  | 50Hertz | 0.9386 | [0.9187, 0.9568] | 6.14% [4.32%, 8.13%] | 837 |

  The figure in the decision — G/F ≈ 0.975, ≈ 2.5% — is **DE's**, and is recorded as
  the pre-registered comparator, with DE primary per spec v1.8's E2 ordering.

  **Two refinements flagged, not substituted.** (i) Â corrects the day-ahead forecast's
  own conditional bias where F does not, so the strictly comparable quantity is the
  **contrast against the > 5 band** rather than the raw ratio: 2.80% for DE. For DE the
  two barely differ, because its > 5 ratio is 1.0035. (ii) **For 50Hertz they differ a
  lot** — 6.14% raw against 3.21% as a contrast — because its > 5 ratio is 0.9697. So
  the comparator is area-specific and the ≈ 2.5% figure must not be applied to 50Hertz.

  **Hirth (2026) context — now verified rather than cited second-hand.** Table 3,
  **page 14**, pooled 2022 to August 2026, wind: the **"0 to 5 (placebo)"** band gives
  a curtailment rate of **4.2%** (1,129 hours, 29 TWh potential, 1.2 TWh curtailed),
  and the **"above 5 (placebo)"** band **−0.37%**. **Hirth labels both bands "placebo"
  himself**, which is the same construction as this section — independent support for
  the design, not merely a number for context.

  **An agreement worth recording.** Hirth's above-5 placebo is **−0.37%**; this
  project's DE onshore > 5 figure is **−0.35%** (G/F 1.0035). Two different datasets,
  two different methods, 0.02 percentage points apart. The two figures are
  **consistent**. That is the whole of the claim: it is **not a validation** of
  either, since neither is a measurement of the other and agreement between two
  descriptive statistics on overlapping data cannot validate a method. What it does
  usefully is set the scale for what "≈ 0" should mean on this band, which makes the
  pre-registered 1-percentage-point bound loose rather than tight.
  *(Wording corrected 1 Nov 2026 per the noise-audit minute: "validation"/"external
  check" replaced by "consistent".)*

### A1.3 Framing: what M2 claims

- **Primary claim: a fleet-level reservation-depth response with known exposure.** This
  is what M2 is for, and what its results are reported as.
- **Cohort-level responses are secondary**, and are **reported only for the months
  where the rank condition holds.** Per section 4.4 that is **18 of 33 months**, and
  they are listed here so the claim cannot later be widened silently:

  **2024:** 01, 02, 03, 04, 05, 06, 07, 08, 09, 10, 12 — eleven months
  **2025:** 04, 05, 06, 08, 09, 10 — six months
  **2026:** 04 — one month

  (2024-11, 2025-01, 02, 03, 07, 11, 12 and 2026-01, 02, 03, 05, 06, 07, 08, 09 all
  have a market value above every award value, so MP = 0, θ = 0 for every cohort, and
  the cohort dimension of X has rank 1.)

  On 2026 alone the cohort claim rests on **April 2026 only**. Any cohort-level
  statement must name the months that identify it.

---

## Amendment 2 — criterion (c) settled: the ex-post structural recovery

**Supervisor's decision. Written 1 November 2026, before any M2 number.**

**Recorded gap:** this amendment did not exist when Amendment 3 was committed
(`81996c4`), whose section 0.3 refers to "the like-for-like ex-post recovery
comparison (Amendment 2)". That reference was reproduced verbatim without noticing it
pointed at nothing. The omission is mine; it is written up here rather than quietly
back-filled, and Amendment 3's text is unchanged.

### A2.1 What criterion (c) is scored on

The question flagged on commit `05485aa` is settled. **M2's A-estimate for scoring is
the structural recovery**

    A_hat_recovered = G_t / (1 - c_hat_t)

not stage A's prediction.

**The original rationale for this is WITHDRAWN (1 Nov 2026).** It read: "Scored on
stage A the criterion is vacuous: stage A is shared by every method and B2 (deletion)
*is* a fit on the uncensored sample, so M2 and B2 would be bit-identical and the test
would tie by construction." **That premise is false.** `fit_b2` and `fit_b3` call
`_fit_plain` (torch quantile head, forecast + weather, train/val split); `fit_m2`
calls `fit_stage_a` (cross-fitted OLS on log(G/F), hour Fourier, no weather). Measured
on cell `r10_g0.0_step_s42`, M2's stage A and B2's differ by **643.5 MW on average,
7,584.4 MW at most**. See Amendment 5.

The structural recovery is still worth scoring — it is the quantity carrying M2's
claim — but **not for the reason given**, and criterion (c) now reports both forms
(Amendment 5 A5.3).

### A2.2 Ex post only

The recovery uses the **observed** G_t, so it is a **T1 / ex-post quantity and can
never be a day-ahead forecast**. It is used for recovery scoring and for T-A, and it
is **forbidden in T-E**, where the forecast stays `G_hat = A_hat_stageA × (1 − c_hat)`
exactly as Amendment 3's 0.3 specifies. Any report of the recovery must carry the
label "ex post".

### A2.3 The 0.2 stability rule

`G/(1 − ĉ)` diverges as ĉ approaches 1, so a quarter-hour's recovery is formed **only
where `1 − ĉ_t ≥ 0.2`**, i.e. ĉ_t ≤ 0.8. Where it is not, the recovery is **undefined
and excluded from scoring**, and **the excluded count and share are reported with
every recovery result**.

*Reading recorded because the instruction was terse ("0.2 stability rule"):* the 0.2
is taken as a floor on the denominator `1 − ĉ`, not as a cap on ĉ's permitted value in
the fit and not as a shrinkage weight. The fit is untouched; this is a scoring guard
only. If a different reading was intended, it must be corrected before any M2 number
exists.

### A2.3a Correction, 1 November 2026 — shared fallback, not per-method exclusion

**Supervisor's correction, before any E1 v2 or M2 number exists.** A2.3's threshold
and its scoring-only character are **confirmed**: nothing enters the fit — no cap on
ĉ, no shrinkage, no change to the objective or the simplex constraint. Both bugs found
while implementing it stand fixed (the 1e-6 denominator floor, and the IEEE754
boundary — `ĉ ≤ 0.8` is exact, `1 − ĉ ≥ 0.2` is not).

**What changes: NaN exclusion is replaced by a shared fallback.** Excluding unstable
quarter-hours per method scores M2 and B3 on *different* quarter-hours, so their MAEs
are not comparable and the paired event-day bootstrap is ill-defined — a pair needs
both members to exist. Instead:

- For each comparison, build **one shared stability mask** over the compared methods:
  `unstable_t = OR over compared methods m of (ĉ_m,t > 0.8)`.
- `A_struct_m,t = G_t / (1 − ĉ_m,t)` where stable; `= A_hat_stageA,t` where unstable.
- Because stage A is shared and identical across methods, unstable quarter-hours
  contribute an **exact tie**, so no method can gain by falling back, and the **full
  censored sample is retained**.
- **Criterion (c) (M2 vs B2):** B2 sits at `A_hat_stageA` everywhere, so the mask is
  M2's own stability and M2 ties with B2 wherever it falls back. Non-gameable.
- The NaN array is kept as an **internal diagnostic** ("recovery undefined");
  scoring uses the fallback.
- **Report per cell:** the fallback share under the shared mask, and the share under
  each method's own rule, so it is visible whether the shared mask binds harder than
  the individual ones.

Implemented as `shared_stability_mask()`, `scored_recovery()` and
`recovery_report()` in `src/censoring/m2.py`. Four tests, including the one this
correction requires: **where unstable, the paired difference between any two compared
methods is exactly 0** — asserted with `==`, not a tolerance, since an approximate tie
would still let a method gain.

**One condition this rests on, stated so it is checked rather than assumed:** the tie
property holds *only* because stage A is bit-identical across the compared methods
(pre-registration section 1, and Amendment 3's 0.1 puts hour Fourier in every method's
stage A). If a future arm ever gave a method its own stage A, unstable quarter-hours
would stop tying and this rule would silently become gameable.

### A2.4 Like-for-like against B3

**B3 is scored on the same construction**: its binned implied response gives a ĉ, and
its recovery is `G/(1 − ĉ_B3)` under the identical 0.2 rule. So the comparison uses
one formula for both sides, as the v1.8 gate did with the derived ĉ. Reporting M2's
structural recovery against B3's *stage-A* estimate would not be like-for-like and is
not done.

---

## Amendment 3 — M2 full test, pre-registered 1 November 2026

**Committed before ANY M2 number exists.** Supersedes the earlier sequencing.
Hard rule 20 applies to every report arising from it. Sections 0.1–0.4 below are the
supervisor's decisions **verbatim**; sections A3.1–A3.3 are the sign-test thresholds
the decisions require to be stated, and the gaps I must fill to run them.

### 0.1 E1 v2 base

> E1 v2 base: built on the REBUILT panel (Stage 1), price > 5 EUR/MWh QHs as true A, as
> before. Seeds 45–49 (disjoint from 42–44). Rates {10,20,40}%, gamma {0,0.5,1}, shapes
> {step,logistic,half}. Hour-of-day Fourier (24h,12h) x season in EVERY method's stage A.

### 0.2 Methods

> Methods: M2 (HRD); M2-noPool (lambda=0); M2-noAtom (no z>0 atom); B3-CV (bins chosen
> by inner event-day CV from {4,8,16,32,64}, training data only); B3@8 (Hirth-like);
> B6 (LightGBM on depth z, cohort exposure shares, hour Fourier; monotone increasing in
> z; hyperparameters by the same inner CV; target derived c_hat = 1 - G/A_hat); B2
> (deletion). M1 is NOT refitted (retired after the v1.8 FAIL; quoted from results/12
> where relevant). Same inner-CV folds and budget for M2's lambda, B3-CV's bins and
> B6's hyperparameters.

### 0.3 Tests and verdicts

> Tests and verdicts (exact two-sided sign tests over paired cells; state the pass
> threshold count for each n in the doc):
>
> **T-A**  Main grid, criteria (a)(b)(c) as already pre-registered in docs/09, plus the
> like-for-like ex-post recovery comparison (Amendment 2). Report only; NOT the decision.
>
> **T-B  DECISIVE — sample-size arm.** Subsample censored episodes by whole event-day to
> n_event_days in {20, 50, 100, all}, nested, fixed by seed. Metric: integrated
> |r_hat - r*|. Primary: n=50. Cells per shape = rates x gamma x seeds = 45.
> PASS = M2 lower than B3-CV in >= threshold of 45 cells on logistic AND step, AND M2
> not significantly worse than B3-CV on half, AND M2 lower than B6 in >= threshold of 45
> cells on logistic AND step. Secondary: n=20 and n=100, same rule, reported. Component
> attribution: same comparisons for M2-noPool and M2-noAtom vs B3-CV.
>
> **T-C**  Robustness (reported, not pass/fail), at n=50 and n=all, seeds 45–47 only:
> (i) theta misspecification: generate with AW main, fit with AW low/high/stress;
> (ii) heterogeneous r* across cohorts (heterogeneous_r=True): per-cohort error where the
> rank condition holds; does pooling bias them?
> (iii) A-bias injection: multiply A_hat by 0.97 and 1.03 before stage r; r_hat error change.
>
> **T-D**  Real-data structural checks (T1, ex post; no forecasting), DE primary, 50Hertz
> secondary, full 2024-01..2026-09 panel:
> (i) cross-fitted placebo: derived c_hat on held-out price > 5 QHs — pass if CI contains
> 0 and |mean| < 1 pp (as Amendment 1);
> (ii) 0–5 band consistency vs 4a contrast (DE 2.80%, 50Hertz 3.21%);
> (iii) identification: rank of X and identifying months; cohort curves only where identified;
> (iv) r_hat stability across AW low/main/high (spec §3's primary real-data identification
> check): report max |delta r_hat| on the fleet curve;
> (v) fleet curtailment rate by Hirth Table 3 price bands vs Hirth's values (p.14) —
> plausibility only, "consistent / not consistent", no pass/fail.
>
> **T-E**  Test 2 (real-data day-ahead forecast) — Amendment 3 to docs/08: M2 primary
> (G_hat = A_hat_stageA x (1 - c_hat)), M1 reported if cheap else omitted with a note;
> B0, B3-G, B5 as registered; same WIN/TIE/LOSS rule. Redispatch stratifier marked
> "unavailable" for 2024-01..2025-09 if the file is still missing; it never enters as a
> feature.

### 0.4 Decision mapping

> Decision mapping (binding; reproduce in the final report):
> - **T-B FAIL** -> STOP. Data-efficiency claim withdrawn. Do not run T-E.
>   Recommendation to student: end this topic.
> - **T-B PASS, T-D(i) placebo FAIL** -> STOP before T-E; stage A is not trustworthy on
>   real data.
> - **T-B PASS, T-D(i) PASS, T-E PASS** -> CONTINUE: this is the thesis.
> - **T-B PASS, T-D(i) PASS, T-E TIE/FAIL** -> SUPERVISOR DECISION; synthetic
>   contribution stands, real-data payoff weak.
>
> T-A, T-C and T-D(ii)-(v) inform the write-up and never change the decision.

---

### A3.1 Sign-test pass thresholds, as 0.3 requires

Exact two-sided sign test against p = 0.5 at α = 0.05. The threshold k is the smallest
count whose exact two-sided p-value is below 0.05; the count one below it is shown so
the margin is visible and cannot be nudged later.

| n paired cells | pass threshold k | exact p at k | exact p at k−1 | where used |
|---|---|---|---|---|
| **45** | **30 of 45** | 0.0357 | 0.0725 | **T-B, per shape** (3 rates × 3 γ × 5 seeds) |
| 27 | 20 of 27 | 0.0192 | 0.0522 | T-C, per shape (3 rates × 3 γ × 3 seeds) |
| 9 | 8 of 9 | 0.0391 | 0.1797 | v1.8 gate (a), unchanged, for reference |

**Non-inferiority, "M2 not significantly worse than B3-CV on half" (n = 45).** B3-CV is
significantly better exactly when M2 is lower in **≤ 15 of 45** (p = 0.0357). So the
condition is satisfied when **M2 is lower in ≥ 16 of 45**. This is deliberately a weak
requirement — it is a non-inferiority clause, not a win — and it must not be reported
as evidence that M2 and B3-CV are equivalent on `half`.

### A3.2 Gaps in 0.1–0.4 that must be filled to run them, fixed here and now

Each of these is needed before a single number exists, and none is a change to a
criterion or a threshold.

1. **B6 produces ĉ, not r̂ — so T-B's metric is undefined for it as written.** T-B scores
   integrated |r̂ − r\*|, and 0.2 gives B6 the target `derived c_hat`. A response must be
   read off B6's fitted surface. **Pre-registered definition: r̂_B6(z) = B6's prediction
   at depth z with the cohort exposure shares set to full exposure (so Σ_k w_k s_k = 1)
   and the hour Fourier terms at their training-sample means.** At that point ĉ ≡ r by
   the observation model, so this reads the response at the only place the two coincide.
   It is an extrapolation of B6 to a region it may not have seen, which is a property of
   comparing a ĉ-model against an r-metric, and is reported as such.
2. **T-B isolates data efficiency only if stage A keeps its full sample.**
   **Pre-registered: the event-day subsample restricts the CENSORED episodes available
   to stage r; stage A keeps the full price > 5 €/MWh sample in every arm.** Subsampling
   both would confound response data-efficiency with latent-model degradation, and T-B's
   whole purpose is the former.
3. **"all" is not a constant n across cells.** The number of censored event-days depends
   on the censoring rate, so `n = all` differs cell by cell. **Pre-registered: `all`
   means every censored event-day in that cell, and the per-cell count is reported
   beside every `all` result.** Nesting is by a seed-fixed permutation of the cell's
   censored event-days, so n=20 ⊂ n=50 ⊂ n=100 ⊂ all by construction.
4. **M1 cannot be a paired comparator in E1 v2.** It was fitted on seeds 42–44 on the
   **pre-rebuild** panel. No E1 v2 cell matches an M1 cell, so quoting `results/12` is
   **context only** — never a paired difference, never a sign test. Stated because 0.2's
   "quoted from results/12 where relevant" could otherwise be read as licensing a
   comparison.
5. **The shared inner-CV budget is the main runtime risk.** 0.2 requires the same folds
   and budget for M2's λ, B3-CV's bins and B6's hyperparameters. M2's λ grid is 14
   values × 5 folds = **70 QP solves per fit**, against 5 bin options for B3-CV. Stage
   2.1 must estimate this before launching. **If the λ CV dominates, the only honest
   responses are a coarser λ grid pre-registered now, or a longer run — not a quiet
   reduction after seeing the clock.**
6. **Criterion (c)'s open interpretation sits inside T-A, which does not decide.** The
   question flagged on commit `05485aa` — whether (c) is scored on stage-A Â (where M2
   and B2 are bit-identical and the test is vacuous) or on the structural recovery — is
   therefore not decision-critical here. **T-A reports both**, labelled, and the
   decision rests on T-B and T-D(i) per 0.4.
7. **T-D(iv)'s stability check has power only in the identifying months.** With MP = 0
   the threshold is θ = 0 regardless of AW, so varying AW low/main/high changes nothing
   in 23 of 33 months (section 4.4). **Pre-registered: max |Δr̂| is reported both over
   the whole panel and restricted to the 18 identifying months**, since the whole-panel
   figure is diluted by months where the check is vacuous by construction.
8. **T-D(v)'s comparison is not like-for-like in period or resolution.** Hirth's Table 3
   (p. 14) pools **2022 to August 2026** on **hourly** bands; this panel is
   2024-01 … 2026-09 quarter-hours. 0.3 already restricts it to "consistent / not
   consistent" with no pass/fail; the period and resolution mismatch is stated with the
   result so the comparison is not over-read.

### A3.3 What would make this amendment invalid

- Any change to 0.1–0.4, or to A3.1's thresholds, after this commit.
- Any criterion, grid, seed or threshold modified after Stage 0 (0.4 and Stage 2.4).
- A bug fixed without re-running the affected cells **in full** and recording the bug
  and the fix in a dated minute.
- Any number reported from a provisional or partial run (hard rule 20).

---

## Amendment 4 — B3-H, the revised fail branch, and the fleet-monotonicity prediction

**Supervisor's decisions, 1 November 2026, before any E1 v2 number.** Amendments 1–3
stand; where this supersedes one, it says so.

### A4.1 B3-H: Hirth's actual bands as a new comparator

> Hirth Fig 12 edges: do NOT change B3-CV or B3@8. Add as Amendment 4 (dated, before
> any E1 v2 number): new comparator B3-H using Hirth's actual bands, exposed-side
> depth edges {0,5,10,20,50,100,inf}. Set HIRTH_FIG12_MARGIN_EDGES_EUR_MWH with a
> provenance comment: "read from raster /Image66 p.17 of 2609.10053v1; axis ticks, not
> text-extracted; [read from figure]". B3-H is reported in T-A and T-B. Pre-registered
> reading, recorded now: if M2 beats B3-CV but loses to B3-H on logistic AND step at
> n=50, the data-efficiency claim is NOT supported. (Strictly harder than the existing
> rule; no existing criterion changes.)

**Implementation note — the two instructions conflicted and had to be decoupled.**
`fit_b3` previously fell back to `HIRTH_FIG12_MARGIN_EDGES_EUR_MWH` whenever it was
not `None`. Setting the constant would therefore have **silently re-binned every
existing B3 fit**, changing B3-CV and B3@8 — the opposite of the instruction, and it
would have invalidated the comparison this amendment creates. The constant is now set
and carries the provenance comment, and `fit_b3`'s default is an explicit
`B3_DEFAULT_EDGES = None` meaning equal-count quantile bins. **B3-H is the only
method that passes Hirth's bands, and it passes them explicitly.** Two regression
tests pin this: one asserts the default stays `None`, the other asserts the two
binnings give different responses, since if they agreed B3-H would not be a distinct
comparator and the new rule would be moot.

Hirth's own six exposed-band response rates — **0.25, 0.32, 0.34, 0.45, 0.61, 0.56** —
are recorded as `HIRTH_FIG12_WIND_RESPONSE` for the T-D(v) comparison only. **They
enter no fit.**

### A4.2 Revised first branch of the decision mapping

Supersedes Amendment 3's 0.4 first branch.

> T-B FAIL -> run the FULL T-D (not just i-iii), then STOP before T-E; topic decision
> goes to the supervisor on T-B + T-D together, with the recommendation to end the
> topic. Rationale to record: the generator's MAR-given-F property makes criterion (b)
> vacuous but does NOT invalidate T-B, because T-B scores the r-side where an unbiased
> A_hat helps; nonetheless a synthetic result alone should not end a topic.

### A4.3 A non-monotone fleet response is predicted, and is not a finding

> Non-monotone fleet response: Hirth Fig 12 falls 61% -> 56% at the deepest band.
> Table 3 p.15 gives 44 h (below -100) and 64 h (-100 to -50), so treat it as probably
> noise, NOT a finding. Record as a pre-registered prediction for T-D(v)/E4: monotone
> cohort curves can yield a non-monotone FLEET curve because cohort exposure
> composition changes with depth. Report M2's predicted fleet curve against Hirth's six
> values and say whether the direction matches. Do not relax M2's per-cohort
> monotonicity.

This is a genuine prediction of the HRD structure rather than a caveat: `r_k` is a CDF
and so monotone for every cohort by construction (tested), yet the capacity-weighted
fleet curve Σ_k w_k s_k(z) r_k(z) can fall with depth, because the **exposure weights
`s_k(z)` change with depth**. If M2 reproduces a non-monotone fleet curve while every
cohort curve rises, that is the mechanism asserting itself, not a defect.

### A4.4 Positioning quote

> Positioning: quote verbatim in docs/06 and docs/07, Hirth 2609.10053 p.18: "Because
> curtailment is not observed cohort by cohort, one common response function is fitted
> across the classes."

Added to both. (The extracted text reads "coh ort"; that is a PDF text-extraction
artefact of the line break, not the paper's spelling.)

### A4.5 T-D additions

> 6. Add to T-D: validate stage A against the Online-Hochrechnung ex post (DE and per
>    area); report level ratio and correlation on uncensored QHs.
> 7. Diagnose TenneT R(>5) = 0.839 before any DE-level aggregate uses the projection:
>    check area definition, offshore inclusion, and whether SMARD's TenneT actual and
>    the projection cover the same fleet. Report findings; if unresolved, exclude
>    TenneT from aggregate validation and say so.
> 8. Label the -20 to -5 band (18 QH, 1 day, CI nan) "point estimate, no inference"
>    everywhere.

These become **T-D(vi)**, **T-D(vii)** and a reporting rule. They are possible only
because the Nr. 5.1 check now passes (spec §7, `results/39_nr51_compliance.csv`),
which makes the Online-Hochrechnung an admissible ex-post proxy for A in T1.

T-D(vii) is a precondition, not a diagnostic: **no DE-level aggregate may use the
projection until TenneT's 0.839 baseline is explained or TenneT is excluded and the
exclusion stated.** TenneT is 30.4 GW, so a silent 16% level bias there would
contaminate any fleet-level validation built on the projection.

---

## Amendment 5 — the stage-A design, pre-registered explicitly

**Supervisor's decision, 1 November 2026, before any E1 v2 or M2 number.** Prompted by
a false claim of mine in Amendment 2 and in `m2.py`, now withdrawn.

### A5.1 The finding that forced this, confirmed against the code

**CONFIRMED, not assumed.** `fit_b2` and `fit_b3` both call `_fit_plain` — a torch
quantile head on `build_latent_features` (forecast plus `weather_ms`, no hour terms,
fitted on a train/val event-day split). `fit_m2` calls `fit_stage_a` — cross-fitted
OLS on log(G/F) with hour Fourier × season and no weather. Three differences:
estimator, feature set, fitting scheme.

Measured on cell `r10_g0.0_step_s42` (`data/processed/e1_gate_artifacts/`):

| comparison | identical | mean abs diff | max abs diff |
|---|---|---|---|
| M2 stage-A vs B2 â | **no** | **643.5 MW** | 7,584.4 MW |
| M2 stage-A vs B3 â | no | 636.1 MW | 6,144.9 MW |
| B2 â vs B3 â | no | 71.9 MW | 2,329.0 MW |

### A5.2 The design

- **ONE shared stage-A array per cell**, from `fit_stage_a`, consumed by **M2, B3-CV,
  B3@8, B3-H and B6**. Rationale: these are compared on their **response** model, so
  holding Â fixed isolates it.
- **B2 keeps its own fit.** It is the Jørgensen deletion baseline; rewiring it makes it
  a different method and voids the no-harm claim.
- **Tests:** assert the shared array is bit-identical across M2/B3-CV/B3@8/B3-H/B6 in
  every cell; assert B2 does **not** consume it. Fail loudly, not silently.
- **Exact-tie property (Amendment 2 A2.3a):** holds **within the M2-vs-B3/B6 family**,
  which shares Â. It does **not** hold for **M2 vs B2**. A2.3a's conditional wording is
  replaced by this statement of fact.

### A5.3 Criterion (c) reports both forms

Criterion (c) reports **both**: the **stage-A Â form, which is the original
pre-registered one and DECIDES**, and the structural recovery alongside. If stage A
does tie, the original reads ≈ 0 and costs nothing; if it does not, a real test is
preserved. **No further rewrites of (c).**

### A5.4 A second finding the supervisor should see before E1 v2 runs

Measuring stage-A variants on the same cell against the true A, cross-fitted
identically (all-QH MAE / censored-QH MAE, in MW):

| stage-A variant | MAE all QH | MAE censored |
|---|---|---|
| **raw forecast F — no model at all** | **1,358.3** | **1,387.4** |
| hour Fourier × season — `fit_stage_a` as written | 1,367.6 | 1,412.3 |
| hour Fourier × season + weather (linear + quadratic) | 1,394.5 | 1,435.8 |
| B2's torch head (forecast + weather) | **1,212.6** | 1,256.3 |

**`fit_stage_a` is worse than the raw day-ahead forecast**, and adding weather to it
linearly makes it worse again. The likely cause is the multiplicative form: fitting
`log(G/F)` by OLS and exponentiating gives a median-like predictor of a skewed
quantity, which is biased for the mean, and a linear-in-log weather term is the wrong
functional form for a variable the torch head maps non-linearly (its correlation with
true A here is 0.915).

**Why this matters and why it does not invalidate T-B.** `y = 1 − G/Â` inherits stage
A's error, so a weak Â adds noise the response model must explain. But under A5.2 the
*same* Â is shared by M2, B3-CV, B3@8, B3-H and B6, so T-B's comparison is handicapped
**equally for all of them** and remains valid. It is the absolute quality of the
recovered response, and criterion (c) against B2, that suffer.

**Open question for the supervisor, not decided here.** Amendment 3's 0.1 says
"Hour-of-day Fourier (24h,12h) × season in EVERY method's stage A" — which reads as
*adding* hour terms to the existing stage A, not *replacing* it with an OLS that drops
weather. Three options, in my order of preference:

1. **Shared stage A = the torch head + hour Fourier** (what 0.1 literally asks for).
   At least as good as B2's, and (c) then tests the response model rather than the
   feature set.
2. Keep `fit_stage_a` but correct the log-space retransformation bias (a Duan smearing
   factor), which should recover at least the raw-forecast baseline.
3. Keep it as written and accept that (c) will fail for a reason unrelated to the
   response model — recording that reason prominently.

**Under option 3, A5.3's expectation that the stage-A form of (c) "reads ≈ 0 and costs
nothing" does not hold:** M2's stage A is ~155 MW worse than B2's on censored
quarter-hours in this cell, so (c) would register a real loss caused by the feature
set. That is the one part of the decision that should not be left to the run.
