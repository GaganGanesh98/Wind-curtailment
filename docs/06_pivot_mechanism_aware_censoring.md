# 06 — Pivot: from forecast correction to mechanism-aware censored learning

Version 1.7, 31 Oct 2026 (v1.6: commit 46026bf; v1.5: commit 8e3b708; v1.4: commit
4b9dc8c; v1.3: commit 2538e56; v1.2: commit 980cd30; v1.1 and v1: not committed).
Working spec, not proposal prose.

**Changes in v1.7** (31 Oct 2026, after the nine-cell gate preview).

> **Minute — gate made self-contained, 31 Oct 2026.** Reason: in both earlier
> versions the gate was decided by the behaviour of *other people's* methods rather
> than our own. v1.3's criterion (b) was unpassable because deletion is unbiased at
> γ = 0; v1.6's was failed by the oracle itself, because at γ = 1 deletion records a
> smaller |bias| than the oracle (100 MW against 141 MW) while having a worse MAE —
> cancelling errors, not better recovery. v1.6's criterion (a) failed on the step and
> half shapes because a binned estimator is near-exact on a flat curve, so the test
> was a strict inequality between two numbers at the noise floor (0.0031 against
> 0.0017). The gate is therefore re-anchored on quantities that belong to this
> project: the known truth of the benchmark, the published TSO forecast, and our own
> oracle. **This is the fourth gate revision and is intended to be the last; it is
> pre-registered before the full grid is run.** External baselines keep their place in
> the results chapter, where positioning the contribution requires them.

- **§7: the week-6 gate is rewritten as three self-contained criteria** (a)–(c) plus
  one reported-not-required comparative condition. The v1.3 and v1.6 wordings are both
  retained for audit.
- **§7: new metric, the recovery skill score** S = (MAE_B0 − MAE_method) /
  (MAE_B0 − MAE_oracle). Bounded, interpretable, and anchored on the status quo and
  the information ceiling rather than on a rival's behaviour.
- **§7: new metric, curtailment recovery** — ĉ against c_true. No baseline produces a
  per-quarter-hour ĉ at all, so this claim has no competitor by construction.
- **§5a (new): the ablation ladder.** M1 against M1 with one piece removed, same code,
  same data, same seed. This is the evidence that the structure earns its place;
  baselines cannot supply it.
- **§7: the recoverable headroom is recorded as a first-class number.** It is only
  125–241 MW against a 1,200–1,800 MW error, which bounds what any method can win on
  A-recovery and is the reason r̂ and ĉ are the headline claims.
- **Generator fixed.** The positive base price was a constant 40 €/MWh, so B2's
  "price ≥ 0" and B3's "price > 5" selected the same sample and the two baselines
  collapsed into one model. The base level is now each quarter-hour's own real price,
  and episodes carry a shoulder priced in (0, 5], which is the only band that
  separates them. They now differ by 1,840 quarter-hours.

**Changes in v1.6** (30 Oct 2026, after the one-seed E1 smoke run).

> **Minute — gate revised 30 Oct 2026 after one-seed smoke run.** Reason: at γ = 0 the
> censoring is random with respect to F, so deletion is unbiased by construction and
> criterion (b) was unpassable as written. Decided by the student and recorded before
> the revised gate was evaluated on any new data. The original v1.3 wording is kept in
> §7 so the change is auditable.

- **§7: the week-6 gate is rewritten** into three parts (a)–(c), separating what γ = 0
  can test (recovery of the response curve, and no harm) from what only γ > 0 can test
  (unbiased recovery of latent power). The original wording is retained for audit.
- **§4: the response head is now a monotone piecewise-linear function** of depth below
  θ, with non-negative increments on fixed knots. The sigmoid becomes an ablation.
  Reason: the sigmoid cannot represent the step or the 50 %-compliance r*, so criterion
  (a) failed for two of three shapes at *every* B3 bin count — a limit of the
  functional form, not of the method. §4 already offered this alternative.
- **§7: the headline E1 metrics are now the bias of Â on censored quarter-hours and the
  curtailed-energy error**, with MAE retained as secondary. MAE cannot distinguish an
  unbiased noisy estimate from a systematically wrong one, and the systematic direction
  is the quantity of interest.
- **§5: B3 bins on Hirth's own Fig. 12 profit-margin bands** — edges **UNRESOLVED**, so
  equal-count quantile bins remain the flagged interim; the 4–64 bin sweep is kept as a
  sensitivity result.
