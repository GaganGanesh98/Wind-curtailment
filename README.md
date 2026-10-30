# MSc Thesis — Mechanism-Aware Learning under Signal-Driven Censoring

Jointly recovering latent wind power and fleet switch-off response from price-curtailed
German data.

Gagan Ganesh, MSc AI/ML (Big Data), SRH Hochschule Berlin. Nov 2026 – Apr 2027.

**Source of truth:** `docs/06_pivot_mechanism_aware_censoring.md` (spec v1.5). Where any
other document disagrees with the spec, the spec wins.

## Status

- **Topic pivoted 29–30 Oct 2026** from forecast correction to a censored-learning method.
  The old plan is archived unchanged at `docs/01_thesis_brief_v1_forecast-correction.md`.
- **RQ1 kill test: GO** (29 Oct 2026). All four checks reproduce, including the redispatch
  control, which confirms that grid redispatch does not explain the negative-price
  over-forecast. DE bias −1,684 MW, 95% CI [−2,694, −807], i.e. −9.1% of the forecast.
  Write-up: `docs/04_rq1_killtest_note_v3.md` (v2 kept unchanged at
  `docs/04_rq1_killtest_note.md`).
- **§51 EEG rule table** built from the consolidated statutory texts:
  `docs/05_eeg_rule_table.md` and `data/reference/eeg_negative_price_rules.csv`.
- **Next gate:** E1 semi-synthetic benchmark must pass the criterion in spec §7 by
  **31 Dec 2026**.

## Layout

```
msc-thesis-wind-curtailment/
├── README.md
├── CLAUDE_CODE_PROMPT.md      phased implementation task (hard rules 1-19)
├── PROJECT_CONTEXT.md         background for a fresh assistant session
├── docs/
│   ├── 01_thesis_brief.md                      v2 working brief
│   ├── 01_thesis_brief_v1_forecast-correction.md   archived v1 plan
│   ├── 02_evidence_base.md                     literature and current affairs
│   ├── 03_data_sources.md
│   ├── 04_rq1_killtest_note.md                 kill test v2 (do not overwrite)
│   ├── 04_rq1_killtest_note_v3.md              kill test v3, verdict GO
│   ├── 05_eeg_rule_table.md                    section 51 rules in plain English
│   ├── 06_pivot_mechanism_aware_censoring.md   THE SPEC (v1.5)
│   └── 07_literature_table.md                  SRH literature table (point D format)
├── srh-guidelines/            SRH / supervisor rules and templates (read-only)
├── data/
│   ├── raw/                   untouched downloads; append-only, gitignored
│   ├── processed/             cleaned Parquet, UTC timestamps; gitignored
│   └── reference/             small tracked reference tables (EEG rule table)
├── src/
│   ├── smard_config.py        filter IDs, areas, price bands, seed
│   ├── ingest_smard.py        weekly JSON download
│   ├── build_panel.py         panel_qh.parquet, DST and gap checks
│   ├── stats_boot.py          event-day block bootstrap (reuse, do not duplicate)
│   ├── kill_test.py           RQ1 analyses 1 and 2
│   ├── check_da_vs_id.py      Check 1, day-ahead vs intraday
│   ├── redispatch_control.py  Check 2, redispatch-stratified excess error
│   ├── make_figures.py        kill-test figures
│   └── censoring/             the pivot: cohorts, generator, model, baselines
├── tests/                     pytest suite
├── notebooks/                 exploration only; anything reused moves to src/
├── results/                   every number in the docs comes from here
└── figures/
```

## Conventions

- Parquet, all timestamps UTC; Berlin-local only for event-day grouping.
- SMARD quarter-hour values are **MWh per quarter-hour**; MW = value × 4.
- Seed 42. Rolling-origin splits with a 7-day embargo, event-day blocks for CV and
  bootstrap, no shuffling.
- `data/raw/` is append-only and never modified. `data/` is gitignored except
  `data/reference/`.
- Every number in a document comes from code in `src/` that writes it to `results/`.
- **Never a model input:** the intraday forecast, redispatch, same-quarter-hour actuals,
  ERA5 and the stitched Historical Forecast archive in task T2, and the published monthly
  Netztransparenz market value. The last of these enters through θ rather than through a
  feature column, so the leakage test checks θ's provenance per task as well.

## How to run

Set up once:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Kill test (already run; results are in `results/`):

```bash
.venv/bin/python src/ingest_smard.py
```

```bash
.venv/bin/python src/build_panel.py
```

```bash
.venv/bin/python src/kill_test.py
```

```bash
.venv/bin/python src/check_da_vs_id.py
```

```bash
.venv/bin/python src/redispatch_control.py
```

```bash
.venv/bin/python src/make_figures.py
```

Phase 2 — semi-synthetic benchmark (E1):

```bash
.venv/bin/python -m src.censoring.run_synthetic --smoke
```

```bash
.venv/bin/python -m src.censoring.run_synthetic
```

Tests:

```bash
.venv/bin/python -m pytest tests -q
```

## Missing

- `srh-guidelines/` lacks the original `.docx` files (Alen Reji's sample proposal and the
  "Simple template"); they are still in the claude.ai Project. The three `.rtf` files are
  included as plain-text extracts.
