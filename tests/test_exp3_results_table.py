"""The C1 conclusions table is exactly what the artifacts give (Phase C1).

Rebuilds `results/C1_conclusions_table.csv` and `docs/C1_conclusions_table.md` from the
committed artifacts and compares them byte for byte with the committed files. The
per-cell checks live in `tests/test_reported_numbers.py` (`_c1_checks`).
"""

from __future__ import annotations

import io

import pytest

from src.experiments import exp3_results_table as bct

pytestmark = pytest.mark.skipif(not (bct.ART / "exp3_german_application" / "monthly_bounds_cells.csv").exists(),
                                reason="Q1/Q5 artifacts not on disk")


def test_csv_rebuilds_byte_for_byte():
    buf = io.BytesIO()
    bct.build().write_csv(buf)
    assert buf.getvalue() == bct.CSV_OUT.read_bytes()


def test_markdown_rebuilds_byte_for_byte():
    assert bct.markdown(bct.build()).encode("utf-8") == bct.MD_OUT.read_bytes()


def test_quantity_rows_add_up_to_the_q5_headline():
    q = bct.build().filter(bct.pl.col("kind") == "quantity")
    assert int(q["real_H_n"].sum()) == 59 and int(q["real_F_n"].sum()) == 59
    assert int(q["real_H_k"].sum()) == 3 and int(q["real_F_k"].sum()) == 6
    assert int(q["real_H_undefined"].sum()) == 11
