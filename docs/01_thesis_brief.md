# MSc Thesis Brief — Mechanism-Aware Learning under Signal-Driven Censoring

Student: Gagan Ganesh — MSc AI/ML (Big Data), SRH Hochschule Berlin, final semester
Window: Nov 2026 – Apr 2027
Version 2, 30 Oct 2026. **v1 is archived unchanged at `01_thesis_brief_v1_forecast-correction.md`.**
Last updated: 30 Oct 2026

> **Working document, not proposal text.** This is a structured brief for planning and for
> Claude Code. Proposal and thesis prose must be written by the student (SRH AI-use rubric).
> The authoritative specification is `06_pivot_mechanism_aware_censoring.md` (spec v1.6).
> Where this brief and the spec disagree, **the spec wins**.

Status (30 Oct 2026): **RQ1 kill test reproduced in full — GO.** All four checks pass,
including the redispatch control (Check 2), which confirms that grid redispatch does not
explain the negative-price over-forecast. See `04_rq1_killtest_note_v3.md`. §51 EEG rule
table built: `05_eeg_rule_table.md` and `data/reference/eeg_negative_price_rules.csv`.
Topic pivoted 29–30 Oct 2026 from forecast correction to a censored-learning method.

---

## 1. Working title (v2)

**Mechanism-Aware Learning under Signal-Driven Censoring: Jointly Recovering Latent Wind
Power and Fleet Switch-Off Response from Price-Curtailed Data**

Alternative: *Learning from Price-Censored Generation Data: A Structured Model of Partial
Fleet Curtailment in Germany's 15-Minute Day-Ahead Market*

## 2. The gap in one paragraph (v2 — method framing)

Models for renewable generation are trained on recorded output. When German day-ahead
prices turn negative, part of the wind fleet switches off for commercial reasons, so the
record stops showing what the wind could have produced: **the label is censored**. The
evidence base behind this is unchanged from v1 and is kept here. Hirth (arXiv 2609.10053,
Sep 2026) estimates 2.11 TWh of wind curtailment in 2025 and finds that below −50 €/MWh
almost all wind had an incentive to stop while only about half did; market-based
curtailment rose ~20% in H1 2026 even as negative hours fell (Montel via pv magazine);
since 1 Oct 2025 SDAC clears in 15-minute steps, so the decision is per quarter-hour. What
changed in v2 is where the contribution sits. Existing practice **deletes** these periods
(Jørgensen et al. 2025), **calibrates on safe periods and treats the residual as
curtailment** (Hirth 2026), or ignores the problem; classical censored regression (Tobit,
censored quantile regression) and the closest prior learning method (Wang & Wang 2026,
censored SCADA under *known* grid commands) all assume the censoring indicator and the
bound are **observed**, with a fixed threshold. Here neither holds: an observed external
signal (price) triggers a **partial, heterogeneous** switch-off, the censored fraction is
latent, and the EEG negative-price rules only *partly* specify which plant groups are
exposed. That structure — known exposure, unknown response — is the method gap.

## 3. Research questions (v2)

- **RQ1 (done):** Does price-driven censoring measurably bias the labels used for wind
  forecasting? → kill test v3, **yes**.
- **RQ2:** Can the mechanism-aware model jointly recover latent available power A and the
  fleet response r_k, and under which conditions (I1–I4)?
- **RQ3:** How do deletion, safe-period calibration and fixed-indicator censoring degrade
  as the censoring rate and the weather–price confounding grow, compared with the proposed
  model?
- **RQ4:** On real German data, does the structured model beat black-box price-aware
  learning (B5) in negative quarter-hours, and does it transfer better across a rule change?

## 4. Hypotheses (v2 — H1 retired, H2–H4 replace it)

H1 of v1 is **answered**, not hypothesised: the kill test measured the bias
(−9.1% [−13.2, −4.8] relative in DE negative QHs, surviving the redispatch control).

- **H2:** On the semi-synthetic benchmark, the proposed model's error on A in censored QHs
  is significantly lower than B1–B4 at censoring rates ≥ 10%, and its r̂ curve error is
  lower than B3's implied response. **B4 prediction:** because B4 treats
  exposed-but-uncurtailed QHs as mere lower bounds and its survival term only pushes
  upward, B4 should *overestimate* A when compliance is low or partial; the gap should be
  largest under the 50%-compliance r*.
