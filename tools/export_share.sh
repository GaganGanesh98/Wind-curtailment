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
INCLUDE=(README.md requirements.txt docs figures results src tests artifacts
         data/reference demo/run_demo.sh demo/run_full_suite.sh)
# The λ-grid edit, uncommitted on purpose (docs/Q_STOP_R1.md), and editor settings.
KNOWN_DIRTY=(" M src/censoring/m2.py" " M src/censoring/tb_methods.py"
             "?? src/censoring/tb_lambda_widening.py" "?? .vscode/")

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

# 2. literature/ from the working tree, files over the limit left out.
if [ -d literature ]; then
  while IFS= read -r -d '' f; do
    EXCLUDED+=("$f ($(( $(stat -f %z "$f") / 1048576 )) MB): download from the upstream repository named in its folder's README.md")
  done < <(find literature -type f -size +"${MAX_MB}"M -print0)
  rsync -a --max-size="${MAX_MB}m" --exclude '.DS_Store' literature "$TARGET/"
fi

# 3. Never-exported items, stated so the reader knows they exist.
EXCLUDED+=("data/ except data/reference/: raw and processed data; rebuild with docs/00_START_HERE.md section 5")
EXCLUDED+=(".git/, .venv/, .claude/, __pycache__/, .pytest_cache/, demo/output/: repository and local state")
EXCLUDED+=("working-tree λ-grid edit (src/censoring/m2.py, tb_methods.py, tb_lambda_widening.py): uncommitted; committed copies in artifacts/TB_lambda/")

find "$TARGET" \( -name '__pycache__' -o -name '.DS_Store' \) -prune -exec rm -rf {} + 2>/dev/null || true
NFILES=$(find "$TARGET" -type f | wc -l | tr -d ' ')

{
  echo "Thesis share export"
  echo "export date: $(date '+%Y-%m-%d %H:%M %Z')"
  echo "commit:      $COMMIT"
  echo "branch:      $BRANCH"
  echo "file count:  $NFILES (excluding this manifest)"
  echo
  echo "Start with README.md, then docs/00_START_HERE.md."
  echo
  echo "Excluded (limit $MAX_MB MB per file):"
  for e in "${EXCLUDED[@]}"; do echo "  - $e"; done
} > "$TARGET/MANIFEST.txt"

echo "exported $NFILES files from $COMMIT to $TARGET"
echo "manifest: $TARGET/MANIFEST.txt"
