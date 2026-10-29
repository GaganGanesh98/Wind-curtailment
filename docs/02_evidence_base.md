# Evidence Base — Current Affairs and Literature (as of 28 Oct 2026)

Condensed from the deep-research report of 28 Oct 2026. Items marked **unverified** or **conflicting** must be checked against primary sources before they go into the thesis. Preprints are not peer-reviewed.

---

## A. Current affairs (Germany / EU wind)

| Topic | Key facts | Why it matters for the thesis | Source (date) |
|---|---|---|---|
| Onshore expansion | 2025: record 20.8 GW permitted, 5.2 GW installed; fleet 29,226 turbines / 68,067 MW; permitting time avg 16.8 months; repowering ~30% of new installs; ~9 GW more permitted H1 2026. 2030 target 115 GW. | Bottleneck shifts to grid and curtailment; MaStR fleet grows fast | Deutsche WindGuard / FA Wind und Solar status report 2025 (2026); Clean Energy Wire (Jan 2026, H1 2026) |
| Offshore auctions | Aug 2025: zero bids for 2.5 GW (N-10.1/N-10.2), first time ever. All 2026 tenders cancelled (28 Jan 2026), moved to 2027. Cabinet adopted WindSeeG overhaul 2 Sep 2026 (CfD fallback). Only 0.5 GW connected in 2025 (9.7 GW total). | Merchant revenue risk incl. negative prices is the core investment question | Clean Energy Wire, WindEurope (6 Aug 2025); Freshfields (3 Sep 2026) |
| Redispatch | 2025 congestion management cost €3.071bn; renewable curtailment compensation €433m; offshore wind redispatch 3,351 GWh (−27%), onshore 3,225 GWh. Q1 2026 onshore wind curtailment +39% to 1,054 GWh. | Confounder: grid-driven curtailment also lowers wind feed-in. Backup topic. | BNetzA via SMARD (30 Mar 2026); BWE fact check (Apr 2026); IWR (Q1 2026) |
| Netzpaket / Redispatch-Vorbehalt | Draft would allow uncompensated curtailment of new plants in congested areas. Draft terms **conflict** (6 vs 10 years; 20% yield cap). Not law; Bundestag hearing 7 Oct 2026. | Could make curtailment forecasting a bankability issue | energiezukunft (May 2026); green-2-market (Jul 2026); hausbesitzer-news (7 Oct 2026) |
| Negative prices & §51 EEG | Negative day-ahead hours: 301 (2023), 457 (2024). For 2025 use the Netztransparenz §51a(3) tables, which count by rule version: **557 h** (§51 as at 24 Feb 2025), **518 h** (§51 as at 31 Dec 2022), **199 QHs** (§51(1) new rule). The old "573 vs 539" pair conflated different counting rules and is withdrawn. Since 1 Oct 2025 an hour counts as negative where the **arithmetic mean of its four QH prices** is negative (§100(45) EEG 2023, verified 29 Oct 2026). Trigger granularity resolved — see `05_eeg_rule_table.md`. | Per-plant incentive depends on commissioning cohort and support scheme → MaStR | Netztransparenz §51a(3) publications; EEG 2023 §100(45) via gesetze-im-internet.de (29 Oct 2026) |
| 15-min day-ahead market | SDAC 15-min market time unit live for delivery from 1 Oct 2025. | Switch-off decisions are per quarter-hour | EPEX SPOT (30 Sep 2025); SDAC (7 Oct 2025) |
| Market-based curtailment | DE commercial curtailment 1,749.7 GWh in 2025 (+~25%); H1 2026 +20% (1,216 → 1,463 GWh) despite negative hours falling 389 → 299; Montel forecasts ~2 TWh record for 2026. Hirth 2026: **2.11 TWh wind / 1.03 TWh solar** for 2025 (Table A8), residual method against an ERA5-based potential; at < −50 €/MWh almost all wind had an incentive to stop, only about half did. Hourly, **ex post, no forecasting**. | **The core gap.** No official statistic; forecasters over-predict in these periods | Montel via pv magazine (3 Feb 2026); Montel Price Sensitive Curtailment Report (Jul 2026); Hirth arXiv 2609.10053 (9 Sep 2026) |
| North Sea wakes | By 2030, 13 of 69 North Sea farms lose >10% to inter-farm wakes; some German farms >18% (simulation). | Physics-heavy; public data too confounded → dropped | Borgers et al., Environ. Res. Lett. (13 Jun 2025) |
| Bat / noise limits | Bat shutdown algorithms standard in DE; 90% bat protection costs 3.5–4.9% AEP. Ice-throw rules **unverified**. | Bat data not public → dropped | J. Environ. Management (2026); Gonzales et al. (2026) |
| Dunkelflaute | Nov and Dec 2024 events; day-ahead price peaked €936/MWh (12 Dec 2024, 17–18h); no market abuse found. | Context for wind value | BNetzA & Bundeskartellamt (21 Oct 2025) |
| Cyber | Viasat hack Feb 2022 cut remote monitoring of 5,800 Enercon turbines (11 GW). 2025 GIDS study on Chinese turbine risk. | No public data → undoable | Reuters (28 Feb 2022); Offshore Magazine (28 May 2025) |
| Reliability | Siemens Gamesa 4.X/5.X €1.6bn charge (2023); no 2025–26 fleet statistics found. 2026 audit found structural defects in Kelmarsh SCADA. | SCADA topics saturated and data-flawed | Siemens Energy (2023); Zenodo 23171808 (2026) |