- **H3:** On real data, the proposed model is at least as accurate as B5 in negative QHs
  (Diebold-Mariano, event-day block bootstrap) and better calibrated (interval coverage).
- **H4:** Trained before a rule change and tested after, the proposed model degrades less
  than B5, because the rule change enters through s_k,t rather than having to be relearned.
- **Falsification:** the H2/H3 tests are not significant, or the I1 placebo fails.

## 5. Key design decisions

### 5.1 Carried forward from v1 — still valid

1. **The published day-ahead forecasts are price-blind by construction.** 18:00 D−1 is the
   *publication* deadline for ENTSO-E 14.1.D, not the forecast time. TenneT freezes its
   day-ahead wind forecast at about **08:00 D−1** and 50Hertz at about **09:00 D−1**, both
   well before the SDAC day-ahead results at **12:57 CET**. The measured bias therefore
   cannot be explained away as TSOs already correcting for curtailment. (Amprion publishes
   no freeze time — open item.)
2. **Two price clocks run at once** (§100(45) EEG 2023). Post-25 Feb 2025 cohorts are judged
   on the **quarter-hour** price; all earlier, hour-based cohorts on the **arithmetic mean
   of the four quarter-hour prices** of the calendar hour, then on a run of consecutive such
   hours (6 h, 4 h, or the 2023–2025 staircase, which tightened from 3 h to **2 h on
   1 Jan 2026 — inside the sample**). Full mapping: `05_eeg_rule_table.md`.
3. **Effective sample size is small.** Negative-price quarter-hours cluster into a few dozen
   episodes. Event-day blocks for CV and bootstrap; 5 of 99 days carry 45–60% of the error.
4. **Target noise.** TSO "actual generation" for wind is partly an extrapolation
   (Hochrechnung), not fully metered. A limitation, not a fixable defect.
5. **Novelty not fully closed.** Semantic Scholar / OpenAlex and a broad web sweep are done;
   **Google Scholar and IEEE Xplore remain to do** (`02_evidence_base.md` search caveat).

### 5.2 New in v2 — the pivot decisions

6. **Rules enter as model structure, not as features.** Feeding the rule step-functions to a
   black box is baseline B5. The claim is that putting them into the observation model as
   *known exposure* is what identifies the response and transfers across rule changes.
7. **The latent-head covariate set is closed** (spec §4): the TSO day-ahead forecast plus the
   task-allowed weather proxy only. **No calendar, no solar, no price, no θ, no s.**
   Temperature and pressure enter only as air density inside the power-curve transform.
8. **Two tasks with separate allow-lists** (spec §3a): T1 ex-post recovery (ERA5 allowed),
   T2 day-ahead forecast (true D−1 vintages only).
9. **Never a model input:** the intraday forecast (no published vintage), redispatch (ex
   post; an evaluation stratifier only), same-QH actuals, ERA5 and the stitched Historical
   Forecast archive in T2, and the **published monthly Netztransparenz market value** — the
   last of these reaches the model through θ, not through a feature column, so the test must
   assert θ's provenance per task as well.
10. **Cohort collapse is pre-registered** at fewer than 10 event-days of differing exposure,
    and pools the response r, not the exposure s (spec §3 I4).

## 6. Method summary (v2 — full detail in spec §4)

Observation model, per quarter-hour t and control area:

    G_t = A_t · (1 − c_t) + ε_t,      c_t = Σ_k w_k,t · s_k,t · r_k(z_t)

- **A_t** — latent available power. Multiplicative head A_t = F_t · exp(g(x^A_t)), motivated
  by the kill-test finding that the bias is a roughly constant ~9% proportional haircut
  (−9.1% overall vs −9.3% in windy QHs), not a fixed MW offset. g never sees price.
- **θ_k,t** — switch-off threshold per cohort: 0 when the §51 trigger is active or support
  has ended, otherwise −max(0, AW_k − MV_m). Deterministic; nothing about it is learned.
- **s_k,t = 1[p_t < θ_k,t]** — exposure, from the rule table.
- **r_k(z_t)** — the learned, monotone fleet response on depth below θ and run length.
- **M1:** non-crossing quantiles, pinball loss on G. **M2:** explicit density fitted by EM.

## 7. Data pipeline

Unchanged from v1 in its conventions; sources extended for the pivot.

