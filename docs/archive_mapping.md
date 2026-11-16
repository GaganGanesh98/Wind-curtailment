# Archive mapping

Approved by the student on 16 November 2026 with every proposal below accepted. Classified
against commit `25b3885` (after K1 was committed so that it could be archived untouched).

**Decisions recorded:** F-1/F-2 (a) — the stage-A modules stay active as `src/method/stage_a/`;
F-3 to F-5 — kept under plain names; F-6 — the two M1-metric tests move to `archive/tests/`;
F-7 — the number checker is split, both halves collected by the suite; F-8 — the uncommitted
λ-grid edit moves with its files and stays uncommitted; F-9 — K1 committed (`25b3885`), then
archived with K0; F-10 — superseded: import lines are rewritten mechanically wherever a module
moves, so archived code keeps importing; figure 08 is a re-plot of existing artifacts.
**One change from the draft:** data loaders sit flat in `src/method/` rather than in a
`data/` subfolder.

**Method:** rule-structured, bias-robust partial identification, with the quality-assured
Online-Hochrechnung (H) as the estimate of available power.

| New name | Built from |
|---|---|
| Available-power estimate (data) | Q0, Q0b |
| Experiment 1 — Known-truth validation | P3 Arm O, P3 Arm D, Q1 |
| Experiment 2 — Bias-robustness validation | Q2, V0, V1 |
| Experiment 3 — German application | V2, Q5 (H rows), the C1 table |

## 1. Dependency map (measured by an import scan of every `.py` file)

Modules reachable from the kept entry points, and the files they read:

| part | modules (current path) | artifacts / results read | raw data read |
|---|---|---|---|
| shared method | `censoring/cohorts.py`, `censoring/identification.py`, `censoring/synthetic.py`, `censoring/window.py`, `identification/bounds.py`, `identification/functionals.py`, `identification/summarise_p3.py`, `identification/lambda5_truth.py` | `results/30_mastr_cohort_shares.csv` (exposure.py) | — |
| θ on the real panel | `censoring/run_identification.py` (`_real_panel_theta`), `check_rule18_real.py`, `compute_theta_inputs.py`, `ingest_market_values.py`, `ingest_mastr.py`, `ingest_award_values.py` | `results/30`, `31`, `32`, `33`, `35`, `38` | MaStR, BNetzA awards, Netztransparenz market values, panel |
| available-power estimate | `potential/q0b_validate_h.py`, `potential/anchors.py`, `check_nr51_compliance.py` (projection + redispatch reader), `redispatch_control.py`, `postauction/common.py`, `smard_config.py`, `stats_boot.py` | `artifacts/Q0/`, `artifacts/Q0b/`, `results/34`, `36`, `39` | quality-assured and operational H, redispatch export, panel |
| Experiment 1 | `identification/run_p3_synthetic.py`, `identification/run_q_dial.py`, `identification/summarise_q1.py` + shared | `artifacts/P3/p3_synthetic_arm_{o,d}*`, `artifacts/Q1/` | — |
| Experiment 2 | `identification/run_q_dial.py`, `identification/summarise_q2.py`, `identification/run_v_bias_robust.py`, `identification/summarise_v.py` + shared | `artifacts/Q2/`, `artifacts/V/v1_*` | — |
| Experiment 3 | `identification/run_p3_real.py`, `identification/run_q5.py`, `identification/summarise_q5.py`, `identification/run_v_bias_robust.py`, `identification/summarise_v.py`, `build_conclusions_table.py` + θ + available-power | `artifacts/Q5/`, `artifacts/V/v2_*`, `results/C1_conclusions_table.csv` | panel, H, redispatch |
| figures | `make_findings_figures.py` | the above, plus `results/01_sample_size.csv`, `02_bias_by_price_band.csv`, `02_worst_days_de.csv` (kill test, for the two motivation figures) | panel |

### Flags — kept code that currently reaches into a module the brief would archive

| # | flag | where | proposal |
|---|---|---|---|
| F-1 | `cohort_runlength_hours` comes from `censoring/model.py`, the M1 (PyTorch) model module | `run_p3_synthetic.py:35` | keep a plain module for it. Either `git mv censoring/model.py → src/method/runlength.py` unchanged (keeps torch in the active tree), or copy the one function into `src/method/exposure.py` (a code edit). **Your call.** |
| F-2 | **Arm D's estimated potential (stage A) is fitted by `fit_shared_stage_a` in `censoring/m2.py`**, which needs `baselines.py` and `model.py` (PyTorch) | `run_p3_synthetic.py:92` (lazy import, Arm D only) | Step 2 only re-runs summarisers, so no fit is needed to reproduce Arm D. But rule 3 forbids an import into `archive/`. Options: (a) keep `m2.py`, `baselines.py`, `model.py` active as `src/method/stage_a/` (M2 code stays in the active tree); (b) archive them and delete the Arm D refit path from the active runner, so Arm D is reproducible only from its stored artifact. **Your call; I lean to (a).** |
| F-3 | `postauction/common.py` (bands, window loader, day bootstrap) is needed by the projection loader and the Q0 anchors | `q0b_validate_h.py:31`, `anchors.py:67` | keep as `src/method/day_bootstrap.py`; archive the rest of `postauction/` |
| F-4 | `redispatch_control.py` (kill-test check 2) supplies `find_input`, `parse_measures` to the redispatch reader | `check_nr51_compliance.py:134` | keep as `src/method/redispatch_reader.py` |
| F-5 | `censoring/run_identification.py` supplies `_real_panel_theta` and also holds E1-gate code | `run_p3_real.py:36` | keep whole as `src/method/real_theta.py` (no code edits) |
| F-6 | `tests/test_identification.py` has two tests importing `censoring/metrics.py` (M1) | lines 257, 275 | split those two tests into `archive/tests/` |
| F-7 | `tests/test_reported_numbers.py` checks archived docs with archived code (K0 facts need `k_bridge_data.py`; T-B, P0, Q0c, Q6 checks read archived artifacts) | — | **split:** `tests/test_reported_numbers.py` for active docs; `archive/tests/test_archived_numbers.py` for archived ones, still collected by the suite (pytest `testpaths = tests archive/tests`), zero-row guard on in both |
| F-8 | the **uncommitted λ-grid edit** lives in `censoring/m2.py` and `tb_methods.py`; `tb_lambda_widening.py` is untracked | working tree | `git mv` carries the edit along; `tools/export_share.sh`'s known-dirty list needs the new paths. Or commit or move the edit first. **Your call.** |
| F-9 | **Phase K's K1 work is uncommitted** (`artifacts/K1/`, `docs/K_results.md`, `src/potential/k_bridge.py`, K1 checks in `tests/test_reported_numbers.py`). K1 ran to completion and FAILED its gate (coverage 0.740, median half-width 0.189); its commit was interrupted | working tree | to archive "untouched": commit K1 as it stands, then `git mv` it with K0 into `archive/`. The alternative (moving it out uncommitted) loses it from git. **Your call.** |
| F-10 | Archived scripts import modules that move (for example `kill_test.py` imports `smard_config`) | archive | archived code is not run; its imports will point at old paths. Proposal: leave it as written, and say so in `archive/README.md` |

