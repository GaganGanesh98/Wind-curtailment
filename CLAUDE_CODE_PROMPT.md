# Claude Code task — thesis pivot to mechanism-aware censored learning

Paste this into Claude Code from the repo root:
> Read CLAUDE_CODE_PROMPT.md and carry it out, phase by phase. Stop at each STOP and report.

*Updated 30 Oct 2026 to match the repo after the RQ1 kill test and the legal verification
work. Changes since the first draft are marked **(new 30 Oct)**.*

---

## Context

This is my MSc thesis repo. The thesis is pivoting from "correct the TSO wind forecast in
negative-price quarter-hours" to **a learning method for labels censored by a
price-triggered, partial fleet switch-off**. The full spec is
`docs/06_pivot_mechanism_aware_censoring.md` (spec v1.6) — **read it completely before doing
anything**. Then read `README.md`, `docs/01_thesis_brief.md`,
`docs/04_rq1_killtest_note_v3.md`, `docs/05_eeg_rule_table.md`,
`data/reference/eeg_negative_price_rules.csv` and everything in `src/`.

### Repo state you are starting from **(new 30 Oct)**

- **The kill test is finished and the verdict is GO.** All four checks reproduce v2:
  DE negative-QH bias −1,684.4 MW, CI [−2,693.6, −806.5]; 2,059 negative QHs on 99
  event-days; and Check 2 (redispatch) confirms that grid redispatch does **not** explain
  the bias (DE excess −1,788.5 MW, CI [−2,809.8, −907.3]). Do not re-run or re-derive any
  of this.
- `src/` holds the kill-test pipeline: `smard_config.py`, `ingest_smard.py`,
  `build_panel.py`, `stats_boot.py`, `kill_test.py`, `check_da_vs_id.py`,
  `redispatch_control.py`, `make_figures.py`. `src/censoring/` and `tests/` do not exist yet.
- `results/00_*` – `04_*` are all populated, including `04_redispatch_test_c.csv`.
- `data/raw/` holds the SMARD weekly JSON (25 series × 57 weeks), the SMARD chart
  configuration, the SMARD Benutzerhandbuch 02/2025 and 04/2026, and the Netztransparenz
  redispatch export `redispatch_2025-10-01_2026-10-28_UTC_dl2026-10-29.csv`.
- `data/reference/eeg_negative_price_rules.csv` (14 rows) is the §51 rule table, built from
  the consolidated statutory texts. `docs/05_eeg_rule_table.md` explains it in plain English.
- The repo is a git repository with a private GitHub remote (`origin`), three branches of
  history already pushed. The panel itself (`data/raw`, `data/processed`) is gitignored;
  `data/reference/` is tracked.
- Environment: `.venv` on Python 3.13.13 with polars 2.1.0, pyarrow 26.0.0, numpy 2.5.4,
  matplotlib 3.11.2, requests 2.34.2.

## Hard rules

1. Never modify anything in `data/raw/`. It is append-only.
2. Never overwrite a versioned doc. Archive first (copy to a new name), then write the new version.
3. Do not change the kill-test code or results (`src/kill_test.py`, `check_da_vs_id.py`,
   `redispatch_control.py`, `results/00_*`–`04_*`) except to import shared helpers from them.
4. Every number written into a doc must come from code in `src/` that produces it into
   `results/`. No hand-typed figures.
5. **Leakage:** the intraday forecast (`id_*` columns, `e_id_mw`), redispatch data and
   same-QH actuals must never be model inputs. Enforce this with an explicit allow-list of
   feature columns and a test that fails if a forbidden column is used.
   **(new 30 Oct)** The intraday series is leakage for a second, independent reason: SMARD
   publishes no vintage, the TSOs refresh it repeatedly, and 08:00 on the delivery day is a
   stated *minimum* not a freeze time (Benutzerhandbuch 04/2026 §1.3). Treat it as a
   diagnostic and a reference point only, never a feature.
   **(new 30 Oct, spec v1.4)** The **published monthly Netztransparenz market value** is on
   this list too — it is released after the month ends. It is not a feature column: it
   reaches the model through θ (rule 17), so the allow-list test will pass while the model
   leaks. Assert the **provenance of θ's inputs per task** as well as the feature set.
