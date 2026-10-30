# 07 — Literature table

Format: `srh-guidelines/06_instructions_to_students_for_their_thesis.txt`, point D —
1. number, 2. title, 3. source, 4. year published, 5. 3–5 sentences of personal comments,
6. methodology used, 7. databases and URL sources, 8. miscellaneous.
Target for the thesis: 25–50 references (point C).

Created 30 Oct 2026 by Claude Code, Phase 1.

**How this file was filled, and what is deliberately empty.**

- **Title, Source, Year** are copied from `06_pivot_mechanism_aware_censoring.md` §9 and
  `02_evidence_base.md`. Nothing is written from memory. Where those documents record only
  an author–year–venue stub and no title, the **Title cell is left `[VERIFY]`** rather than
  reconstructed — a plausible-looking title is exactly the error this project has already
  had to withdraw once (see `02_evidence_base.md` §B2).
- **Comments** is yours. Point D asks for *your personal comments*, and the SRH AI-use
  rubric means this column must not be machine-written. Read title → abstract →
  conclusion → future work, then fill it.
- **Methodology** is left empty for the same reason: it cannot be filled without reading
  the paper.
- **Status** in the Misc column: `[VERIFY]` = not yet checked at the publisher;
  `CONFIRMED` = independently read and checked, with the date.
- Never cite ResearchGate: follow every entry to where it was actually published.

---

## A. Closest prior methods (read first)

| No. | Title | Source | Year | Comments | Methodology | Databases / URL | Misc |
|---|---|---|---|---|---|---|---|
| 1 | [VERIFY] — title not recorded in the repo | SSRN 7025858 (Yang Wang, Haiyun Wang); preprint, un-refereed | 2026 | | | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7025858 | **Read in full 30 Oct 2026.** Closest prior method = **B4**. Turbine-level censored SCADA under *known* grid set-points; point / lower-bound / interval classes; pinball + survival loss; synthetic censoring 20–80%. Censoring indicator **observed** there, latent here. Cite 7025858 as primary. Posting date `[VERIFY]` on SSRN. |
| 2 | [VERIFY] — title not recorded in the repo | SSRN 7195331 (shorter version of No. 1), 35 pp., posted 28 Jul 2026 | 2026 | | | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7195331 | Same study as No. 1, identical data and tables. List once in the thesis; keep both IDs on record. |
| 3 | [VERIFY] — title not recorded in the repo | arXiv 2609.10053 (Lion Hirth, Hertie School / Neon), version of 8 Sep 2026 | 2026 | | | https://arxiv.org/abs/2609.10053 | **Read in full 30 Oct 2026.** = **B3** and the source of the cohort-by-hour threshold construction (cite as his). ERA5 potential calibrated on hours > 5 €/MWh; curtailment = residual; **one pooled response curve** by profit margin (Fig. 12). 2.11 TWh wind / 1.03 TWh solar in 2025 (Table A8); mean correction factor 1.226 (Table A1); Table A11 run-length result. External benchmark for E4. |
| 4 | [VERIFY] — title not recorded in the repo | arXiv 2501.14805 (Jørgensen, Møller, Nystrup & Madsen) | 2025 | | | https://arxiv.org/abs/2501.14805 | = **B2** (deletion). Sequential error correction for probabilistic wind forecasts, DK1/DK2; §2.1 excludes negative-price periods and countertrade-flagged curtailment from **both** training and evaluation. |
| 5 | [VERIFY] — title not recorded in the repo | arXiv 2602.13010v2 (Bruninx, van Binsbergen, Verstraeten, Nowé & Helsen; VUB / NTNU) | 2026 | | | https://arxiv.org/abs/2602.13010 | **Read in full 30 Oct 2026.** B2 family: removes balancing set-points (2.3%) and, as an economic-curtailment proxy, hours below the 5th percentile of their ERA5 wind-speed bin (3.1–3.6%). Fig. 7 / Table VII: ERA5 input beats every single D−1 NWP — evidence for the T1/T2 split. Published version `[VERIFY]`. |

## B. Censored, missing-label and probabilistic-forecasting method literature