- Sources: SMARD (15-min forecasts, actuals, prices — primary), ENTSO-E (cross-check), MaStR
  (plant register, dated snapshot → cohort shares w_k), Netztransparenz (redispatch for
  stratification; market values for T1 and for validating the T2 recomputation), ERA5 and
  Open-Meteo ICON (weather proxy, task-dependent). See `03_data_sources.md`.
- Storage: Parquet, UTC timestamps, explicit DST checks, raw/processed layers. `data/raw` is
  append-only.
- Splits: rolling origin by month, 7-day embargo, no shuffling; CV folds and bootstrap
  blocked by Berlin-local event-day. Seed 42.
- **SMARD unit convention:** quarter-hour values are MWh per quarter-hour; MW = value × 4.
- Confounder control: redispatch stratification using the method validated in
  `src/redispatch_control.py` (5 volume bins × forecast decile).

## 8. Baselines (v2)

| ID | Method | What it represents |
|---|---|---|
| B0 | TSO day-ahead forecast as-is | status quo |
| B1 | Model trained on observed G, all QHs, no price features | naive: learns curtailment as noise |
| B2 | Same, negative-price QHs deleted from training | Jørgensen et al. deletion |
| B3 | Hirth's pipeline: A fitted on QHs > 5 €/MWh; curtailment = residual; implied response = binned residual share by profit margin | two-stage safe-period calibration |
| B4 | Wang & Wang's objective: pinball on non-exposed QHs + survival loss −log(1 − F̂(G)) treating G as a lower bound in every exposed QH | closest prior method: fixed, assumed censoring indicator |
| B5 | Quantile LightGBM on G with price and cohort-exposure features | strong black-box price-aware model |
| Proxy | Solar day-ahead forecast + day type, no price, no MaStR | the practitioner bar (`02_evidence_base.md` §B3: 11% cut with these alone) |
| Oracle | Trained on true A | synthetic benchmark only |

B5 keeps the comparison honest: same information, no structure.

## 9. Experiments (v2)

- **E1 — semi-synthetic benchmark** (do first; needs no MaStR, no ERA5). Inject censoring
  into clean QHs with price > 5 €/MWh; grid of censoring rate {5,10,20,30,40}% ×
  confounding γ {0,0.5,1} × r* shape {step, logistic, half} × 5 seeds.
- **Week-6 checkpoint — go/no-go on E1, due 31 Dec 2026.** Criterion in spec §7.
- **E2 — real data** (T2 unless stated). 15-min panel Oct 2025 – Oct 2026, four control
  areas plus DE. 50Hertz and Amprion primary (cleanest signal in v3).
- **E3 — regulatory transfer.** Only 199 negative QHs on 7 event-days fall before
  1 Jan 2026, so "train 2025, test 2026" needs the hourly 2023 – Sep 2025 set, or
  leave-one-cohort-out within 2026. Decide in month 2.
- **E4 — plausibility** (T1, ERA5 allowed). r̂ vs the statutory curve and vs Hirth's Fig. 12.
- **E5 — stretch.** Solar curtailment, or the pre-auction price-forecast variant from v1.

## 10. Timeline (v2)

Registered window: **16 or 26 weeks — [VERIFY] with the examination office.** The
registration form (Apr 2026) lists 26 weeks for full-time 4-semester study, 18 for MIBE and
39 part-time; registration follows proposal approval. The plan below is the working
calendar, not the registered one.

| When | Work | Deliverable |
|---|---|---|
| Nov wk 1–2 | Proposal (≥15 pages, own writing, incl. "Intended Contribution to Science"); literature table; 30-min topic defence | approved proposal, registration |
| Nov wk 3–4 | E1 generator, proposed model v0, baselines B0–B4 | first synthetic results |
| Dec | E1 full grid; MaStR ingest and cohort shares; B5 | RQ2/RQ3 results; **week-6 checkpoint (31 Dec)** |
| Jan | E2 real data; hourly 2023 – Sep 2025 ingest; E3 design decision | RQ4 results |
| Feb | E3, E4, ablations; paper draft (8–12 pages) | paper draft |
| Mar | Thesis writing (≥20,000 words) | full draft |
| Apr | Buffer, code release, defence slides (numbered n/N) | submission |

## 11. Minimum vs stretch (v2)

- **Minimum passable:** the method, stated identification conditions, and E1 on the
  semi-synthetic benchmark with known truth — even if the real-data gain over B5 is small.
  The contribution rests on E1 plus identification, not on beating a black box by a margin.
