"""Experiment 4, step 1 (docs/12): the input allow-list, the cross-fitting and the look-alike set."""

from __future__ import annotations

from datetime import date

import polars as pl
import pytest

from src.method.learned_potential import config as cfg
from src.method.learned_potential.data import (ART, _easter, check_features, eval_months,
                                               national_holidays, train_last_day)

SCORES = ART / "domain_scores.parquet"
FORBIDDEN = ["price_eur_mwh", "price", "theta", "s", "exposure", "depth", "runlen", "run_length",
             "hr_mw", "h", "act_onshore_mw", "g", "id_onshore_mw", "id_wind_mw", "rd_mw", "e_mw"]


@pytest.mark.parametrize("name", FORBIDDEN)
def test_allow_list_rejects_every_forbidden_column(name):
    with pytest.raises(ValueError, match="forbidden"):
        check_features(["f_onshore_mw", name])


def test_allow_list_rejects_anything_outside_it_and_accepts_itself():
    with pytest.raises(ValueError, match="outside"):
        check_features(["f_onshore_mw", "month"])
    check_features(cfg.ALLOWED_FEATURES)
    assert not set(cfg.ALLOWED_FEATURES) & cfg.FORBIDDEN_FEATURES


def test_calendar():
    assert _easter(2026) == date(2026, 4, 5) and _easter(2025) == date(2025, 4, 20)
    h = national_holidays([2026])
    assert {"2026-04-03", "2026-04-06", "2026-05-14", "2026-05-25", "2026-10-03"} <= h
    assert len(h) == 9


def test_rolling_origin_folds():
    assert eval_months()[0] == "2025-10" and eval_months()[-1] == "2026-09" and len(eval_months()) == 12
    assert train_last_day("2025-10") == "2025-09-23"          # 7-day embargo


def test_every_score_comes_from_a_classifier_that_never_saw_its_month():
    s = pl.read_parquet(SCORES).filter(pl.col("p").is_not_null())
    assert (s["p_heldout_month"] == s["month"]).all()
    assert s.filter(pl.col("valid"))["p"].null_count() == 0


def test_lookalike_rows_are_never_in_the_training_span_that_scores_them():
    s = pl.read_parquet(SCORES).filter(pl.col("lookalike") | pl.col("lookalike_aggregate"))
    assert s.height > 0
    assert (s["berlin_date"] >= cfg.EVAL_WINDOW[0]).all()
    last = s["month"].map_elements(train_last_day, return_dtype=pl.String)
    assert (s["berlin_date"] > last).all()
    assert s.filter(pl.col("lookalike"))["clean"].all()


def test_weights_only_on_clean_rows_and_clipped():
    s = pl.read_parquet(SCORES)
    c = s.filter(pl.col("clean"))
    assert c["w"].null_count() == 0 and (c["w"] <= c["w_clip"]).all() and (c["w"] > 0).all()
    assert s.filter(~pl.col("clean"))["w"].null_count() == s.filter(~pl.col("clean")).height


def test_overlap_report_matches_the_scores():
    s = pl.read_parquet(SCORES).filter(pl.col("target") & (pl.col("berlin_date") >= cfg.EVAL_WINDOW[0]))
    o = {r["unit"]: r for r in pl.read_csv(ART / "domain_overlap.csv").iter_rows(named=True)}
    assert o["pooled area rows"]["n_target"] == s.height
    assert o["pooled area rows"]["n_no_overlap"] == int((s["p"] > cfg.OVERLAP_P).sum())
