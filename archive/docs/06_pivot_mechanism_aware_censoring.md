# 06 — Pivot: from forecast correction to mechanism-aware censored learning

Version 1.9, 8 Nov 2026 (v1.8: commit d86e12d; v1.7: commit 9454c8c; v1.6: commit 46026bf; v1.5: commit 8e3b708; v1.4: commit
4b9dc8c; v1.3: commit 2538e56; v1.2: commit 980cd30; v1.1 and v1: not committed).
Working spec, not proposal prose.

> **Numbering note.** The audit that prompted this revision called it "v1.4", tracking
> the §3 I4 clause's own lineage (v1.2 pre-registered the day count, v1.3 made the
> fallback pool r rather than s). But v1.4 is already taken by a whole-spec revision of
> 30 Oct, and the doc versions the spec rather than the clause, so this is **v1.9**.

**Changes in v1.9** (8 Nov 2026, after `docs/13_theta_audit.md`). **Nothing here is
pre-registered.** v1.8's minute reads "No further gate changes without the student's
written decision", and the two proposals below are gate changes. They are recorded so
they can be adopted *before* the merged grid is scored — a fallback or a drop trigger
chosen with the gate result in hand is not a pre-registration — and they take effect
only on that written decision.

- **§3 I4: the v1.3 clock fallback is retired as inexecutable.** It assumed the price
  clock selects which price a cohort compares against. It does not: the clock selects
  the **θ branch** (§3's own wording at `docs/06:266` and `s_k,t = 1[p_t < θ_k,t]` at
  `:302`), and the comparison is always against the quarter-hour price. Once
  indistinguishable cohorts are merged, the only quarter-hour-clock cohort is absorbed
  into a group whose θ is 0 at every quarter-hour, every survivor carries the hour
  macro, and the partition has **M = 1**. Measured, not inferred: the macro-aggregated
  matrix `A_m = Σ_{k∈m} w_k s_k` has one row. Replaced by a three-tier ladder on the θ
  regime, below.
- **§3 I4: the drop trigger is replaced.** `exposure_differs_by_day` asks whether
  cohorts differ *somewhere*; it is satisfied by one differing pair while every other
  pair is identical, and it cannot see rank. All 81 stored gate cells pass it and fail
  a criterion that tests identification. New trigger: full rank on the feature block
  `[s | depth]`, every cohort pair differing on at least 10 quarter-hours, and
  `cond(s) ≤ 100`. The day count is **demoted to a reported diagnostic**.
- **I4 is not robustly identified on real data (v1.9).** v1.8 already said separation is
  gated by the premium and that the low AW setting "is far closer to [the threshold]
  than the headline 55 suggests". The audit quantifies how much closer: θ is
  **identically 0 fleet-wide** in 8 of 9 usable months at AW low, 4 of 9 at main, 7 of 9
  under the base-tariff stress case, and 0 of 9 at high. At AW low every separating
  quarter-hour falls in a **single month** (April 2026). See §3 I4 and
  `docs/13_theta_audit.md`.
- **The market-value series is verified (v1.9).** The MP = 0 shares depend on MV being
  the wind market value rather than a base-load or monthly-average series, which would
  be systematically too high and would drive MP to zero artefactually. The loader reads
  the row `"MW Wind an Land"` from `Monatsmarktwerte_2026.csv`; recomputed independently
  from the panel as the onshore-weighted average spot price, it sits below the simple
  monthly mean in **9 of 9** months (capture rate 0.717–0.977, mean 0.826) and below the
  recomputation in 9 of 9. It is the right series, and in the conservative direction: a
  lower MV gives a *larger* premium, so MP = 0 occurs despite the more generous input.
- **Study-window coverage is 92.9%, and was 69.4% because of a loader bug (v1.9).** θ needs
  a published monthly market value. `read_published` was hard-coded to
  `Monatsmarktwerte_2026.csv` while the 2025 file sat unread beside it, so Oct–Dec 2025 were
  silently dropped and every real-data θ figure covered nine months of 2026. Fixed to read
  all year files: **12 of 13** months, 35,040 of 37,732 quarter-hours, exposed quarter-hours
  1,853 → 2,052. Only Oct 2026 is legitimately absent (incomplete, and published after month
  end). The gap survived because nothing asserted coverage;
  `tests/test_market_value_coverage.py` now does. **The identification verdict is unchanged**
  — Nov and Dec 2025 have no negative-price quarter-hours, so the whole gain is Oct 2025.
  `docs/14_mv_coverage_fix.md`.

**Changes in v1.8** (31 Oct 2026, student decision).

> **Minute — final revision; criteria fixed before the reduced grid.** v1.7's
> absolute-only gate is withdrawn. Comparative criteria return as the primary test,
> with v1.7's absolute thresholds retained as secondary floors. **No further gate
> changes without the student's written decision.**

- **§7: the gate is comparative again**, in the form below. v1.7's absolute
  thresholds stay as **secondary floors**, explicitly labelled *set after the
  one-seed smoke run* so a reader knows they were chosen with sight of data.
- **§7 (b) is now bias and curtailed-share MAE**, and **every baseline is scored on
  ĉ too**, via ĉ = 1 − G/Â.
- **Correction.** v1.7 claimed no baseline produces a per-quarter-hour ĉ, and built
  a criterion on that. It is wrong: any method with an Â implies ĉ = 1 − G/Â. What
  is distinctive about M1 is that its ĉ is a *structural* output of the observation
  model, not a residual of its own A-estimate — a narrower and defensible claim.
- **§7 E2: switch-back validation and an aggregate volume check** added.
- **§7 E3: the 1 Jan 2026 confound** recorded — two things happen at once.
- **E1 now uses the real MaStR cohort shares**, not the invented dict.
- **§51a RESOLVED (31 Oct 2026), §51a(1) EEG 2023 read at source.** The support-period
  extension counts zeroed quarter-hours **regardless of the plant's own output**, so the
  deferral is identical whether the plant produces or switches off and cancels out of the
  within-quarter-hour decision. **θ = 0 under an active §51 trigger stands**; the
  [VERIFY] is closed and the proposed sensitivity arm is withdrawn. Hirth's pricing of
  §51a as a discounted deferral assumes an output-dependent extension and so does not
  apply.
- **Real award values AW_k** from the BNetzA tender statistics, weighted by built MaStR
  capacity (`results/31_award_values.csv`).