## B. Literature map

| Problem | Key papers | Notes | Crowding |
|---|---|---|---|
| Single-farm wind power forecasting | Many (Kelmarsh/Penmanshiel based) | Same datasets, tiny margins | Saturated |
| SCADA fault/anomaly detection | Zenodo 18430475 (2026); Kelmarsh audit Zenodo 23171462 / 23171808 (2026) | Small UK fleets; data defects | Saturated/Busy |
| Grid-driven curtailment (redispatch, congestion, oversupply) | **Koch, Vogt, Braun, Jost & Dobschinski (Fraunhofer IEE), "Forecasting of wind power curtailment events", 18th Wind Integration Workshop, Dublin, Oct 2019 — CONFIRMED (independently re-read 29 Oct 2026)**; Shamim et al., arXiv 2610.08337 (Oct 2026); Meisenbacher et al., arXiv 2412.00423 (Dec 2024); Titz et al., arXiv 2307.12636 (2023); **Acun et al., arXiv 2405.18526 (2024)** | **Koch et al. is the nearest academic work to the backup topic:** day-ahead binary classification of curtailment occurrence, extreme learning machine + logistic regression, MCC 0.73, one Schleswig-Holstein park. It is **grid-congestion curtailment (EinsMan)**, explicitly not price-driven; day-ahead and intraday prices are named as possible features but not used. Shamim: daily TSO-level redispatch, LightGBM best, 61.9% coverage in high events. Meisenbacher: autoregressive DL doesn't beat power-curve models under redispatch shutdowns. Titz: SHAP drivers, northern wind dominant. Acun et al.: North American ISOs, oversupply and transmission curtailment, call-to-action paper with no model. | Busy |
| **Price-driven wind curtailment** | **Hirth, Lion (Hertie School; Neon), arXiv 2609.10053 (9 Sep 2026)**; **Jørgensen, Møller, Nystrup & Madsen, arXiv 2501.14805 (2025)**; arXiv 2505.05153 (2025, bidding under one-price balancing) | Hirth: hourly, ex-post residual estimate against an ERA5 potential; cannot separate model error from curtailment, and does not forecast. Jørgensen et al.: sequential error correction for probabilistic wind forecasts in **DK1 and DK2**; §2.1 excludes negative-price periods (Jan 2022 – Jul 2023) and countertrade-flagged curtailment from **both training and evaluation** — i.e. it removes exactly the events this thesis targets. | **Thin / near-empty for forecasting** |
| Inter-farm wakes | Borgers et al. ERL (2025); Anantharaman et al., WES 10, 1849 (2025); WES 11, 1077 (2026); WES 11, 3295 (2026); arXiv 2610.23624 (2026) | Mesoscale models; private SCADA | Busy (physics) |
| Bat/noise curtailment | J. Env. Mgmt (2026); Gonzales et al. (2026) | Needs acoustic data | Thin, data-blocked |
| Dunkelflaute risk | arXiv 2509.24788 (2025) | Generative DL on reanalysis | Busy-ish |

