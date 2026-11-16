# P0 — Phase P pre-registration

**Written and committed 15 November 2026, before any P1–P5 model was fitted and
before any test-set metric existed.** Branch
`claude/phase-p-postauction-forecasting-68cc63`, base commit `581b75c` (the gate
branch `f2b601f` merged with `identification-fix` `6d389e0`; the merge kept the gate
branch's `gate_verdict.py`, `metrics.py`, `tests/test_gate_writer.py` and
`results/13_gate_verdict.csv` unchanged).

This file binds P1–P5. Every split, metric and threshold below is fixed **now**.
Nothing in sections 2–9 may change after the first P1–P5 test-set number exists; a
change needs a dated written decision from the student, kept beside the superseded
wording, exactly as `docs/08` and `docs/09` do it. **Every P1–P5 result file records
this file's commit hash** in a `preregistration_commit` column.

**Nothing in this document revises any existing pre-registration.** The v1.8 gate
(`docs/06` §7), its FAIL, the M2 pre-registration (`docs/09`) with Amendments 1–6,
the T-B PASS, the Test 2 pre-registration (`docs/08`) and the fallback decision
(`docs/18`) all stand untouched. Phase P is a new experiment series beside them.

---

## 1. What already exists, and what P1–P5 may reuse

Listed so nothing is duplicated (brief rule 1). Checked against the merged tree, not
remembered.

| Phase | Exists already | Where | Reused how |
|---|---|---|---|
| all | event-day block bootstrap | `src/stats_boot.py`, `src/censoring/metrics.py` (`paired_difference`, `mae_with_ci`, `paired_abs_bias`) | imported; P0 adds a sums-based resampler for statistics that are not means (`src/postauction/common.py:bootstrap_day_sums`) |
| all | window constant | `src/censoring/window.py` (`MTU15_FIRST_DELIVERY_DAY = "2025-10-01"`) | imported, not redefined |
| all | exposure / θ | `src/censoring/cohorts.py` (`theta_and_exposure`, `build_clock_features`, `mastr_cohort_set`) | called; never re-implemented, never hard-coded (brief rule 5) |
| all | real panel in the shape the fitters consume | `src/censoring/real_panel.py` — **untracked in the main checkout, not on this branch** | see §10 item 3 |
| P1 (a) | F as is | panel column `da_onshore_mw` / `da_wind_mw` | no code needed |
| P1 (c) | quantile LightGBM with price and cohort-exposure features | `src/censoring/baselines.py:fit_b5` | reused; its no-incentive counterfactual is irrelevant here because P1's target is G, which is `fit_b5`'s **direct** prediction |
| P1 (d) | M2 (HRD), shared stage A, response curve, stability rule | `src/censoring/m2.py` | reused unmodified; the P-series λ grid is declared in §6.3 rather than edited into `m2.py` |
| P1 (d) secondary | M1 | `src/censoring/model.py:fit_m1` | reused |
| P1 (b2) | isotonic regression | `scipy.optimize` / `sklearn.isotonic` (both pinned) | new 30-line wrapper in `src/postauction/` |
| P1 metrics | pinball, coverage, CRPS, PIT | `src/censoring/metrics.py` | imported |
| P3 | exposure-weighted design, rank, duplicate groups, merge | `src/censoring/identification.py` | imported; `src/identification/` holds **only** the new bounds solver |
| P3 synthetic | generator with known truth, per-cohort response offsets | `src/censoring/synthetic.py` (`SyntheticConfig.r_cohort_offsets`) | reused; new generator cells only |
| P4 | the 81 stored E1 cells, each carrying `g_obs`, `a_true`, `c_true`, `s`, `depth`, `shares`, and `a_hat_*` for nine methods | `data/processed/e1_gate_artifacts{,_merged}/` | **read-only**; P4 re-scores on G from the stored arrays and regenerates nothing |
| leakage | latent-head allow-list | `src/censoring/model.py`, `tests/test_leakage.py` | extended, not replaced, by `src/postauction/leakage.py` and `tests/test_leakage_postauction.py` |

