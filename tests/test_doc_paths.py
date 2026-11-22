"""Every repo path written in backticks in README.md and docs/*.md exists (Phase 7, 22 Nov 2026).

A repo path is a backticked token that contains "/" and starts with a top-level directory of
this repo. Bare file names are shorthand relative to their table and are not checked. Paths
under data/ (not committed, except data/reference/) and under demo/output/ (git-ignored, written
by the demo) are not checked. In docs/archive_mapping.md
only the new-path column is checked: the old paths are, by design, gone.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOP = {"src", "docs", "artifacts", "archive", "data", "figures", "tests", "demo", "tools", "notebooks"}
#: git-ignored output the demo creates when it runs; absent on a fresh clone by design
GENERATED = ("demo/output",)
DOCS = [REPO_ROOT / "README.md", *sorted((REPO_ROOT / "docs").glob("*.md"))]


def _paths(doc: Path) -> list[str]:
    text = doc.read_text(encoding="utf-8")
    if doc.name == "archive_mapping.md":
        cands = re.findall(r"^\| [^|]* \| [A-Z-]+ \| `([^`]+)` \|", text, re.M)
    else:
        cands = re.findall(r"`([^`\n]+)`", text)
    out = []
    for c in (c.strip() for c in cands):
        if not re.fullmatch(r"[A-Za-z0-9_.\-/]+", c) or "/" not in c:
            continue
        if c.split("/")[0] not in TOP:
            continue
        if c.startswith("data/") and not c.startswith("data/reference"):
            continue
        if c.startswith(GENERATED):
            continue
        out.append(c)
    return sorted(set(out))


CASES = [(d.relative_to(REPO_ROOT).as_posix(), p) for d in DOCS for p in _paths(d)]


def test_the_scan_finds_paths():
    assert len(CASES) > 50


@pytest.mark.parametrize("doc,path", CASES, ids=[f"{d}:{p}" for d, p in CASES])
def test_backticked_path_exists(doc, path):
    assert (REPO_ROOT / path.rstrip("/")).exists(), f"{doc} cites `{path}`, which does not exist"
