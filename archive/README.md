# Archive

Everything that is not part of the one method and its three experiments. Nothing here was
deleted or edited in substance: files moved with `git mv` on 16 November 2026 and keep their
history (`git log --follow`). The full old → new mapping is `docs/archive_mapping.md`.

**Still verified.** Every figure quoted in an archived results note is re-derived by
`archive/checks/test_archived_numbers.py`, which the suite collects (`pytest.ini`).
**Not run.** Archived code and the unit tests in `archive/tests/` are kept as record. Their
imports were updated to the new module names wherever a module moved, but they import each
other under their old `src.*` paths and are not collected by the suite.

## What each archived item was, and why it is not in the main thesis

| item | where | what it was | status, and why archived |
|---|---|---|---|
| Forecast-bias check (kill test) | `docs/04_rq1_killtest_note*.md`, `src/kill_test.py`, `check_da_vs_id.py`, `make_figures.py`, `results/00`–`04` | does the TSO day-ahead forecast over-predict wind at negative prices | GO (DE bias −1,684.4 MW). A forecast-versus-generation discrepancy, not a causal measure; kept only as the source of the two motivation figures |
| E1 semi-synthetic benchmark and gate | `docs/06`, `11`, `12`, `16`, `17`, `18`, `19`, `src/e1_*`, `src/censoring/run_*`, `gate_verdict.py`, `results/10`–`13`, `39_identification_gate.csv` | the first method (M1) and its pre-registered gate | the merged gate FAILED, and its base was 61.6% pre-MTU-15; superseded by partial identification |
| M1 / M2 models and baselines B0–B6 | `docs/09`, `10`, `src/censoring/metrics.py`, `tb_methods.py`, `diag_*` | point-estimating curtailment-response models | superseded; only M2's cross-fitted stage A stays active, under `src/method/stage_a/`, because the estimated-potential arm of experiment 1 uses it |
| T-B data-efficiency test | `docs/15`, `20`, `21`, `src/censoring/run_tb*.py`, `results/21_*` | is M2 more data-efficient than its rivals | PASS on the pre-registered λ grid, after a scoring bug was found and declared (docs/20, 21) |
| T-B λ sensitivity | `docs/TB_lambda_sensitivity.md`, `docs/Q_STOP_R1.md`, `artifacts/TB_lambda/` | the same test on a widened λ grid | FAILS there (15 of 45, p = 0.036); provisional; the uncommitted λ-grid edit is still in the working tree |
| Test 2 | `docs/08_test2_preregistration.md` | a real-data preview test | pre-registered (with Amendment 1); no results note exists in the repo |
| P0 and post-auction forecasting | `docs/P0_preregistration.md`, `docs/P_STOP_P0.md`, `src/postauction/`, `artifacts/P0/` | forecasting output after the day-ahead auction | STOPPED: best-case RMSE reduction below 15% everywhere |
| P3 real data with the forecast F | `artifacts/P3/p3_real*.csv` | identified sets on all of Germany with F as the potential | superseded by experiment 3, which uses H on three control areas |
| Q0c volume triangulation | `docs/Q0c_*.md`, `docs/Q_STOP_Q0c.md`, `src/potential/q0c_volume.py`, `artifacts/Q0c/` | three-area curtailed volume against Hirth's 2.5 TWh | NOT TESTABLE at national scale |
| Q6a / Q6b heterogeneity diagnostic | `docs/Q6_*.md`, `src/potential/q6a_heterogeneity.py`, `src/identification/*q6b*`, `artifacts/Q6/` | is the real-data floor day-to-day behaviour | Q6a PRESENT, Q6b NOT SUPPORTED; exploratory, and the synthetic-to-real gap it probed stays unexplained |
| R1 reconciliation | `docs/R1_reconciliation.md`, `artifacts/R1/` | reconciling two working copies | done; housekeeping |
| Phase S and C notes | `docs/00_START_HERE.md`, `00_OBJECTIVE.md`, `S3_literature_map.md`, `C0_preregistration.md`, `C1_conclusions_table.md` | the earlier guide, objective, literature map and conclusions table | superseded by `docs/00_start_here.md`–`07_*`; the C0 rule and C1 table are reused in experiment 3, and `src/experiments/exp3_results_table.py` still rebuilds the C1 note byte for byte |
| Pre-registrations and results notes of the kept work | `docs/P3_results.md`, `Q0_*`, `Q0b_*`, `Q1_results.md`, `Q2_results.md`, `Q5_*`, `V0_preregistration.md`, `V_results.md`, `ERRATUM_lambda5.md` | the original records behind experiments 1–3 and the available-power section | archived unchanged; the active docs cite them by path and commit |
| Phase K bias bridge | `docs/K0_preregistration.md`, `docs/K_results.md`, `src/potential/k_bridge*.py`, `artifacts/K1/` | estimating the projection's bias per event-day | K1 FAILED its gate (coverage 0.740, median half-width 0.189); the phase was cancelled |
| Briefs and background | `docs/01_*`, `02_evidence_base.md`, `07_literature_table.md` | thesis briefs, evidence base, literature table | superseded by the active docs |
| Other results, diagnostics and figures | `results/`, `figures/` | intermediate tables and the old figure sets (including F7 and F8) | not used by the kept method |
| Unit tests of archived code | `archive/tests/` | tests of M1, T-B, P0 leakage, the real-panel T-D code, and two M1-metric tests split out of the identification tests | kept as record; not collected |
