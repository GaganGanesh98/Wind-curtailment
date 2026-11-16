#!/usr/bin/env bash
# Build the folder shared with the supervisor (Phase S7).
#
#   bash tools/export_share.sh TARGET_DIR
#
# Tracked files come from the committed HEAD (git archive), so the export matches the
# commit hash in MANIFEST.txt exactly. literature/ is not in git (copyright) and is
# copied from the working tree. The git repository itself is never exported.
#
# Refuses if TARGET_DIR is inside the repo, if it exists and is not empty, or if the
# working tree has uncommitted changes other than the known λ-grid edit.
set -euo pipefail

MAX_MB=50
# The active tree only, plus archive/README.md and the archived documents the active docs
# cite (pre-registrations and results notes), and the few archived files active code reads.
INCLUDE=(README.md requirements.txt pytest.ini docs figures src tests artifacts data/reference
         demo/run_demo.sh demo/run_full_suite.sh archive/README.md archive/docs
         archive/results/01_sample_size.csv archive/results/02_bias_by_price_band.csv
         archive/results/02_worst_days_de.csv archive/artifacts/Q6/q6a_cells.csv
         archive/artifacts/Q6/q6b_summary.csv)
# The λ-grid edit, uncommitted on purpose (docs/Q_STOP_R1.md), and editor settings.
KNOWN_DIRTY=(" M src/method/stage_a/reservation_depth_model.py" " M archive/src/censoring/tb_methods.py"
             "?? src/censoring/" "?? .vscode/")

[ $# -eq 1 ] || { echo "usage: bash tools/export_share.sh TARGET_DIR" >&2; exit 2; }
REPO=$(cd "$(dirname "$0")/.." && pwd -P)
cd "$REPO"

PARENT=$(cd "$(dirname "$1")" 2>/dev/null && pwd -P) \
  || { echo "REFUSED: the parent folder of $1 does not exist" >&2; exit 1; }
TARGET="$PARENT/$(basename "$1")"
case "$TARGET/" in
  "$REPO"/*) echo "REFUSED: $TARGET is inside the repository $REPO" >&2; exit 1 ;;
esac
mkdir -p "$TARGET"
if [ -n "$(ls -A "$TARGET")" ]; then
  echo "REFUSED: $TARGET is not empty" >&2; exit 1
fi

dirty=$(git status --porcelain | while IFS= read -r line; do
  known=0
  for k in "${KNOWN_DIRTY[@]}"; do [ "$line" = "$k" ] && known=1; done
  [ $known -eq 0 ] && echo "$line"
done || true)
if [ -n "$dirty" ]; then
  echo "REFUSED: uncommitted changes other than the known λ-grid edit:" >&2
  echo "$dirty" >&2
  echo "Commit them, or move them out of the repo, then re-run." >&2
  rmdir "$TARGET" 2>/dev/null || true
  exit 1
fi

COMMIT=$(git rev-parse HEAD)
BRANCH=$(git branch --show-current)
LIMIT=$((MAX_MB * 1024 * 1024))
EXCLUDED=()

# 1. Tracked files at HEAD.
paths=()
for p in "${INCLUDE[@]}"; do git cat-file -e "HEAD:$p" 2>/dev/null && paths+=("$p"); done
git archive --format=tar HEAD -- "${paths[@]}" | tar -x -C "$TARGET"
while IFS= read -r -d '' f; do
  rel=${f#"$TARGET"/}
  EXCLUDED+=("$rel ($(( $(stat -f %z "$f") / 1048576 )) MB): regenerate from src/ (see docs/00_START_HERE.md)")
  rm "$f"            # a copy inside the export, never the repo file
done < <(find "$TARGET" -type f -size +"${MAX_MB}"M -print0)

# 2. literature/ from the working tree. Third-party code keeps its README and code but
#    not its data/ folders; any other file over the limit is left out too.
if [ -d literature ]; then
  for d in literature/06_datasets_and_code/*/data; do
    [ -d "$d" ] || continue
    repo=$(dirname "$d")
    link=$(grep -oE 'https?://[^ )"]+' "$repo/README.md" 2>/dev/null | head -1 || true)
    EXCLUDED+=("$d/ ($(find "$d" -type f | wc -l | tr -d ' ') files, $(du -sh "$d" | cut -f1)): upstream data; obtain it from the repository behind $repo/README.md (link there: ${link:-none}); no repository URL is recorded locally")
  done
  while IFS= read -r -d '' f; do
    EXCLUDED+=("$f ($(( $(stat -f %z "$f") / 1048576 )) MB): over the size limit; obtain from its source")
  done < <(find literature -path 'literature/06_datasets_and_code/*/data' -prune -o \
                -type f -size +"${MAX_MB}"M -print0)
  rsync -a --max-size="${MAX_MB}m" --exclude '.DS_Store' \
        --exclude '/literature/06_datasets_and_code/*/data/' literature "$TARGET/"
fi

# 3. Never-exported items, stated so the reader knows they exist.
EXCLUDED+=("data/ except data/reference/: raw and processed data; rebuild with docs/00_start_here.md, \"How to run\". Without it, the tests that read the panel or the raw downloads fail in this copy; the rest pass")
EXCLUDED+=(".git/, .venv/, .claude/, __pycache__/, .pytest_cache/, demo/output/, every .DS_Store: repository and local state")
EXCLUDED+=("archive/ except README.md, docs/ and the five files the active code reads: the full archive stays in the repository")
EXCLUDED+=("working-tree λ-grid edit (src/method/stage_a/reservation_depth_model.py, archive/src/censoring/tb_methods.py, src/censoring/tb_lambda_widening.py): uncommitted; committed copies in archive/artifacts/TB_lambda/")

find "$TARGET" \( -name '__pycache__' -o -name '.DS_Store' \) -prune -exec rm -rf {} + 2>/dev/null || true
# The archived checker is not exported, so the exported suite collects tests/ only.
printf '[pytest]\n# Exported copy: archive/checks/ is not exported.\ntestpaths = tests\npythonpath = .\n' > "$TARGET/pytest.ini"
NFILES=$(find "$TARGET" -type f | wc -l | tr -d ' ')

{
  echo "Thesis share export"
  echo "export date: $(date '+%Y-%m-%d %H:%M %Z')"
  echo "commit:      $COMMIT"
  echo "branch:      $BRANCH"
  echo "file count:  $NFILES (excluding this manifest)"
  echo
  echo "Start with README.md, then docs/00_start_here.md."
  echo
  echo "Excluded (limit $MAX_MB MB per file):"
  for e in "${EXCLUDED[@]}"; do echo "  - $e"; done
} > "$TARGET/MANIFEST.txt"

echo "exported $NFILES files from $COMMIT to $TARGET"
echo "manifest: $TARGET/MANIFEST.txt"
