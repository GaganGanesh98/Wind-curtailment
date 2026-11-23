"""Experiment 4b rows, sets, folds, domain classifier and Layer 2 (docs/24).

    python -m src.method.learned_potential_v2.hybrid --check-era5     # every ERA5 month 2024-01..2026-09
    python -m src.method.learned_potential_v2.hybrid --lag-check      # DWD stamp lag, ERA5 2024
    python -m src.method.learned_potential_v2.hybrid --build-inputs   # area_hours.parquet (long)

Nothing here fits on real data until `require_inputs()` passes: every ERA5 month of the period
on disk and checked (docs/24, "No fit before the inputs are complete").

Columns of `load_rows()`, one row per (area, UTC hour):
  area, hour_ms, berlin_date, month,
  g, f, h (hourly means of the quarter-hours; f and h for scoring only), c_mw, p_phys_mw,
  the allowed inputs (config.ALLOWED_FEATURES),
  price_gt_clean_all, price_lt0_any, rd_any, unit_check_fail, valid, clean, target, y
Only the allowed inputs ever reach a model, through `features()`, which calls `check_features`.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

import numpy as np
import polars as pl

from src.method.learned_potential_v2 import config as cfg

HOUR_MS = 3_600_000
AREA_CODE = {a: i for i, a in enumerate(cfg.AREAS)}
AREA_HOURS = cfg.ART / "area_hours.parquet"
DWD_LAG = cfg.ART / "dwd_lag_check.csv"
QCOLS = tuple(f"q{int(round(q * 100)):02d}" for q in cfg.QUANTILES)
MODELS = {"H1": False, "H2": True}            # name -> importance-weighted


# ------------------------------------------------------------------ allow-list
def check_features(names) -> None:
    names = list(names)
    bad = [n for n in names if n in cfg.FORBIDDEN_FEATURES]
    if bad:
        raise ValueError(f"forbidden input(s) {bad}: price, θ, exposure, depth, run length, H, F, "
                         "G and redispatch never reach a model")
    outside = [n for n in names if n not in cfg.ALLOWED_FEATURES]
    if outside:
        raise ValueError(f"input(s) {outside} are outside the allow-list {cfg.ALLOWED_FEATURES}")


def features(df: pl.DataFrame, names=cfg.ALLOWED_FEATURES) -> pl.DataFrame:
    check_features(names)
    out = df.select(list(names))
    if "area" in out.columns:
        out = out.with_columns(pl.col("area").replace_strict(AREA_CODE).cast(pl.Int32))
    return out


# ------------------------------------------------------------------ inputs
def required_months() -> list[str]:
    out, (y, m) = [], map(int, cfg.ERA5_FIRST_MONTH_USED.split("-"))
    end = cfg.PERIOD[1][:7]
    while f"{y:04d}-{m:02d}" <= end:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def require_inputs() -> None:
    """Raise unless every ERA5 month of the period is on disk and passes `check_era5`."""
    from src.method.learned_potential_v2.weather import check_era5, era5_path
    missing = [m for m in required_months() if not era5_path(m).exists()]
    if missing:
        raise RuntimeError(f"ERA5 pending: {len(missing)} of {len(required_months())} months not on "
                           f"disk ({missing[0]} to {missing[-1]}); no fit before the inputs are complete")
    bad = [c["month"] for c in map(check_era5, required_months()) if not c["ok"]]
    if bad:
        raise RuntimeError(f"ERA5 months failing the input check: {bad}")


def dwd_lag() -> int:
    """The DWD stamp lag fixed by `--lag-check` (higher correlation with ERA5 10 m speed)."""
    t = pl.read_csv(DWD_LAG)
    return int(t.sort("corr", descending=True)["lag_h"][0])


def build_inputs() -> pl.DataFrame:
    from src.method.learned_potential_v2 import fleet as fl
    from src.method.learned_potential_v2 import weather as w
    require_inputs()
    f, lag = fl.fleet(), dwd_lag()
    out = pl.concat([w.area_month(m, f, lag) for m in required_months()])
    cfg.ART.mkdir(parents=True, exist_ok=True)
    out.write_parquet(AREA_HOURS)
    return out


def panel_hours() -> pl.DataFrame:
    """Hourly G, F and price flags per area from the quarter-hour panel, PERIOD only."""
    from src.method.learned_potential.data import PANEL
    p = (pl.scan_parquet(PANEL)
         .filter(pl.col("area").is_in(list(cfg.AREAS)) & (pl.col("berlin_date") >= cfg.PERIOD[0])
                 & (pl.col("berlin_date") <= cfg.PERIOD[1]))
         .select(["ts_utc", "area", "berlin_date", "price_eur_mwh", "act_onshore_mw", "da_onshore_mw"])
         .collect())
    return (p.with_columns((pl.col("ts_utc") // HOUR_MS * HOUR_MS).alias("hour_ms"))
             .group_by(["area", "hour_ms"]).agg(
                 pl.col("berlin_date").min(), pl.len().alias("n_qh"),
                 pl.col("act_onshore_mw").mean().alias("g"), pl.col("da_onshore_mw").mean().alias("f"),
                 (pl.col("act_onshore_mw") > 0).all().alias("g_pos_all"),
                 (pl.col("price_eur_mwh") > cfg.CLEAN_PRICE_ABOVE).all().alias("price_gt_clean_all"),
                 (pl.col("price_eur_mwh") < cfg.TARGET_PRICE_BELOW).any().alias("price_lt0_any")))


def h_hours() -> pl.DataFrame:
    from src.method.available_power import QS_DIR
    from src.method.projection_and_redispatch import load_projection
    hr, _ = load_projection(QS_DIR)
    return (hr.filter(pl.col("area").is_in(list(cfg.AREAS)))
              .with_columns((pl.col("ts_utc") // HOUR_MS * HOUR_MS).alias("hour_ms"))
              .group_by(["area", "hour_ms"]).agg(pl.col("hr_mw").mean().alias("h"), pl.len().alias("_n"))
              .filter(pl.col("_n") == 4).drop("_n"))


def assemble(panel: pl.DataFrame, weather: pl.DataFrame, flags: pl.DataFrame,
             h: pl.DataFrame | None = None) -> pl.DataFrame:
    """Rows from their parts (testable without real data)."""
    d = (panel.join(weather, on=["area", "hour_ms"], how="left")
              .join(flags, on=["area", "hour_ms"], how="left")
              .with_columns(pl.col("rd_any").fill_null(False), pl.col("unit_check_fail").fill_null(False)))
    if h is not None:
        d = d.join(h, on=["area", "hour_ms"], how="left")
    t = pl.col("hour_ms").cast(pl.Datetime("ms")).dt.replace_time_zone("UTC")
    d = d.with_columns(t.dt.hour().cast(pl.Int32).alias("hour_utc"),
                       pl.col("berlin_date").str.slice(5, 2).cast(pl.Int32).alias("month_of_year"),
                       pl.col("berlin_date").str.slice(0, 7).alias("month"))
    valid = (pl.col("n_qh") == 4) & pl.col("p_phys_mw").is_not_null() & (pl.col("c_mw") > 0)
    kc = cfg.KAPPA * pl.col("c_mw")
    return d.with_columns(
        valid.alias("valid"),
        (valid & pl.col("price_gt_clean_all") & pl.col("g_pos_all") & ~pl.col("rd_any")
         & ~pl.col("unit_check_fail")).alias("clean"),
        (valid & pl.col("price_lt0_any")).alias("target"),
        ((pl.col("g") + kc) / (pl.col("p_phys_mw") + kc)).log().alias("y")).sort(["area", "hour_ms"])


def load_rows() -> pl.DataFrame:
    from src.method.learned_potential_v2.facts import hour_flags
    return assemble(panel_hours(), pl.read_parquet(AREA_HOURS), hour_flags(), h_hours())


def a_hat(yhat: np.ndarray, p_phys_mw: np.ndarray, c_mw: np.ndarray) -> np.ndarray:
    kc = cfg.KAPPA * np.asarray(c_mw, float)
    return np.maximum((np.asarray(p_phys_mw, float) + kc) * np.exp(yhat) - kc, 0.0)


# ------------------------------------------------------------------ folds
def eval_months() -> list[str]:
    out, (y, m) = [], map(int, cfg.EVAL_WINDOW[0][:7].split("-"))
    while f"{y:04d}-{m:02d}" <= cfg.EVAL_WINDOW[1][:7]:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def train_last_day(month: str) -> str:
    return (date.fromisoformat(month + "-01") - timedelta(days=cfg.EMBARGO_DAYS + 1)).isoformat()


def train_mask(df: pl.DataFrame, month: str) -> pl.Series:
    return df["clean"] & (df["berlin_date"] >= cfg.PERIOD[0]) & (df["berlin_date"] <= train_last_day(month))


# ------------------------------------------------------------------ domain classifier
def _classifier():
    import lightgbm as lgb
    return lgb.LGBMClassifier(objective="binary", random_state=cfg.SEED, verbose=-1, deterministic=True,
                              force_row_wise=True, n_jobs=4, **cfg.DOMAIN_PARAMS)


def domain(d: pl.DataFrame) -> pl.DataFrame:
    """p cross-fitted leaving one calendar month out, weights, look-alike flags (as Experiment 4)."""
    lab = d.filter(pl.col("valid") & (pl.col("clean") | pl.col("target")))
    cat = [list(cfg.ALLOWED_FEATURES).index("area")]
    parts = []
    for m in sorted(d["month"].unique().to_list()):
        tr = lab.filter(pl.col("month") != m)
        clf = _classifier()
        clf.fit(features(tr).to_numpy(), tr["target"].cast(pl.Int8).to_numpy(), categorical_feature=cat)
        te = d.filter((pl.col("month") == m) & pl.col("valid"))
        parts.append(te.select(["area", "hour_ms"]).with_columns(
            pl.Series("p", clf.predict_proba(features(te).to_numpy())[:, 1])))
    s = d.join(pl.concat(parts), on=["area", "hour_ms"], how="left")
    n_clean, n_target = int(lab["clean"].sum()), int(lab["target"].sum())
    w_raw = (pl.col("p") / (1.0 - pl.col("p"))) * (n_clean / max(n_target, 1))
    clip = float(s.filter(pl.col("clean")).select(w_raw.quantile(cfg.WEIGHT_CLIP_PERCENTILE / 100.0)).item())
    s = s.with_columns(pl.when(pl.col("clean")).then(pl.min_horizontal(w_raw, pl.lit(clip))).otherwise(None).alias("w"))
    in_eval = (pl.col("berlin_date") >= cfg.EVAL_WINDOW[0]) & (pl.col("berlin_date") <= cfg.EVAL_WINDOW[1])
    cut = float(s.filter(pl.col("clean") & in_eval)["p"].quantile(1.0 - cfg.LOOKALIKE_TOP_SHARE))
    s = s.with_columns((pl.col("clean") & in_eval & (pl.col("p") >= cut)).alias("lookalike"))
    agg = (s.filter(in_eval).group_by("hour_ms")
             .agg(pl.col("clean").all().alias("all_clean"), pl.col("p").mean().alias("p_mean"), pl.len().alias("n"))
             .filter(pl.col("all_clean") & (pl.col("n") == len(cfg.AREAS))))
    cut_agg = float(agg["p_mean"].quantile(1.0 - cfg.LOOKALIKE_TOP_SHARE))
    return s.with_columns(pl.col("hour_ms").is_in(agg.filter(pl.col("p_mean") >= cut_agg)["hour_ms"].implode())
                          .alias("lookalike_aggregate"))


# ------------------------------------------------------------------ Layer 2
def _regressor(alpha: float, params: dict):
    import lightgbm as lgb
    return lgb.LGBMRegressor(objective="quantile", alpha=alpha, random_state=cfg.SEED, deterministic=True,
                             force_row_wise=True, n_jobs=4, verbose=-1, **cfg.GBM_FIXED, **params)


def fit_quantiles(train: pl.DataFrame, params: dict, weighted: bool, quantiles=cfg.QUANTILES) -> list:
    X = features(train).to_numpy()
    w = train["w"].to_numpy() if weighted else None
    cat = [list(cfg.ALLOWED_FEATURES).index("area")]
    out = []
    for q in quantiles:
        m = _regressor(q, params)
        m.fit(X, train["y"].to_numpy(), sample_weight=w, categorical_feature=cat)
        out.append(m)
    return out


def predict(models: list, df: pl.DataFrame) -> np.ndarray:
    X = features(df).to_numpy()
    return np.sort(np.column_stack([m.predict(X) for m in models]), axis=1)


def pinball(y, q, alpha, w=None) -> float:
    e = np.asarray(y) - np.asarray(q)
    return float(np.average(np.maximum(alpha * e, (alpha - 1.0) * e), weights=w))


def select(d: pl.DataFrame, weighted: bool) -> tuple[dict, list[dict]]:
    """Pre-registered selection fold: median pinball loss on the validation month."""
    tr = d.filter(pl.col("clean") & (pl.col("berlin_date") >= cfg.PERIOD[0])
                  & (pl.col("berlin_date") <= cfg.SELECTION_TRAIN_END))
    va = d.filter(pl.col("clean") & (pl.col("month") == cfg.SELECTION_VALIDATION_MONTH))
    table = []
    for params in cfg.GBM_GRID:
        q = predict(fit_quantiles(tr, params, weighted, quantiles=(0.5,)), va)[:, 0]
        table.append({**params, "median_pinball": pinball(va["y"], q, 0.5, va["w"].to_numpy() if weighted else None),
                      "n_train": tr.height, "n_val": va.height})
    best = min(table, key=lambda r: r["median_pinball"])
    return {k: best[k] for k in cfg.GBM_GRID[0]}, table


def run_fold(d: pl.DataFrame, month: str, params: dict, weighted: bool) -> pl.DataFrame:
    tr = d.filter(train_mask(d, month))
    te = d.filter((pl.col("month") == month) & pl.col("valid"))
    q = predict(fit_quantiles(tr, params, weighted), te)
    med = q[:, list(cfg.QUANTILES).index(0.5)]
    return te.select(["area", "hour_ms", "berlin_date", "month", "clean", "target", "lookalike",
                      "lookalike_aggregate", "p"]).with_columns(
        *(pl.Series(c, q[:, i]) for i, c in enumerate(QCOLS)),
        pl.Series("a_hat_mw", a_hat(med, te["p_phys_mw"], te["c_mw"])),
        pl.lit(train_last_day(month)).alias("train_last_day"),
        pl.lit(tr.height).alias("n_train"),
        (pl.col("p") <= cfg.OVERLAP_P).alias("overlap_ok"))


def p0(d: pl.DataFrame) -> pl.DataFrame:
    """P0, physics only: Â = P_phys on every valid hour of the evaluation window."""
    e = d.filter(pl.col("valid") & (pl.col("berlin_date") >= cfg.EVAL_WINDOW[0])
                 & (pl.col("berlin_date") <= cfg.EVAL_WINDOW[1]))
    return e.select(["area", "hour_ms", "berlin_date", "month", "clean", "target", "lookalike",
                     "lookalike_aggregate", "p", pl.col("p_phys_mw").alias("a_hat_mw")]).with_columns(
        (pl.col("p") <= cfg.OVERLAP_P).alias("overlap_ok"))


def main() -> None:
    from src.method.learned_potential_v2 import weather as w
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-era5", action="store_true")
    ap.add_argument("--lag-check", action="store_true")
    ap.add_argument("--build-inputs", action="store_true")
    a = ap.parse_args()
    if a.check_era5:
        for m in required_months():
            print(w.check_era5(m) if w.era5_path(m).exists() else {"month": m, "ok": "pending"})
    if a.lag_check:
        months = [m for m in required_months() if m.startswith("2024")]
        missing = [m for m in months if not w.era5_path(m).exists()]
        if missing:
            raise SystemExit(f"ERA5 2024 pending: {missing}")
        t = w.dwd_lag_check(months)
        cfg.ART.mkdir(parents=True, exist_ok=True)
        t.write_csv(DWD_LAG)
        print(t)
    if a.build_inputs:
        print(build_inputs().shape)


if __name__ == "__main__":
    main()
