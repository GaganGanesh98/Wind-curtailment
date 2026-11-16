# MSc thesis: wind curtailment at negative prices in Germany

Gagan Ganesh, MSc AI/ML (Big Data), SRH Hochschule Berlin.

**Objective.** Determine which conclusions about how German wind farms respond to negative
prices can be supported by public aggregated data, and how much bias in the available-power
estimate each conclusion can survive.

**Method.** Rule-structured, bias-robust partial identification, with the quality-assured
Online-Hochrechnung (H) as the estimate of available power.

**Three experiments:** known-truth validation, bias-robustness validation, German application,
plus a section on the available-power estimate.

**Start with [`docs/00_start_here.md`](docs/00_start_here.md).** The German results table is in
[`docs/06_exp3_german_application.md`](docs/06_exp3_german_application.md).

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
bash demo/run_demo.sh
```

Every figure quoted in an active doc is re-derived by `tests/test_reported_numbers.py`; every
figure quoted in an archived results note by `archive/checks/test_archived_numbers.py`.
