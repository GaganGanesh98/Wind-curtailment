"""Experiment 4b scores and criteria (docs/24): look-alike σ and bias per model, selection, S1 to
S4. The bootstrap statistics are Experiment 4's own functions, imported, so the two experiments
compute intervals the same way (day blocks, the same draws and seed).

Units: each area's look-alike hours, the pooled area rows, and the three-area aggregate
(look-alike hours, log(ΣG / ΣÂ)). Baselines F and H on the same hours.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from src.method.learned_potential.scoring import _mean_sd, _ratio
from src.method.learned_potential_v2 import config as cfg
from src.method.learned_potential_v2.hybrid import QCOLS

BIAS, SIGMA = "bias (mean log G/Â)", "sigma (sd log G/Â)"


def _with_ahat(rows: pl.DataFrame, model: str, preds: dict) -> pl.DataFrame:
    if model == "F":
        return rows.with_columns(pl.col("f").alias("ahat"))
    if model == "H":
        return rows.with_columns(pl.col("h").alias("ahat"))
    p = preds[model].select(["area", "hour_ms", pl.col("a_hat_mw").alias("ahat"),
                             *[c for c in QCOLS if c in preds[model].columns]])
    return rows.join(p, on=["area", "hour_ms"], how="inner")


def row_metrics(r: pl.DataFrame, has_quantiles: bool) -> list[dict]:
    r = r.filter((pl.col("ahat") > 0) & (pl.col("g") > 0))
    e = np.log(r["g"].to_numpy() / r["ahat"].to_numpy())
    days = r["berlin_date"].to_numpy().astype(str)
    st = _mean_sd(e, days)
    out = [{"metric": BIAS, "value": st["mean"], "lo": st["mean_ci"][0], "hi": st["mean_ci"][1]},
           {"metric": SIGMA, "value": st["sigma"], "lo": st["sigma_ci"][0], "hi": st["sigma_ci"][1]}]
    if has_quantiles:
        y = r["y"].to_numpy()
        loss = np.zeros_like(y)
        for c, a in zip(QCOLS, cfg.QUANTILES):
            d = y - r[c].to_numpy()
            loss += np.maximum(a * d, (a - 1.0) * d)
        v, ci = _ratio(loss / len(cfg.QUANTILES), days)
        out.append({"metric": "pinball loss (mean over quantiles, log scale)", "value": v, "lo": ci[0], "hi": ci[1]})
        v, ci = _ratio(((y >= r[QCOLS[0]].to_numpy()) & (y <= r[QCOLS[-1]].to_numpy())).astype(float), days)
        out.append({"metric": "coverage of 0.05-0.95 band", "value": v, "lo": ci[0], "hi": ci[1]})
    return [{**m, "n_hours": st["n_qh"], "n_days": st["n_days"]} for m in out]


def aggregate_metrics(rows: pl.DataFrame, hours: pl.Series, model: str, preds: dict) -> list[dict]:
    r = _with_ahat(rows.filter(pl.col("hour_ms").is_in(hours.implode())), model, preds)
    a = (r.group_by(["hour_ms", "berlin_date"]).agg(pl.col("g").sum(), pl.col("ahat").sum(), pl.len().alias("n"))
           .filter((pl.col("n") == len(cfg.AREAS)) & (pl.col("ahat") > 0)))
    st = _mean_sd(np.log(a["g"].to_numpy() / a["ahat"].to_numpy()), a["berlin_date"].to_numpy().astype(str))
    return [{"metric": BIAS, "value": st["mean"], "lo": st["mean_ci"][0], "hi": st["mean_ci"][1],
             "n_hours": st["n_qh"], "n_days": st["n_days"]},
            {"metric": SIGMA, "value": st["sigma"], "lo": st["sigma_ci"][0], "hi": st["sigma_ci"][1],
             "n_hours": st["n_qh"], "n_days": st["n_days"]}]


def score(rows: pl.DataFrame, preds: dict) -> pl.DataFrame:
    """Look-alike scores for every model in `preds` (P0, H1, H2) and the baselines F and H."""
    ev = rows.filter((pl.col("berlin_date") >= cfg.EVAL_WINDOW[0]) & (pl.col("berlin_date") <= cfg.EVAL_WINDOW[1]))
    agg_hours = ev.filter(pl.col("lookalike_aggregate"))["hour_ms"].unique()
    out = []
    for model in [*preds, "F", "H"]:
        q = model in preds and QCOLS[0] in preds[model].columns
        for unit in (*cfg.AREAS, "pooled area rows"):
            r = ev.filter(pl.col("lookalike"))
            if unit != "pooled area rows":
                r = r.filter(pl.col("area") == unit)
            r = _with_ahat(r, model, preds)
            if r.height:
                out += [{"model": model, "unit": unit, **m} for m in row_metrics(r, q)]
        if agg_hours.len():
            out += [{"model": model, "unit": "three-area aggregate", **m}
                    for m in aggregate_metrics(ev, agg_hours, model, preds)]
    return pl.DataFrame(out)


def _agg(s: pl.DataFrame, model: str, metric: str) -> dict:
    return s.filter((pl.col("model") == model) & (pl.col("unit") == "three-area aggregate")
                    & (pl.col("metric") == metric)).row(0, named=True)


def criteria(s: pl.DataFrame, s4: dict | None = None) -> list[dict]:
    """Selection and S1 to S4 from the aggregate look-alike scores, exactly as docs/24 states."""
    cands = [m for m in cfg.CANDIDATES if m in set(s["model"].to_list())]
    sel = min(cands, key=lambda m: (round(abs(_agg(s, m, BIAS)["value"]), cfg.TIE_DECIMALS),
                                    _agg(s, m, SIGMA)["value"]))
    best = min(cands, key=lambda m: _agg(s, m, SIGMA)["value"])
    b = _agg(s, sel, BIAS)
    out = [{"criterion": "selected", "model": sel, "value": b["value"], "lo": b["lo"], "hi": b["hi"], "pass": ""},
           {"criterion": "S1", "model": best, "value": _agg(s, best, SIGMA)["value"],
            "lo": _agg(s, "F", SIGMA)["value"], "hi": None,
            "pass": _agg(s, best, SIGMA)["value"] < _agg(s, "F", SIGMA)["value"]},
           {"criterion": "S2", "model": sel, "value": b["value"], "lo": b["lo"], "hi": b["hi"],
            "pass": (b["lo"] >= -cfg.S2_HALF_WIDTH) and (b["hi"] <= cfg.S2_HALF_WIDTH)}]
    if {"H1", "H2"} <= set(cands):
        out.append({"criterion": "S3", "model": "H2", "value": _agg(s, "H2", SIGMA)["value"],
                    "lo": _agg(s, "H1", SIGMA)["value"], "hi": None,
                    "pass": _agg(s, "H2", SIGMA)["value"] <= _agg(s, "H1", SIGMA)["value"]})
    if s4 is not None:
        out.append({"criterion": "S4 (descriptive)", "model": sel, "value": s4["model"], "lo": s4["H"],
                    "hi": None, "pass": ""})
    return out


def s4(rows: pl.DataFrame, preds: dict, model: str) -> dict:
    """σ of log(ΣG / ΣÂ) on all clean hours of the evaluation window (clean in all three areas),
    for the selected model and for H."""
    ev = rows.filter((pl.col("berlin_date") >= cfg.EVAL_WINDOW[0]) & (pl.col("berlin_date") <= cfg.EVAL_WINDOW[1]))
    all_clean = (ev.group_by("hour_ms").agg(pl.col("clean").all().alias("c"), pl.len().alias("n"))
                   .filter(pl.col("c") & (pl.col("n") == len(cfg.AREAS)))["hour_ms"])
    return {"model": next(m["value"] for m in aggregate_metrics(ev, all_clean, model, preds) if m["metric"] == SIGMA),
            "H": next(m["value"] for m in aggregate_metrics(ev, all_clean, "H", preds) if m["metric"] == SIGMA)}