6. Price features, θ and s must not enter the latent-power head g (spec §4). Test this too.
6a. Two tasks (spec §3a), each with its **own feature allow-list**. T2 (day-ahead
    forecast) must never see ERA5 or the Open-Meteo *Historical Forecast* (stitched)
    archive; only true D−1 vintages. Add a test that fails if a T1-only column reaches a
    T2 model.
7. Seed 42 everywhere. Splits by time with a 7-day embargo; CV and bootstrap blocked by
   Berlin-local event-day; never shuffle quarter-hours.
8. Keep the existing stack: polars, pyarrow, numpy, matplotlib. Add `torch`, `lightgbm`,
   `scipy` and `pytest`, pinned to the exact versions you install, in `requirements.txt`.
   CPU only. **(new 30 Oct)** Pin to what actually installs — do not guess a version number
   and write it into `requirements.txt`.
9. Do not invent citations or SMARD filter IDs. Read filter IDs from
   `data/raw/smard_market_data_configuration_2026-10-29.json`. If something cannot be
   verified, write `UNRESOLVED` and move on.
10. Do **not** write thesis or proposal prose (introduction, literature review, discussion).
    My university limits AI-written text. Code, docstrings, READMEs, result notes and
    method specs are fine.
11. Use British English in docs. Commit after each phase with a clear message.
    **Do not push** — `origin` exists, but pushing is my call.

### Rules learned the hard way in the kill test **(new 30 Oct)**

12. **Fail loudly on unmapped categorical values.** In `redispatch_control.py` the
    Netztransparenz export spelled the TSO `TenneT DE` while the mapping expected `TenneT`,
    and 7,606 measures were silently dropped — TenneT's volume read 0.0 TWh instead of
    7.4 TWh. Any time you map strings to categories, raise on an unmapped value; never
    `continue`.
13. **Cross-check every aggregate against a known figure before believing it.** If a number
    disagrees with a prior version by an order of magnitude, suspect the pipeline before
    the data.
14. **Never assert that something does not exist on the strength of a failed search.** Say
    "not found, searched X, Y, Z" and mark it `UNRESOLVED`.
15. **Log the filter chain.** Print rows in and rows out at every filtering step, with the
    reason for each drop. Two bugs in Check 2 were invisible until the drop counts were
    printed.

### Design decisions fixed in advance — do not relitigate **(new 30 Oct)**

16. **Latent head A sees the TSO day-ahead forecast and task-allowed wind features only.**
    T1 may use ERA5; T2 may use D−1 ICON vintages only. Temperature and pressure enter
    solely as air density inside the power-curve transform — never as free features. No
    calendar, no solar, no price, no θ, no s. Hour-of-day is admissible only if the I1
    placebo shows a diurnal bias **and** the E1 ablation at γ > 0 shows no loss in
    A recovery; otherwise it stays out. Extend the leakage allow-list test to cover this.