New code in this phase: `src/postauction/{__init__,common,leakage,p0_recompute}.py`
and `tests/test_leakage_postauction.py`. `src/identification/` is created empty and
is filled only in P3.

## 2. Forecast time, and the allow-list

Forecast time is **12:57 CET on D−1**, when the SDAC day-ahead results publish.

**Allowed** (the closed set, enforced by `src/postauction/leakage.py:POSTAUCTION_ALLOWED`):
the TSO day-ahead wind forecast F; the day-ahead quarter-hour price and its calendar-hour
arithmetic mean; run lengths on both §51 clocks; per-cohort exposure `s` and depth below
θ from `cohorts.py`; capacity shares `w`; the month-to-date market value knowable by D−1
(`mv_t2_known_by_d_minus_1`, and the year-to-date series for annual-reference cohorts);
and deterministic calendar terms (hour-of-day Fourier 24 h and 12 h × season).

**Forbidden**: actual wind and any same-quarter-hour actual; the intraday forecast;
redispatch; reBAP; the published monthly Netztransparenz market value; ERA5; the
stitched Open-Meteo Historical Forecast; the Online-Hochrechnung. **reBAP is an
evaluation weight only** and is on the forbidden list so it cannot reach a model by
accident.

**Stage A of model (d) sees a strict subset**: F and the calendar terms only — no
price, no θ, no `s`, no depth, no run length, no market value (spec §4, so A cannot
absorb curtailment).

**θ's provenance is asserted, not assumed.** A Phase P θ is built from
`mv_t2_known_by_d_minus_1` and never from `read_published`; `check_theta_provenance`
enforces it. This closes the gap `docs/13` §1.3 recorded, where the feature allow-list
passed while θ could still be built on the published series.

`tests/test_leakage_postauction.py` fails on any forbidden column, on any column
outside the closed set, on price or exposure reaching stage A, and on a θ built from
the published series. **83 tests pass** across it and `tests/test_leakage.py`; the full
suite is **279 passed, 2 skipped**.

**P2 is the one exception, and it is ex post.** ERA5 is allowed in P2 and nowhere
else. P2's weather potential may never be a P1 input, and no P1 model is refitted
after P2 runs.

## 3. Window, unit of inference, splits

- **Window:** Berlin-local date ≥ **2025-10-01** (`MTU15_FIRST_DELIVERY_DAY`) to the
  end of the panel, 2026-10-28. Before that boundary all four quarter-hour prices are
  identical in 15,335 of 15,335 hours (`docs/12` §F), so exposure carries no
  sub-hourly information and the two §51 clocks coincide. **P1 and P3-on-real-data do
  not cross it.** P4 is synthetic and inherits whatever base its stored cells used,
  which is stated with every P4 number (`docs/19` §1.1b).
- **Unit of inference:** the Berlin-local event-day. All bootstraps are **paired
  event-day block bootstraps, 5,000 draws, seed 42**. 7-day embargo on rolling
  splits. No shuffling of quarter-hours, ever.
- **Target:** observed feed-in G per quarter-hour. **Primary series: onshore**
  (`act_onshore_mw` against `da_onshore_mw`), because the cohort structure describes
  the onshore fleet. The kill-test series (onshore + offshore, `act_wind_mw`) is
  reported as secondary everywhere.
- **Areas:** **DE decides.** 50Hertz and Amprion are confirmatory. TenneT and
  TransnetBW are reported. **TenneT is not significant in the kill test** (mean
  day-ahead error −325.9 MW, 95% CI [−838.3, +137.6]) and that is restated wherever
  area results appear.

The three splits, fixed:

- **S1 — leave-one-event-day-out.** Folds are the 99 negative-price event-days. For
  each fold, training excludes that day and the 7 calendar days either side of it
  (the embargo is two-sided, because an event-day's neighbours carry the same weather
  system). Scored on that day's **negative-price** quarter-hours.
- **S2 — extrapolation.** Train on quarter-hours with price **> −20 €/MWh**, test on
  **≤ −20 €/MWh**. No embargo is possible here (the split is on price, not time) and
  none is applied; the training set may contain quarter-hours on the same day as a
  test quarter-hour, which is stated with every S2 number.
