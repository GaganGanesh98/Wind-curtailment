"""Experiment 4, step 2 (docs/12): L1 and L2 see only the allowed inputs, train only before the
month they score, carry the step 1 overlap flags, and ignore the price entirely."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from src.method.learned_potential import config as cfg
from src.method.learned_potential.data import ART
from src.method.learned_potential import models_gbm as gbm

OOF = {m: ART / f"oof_{m}.parquet" for m in gbm.MODELS}
need_oof = pytest.mark.skipif(not all(p.exists() for p in OOF.values()),
                              reason="step 2 out-of-fold predictions not written yet")


def _tiny(n: int = 400, seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    return pl.DataFrame({
        "f_onshore_mw": rng.uniform(100, 5000, n), "f_offshore_mw": rng.uniform(0, 500, n),
        "f_solar_mw": rng.uniform(0, 9000, n), "qh_of_day": rng.integers(0, 96, n).astype(np.int32),
        "day_of_week": rng.integers(0, 7, n).astype(np.int32), "holiday": np.zeros(n, dtype=np.int32),
        "area": rng.choice(list(cfg.AREAS), n), "price": rng.uniform(-50, 200, n),
        "y": rng.normal(0, 0.1, n), "w": rng.uniform(0.5, 2.0, n)})


def test_training_entry_point_enforces_the_allow_list():
    d = _tiny()
    with pytest.raises(ValueError, match="forbidden"):
        gbm.fit_quantiles(d, {"num_leaves": 7, "n_estimators": 5}, False,
                          names=(*cfg.ALLOWED_FEATURES, "price"))


def _permutation_check(weighted: bool) -> bool:
    d = _tiny()
    rng = np.random.default_rng(1)
    shuffled = d.with_columns(pl.Series("price", rng.permutation(d["price"].to_numpy())))
    params = {"num_leaves": 7, "n_estimators": 20}
    a = gbm.predict(gbm.fit_quantiles(d, params, weighted), d)
    b = gbm.predict(gbm.fit_quantiles(shuffled, params, weighted), shuffled)
    return bool(np.array_equal(a, b))


@pytest.mark.parametrize("weighted", [False, True])
def test_permuting_the_price_column_changes_no_prediction(weighted):
    """Run in a fresh interpreter: LightGBM and PyTorch each bundle libomp, and once another
    test has loaded torch in this process a LightGBM fit can segfault on macOS. The check is
    the same; only the process is separate."""
    import subprocess
    import sys
    code = ("import sys; from tests.test_exp4_gbm import _permutation_check; "
            f"sys.exit(0 if _permutation_check({weighted}) else 3)")
    r = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@need_oof
@pytest.mark.parametrize("model", list(gbm.MODELS))
def test_no_fold_trains_on_a_day_it_scores(model):
    o = pl.read_parquet(OOF[model])
    assert (o["berlin_date"] > o["train_last_day"]).all()
    for m, last in o.select(["month", "train_last_day"]).unique().iter_rows():
        assert date.fromisoformat(last) < date.fromisoformat(m + "-01")


@need_oof
@pytest.mark.parametrize("model", list(gbm.MODELS))
def test_overlap_flags_match_step1_exactly(model):
    o = pl.read_parquet(OOF[model]).filter(pl.col("target"))
    ov = {r["unit"]: r for r in pl.read_csv(ART / "domain_overlap.csv").iter_rows(named=True)}
    for a in cfg.AREAS:
        q = o.filter(pl.col("area") == a)
        assert q.height == ov[a]["n_target"]
        assert int((~q["overlap_ok"]).sum()) == ov[a]["n_no_overlap"]


@need_oof
@pytest.mark.parametrize("model", list(gbm.MODELS))
def test_quantiles_never_cross_and_cover_the_window(model):
    o = pl.read_parquet(OOF[model])
    q = o.select(gbm.QCOLS).to_numpy()
    assert (np.diff(q, axis=1) >= 0).all()
    assert sorted(o["month"].unique().to_list())[0] == cfg.EVAL_WINDOW[0][:7]


@need_oof
def test_fold_table_agrees_and_no_scored_month_is_trained_on():
    f = pl.read_csv(ART / "gbm_fold_training.csv")
    assert (f["n_train_recomputed"] == f["n_train_L1_stored"]).all()
    assert (f["n_train_recomputed"] == f["n_train_L2_stored"]).all()
    assert (f["target_rows_in_train"] == 0).all() and (f["rows_on_or_after_month"] == 0).all()


@need_oof
@pytest.mark.needs_data("data/processed/panel_qh.parquet")
def test_fold_table_recomputes():
    assert gbm.fold_training_table().equals(pl.read_csv(ART / "gbm_fold_training.csv"))
