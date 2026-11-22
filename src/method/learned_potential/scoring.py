"""Experiment 4 look-alike scores (docs/12): σ and mean of log(G / Â), pinball loss and coverage,
with day-block 95% intervals, for the learned models and for F and H on the same quarter-hours.

    python -m src.method.learned_potential.scoring          # writes lookalike_scores.csv

Units: each area's look-alike rows, the pooled area rows, and the three-area aggregate
(look-alike timestamps, log(ΣG / ΣÂ)). Pinball loss and coverage need quantiles, so they are
given for the learned models at row level only.

Subset "sunny days" (descriptive only, not a criterion; doc 43): look-alike days whose clean
quarter-hours have a median solar forecast above the 75th percentile of the clean set's solar
forecast in the evaluation window (per area; at the aggregate, the three-area sum).
"""

from __future__ import annotations

import numpy as np
import polars as pl

from src.method.day_bootstrap import bootstrap_day_sums, ci95
from src.method.learned_potential import config as cfg
from src.method.learned_potential.data import ART, load_rows

OUT = ART / "lookalike_scores.csv"
SUNNY_PERCENTILE = 75


def _eval_rows() -> pl.DataFrame:
    s = pl.read_parquet(ART / "domain_scores.parquet").select(
        ["area", "ts_utc", "lookalike", "lookalike_aggregate"])
    return (load_rows().filter((pl.col("berlin_date") >= cfg.EVAL_WINDOW[0])
                               & (pl.col("berlin_date") <= cfg.EVAL_WINDOW[1]))
            .join(s, on=["area", "ts_utc"], how="left"))


def learned(models=("L1", "L2", "N1")) -> dict[str, pl.DataFrame]:
    return {m: pl.read_parquet(ART / f"oof_{m}.parquet") for m in models
            if (ART / f"oof_{m}.parquet").exists()}


def _mean_sd(x: np.ndarray, days: np.ndarray) -> dict:
    uniq, idx = np.unique(days, return_inverse=True)
    S = np.zeros((uniq.size, 3))
    np.add.at(S[:, 0], idx, 1.0)
    np.add.at(S[:, 1], idx, x)
    np.add.at(S[:, 2], idx, x * x)
    b = bootstrap_day_sums(S, n_boot=cfg.N_BOOT, seed=cfg.SEED)
    with np.errstate(invalid="ignore", divide="ignore"):
        mb = b[:, 1] / b[:, 0]
        sb = np.sqrt(np.maximum(b[:, 2] / b[:, 0] - mb ** 2, 0.0))
    t = S.sum(0)
    m = t[1] / t[0]
    return {"n_qh": int(t[0]), "n_days": int(uniq.size),
            "mean": float(m), "mean_ci": ci95(mb),
            "sigma": float(np.sqrt(max(t[2] / t[0] - m * m, 0.0))), "sigma_ci": ci95(sb)}


def _ratio(num: np.ndarray, days: np.ndarray) -> tuple[float, tuple[float, float]]:
    uniq, idx = np.unique(days, return_inverse=True)
    S = np.zeros((uniq.size, 2))
    np.add.at(S[:, 0], idx, 1.0)
    np.add.at(S[:, 1], idx, num)
    b = bootstrap_day_sums(S, n_boot=cfg.N_BOOT, seed=cfg.SEED)
    return float(S[:, 1].sum() / S[:, 0].sum()), ci95(b[:, 1] / b[:, 0])


def _rows_for(unit_rows: pl.DataFrame, model: str, preds: dict) -> pl.DataFrame:
    """Per-row error columns for one model on the given rows (area level)."""
    r = unit_rows
    if model == "F":
        return r.with_columns(pl.col("y").alias("e"))
    if model == "H":
        return r.with_columns((pl.col("g") / pl.col("h")).log().alias("e"))
    p = preds[model].select(["area", "ts_utc", "a_hat_mw", "q05", "q25", "q50", "q75", "q95"])
    return r.join(p, on=["area", "ts_utc"], how="inner").with_columns(
        (pl.col("g") / pl.col("a_hat_mw")).log().alias("e"))


def _row_metrics(r: pl.DataFrame, model: str) -> list[dict]:
    days = r["berlin_date"].to_numpy().astype(str)
    st = _mean_sd(r["e"].to_numpy(), days)
    out = [{"metric": "bias (mean log G/Â)", "value": st["mean"], "lo": st["mean_ci"][0],
            "hi": st["mean_ci"][1]},
           {"metric": "sigma (sd log G/Â)", "value": st["sigma"], "lo": st["sigma_ci"][0],
            "hi": st["sigma_ci"][1]}]
    if model not in ("F", "H"):
        y = r["y"].to_numpy()
        loss = np.zeros_like(y)
        for qn, a in zip(("q05", "q25", "q50", "q75", "q95"), cfg.QUANTILES):
            e = y - r[qn].to_numpy()
            loss += np.maximum(a * e, (a - 1.0) * e)
        v, ci = _ratio(loss / len(cfg.QUANTILES), days)
        out.append({"metric": "pinball loss (mean over quantiles, log scale)", "value": v, "lo": ci[0], "hi": ci[1]})
        cov = ((y >= r["q05"].to_numpy()) & (y <= r["q95"].to_numpy())).astype(float)
        v, ci = _ratio(cov, days)
        out.append({"metric": "coverage of 0.05-0.95 band", "value": v, "lo": ci[0], "hi": ci[1]})
    return [{**m, "n_qh": st["n_qh"], "n_days": st["n_days"]} for m in out]


