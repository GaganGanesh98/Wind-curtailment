"""Erratum regression (`docs/ERRATUM_lambda5.md`): lambda-5's truth is the TRUE potential's.

Until 16 November 2026 `score_cell` computed lambda-5's truth from the potential handed to the
bounds. These tests fail on that behaviour: scaling the scored potential must leave every
truth unchanged, lambda-5's included.
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from src.identification import lambda5_truth as l5
from src.identification.run_p3_synthetic import prepare_cell, score_cell
from src.identification.summarise_p3 import load


@pytest.fixture(scope="module")
def prep():
    return prepare_cell(0.10, 0.0, "step", 45, "homogeneous")


def _truths(prep, scale: float) -> dict:
    a = np.asarray(prep["data"].a_true_mw, dtype=float)
    p = a * scale
    c_hat = 1.0 - np.asarray(prep["data"].g_obs_mw, dtype=float) / p
    return {r["lam"]: r["truth"] for r in score_cell(prep, c_hat, p, arm="test",
                                                      stage_a_note="lambda-5 truth test")}


def test_lambda5_truth_does_not_move_with_the_scored_potential(prep):
    exact, scaled = _truths(prep, 1.0), _truths(prep, 1.5)
    assert np.isfinite(exact["L5"]) and exact["L5"] > 0
    for lam, t in exact.items():
        assert scaled[lam] == pytest.approx(t, rel=1e-12, abs=1e-12), lam


def test_stored_rows_are_rescored_against_the_true_potential():
    if not l5.ARM_O.exists():
        pytest.skip("P3 artifacts not on disk")
    o = load(l5.ARM_O)
    raw = pl.read_csv(l5.ARM_O, infer_schema_length=0).filter(pl.col("lam") == "L5")
    assert int(o.filter(pl.col("cov").is_not_null())["cov"].sum()) == 1127    # Arm O unchanged
    assert o.filter(pl.col("lam") == "L5").height == raw.height
    q1 = load(l5.REPO_ROOT / "artifacts" / "Q1" / "q1_variance_dial.csv")
    ar1 = q1.filter((pl.col("lam") == "L5") & (pl.col("noise") == "ar1"))
    assert int(ar1["cov"].sum()) == 48 and ar1.height == 54                   # was 54 of 54
