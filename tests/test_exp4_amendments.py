"""docs/12 amendments: the pre-registered text above them is untouched, and the amendment's
numbers are what the step 1 artifacts say."""

from __future__ import annotations

import subprocess
from pathlib import Path

import polars as pl
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DOC = REPO_ROOT / "docs" / "12_learned_potential_preregistration.md"
PREREG_COMMIT = "55bcef3"


def _at_commit() -> str:
    try:
        return subprocess.check_output(["git", "show", f"{PREREG_COMMIT}:docs/{DOC.name}"],
                                       cwd=REPO_ROOT, text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("git history not available")


def test_preregistered_text_above_the_amendment_is_byte_identical():
    now = DOC.read_text(encoding="utf-8")
    prefix = now[:now.index("## Amendment 1 (22 November 2026): limited overlap")]
    assert prefix == _at_commit() + "\n"


def test_design_block_is_byte_identical_to_the_preregistered_one():
    from src.experiments import doc_tables as dt
    assert dt.blocks(DOC.read_text(encoding="utf-8"))["exp4_design"] == dt.blocks(_at_commit())["exp4_design"]


def test_amendment_counts_match_step1():
    o = {r["unit"]: r for r in pl.read_csv(REPO_ROOT / "artifacts" / "exp4_learned_potential"
                                           / "domain_overlap.csv").iter_rows(named=True)}
    d = {r["area"]: r for r in pl.read_csv(REPO_ROOT / "artifacts" / "exp4_learned_potential"
                                           / "overlap_diagnosis.csv").iter_rows(named=True)}
    assert (o["50Hertz"]["n_no_overlap"], o["pooled area rows"]["n_no_overlap"],
            o["aggregate (mean p over the areas)"]["n_no_overlap"]) == (527, 707, 55)
    assert d["50Hertz"]["n_target_no_overlap"] == o["50Hertz"]["n_no_overlap"]
    assert round(d["50Hertz"]["share_target_with_overlap"] * 100, 1) == 74.3


def test_trim_threshold_reuses_the_overlap_constant():
    from src.method.learned_potential import config as cfg
    assert cfg.OVERLAP_TRIM_P is cfg.OVERLAP_P and cfg.PRIMARY_ESTIMAND == "trimmed"
    assert cfg.V1_BOOTSTRAP_DRAWS == 5000 and cfg.V1_TOLERANCE == 0.02