**Search coverage caveat (updated 29 Oct 2026):** novelty checks have now additionally
covered Semantic Scholar / OpenAlex (via a paper-search aggregator, each hit followed to
the publisher or arXiv original — the aggregator itself is never cited) and a broad web
sweep that surfaced Fraunhofer Publica, ScienceDirect, ACM DL and ResearchGate items.
**Still to do: Google Scholar and IEEE Xplore directly.** The aggregator capped results at
three per query on the free tier, so this narrows the novelty risk rather than closing it.

Queries used so far:
- "arXiv redispatch curtailment prediction wind Germany machine learning 2025"
- "wind power negative prices market-based curtailment self-curtailment direct marketing Germany estimation data"
- "wind power forecasting negative prices curtailment arXiv"
- "machine learning inter-farm wake loss German Bight SCADA ENTSO-E data-driven"
- "national-scale loss modeling German onshore wind fleet 2024 10-minute wake noise bat curtailment"

## B2. Verified provenance of key figures (added 29 Oct 2026)

| Figure | Status | Origin and derivation |
|---|---|---|
| Direct-marketed wind switches off at about **−65 €/MWh** | **Confirmed to origin** | Purkus, Gawel, Deissenroth, Nienhaus & Wassermann (2015), *Energy, Sustainability and Society* 5:12, doi 10.1186/s13705-015-0040-1, states that wind plants in direct marketing curtail at negative prices of approximately −65 €/MWh and cites this to reference [42]. Reference [42] is **Götz, Henkel, Lenck & Lenz (2014), "Negative Strompreise: Ursachen und Wirkungen", Energy Brainpool for Agora Energiewende, Berlin** — so Purkus is not the origin. The English edition of that study states that because much wind output is sold directly, production is shut in the negative price range starting around negative 65 euros/MWh. **Cite Götz et al. (2014) as the origin.** It reflects **2014** market premiums and the 2014 direct-marketing population; it is not a current number and must not be presented as one. The study's own scope was the 97 negative-price hours between December 2012 and December 2013. |
| **"Kern et al. (2024)"** | **Withdrawn — no such paper** | This citation was produced in conversation on 29 Oct 2026 from a web-search summary, and the link attached to it duplicated Hirth's. It was never written into this document. No paper of that name could be found. Do not cite it. |
| Hirth 2025 volumes | Confirmed | 2.11 TWh wind, 1.03 TWh solar, Table A8 of arXiv 2609.10053. |

## B3. Grey literature and practitioner work (added 29 Oct 2026)

Not peer-reviewed. Listed because it is independent public-data evidence for the RQ1
phenomenon, and because it sets the bar the thesis has to clear.

| Source | What it shows | Why it matters |
|---|---|---|
| Ricardo analysis via pv magazine, 8 May 2026 | DE-LU, April 2026, hourly: wind below the day-ahead forecast in **102 of 123** negative-price hours | The RQ1 *phenomenon* is already in the trade press. RQ1 is confirmatory, not the contribution. |
| GitHub `michaelserikov/de-weather-to-power` (late 2026) | Hourly, Dec 2024 – Sep 2026, **1,041 negative-price hours**; TSO onshore over-forecast **≈1.5 GW**; adding expected solar and day type cuts the negative-hour onshore error by **11%** | A concrete, reproducible baseline. Any RQ2 claim must beat a price-free proxy model of this kind, not only the raw TSO forecast. Its stated limitations — no price forecast, no plant register — are the gap this thesis occupies. |

