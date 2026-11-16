# Data Sources — Reference Sheet

Identifiers and endpoints below are from general knowledge plus the 28 Oct 2026 research; **verify each one on first use**.

---

## ENTSO-E Transparency Platform (primary)

- Access: free account → email transparency@entsoe.eu to request a RESTful API security token. Python: `entsoe-py` (`EntsoePandasClient`).
- API base: `https://web-api.tp.entsoe.eu/api`
- Licence: ENTSO-E Terms & Conditions; items on the open-data list are CC BY 4.0. Check the list for each dataset used.

| Data | Article | documentType / processType | entsoe-py call |
|---|---|---|---|
| Day-ahead wind & solar forecast | 14.1.D | A69 / A01 | `query_wind_and_solar_forecast` |
| Actual generation per production type | 16.1.B&C | A75 / A16 | `query_generation` |
| Day-ahead prices | 12.1.D | A44 | `query_day_ahead_prices` |
| Installed capacity per production type | 14.1.A | A68 | `query_installed_generation_capacity` |

- Rule to check: 14.1.D forecasts must be published by **18:00 Brussels time D-1**, i.e. after day-ahead results (~12:45). Key question for RQ1: do German TSOs' forecasts already account for prices?
- Area codes (EIC, verify):
  - DE-LU bidding zone: `10Y1001A1001A82H`
  - 50Hertz: `10YDE-VE-------2`
  - Amprion: `10YDE-RWENET---I`
  - TenneT DE: `10YDE-EON------1`
  - TransnetBW: `10YDE-ENBW-----N`
- Production types: B18 = Wind Offshore, B19 = Wind Onshore, B16 = Solar.

## SMARD (Bundesnetzagentur)

- https://www.smard.de — downloads of generation, forecasts and prices at 15-min / hourly resolution; also an unofficial JSON chart-data API.
- Licence: CC BY 4.0 (https://www.smard.de/en/datennutzung).
- Use: cross-check ENTSO-E series; redispatch statistics.

## Marktstammdatenregister (MaStR)

- https://www.marktstammdatenregister.de/MaStR/Datendownload — daily full XML exports.
- Python: `open-mastr` (OpenEnergyPlatform), bulk download into SQLite/CSV. Docs: https://openenergyplatform.github.io/mastr-docs/
- Licence: dl-de/by-2-0.
- Fields needed: unit ID, energy carrier (wind onshore/offshore), net capacity, commissioning date (Inbetriebnahmedatum), TSO/control area or postcode/location, EEG unit data (EEG key, support-related fields — **check whether award/Zuschlag number or direct-marketing status exists and how complete it is**), decommissioning date.
- Always take a **dated snapshot** and record the date in the thesis.

## Netztransparenz.de (the four TSOs jointly)

- https://www.netztransparenz.de — redispatch measures (renewables redispatch from 1 Oct 2023), reBAP imbalance prices, EEG market values (Marktwerte, needed for market-premium break-even prices).
- Licence: **not verified**.
- Use: exclude or control for grid-driven curtailment; imbalance-cost proxy; monthly market values for switch-off price curve.

## ERA5 (ECMWF / Copernicus)

- Copernicus Climate Data Store, `cdsapi`. Dataset: ERA5 hourly single levels; variables `100m_u_component_of_wind`, `100m_v_component_of_wind`.
- Licence: CC BY 4.0 (since Jul 2025, per secondary quote of ECMWF notice — confirm on CDS).
- Use: weather-based "potential" hindcast for analysis labels, not as the forecasting target.

## DWD Open Data

- https://opendata.dwd.de — station wind observations for validation. Licence: CC BY 4.0.

## Legal texts (primary sources for rules)

- EEG 2023 §51, §51a, market premium rules: https://www.gesetze-im-internet.de/eeg_2014/
- Solarspitzengesetz amendments (in force 25 Feb 2025): check the consolidated EEG text.

## Not used / low priority

- New European Wind Atlas, Open Power System Data (OPSD's time series stopped being updated years ago — check), EDP, La Haute Borne, Kelmarsh/Penmanshiel SCADA (UK, saturated), Global Renewables Watch (sanity check of fleet locations only; licence conflicting: MIT vs CC BY 4.0).
