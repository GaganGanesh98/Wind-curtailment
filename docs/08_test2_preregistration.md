# Test 2 — real-data preview: pre-registration

**Written and committed 31 October 2026, before any test-month result was computed.**
Student's decisions, recorded verbatim in sections 1–6. Sections 7–10 record the
sample sizes, the power limits and the items this document does **not** resolve.

This file binds the test. Nothing in sections 1–6 may be changed after the first
test-month number exists; any change needs a written decision from the supervisor
and a new dated section, with the superseded wording kept.

The question: **does the structured model forecast observed wind better than the
alternatives where it matters — in negative-price quarter-hours?**

---

## 1. Target and task

- **Target:** observed generation G, the same series and areas as the RQ1 kill test
  (`results/02_*`): `act_wind_mw`, onshore plus offshore, quarter-hourly.
- **Task T2 only.** The forecast is issued D-1 **after the day-ahead auction clears**,
  so the day-ahead price is known at issue time.
- **Inputs allowed:** the TSO day-ahead forecast F, the day-ahead price, calendar
  features, and θ from the rule-17 market values (≤ D-1, 7-day carry-forward).
- **Inputs forbidden:** **no weather** (no true D-1 vintages exist in this repo),
  **no intraday**, **no redispatch**, **no same-quarter-hour actuals**. The published
  monthly Netztransparenz market value stays forbidden; θ uses the rule-17 SMARD
  recomputation only.
- **Leakage tests must pass**, including θ provenance (`tests/test_leakage.py`).
- **October 2025 negative-price quarter-hours are excluded** — the 2025 monthly market
  value is missing, so θ cannot be formed for them. 199 quarter-hours on 7 event-days
  are dropped. Labelled in every output.

**Areas.** DE is primary and 50Hertz secondary, following spec v1.8's E2 order. **TenneT is NOT significant in the kill test** and must be reported as such wherever area results appear: mean day-ahead error -325.9 MW, 95% event-day CI [-838.3, +137.6], `ci_excludes_zero=False`, -3.6% of forecast (`results/02_overall_negative_qh_bias.csv`, row "TenneT DE"). It is the one control area where the kill test found no significant negative-price bias.
Amprion, TenneT and TransnetBW are out of scope here: spec v1.8 holds them back until
the Netzanschlusspunkte fix lands, and this pre-registration does not override that.

## 2. Split

- **Rolling origin by calendar month.** Test months are the 2026 months with **≥ 100
  negative-price quarter-hours**. Train on all data before the test month, **7-day
  embargo**. No shuffling.
- **Hyperparameters:** E1 settings for M1. Any tuning, for any model, only on an inner
  rolling split **inside the training window**, with the **same budget for M1 and B5**.
  Nothing is tuned on a test month.
- **Seeds 42–44** for M1 and B5; report the mean and the spread. B0 and B3-G are
  deterministic and have no seed.

## 3. Models

| name | definition |
|---|---|
| **B0** | the TSO day-ahead forecast F, as is |
| **B3-G** | F × (1 − binned curtailed share by price band), shares estimated on the training window |
| **B5** | quantile LightGBM on G, with price and cohort-exposure features |
| **M1** | Ĝ = Â × (1 − ĉ), ĉ structural (Σ w·s·r) |
| **M1-single** | the two-cohort / single-response version — the E1 fail branch — as an ablation |

## 4. Metrics — negative-price quarter-hours are primary

- MAE and bias of Ĝ on negative-price quarter-hours, pooled over test months.
- The same **by price-depth band**: [0, −5), [−5, −50), < −50 €/MWh.
- **No-harm:** MAE on all other quarter-hours.
- **Pinball and 80% coverage** for M1 and B5 (both are quantile models).
- **Stratifier only, ex post:** redispatch-affected quarter-hours versus not. Never a
  model input, never part of a verdict.
- **Paired 95% event-day block bootstrap** on MAE differences, pooled over test
  months, seed 42.

## 5. Pre-registered verdict

Per comparison (M1 vs B0, M1 vs B3-G, M1 vs B5), on the CI of (MAE_M1 − MAE_other):