17. **Recompute the T2 market value yourself.** Derive MV_m from SMARD data available by
    D−1 per EEG Anlage 1 Nr. 3.3.2 (month-to-date; on day 1 of a month, the previous
    month's value). The published Netztransparenz Marktwerte are **validation only** and
    must never be a T2 input — they are released after the month ends. **(v1.5)** If the
    current EEG Anlage 1 puts cohorts commissioned and awarded from 2023 on the *annual*
    value, recompute that one year-to-date by D−1 as well; spec §3 [VERIFY].
18. **First check on real data: count the event-days on which the cohort exposure vectors
    s_k actually differ.** This is pre-registered: if the count is **< 10**, collapse to
    two cohorts (quarter-hour clock vs hourly clock) and say so in the results note.
    **Collapse the response, not the exposure:** s_k,t is still computed per legal cohort
    (each row of the rule table) and aggregated into each macro-cohort's exposed capacity
    share; only the response parameters r are pooled within a macro-cohort. The staircase
    cohort sits at 2 h throughout 2026, but the hourly-clock cohorts still differ by
    run-length threshold (6 h, 4 h and 2 h, per `data/reference/eeg_negative_price_rules.csv`),
    and the exposure aggregation must keep that variation.
19. **Award values are a range, not a point.** The cohort flag is "a Zuschlagsnummer is
    present", not the commissioning year. Report AW_k per cohort as a range — the rounded
    minimum and maximum award, widened by the correction-factor uncertainty. θ runs at
    three fixed settings: the **main run** uses the round's volume-weighted average award
    multiplied by the mean site-correction factor **1.226** (Hirth 2026 Table A1, from
    Fachagentur Wind und Solar 2025 — [VERIFY] at source; factor 1 understated AW by about
    a fifth); two **sensitivity runs** use the low and high ends of the correction-factor
    distribution and the bid range. Report r̂ under all three — a large spread is itself a finding about
    identification. Plants past the end of their EEG support period get θ = 0.
    **STOP** and report if the Zuschlagsnummer column is missing from the MaStR snapshot,
    or is filled for less than 50% of the **capacity** of wind units above 750 kW
    commissioned 2019–2022 or of at least 1 MW from 2023, excluding pilot plants — the group that must have
    one. Older, small and transition plants legitimately lack it, so a fill rate over all
    units means nothing. (750 kW is the EEG 2017 tender exemption; EEG 2023 sets it at 1 MW for wind,
    per UBA.) Do not substitute commissioning year for it.

## Phase 1 — docs and structure

- Copy `docs/01_thesis_brief.md` to `docs/01_thesis_brief_v1_forecast-correction.md` (unchanged).
- Rewrite `docs/01_thesis_brief.md` as v2 from the spec: new title, gap paragraph (method
  framing), RQ1–RQ4, H2–H4, method summary, baselines, experiments E1–E5, timeline,
  minimum vs stretch, backup topic. Keep v1's §2 evidence, §5 design decisions, §7 data
  pipeline, §11 contacts, §12 venues and §13 open questions where still valid. Mark changed
  sections "(v2)".
  **(new 30 Oct)** Carry forward, do not re-derive: the kill-test GO and its numbers; the
  §5 finding that TSO day-ahead forecasts are frozen ~08:00–09:00 D−1, before the 12:57 CET
  SDAC results, so they are price-blind by construction; and the §13 items already ticked
  off (14.1.D publication time, §51 trigger granularity, negative-hour counts, windy
  negative-QH count).
- Update `README.md`: title, status, new layout (`src/censoring/`, `tests/`), and
  how to run each phase.
- Create `docs/07_literature_table.md` in the column format of
  `srh-guidelines/06_instructions_to_students_for_their_thesis.txt` point D
  (No., Title, Source, Year, Comments, Methodology, Data/URL, Misc). Pre-fill only Title,
  Source and Year from spec §9 and `docs/02_evidence_base.md`, mark each row `[VERIFY]`,
  and leave Comments empty for me.
  **(new 30 Oct)** Koch et al. 2019 (Fraunhofer IEE) is already **confirmed** — mark it so,
  not `[VERIFY]`. "Kern et al. (2024)" **does exist** as an FfE consultant report
  (Kern, Wasmeier, Bantelmann & Wendlinger, FfE Munich, 21 Oct 2024), cited by Hirth (2026)
  as FfE (2024); grey literature, [VERIFY] at ffe.de before any use — see
  `docs/02_evidence_base.md` §B2 (corrected 30 Oct). The origin of the −65 €/MWh switch-off estimate is
  **Götz, Henkel, Lenck & Lenz (2014)**, not Purkus et al. (2015), which only cites it.

**STOP** — show me the diff summary.

## Phase 2 — semi-synthetic benchmark (E1), no MaStR or ERA5 needed

Create `src/censoring/` with:

- `cohorts.py` — per quarter-hour and wind cohort, compute the switch-off threshold
  θ_k,t and exposure s_k,t = 1[p_t < θ_k,t] (spec §3, v1.4).
  - θ = 0 when the cohort's §51 trigger is active: quarter-hour clock for the post-25 Feb
    2025 rule; hourly mean of the four QH prices plus consecutive-run length for older
    rules, including the 2023–2025 staircase (3 h → 2 h on 1 Jan 2026).
  - θ = 0 for out-of-support cohorts.
  - Otherwise θ = −max(0, AW_k − MV_m).
  - AW_k (award value per cohort) and MV_m (monthly market value) are **parameters** for
    now, with placeholder values clearly marked; real values come in Phase 3.
  - Cohort capacity shares are a parameter (dict).
  - **(new 30 Oct)** Expose a two-cohort mode (quarter-hour clock vs hourly clock) from the
    start, so the rule-18 fallback is a switch rather than a rewrite. In that mode exposure
    is still computed per rule-table row and aggregated to capacity-weighted exposed shares
    per macro-cohort; only r is pooled. Unit-test that the two modes give identical c_t
    when every cohort in a macro-cohort shares the same r.
  - Unit tests on hand-built price sequences for every rule row, plus the market-premium
    case.

  **(new 30 Oct) Facts already verified from the statutory texts — implement these, do not
  re-derive them.** All are sourced in `docs/05_eeg_rule_table.md`.
  - **Two price clocks run at once.** Post-25 Feb 2025 cohorts are judged per
    **quarter-hour** on the QH price. All older, hour-based cohorts are judged per
    **calendar hour** on the **arithmetic mean of that hour's four QH prices**
    (§100(45) EEG 2023), and then on the run length of such hours. A QH at −10 €/MWh inside
    an hour averaging +5 €/MWh triggers one cohort and not the other. The model must not
    collapse these onto one price series.
  - **The staircase steps by the CALENDAR YEAR in which prices are negative**, not by the
    plant's commissioning year. §51(1) reads "Wenn der Spotmarktpreis [im Jahr X] … negativ
    ist" — the year qualifies the price condition. The commissioning date decides only
    *which version* of §51 applies (§100(46)). The whole 2023 – Feb 2025 cohort therefore
    stepped 3 h → 2 h simultaneously at midnight on 1 Jan 2026, inside the sample. This is
    a sharp common exogenous date and a candidate natural experiment for E3.
  - **Size exemptions are part of the rule, not a detail.** A cohort below its threshold
    never triggers, so θ stays at the market-premium value rather than dropping to 0:
    wind <3 MW and other <500 kW before 2021; <500 kW in 2021–22; <400 kW for
    2023 – 24 Feb 2025; <100 kW (until the smart-meter year ends) and <2 kW from
    25 Feb 2025. Aggregation is by §24 EEG 2023 (§32(1) sentence 1 under the 2014 numbering).
  - **Pre-2017 the rule was §24 EEG 2014**, six consecutive hours, exempting plants
    commissioned before 1 Jan 2016, wind <3 MW, other <500 kW and demonstration projects.
  - **Pilot wind** (onshore §3 no. 37(b) EEG, offshore §3 no. 6 WindSeeG) is exempt in every
    version before 25 Feb 2025 and in none after.
  - **§51a is compensation after the fact** (the support period is extended by the number of
    zeroed quarter-hours). It does **not** change the within-quarter-hour incentive, so it
    must not enter θ. Note it as a second-order effect only. **(v1.5)** Hirth (2026, App.
    A1) prices §51a as a discounted deferral (about −0.59σ for wind at 15 years, 6%). That
    holds only if the extension depends on the plant's own output. [VERIFY] the §51a(1)
    wording; if it counts zeroed quarter-hours regardless of output, θ = 0 stands and no
    sensitivity arm is added.
  - **The §100(47) opt-in is invisible in public data.** A plant not otherwise subject to a
    reduction may volunteer for §51/§51a in exchange for +0.6 ct/kWh on its AW, and nothing
    public records who did. Treat it as a named modelling uncertainty and add a sensitivity
    arm over the opt-in share.

- `synthetic.py` — generator per spec §7 E1. Base = DE (and per-area) QHs with price
  > 5 €/MWh; true A := observed actual wind. Inject censoring episodes as contiguous runs
  of QHs on chosen days, with selection probability rising in F_t under confounding
  strength γ. Assign synthetic negative prices with realistic depth and run-length
  distributions, sampled from the real negative QHs in the panel. Apply known r*_k
  (step / logistic / 50% compliance) on depth below θ. Return G_syn, A_true, c_true, r*,
  θ, s, w. Fully seeded; save the config with each result. Option: a synthetic weather
  proxy = A_true passed through a noisy inverse power curve, with a with/without arm.
  **(new 30 Oct)** Sample the run-length distribution with the *hourly-mean* clock as well
  as the QH clock, so the two cohort types see the triggers they would really see.
- `model.py` — the mechanism-aware model, spec §4: multiplicative latent head
  A = F · exp(g(x_A)) with non-crossing quantiles; monotone response head r_k on depth
  below θ; c_t from w, s, r; pinball loss on G; early stopping on event-day-blocked
  validation. This is **M1**.
  **(new 30 Oct)** Rule 16 fixes g's feature set: the TSO day-ahead forecast plus
  task-allowed wind only, with temperature and pressure appearing only as air density
  inside the power-curve transform. Hour-of-day is gated on the I1 and E1 evidence.
  Also implement **M2** (spec §4): parametric density for the capacity factor of A
  (start with logit-normal) and a latent per-QH curtailed fraction (Beta around c̄_t),
  fitted by EM. Write the E- and M-steps out in the docstring as equations, and log the
  likelihood per iteration (it must not decrease).
  **(new 30 Oct)** The kill test found the over-forecast behaves as a roughly constant
  **−9% proportional haircut** on the day-ahead forecast (−9.1% overall vs −9.3% in windy
  QHs, almost fully overlapping intervals), not as a fixed MW offset. That is direct
  empirical support for the multiplicative head; record it as the motivation, and keep an
  additive-head ablation to test it.
- `baselines.py` — B1–B5 and the oracle, spec §5. **(v1.5)** B3 = Hirth's
  pipeline exactly (spec §5): A fitted on QHs > 5 €/MWh, curtailment = residual, implied
  response = binned residual share by profit margin. B4 = Wang & Wang's objective: pinball
  loss on non-exposed QHs plus survival loss −log(1 − F̂(G)) treating G as a lower bound in
  every exposed QH, with F̂ from piecewise-linear interpolation of the predicted quantiles.
  Document both formulations in the docstrings with the citations.
  **(new 30 Oct)** Add a **price-free proxy baseline**: solar day-ahead forecast + day type
  (working day / Saturday / Sunday / holiday), no price and no MaStR. A public-data
  practitioner project reached an 11% cut in negative-hour onshore error with these two
  features alone (`docs/02_evidence_base.md` §B3). Any claim for the mechanism-aware model
  must clear this, not only the raw TSO forecast.
- `metrics.py` — MAE on A (censored QHs), integrated absolute error of r̂ vs r*,
  pinball, 80/90% coverage, MAE on G, CRPS (from quantiles for M1; from the density for
  M2) and PIT histograms; Diebold-Mariano with event-day block bootstrap
  (reuse `src/stats_boot.py`).
  **(new 30 Oct)** `src/stats_boot.py` already provides `eventday_bootstrap_mean`,
  `eventday_bootstrap_weighted_mean`, `eventday_bootstrap_ratio` and `ci_excludes_zero`.
  Reuse them; do not write a second bootstrap. Report errors in **relative** terms as well
  as MW — the kill test showed an MW-only comparison across subsamples is a scale artefact.
- `run_synthetic.py` — the full grid: censoring rate {5,10,20,30,40}% × γ {0,0.5,1} ×
  r* shape {step, logistic, half} × seeds {42..46}. Write `results/10_synthetic_grid.csv`
  and figures `figures/10_error_vs_censoring_<shape>.png` (one line per method, bands
  across seeds).

Tests in `tests/`: generator reproduces c_true exactly when r* is known; EM likelihood
is monotone non-decreasing; the model
recovers r* within tolerance on an easy setting (γ = 0, logistic, 20%); leakage
allow-list test; "no price in g" test; cohort-rule tests.
**(new 30 Oct)** Add: a test that the hourly-mean clock and the QH clock disagree on a
hand-built case where an hour averages positive but contains a negative quarter-hour; and a
test that a cohort under its size threshold never has θ forced to 0.

Start with a smoke run (one cell of the grid, one seed) and report runtime before the full grid.

**STOP** — report results table, figures, runtime, and anything that looks wrong.

## Phase 3 — real data (E2), after I confirm Phase 2

- Add the SMARD solar day-ahead forecast to the panel via `src/ingest_smard.py` and
  `src/build_panel.py`, using filter IDs from the config JSON (do not guess). New panel
  version under a new filename; keep the old one.
  **(new 30 Oct)** The config lists solar day-ahead under "Prognostizierte Erzeugung
  Day-Ahead" as `data_id` **125**; confirm this against the JSON rather than trusting this
  line. Remember SMARD serves **MWh per quarter-hour** — multiply by 4 for MW, as
  `build_panel.py` already does, and as the Benutzerhandbuch confirms ("durch vier dividiert").
- MaStR ingest (`src/ingest_mastr.py`): dated snapshot into `data/raw/mastr/`, wind units
  by control area, commissioning date and capacity → cohort shares w_k,t per rule-table
  row. If the control-area mapping is not directly available, document the proxy used.
  If a field cannot be obtained, write `UNRESOLVED` in `docs/03_data_sources.md`.
  **(new 30 Oct)** Cohort boundaries must come from
  `data/reference/eeg_negative_price_rules.csv`, not from fresh assumptions. Expect the
  auction award value **not** to be joinable to unit IDs — this is already flagged as
  unresolved in `docs/05_eeg_rule_table.md` §6. Per rule 19, the cohort flag is the
  presence of a Zuschlagsnummer, not the commissioning year; **STOP** if that column is
  missing or filled for under 50% of the capacity of wind units above 750 kW commissioned
  2019–2022 or of at least 1 MW from 2023 (rule 19 — never a fill rate over all units). Where it is present,
  report AW_k as a min–max range widened by the correction-factor uncertainty, run θ at
  the round average × 1.226 (main) and at both ends (sensitivity), and set θ = 0 for plants past
  the end of their support period.
- Market values (`src/ingest_market_values.py`): monthly wind onshore/offshore market
  values (Marktwerte) from Netztransparenz into `data/raw/netztransparenz/`. Award values
  AW_k per cohort: statutory values and auction averages, with sources recorded in
  `data/reference/`; any value that cannot be sourced is marked `UNRESOLVED`, never
  guessed.
  **(new 30 Oct)** The Netztransparenz WebAPI (`ds.netztransparenz.de`) returns **HTTP 401**
  and needs an account with the `WebAPIReader` role plus a Client created in the
  WebAPI-Portal (OAuth client-credentials). The public pages serve CSV only through an
  ASP.NET postback with no GET URL. If the Marktwerte hit the same wall, **stop and ask me**
  for a manual export or credentials — do not replay the postback or drive the SPA. The
  licence for Netztransparenz data is still **UNRESOLVED** and must be settled before any of
  it goes into the thesis.
  **(new 30 Oct)** Per rule 17, the downloaded Marktwerte are a **validation series only**.
  The MV_m that feeds θ in a T2 run must be recomputed from SMARD data available by D−1
  (EEG Anlage 1 Nr. 3.3.2, month-to-date). Write both and compare them in the results note.
- Weather (`src/ingest_weather.py`), spec §3a:
  - T2: ICON (D2, else EU) at 1-day lead from the Open-Meteo **Previous Runs** API.
    Record the earliest date actually available for DWD models.
  - T1: ERA5 hourly 100 m wind (Copernicus CDS; needs my API key — stop and ask) or the
    Open-Meteo Historical Forecast archive.
  - Sample at MaStR turbine locations (or a capacity-weighted grid if per-turbine calls
    are too many), aggregate per control area, store with the source and vintage in the
    column names.
  - Check the Open-Meteo licence and record it in `docs/03_data_sources.md`.
  - Also write `src/archive_icon_daily.py`, a small script I can schedule to save each
    day's ICON-D2 run, building a true-vintage archive from now on.
- `src/censoring/run_real.py` — rolling origin by month with 7-day embargo, four control
  areas plus DE, all methods except the oracle. Outputs `results/20_real_*.csv`, bias by
  price band per method, coverage, DM tests vs B5 and B3. Report results above 40 GW of
  DA forecast separately (overlap assumption I2, spec §3).
  **(new 30 Oct)** Use the same price bands as the kill test (`src/smard_config.py`
  `PRICE_BANDS`) so the tables line up with `results/02_bias_by_price_band.csv`. Note that
  SMARD's `DE` region is the exact sum of the four control areas, while `DE-LU` adds
  Luxembourg (~0.2%); the kill test uses `DE`, so stay with it.
- I1 placebo check: residual curtailment on positive-price QHs per method.
- Run T1 (ERA5 allowed) and T2 (D−1 vintages only) as separate configurations with
  separate result files; never mix them in one table without a task column.
- Repeat the overlap check (I2) on the weather proxy.
- **(new 30 Oct)** Stratify by redispatch using the method already validated in
  `src/redispatch_control.py` (5 volume bins × forecast decile, bin 0 = exactly zero).
  Redispatch stays an evaluation stratifier, never a feature. Note that its solar exclusion
  is by plant name only and is the weakest link in that control; if a carrier field can be
  obtained, use it.

**STOP** — report.

## Phase 4 — only when I ask

E3 regulatory transfer (needs the hourly 2023 – Sep 2025 ingest), E4 plausibility vs the
statutory curve, ablations (two-cohort vs K-cohort, additive vs multiplicative A head,
with vs without run length).
**(new 30 Oct)** E3 has a ready-made discontinuity: the 3 h → 2 h staircase step on
1 Jan 2026, which hit the whole 2023 – Feb 2025 cohort at once and no other cohort.

---

## Still unresolved — carry these forward, do not silently resolve them **(new 30 Oct)**

| Item | Where it is recorded | How to settle |
|---|---|---|
| Which intraday forecast vintage SMARD archives | `04_rq1_killtest_note_v3.md` §3, TSO e-mail question 4 | Ask the TSOs; not documented anywhere public |
| Netztransparenz licence / terms of use | `03_data_sources.md`, v3 note §4 | Impressum / Datenschutz, or the API-portal registration terms |
| Whether DSO-initiated Redispatch 2.0 measures are in the export | v3 note, known gaps | Netztransparenz "Redispatch 2.0 at the TSO-DSO interface" page |
| Whether the day-ahead wind series is ever revised after 18:00 D−1 | v3 note, open items | TSO e-mail; the manual says "no later updating" only for the *total* forecast |
| MaStR → auction award (Zuschlagsnummer) join | `05_eeg_rule_table.md` §6 | Inspect the MaStR schema in Phase 3 |
| Open-Meteo Previous Runs start date for DWD models | spec §3a | Open-Meteo docs / API probe |
| Open-Meteo licence | spec §3a | Open-Meteo terms page |
| Google Scholar and IEEE Xplore novelty sweep | `02_evidence_base.md` search caveat | Still to do; Semantic Scholar/OpenAlex and a broad web sweep are done |
