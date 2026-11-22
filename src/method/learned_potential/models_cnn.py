"""Experiment 4, step 3: N1, a temporal CNN with quantile heads (docs/12).

    python -m src.method.learned_potential.models_cnn --time-one-fold   # timing only, writes nothing
    python -m src.method.learned_potential.models_cnn                   # the full run

As pre-registered: 1D convolutions over the three allowed day-ahead forecasts from -6 h to +6 h,
the grid of layers and channels in config.CNN_GRID, kernel 5, five quantile heads, pinball loss,
importance-weighted (step 1 weights), Adam, early stopping on the last 28 days of the training
span (time-ordered), seed 42, CPU, deterministic algorithms. Hyperparameters chosen once on the
pre-window selection fold, then fixed; rolling origin by month as for L1 and L2.

This module never imports LightGBM, directly or through models_gbm / domain (LightGBM and
PyTorch each bundle libomp; loading both in one process can crash on macOS). `main` asserts it.
Mini-batches are drawn in a seeded random order within each training span; the folds themselves
are whole days in time order.

Writes artifacts/exp4_learned_potential/oof_N1.parquet (same columns as oof_L1) and
cnn_selection.csv.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta

import numpy as np
import polars as pl

from src.method.learned_potential import config as cfg
from src.method.learned_potential.data import (ART, PANEL, check_features, eval_months, load_rows,
                                               load_solar, train_last_day, train_mask)

SCORES = ART / "domain_scores.parquet"
QCOLS = tuple(f"q{int(round(q * 100)):02d}" for q in cfg.QUANTILES)
SERIES = ("f_onshore_mw", "f_offshore_mw", "f_solar_mw")      # the windowed inputs
HW = cfg.CNN_HALF_WINDOW_QH
N_STATIC = 2 + 7 + 1 + len(cfg.AREAS)                          # qh sin/cos, weekday, holiday, area


def rows() -> pl.DataFrame:
    s = pl.read_parquet(SCORES).select(["area", "ts_utc", "p", "w", "lookalike", "lookalike_aggregate"])
    return load_rows().join(s, on=["area", "ts_utc"], how="left")


def context() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Per area: sorted timestamps and the three allowed forecasts, one day beyond the
    evaluation window so the +6 h half of the last windows exists. Inputs only."""
    end = (date.fromisoformat(cfg.EVAL_WINDOW[1]) + timedelta(days=1)).isoformat()
    p = (pl.scan_parquet(PANEL)
         .filter(pl.col("area").is_in(list(cfg.AREAS)) & (pl.col("berlin_date") >= cfg.HISTORY_START)
                 & (pl.col("berlin_date") <= end))
         .select(["ts_utc", "area", pl.col("da_onshore_mw").alias("f_onshore_mw"),
                  pl.col("da_offshore_mw").alias("f_offshore_mw")]).collect()
         .join(load_solar(), on=["area", "ts_utc"], how="left").sort(["area", "ts_utc"]))
    out = {}
    for a in cfg.AREAS:
        q = p.filter(pl.col("area") == a)
        ts = q["ts_utc"].to_numpy()
        if (np.diff(ts) != 900_000).any():
            raise ValueError(f"{a}: forecast series is not contiguous quarter-hours")
        out[a] = (ts, q.select(SERIES).to_numpy().astype(np.float32).T)      # (3, T)
    return out


def tensors(df: pl.DataFrame, ctx: dict, scales: dict, names=cfg.ALLOWED_FEATURES):
    """Windowed series (N, 3, 2*HW+1), static features (N, N_STATIC) and a mask of rows whose
    whole window is present. Built from the allowed inputs only."""
    check_features(names)
    n = df.height
    X = np.full((n, len(SERIES), 2 * HW + 1), np.nan, dtype=np.float32)
    area = df["area"].to_numpy()
    ts = df["ts_utc"].to_numpy()
    for a, (cts, vals) in ctx.items():
        m = np.flatnonzero(area == a)
        if m.size == 0:
            continue
        idx = np.searchsorted(cts, ts[m])
        found = (idx < cts.size) & (cts[np.minimum(idx, cts.size - 1)] == ts[m])
        offs = np.arange(-HW, HW + 1)
        win = idx[:, None] + offs[None, :]
        inside = found[:, None] & (win >= 0) & (win < cts.size)
        winc = np.clip(win, 0, cts.size - 1)
        sc = np.array(scales[a], dtype=np.float32)[:, None, None]
        block = vals[:, winc] / sc                                   # (3, m, W)
        block[:, ~inside] = np.nan
        X[m] = np.transpose(block, (1, 0, 2))
    ok = np.isfinite(X).all(axis=(1, 2))
    qh = df["qh_of_day"].to_numpy().astype(np.float32)
    dow = df["day_of_week"].to_numpy()
    S = np.zeros((n, N_STATIC), dtype=np.float32)
    S[:, 0] = np.sin(2 * np.pi * qh / 96.0)
    S[:, 1] = np.cos(2 * np.pi * qh / 96.0)
    S[np.arange(n), 2 + dow] = 1.0
    S[:, 9] = df["holiday"].to_numpy().astype(np.float32)
    for i, a in enumerate(cfg.AREAS):
        S[:, 10 + i] = (area == a).astype(np.float32)
    return np.nan_to_num(X), S, ok