- **WIN** — CI entirely < 0
- **TIE** — CI contains 0
- **LOSS** — CI entirely > 0

**PASS for the thesis question** = WIN vs B0 **and** WIN vs B3-G **and** (WIN or TIE)
vs B5, **and** no-harm (M1 not LOSS vs B0 on the other quarter-hours).

Report the event-day count per test month, and **say plainly if power is too low to
separate the models.**

> **Amendment 1 (31 Oct 2026) adds a SECONDARY verdict on a restricted set of test
> months. It does not change this primary verdict, which still decides. See
> section 11.**

## 6. Output

`results/40_test2_preview.csv`, `results/40_test2_by_band.csv`, and a one-paragraph
verdict. **Stop after reporting.** No re-runs with different settings unless the
supervisor decides in writing.

---

## 7. Sample sizes, fixed here before any modelling

Computed from `data/processed/panel_qh.parquet` (DE, 2025-10-01 to 2026-10-28) by
applying section 2's rule. These are counts, not results.

**Test months** are therefore: **2026-03, 04, 05, 06, 07, 08, 09** — seven months,
**1,820 negative-price quarter-hours on 87 event-days**. Months failing the ≥ 100 rule:
2026-01 (10), 2026-02 (23), 2026-10 (7). 2025-11 and 2025-12 have **none at all**.

| test month | training ends | training neg QH | training days | test neg QH | test days |
|---|---|---|---|---|---|
| 2026-03 | 2026-02-21 | **10** | **1** | 139 | 10 |
| 2026-04 | 2026-03-24 | **134** | 11 | 492 | 19 |
| 2026-05 | 2026-04-23 | 477 | 25 | 315 | 15 |
| 2026-06 | 2026-05-24 | 865 | 40 | 199 | 10 |
| 2026-07 | 2026-06-23 | 1,168 | 55 | 306 | 14 |
| 2026-08 | 2026-07-24 | 1,400 | 66 | 226 | 12 |
| 2026-09 | 2026-08-24 | 1,639 | 80 | 143 | 7 |

Test-month negative quarter-hours by the three reporting bands:

| month | [0, −5) | [−5, −50) | < −50 | days |
|---|---|---|---|---|
| 2026-03 | 120 | 19 | 0 | 10 |
| 2026-04 | 201 | 188 | 103 | 19 |
| 2026-05 | 202 | 71 | 42 | 15 |
| 2026-06 | 118 | 78 | 3 | 10 |
| 2026-07 | 266 | 40 | 0 | 14 |
| 2026-08 | 204 | 22 | 0 | 12 |
| 2026-09 | 125 | 18 | 0 | 7 |
| **total** | **1,236** | **436** | **148** | **87** |

## 8. Power limits, stated before the results rather than after

These follow arithmetically from section 7 and are recorded so that a weak result
cannot later be presented as a surprise, and a strong one cannot be read off an
underpowered month.

1. **2026-03 cannot identify a response.** Its training window holds **10
   negative-price quarter-hours on one event-day**. A response head r(z) fitted on one
   day is not estimated, and θ's cohort structure has nothing to separate. The month is
   still run and reported, as section 2 requires, but it is expected to be
   uninformative, and a bad M1 result there is a statement about the training window,
   not about the method.
2. **2026-04 is thin too** — 134 training quarter-hours on 11 event-days.
3. **The < −50 €/MWh band rests on two months.** 103 of its 148 quarter-hours are in
   April 2026 and 42 in May; June contributes 3 and the other four months none. An
   event-day block bootstrap on that band has roughly **2–3 usable day blocks after
   pooling**, so it will not separate models. Report it, do not rest a verdict on it.
4. **The [−5, −50) band is similarly concentrated** — 188 of 436 in April.
5. **87 test event-days in total.** The RQ1 kill test found 5 of 99 event-days carrying
   45–60% of the error, so the effective sample is a few dozen clustered episodes. CIs
   on MAE differences will be wide, and **TIE is the most likely verdict against B5**.
