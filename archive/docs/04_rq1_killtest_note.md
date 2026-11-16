# RQ1 Kill Test — Go/No-Go Note

Version 2, 29 Oct 2026 (v1: 28 Oct 2026). Data: SMARD 15-min (CC BY 4.0) and Netztransparenz redispatch, 1 Oct 2025 – 28 Oct 2026.
Code: `src/ingest_smard.py`, `src/ingest_smard_intraday.py`, `src/kill_test.py`, `src/check_da_vs_id.py`, `src/fetch_redispatch_pw.py`, `src/fetch_redispatch_all.sh`, `src/redispatch_control.py`. Seed 42, 5,000 bootstrap draws resampling whole Berlin-local event-days.

**Verdict: GO.** The negative-price over-forecast is significant in DE, 50Hertz, Amprion and TransnetBW. It survives the redispatch control. One open item (TSO email) affects interpretation, not the go decision.

## Definitions

- e_t = actual wind feed-in − TSO day-ahead wind forecast, MW (quarter-hour average). Negative = over-forecast.
- Negative QH: DE-LU day-ahead price < 0. Event-day: Berlin-local date with ≥1 negative QH.
- Excess error: e_t in negative QHs minus mean e_t in positive-price QHs in the same stratum (stated per test).

## 1. Sample size vs pivot thresholds

2,059 negative QHs on 99 event-days; 1,347 QHs on 65 days with DE wind forecast ≥ 10 GW. Pivot minimum ~150 QHs / ~20 days. Passes.

## 2. Bias by price band (DE)

| Price band (€/MWh) | QHs | Days | Mean e (MW) | 95% CI | e / forecast |
|---|---|---|---|---|---|
| ≤ −50 | 149 | 12 | −7,641 | [−13,848, −2,430] | −54.7% |
| −50 to −20 | 148 | 20 | −2,654 | [−4,760, −1,293] | −20.8% |
| −20 to −5 | 301 | 38 | −1,693 | [−2,983, −516] | −12.2% |
| −5 to 0 | 1,461 | 99 | −977 | [−1,609, −320] | −4.7% |
| 0 to 5 | 1,274 | 138 | −724 | [−1,318, −199] | −2.9% |
| > 5 | 34,256 | 391 | +184 | [57, 308] | +1.1% |

Robustness: without Easter (5–6 Apr 2026) −1,114 MW [−1,671, −558]; without worst 5 days −994 MW [−1,552, −452]. Top 5 days = 45% of total negative-QH error (heavy tails).

## 3. Check 1 — is the SMARD forecast really day-ahead? PASSED

- SMARD's own chart configuration (`/app/chart_configuration/market_data_configuration.json`, read 29 Oct 2026) lists 123 (onshore) and 3791 (offshore) under "Prognostizierte Erzeugung Day-Ahead". Intraday is a separate subcategory: 5127 (onshore), 5128 (offshore).
- Empirically: day-ahead and intraday values are identical in ≤3% of QHs. Intraday MAE is 20–50% lower in every area, as a later forecast should be.
- SMARD user manual (04/2026): day-ahead forecasts are produced by the TSOs under Reg. 543/2013 Art. 14(1)(d) and sent to ENTSO-E by 18:00 D-1.
- ENTSO-E 14.1.D value cross-check downgraded to optional.
- Side finding: the intraday forecast is also biased in negative QHs (DE −1,394 MW vs −1,684 MW day-ahead).

## 4. Check 2 — does grid redispatch explain the bias? NO

Data: Netztransparenz TSO-instructed redispatch measures, renewable ("Erneuerbar") reductions, solar-named plants excluded, spread over quarter-hours using energy ÷ duration. Assigned to the instructing TSO.

Renewable redispatch is concentrated in TenneT (7.4 TWh) and 50Hertz (1.3 TWh). Amprion (0.02 TWh) and TransnetBW (0.006 TWh) have almost none.

Key observation: at positive prices the raw error stays near zero even with 1.5–3 GW of redispatch (TenneT +72 MW, 50Hertz −507 MW). So TSO-instructed redispatch mostly does not appear as forecast error. Adding it back to "actual" is not a valid control (it overcorrects).