- **Stretch / paper:** significant gain on real data (H3), demonstrated transfer across the
  1 Jan 2026 staircase step (H4), and a credible compliance-gap result against Hirth (E4).

## 12. Backup topic

Unchanged from v1: probabilistic day-ahead forecast of grid-driven onshore wind curtailment
(redispatch) at hourly resolution in the 50Hertz area, focused on extreme events. Nearest
work: Shamim et al., arXiv 2610.08337. Novelty margin is thinner. **Note (v2):** the old
"pivot rule at week 6" is superseded by the E1 checkpoint in spec §7 — the kill test has
already passed, so the trigger is now failure of E1, not failure of RQ1.

## 13. People to contact

1. **Lion Hirth** (Hertie School / Neon, Berlin) — author of arXiv 2609.10053. Ask: how the
   cohort-by-hour threshold table was built; whether it can be shared and cited; whether he
   is already working on forecasting (scoop risk).
2. **50Hertz (Berlin)** — forecasting / system operations / EEG marketing. Ask: do they see
   over-forecasting at negative prices; do they already correct for it; Werkstudent or
   thesis cooperation?
3. **A direct marketer** (e.g. Next Kraftwerke) or a forecaster (e.g. Dexter Energy, energy
   & meteo, enercast) — how curtailment bids are set per plant type; whether anonymised
   curtailment flags exist for validation.

**TSO e-mail questions:** Amprion freeze time; which intraday vintage is archived; whether
the day-ahead wind series is ever revised after 18:00 D−1.

## 14. Target venues (dates to verify)

- ACM e-Energy 2027 — winter deadline ~mid-Jan 2027 (too early for full results)
- IEEE ISGT Europe 2027 — deadline likely ~April 2027 (unverified)
- Climate Change AI workshop at ICLR 2027 — deadline ~early Feb 2027 (unverified)
- Journals: Energy Informatics, Applied Energy, Energy Economics (rolling)

## 15. Open questions / to-verify list

Resolved in v1 and carried forward (do not re-open):

- [x] **ENTSO-E 14.1.D publication time** — 18:00 D−1 is the publication deadline, not the
  forecast time; TenneT ~08:00 D−1, 50Hertz ~09:00 D−1. Still open for **Amprion**.
- [x] **§51 / §51a trigger granularity** — quarter-hour from 25 Feb 2025; hourly mean of the
  four QH prices for all earlier versions (§100(45) EEG 2023). `05_eeg_rule_table.md`.
- [x] **Negative-price hour counts** — the "573 vs 539" pair conflated counting rules and is
  withdrawn. Netztransparenz §51a(3): 2025 = 557 h, 518 h, 199 QHs by rule version.
- [x] **Windy negative quarter-hours since 1 Oct 2025** — 2,059 negative QHs on 99
  event-days; 1,347 QHs on 65 days with DE day-ahead wind forecast ≥ 10 GW.

Still open:

- [ ] **16 vs 26 weeks registered processing time** — [VERIFY] with the examination office.
- [ ] Which intraday forecast vintage SMARD archives — UNRESOLVED; TSO e-mail question 4.
- [ ] Netztransparenz licence / terms of use — UNRESOLVED, must be settled before use.
- [ ] Whether DSO-initiated Redispatch 2.0 measures are in the Netztransparenz export.
- [ ] Whether the day-ahead wind series is ever revised after 18:00 D−1.
- [ ] MaStR fields for support status / auction award (Zuschlagsnummer) / direct marketing.
- [ ] Open-Meteo *Previous Runs* start date for the DWD models; Open-Meteo licence.
- [ ] Google Scholar and IEEE Xplore novelty sweep.
- [ ] EEG Anlage 1 reference period (monthly vs annual market value) for post-2023 cohorts
  — [VERIFY], spec §3.
- [ ] §51a(1) wording: does the support-period extension depend on the plant's own output?
  — [VERIFY], spec §3; decides whether a §51a sensitivity arm is needed.
- [ ] Netzpaket "Redispatch-Vorbehalt" status (draft, not law as of 7 Oct 2026).
- [ ] BMWE EEG Referentenentwurf of 17 Jul 2026 (§10b(7), §51 changes) — watch item,
  re-check monthly. Do not cite "EEG 2027" until a law text exists.
- [ ] SRH thesis regulations: supervisor confirmation, registration deadline.