## 2. Proposed active structure

```
README.md
docs/
  00_start_here.md  01_objective.md  02_method.md  03_available_power_estimate.md
  04_exp1_known_truth_validation.md  05_exp2_bias_robustness_validation.md
  06_exp3_german_application.md  07_limitations_and_future_work.md  archive_mapping.md
  sources/   legal/ and literature/ PDFs cited by path from src, eeg_rule_table.md, data_sources.md
src/method/            exposure, collinearity, synthetic, window, bounds, functionals,
                       synthetic_scoring, potential_error, bias_robust, bias_robust_summary,
                       lambda5_truth, read_results, day_bootstrap, event_day_bootstrap,
                       stage_a/ (latent_model, reservation_depth_model, baselines)
src/method/       real_panel, real_theta, cohort_parameters, theta_inputs, ingest_*,
                       build_panel, smard_config, projection_and_redispatch,
                       redispatch_reader, available_power, validate_market_values
src/experiments/       exp1_known_truth_validation.py, exp2_bias_robustness_validation.py,
                       exp3_german_application.py (new thin runners) + their summary
                       components (exp1_noise_dial_summary, exp2_bias_dial_summary,
                       exp3_real_bounds, exp3_real_bounds_summary, exp3_results_table,
                       available_power_anchors)
src/figures.py
artifacts/available_power_estimate/  exp1_known_truth_validation/
          exp2_bias_robustness_validation/  exp3_german_application/  method_inputs/
figures/  01_… to 09_… (below)
tests/    demo/run_demo.sh  demo/run_full_suite.sh  tools/export_share.sh
archive/  everything else, internal layout kept (archive/src/…, archive/docs/…, archive/results/…)
```

`artifacts/method_inputs/` is new. It holds the θ and exposure inputs now in `results/30`–`38`, which the method reads and writes.

## 3. Figures

| new name | from | note |
|---|---|---|
| `01_motivation_event_day` | F1 | introduction only; reads `archive/results/02_worst_days_de.csv` |
| `02_motivation_forecast_bias_by_band` | F2 | introduction only; reads `archive/results/01_*`, `02_*` |
| `03_available_power_gap_by_band` | F3 | available-power estimate |
| `04_exp1_coverage` | F4, split | only P3 Arm O, P3 Arm D and the Q1 levels; the Q6b rows are dropped |
| `05_exp1_exact_vs_estimated_potential` | F5 | |
| `06_exp1_noise_dial` | F6 | |
| `07_exp1_width_vs_noise` | F9 | |
| `08_exp2_coverage_under_bias` | **new plot of existing artifacts** | Q2 level coverage and V1 coverage by (B, b*). F4 has no bias part today; this comes from `artifacts/Q2/q2_coverage_by_level.csv` and `artifacts/V/v1_coverage.csv`. Confirm this counts as a re-plot, not new data |
| `09_exp3_bias_breakdown` | F10 | |
| archived | F7, F8 | as the brief says |

## 4. Counts

331 tracked files at `25b3885` in `src/`, `docs/`, `results/`, `artifacts/`, `figures/`, `tests/`,
`demo/`, `tools/`, `archive/`: **108 KEEP (renamed), 19 KEEP-AS-COMPONENT, 204 ARCHIVE.**
Not counted: the untracked `tb_lambda_widening.py` (F-8) and the git-excluded `literature/`
folder, which stays where it is. New files added by the restructure (runners, `__init__.py`,
new docs) are not in the table.

## 5. Full mapping table (every tracked file at `25b3885`)

