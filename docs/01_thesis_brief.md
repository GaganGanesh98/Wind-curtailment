# MSc Thesis Brief — Price-Driven Wind Curtailment Forecasting (Germany)

Student: Gagan Ganesh — MSc AI/ML (Big Data), SRH Hochschule Berlin, final semester
Window: ~6 months, starting Nov 2026
Status (29 Oct 2026): topic chosen in principle; **RQ1 kill test reproduced — provisional GO,
pending the redispatch control (Check 2), which is blocked on Netztransparenz data access.**
See `04_rq1_killtest_note_v3.md`. §51 EEG rule table built: `05_eeg_rule_table.md` and
`data/reference/eeg_negative_price_rules.csv`.
Last updated: 29 Oct 2026

---

## 1. Working title

**Who switches off? Forecasting price-driven wind curtailment in Germany's 15-minute day-ahead market**

Alternative: *Post-auction correction of German wind feed-in forecasts in negative-price quarter-hours using plant-level switch-off price curves*

## 2. The gap in one paragraph

Since 1 Oct 2025 the European day-ahead market (SDAC) clears in 15-minute steps. When prices go negative, many German wind plants have a financial reason to stop producing: plants out of EEG support (older than 20 years), plants whose market premium is smaller than the negative price, and plants commissioned from 25 Feb 2025 that lose support in every negative-price period (§51 EEG, Solarspitzengesetz). Hirth (arXiv 2609.10053, Sep 2026) found that in 2025, at prices below −50 €/MWh, almost all wind had an incentive to stop, but only about half did. So switch-off behaviour is real, growing (Montel: market-based curtailment +20% in H1 2026 despite fewer negative hours) and uncertain. Existing work either estimates it after the fact (Hirth) or filters it out as noise (arXiv 2501.14805). No paper found so far forecasts it ahead of delivery.

## 3. Research questions

- **Main RQ:** Can a price- and plant-incentive-aware model significantly reduce the error of the published TSO day-ahead wind forecast in negative-price quarter-hours?
- **RQ1 (bias):** How large and systematic is the TSO day-ahead wind forecast error in negative-price quarter-hours, by price depth and control area? *This is the kill test.*
- **RQ2 (attribution):** How much of any improvement comes from plant-incentive features (switch-off price curve from MaStR) versus price features alone?
- **RQ3 (pre-auction):** How much of the gain survives if realised prices are replaced by a price forecast? (Makes it useful before the auction, not only after.)

## 4. Hypotheses (falsifiable)

- H1: In negative-price quarter-hours, TSO day-ahead forecasts over-forecast wind feed-in, and the bias grows with price depth and with the share of capacity whose break-even price is above the clearing price.
- H2: A model using price + switch-off price curve reduces MAE on the negative-price subset by ≥15% vs (a) the raw TSO forecast and (b) a weather/forecast-only correction model, with no significant loss elsewhere.
- Rejected if: the bias's 95% bootstrap CI includes zero, or the improvement is not significant under a Diebold-Mariano test with event-block bootstrap.

## 5. Key design decisions (from the 28 Oct critique — these override the original research report)

1. **Core assumption checked — and the original reasoning was wrong.** 18:00 D-1 is the *publication* deadline for ENTSO-E 14.1.D, not the forecast time. TenneT freezes its day-ahead wind forecast at about **08:00 D-1** and 50Hertz at about **09:00 D-1**, both well **before** the SDAC day-ahead results at **12:57 CET**. The published day-ahead forecasts are therefore **price-blind by construction**, not price-aware, so the measured bias cannot be explained away as TSOs already correcting for curtailment. (Amprion publishes no freeze time — open item.) RQ1 was run in week 1 and passed.
2. **Replace the crude commissioning-date cohort index with a switch-off price curve.** For each plant, estimate the price below which it loses money by producing:
   - post-EEG plants (>20 years, no support): ~0 €/MWh
   - market-premium plants: ≈ −(market premium) — depends on award value (anzulegender Wert) and monthly market value
   - plants from 25 Feb 2025 under new §51: lose support in every negative-price period → ~0 €/MWh
   - older plants under 3/4/6-hour §51 rules: depends on run length of negative prices
   Aggregate to MW-that-should-switch-off as a function of price, per control area. Comparing this "should" curve with observed behaviour is the core contribution, and speaks directly to Hirth's "only half switch off" puzzle.
   **Price clock, settled 29 Oct 2026 (§100(45) EEG 2023):** the curve must use **two different price series at once**. For plants under the rule in force from 25 Feb 2025 the trigger is the **quarter-hour** price. For plants under any earlier, hour-based version the trigger is the **arithmetic mean of the four quarter-hour prices** of the calendar hour, and then a run of consecutive such hours (6 h, 4 h, or the 2023–2025 staircase, which tightened from 3 h to **2 h on 1 Jan 2026 — inside the sample**). A quarter-hour can therefore be a switch-off signal for one cohort and no signal at all for another. Full mapping: `05_eeg_rule_table.md` and `data/reference/eeg_negative_price_rules.csv`.
   Open question: does MaStR link units to auction awards (Zuschlagsnummer) or support status? If not, estimate break-even prices by commissioning-year cohort and the statutory tariff tables.