- **§5: B5 and the price-free proxy baseline are implemented.** B5's estimate of A is
  its **no-incentive counterfactual**, not its direct prediction.
- **Training budget corrected.** Early stopping at patience 60 fired on the oracle at
  ~195 epochs while M1 trained 400–560, which made M1 appear to beat the oracle. At
  patience 250 the ordering is restored and M1's margins over B1–B4 grow. Early
  stopping is a safety net, not a budget cap, and is identical across methods.

**Changes in v1.5** (30 Oct 2026, after reading Wang & Wang 2026, Bruninx et al. 2026 and
Hirth 2026 in full):
- §3: Wang & Wang verified and positioned; Hirth's description corrected (he *does* fit a
  pooled response curve). The cohort-by-hour threshold construction is credited to Hirth.
- §3: main-run AW uses the mean site-correction factor 1.226, not 1. Fill-rate group gains
  the EEG 2023 1 MW tender threshold. MV reference period (monthly vs annual) flagged.
- §3 I1: placebo split into 0–5 and > 5 €/MWh; intraday-driven curtailment named.
- §5: B3 = Hirth's two-stage pipeline exactly; B4 = Wang & Wang's survival objective.
- §6: H2 gains a falsifiable prediction for B4. §7 E4: Hirth Fig. 12 as external benchmark.
- §8: contribution bullets 3 and 4 narrowed (Wang & Wang already ran synthetic censoring).
- §9: new references logged.

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
  - **AW_k is a range, not a point (v1.2).** The cohort flag is the presence of a Zuschlagsnummer in MaStR, not the commissioning year. AW_k is reported as the rounded minimum and maximum award for the cohort, widened by the correction-factor (Korrekturfaktor) uncertainty. θ is run at three fixed settings: the **main run** uses the round's volume-weighted average award multiplied by the **mean site-correction factor 1.226** (Hirth 2026, Table A1, derived from the Fachagentur Wind und Solar (2025) distribution of awarded turbines — [VERIFY] at that source), and two **sensitivity runs** use the low and high ends of the correction-factor distribution and the round's bid range; r̂ is reported under all three (v1.3; factor corrected from 1 in v1.5, which understated AW by about a fifth). The Zuschlagsnummer fill rate is measured by capacity on wind units > 750 kW commissioned 2019–2022 and ≥ 1 MW from 2023 (the EEG 2023 tender threshold), excluding pilot plants, the group that must carry one; below 50% the join is treated as broken (v1.3). Plants past the end of their support period have θ = 0 regardless.
  - **MV_m is task-dependent (v1.2).** For T1 (ex-post) the published monthly Netztransparenz market value is correct. For T2 it is **leakage** — it is released after the month ends — so T2 recomputes MV_m from SMARD data available by D−1, month-to-date per EEG Anlage 1 Nr. 3.3.2, falling back to the previous month's value on day 1 of a month. The published series is then used only to validate the recomputation.
  - **Reference period — [VERIFY] (v1.5).** EEG Anlage 1 Nr. 2 applies the *monthly* market value to plants commissioned or awarded before 1 Jan 2023; cohorts commissioned and awarded from 2023 may settle on the *annual* value (JW). If so, θ for those cohorts needs a year-to-date recomputation in T2. Hirth (2026, Table A1) lists the post-2023 onshore cohorts as monthly, which conflicts with that text; check the current Anlage 1 (amended 25 Feb 2025) before coding. Hirth also anchors his monthly reconstruction on the official annual value — that anchoring is leakage in T2.
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
- **Censored SCADA learning with known commands (Wang & Wang 2026, SSRN 7025858; shorter version 7195331; preprints).** Turbine-level, three Chinese farms: each sample is classified from command and status logs as a point, lower-bound or interval observation, and trained with pinball loss plus a survival loss −log(1 − F(L)). The censoring indicator and the bound are *observed*. Here neither is: price exposure does not mean curtailment, and the switched-off fraction is latent. They learn no response function. This is B4. (v1.5)
- **Two-stage residual and pooled response (Hirth, arXiv 2609.10053, version of 8 Sep 2026).** Potential model calibrated on hours > 5 €/MWh with ERA5; curtailment = residual, attributed wholly to exposed capacity; then **one pooled response curve** of the residual share against profit margin (price minus cohort threshold), Fig. 12. Hirth states himself that curtailment is not observed by cohort and that potential-model error enters curtailment one-for-one. Ex post, hourly, no forecast. This is B3. The cohort-by-hour threshold construction (including episode length) is his and is cited as such; this thesis claims only the step of placing it inside a jointly estimated observation model. (v1.5 — v1.4 wrongly said Hirth fits no response function.)
- Generic missing-not-at-random imputation: ignores the known structure (s, w), so it is weakly identified.