6. **The excluded October 2025 block is the largest pre-2026 negative-price sample**
   (199 quarter-hours, 7 days) and its exclusion is what makes 2026-03's training
   window empty. This is a consequence of the missing 2025 market value, not of the
   split design.

## 9. What this pre-registration does **not** resolve

Recorded because each is a real gap, and none may be filled from memory later.

1. **Hirth (2026) Fig. 12 band edges are UNRESOLVED [VERIFY].** The constant
   `HIRTH_FIG12_MARGIN_EDGES_EUR_MWH` in `src/censoring/baselines.py` is `None`, and
   E1's B3 uses **equal-count quantile bins** — my choice, not Hirth's. Section 3 asks
   for "Hirth-style, Fig. 12 band edges", which are not in hand, so **B3-G cannot
   comply literally.** Pre-registered fallback: **8 equal-count quantile bins on the
   training window's price-depth distribution**, matching E1's B3 default. This choice
   matters: `results/10_diag_b3_bins.csv` shows the integrated response error moving
   from 0.2507 at 4 bins to 0.0115 at 64 on the logistic shape. The bin count is fixed
   at 8 **now**, before any result, and must not be revisited after one.
   *How to close it:* read the Fig. 12 axis labels off the PDF in `docs/literature/`
   and set the constant.
2. **There is no weather input at all.** `LATENT_ALLOWED_FEATURES["T2"]` permits
   `weather_ms_icon_d1`, but no such vintage exists in the repo. M1's latent head in
   T2 therefore reduces to Â = F × exp(g(calendar)). In E1 the same head had a weather
   proxy correlated 0.6–0.9 with the true A. **So M1's scope to beat B0 on the latent
   side is much smaller here than in E1, and this test is mostly about the censoring
   and response side.** Expect the Â component to add little.
3. **θ provenance is not yet complete.** 0.55 GW across 502 units still has no award
   value, and the AW-unknown bracket cohort (item 2 of the 31 Oct priority list) is
   **not implemented**. Pre-registered choice: the **"main"** θ setting from
   `build_theta` in `src/check_rule18_real.py`, unchanged. The low/high/stress settings
   are not used for the verdict; if they are run at all it is as a labelled
   sensitivity, after the primary result is reported.
4. **Which M1 fit enters the paired bootstrap.** Section 2 asks for seeds 42–44;
   section 4 names seed 42 for the bootstrap. Pre-registered reading: the paired
   bootstrap uses the **seed-42 fit**, and the across-seed mean and spread are reported
   beside it as a robustness note. The alternative — bootstrapping the across-seed mean
   prediction — is not used, because it would mix two sources of variation in one
   interval.
5. **θ is undefined for October–December 2025, not only October.** No 2026-01 market
   value can be carried back. November and December 2025 remain usable training data
   nonetheless: both have **zero** negative-price quarter-hours, and exposure s is zero
   for every cohort whenever the price is ≥ 0 (θ ∈ {0, −MP} with MP ≥ 0, so θ ≤ 0 and
   exposure needs price < θ). θ is only needed where the price is negative.
6. **2026-10 has no market value either**, and is not in the file. It never enters this
   test: it is not a test month (7 quarter-hours) and no test month trains on data
   after September.

## 10. What would invalidate this test

- A leakage test failing, including θ provenance.
- Any input in section 1's forbidden list reaching a model.
- Any hyperparameter chosen with sight of a test month.
- Any change to sections 1–6 after the first test-month number exists, without a dated
  written decision.
- Re-running with different settings and reporting the better outcome.

---

## 11. Amendment 1 — a pre-declared secondary verdict

**Decided by the supervisor and recorded 31 October 2026, before any test-month number
was computed.** Nothing in sections 1–6 is withdrawn or reworded.

### What changes

A **secondary verdict** is added, on the test months whose **training window holds
≥ 20 negative-price event-days**. Applying that threshold to the counts already fixed
in section 7 selects:

> **2026-05, 2026-06, 2026-07, 2026-08, 2026-09** — five months.