3. **Effective sample size is small.** Negative-price quarter-hours cluster into a few dozen events. Use event-day blocks for CV and bootstrap. Add 2023 – Sep 2025 hourly data as a second, larger dataset; Oct 2025 onwards (15-min) is the primary dataset.
4. **Target noise.** TSO "actual generation" for wind is partly an extrapolation (Hochrechnung), not fully metered. Treat as a limitation; check robustness against SMARD vs ENTSO-E series.
5. **Novelty not yet fully verified.** The research covered arXiv + web only. Redo searches on Google Scholar, Semantic Scholar, IEEE Xplore, ScienceDirect (Applied Energy, Energy Economics, Renewable Energy) in week 1. Commercial forecasters almost certainly do curtailment-aware forecasting; state this openly — the gap is academic and methodological, not "nobody has ever thought of it".

## 6. Method

- **Target:** e_t = actual wind generation − TSO day-ahead wind forecast, per control area (50Hertz, Amprion, TenneT DE, TransnetBW) and DE-LU total, at 15-min resolution (hourly for the pre-Oct-2025 set). Onshore and offshore separately where the data allows.
- **Features:** realised day-ahead price; price-depth bands; consecutive negative-period count (for 3/4/6-h rules); forecast level and ramp; hour/season; switch-off price curve evaluated at the clearing price (MW expected to switch off); solar forecast (shared negative-price driver).
- **Models:**
  - Rule-based: predicted switch-off = MW with break-even price above clearing price × compliance factor (fitted)
  - Quantile LightGBM on e_t
  - Two-stage hurdle: P(curtailment event) × expected depth
  - Optional stretch: conformal calibration of intervals
