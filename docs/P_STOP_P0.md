# P_STOP_P0 — Phase P stopped after P0: the headroom criterion is not met

**Written 14 November 2026, after the P0 recomputation and before any P1 model was
fitted.** Branch `claude/phase-p-postauction-forecasting-68cc63`, base commit
`581b75c` (gate branch `f2b601f` merged with `identification-fix` `6d389e0`).

Phase P brief, P0: *"If the recomputed best-case RMSE reduction is below 15%, STOP:
P1 has no headroom either."* Rule 10: stop and write this note when a phase's
dead-end condition is met; do not work around it. Rule 3: if a threshold looks wrong
after seeing data, stop and report, do not edit it.

Two STOP items are recorded here. The first is the dead-end condition. The second is
the reBAP ingestion, which the brief says to STOP-note and continue without.

---

## 1. The dead-end condition: best-case RMSE reduction

All numbers: `artifacts/P0/p0_planning_recompute.csv`, columns `value`, `ci_lo`,
`ci_hi`; rows selected by `area`, `series`, `quantity`. Window 2025-10-01 to
2026-10-28, 2,059 negative-price quarter-hours on 99 event-days
(`artifacts/P0/p0_event_day_counts.csv`, set `negative_all`). CIs are 95% event-day
block bootstrap, 5,000 draws, seed 42.

### 1.1 The construction behind the planning figure of 44%

The brief's planning assumption was: noise σ ≈ 1,150 MW, systematic bias ≈ −1,684 MW
in negative quarter-hours, hence RMSE ≈ √(1,684² + 1,150²) ≈ 2,040 MW, and removing
the bias leaves 1,150 MW, a 44% reduction. That is the statistic
`best_case_rmse_reduction_a_pooled_bias` = 1 − sd(e | negative) / RMSE(e | negative),
with e = G − F. It is the STOP statistic, declared as such in
`src/postauction/p0_recompute.py` before the script was first run.

| area | series | (a) pooled bias removed | 95% CI | planning |
|---|---|---|---|---|
| DE | onshore | **0.100** | [0.054, 0.165] | 0.44 |
| DE | total (onshore + offshore) | **0.078** | [0.038, 0.133] | 0.44 |
| 50Hertz | onshore | 0.107 | [0.062, 0.168] | |
| Amprion | onshore | 0.111 | [0.064, 0.177] | |
| TenneT | onshore | 0.031 | [0.001, 0.084] | |
| TransnetBW | onshore | 0.117 | [0.072, 0.168] | |

**Below 15% in every area and on both series, and the CI excludes 15% for DE total.**
The dead-end condition is met as written.

### 1.2 Why the planning figure was wrong

The planning model assumed the negative-quarter-hour error is a constant bias plus the
positive-price noise. It is not. Same file, DE onshore:

| quantity | value | 95% CI | planning |
|---|---|---|---|
| `sigma_pos_mw` — sd of e on price ≥ 0 QHs | 1,632 | [1,536, 1,728] | 1,150 |
| `sigma_pos_matched_mw` — same, reweighted to the negative QHs' forecast deciles | 1,688 | [1,585, 1,781] | 1,150 |
| `sigma_neg_mw` — sd of e on negative QHs | **3,339** | [2,157, 4,548] | — |
| `mean_bias_neg_pooled_mw` | −1,620 | [−2,431, −894] | −1,684 |
| `between_day_sd_daily_bias_neg_mw` — sd across event-days of the day's mean bias | **2,258** | [1,761, 2,707] | — |
| `within_day_sd_neg_mw_median` — median within-event-day sd | 648 | — | — |
| `rmse_F_neg_mw` | 3,711 | [2,386, 5,084] | ≈ 2,040 |
| `rho_lag1_within_day_event_days` | 0.989 | [0.985, 0.991] | 0.85 |
| `n_eff_ar1_from_rho_event_days` | 11.7 | — | — |

The negative-quarter-hour error is dominated by a **between-day** component
(2,258 MW) that is twice the size of the pooled bias it was supposed to be. Within an
event-day the error barely moves (median sd 648 MW, lag-1 autocorrelation 0.989, so
2,059 quarter-hours carry an AR(1) effective sample of about 12). Removing one pooled
constant therefore buys 10%, not 44%. The DE total series reproduces the kill test
exactly (−1,684.4 MW, CI [−2,693.6, −806.5]), so this is not a data discrepancy; the
planning arithmetic combined two numbers that do not add in quadrature.