**Identification assumptions (each needs a test in the thesis)**
- I1 — no curtailment without incentive: if all s_k,t = 0 then c_t = 0. Test: placebo residuals on positive-price QHs. The current panel shows +0.9% to +2.8% relative bias at positive prices, so A must model the TSO forecast's own bias. **Split the placebo (v1.5):** report it separately for 0–5 €/MWh and > 5 €/MWh, because Hirth (2026, Table 3) finds 4.2% wind curtailment already in the 0–5 band. Intraday-driven curtailment (positive day-ahead, negative intraday price; Hirth Table A9) also violates I1 and is unobservable at D−1: in T2 it is irreducible noise and is reported as such; in T1 it can be stratified if a public intraday price series exists ([VERIFY] Netztransparenz ID-AEP).
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
- **Response head (v1.6):** a **monotone piecewise-linear** function of depth below θ — r_k(d, L) = clamp(base_k + Σ_j inc_j·ramp_j(d) + β·L, 0, 1), with base_k = σ(a_k), every inc_j ≥ 0 and β ≥ 0, on fixed knots (0, 1, 2.5, 5, 7.5, 10, 15, 20, 30, 40, 55, 75, 100, 150, 300 €/MWh). Monotone in depth and in run length by construction (I3). Shared increments plus per-cohort offsets. The knots are fixed once and are **not** chosen per r* shape. Beyond the last knot the response is flat in depth: extrapolating past the deepest prices ever observed would be inventing behaviour. The earlier sigmoid form σ(a_k + softplus(b)·depth + softplus(d)·runlength) is retained as an **ablation** — it can represent neither a step nor a constant partial compliance, which is why it was replaced (v1.6 minute).
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
| B3 | Hirth's pipeline: fit A on QHs with price > 5 €/MWh only; curtailment = residual; implied response = binned ratio of residual to exposed potential by profit margin (Hirth 2026, §6.4) | two-stage safe-period calibration |
| B4 | Wang & Wang's objective: pinball loss on non-exposed QHs; survival loss −log(1 − F̂(G)) treating G as a lower bound of A in **every** exposed QH | closest prior method: censored learning with a fixed, assumed censoring indicator |
| B5 | Quantile LightGBM on G with price and cohort-exposure features | strong black-box price-aware model |
| Proxy | Price-free: solar day-ahead forecast + day type, no price, no MaStR | the practitioner bar (`02_evidence_base.md` §B3) |
| Oracle | Trained on true A | synthetic benchmark only |

B5 is the one that keeps the comparison honest: it gets the same information as the
proposed model, without the structure.

**B5's estimate of A is the no-incentive counterfactual (v1.6).** Because B5 has the
price and exposure features it can and does reproduce the censoring, so its direct
prediction is a forecast of **G**. Scoring that against A_true would score it on a task
it was not given — it lands about 3,400 MW low on censored quarter-hours for exactly
that reason. Its A estimate is therefore the same quarter-hour re-predicted with the
incentive switched off: price at the safe level, every exposure, depth and run length
zero. That is what a practitioner holding this model would do, and it tests whether the
black box learned the mechanism well enough to extrapolate off the incentive — which is
what H4 claims it cannot.

**B3 bin edges — UNRESOLVED (v1.6).** Hirth bins the pooled response on profit-margin
bands (Fig. 12). Those edges are not recorded in this repo and the paper is not archived
in `data/raw/`, so they cannot be used yet, and they must not be guessed: invented edges
would make B3 a straw man and the comparison worthless. The interim is equal-count
quantile bins, flagged on every B3 result as `bin_source = equal_count_quantile`. How
much the choice is worth is recorded in `results/10_diag_b3_bins.csv`: on the logistic
shape int|r̂ − r*| for B3 moves from 0.2507 at 4 bins to 0.0115 at 64. Settle by reading
the edges off Hirth (2026) Fig. 12 or its underlying table.

**The price-free proxy is only half-built in E1 (v1.6).** The solar day-ahead series is
a Phase 3 ingest (SMARD `data_id` 125) and is not in the panel, so E1 runs the day-type
half alone and the baseline is weaker there than the published 11 % result it stands
for. Day type uses the **real** calendar date of each base quarter-hour, not the
synthetic timeline, which is a relabelling. German public holidays are not applied: the
calendar is federal-state specific and is not in the repo.

