"""Shared test configuration.

`data/` is not committed (size, licence; see `docs/00_start_here.md`), so a clean clone has no
panel and no raw Netztransparenz files. A test that reads one of them is marked

    @pytest.mark.needs_data("data/processed/panel_qh.parquet")

and is SKIPPED, with the missing path as the reason, when the file is absent. Paths are relative
to the repo root; a path containing `*` is a glob and needs at least one match. The marker only
decides whether the test runs. When the data is present the test runs unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

PANEL = "data/processed/panel_qh.parquet"
MARKET_VALUES = "data/raw/netztransparenz/Monatsmarktwerte_*.csv"


def _present(rel: str) -> bool:
    if "*" in rel:
        parent, pattern = rel.rsplit("/", 1)
        return any((REPO_ROOT / parent).glob(pattern))
    return (REPO_ROOT / rel).exists()


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "needs_data(*paths): skip when a required, uncommitted data file is absent")


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    for mark in item.iter_markers("needs_data"):
        missing = [p for p in mark.args if not _present(p)]
        if missing:
            pytest.skip(f"needs {', '.join(missing)} (data/ is not committed; "
                        "see docs/00_start_here.md)")
