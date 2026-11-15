# Start here

A guide to this repository for a reader who has not seen it before. It gives no thesis
argument. Every result below is copied from the results note it names. Where a note and
this guide disagree, the note is right.

Student: Gagan Ganesh, MSc AI/ML (Big Data), SRH Hochschule Berlin.

## 1. The problem, in everyday words

German wind farms are paid a market premium on top of the electricity price. When the
day-ahead price falls below zero, the law (§51 EEG) stops that premium for many farms,
so some of them switch off even though the wind is blowing. This is curtailment for
market reasons, not because the grid is full.

What the data records is what the farms produced, not what they *could* have produced.
In a negative-price quarter-hour, a low output can mean little wind or a switched-off
farm, and the published data cannot tell these apart. The output is *censored*: we see
the lower of "available power" and "what the farm chose to deliver".

The thesis asks two things:

- How much power was held back at negative prices?
- What can public, fleet-level data actually reveal about how different groups of farms
  respond to the price?

All of this is measured against pre-registered tests. Each test's rules were committed
to git before its numbers existed.

## 2. Folder map

| Folder or file | What it holds |
|---|---|
| `README.md` | short entry point; points here |
| `docs/` | specs, pre-registrations, results notes (index in §4); `docs/legal/` and `docs/literature/` hold PDFs cited by path from `src/` |
| `src/` | all analysis code; every number in a note is written by a script here |
| `tests/` | pytest suite; `tests/test_reported_numbers.py` re-derives every figure quoted in a results note |
| `results/` | committed result tables from the early phases (kill test, E1, T-B) |
| `artifacts/` | committed result tables from Phases P and Q, one subfolder per step |
| `figures/` | committed figures; `figures/findings/` are the summary figures F1–F8 |
| `data/` | raw downloads and processed panels; only `data/reference/` is in git |
| `demo/` | `run_demo.sh` (live walk-through) and `run_full_suite.sh` |
| `tools/` | `export_share.sh`, which builds the folder shared with the supervisor |
| `literature/` | the papers, renamed `Author_Year_Short-Title.pdf`; not in git (copyright); map in `docs/S3_literature_map.md` |
| `03_legal_texts/`, `04_data_downloads/` | statute PDFs and original downloads; not in git |
| `archive/` | superseded E1 generator code, kept because `src/` cites it |
| `notebooks/` | empty; exploration only |
| `CLAUDE_CODE_PROMPT.md`, `PROJECT_CONTEXT.md` | the implementation brief and background used for assisted coding sessions |

## 3. Experiment timeline

Verdicts are quoted or closely paraphrased from the results file in the same row, never strengthened.

