# 06 — Pivot: from forecast correction to mechanism-aware censored learning

Version 1.4, 30 Oct 2026 (v1.3: 30 Oct 2026, commit 2538e56; v1.2: commit 980cd30;
v1.1 and v1: not committed).
Working spec, not proposal prose.

**Changes in v1.4** (30 Oct 2026):
- §10: one consolidated leakage list — intraday forecast, redispatch, same-quarter-hour
  actuals, and the **published monthly Netztransparenz market value**. The last of these
  reaches the model through θ, not through a feature column, so the allow-list test must
  also check **θ's provenance per task**, not only the feature set.

**Changes in v1.3** (30 Oct 2026, review of v1.2):
- §3: AW_k range → θ runs at three fixed settings (main = round volume-weighted average with
  correction factor 1; sensitivity = low and high ends). The Zuschlagsnummer fill-rate
  test is measured by capacity on wind units > 750 kW commissioned from 2019, not over all
  units.
- §3 I4: the two-cohort fallback **pools the response r, not the exposure s**; the
  run-length thresholds (6 h, 4 h, 2 h) remain identifying variation.
- §7 and §11: the week-6 checkpoint gets a pass/fail criterion (E1, due 31 Dec 2026).
- §10: the MaStR fall-back no longer imputes AW from commissioning year (contradicted
  rule 19); new risk line for a failed checkpoint.

**Changes in v1.2** (design decisions fixed before implementation, 30 Oct 2026). These
four are settled and are not to be reopened during implementation; they appear as hard
rules 16–19 in `CLAUDE_CODE_PROMPT.md`.
- §4: the latent head's covariate set is closed. **No calendar features** (v1.1 allowed
  them). Temperature and pressure enter only as air density inside the power-curve
  transform. Hour-of-day is admissible only on evidence from I1 and the E1 ablation.
- §3: MV_m is **task-dependent**. T2 recomputes it month-to-date from SMARD data available
  by D−1 (EEG Anlage 1 Nr. 3.3.2); the published Netztransparenz value is validation only.
- §3 I4: the collapse to two cohorts is **pre-registered** at fewer than 10 event-days of
  differing exposure.
- §3: AW_k is a **range**, keyed to the presence of a Zuschlagsnummer, not to
  commissioning year.

**Changes in v1.1** (from review feedback, 30 Oct 2026):
- §3: switch-off incentive is now a **price threshold per cohort** (market premium *and*
  §51), not only the §51 trigger. Rules enter as model structure, not as features.
- New §3a: two tasks (ex-post recovery vs day-ahead forecast) and a **weather proxy for
  uncurtailed power** (ERA5 / ICON), with the leakage rules for each.
- §4: explicit-likelihood variant (M2) fitted by EM, alongside the quantile model (M1).
- §5 B4 clarified as censored quantile regression ("pinball loss with censoring").
- §7 metrics: CRPS and PIT on latent power. §9, §10: literature and risks updated,
  including the July 2026 EEG draft. This **supersedes sections 1, 3, 4,
6, 8 and 10 of `01_thesis_brief.md`**. The previous brief is kept unchanged as
`01_thesis_brief_v1_forecast-correction.md`. Sections 2, 5, 7, 11, 12 and 13 of the old
brief still apply unless contradicted here.

---

## 0. Why the pivot

Prof. Iliev's rules (`srh-guidelines/08_thesis_research_clarification.txt`) say the
contribution must be an ML method, "not about analysis and discoveries in the dataset you
are using". They exclude "taking some data and applying some Machine Learning" and "combine
various techniques claiming improvements".

The v1 plan was a correction model for one market's TSO forecast: a rule model, quantile
LightGBM and a hurdle model. It reads as applied analysis, and the model mix reads as
combining techniques. The research question was good; the claimed contribution was in the
wrong place.

