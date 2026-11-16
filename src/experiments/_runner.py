"""Shared helper for the three experiment runners: run a module as `python -m`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def run(module: str, *args: str) -> None:
    print(f"$ python -m {module} {' '.join(args)}".rstrip(), flush=True)
    subprocess.run([sys.executable, "-m", module, *args], cwd=REPO_ROOT, check=True)


def show(commands: list[str]) -> None:
    print("Long fits (not run here; each rewrites the committed cell-level artifacts):")
    for c in commands:
        print(f"  python -m {c}")