### 1.3 Other readings of "conditional bias", reported, not substituted

The brief says "if the conditional bias were removed". Conditional on what decides the
answer, so all four readings are in the artifact:

| reading | DE onshore | 95% CI | DE total | 50Hertz onshore | Amprion onshore |
|---|---|---|---|---|---|
| (a) pooled mean — **STOP statistic** | 0.100 | [0.054, 0.165] | 0.078 | 0.107 | 0.111 |
| (b) mean per price band (4 bands) | 0.160 | [0.084, 0.280] | 0.168 | 0.172 | 0.151 |
| (c) mean per event-day — ex post | 0.465 | [0.403, 0.587] | 0.459 | 0.495 | 0.452 |
| (d) all error above the matched positive-price noise floor | 0.545 | [0.294, 0.671] | 0.567 | 0.498 | 0.438 |

Rows `best_case_rmse_reduction_{a,b,c,d}_*`. Reading (b) is what a band-haircut model
(P1's (b1)) can reach at forecast time; it clears 15% by one point with a CI that
spans 8% to 28%. Readings (c) and (d) are not reachable at 12:57 CET D−1 with the
allowed inputs: (c) uses the realised day's mean, and (d) assumes everything that is
not weather noise is predictable. Whether a model with depth, run length, exposure and
the forecast level can reach substantially more than (b) is exactly what P1 would
test; (b) is the floor of the headroom a forecast-time model has, (c)–(d) its ceiling.

**Nothing here was edited after the fact.** The statistic was chosen as (a) because
that is the construction the 44% came from, and the brief's instruction is to replace
that assumption with its recomputed value. If the student decides that the intended
reading was (b) or (c), that is a written decision to record in `docs/P0_preregistration.md`
section 4 before P1 runs; it is not made here.

### 1.4 What is NOT a dead end

- The deep test set (price ≤ −20 €/MWh) has **297 quarter-hours on 20 event-days**
  (`p0_event_day_counts.csv`, set `S2_test_deep (<= -20)`), above the floor of 15. It is
  concentrated: 12 of the 20 days are in April 2026, 5 in May, 3 in June
  (`p0_counts_by_month.csv`, column `deep_event_days`).
- P3 (partial identification) and P5 (scoping) do not depend on the headroom and are
  unaffected by this stop. P2 depends on the ERA5 key. P4 re-scores existing
  artifacts. Only P1's PASS criterion is the thing the headroom bounds.

## 2. STOP-note: reBAP cannot be ingested without credentials or a manual download

Checked 14 November 2026.

- The reBAP page (`https://www.netztransparenz.de/de-de/Regelenergie/Ausgleichsenergie/reBAP`)
  is a DNN content page with a login link and no download form fields; its data link
  goes to the data centre.
- The **official Netztransparenz Web API** (`api-portal.netztransparenz.de`) requires
  registration and OAuth2 client credentials. That is the credentialed path the brief
  names.
- The **data centre** (`datacenter.netztransparenz.de`) lists two 15-minute series,
  `reBAP überdeckt` and `reBAP unterdeckt`, EUR/MWh, first publication 2014-01-01
  (`/api/chart/data-points`, ids `DataPointreBAP überdeckt`, `DataPointreBAP
  unterdeckt`), behind a Blazor UI with an undocumented browser API. A download
  through that UI is a manual download; scripting against the undocumented endpoint
  was not attempted beyond reading the public catalogue.

**Consequence, as the brief instructs:** P1 would run **without the money-weighted
error** until one of two things happens. (i) The student downloads the two series for
2025-10-01 to 2026-10-28 at 15-minute resolution into
`data/raw/netztransparenz/rebap_2025-10-01_2026-10-28_dl<YYYY-MM-DD>.csv` (the
redispatch export already followed this manual route), or (ii) API credentials are
provided out of band and an ingest script reads them from the environment, never
from the repo. Either way reBAP stays an **evaluation weight only**; it is on the
forbidden list in `src/postauction/leakage.py` and cannot reach a model.

## 3. State of the branch at this stop

- P0 deliverables are complete and committed: `docs/P0_preregistration.md`,
  `artifacts/P0/*.csv`, `src/postauction/{common,p0_recompute,leakage}.py`,
  `tests/test_leakage_postauction.py`.
- No P1 model has been fitted. No test-set metric exists. `src/identification/` is
  an empty package.
- The decision on whether and how P1 proceeds is the student's and is listed in
  `docs/P0_preregistration.md` section 11.