| No. | Title | Source | Year | Comments | Methodology | Databases / URL | Misc |
|---|---|---|---|---|---|---|---|
| 6 | [VERIFY] — title not recorded in the repo | *Econometrica* (Tobin) | 1958 | | | | Recorded in spec §9 as "the censored regression model". `[VERIFY]` full citation. |
| 7 | [VERIFY] — title not recorded in the repo | *Econometrica* (Koenker & Bassett) | 1978 | | | | Recorded in spec §9 as "regression quantiles". `[VERIFY]`. |
| 8 | [VERIFY] — title not recorded in the repo | *Journal of Econometrics* (Powell) | 1986 | | | | Recorded in spec §9 as "censored regression quantiles". `[VERIFY]`. |
| 9 | [VERIFY] — title not recorded in the repo | *JASA* (Portnoy) | 2003 | | | | Recorded in spec §9 as "censored regression quantiles". `[VERIFY]`. |
| 10 | Statistical Analysis with Missing Data | Wiley (Little & Rubin) | [VERIFY] edition and year | | | | Missing-not-at-random framework. Give the edition actually used. `[VERIFY]`. |
| 11 | DeepHit [VERIFY] full title | AAAI (Lee et al.) | 2018 | | | | Deep learning with censored targets (survival). `[VERIFY]`. |
| 12 | [VERIFY] — title not recorded in the repo | *JRSS Series B* (Dempster, Laird & Rubin) | 1977 | | | | The EM algorithm; underpins M2. `[VERIFY]`. |
| 13 | [VERIFY] — title not recorded in the repo | *JASA* (Gneiting & Raftery) | 2007 | | | | Proper scoring rules (CRPS). `[VERIFY]`. |
| 14 | [VERIFY] — title not recorded in the repo | *Energy* 73 (Dahl & Croonenbroeck) | 2014 | | | | Censored wind-power forecasting; B4 lineage. Added in spec v1.5. `[VERIFY]`. |
| 15 | [VERIFY] — title not recorded in the repo | *Wind Energy* 17 (Messner et al.) | 2014 | | | | Censored wind-power forecasting; B4 lineage. Added in spec v1.5. `[VERIFY]`. |

## C. Curtailment, redispatch and negative prices (domain)

