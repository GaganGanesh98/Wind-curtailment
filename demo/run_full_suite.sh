#!/usr/bin/env bash
# Full test suite, Phase S6. About four minutes on the student's laptop.
set -euo pipefail
cd "$(dirname "$0")/.."
printf '\n==== Full test suite (tests/) ====\n'
t0=$(date +%s)
.venv/bin/python -m pytest -q -p no:cacheprovider "$@"      # pytest.ini: tests/ and archive/checks/
echo "---- took $(( $(date +%s) - t0 )) s"
