"""Tests for T-B resume (9 Nov 2026).

The `Writer` opens with mode "w" and its docstring calls itself "append-as-you-go",
which means flush-as-you-go, not append-to-an-existing-file. A plain re-run of
`run_tb.py --pass primary` therefore TRUNCATES the partial results. These tests pin
the opt-in append mode and the completed-cell detection that resume depends on.
"""

from __future__ import annotations

import csv

import pytest

from src.censoring.run_reduced_grid import Writer
from src.censoring.run_tb import cell_key, completed_cells

FIELDS = ("censoring_rate", "gamma", "r_shape", "seed", "method", "int_abs_r")
METHODS = ("M2", "B3-CV", "B6")


def _row(rate, gamma, shape, seed, method, val=0.1):
    return dict(censoring_rate=rate, gamma=gamma, r_shape=shape, seed=seed,
                method=method, int_abs_r=val)


def _write_cells(path, cells, methods=METHODS, append=False):
    w = Writer(path, append=append)
    for (rate, gamma, shape, seed) in cells:
        for m in methods:
            w.write(_row(rate, gamma, shape, seed, m))
    w.close()


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_default_still_truncates(tmp_path):
    """The existing behaviour must not change for any caller that doesn't opt in."""
    p = tmp_path / "out.csv"
    _write_cells(p, [(0.1, 0.0, "step", 45)])
    assert len(_read(p)) == 3
    _write_cells(p, [(0.2, 0.5, "half", 46)])          # append defaults to False
    rows = _read(p)
    assert len(rows) == 3 and rows[0]["censoring_rate"] == "0.2"


def test_append_preserves_existing_rows(tmp_path):
    p = tmp_path / "out.csv"
    _write_cells(p, [(0.1, 0.0, "step", 45)])
    _write_cells(p, [(0.2, 0.5, "half", 46)], append=True)
    rows = _read(p)
    assert len(rows) == 6
    assert rows[0]["censoring_rate"] == "0.1"
    assert rows[3]["censoring_rate"] == "0.2"
    assert sum(r["censoring_rate"] == "0.1" for r in rows) == 3


def test_append_writes_no_second_header(tmp_path):
    p = tmp_path / "out.csv"
    _write_cells(p, [(0.1, 0.0, "step", 45)])
    _write_cells(p, [(0.2, 0.5, "half", 46)], append=True)
    assert p.read_text().count("censoring_rate,gamma") == 1


def test_append_to_missing_file_behaves_like_a_fresh_run(tmp_path):
    p = tmp_path / "out.csv"
    _write_cells(p, [(0.1, 0.0, "step", 45)], append=True)
    assert len(_read(p)) == 3


def test_append_refuses_on_header_mismatch(tmp_path):
    p = tmp_path / "out.csv"
    p.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    w = Writer(p, append=True)
    with pytest.raises(ValueError, match="header does not match"):
        w.write(_row(0.1, 0.0, "step", 45, "M2"))


def test_completed_cells_finds_whole_cells(tmp_path):
    p = tmp_path / "out.csv"
    _write_cells(p, [(0.1, 0.0, "step", 45), (0.2, 1.0, "logistic", 46)])
    done = completed_cells(p, len(METHODS))
    assert done == {("0.1", "0.0", "step", "45"), ("0.2", "1.0", "logistic", "46")}
    assert cell_key(0.2, 1.0, "logistic", 46) in done


def test_completed_cells_raises_on_a_partial_cell(tmp_path):
    """A file that stopped mid-cell must not be resumed silently."""
    p = tmp_path / "out.csv"
    w = Writer(p)
    for m in METHODS:
        w.write(_row(0.1, 0.0, "step", 45, m))
    w.write(_row(0.2, 1.0, "logistic", 46, "M2"))      # 1 of 3 -- partial
    w.close()
    with pytest.raises(ValueError, match="partially written"):
        completed_cells(p, len(METHODS))


def test_completed_cells_on_missing_file(tmp_path):
    assert completed_cells(tmp_path / "nope.csv", 3) == set()


def test_the_real_tb_file_never_duplicates_a_cell():
    """Integrity of results/21_tb_primary.csv at whatever stage the run has reached.

    Replaces an assertion that pinned the file at 82 complete cells (9 Nov 2026).
    That was a snapshot of a run in progress, and the resume run completed it to 135,
    so the test failed for the right reason: the world moved. How far the run has got
    is not a property worth asserting. What is: appending must never duplicate a row,
    and no cell may hold more methods than the grid defines. Both hold while a run is
    in flight, so this does not break if the suite is run mid-grid -- only the cell
    currently being written may be short.
    """
    import collections
    import csv
    from pathlib import Path

    p = Path(__file__).resolve().parents[1] / "archive" / "results" / "21_tb_primary.csv"
    if not p.exists():
        pytest.skip("21_tb_primary.csv not present")
    with open(p, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        pytest.skip("21_tb_primary.csv holds only a header")

    key = lambda r: (r["censoring_rate"], r["gamma"], r["r_shape"], r["seed"])
    pairs = collections.Counter((key(r), r["method"]) for r in rows)
    per_cell = collections.Counter(key(r) for r in rows)

    assert max(pairs.values()) == 1, (
        f"{sum(n - 1 for n in pairs.values() if n > 1)} duplicated (cell, method) "
        f"row(s) -- an append wrote over a cell that was already there"
    )
    assert max(per_cell.values()) <= 7, "a cell holds more than the 7 T-B methods"
    assert len(per_cell) <= 135, f"{len(per_cell)} cells exceeds the 135 in the grid"
    short = [k for k, n in per_cell.items() if n != 7]
    assert len(short) <= 1, f"{len(short)} incomplete cells, expected at most 1: {short[:5]}"