| Phase | Date (2026) | Question | Pre-registration | Results | Verdict |
|---|---|---|---|---|---|
| Kill test (RQ1) | 28–29 Oct | Does the TSO day-ahead forecast over-predict wind at negative prices? | go/no-go rule stated in the note itself | `docs/04_rq1_killtest_note_v3.md`, `results/02_bias_by_price_band.csv` | **GO.** DE negative-quarter-hour bias −1,684.4 MW, 95% CI [−2,693.6, −806.5]; 2,059 negative QHs on 99 event-days. Not significant in TenneT. |
| E1 merged gate | 8–9 Nov | Does the method pass the pre-registered gate on the semi-synthetic benchmark? | `docs/06_pivot_mechanism_aware_censoring.md` §7 (v1.8 gate) | `docs/19_merged_gate_and_power.md`, `results/13_gate_verdict_merged.csv` | **The merged gate FAILS**, on (a) and (b); (c) passes. The merged base is 61.6% pre-MTU15, which disqualifies these numbers as an E1/E2 result. |
| T-B | 9–10 Nov | Is M2 more data-efficient than the rivals B3-CV and B6? | `docs/09_m2_preregistration.md`, Amendment 3 | `results/21_tb_primary_report_20261110.txt`, `docs/20_response_curve_bug.md`, `docs/21_report_only_verdict_bug.md` | **T-B VERDICT at n = 50: PASS**, on the corrected response curve. |
| T-B λ sensitivity | 15 Nov | Does that PASS survive a widened λ grid? | declared sensitivity, `docs/Q_STOP_R1.md` (student decision) | `docs/TB_lambda_sensitivity.md`, `artifacts/TB_lambda/` | **On the widened λ grid, T-B FAILS at n = 50**: M2 wins 15 of 45 half cells against B3-CV, p = 0.036. The committed PASS stands as the pre-registered result. 77 of 135 widened selections sit at the new grid edge; the sensitivity result is itself provisional. |
| P0 | 14–15 Nov | Is there room for a post-auction forecast correction? | `docs/P0_preregistration.md` | `docs/P_STOP_P0.md`, `artifacts/P0/p0_planning_recompute.csv` | **STOP.** Best-case RMSE reduction is below 15% in every area and on both series (DE onshore 0.100, 95% CI [0.054, 0.165]). |
| P3, incl. Arm D | 15 Nov | What can aggregate data identify about cohort responses? | `docs/P0_preregistration.md` §7; gaps filled in `docs/P3_results.md` §0 | `docs/P3_results.md`, `artifacts/P3/` | Bounds contain the truth in 1,127 of 1,127 scored cell-functionals (Arm O). Arm D: coverage 378 of 378, but widths collapse. On real data nothing is identified; the narrowest interval is 0.082. |
| R1 | 15 Nov | Do the two working copies trace to committed code? | none (reconciliation) | `docs/R1_reconciliation.md` | `real_panel.py` committed; the λ-grid edit to `m2.py` / `tb_methods.py` was left as found and raised in `docs/Q_STOP_R1.md`. |
| Q0 | 15 Nov | How noisy is each estimate of potential (the anchors)? | `docs/Q0_preregistration.md` (§1 and Amendment 1) | `artifacts/Q0/q0_anchors.csv` | Anchor H, the statutory projection: σ = 0.066, a lower bound on its error. Anchor T, the TSO day-ahead forecast: σ = 0.180. |
| Q0b | 15 Nov | Does the quality-assured projection add back market curtailment? | `docs/Q0b_preregistration.md` | `docs/Q0b_results.md`, `artifacts/Q0b/` | **ADDS BACK**, on the deciding aggregate (D = +0.2893, 95% CI [+0.2484, +0.3344]) and in every control area. |
| Q0c | 15 Nov | Does the three-area projection volume agree with Hirth v2? | `docs/Q0c_preregistration.md` | `docs/Q0c_results.md`, `artifacts/Q0c/q0c_volume.csv` | **NOT TESTABLE** at national scale: 1.644 TWh, interval [1.162, 2.200], against Hirth's 2.5 TWh. No agreement is claimed. |
| Q1 | 15 Nov | At what noise level does the fleet response stop being informative? | `docs/Q0_preregistration.md` §3 | `docs/Q1_results.md`, `artifacts/Q1/` | **σ\* ≥ 0.35, censored at the top of the pre-registered grid**: a lower bound, not a value. Coverage of the known truth is 100% at all levels. |
| Q5 | 15 Nov | With the projection as the potential, which real-data quantities become informative? | `docs/Q5_preregistration.md` | `docs/Q5_results.md`, `artifacts/Q5/` | **2 of 59 main-setting functional-months, 3.4%, become informative** when `H` replaces `F`; 5 go the other way. |
| Q6a | 15 Nov | Is the real-data floor day-to-day behavioural heterogeneity? | `docs/Q6_preregistration.md` | `docs/Q6_results.md`, `artifacts/Q6/q6a_cells.csv` | **PRESENT.** In all 8 testable cells the between-day variance exceeds what Anchor H's σ = 0.066 produces alone. |
| Q6b | 15 Nov | Can a synthetic day effect reproduce the real-data signatures? | `docs/Q6_preregistration.md` | `docs/Q6_results.md`, `artifacts/Q6/q6b_summary.csv` | **NOT SUPPORTED.** No σ_r meets either signature. |