2026-03 (1 training event-day) and 2026-04 (11) are excluded from the secondary.

The **verdict rule is unchanged** — WIN / TIE / LOSS on the CI of
(MAE_M1 − MAE_other), and PASS = WIN vs B0 **and** WIN vs B3-G **and** (WIN or TIE)
vs B5, **and** no-harm. Only the set of test months differs.

**Both verdicts are reported. The primary, over all seven months, decides.** The
secondary is evidence about *why* a primary result came out as it did, not an appeal
against it.

### Why it is worth having

The primary pools months whose training windows differ by two orders of magnitude —
10 negative-price quarter-hours for 2026-03 against 1,639 for 2026-09. If M1 loses the
primary, that pooling makes two very different explanations observationally similar:
the method does not work, or the method was never given enough data to fit a response
in the early months. The secondary separates them. If M1 loses the primary and wins
the secondary, the first explanation is the weaker one; if it loses both, the training
window is not the excuse.

### What the secondary sample is

| | primary | secondary |
|---|---|---|
| test months | 7 (2026-03 … 09) | 5 (2026-05 … 09) |
| negative-price QH | 1,820 | **1,189** |
| event-days | 87 | **58** |
| [0, −5) | 1,236 | 915 |
| [−5, −50) | 436 | 229 |
| < −50 | 148 | **45** |

### What this amendment does **not** fix

1. **It makes the deepest band worse, not better.** Dropping 2026-04 removes 103 of
   the 148 quarter-hours below −50 €/MWh, leaving **45**, of which 42 are in 2026-05
   alone. The `< −50` band in the secondary rests on essentially one month and
   **cannot support any verdict**. Section 8's warning about that band applies with
   more force here, not less.
2. **It costs a third of the event-days** — 87 down to 58. Confidence intervals on
   MAE differences widen, so the secondary is *more* likely to return TIE, not less.
   A secondary TIE where the primary is a LOSS is weak evidence for the training-window
   explanation, and must be reported as weak.
3. **It does not create power that the data lacks.** Both verdicts run on the same
   87 event-days of real negative prices, and the RQ1 finding that a handful of
   event-days carry most of the error applies to both.
4. **The selection threshold is applied to counts fixed in section 7 before any
   modelling**, so it is not a choice made with sight of results. It must not be
   revisited after a number exists.

---

## 12. Amendment 2 — training history extended to 2024-01-01

**Decided by the supervisor and recorded 31 October 2026, late, before any test-month
number existed.** Sections 1–6 and Amendment 1 stay on record unchanged. This
amendment **supersedes section 2's test-month rule**; the superseded wording is kept
below.

### What changes

- **Training history starts 2024-01-01** (section 2 previously began at the panel's
  start, 2025-10-01).
- **Test months: every month from 2024-07 onwards with ≥ 100 negative-price
  quarter-hours.** Rolling origin, 7-day embargo, no shuffling — unchanged.
- **The primary verdict is pooled over ALL test months.** The verdict rule itself
  (section 5: WIN / TIE / LOSS, and the PASS condition) is unchanged.

> **Superseded wording, section 2, kept for audit:** "Test months are the 2026 months
> with **≥ 100 negative-price quarter-hours**." Section 7's sample-size tables remain
> on record as the pre-extension state and are **not** the test set any more.

### Secondary verdicts

Two, both reported, neither deciding:

1. **QH-era months only — 2025-10 onwards.** The months whose day-ahead prices are
   natively quarter-hourly, so the §51 clock is evaluated at the resolution the rule
   is written in.
2. **Amendment 1's rule — training window with ≥ 20 negative-price event-days.**
   Which months this now selects is **not** stated here: it depends on counts that do
   not exist until the 2024-01 – 2025-09 history is downloaded and the panel rebuilt.
   It is reported in the block-9 count report, computed from the rule, before any
   modelling.

### Prices before 2025-10-01 are hourly

Day-ahead prices are hourly until 2025-10-01 and quarter-hourly from it.