- **S3 — placebo.** Positive-price quarter-hours matched to negative ones on
  **forecast decile × hour-of-day**, deciles taken on the whole window's F. Matching
  is 1:1 without replacement, nearest available cell, seed 42; cells with no positive
  match are dropped and counted. The applied correction should be **zero**.

## 4. P0's recomputation — done, and what it replaces

`artifacts/P0/p0_planning_recompute.csv`, `p0_event_day_counts.csv`,
`p0_counts_by_month.csv`, `p0_largest_error_days.csv`, written by
`python -m src.postauction.p0_recompute`.

**Disclosure of order.** These four files were computed **before** this document was
committed, at base commit `581b75c` (their own `git_head` column says so). They are
descriptive statistics of the published day-ahead forecast error on the panel — P0's
own assignment under the brief — and **not** a test-set metric of any P1–P5 model. No
model has been fitted in this phase. The rule the brief sets ("no test-set metric
before the pre-registration commit") is intact.

The planning assumptions are replaced as follows (DE, onshore, 95% event-day
bootstrap CI, 2,059 negative-price quarter-hours on 99 event-days):

| planning assumption | recomputed | 95% CI |
|---|---|---|
| σ ≈ 1,150 MW | `sigma_pos_mw` = **1,632** | [1,536, 1,728] |
| σ ≈ 1,150 MW, matched to negative-QH forecast levels | `sigma_pos_matched_mw` = **1,688** | [1,585, 1,781] |
| — | `sigma_neg_mw` = **3,339** | [2,157, 4,548] |
| ρ ≈ 0.85 | `rho_lag1_within_day_event_days` = **0.989** | [0.985, 0.991] |
| — | implied AR(1) `n_eff` = **11.7** on 2,059 QHs | — |
| bias ≈ −1,684 MW | `mean_bias_neg_pooled_mw` = **−1,620** (onshore); **−1,684** on the kill-test series | [−2,431, −894]; [−2,694, −806] |
| — | `between_day_sd_daily_bias_neg_mw` = **2,258** | [1,761, 2,707] |
| — | `within_day_sd_neg_mw_median` = **648** | — |
| "44%" | `best_case_rmse_reduction_a_pooled_bias` = **0.100** | [0.054, 0.165] |

**The pre-registered STOP statistic is reading (a)** — `1 − sd(e | neg) / RMSE(e | neg)`
— because that is the construction the 44% came from. Three further readings are
reported and none of them is the STOP statistic: (b) price-band-conditional mean
removed, **0.160** [0.084, 0.280]; (c) event-day-conditional mean removed, **0.465**
[0.403, 0.587], not reachable at forecast time; (d) everything above the matched
positive-price noise floor removed, **0.545** [0.294, 0.671], an assumption rather
than a measurement.

**(a) is below 15% in every area and on both series, so the P0 STOP condition is
met.** It is recorded in `docs/P_STOP_P0.md` and nothing was edited to avoid it. The
decision on how P1 proceeds is the student's and is §11 below.

**Event-day counts**, DE (identical by construction across areas, since the price is
the DE price):

| set | QH | event-days |
|---|---|---|
| negative (price < 0) | 2,059 | 99 |
| band (−5, 0) | 1,461 | 99 |
| band [−20, −5) | 301 | 38 |
| band [−50, −20) | 148 | 20 |
| band ≤ −50 | 149 | 12 |
| **S2 test, price ≤ −20** | **297** | **20** |
| S2 training pool (> −20) | 37,435 | 393 |
| negative with F > 40 GW (thin overlap) | 95 | 7 |
| S3 pool, price > 5 | 34,384 | 392 |
| price 0–5 | 1,289 | 139 |

The deep test set clears the floor of 15 event-days, so **P0's second STOP condition
is not met**. It is concentrated in time: 12 of its 20 days are April 2026, 5 May,
3 June (`p0_counts_by_month.csv`). 96 window quarter-hours are dropped for a missing
F or G and are reported, not filled.

**The five largest-error event-days are named now**, so P1's "without the five
largest-error days" arm cannot be chosen after seeing a result
(`p0_largest_error_days.csv`, DE onshore, ranked by |Σ e| over the day's negative
quarter-hours): **2026-04-05, 2025-10-04, 2026-04-06, 2025-10-05, 2026-09-05**. They
carry 41.1% of the total absolute negative-quarter-hour error between them.

## 5. P1 — models, metrics, verdict

**Target:** G per quarter-hour. **All five models receive the same inputs** (§2).

| id | model |
|---|---|
| (a) | F unchanged |
| (b1) | F × (1 − ĉ_band): mean haircut per price band, bands as §4, estimated on training folds only |
| (b2) | F × (1 − iso(depth, run length)): two-dimensional isotonic haircut, no cohorts |
| (c) | quantile LightGBM (`fit_b5`), direct prediction of G |
| (d) | the structured model: rule-defined exposure, monotone response, trained on G. **Primary = M2.** M1 is secondary and takes no part in pass/fail |

**Exposure is computed at three award settings** — `low`, `main`, `high` — by
`theta_and_exposure` with the real per-unit award values (`results/31_award_values.csv`,
`src/compute_theta_inputs.py`). `main` decides; `low` and `high` are reported beside
it, and the **stability of the verdict across them is a reported diagnostic**. The
`stress` setting is out of scope for P1 (it collapses 62.9% of capacity into one
cohort, `docs/12` §B).

**Metrics**, on negative-price quarter-hours unless stated: MAE; RMSE; CRPS; pinball
over τ ∈ {0.05, …, 0.95}; 80% and 90% interval coverage; bias by price band. Plus the
**money-weighted error** Σ |G − Ĝ| · |reBAP| · 0.25 h, **labelled a proxy** wherever
it appears — and **unavailable** unless reBAP is obtained (§8). Every comparison is a
paired difference with a 95% event-day block-bootstrap CI.

**Pre-registered outcome, DE primary, confirmed on 50Hertz and Amprion:**

- **PASS** — (d) lowers MAE by **≥ 25%** against (a) on S1, **and** by **≥ 15%**
  against (c) on S2, both with a 95% CI excluding zero, **and** the mean placebo shift
  on S3 is **< 100 MW** in absolute value.
- **STRUCTURE-ADDS-NOTHING** — (b1) or (b2) lies within the CI of (d) on **both** S1
  and S2. Reported plainly. The cohort structure is then not justified for
  prediction, and P3 becomes the method core.
- **PLACEBO-FAIL** — the S3 shift is **≥ 100 MW** in absolute value. P2 runs before
  anything else.

These three are not exhaustive and are not exclusive; the verdict reports which hold.
A failed criterion is reported as failed (brief rule 8).

**Also reported, deciding nothing:** S1 restricted to quarter-hours with F > 40 GW
(95 QH on 7 days — far too few to separate models, stated in advance); S1 excluding
the five event-days named in §4; and the per-band bias table.

## 6. Hyperparameters, budgets and grids

Chosen **inside the training folds only**, by inner event-day 5-fold CV, fixed
assignment, seed 42. **Identical budget across models**, fixed here:

| model | search space | size |
|---|---|---|
| (b1) | none (band means) | 1 |
| (b2) | isotonic, monotone in both arguments; 1 smoothing parameter over 14 values | 14 |
| (c) | LightGBM: `num_leaves` ∈ {7, 15, 31}, `min_child_samples` ∈ {20, 40, 80}, `learning_rate` fixed 0.05, 400 trees with early stopping at 50 | 9, extended to 14 by `n_estimators` ∈ {200, 400} on the best 5 |
| (d) M2 | λ over the **widened grid** of §6.3 | 22 |

The budget is not equal in count, because the models' spaces differ in dimension; it
is equal in **what may be searched** — no model gets a second pass, nothing is tuned
after a test-set number exists, and the chosen value and whether it sat at a grid
boundary are recorded per fit.

### 6.3 The widened M2 smoothing grid (brief rule 7)

The grid used in the 9 November T-B run was `(0.0,) + logspace(-4, 2, 13)`, whose
upper edge 100.0 was **selected in 104 of 135 M2 fits**
(`results/40_m2_lambda_boundary.csv`, main checkout) — a clipped search, not a
converged one. **The Phase P grid is:**

```
P_LAMBDA_GRID = (0.0,) + tuple(np.logspace(-6, 4, 21))
```

Two decades beyond each old positive edge, on the same half-decade lattice, so the
old 13 positive points are an exact float subset of the new 21 and selections remain
comparable; 0.0 (no smoothing) stays, and log space cannot extend below it.

**It is declared here and used by Phase P only.** `src/censoring/m2.py:LAMBDA_GRID`
is a pre-registered quantity of `docs/09` and is **not edited by this phase**; the
Phase P fitter passes its own grid. (An uncommitted widening of `m2.py` to this same
grid exists in the **main checkout's working tree**, with a `docs/22` that has never
been written. It is not on this branch, it is not Phase P's, and Phase P neither
depends on it nor touches it. Whether T-B is re-run on the widened grid is a separate
decision for the student.)

## 7. P3 — the quantities whose bounds are computed

The identified set of a linear functional λ′r of the cohort responses is

```
min / max  λ'r   subject to   ||X r − ĉ|| ≤ ε,  0 ≤ r ≤ 1,
                              r monotone non-decreasing in depth and in run length
```

with X the exposure-weighted design from `src/censoring/identification.py`.

**ε is fixed now**, before any bound is computed: ε = the **95th percentile of
‖X r̂ − ĉ‖ over the 5,000 event-day bootstrap resamples of ĉ**, computed per arm and
reported with every interval. No other ε is used, and ε is never chosen to make an
interval narrow.

**The quantities λ, named now** (brief: "examples in P0" — these are the list, not
examples):

1. **λ₁** — fleet response at depth band (−20, −5]: Σ_k w_k s_k(z) r_k(z) averaged
   over that band's quarter-hours.
2. **λ₂** — the same at depth ≤ −50.
3. **λ₃** — the response of the **pre-2016 cohort alone** (`pre2016_in_support_no_s51`,
   33.6% of capacity).
4. **λ₄** — the response of the **merged θ ≡ 0 cohort** (`out_of_support` +
   `post_feb2025_qh`, 29.3%).
5. **λ₅** — counterfactual curtailed energy if the `wind2023_feb2025_staircase`
   cohort's threshold moved to 0, over the window, in GWh.
6. **λ₆** — the difference λ₃ − λ₄, the cohort-heterogeneity contrast that Hirth's
   single pooled response cannot express.

**Synthetic first.** Generator cells in which cohort responses differ **along the
collinear directions** (`SyntheticConfig.r_cohort_offsets` set so that the merged
pair's members differ). Reported: (i) the share of cells whose bounds contain the
truth — **target ≥ 95%**; (ii) how often a point estimate under a single common
response function misses the truth by more than the bound width; (iii) bound width
against censoring rate and against the rank of the exposure matrix.

**Then real data**, per award setting (`low`, `main`, `high`) and per month. Reported:
which λ are **point-identified** (λ in the row space of X) and which get an interval,
and how that changes as the market premium goes to zero — which is the live case, since
θ ≡ 0 fleet-wide in 4 of 9 months at `main` and 8 of 9 at `low` (`docs/13` §2).

**Dead end, declared in advance:** if every λ listed above is point-identified on real
data, the bounds add nothing and P3 is reported as a **null result**, not rewritten.

## 8. P2, P4, P5 — what is fixed

**P2** runs **immediately after P1 if PLACEBO-FAIL**, otherwise after P3. The weather
potential P_t is ERA5 at MaStR turbine locations, capacity-weighted, with a fleet power
curve **fitted on quarter-hours with price > 5 €/MWh only**. Matching for the
comparison of F against P_t is on **wind level × load × solar day-ahead forecast**,
positive-price to negative-price, 1:1 nearest cell, seed 42. Reported: mean F − P_t in
matched positive-price quarter-hours with an event-day CI, against the same quantity
in unmatched positive-price quarter-hours; and a volume reconciliation on **one window,
2025-10-01 to 2026-10-28, stated with the number**, of curtailed energy from the
forecast counterfactual (F − G) against the weather counterfactual (P_t − G), each with
a CI, plus their ratio. **No explanation beyond what the matched comparison supports.**
**If the ERA5 key is missing, P2 is STOP-noted and skipped** — and it is missing today
(no `~/.cdsapirc`, no CDS credentials in the environment).

**P4** re-scores the **existing** 81 E1 cells on **G, not A**, for models (a)–(d), from
the stored `g_obs`, `s`, `depth`, `shares` and `a_hat_*` arrays. **Nothing is
regenerated** unless the cohort merge requires it. The extrapolation split is added to
the generator: train on shallow synthetic prices, test on deep. Reported: where (d)
wins, ties and loses against (b2) and (c), by response shape, censoring rate and
confounding γ. Every P4 number carries the window caveat — the merged cells' base is
61.6% pre-MTU15 (`docs/19` §1.1b).

**P5** is **scoping only**: `docs/P5_nem_scoping.md` on the AEMO NEMWeb/MMSDM tables
carrying unconstrained availability (UIGF), dispatched output and bids for
semi-scheduled wind — resolution, date range, download size, licence, effort — each
fact confirmed on the AEMO site. **No ingestion.**

**reBAP** could not be obtained without credentials or a manual download, so the
money-weighted error is **unavailable**. The finding and the two ways to close it are
in `docs/P_STOP_P0.md` §2. P1 runs without that metric and says so.

## 9. What would invalidate this pre-registration

- Any change to §§2–8 after the first P1–P5 test-set number exists, without a dated
  written decision kept beside the superseded wording.
- A hyperparameter, grid, threshold or split chosen with sight of a test-set number.
- A forbidden input reaching a model, or a θ built from the published market value.
- A number quoted from a partial or provisional run (hard rule 20).
- A result file without this file's commit hash in `preregistration_commit`.

## 10. What this pre-registration does not settle

1. **The headroom.** §4's STOP condition is met on reading (a). Whether P1 is worth
   running against reading (b)'s 16% is §11, not a conclusion of this document.
2. **ERA5.** No key, so P2 is unreachable today.
3. **`real_panel.py` is untracked in the main checkout.** It is the adapter that puts
   the real panel in the shape `fit_m2` consumes, and P1 needs it. It is not on this
   branch and Phase P has not copied it: adopting another session's uncommitted file
   silently would make its provenance unauditable. **It must be committed by its
   author, or re-derived here with that stated**, before P1 runs.
4. **Hirth Fig. 12 band edges** remain `[read from figure]` (`docs/09` Amendment 4);
   P1's (b1) uses the §4 bands, which are the brief's, not Hirth's.
5. **The 2024-01 history.** The panel runs from 2024-01-01, but §3 restricts P1 to the
   MTU15 window. The pre-MTU15 period is available to P4 and to E3-style work and is
   not used here.

## 11. The decision this document hands to the student

The P0 STOP condition is met: the best-case RMSE reduction from removing a pooled
conditional bias is **10.0%** (DE onshore), not 44%, against a floor of 15%. Under
brief rule 10 the phase stops here and does not work around it.

Three options, stated without a recommendation being acted on:

1. **Stop P1.** The forecast-time headroom on G is smaller than the brief assumed.
   P3 and P5 are unaffected and could run alone.
2. **Re-scope the P1 criterion to reading (b)** — band-conditional bias, 16.0%
   [8.4%, 28.0%] — and with it the PASS thresholds, which were set against a 44%
   premise and cannot survive unchanged. This is a change to §5 and needs a written
   decision **before** P1 runs.
3. **Run P1 as a measurement, not a test** — report (a)–(d) against each other with
   no PASS/FAIL, on the ground that the comparison between models is informative even
   where the absolute prize is small.

Whichever is chosen is recorded here as a dated section, with this one kept.
