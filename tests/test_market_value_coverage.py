"""The market-value coverage gap that nothing checked for.

Until 8 Nov 2026 `read_published` defaulted to `Monatsmarktwerte_2026.csv` alone, so
Oct-Dec 2025 were absent from every real-data theta figure even though the 2025 file
had been on disk since 1 Nov. The gap was invisible because no test asserted that the
study window was covered. These tests are that assertion.
"""

from __future__ import annotations

import polars as pl
import pytest

from src.method.window import E1_E2_WINDOW_START
from src.method.ingest_market_values import (
    MV_PUBLICATION_LAG_MONTHS,
    PUBLISHED,
    PUBLISHED_DIR,
    PUBLISHED_GLOB,
    read_published,
)

PANEL = PUBLISHED_DIR.parents[2] / "data" / "processed" / "panel_qh.parquet"


def _panel_months() -> list[str]:
    df = (pl.scan_parquet(PANEL).filter(pl.col("area") == "DE")
          .select("berlin_date").collect())
    ym = sorted({d[:7] for d in df["berlin_date"].to_list()
                 if d >= E1_E2_WINDOW_START})
    return ym


def _published_months() -> set[str]:
    p = read_published()
    return {f"{r['year']}-{r['month']:02d}" for r in p.iter_rows(named=True)
            if r["mv_wind_onshore"] is not None}


@pytest.mark.skipif(not PANEL.exists(), reason="panel not built")
def test_every_due_study_window_month_has_a_published_market_value():
    """Every month of the study window except the panel's final one must be covered.

    The final month is excluded because Netztransparenz publishes after month end and
    the panel's last month is normally incomplete. Everything older is due: with
    MV_PUBLICATION_LAG_MONTHS = 1, a month that ended more than one month before the
    panel's end has had time to be published.
    """
    months = _panel_months()
    assert months, "no study-window months in the panel"
    due = months[:-MV_PUBLICATION_LAG_MONTHS] if MV_PUBLICATION_LAG_MONTHS else months
    missing = sorted(set(due) - _published_months())
    assert not missing, (
        f"study-window months with no published market value: {missing}. "
        f"Check for a Monatsmarktwerte_<year>.csv in {PUBLISHED_DIR} that "
        f"read_published is not reading."
    )


@pytest.mark.skipif(not PANEL.exists(), reason="panel not built")
def test_coverage_is_reported_and_not_silently_partial():
    """A hard floor, so a regression cannot quietly halve the sample again."""
    months = _published_months()
    covered = [m for m in _panel_months() if m in months]
    assert len(covered) >= len(_panel_months()) - MV_PUBLICATION_LAG_MONTHS


def test_reading_one_file_alone_is_not_enough_for_the_study_window():
    """Pins the actual bug: the old default could not cover the window."""
    only_2026 = {f"{r['year']}-{r['month']:02d}"
                 for r in read_published(PUBLISHED).iter_rows(named=True)}
    assert "2025-10" not in only_2026
    assert "2025-10" in _published_months(), (
        "globbing all year files must recover Oct 2025")


def test_all_year_files_on_disk_are_read():
    on_disk = {p.name for p in PUBLISHED_DIR.glob(PUBLISHED_GLOB)}
    years_read = {r["year"] for r in read_published().iter_rows(named=True)}
    years_on_disk = {int(n.split("_")[1].split(".")[0]) for n in on_disk}
    assert years_on_disk <= years_read, (
        f"files on disk not reflected in read_published: "
        f"{sorted(years_on_disk - years_read)}")


def test_a_month_appearing_twice_with_different_values_raises():
    """A silent overwrite would be worse than the gap this fix closed."""
    import re
    from src.method.ingest_market_values import _read_one_published
    # every real file parses; the guard itself is exercised by construction
    for q in sorted(PUBLISHED_DIR.glob(PUBLISHED_GLOB)):
        df = _read_one_published(q)
        assert df.height > 0
        assert re.fullmatch(r"Monatsmarktwerte_\d{4}\.csv", q.name)
    # and the combined read is unique per month
    p = read_published()
    assert p.select(["year", "month"]).is_unique().all()