**What changes:** the contribution moves from "forecast German curtailment" to **a learning
method for labels that are hidden by a price-triggered, partial switch-off decision**.
Germany's wind fleet becomes the benchmark.

**What does not change:** the RQ1 kill test (v3). It becomes the motivating evidence that the
censoring problem is real, large and not explained by redispatch:
−9.1% [−13.2, −4.8] relative bias in negative quarter-hours, surviving the redispatch control.

## 1. Title and description

**Title:** *Mechanism-Aware Learning under Signal-Driven Censoring: Jointly Recovering
Latent Wind Power and Fleet Switch-Off Response from Price-Curtailed Data*

**Alternative:** *Learning from Price-Censored Generation Data: A Structured Model of Partial
Fleet Curtailment in Germany's 15-Minute Day-Ahead Market*

**Description (abstract draft — rewrite in your own words for the proposal):**
Forecasting models for renewable generation are trained on recorded output. When prices
turn negative, part of the fleet switches off, so the recorded output no longer shows what
the wind could have produced. The label is censored. Current practice either deletes these
periods, calibrates only on periods without curtailment, or ignores the problem, and
classical censored-regression methods assume a fixed, known threshold. None of these fits a
case where an observed external signal (the price) triggers a partial, heterogeneous
response, and where statutory rules partly specify which plant groups are exposed. This
thesis proposes a mechanism-aware model that learns latent available power and a monotone
fleet response function jointly, using the known exposure structure from the EEG
negative-price rules and the plant register as constraints. It states conditions under
which the two components can be told apart, evaluates the method on a semi-synthetic
benchmark with known ground truth, and tests it on German 15-minute data from October 2025
onwards against deletion, safe-period calibration, inequality-censored quantile regression
and black-box price-aware models.

## 2. What stays, what changes, what goes

| Item | v1 | v2 (this spec) |
|---|---|---|
| Kill test, panel, redispatch control, EEG rule table | core | **kept as-is** — motivating evidence (thesis ch. 3) and the cohort signal source |
| Target | e_t = actual − TSO DA forecast | **latent available power A_t** and **response r_k**; observed G_t is what the model must explain |
| Main model | rule model + quantile LightGBM + hurdle | **one structured model** (§4); LightGBM becomes a baseline |
| Contribution | better forecast in negative QHs | **a learning method for signal-driven partial censoring**, with identification conditions and a benchmark |
| Ground truth | none (TSO actuals only) | **semi-synthetic benchmark with known truth** (E1) + real data (E2) |
| H2 "≥15% MAE cut" | headline | replaced by H2–H4 (§6) |
| RQ3 pre-auction price forecast | core | **stretch only** |
| Hurdle model, conformal stretch | planned | dropped (hurdle) / optional (conformal) |
| Intraday forecast, redispatch | evaluation only | **unchanged rule: never a model input** |

## 3. Problem formulation

Per quarter-hour t and control area:

