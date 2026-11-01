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
  two different methods, 0.02 percentage points apart. That is a meaningful external
  check on the placebo band itself, and it sets the scale for what "≈ 0" should mean:
  the pre-registered 1-percentage-point bound is loose by comparison, not tight.

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