- **Market value recomputation is NOT validated** and must not build θ yet — see §3.
- **The market-premium channel IS live where it matters (v1.8, corrected).** An
  earlier pass reported 100% of capacity at MP = 0 in six of nine months and
  concluded the premium barely separates cohorts. That was wrong twice over: it
  covered only the 22.8 GW of *tendered* capacity, and it compared every unit with
  the monthly MW even where Anlage 1 Nr. 2 prescribes the annual JW. Redone per
  unit with the correct reference and with Hirth Table A1 status-A values for the
  non-tendered fleet, and **weighted by negative-price quarter-hours** rather than
  by month: **48.4%** of in-support capacity has MP = 0 when the price is actually
  negative, against an unweighted monthly mean of 57.5%. The weighting matters
  because the months with the most negative quarter-hours are exactly the months
  with the lowest MP = 0 share — April carries 492 of the 1,853 negative
  quarter-hours and sits at 1.9%. So **I4 does not rest mainly on the §51 clocks**:
  roughly half the in-support fleet carries a live premium in the quarter-hours
  where θ is actually tested, and the premium and the clocks identify cohorts
  together. `results/35_market_premium_zero.csv`.
- **MP = 0 shares are a lower bound (v1.8).** Table A1's values are *blended* over
  the initial and base tariff. A plant that has dropped to the base tariff, roughly
  5 ct/kWh for these vintages, has MP = 0 against any 2026 market value, so the
  blended figure overstates the premium for that part of the fleet. No per-plant
  tariff-phase modelling is done and none is planned: a named limitation.
- **AW for non-tendered capacity is now a status-A estimate (v1.8).** 36.3 GW of
  in-support, never-tendered capacity takes Hirth (2026) Table A1 values
  (`docs/literature/hirth_2026_2609.10053v1.pdf`, App. A2 pp. 26–28): 8.0 ct/kWh up
  to 2002, 8.5 ct 2003–2011, 8.9 ct 2012–2015 incl. the management premium, 7.6 ct
  2016–2020 — all labelled *"Hirth (2026) Table A1, own estimate, status A"* with a
  ±15% band. The 22.8 GW of tendered capacity keeps its BNetzA round value times
  the §36h factor; **Hirth's tendered-cohort bids are deliberately not used**,
  because they disagree with the BNetzA statistics, notably for 2021–22. A further
  12.5 GW is out of support and carries θ = 0 with no AW at all, and 1.20 GW is on
  a feed-in tariff, where θ does not exist rather than being 0 (Table A1 puts the
  feed-in-tariff share at 5.0% of each pre-2016 vintage; MaStR does not identify
  which units they are, so the share is applied within the vintage and labelled).
- **Anlage 1, §36h and §51a read at source (31 Oct 2026, texts in `docs/legal/`).**
  The reference period, the correction table and the §51a question are all settled;
  what replaces them is a single new dependency, the Online-Hochrechnung. See §3.

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
- **§7: new metric, curtailment recovery** — ĉ against c_true.
  **Corrected in v1.8:** the v1.7 text claimed no baseline produces a per-quarter-hour
  ĉ. That was wrong. Any method with an estimate of available power yields one by
  ĉ = 1 − G/Â, so every baseline can be scored on it and must be.
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
  - **Reference period — RESOLVED 31 Oct 2026 (v1.8), EEG Anlage 1 Nr. 2 read at
    source (`docs/legal/anlage1_EEG2023.pdf`).** A unit uses the **monthly** market
    value MW if it was commissioned before 1 Jan 2023 **or** its award was granted
    before 1 Jan 2023 — either condition suffices — and the **annual** value JW
    otherwise. This is per unit, not per cohort, so θ carries both: for
    annual-reference units θ = −max(0, AW − JW). On the MaStR snapshot that is
    60,360 MW monthly (28,085 units) against 11,216 MW annual (2,355 units).
    **Hirth (2026, Table A1) lists the post-2023 onshore cohorts as monthly; the
    statute governs, and the discrepancy is noted here rather than reconciled.**
    Remaining **[VERIFY]:** whether the 01.12.2022 round counts as awarded in 2023.
    Both readings are computed; the difference is **173 MW**, 0.24% of the fleet,
    so it cannot change a conclusion. In T2 the JW is year-to-date from data up to
    D−1; for T1 in 2026 the year-to-date JW is used and labelled approximate,
    because the year is not over.
  - **MV and JW must be weighted by the Online-Hochrechnung, not by metered
    output (v1.8).** Anlage 1 Nr. 3.3.2 defines MW_onshore as the spot price
    weighted by "the amount of electricity generated in that quarter hour from
    onshore wind turbines **according to the online projection in section 5.1**".
    Recomputing on SMARD's realised generation is therefore not an approximation of
    the legal definition but a different quantity, which is why the first attempt
    missed the published series by up to 25%.
  - **Anlage 1 Nr. 5.1 — the online projection is a curtailment-free potential
    (v1.8).** Verbatim: *"Reductions in the feed-in power of the plant by the grid
    operator or within the framework of direct marketing are not to be taken into
    account when creating the online projection."* Both grid curtailment and
    price-driven switch-off are excluded **by law**. If the published series
    complies, it is an official, public, quarter-hourly estimate of uncurtailed wind
    potential — which is very close to A, the quantity this thesis exists to
    recover. That would be a major input and a major caveat at once, so it is tested
    before it is used: see the pre-E2 check in §7. Compliance is a legal
    requirement, not a guarantee of practice.

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
- I4 — separability of cohorts: cohorts enter `c = Σ_k w_k s_k r*(depth_k)` only through
  the pair `(s_k, depth_k)`, and that pair depends on the cohort only through **θ_k on the
  exposed set**. Two cohorts whose θ agrees wherever either is exposed are therefore
  bit-identical in every feature a model can see, for any price series. The identifying
  variation is **θ separation**, which has three channels: the gap between θ = 0 (support
  zeroed, by §51 or by the end of support) and θ = −MP; the run-length thresholds that flip
  a cohort between them; and the spread of MP across cohorts.

  **Tiered fallback (v1.9, PROPOSED — see the v1.9 note; not pre-registered).** Each tier is
  entered only when the tier above fails the drop trigger, and the tier actually used is
  reported with the result.

  | tier | structure | measured conditioning |
  |---|---|---|
  | 1 | K cohorts, response per cohort | benchmark rank 6/8 unmerged, 6/6 merged; real panel 7/8 (`low`/`main`/`high`), 6/8 (`stress`) |
  | 2 | macro-cohorts by **θ regime** — always 0 / switching / never 0 — pooling r within a macro, `s_k` still per legal cohort | benchmark M = 3, cond 6.2; real panel M = 2, cond 6.7 ("never 0" empty) |
  | 3 | one shared monotone r over per-cohort exposures | always available |

  Tier 2 replaces v1.3's clock partition, which is inexecutable after merging (M = 1).
  **Tier 2 is identified, not strongly identified:** its weakest pair of macro profiles
  differs by a mean of **0.0137** on the benchmark and **0.0191** on the real panel, against
  0.0407 for the clock partition before merging. It will run; what it recovers will be
  imprecise, and that goes in the write-up rather than a footnote.

  **Tier 3 changes the claim, not just the estimator.** With one shared r the result is a
  statement about the *structural* form — censoring is price-driven and monotone in depth —
  and no longer about cohort heterogeneity. RQ2's "and r_k" clause cannot be answered from
  tier 3, and any cohort-level number reported from it would be the shared curve relabelled.

  **Drop trigger (v1.9, replaces the v1.2 day count).** Evaluated on the evaluation window,
  per AW setting, before any modelling: (i) full rank on the feature block `[s | depth]`,
  with `rank(s)` reported alongside — not `rank(s) == K`, which fails a pair that is weakly
  identified through depth but genuinely identified; (ii) every cohort pair differing on at
  least **10** quarter-hours, inheriting v1.2's figure but applied per pair rather than as a
  day count; (iii) `cond(s) ≤ 100`, a backstop calibrated so a design whose worst pair
  differs on 0 or 1 quarter-hours is rejected. **Not `cond(w·s)`** — it is nearly blind to
  near-collinearity (543.6 with one differing quarter-hour against 602.2 untouched, and it
  *falls* as duplication worsens); report it, never gate on it. Cohorts are merged on the
  realised `(s, depth)` block before the trigger is read, with the legal labels kept as
  metadata; **not** on θ, which is sufficient but not necessary and misses the collinear
  pair entirely at AW `high`.

  **Where tier 1 actually stands on real data (v1.9).** θ is identically 0 fleet-wide — no
  cohort structure of any kind — in **8 of 9** usable months at AW `low`, **4 of 9** at
  `main`, **7 of 9** under the base-tariff stress case, and **0 of 9** at `high`. At `low`
  all 492 separating quarter-hours fall in one month. Of the three channels, the premium
  spread is much the richest (mean 4.4–7.0 distinct θ values where live) while the trigger
  and support-status channels are binary by construction (2.0) — so separation rests on the
  channel that disappears whenever MV ≥ AW. **Tier 1 is identified at `high`, weakly at
  `main`, and not identified at `low` or under stress.** Since rule 19 requires the result
  to be stable across all three AW settings, tier 1 is **not robustly identified**, and
  which tier the thesis runs on is a supervisor decision rather than an outcome of the gate.
  `docs/13_theta_audit.md`.

  **Superseded wordings, kept for audit.** *v1.2* (replaced 8 Nov): "before any modelling on
  real data, count the Berlin-local event-days on which the cohort exposure vectors s_k
  actually differ. Fewer than **10** such days and the K-cohort model is abandoned for the
  two-cohort one, with the count reported either way." — the count is retained as a
  **reported diagnostic**; it no longer triggers anything, because it is satisfied by a
  single differing pair and cannot see rank. *v1.3* (replaced 8 Nov): "the two-cohort
  fallback **pools the response r, not the exposure s**; the run-length thresholds (6 h, 4 h,
  2 h) remain identifying variation." — pooling r and not s carries over to tier 2 unchanged;
  what is retired is the **clock** partition it pooled over. The run-length thresholds remain
  identifying variation, now as one of the three θ channels, and are the binary one.