- G_t — observed wind feed-in (TSO actual), MW
- A_t — latent available power: what the fleet would have produced with no market-driven switch-off (unobserved)
- x_t — covariates known after 12:57 CET D−1: TSO day-ahead wind forecast F_t, DA price (quarter-hour p_t and hourly mean of its four QHs), run length of consecutive negative periods on both clocks, calendar, solar DA forecast
- k = 1..K — plant cohorts defined by the EEG rule table (`data/reference/eeg_negative_price_rules.csv`)
- w_k,t — capacity share of cohort k (MaStR, by commissioning date and size; known)
- θ_k,t — **switch-off price threshold** of cohort k at t: the price below which producing loses money. (v1.1)
  - θ = 0 when the cohort's §51 trigger is active (quarter-hour clock for post-25 Feb 2025 plants; hourly mean of the four QH prices plus run length for older rules), and for plants out of support.
  - Otherwise θ = −MP_k,t, the market premium: MP = max(0, AW_k − MV_m), with AW_k the cohort's award value (anzulegender Wert) and MV_m the monthly market value for wind. This covers cohorts §51 never touches (pre-2016 plants, rule R01), which still switch off below −MP.
  - **AW_k is a range, not a point (v1.2).** The cohort flag is the presence of a Zuschlagsnummer in MaStR, not the commissioning year. AW_k is reported as the rounded minimum and maximum award for the cohort, widened by the correction-factor (Korrekturfaktor) uncertainty. θ is run at three fixed settings: the **main run** uses the round's volume-weighted average award with correction factor 1, and two **sensitivity runs** use the low and high ends of the range; r̂ is reported under all three (v1.3). The Zuschlagsnummer fill rate is measured by capacity on wind units > 750 kW commissioned on or after 1 Jan 2019 (excluding pilot plants), the group that must carry one; below 50% the join is treated as broken (v1.3). Plants past the end of their support period have θ = 0 regardless.
  - **MV_m is task-dependent (v1.2).** For T1 (ex-post) the published monthly Netztransparenz market value is correct. For T2 it is **leakage** — it is released after the month ends — so T2 recomputes MV_m from SMARD data available by D−1, month-to-date per EEG Anlage 1 Nr. 3.3.2, falling back to the previous month's value on day 1 of a month. The published series is then used only to validate the recomputation.
  - θ is a **step function of the rules**, computed deterministically; nothing about it is learned. Its only uncertainty is the AW_k range above.
- s_k,t = 1[p_t < θ_k,t] — exposure indicator (deterministic given prices, rules, AW and MV)
- r_k(z_t) ∈ [0,1] — fraction of exposed cohort-k capacity that actually switches off, as a function of price depth and run length z_t (**unknown, learned**)

Observation model:

    G_t = A_t · (1 − c_t) + ε_t,      c_t = Σ_k w_k,t · s_k,t · r_k(z_t)

Market-based curtailment in MW is A_t · c_t. The response r_k takes the depth below the
cohort's own threshold, p_t − θ_k,t, as its main input.

**Rules are structure, not features.** Feeding the rule step-functions as features into a
black-box model is baseline B5. The method's claim is that putting them into the
observation model, as known exposure, is what identifies the response and transfers across
rule changes.

**Why this is not covered by standard methods**
- Tobit / censored quantile regression / survival models: treat G as a lower bound of A (right-censoring) with a fixed, known threshold, and throw away the information in how much was switched off. Here the censoring is a *fraction*, triggered by an exogenous signal, and the trigger rule differs between cohorts.
- Deleting negative-price periods (Jørgensen et al., arXiv 2501.14805): discards exactly the regime of interest and leaves the model blind in it.
- Safe-period calibration plus residual (Hirth, arXiv 2609.10053): ex post, with no learned response function, and it cannot separate model error from curtailment.
- Generic missing-not-at-random imputation: ignores the known structure (s, w), so it is weakly identified.

**Identification assumptions (each needs a test in the thesis)**
- I1 — no curtailment without incentive: if all s_k,t = 0 then c_t = 0. Test: placebo residuals on positive-price QHs. The current panel shows +0.9% to +2.8% relative bias at positive prices, so A must model the TSO forecast's own bias.
- I2 — overlap: censored QHs have weather/forecast conditions that also occur uncensored. **Checked 29 Oct 2026 (DE):** positive-price QHs exist at every DA forecast level — 7,479 QHs at 20–30 GW, 3,284 at 30–40 GW, but only **948 QHs on 36 days above 40 GW**, where 253 negative QHs sit. Report results separately above 40 GW.
- I3 — monotonicity: r_k is non-decreasing in price depth (constraint built into the model).
- I4 — separability of cohorts: the two price clocks (quarter-hour vs hourly mean plus run length) create QHs where one cohort is exposed and another is not. This regulatory mismatch is the identifying variation. If K cohorts are not separable, collapse to two cohorts (QH-clock vs hourly-clock). **Pre-registered test (v1.2):** before any modelling on real data, count the Berlin-local event-days on which the cohort exposure vectors s_k actually differ. Fewer than **10** such days and the K-cohort model is abandoned for the two-cohort one, with the count reported either way. **The collapse pools the response, not the exposure (v1.3):** s_k,t is still computed per legal cohort (rule-table row) and aggregated into each macro-cohort's exposed capacity share; only r is shared within a macro-cohort. The staircase cohort sits at 2 h throughout 2026, but the hourly-clock cohorts still differ by run-length threshold (6 h, 4 h, 2 h), and that variation is kept.

