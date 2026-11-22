# Start here

**What this is.** When the German day-ahead price turns negative, many wind farms lose their
market premium (§51 EEG) and some switch off. Public data show what the fleet produced, not what
it could have produced. This repository asks which conclusions about that switch-off can be
supported from public aggregated data, and how much bias in the estimate of available power
each conclusion survives.

**One method:** rule-structured, bias-robust partial identification, with the quality-assured
Online-Hochrechnung (H) as the estimate of available power. Every test was pre-registered
before its numbers existed; the pre-registrations are in `archive/docs/`, cited by commit.

## Reading order

| doc | content |
|---|---|
| `01_objective.md` | objective, research question, the three sub-questions |
| `02_method.md` | the method in six steps |
| `03_available_power_estimate.md` | how good and how biased H is |
| `04_exp1_known_truth_validation.md` | coverage and width where the truth is known |
| `05_exp2_bias_robustness_validation.md` | what bias does, and the bias-robust set |
| `06_exp3_german_application.md` | the German results table |
| `06b_policy_use_and_data_requirement.md` | what each quantity answers, and the accuracy it needs |
| `07_limitations_and_future_work.md` | limits and next steps |
| `archive_mapping.md` | every old file → new path |

Motivation figures: `figures/01_motivation_event_day.png`, `02_motivation_forecast_bias_by_band.png`
(from the archived forecast-bias check).

## Folder map

| folder | content |
|---|---|
| `src/method/` | the method: exposure, bounds, functionals, bias-robust set, data loaders, stage A |
| `src/experiments/` | thin runners for experiments 1–3 and the available-power section, their summarisers, the doc tables |
| `src/figures.py` | figures 01–09 and 13 |
| `artifacts/` | one folder per experiment, `available_power_estimate/`, and `method_inputs/` (θ and exposure inputs) |
| `figures/` | figures 01–09 and 13 with data CSV and caption |
| `tests/` | active tests and the number checker for these docs |
| `archive/` | everything else, unchanged and still verified (`archive/README.md`) |
| `docs/sources/` | statute and literature PDFs cited by the code, the §51 rule table, the data-source sheet |

## How to run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/python -m src.experiments.exp3_german_application
```

Each `src.experiments.exp*` runner re-derives its summaries from the committed cell-level
artifacts and reproduces them byte for byte; `--fits` prints the long-fit commands instead.

```bash
bash demo/run_demo.sh
```

```bash
bash demo/run_full_suite.sh
```

Rebuilding the data from scratch: SMARD with `src/method/ingest_smard.py` and
`src/method/build_panel.py`; Netztransparenz projection, redispatch and market values are manual
downloads into `data/raw/netztransparenz/` (`docs/sources/data_sources.md`); MaStR with
`src/method/ingest_mastr.py --download`; BNetzA award statistics into `data/raw/bnetza/`.

<!-- numbers-check: skip -->
`demo/run_demo.sh`, measured on the student's laptop on 16 Nov 2026 (wall clock, whole seconds):

| step | shows | time |
|---|---|---|
| 1 | environment and commit | 1 s |
| 2 | experiment 1: one synthetic cell, true value, interval and coverage per functional | 5 s |
| 3 | experiment 2: one cell with its potential biased by −0.047, plain set vs bias-robust set at B = 0.05 | 9 s |
| 4 | experiment 3: the German results table, rebuilt from the artifacts | 1 s |
| 5 | the number checker, active docs and archived notes | 6 s |
| 6 | figures 01–09 and 13 regenerated into `demo/output/figures/` | 3 s |
| full suite | `bash demo/run_full_suite.sh` | about 35 s |

The demo writes only to `demo/output/` and stops with an error if anything under `artifacts/`
or `figures/` changed.
<!-- /numbers-check -->