Valid control (test C): compare negative-price QHs with positive-price QHs at the same redispatch level (5 bins) and forecast-level decile.

| Area | Raw bias, neg QHs (MW) | Excess, test C (MW) | 95% CI | Neg QHs with any RE redispatch |
|---|---|---|---|---|
| DE | −1,684 | −1,713 | [−2,741, −822] | 96% |
| 50Hertz | −833 | −741 | [−1,102, −406] | 63% |
| Amprion | −431 | −501 | [−687, −338] | 2% |
| TenneT DE | −326 | −402 | [−916, 72] | 94% |
| TransnetBW | −94 | −93 | [−128, −60] | 6% |

Also: in 50Hertz QHs with zero redispatch the bias is −515 MW [−798, −245]. Amprion and TransnetBW are effectively redispatch-free and still biased.

## 5. Check 3 — TenneT forecast method

- TenneT: day-ahead forecast "basieren auf einer Kombination von mehreren Windenergieeinspeisungsprognosen mit Stand 8:00 Uhr für den Folgetag", published 18:00 (netztransparenz.tennet.eu, read 29 Oct 2026).
- 50Hertz: forecast values are "those of 09:00 hrs the previous day", from service providers, GFS/ECMWF-based (50hertz.com, read 29 Oct 2026).
- SDAC day-ahead gate closure 12:00 CET, results 12:57 CET (BSP SouthPool Day-ahead Timings v1.5, valid from 30 Sep 2025).
- Conclusion: at least TenneT and 50Hertz freeze their forecast **before** the day-ahead prices exist. The forecasts are price-blind by construction. The v1 hypothesis "TenneT is price-aware" is rejected.
- TenneT's weak bias is still unexplained. Candidates:
  - (a) its reference-park extrapolation under-represents plants that switch off;
  - (b) overlap with heavy redispatch (a plant already curtailed for the grid cannot also switch off for price);
  - (c) a different plant mix by EEG cohort. Test (c) with MaStR.

## Corrections to v1 (28 Oct)

1. v1 said the TSO forecast is made after the auction ("due 18:00, after results"). Wrong: 18:00 is the publication deadline. TenneT and 50Hertz forecasts are frozen at 08:00 and 09:00 D-1.
2. v1 said redispatch is "unlikely the main driver" based on geography alone. Now supported by test C, but v1's reasoning was insufficient.
3. TenneT price-aware hypothesis: rejected (see §5).

## Implications for the method (update brief)

- **Fair-comparison trap.** The model's forecast time must be after 12:57 CET D-1, so it also gets 4–5 h fresher weather than the TSO forecast. Mandatory ablation: same model and forecast time *without* price and MaStR features. Only the gain over this ablation counts as price-information value for RQ2.
- **Leakage.** Redispatch data is published after the fact. Use it only to stratify the evaluation, never as a model input.
- **Evaluation focus.** 50Hertz and Amprion are primary (clean, significant signal). TransnetBW is small. TenneT is secondary and reported with the caveat above.
- **Measurement limitation.** "Actual" wind is an extrapolation from metered reference plants (TenneT, 50Hertz, Amprion pages). Errors are measured against the TSOs' own published actuals.

## Open item

- [ ] Email TSO forecasting teams (50Hertz, TenneT, Amprion). Ask:
  - (1) Does the day-ahead forecast include expected redispatch or market-driven curtailment?
  - (2) Do the reference plants for the extrapolation include direct-marketed plants that switch off at negative prices?
  - (3) What is the exact forecast freeze time? (Amprion's page gives none.)
- [ ] Optional: ENTSO-E 14.1.D value cross-check once the API token arrives.

## Known gaps

- Redispatch data covers TSO-instructed measures. Whether DSO-initiated Redispatch 2.0 measures for DSO congestion are included is unverified. Check the Netztransparenz "Redispatch 2.0 at the TSO-DSO interface" page.
- Wind vs solar split in the redispatch data is by plant name only (0.6% solar-named). Pooled entries ("UW …", DSO pools) may contain PV.
- Effective sample is ~20 deep-negative event-days; one weekend dominates the tail.