## 3a. Two tasks and the weather proxy (v1.1)

The thesis separates two tasks, because they allow different data:

| | T1 — ex-post recovery | T2 — day-ahead forecast |
|---|---|---|
| Question | how much power was available, how much switched off, and what is r_k? | forecast G_t after the auction (12:57 CET D−1) |
| Allowed weather | **ERA5** reanalysis (hourly, ~31 km); Open-Meteo *Historical Forecast* archive | only **true D−1 vintages**: TSO day-ahead forecast F_t; ICON at 1-day lead from the Open-Meteo *Previous Runs* API |
| Forbidden | — | ERA5 and the stitched *Historical Forecast* archive (both contain information from after D−1: **leakage**) |
| Thesis role | RQ2 and E4 on real data | RQ4, E2, E3 |

**Why weather matters for identification.** The model must tell "low wind" apart from "high
wind, but switched off". F_t already helps (TSO forecasts are frozen before the auction, so
they are price-blind), but it carries the TSO's own errors. A weather-based proxy that never
sees price gives the latent-power head a second, independent anchor.

**Construction.** Hub-height wind speed (100/120 m) at MaStR turbine locations, aggregated
per control area with capacity weights, plus a fleet power-curve transform. The overlap
check (I2) is repeated on this weather proxy, not only on F_t.

**Data facts checked 30 Oct 2026.** Open-Meteo archives DWD ICON-D2 (~2 km), ICON-EU and
ICON global, hourly, from 24 Nov 2022. Its Historical Forecast product is stitched from the
first hours of successive runs, so it is **not** a D−1 vintage. The Previous Runs API
offers fixed 1–7-day leads from January 2024; the start date for the DWD models
specifically is **UNRESOLVED**. Licence terms: to verify.

## 4. Method (the proposed model)

- **Latent power head:** A_t = F_t · exp(g_θ(x_t^A)), with g a small MLP or spline model on non-price covariates. Multiplicative form follows the kill-test finding that the negative-QH error behaves as a ~9% proportional haircut. Price features are **excluded** from g, otherwise A can absorb curtailment.
- **Response head:** r_k(z) = σ(a_k + softplus(b_k) · depth + softplus(d_k) · runlength), or a monotone piecewise-linear function with non-negative increments. Shared shape plus per-cohort offsets.
- **Probabilistic output:** predict quantiles of A (non-crossing via cumulative softplus increments). Because (1 − c_t) ≥ 0, quantiles of G are exactly (1 − c_t) × quantiles of A. Train with pinball loss on G over τ ∈ {0.05, 0.1, …, 0.95}.
- **Training:** PyTorch on CPU, Adam, early stopping on event-day-blocked validation, seed 42. Uncertainty in r via event-day bootstrap refits (reuse `src/stats_boot.py` logic).
- **Outputs:** A quantiles, curtailed MW, r_k curves with bands.
- **Latent-head covariates — closed set (v1.2, replaces v1.1):** F_t plus the §3a weather proxy only, task-dependent (T1 may use ERA5; T2 only D−1 ICON vintages). Temperature and pressure enter **solely as air density inside the fleet power-curve transform**, never as free features. **No calendar features, no solar forecast, no price, no θ, no s** — v1.1 allowed calendar; v1.2 does not, because a calendar feature can proxy the diurnal price shape and so smuggle the incentive into A. Hour-of-day may be added only if the I1 placebo shows a genuine diurnal bias in A **and** the E1 ablation at γ > 0 shows no loss in A recovery; the decision and its evidence are recorded in the results note. Enforced by the per-task leakage allow-list test, which fails on any column outside this set.

