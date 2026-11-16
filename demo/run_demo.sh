#!/usr/bin/env bash
# Live demo, Phases S6 and C3. Seven steps, each under two minutes on the student's laptop.
# Writes only to demo/output/ (git-ignored); never to results/ or artifacts/.
#
#   bash demo/run_demo.sh          all steps
#   bash demo/run_demo.sh 2 4      chosen steps only
set -euo pipefail

cd "$(dirname "$0")/.."
PY=.venv/bin/python
OUT=demo/output
mkdir -p "$OUT"
STEPS=("$@")
[ ${#STEPS[@]} -eq 0 ] && STEPS=(1 2 3 4 5 6 7)
BEFORE=$(git status --porcelain -- results artifacts)

header() { printf '\n==== Step %s: %s ====\n' "$1" "$2"; }

step1() {
  header 1 "check the environment: Python, packages, data on disk, git commit"
  $PY --version
  $PY -c "import polars, numpy, scipy, cvxpy, matplotlib, pytest; print('packages ok: polars', polars.__version__, '| numpy', numpy.__version__, '| cvxpy', cvxpy.__version__)"
  for f in data/processed/panel_qh.parquet artifacts/P3/p3_synthetic_arm_o.csv artifacts/Q1/q1_summary_by_level.csv; do
    if [ -e "$f" ]; then echo "present  $f"; else echo "MISSING  $f"; fi
  done
  echo "commit   $(git rev-parse --short HEAD) on $(git branch --show-current)"
}

step2() {
  header 2 "re-run the kill test on the committed window and print the Germany table"
  mkdir -p "$OUT/kill_test"
  $PY - "$OUT/kill_test" <<'EOF' > "$OUT/kill_test/log.txt"
import sys
sys.path.insert(0, "src")
import polars as pl
import kill_test as k
# The panel now starts 2024-01-01; the kill test's committed window starts 2025-10-01.
full = k.load
k.load = lambda: full().filter(pl.col("berlin_date") >= "2025-10-01")
k.RESULTS_DIR = sys.argv[1]
k.main()
EOF
  $PY - "$OUT/kill_test" <<'EOF'
import sys, filecmp
import polars as pl
d = pl.read_csv(f"{sys.argv[1]}/02_bias_by_price_band.csv").filter(pl.col("area") == "DE")
with pl.Config(tbl_rows=10, tbl_hide_dataframe_shape=True, tbl_hide_column_data_types=True):
    print(d.select(["price_band_eur_mwh", "qhs", "days", "mean_e_mw", "ci_lo_mw", "ci_hi_mw"]))
for f in ("01_sample_size", "02_bias_by_price_band", "02_overall_negative_qh_bias",
          "02_robustness_de", "02_worst_days_de"):
    same = filecmp.cmp(f"results/{f}.csv", f"{sys.argv[1]}/{f}.csv", shallow=False)
    print(f"{'identical to' if same else 'DIFFERS FROM'} results/{f}.csv")
EOF
}

step3() {
  header 3 "re-derive every figure quoted in the results notes"
  $PY -m pytest tests/test_reported_numbers.py -q -p no:cacheprovider 2>&1 | tail -3
}

step4() {
  header 4 "one synthetic cell end to end: true response, identified set, coverage"
  $PY -m src.method.synthetic_scoring --smoke --out "$OUT/p3_smoke_cell.csv"
}

step5() {
  header 5 "regenerate the findings figures from the committed artifacts"
  $PY -m src.figures --out "$OUT/findings"
}

step6() {
  header 6 "print the experiment timeline"
  awk '/^## 3\. Experiment timeline/{p=1} /^## 4\./{p=0} p' docs/00_START_HERE.md
}

step7() {
  header 7 "print the conclusions table: what public data can and cannot tell us"
  $PY -m src.experiments.exp3_results_table --print
}

for s in "${STEPS[@]}"; do
  t0=$(date +%s)
  "step$s"
  echo "---- step $s took $(( $(date +%s) - t0 )) s"
done

AFTER=$(git status --porcelain -- results artifacts)
if [ "$BEFORE" != "$AFTER" ]; then
  echo "ERROR: the demo changed files under results/ or artifacts/" >&2
  exit 1
fi