- **Each quarter-hour takes its hour's price.**
- **Trigger logic uses the §51 version in force for each cohort**, from
  `data/reference/eeg_negative_price_rules.csv`. For the extended period that means:
  R02 (≥ 6 consecutive hours) for 2016–2020 wind ≥ 3 MW; R04 (≥ 4 h) for 2021–2022;
  **R06 (≥ 3 h) for the 2023 – 24 Feb 2025 cohort in calendar years 2024 and 2025**,
  stepping to R07 (≥ 2 h) in 2026; R01 (never) for pre-2016; R09 (any negative
  quarter-hour) only for units commissioned from 25 Feb 2025.
- A negative-price quarter-hour count before 2025-10-01 is therefore necessarily a
  **multiple of four** — 100 quarter-hours is 25 negative hours, the same physical
  duration as in the quarter-hour era, so the ≥ 100 threshold is consistent across
  both.

**The consequence this amendment must own.** For cohort R09 — commissioned from
25 Feb 2025, trigger "any quarter-hour with a negative spot price", price resolution
quarter-hour — the rule asks a question the data cannot answer between 2025-02-25 and
2025-09-30: with only hourly prices, a single negative quarter-hour inside an
otherwise positive hour is invisible, and an hour priced negative makes all four of
its quarter-hours exposed. In that window R09's clock **degenerates to the hourly
clock**, so its exposure is measured with error in both directions. Secondary verdict
(i) exists precisely to bound this: it restricts to the months where no such
degeneration occurs. R09 capacity is also small in that window, which limits but does
not remove the problem. This is recorded as a known measurement error, pre-registered,
not discovered afterwards.

### Unchanged

**Redispatch remains an ex-post stratifier only, never a feature**, in every verdict
and every stratum. Section 8's redispatch availability gap for 2024-01 – 2025-09 is
tracked separately: the stratifier is simply unavailable for that period until the
file arrives, and strata that depend on it are reported as unavailable rather than
imputed.

---

### Dated note to Amendment 2 — 1 November 2026: the R09 error claim is withdrawn

Amendment 2's section 12 is **not** rewritten. This note corrects one claim in it.

**Withdrawn.** Section 12 asserted that between 2025-02-25 and 2025-09-30 cohort R09's
clock "degenerates to the hourly clock, so its exposure is measured with error in both
directions". That is wrong. There is no measurement error.