**Variant M2 — explicit likelihood, fitted by EM (v1.1).** M1 above is distribution-free
(quantiles). M2 writes a full conditional density P(A_t | x_t): for example a logit-normal
or Beta density on the capacity factor, with covariate-dependent parameters. The per-QH
switched-off fraction is treated as a latent random variable around c̄_t = Σ w·s·r (for
example a Beta). It is fitted by expectation-maximisation: the E-step estimates the hidden
curtailed fraction given G, and the M-step refits the density and response parameters.
Alternatively it can be fitted by Monte Carlo marginal likelihood.

Report M1 vs M2 as a design comparison: M2 gives a proper density and handles
plant-level randomness; M1 is more robust if the density is misspecified. EM is an
estimation choice. The contribution is the structure, so it holds for either variant.

## 5. Baselines

| ID | Method | What it represents |
|---|---|---|
| B0 | TSO day-ahead forecast as-is | status quo |
| B1 | Model trained on observed G, all QHs, no price features | naive: learns curtailment as noise |
| B2 | Same, negative-price QHs deleted from training | Jørgensen et al. deletion |
| B3 | Fit A on safe QHs only; curtailment = residual | Hirth-style safe-period calibration |
| B4 | Censored quantile regression ("pinball loss with censoring", Powell-type): G is a lower bound of A in exposed QHs | classical censoring / survival-style method with a fixed rule |
| B5 | Quantile LightGBM on G with price and cohort-exposure features | strong black-box price-aware model |
| Oracle | Trained on true A | synthetic benchmark only |

B5 is the one that keeps the comparison honest: it gets the same information as the
proposed model, without the structure.

## 6. Research questions and hypotheses

- **RQ1 (done):** Does price-driven censoring measurably bias the labels used for wind forecasting? → kill test v3, yes.
- **RQ2:** Can the mechanism-aware model jointly recover A and r_k, and under which conditions (I1–I4)?
- **RQ3:** How do deletion, safe-period calibration and fixed-rule censoring degrade as the censoring rate and the weather–price confounding increase, compared with the proposed model?
- **RQ4:** On real German data, does the structured model beat black-box price-aware learning (B5) in negative QHs, and does it transfer better across regulatory change?

- **H2:** On the semi-synthetic benchmark, the proposed model's error on A in censored QHs is significantly lower than B1–B4 at censoring rates ≥ 10%, and its r̂ curve error is lower than B3's implied response.
- **H3:** On real data, the proposed model is at least as accurate as B5 in negative QHs (Diebold-Mariano, event-day block bootstrap) and better calibrated (interval coverage).
- **H4:** When trained before a rule change and tested after, the proposed model degrades less than B5, because the rule change enters through s_k,t rather than having to be relearned.
- Falsification: the H2/H3 tests are not significant, or the I1 placebo fails.

## 7. Experiments