- **Baselines:** (1) raw TSO forecast; (2) LightGBM correction without price/incentive features, at the *same* forecast time (the fair-comparison ablation); (3) rule-based model; (4) **proxy baseline, added 29 Oct 2026 — price + solar forecast + day type/holidays, no MaStR.** A public-data practitioner project reached an 11% cut in negative-hour onshore error with solar and day type alone (`02_evidence_base.md` §B3). RQ2 must beat this, not only the raw TSO forecast; otherwise the plant-incentive features have not earned their place.
- **Secondary benchmark, not a baseline:** the published **intraday** forecast. It is made no earlier than 08:00 on the delivery day and refreshed repeatedly after that, yet still leaves ~83% of the DE negative-QH bias (and makes Amprion's worse). It is a demanding reference point, but its vintage is unknown and possibly near-delivery, so it is **leakage** and must never be a model input. See `04_rq1_killtest_note_v3.md` §3.
- **Ablations:** no price; price only; incentive curve only; hourly vs 15-min; realised vs forecast price; per-TSO vs pooled; leave-one-control-area-out.
- **Metrics:** MAE/RMSE on negative-price subset and overall; bias by price band; pinball loss, interval coverage; imbalance-cost proxy (volume × imbalance price, reBAP).
- **Significance:** Diebold-Mariano tests; event-block bootstrap.

## 7. Data pipeline

- Sources: ENTSO-E Transparency (forecasts, actuals, prices), SMARD (cross-check), MaStR (plant registry, dated snapshot), ERA5 100 m wind (hindcast "potential" for analysis labels), Netztransparenz (redispatch to exclude grid-driven curtailment; reBAP imbalance prices). See `03_data_sources.md`.
- Storage: Parquet, UTC timestamps, explicit DST checks, raw/clean/features layers.
- Splits: rolling origin by month, 7-day embargo, no shuffling; CV folds and bootstrap blocked by event-day. Plant features use only plants commissioned before the test window.
- Confounder to control: grid-driven redispatch also lowers feed-in during windy periods. Flag/exclude periods with large wind redispatch in the same control area, or include redispatch volume as a feature.

## 8. Six-month plan

| Month | Work | Deliverable |
|---|---|---|
| 1 (Nov) | **Week 1 kill test (RQ1 quick version)**; full literature re-check; EEG §51 / market-premium rule table from primary legal text; data ingestion | Go/no-go note, data lake, rule table |
| 2 (Dec) | Full bias analysis (RQ1); baselines; switch-off price curve v1 from MaStR | **Week-6 checkpoint**; RQ1 chapter draft |
| 3 (Jan) | Models (rule, LightGBM, hurdle) | Model v1 + results |
| 4 (Feb) | Ablations (RQ2); price-forecast variant (RQ3) | Results tables |
| 5 (Mar) | Robustness, per-TSO transfer, cost proxy; paper draft | Workshop/paper draft |
| 6 (Apr) | Writing, code release, defence prep | Thesis, arXiv preprint, GitHub repo |

**Pivot rule (week 6 at the latest):** if the TSO forecast shows no significant positive bias in negative-price quarter-hours (bootstrap 95% CI includes zero), or fewer than ~150 usable windy negative quarter-hours / ~20 event-days exist, switch to the backup and reuse the pipeline.

## 9. Backup topic

Probabilistic day-ahead forecast of grid-driven onshore wind curtailment (redispatch) at hourly resolution in the 50Hertz area, focused on extreme events. Nearest work: Shamim et al., arXiv 2610.08337 (daily, all-TSO totals, intervals reach only 61.9% coverage in high-volume events). Novelty margin is thinner.

## 10. Minimum vs stretch

- **Minimum passable:** clean, reproducible measurement of the bias (RQ1) + switch-off price curve + baseline correction, even if the gain is modest.
- **Stretch / paper:** significant improvement, ablation showing the incentive curve matters, working pre-auction version, explanation of the compliance gap.

## 11. People to contact

1. **Lion Hirth** (Hertie School / Neon, Berlin; verify) — author of arXiv 2609.10053. Ask: how he built the incentive table; whether it can be shared/cited; whether he is already working on forecasting (scoop risk).
2. **50Hertz (Berlin)** — forecasting / system operations / EEG marketing. Ask: do they see over-forecasting at negative prices; do they already correct for it; Werkstudent or thesis cooperation?
3. **A direct marketer** (e.g. Next Kraftwerke) or a forecaster (e.g. Dexter Energy, energy & meteo, enercast) — ask how curtailment bids are set per plant type; whether anonymised curtailment flags exist for validation.

## 12. Target venues (dates to verify)

- ACM e-Energy 2027 — winter deadline ~mid-Jan 2027 (too early for full results; consider workshops/posters)
- IEEE ISGT Europe 2027 — deadline likely ~April 2027 (unverified)
- Climate Change AI workshop at ICLR 2027 — deadline ~early Feb 2027 (unverified)
- Journals: Energy Informatics, Applied Energy, Energy Economics (rolling)

## 13. Open questions / to-verify list

- [x] **Exact ENTSO-E 14.1.D publication time used by German TSOs** — resolved 29 Oct 2026. 18:00 D-1 is the publication deadline (SMARD Benutzerhandbuch 02/2025 §1.2.2, Art. 14(1)(d) Reg. (EU) 543/2013); TenneT freezes ~08:00 D-1, 50Hertz ~09:00 D-1. Neither methodology page mentions price or curtailment. **Still open for Amprion**, and whether the wind day-ahead series is ever revised after transmission.
- [x] **§51 / §51a EEG trigger granularity (quarter-hour vs hour)** — resolved 29 Oct 2026 from the consolidated statutory texts. Quarter-hour for the rule in force from 25 Feb 2025; for all earlier, hour-based versions, a calendar hour counts when the arithmetic mean of its four quarter-hour prices is negative (§100(45) EEG 2023). Full table: `05_eeg_rule_table.md`.
- [x] **Negative-price hour counts** — resolved 29 Oct 2026. The "573 vs 539" pair conflated counting rules and is withdrawn. Use the Netztransparenz §51a(3) tables, which count separately per rule version: 2025 = 557 h (§51 as at 24 Feb 2025), 518 h (as at 31 Dec 2022), 199 QHs (new §51(1)).
- [ ] MaStR fields for support status / auction award / direct marketing
- [x] **Count of windy negative quarter-hours since 1 Oct 2025** — resolved 29 Oct 2026: 2,059 negative QHs on 99 event-days; 1,347 QHs on 65 days with DE day-ahead wind forecast ≥ 10 GW. Both clear the pivot thresholds by a wide margin.
- [ ] **Which intraday forecast vintage SMARD archives** — UNRESOLVED as of 29 Oct 2026; searched the SMARD manual, FAQ/announcement, chart-configuration JSON and API payloads. Added as question 4 to the TSO e-mail list.
- [ ] Netzpaket "Redispatch-Vorbehalt" status (draft, not law as of 7 Oct 2026)
- [ ] SRH thesis regulations: length, format, supervisor requirements, registration deadline
