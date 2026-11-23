"""Experiment 4b build (docs/24, "Build commitments"). Synthetic data for the model tests; the
ERA5 month and the MaStR fleet on disk for the physics and capacity tests (skipped if absent).
Nothing here fits on real G."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from src.method.learned_potential_v2 import config as cfg
from src.method.learned_potential_v2 import hybrid as hy
from src.method.learned_potential_v2 import physics as ph
from src.method.learned_potential_v2 import weather as we

SMALL = {"num_leaves": 7, "n_estimators": 30}
ERA5_TEST_MONTH = "2021-10"


def _synthetic(n_days: int = 60, seed: int = 0) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    days = [date(2025, 8, 1) + timedelta(days=i) for i in range(n_days)]
    rows = []
    for d in days:
        for a in cfg.AREAS:
            for h in range(24):
                ws = rng.gamma(4.0, 2.0)
                rows.append({"area": a, "berlin_date": d.isoformat(), "month": d.isoformat()[:7],
                             "hour_ms": int((date(1970, 1, 1) - date(1970, 1, 1)).days) + h,
                             "p_phys_cf": min(ws / 15.0, 1.0), "era5_ws100": ws, "era5_ws_hub": ws * 1.1,
                             "era5_dir_sin": rng.uniform(-1, 1), "era5_dir_cos": rng.uniform(-1, 1),
                             "era5_rho": rng.normal(1.22, 0.02), "era5_gust": ws * 1.4,
                             "era5_gust_ratio": 1.4, "era5_shear": rng.uniform(0.1, 0.35),
                             "era5_t2m": rng.normal(285, 5), "dwd_ws": ws * 0.6,
                             "new_cap_share": 0.02, "hour_utc": h, "month_of_year": d.month,
                             "price_eur_mwh": rng.normal(60, 40), "w": rng.uniform(0.5, 2.0)})
    d = pl.DataFrame(rows)
    return d.with_columns((pl.col("p_phys_cf").log1p() * 0.1 + pl.Series(rng.normal(0, 0.05, d.height))).alias("y"),
                          pl.lit(True).alias("clean"), pl.lit(True).alias("valid"))


# ------------------------------------------------------------------ allow-list
def test_allow_list():
    assert not set(cfg.ALLOWED_FEATURES) & cfg.FORBIDDEN_FEATURES
    assert set(cfg.FEATURE_TEXT) == set(cfg.ALLOWED_FEATURES)
    for bad in ("price_eur_mwh", "price", "h", "g", "theta", "exposure", "runlen", "f_onshore_mw",
                "da_onshore_mw", "f", "rd_any", "unit_check_fail", "y", "clean", "target"):
        with pytest.raises(ValueError):
            hy.check_features([*cfg.ALLOWED_FEATURES, bad])
    with pytest.raises(ValueError):
        hy.check_features(["not_a_feature"])
    d = _synthetic(3)
    assert hy.features(d).columns == list(cfg.ALLOWED_FEATURES)


def _in_fresh_process(fn: str) -> None:
    """Run a check that fits LightGBM in a fresh interpreter: LightGBM and PyTorch each bundle
    libomp, and once another test has loaded torch a LightGBM fit can segfault on macOS (as in
    tests/test_exp4_gbm.py). The check is the same; only the process is separate."""
    import subprocess
    import sys
    from pathlib import Path
    r = subprocess.run([sys.executable, "-c", f"from tests.test_exp4b_build import {fn}; {fn}()"],
                       cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_price_permutation_leaves_predictions_unchanged():
    _in_fresh_process("_check_price_permutation")


def test_reproducible_from_seed():
    _in_fresh_process("_check_reproducible")


def test_pipeline_runs_end_to_end_on_synthetic_rows():
    """Domain classifier, a fold of H1 and H2, P0, scores and criteria, on synthetic rows only."""
    _in_fresh_process("_check_pipeline")


def _check_price_permutation():
    d = _synthetic(40)
    perm = d.with_columns(pl.Series("price_eur_mwh", np.random.default_rng(7).permutation(d["price_eur_mwh"].to_numpy())))
    assert hy.features(d).equals(hy.features(perm))
    a = hy.predict(hy.fit_quantiles(d, SMALL, weighted=True), d)
    b = hy.predict(hy.fit_quantiles(perm, SMALL, weighted=True), perm)
    np.testing.assert_array_equal(a, b)


def _check_reproducible():
    d = _synthetic(30)
    a = hy.predict(hy.fit_quantiles(d, SMALL, weighted=False), d)
    b = hy.predict(hy.fit_quantiles(d, SMALL, weighted=False), d)
    np.testing.assert_array_equal(a, b)
    assert np.all(np.diff(a, axis=1) >= 0)                       # quantiles never cross


# ------------------------------------------------------------------ folds
def test_no_fold_scores_a_day_it_trained_on():
    start, end = date.fromisoformat(cfg.PERIOD[0]), date.fromisoformat(cfg.PERIOD[1])
    days = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
    d = pl.DataFrame({"berlin_date": days, "month": [x[:7] for x in days], "clean": [True] * len(days)})
    for m in hy.eval_months():
        tr = set(d.filter(hy.train_mask(d, m))["berlin_date"].to_list())
        sc = set(d.filter(pl.col("month") == m)["berlin_date"].to_list())
        assert tr and sc and not tr & sc
        gap = (date.fromisoformat(min(sc)) - date.fromisoformat(max(tr))).days
        assert gap > cfg.EMBARGO_DAYS
    assert hy.eval_months()[0] == cfg.EVAL_WINDOW[0][:7] and hy.eval_months()[-1] == cfg.EVAL_WINDOW[1][:7]


# ------------------------------------------------------------------ physics
def test_power_curve_shape():
    v = np.linspace(0.0, 30.0, 3001)
    for sp in (180.0, 250.0, 350.0, 450.0, 600.0):
        p = ph.power_curve(v, ph.rated_speed(sp))
        assert np.all(p[v < cfg.CUT_IN] == 0.0)
        assert np.all(p[v >= cfg.CUT_OUT] == 0.0)
        mid = (v >= cfg.CUT_IN) & (v < cfg.CUT_OUT)
        assert np.all(np.diff(p[mid]) >= 0.0)
        assert np.all((p >= 0.0) & (p <= 1.0))
        assert p[mid].max() == 1.0


def test_shear_exponent_clip_and_fallback():
    a = ph.shear_exponent(np.array([5.0, 5.0, 0.1, 5.0]), np.array([5.0 * 10 ** 0.2, 50.0, 8.0, 4.0]))
    assert a[0] == pytest.approx(0.2)
    assert a[1] == cfg.SHEAR_CLIP[1] and a[3] == cfg.SHEAR_CLIP[0] and a[2] == cfg.SHEAR_FALLBACK


def test_bilinear_interpolation():
    lat = np.array([55.0, 54.75, 54.5])                          # descending, as ERA5
    lon = np.array([6.0, 6.25, 6.5, 6.75])
    field = (2.0 * lat[:, None] + 3.0 * lon[None, :]).ravel()    # linear, so bilinear is exact
    pts_lat, pts_lon = np.array([54.6, 54.9, 56.0]), np.array([6.1, 6.6, 5.0])
    W = we.bilinear(lat, lon, pts_lat, pts_lon)
    np.testing.assert_allclose(np.asarray(W.sum(axis=1)).ravel(), 1.0)
    got = W @ field
    np.testing.assert_allclose(got[:2], 2.0 * pts_lat[:2] + 3.0 * pts_lon[:2])
    assert got[2] == pytest.approx(2.0 * 55.0 + 3.0 * 6.0)       # outside: nearest edge point


# ------------------------------------------------------------------ sets and target
def test_assemble_sets_and_target():
    panel = pl.DataFrame({"area": ["50Hertz"] * 5, "hour_ms": [0, 1, 2, 3, 4],
                          "berlin_date": ["2025-01-01"] * 5, "n_qh": [4, 4, 4, 4, 3],
                          "g": [100.0, 100.0, 100.0, 50.0, 100.0], "f": [1.0] * 5,
                          "g_pos_all": [True] * 5, "price_gt_clean_all": [True, True, True, False, True],
                          "price_lt0_any": [False, False, False, True, False]})
    weather = pl.DataFrame({"area": ["50Hertz"] * 5, "hour_ms": [0, 1, 2, 3, 4], "c_mw": [1000.0] * 5,
                            "p_phys_mw": [200.0] * 5})
    flags = pl.DataFrame({"area": ["50Hertz", "50Hertz"], "hour_ms": [1, 2],
                          "rd_any": [True, False], "unit_check_fail": [False, True]})
    d = hy.assemble(panel, weather, flags)
    assert d["clean"].to_list() == [True, False, False, False, False]
    assert d["target"].to_list() == [False, False, False, True, False]
    assert d["valid"].to_list() == [True, True, True, True, False]
    y0 = np.log((100.0 + cfg.KAPPA * 1000.0) / (200.0 + cfg.KAPPA * 1000.0))
    assert d["y"][0] == pytest.approx(y0)
    assert hy.a_hat(np.array([y0]), np.array([200.0]), np.array([1000.0]))[0] == pytest.approx(100.0)


def test_no_fit_before_inputs_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "ERA5_DIR", tmp_path)
    with pytest.raises(RuntimeError, match="ERA5 pending"):
        hy.require_inputs()


# ------------------------------------------------------------------ real inputs (no fitting)
@pytest.mark.skipif(not we.era5_path(ERA5_TEST_MONTH).exists(), reason="ERA5 test month not on disk")
def test_era5_month_check():
    c = we.check_era5(ERA5_TEST_MONTH)
    assert c["ok"] and c["hours"] == 744 and c["missing"] == 0


@pytest.fixture(scope="module")
def fleet():
    if not cfg.MASTR_PROCESSED.exists() or not (cfg.MASTR_DIR / "EinheitenWind.xml").exists():
        pytest.skip("MaStR not on disk")
    from src.method.learned_potential_v2 import fleet as fl
    return fl.fleet()


def test_capacity_matches_mastr_totals(fleet):
    from src.method.learned_potential_v2 import fleet as fl
    got = fl.capacity_mw(fleet, date(2026, 10, 31))            # the snapshot day
    p = pl.read_parquet(cfg.MASTR_PROCESSED).group_by("control_area").agg((pl.col("net_kw").sum() / 1000).alias("mw"))
    want = {r["control_area"]: r["mw"] for r in p.iter_rows(named=True)}
    for a in cfg.AREAS:
        assert abs(got[a] / want[a] - 1.0) <= 0.01, (a, got[a], want[a])


@pytest.mark.skipif(not we.era5_path(ERA5_TEST_MONTH).exists(), reason="ERA5 test month not on disk")
def test_p_phys_capacity_factor_in_unit_interval(fleet):
    d = we.area_month(ERA5_TEST_MONTH, fleet, dwd_lag_h=0)
    assert d.height == 744 * len(cfg.AREAS)
    cf = d["p_phys_cf"].to_numpy()
    assert np.all(np.isfinite(cf)) and cf.min() >= 0.0 and cf.max() <= 1.0
    assert (d["c_mw"] > 0).all()


def _check_pipeline():
    from src.method.learned_potential_v2 import evaluate as ev
    rng = np.random.default_rng(3)
    d = _synthetic(80, seed=3).with_columns(
        (pl.col("berlin_date").str.to_date() + pl.duration(days=55)).cast(pl.String).alias("berlin_date"))
    d = d.with_columns(pl.col("berlin_date").str.slice(0, 7).alias("month"),
                       ((pl.col("berlin_date").str.to_date().cast(pl.Int64) * 24 + pl.col("hour_utc"))
                        * 3_600_000).alias("hour_ms"))
    n = d.height
    target = rng.uniform(size=n) < 0.15
    c = 1000.0
    p_phys = d["p_phys_cf"].to_numpy() * c
    g = p_phys * np.exp(rng.normal(-0.05, 0.1, n))
    d = d.with_columns(pl.Series("target", target), pl.Series("clean", ~target), pl.lit(c).alias("c_mw"),
                       pl.Series("p_phys_mw", p_phys), pl.Series("g", g), pl.Series("f", g * 1.05),
                       pl.Series("h", g * 1.01))
    d = d.with_columns(((pl.col("g") + cfg.KAPPA * c) / (pl.col("p_phys_mw") + cfg.KAPPA * c)).log().alias("y"))
    s = hy.domain(d.drop("w"))
    assert s["p"].is_not_null().all() and s.filter(pl.col("lookalike")).height > 0
    month = hy.eval_months()[1]
    preds = {"P0": hy.p0(s).filter(pl.col("month") == month),
             "H1": hy.run_fold(s, month, SMALL, weighted=False),
             "H2": hy.run_fold(s, month, SMALL, weighted=True)}
    assert set(preds["H1"]["berlin_date"].to_list()).isdisjoint(
        s.filter(hy.train_mask(s, month))["berlin_date"].to_list())
    sc = ev.score(s.filter(pl.col("month") == month), preds)
    assert {"P0", "H1", "H2", "F", "H"} <= set(sc["model"].to_list())
    crit = {r["criterion"]: r for r in ev.criteria(sc)}
    assert {"selected", "S1", "S2", "S3"} <= set(crit) and crit["selected"]["model"] in cfg.CANDIDATES