**I4 on real data — cohort separation is gated by the market premium (v1.8,
31 Oct 2026).** The pre-registered rule-18 count was run on real 2026 data with
real MaStR shares, the per-unit AW provenance, published MW/JW and real prices:
**55 event-days** with differing cohort exposure against a threshold of 10, so the
K-cohort model stands. Decomposed by quarter-hour, the §51 clock **never**
separates cohorts on its own (0 of 803); the premium alone accounts for 169 and
both channels together for 634. The reason is structural: θ = 0 both when the §51
trigger fires and when the premium is zero, so where MP = 0 the trigger changes
nothing. Repeated across rule 19's AW settings and a base-tariff stress case
(all pre-2016 in-support capacity forced to MP = 0):

| setting | QHs differing | event-days | verdict |
|---|---|---|---|
| AW low | 292 | 19 | K-cohort stands |
| AW main | 803 | 55 | K-cohort stands |
| AW high | 1,220 | 71 | K-cohort stands |
| base-tariff stress | 362 | 29 | K-cohort stands |

All four clear the threshold, but the low setting at 19 days is far closer to it
than the headline 55 suggests. **Because separation is gated by the premium, the
stability of r̂ across these three θ settings is the primary real-data
identification check** — not the day count, which only says the variation exists.
`results/38_rule18_settings.csv`.

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
- **E1-MNAR arm — CONSIDERED AND CANCELLED, 31 Oct 2026 (student's decision).** The
  proposal was a fourth E1 arm whose placement weight was exp(γ·z(A − F)) rather than
  exp(γ·z(F)), or which used a synthetic "market forecast" closer to A than F — i.e.
  censoring that depends on the thing being recovered, making it missing-not-at-random.
  It was to be pre-registered as post-fail and exploratory, never a gate replacement.
  **Cancelled before it was built**, because 4a-proper removed its real-data
  motivation: above 5 €/MWh, where no switch-off incentive exists, the price does not
  predict log(G/F) once F is controlled for — the (5,20] versus (50,100] contrast
  excludes zero in neither DE nor 50Hertz, and the signs differ (+0.041 and −0.015).
  Bracketed on the treatment that keeps all 942/961 quarter-hours, the effect sits
  near zero from both sides (`results/16_4a_proper_placebo.csv`). An MNAR arm with no
  evidence of MNAR behaviour in the real data would be a synthetic construction
  answering a question the data does not pose. **Not deferred — dropped.** Reopening
  it needs a written decision and new evidence.
- **Week-6 checkpoint — go/no-go on E1 (v1.8, due 31 Dec 2026).** Censoring rates
  ≥ 10%, seeds 42–44 on the reduced grid, all three r\* shapes. Every test is paired,
  with a 95% event-day block-bootstrap CI pooled over seeds. Pass needs all three:

  - **(a) γ = 0, each r\* shape.** Integrated |r̂ − r\*| lower than B3's implied
    response.
  - **(b) γ ∈ {0.5, 1}.** Both the **absolute bias of Â** and the **curtailed-share
    MAE** (ĉ against c_true) lower than each of B1–B4. Every baseline's ĉ is
    **1 − G/Â**; M1 is scored the same way, so the comparison uses one formula for
    everyone. M1's structural ĉ = Σ w·s·r is reported alongside as its real output.
  - **(c) γ = 0.** M1's MAE not significantly worse than B2 — the no-harm clause.

  **Secondary floors (set after the one-seed smoke run, 30–31 Oct 2026).** Reported
  with the verdict, not part of the pass: integrated |r̂ − r\*| ≤ 0.05; recovery skill
  S = (MAE_B0 − MAE_M1)/(MAE_B0 − MAE_oracle) ≥ 0.80 at γ > 0. They were chosen with
  sight of one seed's results and are labelled as such, so they carry less weight
  than the comparative criteria.

  **Recoverable headroom** (MAE_B0 − MAE_oracle) is reported beside every skill
  score. It was 125–241 MW against a 1,200–1,800 MW error on the one-seed preview;
  a skill score without it invites the reader to imagine a larger prize than exists.

  On a fail: refit with the two-cohort / single-response structure and re-test by
  15 Jan 2027; if that also fails, the structure is not identified on this design —
  stop and agree the next step with the supervisor before any further real-data work.

  **Superseded wordings, kept for audit.** *v1.3* (replaced 30 Oct): γ = 0 only, MAE
  below each of B1–B4 — unpassable because deletion is unbiased at γ = 0. *v1.6*
  (replaced 31 Oct): |bias| and curtailed-energy error at γ > 0 — failed by the
  oracle itself, which records a larger |bias| than deletion while having the better
  MAE. *v1.7* (replaced 31 Oct): absolute thresholds only — withdrawn by the student
  as insufficiently comparative, and one of its criteria rested on the mistaken claim
  that baselines have no ĉ.

  **E1 design findings, recorded 31 Oct 2026. These change nothing in the gate** —
  the criteria, thresholds and fail branch above stand exactly as written. They are
  recorded because they govern how the verdict should be *read*, and because each was
  found while building the gate rather than inferred afterwards.

  **(i) The placement weight makes the censoring MAR given F, so criterion (b) has
  near-zero discriminating power.** Quarter-hours are selected with weight
  exp(γ·z(F_t)), which depends only on the day-ahead forecast — a variable *every*
  baseline observes. Censoring is therefore missing-at-random conditional on F, and
  simple deletion stays unbiased however large γ grows. The pooled absolute bias of
  B2 across the 31 Oct grid bears this out: 92.5 MW at γ = 0, 14.8 at γ = 0.5, 0.4 at
  γ = 1 — deletion gets *better* as the confounding strengthens, which is the opposite
  of what the design intended. A criterion asking M1 to beat deletion on bias under
  confounding cannot discriminate when the confounder is observed by both. This is a
  property of E1's generator, not a result about M1.

  **(ii) No method has an hour feature, so all of them share a ~900 MW diurnal bias,
  part of which criterion (b) scores.** `LATENT_ALLOWED_FEATURES["E1"]` is
  {forecast_mw, weather_ms}. There is a real diurnal component in A given F that none
  of the methods can represent. At γ = 0 the bias runs from −851 (B0), −593 (M1),
  −592 (Oracle) MW at 23:00 to +149, +285, +294 at 10:00: a swing of 872–1,049 MW
  against a pooled bias of −136 to −323 MW (`results/17_bias_by_hour.csv`). **The
  Oracle is trained on the true A and carries a spread of 886 MW**, so this is a
  shared specification gap, not a modelling failure of any one method. The pooled
  γ = 0 bias is the incomplete cancellation of that swing. Criterion (b) is therefore
  partly measuring a missing feature common to every method rather than anything about
  censoring.

  **(iii) Criterion (a) is sensitive to B3's bin count, which is my choice and not
  Hirth's.** From `results/10_diag_b3_bins.csv`, integrated |r̂ − r*|:

  | shape | 4 bins | 8 bins | 16 | 32 | 64 |
  |---|---|---|---|---|---|
  | logistic, B3 ÷ M1 | 58.4× | 47.9× | 25.5× | 5.5× | 2.7× |
  | step, M1 better | no | no | no | no | no |
  | half, M1 better | no | no | no | no | no |

  M1's advantage on the logistic shape falls from about 50× at 8 bins to about 3× at
  64, while **B3 is the better estimator on step and half at every bin count tested**.
  `HIRTH_FIG12_MARGIN_EDGES_EUR_MWH` is still `None` [VERIFY], so B3 uses equal-count
  quantile bins at the default of 8 — a choice that is worth a factor of twenty to the
  one shape M1 wins. The gate's bin count stays at 8 as pre-registered; this is
  recorded so that an (a) result on the logistic shape is never read as a clean 50×
  margin.

- **Pre-E2 check — does the Online-Hochrechnung actually ignore curtailment?
  (v1.8, blocking).** Anlage 1 Nr. 5.1 says it must. Test it before any E2 fitting:
  in negative-price quarter-hours, compare the Netztransparenz Online-Hochrechnung
  for wind onshore against the SMARD actual, per control area — bias and ratio by
  price band, with the event-day block bootstrap. **If the projection does not fall
  with the curtailment** (i.e. the gap to the metered actual widens as prices go
  negative), it is behaving as the law requires and becomes an **external, ex-post
  proxy for A**: admissible in T1 and as validation, and added to the leakage list
  as **never a T2 input**, since it is published after the fact. **If it does fall
  with the curtailment**, the projection is tracking metered output, it is not a
  potential series, and it must not be used as one. Report the result before
  deciding either way. **Status, 31 Oct 2026: RAN, and the download is the wrong
  series.** The Netztransparenz "Hochrechnung Windenergie" export is **1.57% of the
  SMARD metered onshore actual** over six sample days, region-dependent — 50Hertz
  0.89%, Amprion 1.55%, TenneT 2.17%, TransnetBW 0.05% (never above 1.0 MW) — while
  correlating 0.80–0.995 with it. It tracks wind but covers a tiny subset, so it is
  **not** the fleet-level Nr. 5.1 projection. Labelled **"EEG-vermarktete
  Windeinspeisung [VERIFY]"**; **not** to be used for MV/JW or as a proxy for A, and
  kept only as a candidate for sizing the feed-in-tariff cohort
  (`results/34_hochrechnung_check.csv`).

  **RESOLVED 1 November 2026: the Nr. 5.1 compliance check has RUN and PASSES in all
  four control areas.** The genuine fleet-level series arrived — Online-Hochrechnung
  Wind Onshore, 2026-09-01 to 2026-10-29, 5,668 quarter-hours, all four TSOs
  populated. The test code was committed in `a2e3262` before the data existed, so the
  verdict is pre-registered. R = projection ÷ (SMARD metered actual + onshore
  renewable redispatch), so redispatch is added back and cannot masquerade as
  compliance (`results/39_nr51_compliance.csv`):

  | area | R(> 5) | R(0–5) | R(−5–0) | R(−20–−5) | R(neg) | verdict |
  |---|---|---|---|---|---|---|
  | 50Hertz | 1.040 | 1.098 | 1.392 | 2.317 | 1.635 | PASS |
  | Amprion | 1.022 | 1.120 | 1.373 | 2.324 | 1.611 | PASS |
  | TenneT | 0.839 | 0.887 | 1.111 | 1.785 | 1.281 | PASS |
  | TransnetBW | 1.033 | 1.172 | 1.522 | 3.872 | 1.808 | PASS |

  Monotone in every area; the −5 to 0 band's CI excludes the positive-price baseline
  in all four (50Hertz [1.303, 1.507] against 1.040). Sample 58 days, **9 carrying a
  negative quarter-hour**. The −20 to −5 band rests on 18 quarter-hours over fewer
  than two event-days, so its CI is [nan, nan] — **point estimate, no inference**.

  **Consequence, as this bullet pre-committed:** the projection does not fall with the
  curtailment, so it **becomes an external, ex-post proxy for A** — admissible in T1
  and as validation, and **added to the leakage list as NEVER a T2 input**, since it is
  published after the fact.

  **Caveat on levels, not on the verdict.** TenneT's positive-price baseline is 0.839:
  its projection runs about 16% *below* the metered actual where no curtailment is
  expected. The test uses the *change* across price bands, not the level, so the
  verdict stands — but the level bias means the series cannot be used as a direct
  magnitude for A in TenneT without a calibration step.

  **Baseline corrected (31 Oct 2026).** Nr. 5.1 excludes grid-operator reductions
  as well as direct-marketing ones, so the comparator is the SMARD actual **plus
  onshore wind redispatch**, not the actual alone. On 2026-10-30 the raw excess was
  +3.5% over three areas (50Hertz +8.2%, Amprion +2.8%, TransnetBW +1.7%). That
  cannot be a curtailment-free baseline: the committed redispatch export stops on
  28 Oct, but in its last covered week onshore wind redispatch averaged 98.4 MW in
  50Hertz and 68.5 MW in Amprion, both **larger** than the 47 MW and 60 MW excess
  measured on the 30th. Redispatch of that size would absorb the excess entirely in
  those two areas. **The 1.035 figure is withdrawn as a baseline**; the real
  baseline is the > 5 €/MWh band over the full range with an event-day bootstrap,
  and it needs projection data inside the redispatch export's window.
  TransnetBW had no wind redispatch at all that week, and its +1.7% (12 MW) stands
  unexplained.

  **The two series are not independent (31 Oct 2026).** SMARD's "actual" may itself
  derive from the TSO extrapolation — TransnetBW correlates 1.000 and TenneT/Amprion
  0.99+ — so outside curtailment the comparison is close to self-referential. Only
  the negative-price quarter-hours are informative, which is what the check is for.

- **E2 — real data (task T2 unless stated).** 15-minute panel, Oct 2025 – Oct 2026, four control areas plus DE. Rolling origin by month, 7-day embargo, event-day blocks. Metrics on negative QHs and overall: MAE, pinball, coverage, bias by price band; Diebold-Mariano with event-day block bootstrap. 50Hertz and Amprion are primary (cleanest signal in v3). **TenneT is NOT significant in the kill test** and must be reported as such wherever area results appear: mean day-ahead error -325.9 MW, 95% event-day CI [-838.3, +137.6], `ci_excludes_zero=False`, -3.6% of forecast (`results/02_overall_negative_qh_bias.csv`, row "TenneT DE"). It is the one control area where the kill test found no significant negative-price bias.
  **Order (v1.8):** DE first, then 50Hertz — which is unaffected by the split-state
  control-area proxy — then the remaining areas only after the Netzanschlusspunkte
  fix lands.
  **Switch-back validation (v1.8).** Real data has no A_true, so recovery cannot be
  scored directly; the nearest observable is the switch-back. Compare Â in the last
  negative quarter-hour of an episode with observed G in the first positive
  quarter-hours after it: if Â was right, the two should line up once the incentive
  goes. Wang & Wang (2026) validate on release events in the same spirit; cite them.
  Confounded by ramping, so report the ramp rate alongside.
  **Aggregate volume check (v1.8).** Total recovered market curtailment for
  Jan–Aug 2026 against Hirth (2026). [VERIFY] whether his wind figure includes
  offshore before comparing; this project's panel is onshore plus offshore by area.
- **E3 — regulatory transfer.** **Confound, found 31 Oct 2026 (v1.8): two things
  happen on 1 Jan 2026.** The 2023 – Feb 2025 staircase steps 3 h → 2 h, *and* the
  2005 commissioning vintage leaves EEG support (20 years plus the commissioning
  year, §25), moving that capacity's threshold from −MP to 0. Both change exposure
  on the same date, in the same direction. E3 must separate them — the staircase hits
  one cohort and the support expiry another, so the capacity shares identify them
  separately, but a naive before/after comparison attributes the sum to the rule
  change. **Constraint found 29 Oct 2026:** only **199 negative QHs on 7 event-days** fall before 1 Jan 2026 in the 15-minute panel, so "train 2025, test 2026" is not feasible on that panel alone. Options: (a) add the hourly 2023 – Sep 2025 dataset (already planned in v1 §5.3), train before the 1 Jan 2026 staircase change and test after; (b) leave-one-cohort-out within 2026. Decide in month 2.
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
- Cohorts not separable → drop a tier: macro-cohorts by **θ regime**, pooling r but not s; then one shared r. The v1.3 clock partition is retired as inexecutable after merging (v1.9, §3 I4).
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

  **Noise-audit minute, 1 November 2026. No criterion, threshold or verdict changes.**
  Four corrections to how the week-6 gate is inferred and reported, decided **before
  the 81 cells were scored**.

  **(1) Criterion (a) now has a stated inference procedure.** The pre-registered
  statistic — integrated |r̂ − r\*| over the uniform depth grid — is a functional of a
  fitted curve and admits no event-day bootstrap CI without refitting the model on each
  resample. It is therefore judged, **per shape, by an exact two-sided sign test over
  the 9 paired cells** (3 rates × 3 seeds), with **pass requiring M1 lower in at least
  8 of 9** (exact two-sided p = 0.0391 at 8/9, p = 0.0039 at 9/9). All nine paired
  differences are reported. The criterion itself is unchanged; only its inference is
  now specified instead of improvised. The per-quarter-hour `fleet_r_err` figure is
  **a substitute statistic, supplementary only**, and cannot decide (a).

  **(2) Design finding (iii) is CORRECTED. Its figures came from one seed and two of
  its three claims were wrong.** Recomputed over seeds 42–44 at γ = 0 at all three
  censoring rates — 9 cells per shape — by rebinning the stored per-quarter-hour
  predictions with no refitting (`results/19_b3_bins_multiseed.csv`):

  | shape | bins | B3 ÷ M1, mean | range | M1 lower in |
  |---|---|---|---|---|
  | logistic | 8 | **20.71** | [14.42, 26.72] | 9/9 |
  | logistic | 64 | **1.17** | [0.79, 1.52] | 8/9 |
  | step | 4 | 1.48 | [0.75, 2.12] | **6/9** |
  | step | 8 | 1.11 | [0.65, 1.44] | **5/9** |
  | step | 16 | 0.85 | [0.51, 1.15] | 4/9 |
  | half | 8 | 0.47 | [0.18, 1.29] | 1/9 |
  | half | 64 | 0.65 | [0.24, 1.47] | 2/9 |

  - The superseded figures **47.9× at 8 bins and 2.7× at 64 are withdrawn.** They were
    a single seed at a single rate; the correct multi-seed means are **20.71×** and
    **1.17×**, and the 64-bin range **crosses 1.0**, so at 64 bins B3 and M1 are
    **equivalent on logistic**, not 2.7× apart. Do not quote the old numbers.
  - The claim that **"B3 is the better estimator on step and half at every bin count"
    is FALSE for step at the coarse end**: M1 is lower in 6 of 9 cells at 4 bins and
    5 of 9 at 8 bins. B3 is better on step only from 16 bins upward. The claim holds
    for `half` at every bin count tested.
  - What survives unchanged: criterion (a) is strongly sensitive to a bin count that is
    **my choice and not Hirth's** (`HIRTH_FIG12_MARGIN_EDGES_EUR_MWH` is still `None`),
    and the sensitivity runs the full distance from a 20× gap to equivalence.

  **(3) 4a-proper's exploratory tests are Holm-adjusted, and the > 150 band does not
  survive.** The script ran **94 exploratory tests** (band × stratum × treatment ×
  area) besides the one pre-registered contrast. 27 are significant unadjusted and
  **8 after Holm** (`results/16_4a_proper_placebo.csv`, column `p_holm`). **Every one
  of the 8 survivors is on the `add_back` treatment** — the over-inclusive one that
  biases low bands upward, so those are the least trustworthy of the three. The
  earlier statement that the **> 150** band "is significant in both areas with the
  same sign" is **corrected to NOT ROBUST after adjustment**: on `raw` its Holm p is
  **0.332** (DE) and **1.000** (50Hertz); on `exclude`, 1.000 in both. The
  pre-registered contrast is unadjusted by design, being a single pre-specified test,
  and returns p = 0.2560 (DE) and p = 0.6048 (50Hertz) — the NO verdict stands and is
  not marginal.

  **(4) Wording.** The agreement between this project's DE onshore > 5 placebo
  (−0.35%) and Hirth's (−0.37%) is **consistent**, not a validation of either; see
  `docs/09_m2_preregistration.md` Amendment 1. And **TenneT is not significant in the
  kill test** — it is now stated wherever area results are listed, here and in
  `docs/08`.

**Positioning against Hirth (2026).** Hirth faces the same identification problem and
resolves it by not resolving it, in his own words (arXiv 2609.10053, p. 18): *"Because
curtailment is not observed cohort by cohort, one common response function is fitted
across the classes."* That is precisely the gap this project targets: M2's hierarchical
reservation-depth structure estimates a response **per cohort** from the exposure the
EEG rules imply, where Hirth fits one pooled curve. The limitation is his stated
choice, not an oversight, and the contribution here is to test whether the cohort
structure is recoverable at all — which `docs/09` section 4.4 shows is identified in
only 18 of 33 months.

### Methodology note — retransformation bias, and what it did and did not cause

Recorded 1 November 2026 after a stage-A design error, because the mistake is a
standard one and the correction is not quite the textbook one.

**The bias is real.** Fitting `log Y = x'b + e` by OLS and reporting `exp(x'b)`
estimates the conditional **geometric mean**, not the arithmetic mean. For a
right-skewed quantity the geometric mean is lower, so the naive retransformation is
biased low. Duan's (1983) smearing factor — `mean(exp(e_i))` over the training
residuals — is the non-parametric correction. Verified here on a log-normal with a
known mean: at σ = 0.8 the naive estimator is low by a factor of about 1.38, and
smearing recovers the truth to within 2% (`tests/test_m2.py`).

**But it was not the cause of the failure, and correcting it made things worse.** A
stage-A model `Â = F · exp(ĝ(calendar))` fitted this way scored **worse than the raw
day-ahead forecast** (MAE 1,367.6 against 1,358.3 MW on cell `r10_g0.0_step_s42`), and
applying smearing moved it further away, to 1,390.7. The reason is the loss function:
`exp(OLS on logs)` estimates the conditional **median**, and the **median minimises
MAE** for a skewed quantity, while the mean does not. Smearing corrects towards the
mean and therefore away from the MAE optimum. The real cause of the failure was much
plainer — a calendar-only multiplicative model carries little signal, and honest
cross-fitting exposes that, so the fitted factor added more variance than it removed.

**Three practical rules follow, and they are now in the code.**

1. Apply smearing only when the target is a **mean**. Under MAE, the unsmeared
   median-like predictor is the better estimator, not the worse one.
2. Do **not** apply it to a multiplicative head trained in levels. The
   `F · exp(g(x))` heads in `src/censoring/model.py` and `src/censoring/baselines.py`
   are fitted by pinball loss on observed G in levels, so `exp` is a link function the
   optimiser already accounts for; smearing them would **introduce** the bias it is
   meant to remove.
3. Always test a latent model against the trivial baseline it is supposed to improve
   on. `assert_stage_a_beats_forecast()` now raises per cell if stage A's held-out MAE
   exceeds the raw forecast's. That single assertion would have caught this on the
   first run instead of two amendments later.

### Pre-registered interpretation note — the uncensored offset, 1 November 2026

**Recorded before any T-B or T-D result exists.** Nothing here changes a criterion,
and it is placed in this file rather than in `docs/09` so the freeze on that document
holds.

#### The decomposition, verified numerically

Write `A_hat/A = (1 + b)(1 + ε)` with `E[ε] = 0`. Then `b = mean(A_hat/A) − 1`,
`σ = sd(A_hat/A)/(1 + b)`, and a second-order expansion of
`E[A/A_hat] = E[1/((1+b)(1+ε))] ≈ (1 + σ²)/(1 + b)` gives

    mean(1 − G/A_hat)  ≈  b − σ²      ( = −(σ² − b) )

the **level bias minus the Jensen term**. Measured over 9 cells, 3 rates × 3 seeds at
γ = 0, on uncensored quarter-hours where `G = A` exactly
(`results/20_stage_a_diagnostics.csv`):

| term | mean | range |
|---|---|---|
| `b` — level bias, **correctable by recalibration** | **+0.01069** | [0.00893, 0.01355] |
| `σ` — relative-error spread | **0.16118** | [0.15607, 0.16724] |
| `σ²` — Jensen term, **NOT correctable by recalibration** | **+0.02599** | [0.02436, 0.02797] |
| predicted offset `b − σ²` | −0.01530 | [−0.01678, −0.01354] |
| **measured offset** | **−0.01194** | [−0.01379, −0.00938] |
| \|predicted − measured\| | 0.00336 | [0.00259, 0.00429] |

**Both parts confirmed; the accounting is approximate, not exact.** `b = +1.07%` and
`σ = 16.1%` (so `σ² = +2.60%`). The second-order expansion **over-predicts the offset
by 0.34 pp, about 28% of the measured value**, because σ = 16% is not small enough for
the third-order term to vanish and the relative-error distribution is skewed. The
mechanism is established; the decomposition should be quoted as an explanation, not as
an exact budget.

**A consequence worth stating in advance: recalibrating the level would make the
offset WORSE.** Removing `b` leaves `−σ²`, roughly **−2.6 pp** against the −1.19 pp
measured now — the level bias is currently *cancelling* part of the Jensen term. So a
naive "fix the bias" recalibration would roughly double the offset, not remove it.

#### Three predictions, stated before the results

**(i) T-D(i)'s placebo may FAIL structurally, not because stage A is wrong.** The
placebo is `|mean(1 − G/A_hat)| < 1 pp` on held-out price > 5 €/MWh quarter-hours —
exactly the quantity above, which measures **1.194 pp** in E1. **The criterion is NOT
changed.** If it fails, this note is the explanation, and the failure is a property of
a ratio with a noisy denominator rather than evidence that stage A is mis-specified.

**(ii) The offset grows as σ², so T2 will carry a larger one.** T2 has no D-1 weather
vintage (`docs/08` §9.2), and weather correlates 0.915 with true A in E1, so σ for
T2's stage A must be larger and the offset grows with its square. **σ for T2's stage A
is to be quantified when that stage A exists**, and the offset re-derived from it
rather than carried over from E1.

**(iii) Residual-based ĉ inherits this; M2's structural ĉ does not.** Any
`ĉ = 1 − G/A_hat` carries the offset directly, and Hirth's `max(0, A_hat − G)` carries
it *and* clips at zero, which rectifies the negative part rather than cancelling it.
M2's structural `ĉ = Σ w·s·r` is built from exposure and a response on the simplex and
has no such term. **T-A already reports both forms, so the gap between them is the
quantitative test of this prediction** and is to be reported beside this note.

#### T-B sensitivity arm — reported, decides nothing

Every method is refitted on `y` and on `y − offset_hat`, where `offset_hat` is
`mean(1 − G/A_hat)` measured on **that cell's uncensored quarter-hours only** — so it
uses no censored information and cannot leak the answer. Same cells, same seeds.
**Report whether the T-B verdict differs between the two.** It decides nothing; the
pre-registered T-B verdict stands on the unadjusted `y`.

**Rationale.** A negative offset interacts **asymmetrically** with the two sides of
the comparison. M2's `p_k` lies on the simplex, so its response cannot go negative and
a negative offset in `y` must be absorbed as a smaller fitted response or pushed into
the never-respond atom; B3's binned mean is unconstrained and can simply return a
negative bin. At a 10% censoring rate the offset is **20.0% of mean `c_true`** (0.0598),
10.0% at 20% and 5.0% at 40%, so the asymmetry bites hardest exactly where T-B is
hardest and where the data-efficiency claim is being tested.

### T-B note, 1 November 2026 — recorded before PASS 1 landed

Not an amendment and not a criterion change. `docs/09` stays frozen.

#### Limitation at n = 20: both methods sit on their regularisation ceiling

Measured on cell `r10/γ0/step/seed45` before any verdict existed:

| n_event_days | stage-r observations | M2 λ chosen | B3-CV bins chosen |
|---|---|---|---|
| 50 | 681 | 0.316 | 4 |
| **20** | **304** | **100.0 — top of a 14-value grid** | **4 — bottom of {4,8,16,32,64}** |

At n = 20 M2's λ is at the **most-regularised end of its grid** and B3-CV's bin count
is at **its most-smoothed end**. The pressure is symmetric, so neither method is
favoured — but the n = 20 secondary is comparing two methods **at their grid limits
rather than at preferred settings**, and a result there is a statement about the
grids as much as about the methods.

**Neither grid is widened.** Doing so after seeing which boundary was hit is exactly
the move pre-registration exists to prevent. Instead the **chosen λ and the chosen bin
count are recorded per cell** (`chosen_lambda`, `chosen_bins`, `at_grid_boundary` in
`results/21_tb_*.csv`), so a reader can see every cell where a boundary bound.

Note also that M2 carries **654 free parameters against 304 observations at n = 20** —
more parameters than data points. That it is estimable at all is the simplex
constraint plus λ, which is the next point.

#### Prediction, stated before the result

At λ = 100 the pooling penalty dominates the fit and every block is pulled onto the
common `p_bar`, so **M2 at n = 20 is effectively a single fleet response** rather than
a hierarchy. Two consequences follow, recorded now so they cannot be claimed
afterwards:

1. The component attribution should show **pooling carrying almost all of the gain**
   at n = 20.
2. **M2-noPool should do badly there** — λ = 0 leaves 654 free parameters on ~304
   observations with nothing but the simplex to restrain them.

**If M2-noPool instead does WELL at n = 20, the λ cross-validation is not behaving as
intended, and the result must be investigated before it is believed.** That is a
falsifiable prediction about the machinery, not about the verdict.

#### The parameter counts are not commensurable across families — permanent caveat

To be attached wherever those counts are reported. M2's parameters lie on simplexes,
one per block, so each block spends a fixed mass rather than ranging freely and the
effective dimension is far below the nominal count. B6's figure is
trees × max-leaves, an upper bound that boosting's shrinkage does not reach. A bin
count is a third kind of quantity again. **The honest use is the order of magnitude
against the stage-r observation count, never a like-for-like ratio between methods.**

#### Scheduling correction, 1 November 2026 — the sensitivity arm must run at n = 50

The T-B sensitivity arm (`y` against `y − offset_hat`) was scheduled with PASS 2, at
n ∈ {20, 100, all}. **As scheduled it could not answer the question it was given.**
The arm is required to report "whether the T-B **verdict** differs", and the verdict
is defined at **n = 50** — a level PASS 2 does not run. An arm at 20, 100 and all
would report differences in metrics at levels where no verdict exists.

**It therefore runs as its own n = 50 pass, after PASS 1**, and the two verdicts are
compared directly. It is **not** folded into PASS 1: that would double the inner λ
cross-validation, which is the dominant cost, and push the run past the alternative
it was chosen to beat. Reported, **gates nothing**, written to its own CSV.

Order from here: PASS 1 → sensitivity arm at n = 50 → PASS 2 → T-A → T-D → verdict.

### T-B note, 2 November 2026 — the sensitivity arm was specified but not implemented

Not an amendment and not a criterion change. `docs/09` stays frozen.

The scheduling correction of 1 November 2026 placed the sensitivity arm after PASS 1
and before PASS 2. On 2 November, with PASS 1 at 60 of 135 cells, the arm was found to
have **no implementation**: `run_tb.py --pass` offers only `primary` and `secondary`,
and neither carries the `y − offset_hat` refit. The arm's own docstring line
("`--pass secondary`   n in {20, 100, all} + arms") promised arms that did not exist.
Had PASS 1 been left to finish unattended, the next registered step would have had no
runner.

It is now implemented as `src/censoring/run_tb_sensitivity.py`, a **separate module**.
`run_tb.py` was executing PASS 1 at the time and is the pre-registered runner; editing
it mid-run would have risked the registered artefact for no gain. Every criterion,
threshold and subsampling primitive is imported from it unchanged.

#### The shift is applied to the observed output, not to one regression target

The specification says "every method is refitted on `y` and on `y − offset_hat`" and
does not say how. Each method builds `y = 1 − G/A_hat` for itself, inside itself, so
there are two readings and they measure different things.

**Chosen:** shift `G` by `offset·A_hat` once per cell. Then
`1 − (G + offset·A_hat)/A_hat = y − offset` exactly, for every method, and each method
derives everything else from the corrected output — including B3's
`residual = max(0, A_hat − G)`, which is where B3's response actually comes from.

**Rejected:** shift only the regression target and leave B3's residual on the
unadjusted `G`. The arm's stated rationale is the **asymmetry** between a response
confined to the simplex and a binned mean free to return a negative bin. Exempting
B3's residual from the adjustment would exempt B3 from precisely the asymmetry being
tested. The rejected reading measures something; it does not measure that.

`A_hat` is fitted on the original `G` and reused unchanged — the offset is measured
*from* `A_hat`, so refitting on the corrected output would be circular. The censored
mask is `c_true > 0`, which no change to `G` can touch, so cells, event-days,
subsample and fit mask are bit-identical to PASS 1.

#### Only the adjusted arm is computed

The unadjusted arm is already in `results/21_tb_primary.csv`. Recomputing it would
spend a further ~5 hours reproducing numbers that are deterministic given the seeds.
The arm therefore computes the adjusted side only and compares its verdict against
PASS 1's. `--verify-cells N` recomputes the unadjusted arm on the first N cells and
reports any disagreement, which is the cheap form of that assumption's test.

#### Disclosure — an interim partial verdict was computed, and is not interpretable

While verifying that the arm's reporting path could read PASS 1's CSV at all, the
verdict function was run against the **partial** `21_tb_primary.csv` (406 rows, 58 of
135 cells) and printed an interim verdict. This is recorded because a pre-registered
programme must be able to answer truthfully whether interim results were seen.

It carries no weight, and nothing was or may be changed in response to it:

- The cells are generated in a fixed order with the censoring rate as the outer loop,
  so at 43% the subset contains rates 0.10 and 0.20 and **none of rate 0.40**. It is a
  systematically incomplete stratum, not a random subsample, and a sign test over it
  estimates nothing the full grid will report.
- Hard rule 20 forbids claims from provisional subsets. The interim figure is not
  quoted here, is not a finding, and does not appear in any result table.
- `docs/09` is frozen. No criterion, threshold, grid or method may move in response to
  a partial read, and none did.

The binding T-B verdict is the one `overall()` returns on the complete 945-row
`results/21_tb_primary.csv`, under Amendment 3 section 0.3.

#### The arm and PASS 2 must run on the same machine as PASS 1

Offloading either to another machine was considered and rejected. `N_SECONDARY` is
`(20, 100, None)`; n = 50 exists only in PASS 1, so every cross-level and cross-arm
comparison is against a PASS 1 number. The nested design's claim is that a difference
between levels "is attributable to the response estimation and nothing else" — a claim
that fails the moment the levels are computed on different Python, torch and BLAS
builds, because any difference then admits a platform explanation. Measured cost of
the alternative, on a one-cell probe: the cloud VM available to this session ran
roughly **four times slower** than the laptop, so the offload would have been slower
as well as confounded.