TenneT is excluded from every DE-wide projection aggregate (Q0b, Q0c, Q5, Q6), following
the supervisor minute T-D(vii). See `docs/Q_STOP_Q0c.md`.

## 4. Docs index

Labels: **pre-registration** (rules committed before the numbers), **results note**
(reports numbers, including STOP, audit and bug notes), **spec** (design and decisions),
**superseded** (kept unchanged, replaced by a later file), **reference** (background
tables).

| File | Label | One line |
|---|---|---|
| `00_START_HERE.md` | reference | this guide |
| `01_thesis_brief.md` | spec | working thesis brief (v2) |
| `01_thesis_brief_v1_forecast-correction.md` | superseded | original forecast-correction plan |
| `02_evidence_base.md` | reference | literature and current affairs, 28 Oct |
| `03_data_sources.md` | reference | data sources and endpoints |
| `04_rq1_killtest_note.md` | superseded | kill test v2 (replaced by v3) |
| `04_rq1_killtest_note_v3.md` | results note | kill test v3, verdict GO |
| `05_eeg_rule_table.md` | reference | §51 EEG negative-price rules in plain English |
| `06_pivot_mechanism_aware_censoring.md` | spec | the main spec (v1.9); its §7 holds the E1 gate |
| `07_literature_table.md` | reference | literature table in SRH format |
| `08_test2_preregistration.md` | pre-registration | Test 2, real-data preview, with Amendment 1 |
| `09_m2_preregistration.md` | pre-registration | M2 model and the T-B / T-D / T-E tests, with amendments |
| `10_m2_verdict.md` | results note | M2 verdict template; status OPEN, T-B section never filled (T-B result is in `results/21_tb_primary_report_20261110.txt`) |
| `11_e1_identification_audit.md` | results note | audit of the E1 generator against `synthetic.py` |
| `12_identification_fix.md` | results note | identification fix: statute, rank, merge, window |
| `13_theta_audit.md` | results note | market-value series and tier-1 identification |
| `14_mv_coverage_fix.md` | results note | market-value coverage gap and its fix |
| `15_tb_restart.md` | results note | why T-B stopped and whether it could resume |
| `16_e1_generator_design.md` | superseded | design of the old E1 generator |
| `17_e1_first_run_report.md` | results note | first E1 run on the real panel (old generator) |
| `18_fallback_decision.md` | spec | student decision on fallback structure and drop trigger |
| `19_merged_gate_and_power.md` | results note | E1 merged gate verdict and power diagnostic |
| `20_response_curve_bug.md` | results note | scoring bug found after the first T-B verdict |
| `21_report_only_verdict_bug.md` | results note | `--report-only` printed FAIL on a PASS |
| `P0_preregistration.md` | pre-registration | Phase P (P1–P5 and P3 programme) |
| `P_STOP_P0.md` | results note | Phase P stopped after P0: headroom below 15% |
| `P3_results.md` | results note | partial identification, Arms O and D, real data |
| `Q0_preregistration.md` | pre-registration | Phase Q anchors and noise dial, with Amendment 1 |
| `Q0b_preregistration.md` | pre-registration | does Anchor H add back market curtailment |
| `Q0b_results.md` | results note | ADDS BACK |
| `Q0c_preregistration.md` | pre-registration | volume against Hirth v2; cites `Literature Review/2609.10053v2.pdf`, now `literature/01_closest_work/Hirth_2026_Curtail-at-negative-prices_arXiv-v2.pdf` |
| `Q0c_results.md` | results note | NOT TESTABLE |
| `Q1_results.md` | results note | variance dial, σ\* ≥ 0.35 |
| `Q5_preregistration.md` | pre-registration | real-data bounds with the projection |
| `Q5_results.md` | results note | 2 of 59 become informative |
| `Q6_preregistration.md` | pre-registration | real-data floor as heterogeneity (Q6a, Q6b) |
| `Q6_results.md` | results note | Q6a PRESENT, Q6b NOT SUPPORTED |
| `Q_STOP_Q0c.md` | results note | DE-wide volume vs the TenneT precondition |
| `Q_STOP_R1.md` | results note | λ-grid change against a frozen pre-registration; closed by student decision |
| `R1_reconciliation.md` | results note | reconciling the two working copies |
| `S3_literature_map.md` | reference | old → new literature paths |
| `TB_lambda_sensitivity.md` | results note | T-B on the widened λ grid: FAILS (sensitivity) |

