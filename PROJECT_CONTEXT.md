# Project context — MSc thesis (paste into the Claude Project instructions or knowledge)

Last updated: 30 Oct 2026. The repo `msc-thesis-wind-curtailment` is the source of truth.
If this file and the repo disagree, the repo wins: `docs/06_pivot_mechanism_aware_censoring.md`
(spec v1.7) is the current plan.

## Who and what

- Gagan Ganesh, MSc Computer Science, focus Big Data & AI, SRH Hochschule Berlin, final semester.
- Thesis is the remaining work. Planned window Nov 2026 – Apr 2027; the examination office
  gives 16 weeks from registration (extendable). [VERIFY: the SRH registration form
  (Apr 2026) lists processing time 26 weeks for full-time 4-semester study, 18 for MIBE,
  39 part-time — confirm which applies with the examination office.]
- Strong in Python, ML pipelines and data engineering; not a power-systems or CFD engineer.
  Compute: CPU or a modest GPU; public data only.
- Wants a topic with a real research gap that impresses the supervisors and helps his
  Berlin AI/ML and data job search.

## How to respond to me

- Direct and concise, no preamble. British English. No emoji.
- Plain language: keep the substance, but explain technical terms instead of assuming them.
- Push back when I'm wrong or when there's a better approach.
- Code first, explanation second.
- Never write thesis or proposal prose for me. SRH's AI-use rubric rejects work with more
  than about 30% AI-assisted text (paragraph rewriting is already a warning). Help with
  structure, outlines, critique, code, maths and checking — the prose must be mine.
- Verify every citation at the publisher before it goes in. Mark anything unverified as
  `[VERIFY]` or `UNRESOLVED`. Never assert that something does not exist from a failed search.

## Supervisor rules (Prof. Dr. Alexander Iliev, head of the Big Data & AI programme)

From `srh-guidelines/`:
- The contribution must be an **ML / analytical method** — invented, or an existing one
  improved — "not about analysis and discoveries in the dataset". The data is only the
  benchmark.
- **Not a thesis:** applying ML to a dataset and claiming novelty for the combination;
  evaluating well-known methods without a new one; combining techniques and claiming
  improvements; hyperparameter tuning.
- Show that the most recent research did not solve the problem. Never write "I am the
  first" or "no one has done this".
- **Proposal:** at least 15 pages. Sections: Title, Supervisors, Introduction, Problem
  Description, Objectives, Hypothesis, Methodology, Research Methods, Timeline (table),
  Summary, then **"Intended Contribution to Science"** (½–1 page, arguing why earlier work
  failed or did not tackle the problem this way, backed by the latest research) and
  **"My intended original contribution to science"** (bullet points). Include a table of
  contents, figures, tables and references. Then a 30-minute online defence with the
  supervisor before registration.
- **Sources:** IEEE, ACM, ScienceDirect/Elsevier, Scopus, Web of Science, Springer, MDPI.
  Never cite ResearchGate directly; find where the paper was actually published. Read
  title → abstract → conclusion → future work.
- **Literature table** columns: No., Title, Source, Year, 3–5 sentences of own comments,
  Methodology, Databases/URLs, Misc. Target 25–50 references in the thesis.
- **Paper:** 8–12 pages, aimed at publication (use Elsevier Journal Finder or SCImago).
  Structure: Title, Authors, Abstract, Keywords, Introduction/literature review, Method
  sections, Results, Conclusion (8–10 sentences), References in APA format.
- **Thesis:** at least 20,000 words; Times New Roman 12 pt, 1.5 spacing, justified. No
  full-page chapter titles, no bulky images, no more than a third of images from other
  sources. Code only as numbered "Code snippet N". References numbered in increasing order.
- **Defence:** every slide numbered "n/N". Hand in .doc, .ppt and the code files.
- Two supervisors, at least one from SRH. Involve the supervisor throughout. Two attempts
  only; plagiarism can lead to exmatriculation.

## Topic (decided 29–30 Oct 2026)

**Title:** *Mechanism-Aware Learning under Signal-Driven Censoring: Jointly Recovering
Latent Wind Power and Fleet Switch-Off Response from Price-Curtailed Data*

**The idea in plain words.** Wind forecasting models learn from recorded output. When
German prices go negative, some wind plants switch off for money reasons, so the record no
longer shows how much wind power was available — the label is "censored".

Current practice handles this in one of three ways:
- delete those periods (Jørgensen et al., arXiv 2501.14805);
- calibrate only on uncurtailed periods and treat the leftover as curtailment, after the fact (Hirth, arXiv 2609.10053);
- or ignore it.

Classical censored regression assumes a fixed, known cut-off. Here, instead, an observed
signal (price) triggers a *partial*, uneven switch-off, and the EEG rules partly tell you
which plant groups are exposed.