| No. | Title | Source | Year | Comments | Methodology | Databases / URL | Misc |
|---|---|---|---|---|---|---|---|
| 16 | Forecasting of wind power curtailment events | 18th Wind Integration Workshop, Dublin (Koch, Vogt, Braun, Jost & Dobschinski, Fraunhofer IEE) | 2019 | | | https://publica.fraunhofer.de/ (PDF: publica-rest.fraunhofer.de/server/api/core/bitstreams/25c35a90-7b4f-48ac-b142-0a867f32879d/content) | **CONFIRMED — independently re-read 29 Oct 2026.** Nearest academic work to the *backup* topic. Day-ahead binary classification, extreme learning machine + logistic regression, MCC 0.73, one Schleswig-Holstein park. **Grid-congestion (EinsMan) curtailment, explicitly not price-driven.** |
| 17 | [VERIFY] — title not recorded in the repo | arXiv 2610.08337 (Shamim et al.) | 2026 | | | https://arxiv.org/abs/2610.08337 | Daily TSO-level redispatch forecasting; LightGBM best; 61.9% coverage in high-volume events. Crowds the backup topic. `[VERIFY]`. |
| 18 | [VERIFY] — title not recorded in the repo | arXiv 2412.00423 (Meisenbacher et al.) | 2024 | | | https://arxiv.org/abs/2412.00423 | Autoregressive DL does not beat power-curve models under redispatch shutdowns. `[VERIFY]`. |
| 19 | [VERIFY] — title not recorded in the repo | arXiv 2307.12636 (Titz et al.) | 2023 | | | https://arxiv.org/abs/2307.12636 | SHAP drivers of curtailment; northern wind dominant. `[VERIFY]`. |
| 20 | [VERIFY] — title not recorded in the repo | arXiv 2405.18526 (Acun et al.) | 2024 | | | https://arxiv.org/abs/2405.18526 | North American ISOs; oversupply and transmission curtailment; call-to-action paper, no model. `[VERIFY]`. |
| 21 | Negative Strompreise: Ursachen und Wirkungen | Energy Brainpool for Agora Energiewende, Berlin (Götz, Henkel, Lenck & Lenz) | 2014 | | | https://www.agora-energiewende.de/publikationen/negative-strompreise-ursachen-und-wirkungen | **CONFIRMED as the origin of the "−65 €/MWh" switch-off figure** (29 Oct 2026). Purkus et al. (2015) only cites it. Reflects **2014** market premiums and the 2014 direct-marketing population; 97 negative-price hours Dec 2012 – Dec 2013. Must not be presented as a current number. |
| 22 | [VERIFY] — title not recorded in the repo | *Energy, Sustainability and Society* 5:12 (Purkus, Gawel, Deissenroth, Nienhaus & Wassermann) | 2015 | | | https://doi.org/10.1186/s13705-015-0040-1 | Cites the −65 €/MWh figure to Götz et al. (No. 21); **not the origin**. `[VERIFY]` for anything else taken from it. |
| 23 | Negative electricity prices: How many renewable energy systems will run through? | FfE Munich (Kern, Wasmeier, Bantelmann & Wendlinger), 21 Oct 2024; consultant report, not peer-reviewed | 2024 | | | ffe.de — `[VERIFY]` at source | Cited by Hirth (2026) as FfE (2024): 75% of solar and 67% of wind capacity hold a fixed tariff or an unrestricted premium. **Grey literature.** Earlier wrongly recorded as non-existent — see `02_evidence_base.md` §B2. Cite only after checking at ffe.de. |
| 24 | [VERIFY] — title not recorded in the repo | *Energy Economics* 109 (Frondel et al.) | 2022 | | | | From Hirth's reference list. `[VERIFY]`. |
| 25 | [VERIFY] — title not recorded in the repo | Ghent University working paper 25/1124 (Van Steenberghe & Ovaere) | 2025 | | | | From Hirth's reference list. Working paper. `[VERIFY]`. |
| 26 | [VERIFY] — title not recorded in the repo | *Energy Economics* 126 (López Prol & Zilberman) | 2023 | | | | From Hirth's reference list. `[VERIFY]`. |
| 27 | [VERIFY] — title not recorded in the repo | Fachagentur Wind und Solar, "Gütefaktoren" | 2025 | | | | Source of the site-correction-factor distribution behind the mean 1.226 used in the main θ run (rule 19). `[VERIFY] at this source` — currently taken from Hirth (2026) Table A1. |
| 28 | [VERIFY] — companion paper on the potential series | Hirth (2026), DOI forthcoming | 2026 | | | | Named in spec §9. Track for the DOI. `[VERIFY]`. |

## D. Weather, reanalysis and data sources

| No. | Title | Source | Year | Comments | Methodology | Databases / URL | Misc |
|---|---|---|---|---|---|---|---|
| 29 | [VERIFY] — title not recorded in the repo | *QJRMS* (Hersbach et al.) — ERA5 | 2020 | | | Copernicus CDS | Cite for ERA5 (task T1 only; **leakage in T2**). `[VERIFY]`. |
| 30 | [VERIFY] — title not recorded in the repo | *Energy* 114 (Staffell & Pfenninger) | 2016 | | | | From Hirth's reference list; reanalysis-to-power conversion. `[VERIFY]`. |
| 31 | Open-Meteo Historical Forecast and Previous Runs APIs | Open-Meteo (data source) | n/a | | | https://open-meteo.com | Cite per their licence page. **Licence UNRESOLVED**; DWD-model start date in *Previous Runs* **UNRESOLVED**. The *Historical Forecast* product is stitched from successive runs and is **not** a D−1 vintage. |

## E. Grey literature and practitioner work (not peer-reviewed; sets the bar)