## 5. How to run things

Set up once:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Live demo: every step prints a one-line header and writes only to `demo/output/`.

```bash
bash demo/run_demo.sh
```

Full test suite:

```bash
bash demo/run_full_suite.sh
```

<!-- numbers-check: skip -->
Measured step times on the student's laptop are recorded in §5.1 when the demo is run (Phase S6).
<!-- /numbers-check -->

### Rebuild the data from scratch

`data/` is not in git, except `data/reference/`. To rebuild it:

1. **SMARD** (prices, forecasts, actuals). Download with `.venv/bin/python src/ingest_smard.py`,
   then build the quarter-hour panel with `.venv/bin/python src/build_panel.py`. The panel
   spans 2024-01-01 to 2026-10-28. The kill-test window starts 2025-10-01; `demo/run_demo.sh`
   step 2 applies that filter.
2. **Netztransparenz** (redispatch, Online-Hochrechnung, market values). Manual CSV
   downloads into `data/raw/netztransparenz/`, under the file names the notes cite. The
   quality-assured projection's sha256 is checked by `tests/test_reported_numbers.py`.
3. **MaStR** (unit register): `.venv/bin/python src/ingest_mastr.py --download`, written to
   `data/raw/mastr/<date>/`.
4. **BNetzA** award statistics: manual download to `data/raw/bnetza/`, read by
   `src/ingest_award_values.py`.

Then run each phase's runner, named at the top of its results note. The runners write to
`results/` or `artifacts/`; re-running one overwrites the committed numbers it produced.

## 6. Glossary

| Term | Meaning here |
|---|---|
| curtailment | a wind farm producing less than the wind allows, on purpose |
| market curtailment | curtailment chosen by the operator because the price is too low |
| redispatch | curtailment ordered by a grid operator to relieve a congested line; not a market decision |
| market premium | the top-up a farm receives above the market price under the EEG |
| §51 EEG | the rule that suspends the market premium during negative prices; its details differ by commissioning year |
| quarter-hour (QH) | the 15-minute interval in which German day-ahead prices and SMARD data are reported |
| negative QH | a quarter-hour with a day-ahead price below zero |
| event-day | a Berlin calendar day with at least one negative QH; the unit of the bootstrap |
| control area | one of the four German TSO zones: 50Hertz, Amprion, TenneT, TransnetBW |
| potential | the power the fleet could have produced with no curtailment; never observed directly |
| Online-Hochrechnung | the TSOs' published estimate of wind feed-in (projection `H`), which includes curtailed output |
| day-ahead forecast | the TSOs' wind forecast published the day before (`F`) |
| censoring | seeing the minimum of potential and the chosen output, not potential itself |
| cohort | a group of turbines that face the same §51 rule and price threshold |
| response | the share of a cohort's potential that it switches off at a given price |
| identified set | the range of response values that all fit the data; when it is a single point, the response is identified |
| coverage | how often an identified set or interval contains the known true value on synthetic data |
| informative | an identified set narrow enough to say something, by the threshold fixed in `docs/Q0_preregistration.md` §5 |
| pre-registration | a file committing the test, data window and pass rule to git before any result exists |
| semi-synthetic benchmark | real prices and fleet structure with simulated curtailment, so the truth is known |