**Method.** One model with two parts trained together:
- **Observation model:** observed output G = available power A × (1 − curtailed share c).
- **Available power A:** a multiplicative head on the TSO day-ahead forecast and a weather proxy. It never sees price.
- **Curtailed share c:** the sum over plant cohorts of capacity share × exposure (price below the cohort's threshold θ) × learned response r. The response is monotone in depth below θ.
- **Threshold θ:** 0 when the §51 rule is triggered or support has ended; otherwise minus the market premium. Rules enter as model structure, not as features.
- **Variant M1:** quantiles with pinball loss.
- **Variant M2:** an explicit probability density fitted with EM.

**Two tasks.**
- **T1 — after the fact:** recover available power and the response. ERA5 is allowed.
- **T2 — day-ahead forecast:** only true D−1 vintages are allowed (TSO forecast; ICON at 1-day lead from the Open-Meteo Previous Runs API). ERA5 and the stitched Historical Forecast archive would be leakage.

**Baselines:**
- B0: TSO forecast.
- B1: naive model.
- B2: deletion.
- B3: safe-period calibration (Hirth-style).
- B4: censored quantile regression ("pinball with censoring").
- B5: LightGBM given the same price and rule features but no structure — the honest comparison.
- Oracle: trained on true available power (synthetic data only).

**Experiments:**
- **E1:** semi-synthetic benchmark with known truth. Inject censoring into clean positive-price periods; vary censoring rate, weather–price confounding and response shape.
- **E2:** real German 15-minute data.
- **E3:** transfer across a rule change. Needs the hourly 2023 – Sep 2025 data, because only 7 event-days fall before 1 Jan 2026.
- **E4:** learned response vs the statutory "should switch off" curve.
- **E5 (stretch):** solar, or a pre-auction variant.

**Research questions:**
- RQ1 (done): does price-driven censoring bias the labels?
- RQ2: can the model recover A and r, and under which conditions?
- RQ3: how do existing methods degrade as censoring grows?
- RQ4: does the model beat the black box on real data and transfer across rule changes?

**Identification assumptions:**
- I1: no curtailment without an incentive (placebo test).
- I2: overlap. Checked: fine up to 40 GW of forecast wind; above 40 GW only 948 positive-price QHs on 36 days.
- I3: monotone response.
- I4: cohorts separable through the two price clocks (quarter-hour vs hourly mean plus run length).

## Results so far (RQ1 kill test v3, 29 Oct 2026 — verdict GO)

- Data: SMARD 15-minute series, 1 Oct 2025 – 28 Oct 2026; 2,059 negative-price quarter-hours (QHs) on 99 event-days.
- DE bias in negative QHs: **−1,684 MW, 95% CI [−2,694, −807]**, which is **−9.1% [−13.2, −4.8]** of the forecast.
- The bias deepens with price depth: −7,641 MW (−54.7%) at prices ≤ −50 €/MWh.
- Significant in DE, 50Hertz, Amprion and TransnetBW; not in TenneT.
- It behaves like a roughly constant ~9% proportional haircut, so a multiplicative model fits.
- **Survives the redispatch control:** DE excess −1,789 MW, CI [−2,810, −907].
- The intraday forecast still leaves 83% of the DE bias, and makes Amprion 30% worse. Its vintage is unknown, so it is leakage: **never a model input**.
- TSO day-ahead forecasts are frozen before the auction (TenneT ~08:00, 50Hertz ~09:00 D−1), so they are price-blind.
- Tail: 5 of 99 days carry 45–60% of the error, so evaluate by event-day blocks.

## Phase 2 / E1 — first results and the gate revision (30 Oct 2026)

- **Code built:** `src/censoring/` (cohorts, generator, M1, B0–B5, proxy, oracle,
  metrics, runner) and `tests/` (79 tests). The full grid, M2 and the real-data phase
  are not started.
- **M1 recovers the response curve.** On the logistic r\* at 20% censoring, γ = 0,
  int|r̂ − r\*| = 0.0061 against B3's 0.1939, and M1's bias on censored quarter-hours
  is −21 MW against the oracle's −36 MW.
- **The week-6 gate was revised to spec v1.6** after the one-seed smoke run. Minute:
  *gate revised 30 Oct 2026 after one-seed smoke run; reason: at γ = 0 censoring is
  random with respect to F, so deletion is unbiased by construction and criterion (b)
  was unpassable as written.* The new three-part gate is in spec §7, with the
  superseded v1.3 wording kept beside it for audit.
- **Two implementation lessons worth not repeating.** A quantile head built from
  cumulative `softplus` increments must have its bias initialised, or the top quantile
  starts at exp(0.69 × n) times the forecast and every method including the oracle
  scores worse than the raw forecast. And early stopping must be slack enough to be a
  safety net rather than a budget cap: at patience 60 the oracle stopped at ~195 epochs
  while M1 trained 400–560, which made M1 appear to beat the oracle.
- **The gate was made self-contained in spec v1.7 (31 Oct 2026).** Minute: *in both
  earlier versions the gate was decided by other people's methods rather than our own*
  — v1.3's criterion was unpassable because deletion is unbiased at γ = 0, and v1.6's
  was failed by the oracle itself. It now rests on the benchmark's known truth, the
  published TSO forecast and our own oracle, with three criteria: integrated
  |r̂ − r\*| ≤ 0.05, recovery skill score ≥ 0.80, and ĉ correlation ≥ 0.8. External
  baselines stay in the results chapter for positioning, as Iliev's rule requires, but
  no longer decide the go/no-go. Fourth and intended final revision, pre-registered
  before the full grid.
- **Ablation ladder added (§5a).** M1 against M1 with one piece removed — the rule
  table, the cohort structure, the response-head form, the multiplicative form, the
  weather proxy, and the leakage rule deliberately broken. This is the evidence that
  the structure earns its place; baselines cannot supply it.
- **The recoverable headroom is small and should be quoted whenever A-recovery is:**
  the gap between the raw TSO forecast and the oracle is 125–241 MW against a
  1,200–1,800 MW error. That is why r̂ and ĉ are the headline claims.
- **Generator defect fixed (31 Oct).** The positive base price was a constant
  40 €/MWh, so B2 ("price ≥ 0") and B3 ("price > 5") trained on the same sample and
  were the same model in all nine preview cells. Base price is now each quarter-hour's
  own real price, and episodes carry a (0, 5] shoulder; they now differ by 1,840
  quarter-hours. Every number from before 31 Oct predates this fix.
- **Still open before the full grid:** Hirth's Fig. 12 bin edges (UNRESOLVED — do not
  guess them); the solar day-ahead series for the price-free proxy (Phase 3,
  `data_id` 125); M2.

