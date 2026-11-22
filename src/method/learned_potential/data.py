"""Experiment 4 data: one row per (area, quarter-hour), the clean and target sets, the input
allow-list and the rolling-origin folds (docs/12).

Columns of `load_rows()`:
  ts_utc (ms), berlin_date, month, area,
  price, g (onshore actual G), h (quality-assured projection H; evaluation window only),
  rd (renewable redispatch R, MW, the Phase 6 series),
  f_onshore_mw, f_offshore_mw, f_solar_mw, qh_of_day, day_of_week, holiday   <- the inputs
  valid, clean, target

Only the input columns ever reach a model, through `features()`, which calls
`check_features`. Price, G, H and R are here to define the sets and to score, never as inputs.
"""

from __future__ import annotations

import glob
import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import polars as pl

from src.method.learned_potential import config as cfg

REPO_ROOT = Path(__file__).resolve().parents[3]
PANEL = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"
SMARD = REPO_ROOT / "data" / "raw" / "smard"
ART = REPO_ROOT / "artifacts" / "exp4_learned_potential"
AREA_CODE = {a: i for i, a in enumerate(cfg.AREAS)}


# ------------------------------------------------------------------ allow-list

def check_features(names) -> None:
    """Raise if a model is handed anything outside the closed allow-list (hard rule 3)."""
    names = list(names)
    bad = [n for n in names if n in cfg.FORBIDDEN_FEATURES]
    if bad:
        raise ValueError(f"forbidden input(s) {bad}: price, theta, exposure, depth, run length, "
                         "H, G, the intraday forecast and redispatch never reach a model")
    outside = [n for n in names if n not in cfg.ALLOWED_FEATURES]
    if outside:
        raise ValueError(f"input(s) {outside} are outside the allow-list {cfg.ALLOWED_FEATURES}")


def features(df: pl.DataFrame, names=cfg.ALLOWED_FEATURES) -> pl.DataFrame:
    check_features(names)
    out = df.select(list(names))
    if "area" in out.columns:
        out = out.with_columns(pl.col("area").replace_strict(AREA_CODE).cast(pl.Int32))
    return out


# --------------------------------------------------------------------- calendar

def _easter(y: int) -> date:
    """Gregorian Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = ((h + l_ - 7 * m + 114) % 31) + 1
    return date(y, month, day)


def national_holidays(years) -> set[str]:
    """German public holidays observed in every state (state-only holidays are excluded)."""
    out = set()
    for y in years:
        e = _easter(y)
        for d in (date(y, 1, 1), e - timedelta(days=2), e + timedelta(days=1), date(y, 5, 1),
                  e + timedelta(days=39), e + timedelta(days=50), date(y, 10, 3),
                  date(y, 12, 25), date(y, 12, 26)):
            out.add(d.isoformat())
    return out


# ------------------------------------------------------------------------ data

def load_solar() -> pl.DataFrame:
    """Day-ahead solar forecast (SMARD filter 125), MW, per area, from the raw weekly files."""
    rows = []
    for area in cfg.AREAS:
        files = sorted(glob.glob(str(SMARD / f"125_{area}" / "*.json")))
        if not files:
            raise FileNotFoundError(f"no SMARD filter 125 files for {area} under {SMARD}")
        for f in files:
            for ts, v in json.loads(Path(f).read_text(encoding="utf-8"))["series"]:
                rows.append((area, int(ts), None if v is None else float(v) * 4.0))
    return (pl.DataFrame(rows, schema=["area", "ts_utc", "f_solar_mw"], orient="row")
              .unique(["area", "ts_utc"], keep="first"))


@lru_cache(maxsize=1)
def load_rows() -> pl.DataFrame:
    from src.method.available_power import QS_DIR
    from src.method.projection_and_redispatch import load_projection, redispatch_qh
    panel = (pl.scan_parquet(PANEL)
             .filter(pl.col("area").is_in(list(cfg.AREAS))
                     & (pl.col("berlin_date") >= cfg.HISTORY_START)
                     & (pl.col("berlin_date") <= cfg.EVAL_WINDOW[1]))
             .select(["ts_utc", "area", "berlin_date", pl.col("price_eur_mwh").alias("price"),
                      pl.col("act_onshore_mw").alias("g"),
                      pl.col("da_onshore_mw").alias("f_onshore_mw"),
                      pl.col("da_offshore_mw").alias("f_offshore_mw")])
             .collect())
    days = set(panel["berlin_date"].unique().to_list())
    rd = redispatch_qh(days).filter(pl.col("area").is_in(list(cfg.AREAS)))
    hr, _ = load_projection(QS_DIR)
    hr = hr.filter(pl.col("area").is_in(list(cfg.AREAS))).select(["ts_utc", "area", pl.col("hr_mw").alias("h")])
    hol = national_holidays(range(2023, 2028))
    d = (panel.join(load_solar(), on=["area", "ts_utc"], how="left")
              .join(rd.rename({"rd_mw": "rd"}), on=["area", "ts_utc"], how="left")
              .join(hr, on=["area", "ts_utc"], how="left")
              .with_columns(pl.col("rd").fill_null(0.0),
                            pl.col("ts_utc").cast(pl.Datetime("ms")).dt.replace_time_zone("UTC")
                              .dt.convert_time_zone("Europe/Berlin").alias("_local"))
              .with_columns((pl.col("_local").dt.hour() * 4 + pl.col("_local").dt.minute() // 15)
                              .cast(pl.Int32).alias("qh_of_day"),
                            (pl.col("_local").dt.weekday() - 1).cast(pl.Int32).alias("day_of_week"),
                            pl.col("berlin_date").is_in(list(hol)).cast(pl.Int32).alias("holiday"),
                            pl.col("berlin_date").str.slice(0, 7).alias("month"))
              .drop("_local").sort(["area", "ts_utc"]))
    inputs_ok = (pl.all_horizontal(pl.col(c).is_not_null() & pl.col(c).is_finite()
                                   for c in ("f_onshore_mw", "f_offshore_mw", "f_solar_mw"))
                 & (pl.col("f_onshore_mw") > 0))
    g_ok = pl.col("g").is_not_null() & pl.col("g").is_finite() & (pl.col("g") > 0)
    return d.with_columns(
        inputs_ok.alias("valid"),
        (inputs_ok & g_ok & (pl.col("price") > cfg.CLEAN_PRICE_ABOVE) & (pl.col("rd") <= 0.0)).alias("clean"),
        (inputs_ok & (pl.col("price") < cfg.TARGET_PRICE_BELOW)).alias("target"),
        pl.when(g_ok & inputs_ok).then((pl.col("g") / pl.col("f_onshore_mw")).log()).otherwise(None).alias("y"))


# ------------------------------------------------------------------------ folds

def eval_months() -> list[str]:
    out, y, m = [], *map(int, cfg.EVAL_WINDOW[0][:7].split("-"))
    end = cfg.EVAL_WINDOW[1][:7]
    while f"{y:04d}-{m:02d}" <= end:
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def train_last_day(month: str) -> str:
    """Last Berlin date a model scoring `month` may train on (rolling origin, embargo)."""
    return (date.fromisoformat(month + "-01") - timedelta(days=cfg.EMBARGO_DAYS + 1)).isoformat()


def train_mask(df: pl.DataFrame, month: str) -> pl.Series:
    return df["clean"] & (df["berlin_date"] >= cfg.HISTORY_START) & (df["berlin_date"] <= train_last_day(month))
