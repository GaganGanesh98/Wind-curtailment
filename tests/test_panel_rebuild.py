"""The rebuilt panel must not disturb a single pre-existing row.

Stage 1.1's condition: extending the panel back to 2024-01-01 adds history and
changes nothing from 2025-10-01 onwards. Every committed result -- the v1.8 gate, the
kill test, 4a-response, 4a-proper, the Nr. 5.1 check -- was computed on those rows, so
a silent change there would invalidate them all without any of them failing visibly.

Compared against a pre-rebuild copy kept in the session scratchpad. When that copy is
absent the test SKIPS rather than passes, so it can never be mistaken for a check that
ran.
"""

from __future__ import annotations

import os
from pathlib import Path

import polars as pl
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PANEL = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"
PRE = Path(os.environ.get(
    "PANEL_PRE_REBUILD",
    "/private/tmp/claude-501/-Users-gagan-msc-thesis-wind-curtailment/"
    "ec908bf9-085b-4fed-b0b8-bbb1c96d2eef/scratchpad/panel_qh.PRE_REBUILD.parquet"))
CUTOVER = "2025-10-01"


@pytest.mark.skipif(not PRE.exists(), reason="no pre-rebuild panel copy to compare")
def test_every_row_from_the_cutover_is_byte_identical():
    old = pl.read_parquet(PRE).sort(["area", "ts_utc"])
    new = (pl.read_parquet(PANEL).filter(pl.col("berlin_date") >= CUTOVER)
             .sort(["area", "ts_utc"]))
    assert new.height == old.height, (
        f"row count changed from {CUTOVER}: {old.height:,} -> {new.height:,}")
    assert new.columns == old.columns
    for col in old.columns:
        a, b = old[col], new[col]
        assert a.equals(b), f"column {col!r} changed from {CUTOVER} onwards"


@pytest.mark.skipif(not PRE.exists(), reason="no pre-rebuild panel copy to compare")
def test_the_rebuild_only_added_history():
    old = pl.read_parquet(PRE)
    new = pl.read_parquet(PANEL)
    assert new.height > old.height
    added = new.filter(pl.col("berlin_date") < CUTOVER)
    assert added.height == new.height - old.height
    assert added["berlin_date"].min() == "2024-01-01"
    assert added["berlin_date"].max() < CUTOVER


@pytest.mark.needs_data("data/processed/panel_qh.parquet")
def test_pre_october_2025_prices_are_hourly_repeated_not_missing():
    """The resolution finding Stage 1 rests on, asserted on the real panel."""
    import numpy as np

    df = (pl.read_parquet(PANEL)
            .filter((pl.col("area") == "DE") & (pl.col("berlin_date") < CUTOVER))
            .sort("ts_utc"))
    p = df["price_eur_mwh"].to_numpy()
    hour = df["ts_utc"].to_numpy().astype("int64") // 3_600_000
    uniq, inv = np.unique(hour, return_inverse=True)
    spread = np.zeros(len(uniq))
    mx = np.full(len(uniq), -np.inf); mn = np.full(len(uniq), np.inf)
    np.maximum.at(mx, inv, p); np.minimum.at(mn, inv, p)
    spread = mx - mn
    ok = np.isfinite(spread)
    assert ok.sum() > 8000
    assert (spread[ok] == 0).mean() > 0.999, (
        "pre-Oct-2025 prices should be the hourly value repeated into all four "
        "quarter-hours")
    assert np.isfinite(p).mean() > 0.99, "and present, not missing"