## Data and pipeline facts

- **SMARD:** quarter-hour values are MWh per QH; multiply by 4 to get MW. `DE` is the exact sum of the four control areas. Filter IDs are read from the archived chart-configuration JSON.
- **EEG §51 rules:** in `data/reference/eeg_negative_price_rules.csv` and `docs/05_eeg_rule_table.md`.
  - The post-25 Feb 2025 rule uses the quarter-hour price.
  - Older rules use the hourly mean of the four QH prices plus a run length of 6 h, 4 h, or the 2023–25 staircase, which went from 3 h to 2 h on 1 Jan 2026.
  - Pre-2016 plants are exempt from §51.
- **Redispatch** (Netztransparenz export) and **intraday forecasts** are for evaluation and stratification only.
- **Conventions:** Parquet, UTC timestamps, seed 42, rolling-origin splits with a 7-day embargo, event-day block bootstrap, `data/raw` append-only, no shuffling.

## Literature anchors (verify before citing)

- **Closest prior work — read first:** Wang & Wang (2026), SSRN 7025858 (primary) and 7195331, preprints of one study. Censored SCADA under known grid commands, three Chinese farms. **Verified 30 Oct** — the censoring indicator is observed there and latent here; their objective is B4.
- **Domain:** Hirth (2026); Jørgensen, Møller, Nystrup & Madsen (2025); Koch et al. (2019, Fraunhofer IEE, grid curtailment); Shamim et al. (2026, redispatch forecasting); Götz et al. (2014, Agora — origin of the "−65 €/MWh" figure; Purkus et al. 2015 and Hirth 2026 cite it secondhand).
- **Method side:** Tobin (1958); Koenker & Bassett (1978); Powell (1986); Portnoy (2003); Dempster, Laird & Rubin (1977); Little & Rubin (missing data); Lee et al. (2018, DeepHit); Gneiting & Raftery (2007); Hersbach et al. (2020, ERA5).
- **Corrected 30 Oct:** "Kern et al. (2024)" exists — an FfE consultant report (Kern, Wasmeier, Bantelmann & Wendlinger, 21 Oct 2024), cited by Hirth (2026) as FfE (2024). Grey literature; verify at ffe.de before any use. The earlier "does not exist" entry broke our own rule.
- **Do not cite "EEG 2027":** only a ministry draft exists (17 Jul 2026), not law. It proposes a mandatory price threshold for curtailment in direct-marketing contracts (§10b(7)) and changes to §51. Watch item.

## Open items

- Choose and confirm the first and second supervisors; write the proposal and do the 30-minute defence; register.
- Wang & Wang verified 30 Oct; still to run: Google Scholar and IEEE Xplore novelty checks.
- MaStR link to support status and award values; monthly market values; ERA5 access (Copernicus key).
- Earliest DWD ICON date in the Open-Meteo Previous Runs API; the Open-Meteo licence.
- Questions for the TSOs: Amprion freeze time; intraday vintage; whether the day-ahead wind series is ever revised.
- Possible contacts: Lion Hirth (Hertie School / Neon); 50Hertz forecasting; a direct marketer.

## Repo map

- `docs/06_pivot_mechanism_aware_censoring.md` — the current plan (spec v1.7)
- `docs/04_rq1_killtest_note_v3.md` — kill-test evidence
- `docs/05_eeg_rule_table.md` — rule table
- `docs/02_evidence_base.md` — evidence base
- `CLAUDE_CODE_PROMPT.md` — the phased implementation task for Claude Code
- `docs/01_thesis_brief.md` — will be rewritten to v2 by Claude Code; the old version is archived as `_v1_forecast-correction`