| No. | Title | Source | Year | Comments | Methodology | Databases / URL | Misc |
|---|---|---|---|---|---|---|---|
| 32 | [VERIFY] — article title not recorded in the repo | Ricardo analysis via pv magazine, 8 May 2026 | 2026 | | | https://www.pv-magazine.com/2026/05/08/europes-negative-electricity-price-hours-double-in-q1-amid-renewables-surpluses-market-imbalances/ | DE-LU, April 2026, hourly: wind below the day-ahead forecast in **102 of 123** negative-price hours. Shows the RQ1 *phenomenon* is already in the trade press — RQ1 is confirmatory, not the contribution. |
| 33 | de-weather-to-power (code repository) | GitHub, `michaelserikov/de-weather-to-power` | 2026 | | | https://github.com/michaelserikov/de-weather-to-power | Hourly Dec 2024 – Sep 2026, 1,041 negative-price hours; TSO onshore over-forecast ≈1.5 GW; solar + day type alone cut negative-hour onshore error by **11%**. This is the **price-free proxy baseline** the thesis must clear. |
| 34 | European Price Sensitive Curtailment Report | Montel | 2026 | | | https://montel.energy/resources/reports/european-price-sensitive-curtailment-report | Market-based curtailment +20% in H1 2026 despite negative hours falling. Commercial report. `[VERIFY]` access terms before citing. |

## F. Legal and regulatory primary sources (not "literature", but cited)

Kept here so the thesis reference list is complete. Full detail and access dates are in
`docs/05_eeg_rule_table.md` and `data/reference/eeg_negative_price_rules.csv`.

| No. | Title | Source | Year | Comments | Methodology | Databases / URL | Misc |
|---|---|---|---|---|---|---|---|
| 35 | EEG 2023 §§ 51, 51a, 51b, 100 (consolidated, current) | gesetze-im-internet.de | 2023– | | | https://www.gesetze-im-internet.de/eeg_2014/ | Accessed 29 Oct 2026. §51(1) as amended by Art. 4 EnWGEUVAendG, BGBl. 2025 I Nr. 51, in force 25 Feb 2025. |
| 36 | EEG § 51 version history (consolidated historical versions) | buzer.de | 2014–2025 | | | https://www.buzer.de/51_EEG.htm | Accessed 29 Oct 2026. Source for rules R02–R08. |
| 37 | EEG 2014 § 24, "Verringerung der Förderung bei negativen Preisen" | BGBl. I 2014 S. 1066, in force 1 Aug 2014 – 31 Dec 2016 | 2014 | | | https://www.haufe.de/id/norm/erneuerbare-energien-gesetz-2014-bis-31122016-24-verringerung-der-foerderung-bei-negativen-preisen-HI7054784_p24.html | Accessed 29 Oct 2026. The pre-2017 home of the rule (R01–R03, R12). |
| 38 | SMARD Benutzerhandbuch, editions 02/2025 and 04/2026 | Bundesnetzagentur / SMARD | 2025, 2026 | | | Archived in `data/raw/` | 04/2026 §1.3: intraday forecasts are refreshed repeatedly and 08:00 on the delivery day is a **minimum**, not a freeze time. Confirms the MWh-per-quarter-hour convention ("durch vier dividiert"). |
| 39 | Netztransparenz § 51a(3) publications and redispatch export | Netztransparenz | 2025–2026 | | | https://www.netztransparenz.de | Export `redispatch_2025-10-01_2026-10-28_UTC_dl2026-10-29.csv` in `data/raw/`. **Licence / terms of use UNRESOLVED** — settle before any of it goes into the thesis. |

---

## Not to cite

- **"Kern et al. (2024)" as a peer-reviewed paper.** It exists (No. 23) but is an FfE
  consultant report. Cite it as FfE (2024), grey literature, after checking at ffe.de.
- **"EEG 2027".** Only a BMWE Referentenentwurf of 17 Jul 2026 exists; it is not law.
  Re-check monthly (`06_pivot_mechanism_aware_censoring.md` §10).
- **ResearchGate** as a source for anything — follow to the publisher.
- **consensus.app or any other AI aggregator** as a source — follow to the original.

## Coverage caveat

`02_evidence_base.md` records that novelty checks have covered arXiv, a broad web sweep and
Semantic Scholar / OpenAlex (capped at three hits per query on the free tier).
**Google Scholar and IEEE Xplore remain to do.** This table is therefore incomplete by
construction, not by oversight.