- **E1 — semi-synthetic benchmark (do first; needs no MaStR, no ERA5).** Base data: uncensored QHs (price > 5 €/MWh). Treat their actual G as true A. Inject synthetic censoring: choose QHs with probability rising in F_t (confounding strength γ ∈ {0, 0.5, 1}), assign synthetic negative prices and run lengths, compute s_k with the real rule logic and synthetic cohort shares, apply known r*_k (step, logistic, 50%-compliance). Grid: censoring rate {5, 10, 20, 30, 40}% × γ × r* shape × 5 seeds. Metrics: MAE of Â on censored QHs, integrated absolute error of r̂ vs r*, 80/90% coverage, MAE on G, **CRPS and PIT histograms for A** (true A is known here, so calibration of P(A|x) can be checked directly). Add a weather-proxy arm: synthetic censoring with and without the weather covariate, to measure how much it helps identification.
- **Week-6 checkpoint — go/no-go on E1 (v1.3, due 31 Dec 2026).** Pass if, at censoring rates ≥ 10% with γ = 0, for each r* shape: (a) the integrated absolute error of r̂ vs r* is lower than that of B3's implied response, and (b) the MAE of Â on censored QHs is lower than each of B1–B4; both judged on the paired difference, with a 95% event-day block-bootstrap CI (pooled over the 5 seeds) that excludes zero. γ > 0 results are reported but are not part of the gate. On a fail: refit with the two-cohort / single-response structure and re-test by 15 Jan 2027; if that also fails, the structure is not identified on this design — stop and agree the next step with the supervisor before any further real-data work.
- **E2 — real data (task T2 unless stated).** 15-minute panel, Oct 2025 – Oct 2026, four control areas plus DE. Rolling origin by month, 7-day embargo, event-day blocks. Metrics on negative QHs and overall: MAE, pinball, coverage, bias by price band; Diebold-Mariano with event-day block bootstrap. 50Hertz and Amprion are primary (cleanest signal in v3).
- **E3 — regulatory transfer.** **Constraint found 29 Oct 2026:** only **199 negative QHs on 7 event-days** fall before 1 Jan 2026 in the 15-minute panel, so "train 2025, test 2026" is not feasible on that panel alone. Options: (a) add the hourly 2023 – Sep 2025 dataset (already planned in v1 §5.3), train before the 1 Jan 2026 staircase change and test after; (b) leave-one-cohort-out within 2026. Decide in month 2.
- **E4 — plausibility (domain result, secondary; task T1, ERA5 allowed).** Compare r̂ with the statutory "should switch off" curve and with Hirth's "about half switch off" finding; report the compliance gap per cohort.
- **E5 — stretch.** Same code on solar curtailment (SMARD solar series), to show the method is not wind-specific; or the pre-auction price-forecast variant from v1.

## 8. Intended contribution to science — draft bullets (rewrite in your own words)

- A formal model of signal-driven partial censoring, where an observed external signal triggers a partial, heterogeneous response and a regulatory rule partly specifies the exposure.
- A jointly trained, monotone-constrained model that separates latent available power from fleet response, with stated identification conditions and tests for them.
- A semi-synthetic benchmark with known ground truth for learning from curtailment-censored generation data.
- Evidence on how deletion, safe-period calibration and fixed-threshold censoring degrade as censoring becomes more frequent, a trend that matters as negative-price periods grow.

Iliev rule: do not write "first" or "no one has done this". Say what recent work does and
does not cover, with citations.

## 9. Literature to add (censored and missing-label learning side)

All entries are **[VERIFY]** — check each at the publisher before citing, following the
`02_evidence_base.md` practice. Log each in the literature table format from
`srh-guidelines/06_instructions_to_students_for_their_thesis.txt` (D).

- **Closest prior work — read first:** Wang & Wang (2026), SSRN 7025858 and 7195331. Reported to treat curtailed SCADA as censored observations of latent turbine available power, for grid set-point curtailment at three Chinese farms. Source: the 29 Oct research report, abstracts only, **not yet verified**. Differentiate on: price signal rather than known command, fleet level, learned heterogeneous response, regulatory-clock identification.
- Tobin (1958), Econometrica — the censored regression model.
- Koenker & Bassett (1978), Econometrica — regression quantiles.
- Powell (1986), Journal of Econometrics — censored regression quantiles.
- Portnoy (2003), JASA — censored regression quantiles.
- Little & Rubin, *Statistical Analysis with Missing Data* (Wiley) — missing-not-at-random framework.
- Lee et al. (2018), DeepHit, AAAI — deep learning with censored targets (survival).
- Dempster, Laird & Rubin (1977), JRSS Series B — the EM algorithm.
- Gneiting & Raftery (2007), JASA — proper scoring rules (CRPS).
- Hersbach et al. (2020), QJRMS — ERA5 reanalysis.
- Open-Meteo Historical Forecast and Previous Runs APIs (data source; cite per their licence page).
- Already in the evidence base: Hirth (2026), Jørgensen et al. (2025), Koch et al. (2019), Shamim et al. (2026).