## 5a. The ablation ladder (v1.7)

A **baseline** is somebody else's method and answers *is this better than what
exists?*. An **ablation** is this method with one component switched off — same code,
same data, same seed — and answers *which part is doing the work?*. A method
contribution has to answer the second question, and no external baseline can. Both are
kept: ablations are the evidence that the structure earns its place, baselines are the
evidence that recent work did not already solve the problem (Iliev's rule).

Every rung differs from the full model in exactly one recorded field, asserted in code
(`src/censoring/run_ablations.py`), not trusted.

| Rung | Piece removed | What it isolates |
|---|---|---|
| M1 | — | the full model |
| A1 | the whole observation model (numerically the same estimator as B1) | the entire contribution |
| A2 | the EEG rule table: every cohort exposed in every quarter-hour, depth below zero | what the **legal structure** buys, over and above knowing the price |
| A3 | cohort structure: one fleet-wide cohort and one response | whether cohorts are needed, or one threshold suffices |
| A4 | the piecewise-linear response head (sigmoid instead) | whether the functional form matters |
| A5 | the multiplicative latent head (additive instead) | the kill test's ~9% proportional-haircut finding |
| A6 | the weather proxy | how much the second, price-blind anchor is worth |
| A7 | the leakage rule: price fed into g | what the rule is protecting against |

**A1 is listed twice on purpose**, as a baseline and as an ablation. It is the naive
model *and* M1 with the observation model removed; the two roles coincide, and saying
so is more honest than presenting one number under two names.

**A7 is read differently from the rest.** It should **not** look bad on the headline
error — if it did, the leakage rule would be self-enforcing and would need no test.
What it should damage is r̂: once A can see the price it absorbs the curtailment and
leaves the response head nothing to explain. A failure invisible in the headline error
and visible only in r̂ is exactly why the rule is enforced by a test rather than by
reviewer discipline.

## 6. Research questions and hypotheses

- **RQ1 (done):** Does price-driven censoring measurably bias the labels used for wind forecasting? → kill test v3, yes.
- **RQ2:** Can the mechanism-aware model jointly recover A and r_k, and under which conditions (I1–I4)?
- **RQ3:** How do deletion, safe-period calibration and fixed-rule censoring degrade as the censoring rate and the weather–price confounding increase, compared with the proposed model?
- **RQ4:** On real German data, does the structured model beat black-box price-aware learning (B5) in negative QHs, and does it transfer better across regulatory change?

- **H2:** On the semi-synthetic benchmark, the proposed model's error on A in censored QHs is significantly lower than B1–B4 at censoring rates ≥ 10%, and its r̂ curve error is lower than B3's implied response. **B4 prediction (v1.5):** because B4 treats exposed-but-uncurtailed QHs as mere lower bounds and its survival term only pushes upward, B4 should *overestimate* A when compliance is low or partial; the gap to the proposed model should be largest under the 50%-compliance r*.
- **H3:** On real data, the proposed model is at least as accurate as B5 in negative QHs (Diebold-Mariano, event-day block bootstrap) and better calibrated (interval coverage).
- **H4:** When trained before a rule change and tested after, the proposed model degrades less than B5, because the rule change enters through s_k,t rather than having to be relearned.
- Falsification: the H2/H3 tests are not significant, or the I1 placebo fails.

## 7. Experiments

- **E1 — semi-synthetic benchmark (do first; needs no MaStR, no ERA5).** Base data: uncensored QHs (price > 5 €/MWh). Treat their actual G as true A. Inject synthetic censoring: choose QHs with probability rising in F_t (confounding strength γ ∈ {0, 0.5, 1}), assign synthetic negative prices and run lengths, compute s_k with the real rule logic and synthetic cohort shares, apply known r*_k (step, logistic, 50%-compliance). Grid: censoring rate {5, 10, 20, 30, 40}% × γ × r* shape × 5 seeds. Metrics: MAE of Â on censored QHs, integrated absolute error of r̂ vs r*, 80/90% coverage, MAE on G, **CRPS and PIT histograms for A** (true A is known here, so calibration of P(A|x) can be checked directly). Add a weather-proxy arm: synthetic censoring with and without the weather covariate, to measure how much it helps identification.
- **Week-6 checkpoint — go/no-go on E1 (v1.7, due 31 Dec 2026).** Censoring rates
  ≥ 10%, seeds 42–46, all three r\* shapes. Every test is paired, with a 95% event-day
  block-bootstrap CI pooled over the five seeds.

  The gate is **self-contained**: it is decided by the known truth of the benchmark,
  by the published TSO forecast, and by our own oracle — never by how a rival method
  happens to behave. Pass needs all three:

  - **(a) Response recovery.** Integrated |r̂ − r\*| ≤ **0.05** at γ = 0 for each r\*
    shape. An absolute threshold, not a comparison: r\* is known, so "did we recover
    it?" needs no second method. (M1 is currently at 0.003–0.007.)
  - **(b) Latent-power recovery.** The recovery skill score
    S = (MAE_B0 − MAE_M1) / (MAE_B0 − MAE_oracle) ≥ **0.80** at γ ∈ {0.5, 1}, each
    shape. 1.0 is the oracle, 0.0 is the raw TSO forecast. The oracle is the
    information ceiling, so no method can exceed 1.0 and the v1.6 pathology — a
    baseline beating the ceiling on the gate's own metric — cannot recur.
  - **(c) Curtailment recovery.** ĉ against c_true on censored quarter-hours:
    correlation ≥ **0.8** and |mean ĉ − mean c_true| ≤ **0.05**. No baseline produces
    a per-quarter-hour ĉ at all, so this claim has no competitor by construction.

  **Reported but not required:** M1's skill score at least matching the best of
  B1–B5 at γ > 0, and the ablation ladder of §5a. A purely self-referential gate can
  be passed by a method no reviewer would accept, so the comparison is still run and
  still published — it simply does not decide the go/no-go.

  **Recoverable headroom.** MAE_B0 − MAE_oracle is only **125–241 MW** against a
  1,200–1,800 MW error. That bounds what any method can win on A-recovery, and it is
  why r̂ and ĉ are the headline claims and A-recovery is supporting. Report the
  headroom beside every skill score; a skill score without it invites the reader to
  imagine a larger prize than exists.

  On a fail: refit with the two-cohort / single-response structure and re-test by
  15 Jan 2027; if that also fails, the structure is not identified on this design —
  stop and agree the next step with the supervisor before any further real-data work.

  **Superseded wordings, kept for audit.**
  *v1.3 (replaced 30 Oct 2026):* pass if, at γ = 0, (a) integrated |r̂ − r\*| below
  B3's and (b) MAE of Â on censored QHs below each of B1–B4. Replaced because at
  γ = 0 censoring is random with respect to F, so deletion is unbiased by
  construction, B2/B3/B4 land on the oracle and (b) was unpassable.
  *v1.6 (replaced 31 Oct 2026):* (a) as above; (b) |bias| and curtailed-energy error
  below each of B1–B4 at γ ∈ {0.5, 1}; (c) no harm against B2 at γ = 0. Replaced
  because (b) was failed by the oracle itself — at γ = 1 deletion records |bias| 100 MW
  against the oracle's 141 MW while having the worse MAE, so the criterion rewarded
  cancelling errors — and because (a) on the step and half shapes compared two numbers
  at the noise floor (0.0031 against B3's 0.0017).

- **E2 — real data (task T2 unless stated).** 15-minute panel, Oct 2025 – Oct 2026, four control areas plus DE. Rolling origin by month, 7-day embargo, event-day blocks. Metrics on negative QHs and overall: MAE, pinball, coverage, bias by price band; Diebold-Mariano with event-day block bootstrap. 50Hertz and Amprion are primary (cleanest signal in v3).
- **E3 — regulatory transfer.** **Constraint found 29 Oct 2026:** only **199 negative QHs on 7 event-days** fall before 1 Jan 2026 in the 15-minute panel, so "train 2025, test 2026" is not feasible on that panel alone. Options: (a) add the hourly 2023 – Sep 2025 dataset (already planned in v1 §5.3), train before the 1 Jan 2026 staircase change and test after; (b) leave-one-cohort-out within 2026. Decide in month 2.
- **E4 — plausibility (domain result, secondary; task T1, ERA5 allowed).** Compare r̂ with the statutory "should switch off" curve and with Hirth's (2026) Fig. 12 pooled wind response by profit margin, aggregating quarter-hour r̂ to hours ([VERIFY] whether his "wind" includes offshore); report the compliance gap per cohort. Hirth's Table A11 (2026: 32.8% curtailed in negative runs ≥ 6 h vs 6.0% in 1–3 h) is a second check on the run-length term.
- **E5 — stretch.** Same code on solar curtailment (SMARD solar series), to show the method is not wind-specific; or the pre-auction price-forecast variant from v1.

## 8. Intended contribution to science — draft bullets (rewrite in your own words)

- A formal model of signal-driven partial censoring, where an observed external signal triggers a partial, heterogeneous response and a regulatory rule partly specifies the exposure.
- A jointly trained, monotone-constrained model that separates latent available power from fleet response, with stated identification conditions and tests for them.
- A semi-synthetic benchmark for **partial, signal-triggered, weather–price-confounded** censoring at fleet level (synthetic censoring with known truth as such is not new: Wang & Wang 2026 inject commands at 20–80%).
- Evidence on how safe-period calibration (Hirth) and fixed-indicator censoring (Wang & Wang) degrade when censoring is partial and latent, and as weather–price confounding γ grows (Wang & Wang already show command-as-label and deletion degrading with the censoring rate).

Iliev rule: do not write "first" or "no one has done this". Say what recent work does and
does not cover, with citations.

## 9. Literature to add (censored and missing-label learning side)

All entries are **[VERIFY]** — check each at the publisher before citing, following the
`02_evidence_base.md` practice. Log each in the literature table format from
`srh-guidelines/06_instructions_to_students_for_their_thesis.txt` (D).

- **Closest prior work — read first:** Wang & Wang (2026), SSRN 7025858 and 7195331. Reported to treat curtailed SCADA as censored observations of latent turbine available power, for grid set-point curtailment at three Chinese farms. **Verified 30 Oct 2026** from the full PDFs and SSRN records: authors Yang Wang and Haiyun Wang; 7195331 posted 28 Jul 2026 (35 pp.); 7025858 posting date [VERIFY] on SSRN. Both are un-refereed preprints of one study (identical data and tables): cite 7025858 as primary. See §3 for the positioning. Differentiate on: price signal rather than known command, fleet level, learned heterogeneous response, regulatory-clock identification.
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
- **Added v1.5 (all [VERIFY]):** Bruninx, van Binsbergen, Verstraeten, Nowé & Helsen (2026), arXiv 2602.13010v2 — deletion via ERA5 wind-bin percentile filter (B2 family); also shows ERA5 input beating every single D−1 NWP, evidence for the T1/T2 split. Dahl & Croonenbroeck (2014), *Energy* 73; Messner et al. (2014), *Wind Energy* 17 — censored wind-power forecasting (B4 lineage). From Hirth's list: Purkus et al. (2015); Frondel et al. (2022), *Energy Economics* 109; Van Steenberghe & Ovaere (2025), Ghent WP 25/1124; López Prol & Zilberman (2023), *Energy Economics* 126; Staffell & Pfenninger (2016), *Energy* 114; Fachagentur Wind und Solar (2025), Gütefaktoren; Hirth (2026) companion paper on the potential series (DOI forthcoming).

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

**Week-6 checkpoint (v1.7).** The gate is the three-part criterion in §7, due
31 Dec 2026, judged on seeds 42–46 at censoring rates ≥ 10%. It was revised twice —
on 30 Oct 2026 after the one-seed smoke run, and on 31 Oct 2026 after the nine-cell
preview, which made it self-contained. Both minutes and both superseded wordings are
in the changelog and in §7. **No further revision after the full grid has been run.** The full grid is 5 rates × 3 γ × 3 r\* shapes × 5 seeds =
225 cells, roughly 150 s per cell on the project machine (CPU, 4 threads), so about
9 hours — it is a background run, not an interactive one.

| When | Work | Deliverable |
|---|---|---|
| Nov wk 1–2 | Proposal (≥15 pages, own writing, incl. "Intended Contribution to Science"); literature table; 30-min topic defence with supervisor | approved proposal, registration |
| Nov wk 3–4 | E1 generator, proposed model v0, baselines B0–B4 | first synthetic results |
| Dec | E1 full grid; MaStR ingest and cohort shares; B5 | RQ2/RQ3 results; week-6 checkpoint (§7 criterion as revised in v1.6, 31 Dec) |
| Jan | E2 real data; hourly 2023–Sep 2025 ingest; E3 design decision | RQ4 results |
| Feb | E3, E4, ablations; paper draft (8–12 pages) | paper draft |
| Mar | Thesis writing (≥20,000 words) | full draft |
| Apr | Buffer, code release, defence slides (numbered 1/N) | submission |

## 12. Repo changes

Implemented by Claude Code from `CLAUDE_CODE_PROMPT.md`.