**Not via § 3 Nr. 42a, though.** Checked in the buzer.de version history of EEG 2023
§ 3 (accessed 1 Nov 2026, https://www.buzer.de/3_EEG.htm and the version pages linked
from it): Nr. 42a's reference changed from `Stromstundenkontrakten` to
`Stromviertelstundenkontrakten am Day-Ahead-Markt` **with effect from 1 January
2025** — retroactively, promulgated 24 Feb 2025 — by Art. 3 Nr. 1 of the
EnWGEÜVÄndG, G. v. 21.02.2025, BGBl. 2025 I Nr. 51
(https://www.buzer.de/gesetz/16897/a321772.htm). So from 1 Jan 2025 the definition
already pointed at quarter-hour contracts, months before the market traded any. Nr. 42a
on its own therefore cannot be what makes the price hourly in that window; read alone
it points at a product that did not yet exist.

**The bridge is § 100 Abs. 45 Satz 1** (verbatim text at
https://www.gesetze-im-internet.de/eeg_2014/__100.html and
https://www.buzer.de/100_EEG.htm, both accessed 1 Nov 2026; inserted by Art. 3 Nr. 2
of the same law). For the period from 1 January 2025 up to and including the day on
which the exchanges first base the day-ahead order-book coupling on quarter-hour
contracts, the **31 December 2024 version of § 3 Nr. 42a — the hourly one — applies**
for determining the hours in which the Spotmarktpreis is negative under § 51(1). It
names the version of § 51(1) in force from 25 Feb 2025 explicitly, so it covers R09.

**So the supervisor's conclusion is confirmed: the hourly trigger for R09 in
2025-02-25 … 2025-09-30 is the law as applied, not an approximation.**

**And the reason the withdrawn claim was wrong is sharper than "the law says hourly".**
The legal spot price in that window is constant inside each calendar hour. With a
constant price, "any quarter-hour whose spot price is negative" and "the quarter-hours
of a negative hour" select **exactly the same set of quarter-hours**. The error I
claimed required a finer, quarter-hourly price to exist and go unobserved. None
existed — not in the market and not in law — so there was nothing to be in error
against, in either direction.

**Secondary verdict (i) is restated accordingly.** It is a **market-regime
comparison** — hourly-contract day-ahead market against quarter-hour-contract
day-ahead market, two genuinely different price-formation regimes — and **not** an
error bound on a degraded clock. Its purpose is to show whether the method's
performance depends on the regime, which is a question about generalisation, not about
measurement quality. Its value does not rest on the withdrawn claim.

**The statute gives a condition, not a date.** Both Abs. 44 and Abs. 45 end at "the
day the exchanges first base the coupling on quarter-hour contracts"; neither names
30 Sep or 1 Oct 2025, and no legal source consulted states the actual first coupling
day. Empirically the changeover is at delivery 2025-10-01: 745 of 745 October 2025
calendar hours show a non-zero within-hour price spread and September shows none. A
one-day ambiguity remains between the auction day (30 Sep) and the delivery day
(1 Oct). **It is immaterial here:** 2025-10-01 contains no negative quarter-hour at
all (minimum price 61.37 €/MWh) and the first negative October day is 2025-10-04, so
no § 51 determination turns on which of the two days is meant.

**One open point, now much narrower.** Whether R09's counting unit in that window is
the hour or the quarter-hour is not settled here — Abs. 45 Satz 2 is conditioned on the
applicable § 51(1) version using *hours* as the unit, which implies some versions do
not. It makes **no difference to exposure**, by the constant-price argument above, but
it may matter to **§ 51a(1)**, which extends the support period by the *number of
zeroed quarter-hours*: four per negative hour, or one. [VERIFY] — needs § 51(1) as in
force 25 Feb 2025, and § 51a. Not blocking for Test 2, which models exposure.

**Correction to `data/reference/eeg_negative_price_rules.csv`.** Its
`price_resolution_since_2025-10-01` column reads "hourly mean of the four QH prices".
Abs. 45 Satz 2 says the arithmetic mean of the Spotmarktpreise of *the quarter-hours
of that calendar hour*, with no "four". Immaterial for this project — `build_clock_features`
groups on UTC hours, and because Berlin is a whole number of hours from UTC the Berlin
calendar-hour partition is the same partition, so every hour has exactly four
quarter-hours including at DST transitions — but the table over-specifies the statute
and should not be quoted as if the number four were in it.

**Also found, and it bears on block 5 rather than on this amendment: § 100 Abs. 44.**
Satz 1 applies the hourly Nr. 42a and Anlage 1, for the same period, to the monthly
market values (Anlage 1 Nr. 3), the TSO publication duties (Nr. 5.1, 5.2, 5.4) and the
exchanges' reports to the TSOs (Nr. 6). Satz 2, for the 2025 **annual** value, sets
each quarter-hour's Spotmarktpreis to its calendar hour's hourly-contract average and
spreads the hourly Online-Hochrechnung quantity **evenly across the quarter-hours**.
That is precisely the construction under which block 5's ratio-of-sums identity holds,
so the "no 60-minute code path is needed" conclusion is not merely algebraically safe —
it is the computation the statute prescribes. Satz 3 is the mixed-month provision the
Netztransparenz PDF deferred to; it never bites here, because the changeover fell on a
month boundary.

### Precondition for Test 2, added 1 November 2026

After the panel rebuild, the block-4 negative-price flag validation **must be re-run on
the 21 months 2024-01 … 2025-09**, covering the 6H / 4H / 3H / 1H rule versions.
**Any mismatch stops Test 2 and is reported, not worked around.** The first 12 months
checked (2025-10 … 2026-09, 61 comparisons) passed with no mismatch, which is what
makes a later mismatch interpretable as a statement about the data rather than about
the trigger logic.
