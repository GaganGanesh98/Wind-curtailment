#!/usr/bin/env bash
# Live demo: the one method and its three experiments, in seconds per step.
# Writes only to demo/output/ (git-ignored); never to artifacts/ or figures/.
#
#   bash demo/run_demo.sh          all steps
#   bash demo/run_demo.sh 3 4      chosen steps only
set -euo pipefail

cd "$(dirname "$0")/.."
PY=.venv/bin/python
OUT=demo/output
mkdir -p "$OUT"
STEPS=("$@")
[ ${#STEPS[@]} -eq 0 ] && STEPS=(1 2 3 4 5 6)
BEFORE=$(git status --porcelain -- artifacts figures)

header() { printf '\n==== Step %s: %s ====\n' "$1" "$2"; }

# data/ is not committed. Steps that read the panel print one line and continue without it;
# steps 4, 5 and 6 run from the committed artifacts.
PANEL=data/processed/panel_qh.parquet
have_panel() {
  [ -f "$PANEL" ] && return 0
  echo "skipped: needs $PANEL, see docs/00_start_here.md"
  return 1
}

step1() {
  header 1 "environment and commit"
  $PY --version
  $PY -c "import polars, numpy, scipy, cvxpy, matplotlib, pytest; print('packages ok: polars', polars.__version__, '| cvxpy', cvxpy.__version__)"
  echo "commit $(git rev-parse --short HEAD) on $(git branch --show-current)"
}

step2() {
  header 2 "experiment 1: one synthetic cell with a known truth -- interval and coverage per functional"
  have_panel || return 0
  $PY -m src.method.synthetic_scoring --smoke --out "$OUT/known_truth_cell.csv"
}

step3() {
  header 3 "experiment 2: one cell whose potential is biased by -0.047 (the operational series' bias; quality-assured: sigma 0.0610, bias -0.0326) -- plain set vs bias-robust set (B = 0.05)"
  have_panel || return 0
  $PY -m src.method.bias_robust --part demo
}

step4() {
  header 4 "experiment 3: the German results table, rebuilt from the artifacts"
  $PY -m src.experiments.doc_tables --table exp3_results
}

step5() {
  header 5 "the number checker: every figure in the active docs and the archived notes"
  $PY -m pytest tests/test_reported_numbers.py archive/checks -q -p no:cacheprovider 2>&1 | tail -2
}

step6() {
  header 6 "regenerate figures 01-09 and 13 from the committed artifacts"
  $PY -m src.figures --out "$OUT/figures"
}

for s in "${STEPS[@]}"; do
  t0=$(date +%s)
  "step$s"
  echo "---- step $s took $(( $(date +%s) - t0 )) s"
done

AFTER=$(git status --porcelain -- artifacts figures)
if [ "$BEFORE" != "$AFTER" ]; then
  echo "ERROR: the demo changed files under artifacts/ or figures/" >&2
  exit 1
fi