## C. Candidates considered and why they were dropped

| Candidate | Verdict | Reason |
|---|---|---|
| A. Price-driven curtailment-aware forecast | **Winner** (score 32/35) | Open gap, public data, cheap, career-relevant |
| B. Hourly 50Hertz redispatch forecast | **Backup** (28/35) | Real but crowding since Oct 2026 (Shamim) |
| C. "Wind theft" between offshore farms from public data | Dropped | Hourly ENTSO-E data too contaminated by redispatch/outages |
| D. Bat/noise curtailment detection in open SCADA | Dropped | UK farms, no labels, wrong regulations |
| E. Main-bearing model transfer across turbine types | Dropped | Saturated; defective dataset |

## D. Key URLs

- Hirth 2026: https://arxiv.org/abs/2609.10053
- Shamim et al. 2026: https://arxiv.org/abs/2610.08337
- Meisenbacher et al. 2024: https://arxiv.org/abs/2412.00423
- Titz et al. 2023: https://arxiv.org/abs/2307.12636
- Jørgensen, Møller, Nystrup & Madsen 2025 (DK1/DK2 sequential error correction): https://arxiv.org/abs/2501.14805
- Koch et al. 2019 (Fraunhofer IEE, curtailment-event forecasting): https://publica.fraunhofer.de/ — Publica record; PDF at publica-rest.fraunhofer.de/server/api/core/bitstreams/25c35a90-7b4f-48ac-b142-0a867f32879d/content
- Acun et al. 2024 (curtailment prediction, North American ISOs): https://arxiv.org/abs/2405.18526
- Götz, Henkel, Lenck & Lenz 2014 (Agora/Energy Brainpool, origin of −65 €/MWh): https://www.agora-energiewende.de/publikationen/negative-strompreise-ursachen-und-wirkungen (EN PDF: .../fileadmin/Projekte/2013/Agora_Negative_Electricity_Prices_Web.pdf)
- Purkus et al. 2015: https://doi.org/10.1186/s13705-015-0040-1
- EEG §51 / §51a / §100, current: https://www.gesetze-im-internet.de/eeg_2014/
- EEG §51 version history: https://www.buzer.de/51_EEG.htm
- Ricardo via pv magazine, 8 May 2026: https://www.pv-magazine.com/2026/05/08/europes-negative-electricity-price-hours-double-in-q1-amid-renewables-surpluses-market-imbalances/
- de-weather-to-power: https://github.com/michaelserikov/de-weather-to-power
- Bidding under one-price balancing 2025: https://arxiv.org/abs/2505.05153
- Montel price-sensitive curtailment report: https://montel.energy/resources/reports/european-price-sensitive-curtailment-report
- pv magazine, curtailment 2025: https://www.pv-magazine.com/2026/02/03/germany-france-netherlands-curtail-3-9-twh-of-renewables-in-2025/
- Clean Horizon, negative prices: https://www.cleanhorizon.com/news/negative-prices-on-day-ahead-markets-why-and-whats-next/
- EPEX 15-min go-live: https://www.epexspot.com/en/news/15-minute-products-live-epex-spot-day-ahead-markets
- SMARD redispatch 2025: https://www.smard.de/page/en/topic-article/5892/220534/volume-of-measures-stable-in-the-year-as-a-whole
- Clean Energy Wire, zero-bid offshore auction: https://www.cleanenergywire.org/news/no-bids-german-offshore-wind-auction-first-time-industry-association
- Freshfields, WindSeeG overhaul: https://www.freshfields.com/en/our-thinking/blogs/sustainability/new-winds-ahead-germanys-overhaul-of-its-offshore-wind-regime-102nrmg
- Borgers et al. 2025 (wakes): https://iopscience.iop.org/article/10.1088/1748-9326/add8a2
- Dunkelflaute generative DL: https://arxiv.org/abs/2509.24788
- ACM e-Energy 2027: https://energy.acm.org/conferences/eenergy/2027/
