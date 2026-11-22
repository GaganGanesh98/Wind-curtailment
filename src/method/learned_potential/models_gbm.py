"""Experiment 4, step 2: LightGBM quantile models L1 (unweighted) and L2 (importance-weighted).

    python -m src.method.learned_potential.models_gbm --time-one-fold   # timing only, writes nothing
    python -m src.method.learned_potential.models_gbm                   # the full run

Pre-registered in docs/12 (design block). Target y = log(G / F); the five quantiles are fitted
as separate models and sorted per row so they never cross. Hyperparameters are chosen once on
the pre-window selection fold (median pinball loss; importance-weighted for L2), then fixed.
Rolling origin by month: the model for month m trains on clean quarter-hours from the history
start to `train_last_day(m)` and predicts every valid row of month m.

Writes artifacts/exp4_learned_potential/oof_L1.parquet, oof_L2.parquet (one row per area and
quarter-hour of the evaluation window: the five log-scale quantiles, Â = F · exp(median), the
fold's last training day, the set flags, p_domain and overlap_ok) and gbm_selection.csv.
"""

from __future__ import annotations

import argparse
import time

import numpy as np
import polars as pl

from src.method.learned_potential import config as cfg
from src.method.learned_potential.data import (ART, check_features, eval_months, features,
                                               load_rows, train_last_day, train_mask)
from src.method.learned_potential.domain import SCORES

QCOLS = tuple(f"q{int(round(q * 100)):02d}" for q in cfg.QUANTILES)
MODELS = {"L1": False, "L2": True}          # name -> importance-weighted


def rows() -> pl.DataFrame:
    """Experiment 4 rows with the step 1 domain scores and weights attached."""
    s = pl.read_parquet(SCORES).select(["area", "ts_utc", "p", "w", "lookalike", "lookalike_aggregate"])
    return load_rows().join(s, on=["area", "ts_utc"], how="left")


def _regressor(alpha: float, params: dict):
    import lightgbm as lgb
    return lgb.LGBMRegressor(objective="quantile", alpha=alpha, random_state=cfg.SEED,
                             deterministic=True, force_row_wise=True, n_jobs=4, verbose=-1,
                             **cfg.GBM_FIXED, **params)


def fit_quantiles(train: pl.DataFrame, params: dict, weighted: bool,
                  names=cfg.ALLOWED_FEATURES, quantiles=cfg.QUANTILES) -> list:
    """One LightGBM model per quantile, on the allowed inputs only (allow-list enforced here)."""
    check_features(names)
    X = features(train, names).to_numpy()
    y = train["y"].to_numpy()
    w = train["w"].to_numpy() if weighted else None
    cat = [list(names).index("area")] if "area" in names else "auto"
    out = []
    for q in quantiles:
        m = _regressor(q, params)
        m.fit(X, y, sample_weight=w, categorical_feature=cat)
        out.append(m)
    return out


def predict(models: list, df: pl.DataFrame, names=cfg.ALLOWED_FEATURES) -> np.ndarray:
    check_features(names)
    X = features(df, names).to_numpy()
    return np.sort(np.column_stack([m.predict(X) for m in models]), axis=1)


def pinball(y: np.ndarray, q: np.ndarray, alpha: float, w: np.ndarray | None = None) -> float:
    e = y - q
    loss = np.maximum(alpha * e, (alpha - 1.0) * e)
    return float(np.average(loss, weights=w))


def select(d: pl.DataFrame, weighted: bool) -> tuple[dict, list[dict]]:
    """Pre-registered selection fold: median pinball loss on the validation month."""
    tr = d.filter(pl.col("clean") & (pl.col("berlin_date") >= cfg.HISTORY_START)
                  & (pl.col("berlin_date") <= cfg.SELECTION_TRAIN_END))
    va = d.filter(pl.col("clean") & (pl.col("month") == cfg.SELECTION_VALIDATION_MONTH))
    table = []
    for params in cfg.GBM_GRID:
        m = fit_quantiles(tr, params, weighted, quantiles=(0.5,))
        qv = predict(m, va)[:, 0]
        loss = pinball(va["y"].to_numpy(), qv, 0.5, va["w"].to_numpy() if weighted else None)
        table.append({**params, "median_pinball": loss, "n_train": tr.height, "n_val": va.height})
    best = min(table, key=lambda r: r["median_pinball"])
    return {k: best[k] for k in cfg.GBM_GRID[0]}, table


def run_fold(d: pl.DataFrame, month: str, params: dict, weighted: bool) -> pl.DataFrame:
    tr = d.filter(train_mask(d, month))
    te = d.filter((pl.col("month") == month) & pl.col("valid"))
    q = predict(fit_quantiles(tr, params, weighted), te)
    med = q[:, list(cfg.QUANTILES).index(0.5)]
    return te.select(["area", "ts_utc", "berlin_date", "month", "f_onshore_mw", "clean", "target",
                      "lookalike", "lookalike_aggregate",
                      pl.col("p").alias("p_domain")]).with_columns(
        *(pl.Series(c, q[:, i]) for i, c in enumerate(QCOLS)),
        pl.Series("a_hat_mw", te["f_onshore_mw"].to_numpy() * np.exp(med)),
        pl.lit(train_last_day(month)).alias("train_last_day"),
        pl.lit(tr.height).alias("n_train"),
        (pl.col("p_domain") <= cfg.OVERLAP_TRIM_P).alias("overlap_ok"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--time-one-fold", action="store_true")
    args = ap.parse_args()
    d = rows()
    if args.time_one_fold:
        t0 = time.time()
        params, _ = select(d, False)
        t_sel = time.time() - t0
        t0 = time.time()
        run_fold(d, eval_months()[-1], params, True)
        t_fold = time.time() - t0
        n_fits_sel = 2 * len(cfg.GBM_GRID)
        total = 2 * t_sel + 2 * len(eval_months()) * t_fold
        print(f"selection for one model ({len(cfg.GBM_GRID)} median fits): {t_sel:.0f} s; "
              f"one fold, 5 quantiles, largest training span: {t_fold:.0f} s")
        print(f"expected full run (2 selections, {n_fits_sel} median fits; "
              f"{2 * len(eval_months())} folds): at most about {total / 60:.0f} min")
        return
    ART.mkdir(parents=True, exist_ok=True)
    sel_rows = []
    for name, weighted in MODELS.items():
        params, table = select(d, weighted)
        sel_rows += [{"model": name, **r, "chosen": all(r[k] == params[k] for k in params)} for r in table]
        parts = []
        for month in eval_months():
            t0 = time.time()
            parts.append(run_fold(d, month, params, weighted))
            print(f"  {name} {month}: {time.time() - t0:.0f} s", flush=True)
        pl.concat(parts).with_columns(pl.lit(name).alias("model")).write_parquet(ART / f"oof_{name}.parquet")
        print(f"wrote oof_{name}.parquet (params {params})", flush=True)
    pl.DataFrame(sel_rows).write_csv(ART / "gbm_selection.csv")
    print(f"wrote {ART / 'gbm_selection.csv'}")


if __name__ == "__main__":
    main()
