# MSc Thesis — Price-Driven Wind Curtailment Forecasting (Germany)

Gagan Ganesh, MSc AI/ML (Big Data), SRH Hochschule Berlin. Nov 2026 – Apr 2027.

## Layout

```
msc-thesis-wind-curtailment/
├── README.md
├── docs/                  thesis working documents (source of truth: 01_thesis_brief.md)
│   ├── 01_thesis_brief.md
│   ├── 02_evidence_base.md
│   ├── 03_data_sources.md
│   └── 04_rq1_killtest_note.md
├── srh-guidelines/        SRH / supervisor rules, templates, slides (read-only reference)
├── data/
│   ├── raw/               untouched downloads (SMARD, ENTSO-E, MaStR snapshot, Netztransparenz)
│   └── processed/         cleaned Parquet, UTC timestamps
├── src/                   ingestion, kill test, features, models
├── notebooks/             exploration only; anything reused moves to src/
└── figures/               plots for the thesis
```

## Conventions

- Data in Parquet, all timestamps UTC; Berlin-local only for event-day grouping.
- `data/` is not committed to git; record download date and source for every raw file.
- Rolling-origin splits, event-day blocks for CV and bootstrap, no shuffling.

## Status

- **RQ1 kill test rebuilt (29 Oct 2026).** `src/` now holds the full pipeline; results in
  `results/`, figures in `figures/`, write-up in `docs/04_rq1_killtest_note_v3.md`
  (v2 kept unchanged at `docs/04_rq1_killtest_note.md`). Verdict: **GO**.
- **One step is blocked.** Check 2 (redispatch control) needs the Netztransparenz
  redispatch export, which requires OAuth client credentials or a browser download.
  `src/redispatch_control.py` is written and exits 2 until a CSV is placed in
  `data/raw/netztransparenz/`. See §4 of the v3 note.

## Missing
- `srh-guidelines/` lacks the original `.docx` files (Alen Reji's sample proposal and the
  "Simple template"); they are still in the claude.ai Project. The three `.rtf` files are
  included as plain-text extracts.