| old path | class | new path | note |
|---|---|---|---|
| `archive/e1_generator.py` | ARCHIVE | `archive/src/e1_generator.py` | already archived |
| `archive/e1_validate.py` | ARCHIVE | `archive/src/e1_validate.py` | already archived |
| `artifacts/K1/k1_covariance.csv` | ARCHIVE | `archive/artifacts/K1/k1_covariance.csv` |  |
| `artifacts/K1/k1_diagnostics.csv` | ARCHIVE | `archive/artifacts/K1/k1_diagnostics.csv` |  |
| `artifacts/K1/k1_masked_qh.csv` | ARCHIVE | `archive/artifacts/K1/k1_masked_qh.csv` |  |
| `artifacts/K1/k1_summary.csv` | ARCHIVE | `archive/artifacts/K1/k1_summary.csv` |  |
| `artifacts/K1/k1_verdict.csv` | ARCHIVE | `archive/artifacts/K1/k1_verdict.csv` |  |
| `artifacts/K1/k1_windows.csv` | ARCHIVE | `archive/artifacts/K1/k1_windows.csv` |  |
| `artifacts/P0/p0_counts_by_month.csv` | ARCHIVE | `archive/artifacts/P0/p0_counts_by_month.csv` |  |
| `artifacts/P0/p0_event_day_counts.csv` | ARCHIVE | `archive/artifacts/P0/p0_event_day_counts.csv` |  |
| `artifacts/P0/p0_largest_error_days.csv` | ARCHIVE | `archive/artifacts/P0/p0_largest_error_days.csv` |  |
| `artifacts/P0/p0_planning_recompute.csv` | ARCHIVE | `archive/artifacts/P0/p0_planning_recompute.csv` |  |
| `artifacts/P3/p3_real.csv` | ARCHIVE | `archive/artifacts/P3/p3_real.csv` | P3 real data uses F; exp3 uses H |
| `artifacts/P3/p3_real_summary.csv` | ARCHIVE | `archive/artifacts/P3/p3_real_summary.csv` | P3 real data uses F; exp3 uses H |
| `artifacts/P3/p3_synthetic_arm_d.csv` | KEEP | `artifacts/exp1_known_truth_validation/estimated_potential_cells.csv` |  |
| `artifacts/P3/p3_synthetic_arm_d_summary.csv` | KEEP | `artifacts/exp1_known_truth_validation/estimated_potential_cells_summary.csv` |  |
| `artifacts/P3/p3_synthetic_arm_o.csv` | KEEP | `artifacts/exp1_known_truth_validation/exact_potential_cells.csv` |  |
| `artifacts/P3/p3_synthetic_arm_o_summary.csv` | KEEP | `artifacts/exp1_known_truth_validation/exact_potential_cells_summary.csv` |  |
| `artifacts/Q0/q0_anchors.csv` | KEEP | `artifacts/available_power_estimate/error_anchors.csv` |  |
| `artifacts/Q0b/q0b_gap_shares.csv` | KEEP | `artifacts/available_power_estimate/gap_shares.csv` |  |
| `artifacts/Q0b/q0b_h_agreement.csv` | KEEP | `artifacts/available_power_estimate/agreement_at_positive_prices.csv` |  |
| `artifacts/Q0b/q0b_verdicts.csv` | KEEP | `artifacts/available_power_estimate/adds_back_verdicts.csv` |  |
| `artifacts/Q0c/q0c_volume.csv` | ARCHIVE | `archive/artifacts/Q0c/q0c_volume.csv` |  |
| `artifacts/Q1/q1_headline.csv` | KEEP | `artifacts/exp1_known_truth_validation/noise_dial_headline.csv` |  |
| `artifacts/Q1/q1_summary_by_level.csv` | KEEP | `artifacts/exp1_known_truth_validation/noise_dial_summary.csv` |  |
| `artifacts/Q1/q1_variance_dial.csv` | KEEP | `artifacts/exp1_known_truth_validation/noise_dial_cells.csv` |  |
| `artifacts/Q2/q2_coverage_by_level.csv` | KEEP | `artifacts/exp2_bias_robustness_validation/bias_dial_coverage.csv` |  |
| `artifacts/Q2/q2_summary_by_level.csv` | KEEP | `artifacts/exp2_bias_robustness_validation/bias_dial_summary.csv` |  |
| `artifacts/Q2/q2a_bias_dial.csv` | KEEP | `artifacts/exp2_bias_robustness_validation/bias_dial_cells.csv` |  |
| `artifacts/Q2/q2b_crossed.csv` | KEEP | `artifacts/exp2_bias_robustness_validation/bias_noise_crossed_cells.csv` |  |
| `artifacts/Q5/q5_real.csv` | KEEP | `artifacts/exp3_german_application/monthly_bounds_cells.csv` | F and H rows; exp3 reports H |
| `artifacts/Q5/q5_summary.csv` | KEEP | `artifacts/exp3_german_application/monthly_bounds_summary.csv` | F and H rows; exp3 reports H |
| `artifacts/Q6/q6a_cells.csv` | ARCHIVE | `archive/artifacts/Q6/q6a_cells.csv` |  |
| `artifacts/Q6/q6b_day_effect.csv` | ARCHIVE | `archive/artifacts/Q6/q6b_day_effect.csv` |  |
| `artifacts/Q6/q6b_summary.csv` | ARCHIVE | `archive/artifacts/Q6/q6b_summary.csv` |  |
| `artifacts/R1/lambda_grid_widening_uncommitted.patch` | ARCHIVE | `archive/artifacts/R1/lambda_grid_widening_uncommitted.patch` |  |
| `artifacts/R1/superseded_main_worktree_20261110/00_data_quality.csv` | ARCHIVE | `archive/artifacts/R1/superseded_main_worktree_20261110/00_data_quality.csv` |  |
| `artifacts/R1/superseded_main_worktree_20261110/00_dst_check.csv` | ARCHIVE | `archive/artifacts/R1/superseded_main_worktree_20261110/00_dst_check.csv` |  |
| `artifacts/R1/superseded_main_worktree_20261110/01_sample_size.csv` | ARCHIVE | `archive/artifacts/R1/superseded_main_worktree_20261110/01_sample_size.csv` |  |
| `artifacts/R1/superseded_main_worktree_20261110/02_bias_by_price_band.csv` | ARCHIVE | `archive/artifacts/R1/superseded_main_worktree_20261110/02_bias_by_price_band.csv` |  |
| `artifacts/R1/superseded_main_worktree_20261110/02_overall_negative_qh_bias.csv` | ARCHIVE | `archive/artifacts/R1/superseded_main_worktree_20261110/02_overall_negative_qh_bias.csv` |  |
| `artifacts/R1/superseded_main_worktree_20261110/02_robustness_de.csv` | ARCHIVE | `archive/artifacts/R1/superseded_main_worktree_20261110/02_robustness_de.csv` |  |
| `artifacts/R1/superseded_main_worktree_20261110/02_worst_days_de.csv` | ARCHIVE | `archive/artifacts/R1/superseded_main_worktree_20261110/02_worst_days_de.csv` |  |
| `artifacts/R1/superseded_main_worktree_20261110/21_tb_primary_report_20261110.txt` | ARCHIVE | `archive/artifacts/R1/superseded_main_worktree_20261110/21_tb_primary_report_20261110.txt` |  |
| `artifacts/R1/superseded_main_worktree_20261110/diff_vs_committed.patch` | ARCHIVE | `archive/artifacts/R1/superseded_main_worktree_20261110/diff_vs_committed.patch` |  |
| `artifacts/R1/test_real_panel.py.handover.txt` | ARCHIVE | `archive/artifacts/R1/test_real_panel.py.handover.txt` |  |
| `artifacts/TB_lambda/41_tb_lambda_widening.csv` | ARCHIVE | `archive/artifacts/TB_lambda/41_tb_lambda_widening.csv` |  |
| `artifacts/TB_lambda/42_tb_primary_widened_lambda.csv` | ARCHIVE | `archive/artifacts/TB_lambda/42_tb_primary_widened_lambda.csv` |  |
| `artifacts/TB_lambda/42_verdict_report.txt` | ARCHIVE | `archive/artifacts/TB_lambda/42_verdict_report.txt` |  |
| `artifacts/TB_lambda/tb_lambda_widening.py.txt` | ARCHIVE | `archive/artifacts/TB_lambda/tb_lambda_widening.py.txt` |  |
| `artifacts/TB_lambda/widened_grid.diff` | ARCHIVE | `archive/artifacts/TB_lambda/widened_grid.diff` |  |
| `artifacts/V/v1_by_functional.csv` | KEEP | `artifacts/exp2_bias_robustness_validation/bias_robust_by_functional.csv` |  |
| `artifacts/V/v1_coverage.csv` | KEEP | `artifacts/exp2_bias_robustness_validation/bias_robust_coverage.csv` |  |
| `artifacts/V/v1_raw_shard0of4.csv` | KEEP | `artifacts/exp2_bias_robustness_validation/bias_robust_cells_shard0of4.csv` |  |
| `artifacts/V/v1_raw_shard1of4.csv` | KEEP | `artifacts/exp2_bias_robustness_validation/bias_robust_cells_shard1of4.csv` |  |
| `artifacts/V/v1_raw_shard2of4.csv` | KEEP | `artifacts/exp2_bias_robustness_validation/bias_robust_cells_shard2of4.csv` |  |
| `artifacts/V/v1_raw_shard3of4.csv` | KEEP | `artifacts/exp2_bias_robustness_validation/bias_robust_cells_shard3of4.csv` |  |
| `artifacts/V/v1_width_cost.csv` | KEEP | `artifacts/exp2_bias_robustness_validation/bias_robust_width_cost.csv` |  |
| `artifacts/V/v2_breakdown.csv` | KEEP | `artifacts/exp3_german_application/breakdown_points.csv` |  |
| `artifacts/V/v2_real_raw.csv` | KEEP | `artifacts/exp3_german_application/bias_robust_full_window_cells.csv` |  |
| `artifacts/V/v2_robust_intervals.csv` | KEEP | `artifacts/exp3_german_application/bias_robust_full_window_intervals.csv` |  |
| `demo/run_demo.sh` | KEEP | `demo/run_demo.sh` | rewritten in Step 6 |
| `demo/run_full_suite.sh` | KEEP | `demo/run_full_suite.sh` |  |
| `docs/00_OBJECTIVE.md` | ARCHIVE | `archive/docs/00_OBJECTIVE.md` | pre-registrations and results notes, unchanged |
| `docs/00_START_HERE.md` | ARCHIVE | `archive/docs/00_START_HERE.md` | pre-registrations and results notes, unchanged |
| `docs/01_thesis_brief.md` | ARCHIVE | `archive/docs/01_thesis_brief.md` | pre-registrations and results notes, unchanged |
| `docs/01_thesis_brief_v1_forecast-correction.md` | ARCHIVE | `archive/docs/01_thesis_brief_v1_forecast-correction.md` | pre-registrations and results notes, unchanged |
| `docs/02_evidence_base.md` | ARCHIVE | `archive/docs/02_evidence_base.md` | pre-registrations and results notes, unchanged |
| `docs/03_data_sources.md` | KEEP | `docs/sources/data_sources.md` | reference |
| `docs/04_rq1_killtest_note.md` | ARCHIVE | `archive/docs/04_rq1_killtest_note.md` | pre-registrations and results notes, unchanged |
| `docs/04_rq1_killtest_note_v3.md` | ARCHIVE | `archive/docs/04_rq1_killtest_note_v3.md` | pre-registrations and results notes, unchanged |
| `docs/05_eeg_rule_table.md` | KEEP | `docs/sources/eeg_rule_table.md` | plain-English §51 reference, cited by 02_method |
| `docs/06_pivot_mechanism_aware_censoring.md` | ARCHIVE | `archive/docs/06_pivot_mechanism_aware_censoring.md` | pre-registrations and results notes, unchanged |
| `docs/07_literature_table.md` | ARCHIVE | `archive/docs/07_literature_table.md` | pre-registrations and results notes, unchanged |
| `docs/08_test2_preregistration.md` | ARCHIVE | `archive/docs/08_test2_preregistration.md` | pre-registrations and results notes, unchanged |
| `docs/09_m2_preregistration.md` | ARCHIVE | `archive/docs/09_m2_preregistration.md` | pre-registrations and results notes, unchanged |
| `docs/10_m2_verdict.md` | ARCHIVE | `archive/docs/10_m2_verdict.md` | pre-registrations and results notes, unchanged |
| `docs/11_e1_identification_audit.md` | ARCHIVE | `archive/docs/11_e1_identification_audit.md` | pre-registrations and results notes, unchanged |
| `docs/12_identification_fix.md` | ARCHIVE | `archive/docs/12_identification_fix.md` | pre-registrations and results notes, unchanged |
| `docs/13_theta_audit.md` | ARCHIVE | `archive/docs/13_theta_audit.md` | pre-registrations and results notes, unchanged |
| `docs/14_mv_coverage_fix.md` | ARCHIVE | `archive/docs/14_mv_coverage_fix.md` | pre-registrations and results notes, unchanged |
| `docs/15_tb_restart.md` | ARCHIVE | `archive/docs/15_tb_restart.md` | pre-registrations and results notes, unchanged |
| `docs/16_e1_generator_design.md` | ARCHIVE | `archive/docs/16_e1_generator_design.md` | pre-registrations and results notes, unchanged |
| `docs/17_e1_first_run_report.md` | ARCHIVE | `archive/docs/17_e1_first_run_report.md` | pre-registrations and results notes, unchanged |
| `docs/18_fallback_decision.md` | ARCHIVE | `archive/docs/18_fallback_decision.md` | pre-registrations and results notes, unchanged |
| `docs/19_merged_gate_and_power.md` | ARCHIVE | `archive/docs/19_merged_gate_and_power.md` | pre-registrations and results notes, unchanged |
| `docs/20_response_curve_bug.md` | ARCHIVE | `archive/docs/20_response_curve_bug.md` | pre-registrations and results notes, unchanged |
| `docs/21_report_only_verdict_bug.md` | ARCHIVE | `archive/docs/21_report_only_verdict_bug.md` | pre-registrations and results notes, unchanged |
| `docs/C0_preregistration.md` | ARCHIVE | `archive/docs/C0_preregistration.md` | pre-registrations and results notes, unchanged |
| `docs/C1_conclusions_table.md` | ARCHIVE | `archive/docs/C1_conclusions_table.md` | pre-registrations and results notes, unchanged |
| `docs/ERRATUM_lambda5.md` | ARCHIVE | `archive/docs/ERRATUM_lambda5.md` | pre-registrations and results notes, unchanged |
| `docs/K0_preregistration.md` | ARCHIVE | `archive/docs/K0_preregistration.md` | pre-registrations and results notes, unchanged |
| `docs/K_results.md` | ARCHIVE | `archive/docs/K_results.md` | pre-registrations and results notes, unchanged |
| `docs/P0_preregistration.md` | ARCHIVE | `archive/docs/P0_preregistration.md` | pre-registrations and results notes, unchanged |
| `docs/P3_results.md` | ARCHIVE | `archive/docs/P3_results.md` | pre-registrations and results notes, unchanged |
| `docs/P_STOP_P0.md` | ARCHIVE | `archive/docs/P_STOP_P0.md` | pre-registrations and results notes, unchanged |
| `docs/Q0_preregistration.md` | ARCHIVE | `archive/docs/Q0_preregistration.md` | pre-registrations and results notes, unchanged |
| `docs/Q0b_preregistration.md` | ARCHIVE | `archive/docs/Q0b_preregistration.md` | pre-registrations and results notes, unchanged |
| `docs/Q0b_results.md` | ARCHIVE | `archive/docs/Q0b_results.md` | pre-registrations and results notes, unchanged |
| `docs/Q0c_preregistration.md` | ARCHIVE | `archive/docs/Q0c_preregistration.md` | pre-registrations and results notes, unchanged |
| `docs/Q0c_results.md` | ARCHIVE | `archive/docs/Q0c_results.md` | pre-registrations and results notes, unchanged |
| `docs/Q1_results.md` | ARCHIVE | `archive/docs/Q1_results.md` | pre-registrations and results notes, unchanged |
| `docs/Q2_results.md` | ARCHIVE | `archive/docs/Q2_results.md` | pre-registrations and results notes, unchanged |
| `docs/Q5_preregistration.md` | ARCHIVE | `archive/docs/Q5_preregistration.md` | pre-registrations and results notes, unchanged |
| `docs/Q5_results.md` | ARCHIVE | `archive/docs/Q5_results.md` | pre-registrations and results notes, unchanged |
| `docs/Q6_preregistration.md` | ARCHIVE | `archive/docs/Q6_preregistration.md` | pre-registrations and results notes, unchanged |
| `docs/Q6_results.md` | ARCHIVE | `archive/docs/Q6_results.md` | pre-registrations and results notes, unchanged |
| `docs/Q_STOP_Q0c.md` | ARCHIVE | `archive/docs/Q_STOP_Q0c.md` | pre-registrations and results notes, unchanged |
| `docs/Q_STOP_R1.md` | ARCHIVE | `archive/docs/Q_STOP_R1.md` | pre-registrations and results notes, unchanged |
| `docs/R1_reconciliation.md` | ARCHIVE | `archive/docs/R1_reconciliation.md` | pre-registrations and results notes, unchanged |
| `docs/S3_literature_map.md` | ARCHIVE | `archive/docs/S3_literature_map.md` | pre-registrations and results notes, unchanged |
| `docs/TB_lambda_sensitivity.md` | ARCHIVE | `archive/docs/TB_lambda_sensitivity.md` | pre-registrations and results notes, unchanged |
| `docs/V0_preregistration.md` | ARCHIVE | `archive/docs/V0_preregistration.md` | pre-registrations and results notes, unchanged |
| `docs/V_results.md` | ARCHIVE | `archive/docs/V_results.md` | pre-registrations and results notes, unchanged |
| `docs/legal/anlage1_EEG2023.pdf` | KEEP | `docs/sources/legal/anlage1_EEG2023.pdf` | cited by path from src (path updated) |
| `docs/legal/s36h_EEG2023.pdf` | KEEP | `docs/sources/legal/s36h_EEG2023.pdf` |  |
| `docs/legal/s51a_EEG2023.pdf` | KEEP | `docs/sources/legal/s51a_EEG2023.pdf` |  |
| `docs/literature/hirth_2026_2609.10053v1.pdf` | KEEP | `docs/sources/literature/hirth_2026_2609.10053v1.pdf` | cited by src |
| `docs/literature/titz_2023_2307.12636v1.pdf` | KEEP | `docs/sources/literature/titz_2023_2307.12636v1.pdf` |  |
| `docs/literature/windguard_2024_status_windenergieausbau_land_jahr2023.pdf` | KEEP | `docs/sources/literature/windguard_2024_status_windenergieausbau_land_jahr2023.pdf` | cited by src |
| `figures/.gitkeep` | KEEP | `figures/.gitkeep` |  |
| `figures/10_response_gate_half.png` | ARCHIVE | `archive/figures/10_response_gate_half.png` | kill test / E1 figures |
| `figures/10_response_gate_logistic.png` | ARCHIVE | `archive/figures/10_response_gate_logistic.png` | kill test / E1 figures |
| `figures/10_response_gate_step.png` | ARCHIVE | `archive/figures/10_response_gate_step.png` | kill test / E1 figures |
| `figures/10_response_smoke.png` | ARCHIVE | `archive/figures/10_response_smoke.png` | kill test / E1 figures |
| `figures/11_ablation_gamma0.0.png` | ARCHIVE | `archive/figures/11_ablation_gamma0.0.png` | kill test / E1 figures |
| `figures/11_ablation_gamma0.5.png` | ARCHIVE | `archive/figures/11_ablation_gamma0.5.png` | kill test / E1 figures |
| `figures/11_ablation_gamma1.0.png` | ARCHIVE | `archive/figures/11_ablation_gamma1.0.png` | kill test / E1 figures |
| `figures/bias_by_price_band_50Hertz.png` | ARCHIVE | `archive/figures/bias_by_price_band_50Hertz.png` | kill test / E1 figures |
| `figures/bias_by_price_band_Amprion.png` | ARCHIVE | `archive/figures/bias_by_price_band_Amprion.png` | kill test / E1 figures |
| `figures/bias_by_price_band_DE.png` | ARCHIVE | `archive/figures/bias_by_price_band_DE.png` | kill test / E1 figures |
| `figures/bias_by_price_band_TenneT_DE.png` | ARCHIVE | `archive/figures/bias_by_price_band_TenneT_DE.png` | kill test / E1 figures |
| `figures/bias_by_price_band_TransnetBW.png` | ARCHIVE | `archive/figures/bias_by_price_band_TransnetBW.png` | kill test / E1 figures |
| `figures/bias_by_price_band_all_areas.png` | ARCHIVE | `archive/figures/bias_by_price_band_all_areas.png` | kill test / E1 figures |
| `figures/findings/F10_bias_breakdown.png` | KEEP | `figures/09_exp3_bias_breakdown.png` |  |
| `figures/findings/F10_bias_breakdown_caption.txt` | KEEP | `figures/09_exp3_bias_breakdown_caption.txt` |  |
| `figures/findings/F10_bias_breakdown_data.csv` | KEEP | `figures/09_exp3_bias_breakdown_data.csv` |  |
| `figures/findings/F1_problem_schematic.png` | KEEP | `figures/01_motivation_event_day.png` | motivation; reads archived kill-test files |
| `figures/findings/F1_problem_schematic_caption.txt` | KEEP | `figures/01_motivation_event_day_caption.txt` | motivation; reads archived kill-test files |
| `figures/findings/F1_problem_schematic_data.csv` | KEEP | `figures/01_motivation_event_day_data.csv` | motivation; reads archived kill-test files |
| `figures/findings/F2_forecast_bias_by_price_band.png` | KEEP | `figures/02_motivation_forecast_bias_by_band.png` | motivation; reads archived kill-test files |
| `figures/findings/F2_forecast_bias_by_price_band_caption.txt` | KEEP | `figures/02_motivation_forecast_bias_by_band_caption.txt` | motivation; reads archived kill-test files |
| `figures/findings/F2_forecast_bias_by_price_band_data.csv` | KEEP | `figures/02_motivation_forecast_bias_by_band_data.csv` | motivation; reads archived kill-test files |
| `figures/findings/F3_projection_vs_forecast_gap_by_band.png` | KEEP | `figures/03_available_power_gap_by_band.png` |  |
| `figures/findings/F3_projection_vs_forecast_gap_by_band_caption.txt` | KEEP | `figures/03_available_power_gap_by_band_caption.txt` |  |
| `figures/findings/F3_projection_vs_forecast_gap_by_band_data.csv` | KEEP | `figures/03_available_power_gap_by_band_data.csv` |  |
| `figures/findings/F4_coverage_never_fails.png` | KEEP | `figures/04_exp1_coverage.png` | split: exp1 rows only (P3 O, P3 D, Q1); Q6b rows dropped |
| `figures/findings/F4_coverage_never_fails_caption.txt` | KEEP | `figures/04_exp1_coverage_caption.txt` | split: exp1 rows only (P3 O, P3 D, Q1); Q6b rows dropped |
| `figures/findings/F4_coverage_never_fails_data.csv` | KEEP | `figures/04_exp1_coverage_data.csv` | split: exp1 rows only (P3 O, P3 D, Q1); Q6b rows dropped |
| `figures/findings/F5_exact_vs_estimated_potential.png` | KEEP | `figures/05_exp1_exact_vs_estimated_potential.png` |  |
| `figures/findings/F5_exact_vs_estimated_potential_caption.txt` | KEEP | `figures/05_exp1_exact_vs_estimated_potential_caption.txt` |  |
| `figures/findings/F5_exact_vs_estimated_potential_data.csv` | KEEP | `figures/05_exp1_exact_vs_estimated_potential_data.csv` |  |
| `figures/findings/F6_noise_dial.png` | KEEP | `figures/06_exp1_noise_dial.png` |  |
| `figures/findings/F6_noise_dial_caption.txt` | KEEP | `figures/06_exp1_noise_dial_caption.txt` |  |
| `figures/findings/F6_noise_dial_data.csv` | KEEP | `figures/06_exp1_noise_dial_data.csv` |  |
| `figures/findings/F7_synthetic_vs_real.png` | ARCHIVE | `archive/figures/findings/F7_synthetic_vs_real.png` |  |
| `figures/findings/F7_synthetic_vs_real_caption.txt` | ARCHIVE | `archive/figures/findings/F7_synthetic_vs_real_caption.txt` |  |
| `figures/findings/F7_synthetic_vs_real_data.csv` | ARCHIVE | `archive/figures/findings/F7_synthetic_vs_real_data.csv` |  |
| `figures/findings/F8_day_heterogeneity.png` | ARCHIVE | `archive/figures/findings/F8_day_heterogeneity.png` |  |
| `figures/findings/F8_day_heterogeneity_caption.txt` | ARCHIVE | `archive/figures/findings/F8_day_heterogeneity_caption.txt` |  |
| `figures/findings/F8_day_heterogeneity_data.csv` | ARCHIVE | `archive/figures/findings/F8_day_heterogeneity_data.csv` |  |
| `figures/findings/F9_width_vs_noise.png` | KEEP | `figures/07_exp1_width_vs_noise.png` |  |
| `figures/findings/F9_width_vs_noise_caption.txt` | KEEP | `figures/07_exp1_width_vs_noise_caption.txt` |  |
| `figures/findings/F9_width_vs_noise_data.csv` | KEEP | `figures/07_exp1_width_vs_noise_data.csv` |  |
| `results/00_data_quality.csv` | ARCHIVE | `archive/results/00_data_quality.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/00_dst_check.csv` | ARCHIVE | `archive/results/00_dst_check.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/01_sample_size.csv` | ARCHIVE | `archive/results/01_sample_size.csv` | kill test; F2 reads it from the archive |
| `results/02_bias_by_price_band.csv` | ARCHIVE | `archive/results/02_bias_by_price_band.csv` | kill test; F2 reads it from the archive |
| `results/02_overall_negative_qh_bias.csv` | ARCHIVE | `archive/results/02_overall_negative_qh_bias.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/02_robustness_de.csv` | ARCHIVE | `archive/results/02_robustness_de.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/02_worst_days_de.csv` | ARCHIVE | `archive/results/02_worst_days_de.csv` | kill test; F1 reads it from the archive |
| `results/03_da_id_identity_tolerance.csv` | ARCHIVE | `archive/results/03_da_id_identity_tolerance.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/03_da_vs_id.csv` | ARCHIVE | `archive/results/03_da_vs_id.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/03_id_bias_negative_qh.csv` | ARCHIVE | `archive/results/03_id_bias_negative_qh.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/04_redispatch_test_c.csv` | ARCHIVE | `archive/results/04_redispatch_test_c.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/10_diag_b3_bins.csv` | ARCHIVE | `archive/results/10_diag_b3_bins.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/10_diag_gamma.csv` | ARCHIVE | `archive/results/10_diag_gamma.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/10_gate_preview.csv` | ARCHIVE | `archive/results/10_gate_preview.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/10_gate_preview.log` | ARCHIVE | `archive/results/10_gate_preview.log` | kill test, E1, M2/T-B, diagnostics |
| `results/10_gate_preview_summary.json` | ARCHIVE | `archive/results/10_gate_preview_summary.json` | kill test, E1, M2/T-B, diagnostics |
| `results/10_smoke_run.csv` | ARCHIVE | `archive/results/10_smoke_run.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/10_smoke_run_config.json` | ARCHIVE | `archive/results/10_smoke_run_config.json` | kill test, E1, M2/T-B, diagnostics |
| `results/11_ablation_ladder.csv` | ARCHIVE | `archive/results/11_ablation_ladder.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/11_ablation_ladder.log` | ARCHIVE | `archive/results/11_ablation_ladder.log` | kill test, E1, M2/T-B, diagnostics |
| `results/12_hetero_r.csv` | ARCHIVE | `archive/results/12_hetero_r.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/12_ladder.csv` | ARCHIVE | `archive/results/12_ladder.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/12_proxy_quality.csv` | ARCHIVE | `archive/results/12_proxy_quality.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/12_reduced_grid.csv` | ARCHIVE | `archive/results/12_reduced_grid.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/12_reduced_grid_merged.csv` | ARCHIVE | `archive/results/12_reduced_grid_merged.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/13_gate_verdict.csv` | ARCHIVE | `archive/results/13_gate_verdict.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/13_gate_verdict_merged.csv` | ARCHIVE | `archive/results/13_gate_verdict_merged.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/13_oracle_power_diagnostic.csv` | ARCHIVE | `archive/results/13_oracle_power_diagnostic.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/13_oracle_power_diagnostic_merged.csv` | ARCHIVE | `archive/results/13_oracle_power_diagnostic_merged.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/13_power_evidence_merged.csv` | ARCHIVE | `archive/results/13_power_evidence_merged.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/15_4a_response.csv` | ARCHIVE | `archive/results/15_4a_response.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/16_4a_proper_placebo.csv` | ARCHIVE | `archive/results/16_4a_proper_placebo.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/17_bias_by_hour.csv` | ARCHIVE | `archive/results/17_bias_by_hour.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/18_market_value_validation.csv` | KEEP-AS-COMPONENT | `artifacts/method_inputs/market_value_validation.csv` |  |
| `results/19_b3_bins_multiseed.csv` | ARCHIVE | `archive/results/19_b3_bins_multiseed.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/20_stage_a_diagnostics.csv` | ARCHIVE | `archive/results/20_stage_a_diagnostics.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/21_tb_primary.csv` | ARCHIVE | `archive/results/21_tb_primary.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/21_tb_primary_buggy_curve_20261109.csv` | ARCHIVE | `archive/results/21_tb_primary_buggy_curve_20261109.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/21_tb_primary_report_20261110.txt` | ARCHIVE | `archive/results/21_tb_primary_report_20261110.txt` | kill test, E1, M2/T-B, diagnostics |
| `results/21_tb_primary_rerun_20261109.log` | ARCHIVE | `archive/results/21_tb_primary_rerun_20261109.log` | kill test, E1, M2/T-B, diagnostics |
| `results/23_fleet_history.csv` | ARCHIVE | `archive/results/23_fleet_history.csv` | no kept reader |
| `results/24_test2_counts_rebuilt.csv` | ARCHIVE | `archive/results/24_test2_counts_rebuilt.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/30_mastr_cohort_shares.csv` | KEEP-AS-COMPONENT | `artifacts/method_inputs/mastr_cohort_shares.csv` | read by exposure.py |
| `results/30_mastr_zuschlagsnummer_fill.csv` | KEEP-AS-COMPONENT | `artifacts/method_inputs/mastr_zuschlagsnummer_fill.csv` |  |
| `results/31_award_values.csv` | KEEP-AS-COMPONENT | `artifacts/method_inputs/award_values.csv` |  |
| `results/32_market_values.csv` | KEEP-AS-COMPONENT | `artifacts/method_inputs/market_values.csv` |  |
| `results/33_reference_period.csv` | KEEP-AS-COMPONENT | `artifacts/method_inputs/reference_period.csv` |  |
| `results/34_hochrechnung_check.csv` | KEEP-AS-COMPONENT | `artifacts/available_power_estimate/projection_check_operational.csv` | read by checker (Q0 A1) |
| `results/35_market_premium_zero.csv` | KEEP-AS-COMPONENT | `artifacts/method_inputs/market_premium_zero.csv` |  |
| `results/36_hochrechnung_onshore_check.csv` | KEEP-AS-COMPONENT | `artifacts/available_power_estimate/projection_check_onshore.csv` | read by checker (Q0 A1) |
| `results/37_event_days_to_export.csv` | ARCHIVE | `archive/results/37_event_days_to_export.csv` | no kept reader |
| `results/38_rule18_real.csv` | KEEP-AS-COMPONENT | `artifacts/method_inputs/cohort_parameters.csv` |  |
| `results/38_rule18_settings.csv` | KEEP-AS-COMPONENT | `artifacts/method_inputs/cohort_parameter_settings.csv` |  |
| `results/39_identification_gate.csv` | ARCHIVE | `archive/results/39_identification_gate.csv` | kill test, E1, M2/T-B, diagnostics |
| `results/39_nr51_compliance.csv` | KEEP-AS-COMPONENT | `artifacts/available_power_estimate/projection_adds_back_curtailment.csv` |  |
| `results/C1_conclusions_table.csv` | KEEP | `artifacts/exp3_german_application/results_table.csv` |  |
| `src/.gitkeep` | ARCHIVE | `archive/src/.gitkeep` | kill test and diagnostics |
| `src/build_conclusions_table.py` | KEEP-AS-COMPONENT | `src/experiments/exp3_results_table.py` | C0 rule; writes the exp3 table |
| `src/build_fleet_history.py` | ARCHIVE | `archive/src/build_fleet_history.py` | no kept reader |
| `src/build_panel.py` | KEEP | `src/method/build_panel.py` | rebuild from scratch |
| `src/censoring/__init__.py` | ARCHIVE | `archive/src/censoring/__init__.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/baselines.py` | KEEP | `src/method/stage_a/baselines.py` | F-2: needed by stage A |
| `src/censoring/check_price_bands.py` | ARCHIVE | `archive/src/censoring/check_price_bands.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/check_window.py` | ARCHIVE | `archive/src/censoring/check_window.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/cohorts.py` | KEEP | `src/method/exposure.py` | θ, exposure s, depth, cohort sets |
| `src/censoring/diag_b3_bins.py` | ARCHIVE | `archive/src/censoring/diag_b3_bins.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/diag_bias_by_forecast.py` | ARCHIVE | `archive/src/censoring/diag_bias_by_forecast.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/diag_bias_by_hour.py` | ARCHIVE | `archive/src/censoring/diag_bias_by_hour.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/diag_stage_a.py` | ARCHIVE | `archive/src/censoring/diag_stage_a.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/gate_verdict.py` | ARCHIVE | `archive/src/censoring/gate_verdict.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/identification.py` | KEEP | `src/method/collinearity.py` | exposure rank, duplicate cohort groups |
| `src/censoring/m2.py` | KEEP | `src/method/stage_a/reservation_depth_model.py` | F-2: Arm D stage A; carries the uncommitted λ-grid edit (F-8) |
| `src/censoring/metrics.py` | ARCHIVE | `archive/src/censoring/metrics.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/model.py` | KEEP | `src/method/stage_a/latent_model.py` | F-1/F-2: cohort_runlength_hours; stage A |
| `src/censoring/oracle_power_check.py` | ARCHIVE | `archive/src/censoring/oracle_power_check.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/power_evidence_tables.py` | ARCHIVE | `archive/src/censoring/power_evidence_tables.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/real_panel.py` | ARCHIVE | `archive/src/censoring/real_panel.py` | T-D real panel for M2 |
| `src/censoring/run_ablations.py` | ARCHIVE | `archive/src/censoring/run_ablations.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/run_identification.py` | KEEP | `src/method/real_theta.py` | _real_panel_theta (θ on the real panel); also E1 identification gate code |
| `src/censoring/run_reduced_grid.py` | ARCHIVE | `archive/src/censoring/run_reduced_grid.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/run_synthetic.py` | ARCHIVE | `archive/src/censoring/run_synthetic.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/run_tb.py` | ARCHIVE | `archive/src/censoring/run_tb.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/run_tb_sensitivity.py` | ARCHIVE | `archive/src/censoring/run_tb_sensitivity.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/synthetic.py` | KEEP | `src/method/synthetic.py` | generator with known truth |
| `src/censoring/tb_methods.py` | ARCHIVE | `archive/src/censoring/tb_methods.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/tb_param_counts.py` | ARCHIVE | `archive/src/censoring/tb_param_counts.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/theta_audit.py` | ARCHIVE | `archive/src/censoring/theta_audit.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/validate_synthetic.py` | ARCHIVE | `archive/src/censoring/validate_synthetic.py` | M1/M2, baselines, E1, T-B, diagnostics |
| `src/censoring/window.py` | KEEP | `src/method/window.py` | MTU-15 start date |
| `src/check_da_vs_id.py` | ARCHIVE | `archive/src/check_da_vs_id.py` | kill test and diagnostics |
| `src/check_hochrechnung.py` | ARCHIVE | `archive/src/check_hochrechnung.py` | kill test and diagnostics |
| `src/check_hochrechnung_onshore.py` | ARCHIVE | `archive/src/check_hochrechnung_onshore.py` | kill test and diagnostics |
| `src/check_nr51_compliance.py` | KEEP | `src/method/projection_and_redispatch.py` | load_projection, redispatch_qh, §51 compliance check |
| `src/check_rule18_real.py` | KEEP | `src/method/cohort_parameters.py` | cohort parameters on the real panel |
| `src/compute_theta_inputs.py` | KEEP | `src/method/theta_inputs.py` |  |
| `src/diag_price_logratio.py` | ARCHIVE | `archive/src/diag_price_logratio.py` | kill test and diagnostics |
| `src/diag_price_placebo.py` | ARCHIVE | `archive/src/diag_price_placebo.py` | kill test and diagnostics |
| `src/e1_check_geometry.py` | ARCHIVE | `archive/src/e1_check_geometry.py` | E1 |
| `src/e1_check_numbers.py` | ARCHIVE | `archive/src/e1_check_numbers.py` | E1 |
| `src/e1_check_panel.py` | ARCHIVE | `archive/src/e1_check_panel.py` | E1 |
| `src/e1_check_thin.py` | ARCHIVE | `archive/src/e1_check_thin.py` | E1 |
| `src/e1_cmp_mastr.py` | ARCHIVE | `archive/src/e1_cmp_mastr.py` | E1 |
| `src/e1_cmp_rank.py` | ARCHIVE | `archive/src/e1_cmp_rank.py` | E1 |
| `src/e1_cmp_synthetic.py` | ARCHIVE | `archive/src/e1_cmp_synthetic.py` | E1 |
| `src/e1_run_grid.py` | ARCHIVE | `archive/src/e1_run_grid.py` | E1 |
| `src/identification/__init__.py` | ARCHIVE | `archive/src/identification/__init__.py` | src/method/__init__.py is new |
| `src/identification/bounds.py` | KEEP | `src/method/bounds.py` | min/max programme, ε |
| `src/identification/functionals.py` | KEEP | `src/method/functionals.py` | λ₁–λ₇ |
| `src/identification/lambda5_truth.py` | KEEP | `src/method/lambda5_truth.py` | erratum correction on read |
| `src/identification/run_p3_real.py` | KEEP | `src/method/real_panel.py` | real-data panel + run_arm |
| `src/identification/run_p3_synthetic.py` | KEEP | `src/method/synthetic_scoring.py` | prepare_cell, score_cell, truths (Arm O/D harness) |
| `src/identification/run_q5.py` | KEEP-AS-COMPONENT | `src/experiments/exp3_real_bounds.py` | runs F and H; exp3 reports H |
| `src/identification/run_q6b.py` | ARCHIVE | `archive/src/identification/run_q6b.py` | Q6b |
| `src/identification/run_q_dial.py` | KEEP | `src/method/potential_error.py` | noise/bias applied to the potential (Q1, Q2) |
| `src/identification/run_v_bias_robust.py` | KEEP | `src/method/bias_robust.py` | outer loop over the b grid |
| `src/identification/summarise_p3.py` | KEEP | `src/method/read_results.py` | load(): casts + λ₅ correction |
| `src/identification/summarise_q1.py` | KEEP-AS-COMPONENT | `src/experiments/exp1_noise_dial_summary.py` |  |
| `src/identification/summarise_q2.py` | KEEP-AS-COMPONENT | `src/experiments/exp2_bias_dial_summary.py` |  |
| `src/identification/summarise_q5.py` | KEEP-AS-COMPONENT | `src/experiments/exp3_real_bounds_summary.py` |  |
| `src/identification/summarise_q6b.py` | ARCHIVE | `archive/src/identification/summarise_q6b.py` | Q6b |
| `src/identification/summarise_v.py` | KEEP | `src/method/bias_robust_summary.py` | hulls S_B, breakdown points |
| `src/ingest_award_values.py` | KEEP | `src/method/ingest_award_values.py` |  |
| `src/ingest_market_values.py` | KEEP | `src/method/ingest_market_values.py` |  |
| `src/ingest_mastr.py` | KEEP | `src/method/ingest_mastr.py` |  |
| `src/ingest_smard.py` | KEEP | `src/method/ingest_smard.py` | rebuild from scratch |
| `src/kill_test.py` | ARCHIVE | `archive/src/kill_test.py` | kill test and diagnostics |
| `src/make_figures.py` | ARCHIVE | `archive/src/make_figures.py` | kill test and diagnostics |
| `src/make_findings_figures.py` | KEEP | `src/figures.py` | F7, F8 removed; F4 split |
| `src/postauction/__init__.py` | ARCHIVE | `archive/src/postauction/__init__.py` | P0 / forecasting |
| `src/postauction/common.py` | KEEP | `src/method/day_bootstrap.py` | FLAG: postauction module needed by Q0/Q0b (bands, window, day bootstrap) |
| `src/postauction/leakage.py` | ARCHIVE | `archive/src/postauction/leakage.py` | P0 / forecasting |
| `src/postauction/p0_recompute.py` | ARCHIVE | `archive/src/postauction/p0_recompute.py` | P0 |
| `src/potential/__init__.py` | ARCHIVE | `archive/src/potential/__init__.py` |  |
| `src/potential/anchors.py` | KEEP-AS-COMPONENT | `src/experiments/available_power_anchors.py` | Q0 σ and bias anchors |
| `src/potential/k_bridge.py` | ARCHIVE | `archive/src/potential/k_bridge.py` |  |
| `src/potential/k_bridge_data.py` | ARCHIVE | `archive/src/potential/k_bridge_data.py` | Phase K (cancelled) |
| `src/potential/q0b_validate_h.py` | KEEP | `src/method/available_power.py` | load_frames (H, G, F, RD per area) + the Q0b test |
| `src/potential/q0c_volume.py` | ARCHIVE | `archive/src/potential/q0c_volume.py` | Q0c |
| `src/potential/q6a_heterogeneity.py` | ARCHIVE | `archive/src/potential/q6a_heterogeneity.py` | Q6a |
| `src/redispatch_control.py` | KEEP | `src/method/redispatch_reader.py` | FLAG: kill-test check-2 module; find_input/parse_measures needed by the redispatch reader |
| `src/smard_config.py` | KEEP | `src/method/smard_config.py` | areas, price bands (read by projection loader) |
| `src/stats_boot.py` | KEEP | `src/method/event_day_bootstrap.py` | event-day bootstrap |
| `src/validate_market_values.py` | KEEP-AS-COMPONENT | `src/method/validate_market_values.py` | writes results/18 (kept as data check) |
| `tests/__init__.py` | KEEP | `tests/__init__.py` |  |
| `tests/test_ablations.py` | ARCHIVE | `archive/tests/test_ablations.py` | tests of archived code |
| `tests/test_bounds.py` | KEEP | `tests/test_bounds.py` |  |
| `tests/test_cohorts.py` | KEEP | `tests/test_exposure.py` |  |
| `tests/test_conclusions_table.py` | KEEP | `tests/test_exp3_results_table.py` |  |
| `tests/test_findings_figures.py` | KEEP | `tests/test_figures.py` |  |
| `tests/test_gate_writer.py` | ARCHIVE | `archive/tests/test_gate_writer.py` | tests of archived code |
| `tests/test_identification.py` | KEEP | `tests/test_collinearity.py` | F-6: its two M1-metric tests move to archive/tests in Step 4 |
| `tests/test_lambda5_truth.py` | KEEP | `tests/test_lambda5_truth.py` |  |
| `tests/test_leakage.py` | ARCHIVE | `archive/tests/test_leakage.py` | M1 feature leakage |
| `tests/test_leakage_postauction.py` | ARCHIVE | `archive/tests/test_leakage_postauction.py` | forecast allow-list (P) + K0 extension |
| `tests/test_m2.py` | ARCHIVE | `archive/tests/test_m2.py` | tests of archived code |
| `tests/test_market_value_coverage.py` | KEEP | `tests/test_market_value_coverage.py` | data |
| `tests/test_market_value_resolution.py` | KEEP | `tests/test_market_value_resolution.py` | data |
| `tests/test_panel_rebuild.py` | KEEP | `tests/test_panel_rebuild.py` | data |
| `tests/test_real_panel.py` | ARCHIVE | `archive/tests/test_real_panel.py` | tests of archived code |
| `tests/test_reported_numbers.py` | KEEP | `tests/test_reported_numbers.py` | FLAG: split proposed (active docs here; archived docs' checks under archive/tests/) |
| `tests/test_response_curve_truth.py` | ARCHIVE | `archive/tests/test_response_curve_truth.py` | tests of archived code |
| `tests/test_response_head.py` | ARCHIVE | `archive/tests/test_response_head.py` | tests of archived code |
| `tests/test_synthetic.py` | KEEP | `tests/test_synthetic.py` |  |
| `tests/test_tb.py` | ARCHIVE | `archive/tests/test_tb.py` | tests of archived code |
| `tests/test_tb_resume.py` | ARCHIVE | `archive/tests/test_tb_resume.py` | tests of archived code |
| `tests/test_theta_inputs.py` | KEEP | `tests/test_theta_inputs.py` | data |
| `tools/export_share.sh` | KEEP | `tools/export_share.sh` | active tree + archive/README.md only (Step 6) |