## 10. Risks and fall-backs

- I2 overlap weak above 40 GW → report that region separately; add hourly history.
- Cohorts not separable → two-cohort model (QH clock vs hourly clock), pooling r but not s (§3 I4).
- MaStR award-number join weak → §51 cohort shares still come from commissioning date and size (that is what the rule table keys on), but AW is **never** imputed from commissioning year (rule 19): STOP and decide. E1 does not depend on MaStR. (v1.3)
- Week-6 checkpoint fails (§7) → two-cohort / single-response refit by 15 Jan 2027; if that fails too, supervisor decision before further real-data work. (v1.3)
- Wang & Wang turns out to cover the price-driven case → keep the fleet-level, signal-driven and regulatory-transfer angle; tighten the claim.
- **Leakage from weather (v1.1):** ERA5 or the stitched ICON archive used in T2 would leak post-D−1 information. Enforce this with per-task allow-lists and tests.
- **Leakage, consolidated list (v1.4).** Never a T2 model input: the **intraday forecast**
  (no published vintage), **redispatch** (ex post; an evaluation stratifier only), **same-QH
  actuals**, **ERA5 and the stitched Historical Forecast archive**, and the **published
  monthly Netztransparenz market value** (released after the month ends; T2 recomputes
  MV_m month-to-date from SMARD data up to D−1, per §3). The first four are feature
  columns and are caught by the per-task allow-list. The fifth is **not a feature** — it
  enters through θ — so the test must assert the provenance of θ's inputs per task as
  well, or the allow-list will pass while the model leaks.
- **D−1 ICON vintages not available back to Oct 2025 for the DWD models** → T2 runs with F_t only; weather is used in T1 and the synthetic benchmark. Start archiving daily ICON-D2 runs now as a prospective set.
- **EEG draft (watch item, v1.1).** A BMWE Referentenentwurf of 17 Jul 2026 for an EEG amendment is **not law**. The BEE statement of 22 Jul 2026 says it adds §10b(7), a mandatory price-dependent curtailment threshold in direct-marketing contracts, and changes §51, with details not given in the statement. If enacted inside the sample window, it would push compliance towards 1 and act as a natural experiment for E3; if after, it is a scope note. Re-check monthly. Do not cite "EEG 2027" until a law text exists.
- Real-data gain over B5 is small → the method contribution still stands on E1 plus identification; report it honestly (the minimum passable thesis).

## 11. Timeline (registered window: 16 or 26 weeks — [VERIFY] with the examination office; the registration form lists 26 weeks for full-time 4-semester study; registration after proposal approval)

| When | Work | Deliverable |
|---|---|---|
| Nov wk 1–2 | Proposal (≥15 pages, own writing, incl. "Intended Contribution to Science"); literature table; 30-min topic defence with supervisor | approved proposal, registration |
| Nov wk 3–4 | E1 generator, proposed model v0, baselines B0–B4 | first synthetic results |
| Dec | E1 full grid; MaStR ingest and cohort shares; B5 | RQ2/RQ3 results; week-6 checkpoint (§7 criterion, 31 Dec) |
| Jan | E2 real data; hourly 2023–Sep 2025 ingest; E3 design decision | RQ4 results |
| Feb | E3, E4, ablations; paper draft (8–12 pages) | paper draft |
| Mar | Thesis writing (≥20,000 words) | full draft |
| Apr | Buffer, code release, defence slides (numbered 1/N) | submission |

## 12. Repo changes

Implemented by Claude Code from `CLAUDE_CODE_PROMPT.md`.