def _aggregate_metrics(ev: pl.DataFrame, ts_set: pl.Series, model: str, preds: dict) -> list[dict]:
    r = ev.filter(pl.col("ts_utc").is_in(ts_set.implode()))
    if model == "F":
        r = r.with_columns(pl.col("f_onshore_mw").alias("ahat"))
    elif model == "H":
        r = r.with_columns(pl.col("h").alias("ahat"))
    else:
        r = r.join(preds[model].select(["area", "ts_utc", pl.col("a_hat_mw").alias("ahat")]),
                   on=["area", "ts_utc"], how="inner")
    a = (r.group_by(["ts_utc", "berlin_date"]).agg(pl.col("g").sum(), pl.col("ahat").sum(), pl.len().alias("n"))
           .filter(pl.col("n") == len(cfg.AREAS)))
    e = np.log(a["g"].to_numpy() / a["ahat"].to_numpy())
    st = _mean_sd(e, a["berlin_date"].to_numpy().astype(str))
    return [{"metric": "bias (mean log G/Â)", "value": st["mean"], "lo": st["mean_ci"][0], "hi": st["mean_ci"][1],
             "n_qh": st["n_qh"], "n_days": st["n_days"]},
            {"metric": "sigma (sd log G/Â)", "value": st["sigma"], "lo": st["sigma_ci"][0], "hi": st["sigma_ci"][1],
             "n_qh": st["n_qh"], "n_days": st["n_days"]}]


def sunny_days(ev: pl.DataFrame) -> dict[str, set[str]]:
    """Look-alike days whose clean quarter-hours have a median solar forecast above the clean
    set's 75th percentile, per area and at the aggregate (descriptive subset)."""
    out = {}
    for a in cfg.AREAS:
        c = ev.filter((pl.col("area") == a) & pl.col("clean"))
        cut = float(c["f_solar_mw"].quantile(SUNNY_PERCENTILE / 100))
        med = c.group_by("berlin_date").agg(pl.col("f_solar_mw").median())
        la = set(ev.filter((pl.col("area") == a) & pl.col("lookalike"))["berlin_date"].to_list())
        out[a] = {d for d, v in med.iter_rows() if v > cut and d in la}
    agg_clean = (ev.group_by(["ts_utc", "berlin_date"])
                   .agg(pl.col("clean").all().alias("c"), pl.col("f_solar_mw").sum().alias("sol"), pl.len().alias("n"))
                   .filter(pl.col("c") & (pl.col("n") == len(cfg.AREAS))))
    cut = float(agg_clean["sol"].quantile(SUNNY_PERCENTILE / 100))
    med = agg_clean.group_by("berlin_date").agg(pl.col("sol").median())
    la = set(ev.filter(pl.col("lookalike_aggregate"))["berlin_date"].to_list())
    out["aggregate"] = {d for d, v in med.iter_rows() if v > cut and d in la}
    return out


def score() -> pl.DataFrame:
    ev = _eval_rows()
    preds = learned()
    models = [*preds, "F", "H"]
    sunny = sunny_days(ev)
    agg_ts_all = ev.filter(pl.col("lookalike_aggregate"))["ts_utc"].unique()
    out = []
    for subset in ("all look-alike", "sunny look-alike days"):
        for model in models:
            for unit in (*cfg.AREAS, "pooled area rows"):
                r = ev.filter(pl.col("lookalike"))
                if unit != "pooled area rows":
                    r = r.filter(pl.col("area") == unit)
                if subset != "all look-alike":
                    keep = (sunny[unit] if unit != "pooled area rows"
                            else None)
                    if keep is None:
                        r = r.filter(pl.struct(["area", "berlin_date"]).map_elements(
                            lambda s: s["berlin_date"] in sunny[s["area"]], return_dtype=pl.Boolean))
                    else:
                        r = r.filter(pl.col("berlin_date").is_in(list(keep)))
                r = _rows_for(r, model, preds)
                if r.height == 0:
                    continue
                for m in _row_metrics(r, model):
                    out.append({"subset": subset, "model": model, "unit": unit, **m})
            ts = agg_ts_all
            if subset != "all look-alike":
                ts = ev.filter(pl.col("lookalike_aggregate")
                               & pl.col("berlin_date").is_in(list(sunny["aggregate"])))["ts_utc"].unique()
            if ts.len():
                for m in _aggregate_metrics(ev, ts, model, preds):
                    out.append({"subset": subset, "model": model, "unit": "three-area aggregate", **m})
    return pl.DataFrame(out)


def main() -> None:
    s = score()
    s.write_csv(OUT)
    pl.Config.set_tbl_rows(200)
    print(s.filter(pl.col("metric").str.starts_with("sigma") | pl.col("metric").str.starts_with("bias")))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
