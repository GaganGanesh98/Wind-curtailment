# MSc thesis: wind curtailment at negative prices in Germany

Gagan Ganesh, MSc AI/ML (Big Data), SRH Hochschule Berlin.

**Objective.** Develop and evaluate a rule-structured partial-identification framework that
uses aggregated wind generation data and estimated available power to determine which
fleet-level and cohort-level price-response quantities can be meaningfully identified, and how
their informativeness changes with uncertainty in the available-power estimate
([`docs/00_OBJECTIVE.md`](docs/00_OBJECTIVE.md)).

**Conclusions table:** [`docs/C1_conclusions_table.md`](docs/C1_conclusions_table.md).

When the German day-ahead price turns negative, many wind farms lose their market premium
(§51 EEG) and some switch off. Published data shows what the fleet produced, not what it
could have produced. This repository measures how much was held back and what fleet-level
data can and cannot reveal about who switched off. Every test was pre-registered before
its numbers existed.

**Read first:** [`docs/00_START_HERE.md`](docs/00_START_HERE.md). It has the plain-language
problem, a folder map, the experiment timeline with verdicts, an index of every doc, how to
run things, and a glossary.

Quick start:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
bash demo/run_demo.sh
```

Every figure quoted in a results note is re-derived by `tests/test_reported_numbers.py`.
Summary figures are in `figures/findings/`. The main spec is
`docs/06_pivot_mechanism_aware_censoring.md`.
