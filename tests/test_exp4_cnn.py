"""Experiment 4, step 3 (docs/12): N1 sees only the allowed inputs, ignores the price, and its
process never loads LightGBM. The training checks run in fresh interpreters: PyTorch and
LightGBM each bundle libomp, and loading both in one process can crash on macOS."""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from src.method.learned_potential import config as cfg
from src.method.learned_potential.data import ART

ROOT = Path(__file__).resolve().parents[1]
OOF = ART / "oof_N1.parquet"
need_oof = pytest.mark.skipif(not OOF.exists(), reason="N1 out-of-fold predictions not written yet")


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)


def _tiny(n: int = 600, seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    ts = 1_700_000_000_000 + np.arange(n) * 900_000
    return pl.DataFrame({
        "area": ["Amprion"] * n, "ts_utc": ts, "berlin_date": ["2026-01-01"] * n,
        "f_onshore_mw": rng.uniform(100, 3000, n), "f_offshore_mw": np.zeros(n),
        "f_solar_mw": rng.uniform(0, 9000, n), "qh_of_day": (np.arange(n) % 96).astype(np.int32),
        "day_of_week": ((np.arange(n) // 96) % 7).astype(np.int32), "holiday": np.zeros(n, dtype=np.int32),
        "price": rng.uniform(-50, 200, n), "y": rng.normal(0, 0.1, n).astype(np.float32),
        "w": rng.uniform(0.5, 2.0, n).astype(np.float32)})


def _permutation_check() -> bool:
    from src.method.learned_potential import models_cnn as cnn

    def fit_predict(df):
        ctx = {"Amprion": (df["ts_utc"].to_numpy(), df.select(cnn.SERIES).to_numpy().astype(np.float32).T)}
        scales = {a: [1000.0, 1.0, 1000.0] for a in cfg.AREAS}
        X, S, ok = cnn.tensors(df, ctx, scales)
        y, w = df["y"].to_numpy(), df["w"].to_numpy()
        m, _, _ = cnn.train_model(X[ok][:400], S[ok][:400], y[ok][:400], w[ok][:400],
                                  X[ok][400:], S[ok][400:], y[ok][400:], w[ok][400:], 2, 8, max_epochs=2)
        return cnn.predict(m, X[ok], S[ok])
    d = _tiny()
    rng = np.random.default_rng(1)
    shuffled = d.with_columns(pl.Series("price", rng.permutation(d["price"].to_numpy())))
    return bool(np.array_equal(fit_predict(d), fit_predict(shuffled)))


def test_permuting_the_price_column_changes_no_n1_prediction():
    r = _run("import sys; from tests.test_exp4_cnn import _permutation_check; "
             "sys.exit(0 if _permutation_check() else 3)")
    assert r.returncode == 0, r.stdout + r.stderr


def test_n1_module_never_loads_lightgbm():
    r = _run("import sys; import src.method.learned_potential.models_cnn as m; "
             "m.build(2, 8); sys.exit(3 if 'lightgbm' in sys.modules else 0)")
    assert r.returncode == 0, r.stdout + r.stderr


def test_n1_inputs_go_through_the_allow_list():
    r = _run("import sys; from tests.test_exp4_cnn import _tiny; "
             "from src.method.learned_potential import models_cnn as cnn\n"
             "try:\n    cnn.tensors(_tiny(), {}, {}, names=('f_onshore_mw', 'price'))\n"
             "except ValueError as e:\n    sys.exit(0 if 'forbidden' in str(e) else 4)\n"
             "sys.exit(3)")
    assert r.returncode == 0, r.stdout + r.stderr


@need_oof
def test_no_n1_fold_trains_on_a_day_it_scores():
    o = pl.read_parquet(OOF)
    assert (o["berlin_date"] > o["train_last_day"]).all()
    for m, last in o.select(["month", "train_last_day"]).unique().iter_rows():
        assert date.fromisoformat(last) < date.fromisoformat(m + "-01")


@need_oof
def test_n1_overlap_flags_match_step1_exactly():
    o = pl.read_parquet(OOF).filter(pl.col("target"))
    ov = {r["unit"]: r for r in pl.read_csv(ART / "domain_overlap.csv").iter_rows(named=True)}
    for a in cfg.AREAS:
        q = o.filter(pl.col("area") == a)
        assert q.height == ov[a]["n_target"]
        assert int((~q["overlap_ok"]).sum()) == ov[a]["n_no_overlap"]


@need_oof
def test_n1_quantiles_never_cross():
    o = pl.read_parquet(OOF)
    q = o.select([c for c in o.columns if c.startswith("q") and c[1:].isdigit()]).to_numpy()
    assert (np.diff(q, axis=1) >= 0).all()


TRACE = ART / "cnn_loss_trace.csv"
need_trace = pytest.mark.skipif(not TRACE.exists(), reason="N1 loss trace not written yet")


def test_trace_pattern_rule():
    from src.method.learned_potential.report import trace_pattern
    assert trace_pattern([1.00, 0.99, 0.995, 1.005], 2) == "flat"            # at most 1.5% above best
    assert trace_pattern([1.2, 1.0, 1.01, 1.03, 1.05], 2) == "rising after the best epoch"
    assert trace_pattern([1.2, 1.0, 1.10, 1.02, 1.08], 2) == "unstable"


@need_trace
def test_trace_summary_regenerates_and_matches_the_run():
    from src.method.learned_potential import report
    assert report.trace_summary().equals(pl.read_csv(report.TRACE_SUMMARY))
    s = pl.read_csv(report.TRACE_SUMMARY)
    sel = pl.read_csv(ART / "cnn_selection.csv")
    oof = pl.read_parquet(OOF).group_by("month").agg(pl.col("best_epoch").first())
    for r in sel.iter_rows(named=True):
        q = s.filter((pl.col("fit") == "selection") & (pl.col("layers") == r["layers"])
                     & (pl.col("channels") == r["channels"])).row(0, named=True)
        assert q["best_epoch"] == r["best_epoch"] and q["val_best"] == r["val_loss"]
    for m, be in oof.iter_rows():
        assert s.filter(pl.col("fit") == m)["best_epoch"][0] == be


@need_trace
def test_validation_window_is_the_last_28_days_before_the_embargo():
    t = pl.read_csv(TRACE).select(["fit", "fit_last_day", "val_first_day", "val_last_day"]).unique()
    from src.method.learned_potential.data import train_last_day
    for r in t.filter(pl.col("fit") != "selection").iter_rows(named=True):
        assert r["val_last_day"] == train_last_day(r["fit"])
        assert r["fit_last_day"] < r["val_first_day"]
        assert (date.fromisoformat(r["val_last_day"]) - date.fromisoformat(r["val_first_day"])).days == 27


@need_oof
def test_selection_rule_and_s2_outcome():
    from src.method.learned_potential import report
    assert report.selected_model() == "L2"
    b = report._agg("L2", "bias")
    assert not (b["lo"] >= -cfg.S2_HALF_WIDTH and b["hi"] <= cfg.S2_HALF_WIDTH)


@need_trace
def test_figure_14_data_matches_the_trace():
    from src import figures as mf
    committed = pl.read_csv(ROOT / "figures" / "14_exp4_n1_loss_curves_data.csv")
    fresh = pl.read_csv(mf.cnn_trace_data().write_csv().encode())
    assert fresh.equals(committed)