def fold_scales(train: pl.DataFrame) -> dict:
    """Per area, the 99th percentile of each windowed input on the fold's training rows (1 if 0)."""
    out = {}
    for a in cfg.AREAS:
        q = train.filter(pl.col("area") == a)
        out[a] = [max(float(q[c].quantile(0.99) or 0.0), 1.0) for c in SERIES]
    return out


def _torch():
    import torch
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(4)
    return torch


def build(layers: int, channels: int):
    torch = _torch()
    nn = torch.nn
    k = cfg.CNN_FIXED["kernel"]

    class QCNN(nn.Module):
        def __init__(self):
            super().__init__()
            convs = [nn.Conv1d(len(SERIES), channels, k, padding=k // 2), nn.ReLU()]
            for dil in (2, 4)[:layers - 1]:
                convs += [nn.Conv1d(channels, channels, k, padding=(k // 2) * dil, dilation=dil), nn.ReLU()]
            self.convs = nn.Sequential(*convs)
            self.head = nn.Sequential(nn.Linear(2 * channels + N_STATIC, 32), nn.ReLU(),
                                      nn.Linear(32, len(cfg.QUANTILES)))
            with torch.no_grad():        # start near the data: lowest quantile below zero, small steps
                self.head[-1].bias[0] = -0.35
                self.head[-1].bias[1:] = float(np.log(np.expm1(0.15)))

        def forward(self, x, s):
            h = self.convs(x)
            z = torch.cat([h[:, :, HW], h.mean(dim=2), s], dim=1)
            out = self.head(z)
            inc = torch.nn.functional.softplus(out[:, 1:])
            return torch.cat([out[:, :1], out[:, :1] + torch.cumsum(inc, dim=1)], dim=1)

    return QCNN()


def _pinball(torch, q, y, w):
    taus = torch.tensor(cfg.QUANTILES, dtype=q.dtype)
    e = y[:, None] - q
    loss = torch.maximum(taus * e, (taus - 1.0) * e).mean(dim=1)
    return (loss * w).sum() / w.sum()


def train_model(Xtr, Str, ytr, wtr, Xva, Sva, yva, wva, layers, channels, max_epochs=None):
    """Adam, weighted pinball loss, early stopping on the validation span; best weights restored."""
    torch = _torch()
    torch.manual_seed(cfg.SEED)
    np.random.seed(cfg.SEED)
    model = build(layers, channels)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.CNN_FIXED["lr"])
    T = lambda a: torch.from_numpy(np.ascontiguousarray(a, dtype=np.float32))     # noqa: E731
    Xtr, Str, ytr, wtr = T(Xtr), T(Str), T(ytr), T(wtr)
    Xva, Sva, yva, wva = T(Xva), T(Sva), T(yva), T(wva)
    gen = torch.Generator().manual_seed(cfg.SEED)
    bs = cfg.CNN_FIXED["batch"]
    best, best_state, best_epoch, bad = np.inf, None, 0, 0
    for epoch in range(max_epochs or cfg.CNN_FIXED["max_epochs"]):
        model.train()
        perm = torch.randperm(Xtr.shape[0], generator=gen)
        for i in range(0, Xtr.shape[0], bs):
            b = perm[i:i + bs]
            opt.zero_grad()
            _pinball(torch, model(Xtr[b], Str[b]), ytr[b], wtr[b]).backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            v = float(_pinball(torch, model(Xva, Sva), yva, wva))
        if v < best - 1e-7:
            best, best_epoch, bad = v, epoch + 1, 0
            best_state = {k: t.detach().clone() for k, t in model.state_dict().items()}
        else:
            bad += 1
            if bad >= cfg.CNN_FIXED["patience"]:
                break
    model.load_state_dict(best_state)
    model.eval()
    return model, best, best_epoch


def predict(model, X, S) -> np.ndarray:
    torch = _torch()
    with torch.no_grad():
        q = model(torch.from_numpy(X), torch.from_numpy(S)).numpy()
    return np.sort(q, axis=1)


def _split_val(tr: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    last = tr["berlin_date"].max()
    cut = (date.fromisoformat(last) - timedelta(days=cfg.CNN_FIXED["val_days"])).isoformat()
    return tr.filter(pl.col("berlin_date") <= cut), tr.filter(pl.col("berlin_date") > cut)


def _xy(df, ctx, scales):
    X, S, ok = tensors(df, ctx, scales)
    return X[ok], S[ok], df["y"].to_numpy()[ok].astype(np.float32), df["w"].to_numpy()[ok].astype(np.float32), ok


def fit_on(train: pl.DataFrame, ctx: dict, layers: int, channels: int, max_epochs=None):
    scales = fold_scales(train)
    fit, val = _split_val(train)
    a = _xy(fit, ctx, scales)
    b = _xy(val, ctx, scales)
    model, vloss, epoch = train_model(*a[:4], *b[:4], layers, channels, max_epochs)
    return model, scales, {"val_loss": vloss, "best_epoch": epoch, "n_fit": int(a[4].sum()),
                           "n_val": int(b[4].sum())}


def select(d: pl.DataFrame, ctx: dict) -> tuple[dict, list[dict]]:
    tr = d.filter(pl.col("clean") & (pl.col("berlin_date") >= cfg.HISTORY_START)
                  & (pl.col("berlin_date") <= cfg.SELECTION_TRAIN_END))
    va = d.filter(pl.col("clean") & (pl.col("month") == cfg.SELECTION_VALIDATION_MONTH))
    table = []
    for g in cfg.CNN_GRID:
        model, scales, info = fit_on(tr, ctx, g["layers"], g["channels"])
        X, S, y, w, _ = _xy(va, ctx, scales)
        med = predict(model, X, S)[:, list(cfg.QUANTILES).index(0.5)]
        e = y - med
        loss = float(np.average(np.maximum(0.5 * e, -0.5 * e), weights=w))
        table.append({**g, "median_pinball_weighted": loss, **info, "n_validation_month": int(y.size)})
        print(f"  selection {g}: {loss:.5f} (best epoch {info['best_epoch']})", flush=True)
    best = min(table, key=lambda r: r["median_pinball_weighted"])
    return {"layers": best["layers"], "channels": best["channels"]}, table


def run_fold(d: pl.DataFrame, ctx: dict, month: str, params: dict) -> pl.DataFrame:
    tr = d.filter(train_mask(d, month))
    model, scales, info = fit_on(tr, ctx, params["layers"], params["channels"])
    te = d.filter((pl.col("month") == month) & pl.col("valid"))
    X, S, ok = tensors(te, ctx, scales)
    q = predict(model, X[ok], S[ok])
    te = te.filter(pl.Series(ok))
    med = q[:, list(cfg.QUANTILES).index(0.5)]
    return te.select(["area", "ts_utc", "berlin_date", "month", "f_onshore_mw", "clean", "target",
                      "lookalike", "lookalike_aggregate", pl.col("p").alias("p_domain")]).with_columns(
        *(pl.Series(c, q[:, i]) for i, c in enumerate(QCOLS)),
        pl.Series("a_hat_mw", te["f_onshore_mw"].to_numpy() * np.exp(med)),
        pl.lit(train_last_day(month)).alias("train_last_day"),
        pl.lit(tr.height).alias("n_train"), pl.lit(info["best_epoch"]).alias("best_epoch"),
        pl.lit(int((~ok).sum())).alias("n_scored_rows_without_window"),
        (pl.col("p_domain") <= cfg.OVERLAP_TRIM_P).alias("overlap_ok"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--time-one-fold", action="store_true")
    args = ap.parse_args()
    d, ctx = rows(), context()
    if args.time_one_fold:
        # One epoch of the largest configuration on the largest training span; the full run is
        # bounded by (selection fits + folds) x the pre-registered maximum of epochs.
        g = cfg.CNN_GRID[-1]
        tr = d.filter(train_mask(d, eval_months()[-1]))
        t0 = time.time()
        fit_on(tr, ctx, g["layers"], g["channels"], max_epochs=1)
        t = time.time() - t0
        n = len(cfg.CNN_GRID) + len(eval_months())
        e = cfg.CNN_FIXED["max_epochs"]
        print(f"one epoch, largest configuration {g}, largest training span: {t:.0f} s")
        print(f"upper bound for the full run ({n} fits x {e} epochs): about {n * e * t / 3600:.1f} h; "
              f"with early stopping it is usually shorter")
        assert "lightgbm" not in sys.modules
        return
    ART.mkdir(parents=True, exist_ok=True)
    params, table = select(d, ctx)
    pl.DataFrame([{**r, "chosen": r["layers"] == params["layers"] and r["channels"] == params["channels"]}
                  for r in table]).write_csv(ART / "cnn_selection.csv")
    parts = []
    for month in eval_months():
        t0 = time.time()
        parts.append(run_fold(d, ctx, month, params))
        print(f"  N1 {month}: {time.time() - t0:.0f} s, best epoch {parts[-1]['best_epoch'][0]}", flush=True)
    assert "lightgbm" not in sys.modules, "LightGBM was loaded into the N1 process"
    pl.concat(parts).with_columns(pl.lit("N1").alias("model")).write_parquet(ART / "oof_N1.parquet")
    print(f"wrote oof_N1.parquet and cnn_selection.csv (params {params})")


if __name__ == "__main__":
    main()
