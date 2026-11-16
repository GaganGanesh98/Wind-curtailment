"""Every figure quoted in an active doc, re-derived from the artifacts, under pytest.

    pytest tests/test_reported_numbers.py -q
    python tests/test_reported_numbers.py        # the same checks, as a CLI

Each check is (name, got, want, tolerance); the tolerance is the rounding the document
uses. Archived results notes are checked by archive/checks/test_archived_numbers.py, which
the suite also collects (pytest.ini). The zero-row guard is on here too.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import polars as pl
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_DOCS = ("README.md",)
_SKIP = re.compile(r"<!-- numbers-check: skip -->.*?<!-- /numbers-check -->", re.S)
_CODE = re.compile(r"```.*?```|`[^`\n]*`|\]\([^)]*\)", re.S)
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    return {m.group().rstrip(",") for m in _NUM.finditer(text)}


def _trace_checks():
    """Every number in an active doc must appear in a source note (archived results notes,
    or the active docs' own tables). Paths and code in backticks, and marked blocks, are exempt."""
    sources = sorted((REPO_ROOT / "archive" / "docs").glob("*.md"))
    known = set().union(*(_numbers(p.read_text(encoding="utf-8")) for p in sources))
    out = []
    for d in ACTIVE_DOCS:
        p = REPO_ROOT / d
        if not p.exists():
            continue
        text = _CODE.sub(" ", _SKIP.sub(" ", p.read_text(encoding="utf-8")))
        for n in sorted(_numbers(text)):
            out.append((f"{d} number {n} appears in a source note", float(n in known), 1.0, 0))
    return out


# --------------------------------------------------------------------- zero-row guard
# A check must never pass on nothing (16 Nov 2026: a V1 check passed because a string
# filter on a boolean column matched no row, and `.all()` of nothing is True). While the
# checks are collected, every DataFrame.filter that selects zero rows, and every
# Series.all()/.any() over an empty series, called from this file, raises EmptySelection
# naming the line. A check
# whose honest answer is "zero rows" counts them with `_count`, which never selects.


class EmptySelection(AssertionError):
    """A check's filter selected no row, or reduced an empty series."""


def _count(df: pl.DataFrame, expr: pl.Expr) -> int:
    """Rows of `df` where `expr` holds -- a count that may legitimately be zero."""
    return int(df.select(expr.sum()).item())


def _where() -> str:
    import traceback
    frames = [f for f in traceback.extract_stack()[:-2]
              if f.filename.endswith(("test_reported_numbers.py",)) or "/src/" in f.filename]
    f = frames[-1] if frames else None
    return f"{f.filename.rsplit('/', 1)[-1]}:{f.lineno}: {f.line}" if f else "unknown"


def _guarded(fn):
    """Run `fn` with the zero-row guard on, and always restore polars afterwards."""
    orig_filter, orig_all, orig_any = pl.DataFrame.filter, pl.Series.all, pl.Series.any

    def from_checker() -> bool:
        # Only selections written in this file are checks; filters inside the loaders and
        # summarisers a check calls into may legitimately be empty and are not guarded.
        return sys._getframe(2).f_code.co_filename == __file__

    def filt(self, *a, **k):
        r = orig_filter(self, *a, **k)
        if r.height == 0 and self.height > 0 and from_checker():
            raise EmptySelection(f"filter selected 0 of {self.height} rows at {_where()}")
        return r

    def red(orig):
        def g(self, *a, **k):
            if self.len() == 0 and from_checker():
                raise EmptySelection(f"{orig.__name__}() of an empty series at {_where()}")
            return orig(self, *a, **k)
        return g
    pl.DataFrame.filter, pl.Series.all, pl.Series.any = filt, red(orig_all), red(orig_any)
    try:
        return fn()
    finally:
        pl.DataFrame.filter, pl.Series.all, pl.Series.any = orig_filter, orig_all, orig_any


def _collect():
    out = _trace_checks()
    return out, []


_CHECKS, _SKIPPED = _guarded(_collect)


@pytest.mark.parametrize("name,got,want,tol", _CHECKS or [("no checks", 0, 0, 0)],
                         ids=[c[0] for c in _CHECKS] or ["none"])
def test_quoted_figure_reproduces(name, got, want, tol):
    """A figure quoted in an active doc must still come out of the artifacts."""
    assert abs(float(got) - float(want)) <= tol, f"{name}: got {got!r}, the doc quotes {want!r}"


def test_the_checker_is_actually_checking_something():
    assert len(_CHECKS) >= 1, f"only {len(_CHECKS)} checks collected"


def test_zero_row_guard_bites_and_cleans_up():
    df = pl.DataFrame({"x": [1, 2, 3], "flag": [True, False, True]})
    with pytest.raises(EmptySelection):
        _guarded(lambda: df.filter(pl.col("flag").cast(pl.String) == "True"))
    with pytest.raises(EmptySelection):
        _guarded(lambda: df["x"].head(0).all())
    assert _guarded(lambda: _count(df, pl.col("x") > 5)) == 0
    assert df.filter(pl.col("x") > 5).height == 0


def main() -> None:
    checks, _ = _guarded(_collect)
    bad = sum(abs(float(g) - float(w)) > t for _, g, w, t in checks)
    for name, got, want, tol in checks:
        print(f"{'ok  ' if abs(float(got) - float(want)) <= tol else 'FAIL'}  {name:<60} {got!r:>12}  quoted {want!r}")
    print(f"\n{bad} mismatch(es)" if bad else f"\nevery quoted figure reproduces ({len(checks)} checks)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
