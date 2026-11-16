"""Q0 anchors: how accurate are the potential estimators this repo actually has?

    python -m src.experiments.available_power_anchors

Phase Q hard rule 5: the anchor levels come from this repo's own panel, measured
here, never from a paper or from the brief. Writes `artifacts/available_power_estimate/error_anchors.csv`.

WHAT AN ANCHOR IS
-----------------
Q1 multiplies the true potential by lognormal noise and asks how much the identified
sets widen. For that dial to mean anything, the levels have to be pinned to estimators
that exist. Each anchor is therefore the **multiplicative** error of a potential
estimate P against observed output G, on quarter-hours where nothing should be
switched off:

    x_t = log(G_t / P_t),     sigma = sd(x),     b = mean(x)

`sigma` is the dial's unit -- it is exactly the lognormal width Q1 injects. `b` is
the bias term Q2 uses. Both carry a 95% event-day block-bootstrap interval, 5,000
draws, seed 42, blocked on the Berlin-local date (hard rule 6).

**Why positive-price quarter-hours.** There the switch-off incentive does not exist,
so G is what the fleet produced with nothing withheld and the gap to P is the
estimator's own error rather than curtailment. The brief fixes "positive-price" as
price >= 0; this module reports price > 5 EUR/MWh beside it, because Hirth (2026)
Table 3 finds 4.2% wind curtailment already in the 0-5 band, so the two are not
interchangeable and the difference should be visible rather than assumed away.

THE ANCHORS
-----------
**T -- the TSO day-ahead forecast.** P = F, the published day-ahead wind forecast.
This is the potential every Phase P and Test 2 model actually has, and the one P3's
real-data arm used. Reported overall and restricted to the forecast-level band where
negative-price quarter-hours live, because that band is where Q's question bites.

**H -- the Online-Hochrechnung.** P = the Netztransparenz Anlage 1 Nr. 5.1 online
projection for wind onshore. By statute it excludes both grid curtailment and
direct-marketing reductions, and `results/39_nr51_compliance.csv` shows it passing
that test in all four control areas, so it is an official, published, quarter-hourly
estimate of uncurtailed potential -- a genuinely better P than F, measured rather
than imagined. It is ex post and is on the Phase P leakage list as never a forecast
input; Q1 and Q2 are identification questions, not forecasts, so that does not bite
here.

  **TenneT is excluded from every aggregate.** `docs/09` Amendment 4 A4.5 makes
  T-D(vii) a *precondition*, not a diagnostic: no DE-level aggregate may use the
  projection until TenneT's positive-price ratio of 0.839 is explained or TenneT is
  excluded and the exclusion stated. It is not explained, so it is excluded and
  stated, and TenneT's own row is reported on its own so the anomaly stays visible.

**W -- a weather-based potential.** Does not exist in this repo: there is no ERA5 or
ICON potential series, and no CDS credential. Recorded `[UNRESOLVED -- needs P2]`.

**Z -- exact.** Zero by construction, the P3 Arm O case.
"""

from __future__ import annotations

import csv
import subprocess
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl

from src.method.day_bootstrap import (
    AREAS, ARTIFACTS, N_BOOT, SAFE_FLOOR, SEED, SERIES, WINDOW_START,
    bootstrap_day_sums, ci95, day_index, load_window,
)

OUT_DIR = ARTIFACTS / "available_power_estimate"

#: The forecast-level band Q cares about: where the negative-price quarter-hours
#: actually sit. Percentiles of F over the negative-price quarter-hours of the same
#: area and series, so the band is read off the data rather than chosen.
BAND_PCTILES = (10.0, 90.0)

#: Ratios outside this are not an estimator error, they are a broken row.
RATIO_SANITY = (0.01, 100.0)

AREAS_FOR_H = ("50Hertz", "Amprion", "TransnetBW")   # TenneT excluded, see module docstring
TENNET = "TenneT"


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:                                            # noqa: BLE001
        return "unknown"


# ------------------------------------------------------------------ statistics


def _per_day(x: np.ndarray, idx: np.ndarray, n_days: int) -> np.ndarray:
    out = np.zeros((n_days, 3))
    np.add.at(out[:, 0], idx, 1.0)
    np.add.at(out[:, 1], idx, x)
    np.add.at(out[:, 2], idx, x * x)
    return out


def _mean(S: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        return S[..., 1] / S[..., 0]


def _sd(S: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.sqrt(np.maximum(S[..., 2] / S[..., 0] - (S[..., 1] / S[..., 0]) ** 2, 0.0))


def log_ratio_stats(g: np.ndarray, p: np.ndarray, days: np.ndarray,
                    mask: np.ndarray) -> dict:
    """mean and sd of log(G/P) on `mask`, with event-day block-bootstrap intervals.

    Rows where either side is non-positive or non-finite have no logarithm and are
    dropped and COUNTED, never filled: a quarter-hour with zero output is a real
    quarter-hour, and silently treating it as a ratio of one would flatter the
    estimator.
    """
    ok = mask & np.isfinite(g) & np.isfinite(p) & (g > 0) & (p > 0)
    dropped = int(mask.sum() - ok.sum())
    if ok.sum() < 2:
        return {"n_qh": int(ok.sum()), "n_days": 0, "n_dropped": dropped,
                "sigma": np.nan, "sigma_lo": np.nan, "sigma_hi": np.nan,
                "bias": np.nan, "bias_lo": np.nan, "bias_hi": np.nan,
                "n_outside_sanity": 0}

    ratio = g[ok] / p[ok]
    lo, hi = RATIO_SANITY
    insane = int(((ratio < lo) | (ratio > hi)).sum())
    x = np.log(ratio)
    uniq, idx = day_index(days[ok])
    S = _per_day(x, idx, uniq.size)
    boot = bootstrap_day_sums(S, n_boot=N_BOOT, seed=SEED)
    s_lo, s_hi = ci95(_sd(boot))
    b_lo, b_hi = ci95(_mean(boot))
    tot = S.sum(0)
    return {"n_qh": int(ok.sum()), "n_days": int(uniq.size), "n_dropped": dropped,
            "sigma": float(_sd(tot)), "sigma_lo": s_lo, "sigma_hi": s_hi,
            "bias": float(_mean(tot)), "bias_lo": b_lo, "bias_hi": b_hi,
            "n_outside_sanity": insane}


# ------------------------------------------------------------------- anchor T


def anchor_t(area: str, series: str) -> list[dict]:
    f_col, g_col = SERIES[series]
    df = load_window(area)
    f = df[f_col].to_numpy().astype(float)
    g = df[g_col].to_numpy().astype(float)
    price = df["price_eur_mwh"].to_numpy()
    days = df["berlin_date"].to_numpy().astype(str)

    neg = price < 0
    finite_f = np.isfinite(f)
    band = (np.nan, np.nan)
    if (neg & finite_f).any():
        band = tuple(np.percentile(f[neg & finite_f], BAND_PCTILES))

    base = {"anchor": "T", "estimator": "TSO day-ahead forecast F",
            "area": area, "series": series, "window_start": WINDOW_START}
    rows = []
    for label, m, note in (
        ("price >= 0", price >= 0.0, "the brief's definition of positive-price"),
        (f"price > {SAFE_FLOOR:g}", price > SAFE_FLOOR,
         "the no-incentive set used elsewhere in the repo; Hirth Table 3 finds 4.2% "
         "curtailment in the 0-5 band, so this is not the same sample"),
        ("price >= 0, in the negative-QH forecast band",
         (price >= 0.0) & finite_f & (f >= band[0]) & (f <= band[1]),
         f"F in [{band[0]:.0f}, {band[1]:.0f}] MW, the {BAND_PCTILES[0]:.0f}-"
         f"{BAND_PCTILES[1]:.0f}th percentile of F over negative-price quarter-hours"),
    ):
        st = log_ratio_stats(g, f, days, m)
        rows.append({**base, "sample": label, **st, "band_lo_mw": band[0],
                     "band_hi_mw": band[1], "note": note})
    return rows


# ------------------------------------------------------------------- anchor H


def _projection() -> pl.DataFrame:
    """The Nr. 5.1 projection, long format, through the repo's working reader.

    `src/check_nr51_compliance.py` is used rather than
    `src/check_hochrechnung_onshore.py`: the latter has carried a module-level
    `re.compile` with no `import re` in every commit it has ever appeared in, so it
    raises `NameError` on import and cannot be the source of anything. That is
    recorded in `docs/Q0_preregistration.md` section 1.4 and fixed separately; it is
    not fixed here because this module has a working alternative and Q0 should not
    depend on a repair of its own making.
    """
    from src.method.projection_and_redispatch import load_projection

    df, empty = load_projection()
    return df.with_columns(pl.lit(str(empty)).alias("_empty_cells"))


def anchor_h() -> list[dict]:
    hr = _projection()
    empty_note = hr["_empty_cells"][0] if hr.height else "{}"
    rows: list[dict] = []
    per_area: dict[str, dict[str, np.ndarray]] = {}

    for area in (*AREAS_FOR_H, TENNET):
        sub = hr.filter(pl.col("area") == area).select(["ts_utc", "hr_mw"])
        if sub.height == 0:
            continue
        panel = (load_window(area, start="2000-01-01")
                 .select(["ts_utc", "berlin_date", "price_eur_mwh", "act_onshore_mw",
                          "da_onshore_mw"]))
        j = panel.join(sub, on="ts_utc", how="inner").sort("ts_utc")
        if j.height == 0:
            continue
        d = {"g": j["act_onshore_mw"].to_numpy().astype(float),
             "p": j["hr_mw"].to_numpy().astype(float),
             "f": j["da_onshore_mw"].to_numpy().astype(float),
             "price": j["price_eur_mwh"].to_numpy().astype(float),
             "days": j["berlin_date"].to_numpy().astype(str),
             "ts": j["ts_utc"].to_numpy().astype("int64")}
        per_area[area] = d

        for label, m in (("price >= 0", d["price"] >= 0.0),
                         (f"price > {SAFE_FLOOR:g}", d["price"] > SAFE_FLOOR)):
            st = log_ratio_stats(d["g"], d["p"], d["days"], m)
            rows.append({
                "anchor": "H", "estimator": "Online-Hochrechnung (Anlage 1 Nr. 5.1)",
                "area": area, "series": "onshore",
                "window_start": str(j["berlin_date"].min()), "sample": label, **st,
                "band_lo_mw": np.nan, "band_hi_mw": np.nan,
                "note": ("REPORTED ONLY, excluded from every aggregate: T-D(vii) is a "
                         "precondition and TenneT's 0.839 positive-price ratio is "
                         "unexplained (docs/09 A4.5)" if area == TENNET else
                         f"projection covers 2026-09-01 onwards only; empty cells {empty_note}"),
            })

    # The aggregate, on the quarter-hours where all three areas are present. Joining
    # on the timestamp rather than trusting positional alignment: TransnetBW has 292
    # empty cells and TenneT 96, so the per-area series are NOT the same length.
    have = [a for a in AREAS_FOR_H if a in per_area]
    if len(have) == len(AREAS_FOR_H):
        common = set(per_area[have[0]]["ts"])
        for a in have[1:]:
            common &= set(per_area[a]["ts"])
        ts_sorted = np.array(sorted(common), dtype="int64")
        if ts_sorted.size:
            g = np.zeros(ts_sorted.size)
            p = np.zeros(ts_sorted.size)
            f = np.zeros(ts_sorted.size)
            for a in have:
                d = per_area[a]
                order = {t: i for i, t in enumerate(d["ts"])}
                idx = np.array([order[t] for t in ts_sorted])
                g += d["g"][idx]
                p += d["p"][idx]
                f += d["f"][idx]
            d0 = per_area[have[0]]
            order0 = {t: i for i, t in enumerate(d0["ts"])}
            idx0 = np.array([order0[t] for t in ts_sorted])
            price, days = d0["price"][idx0], d0["days"][idx0]
            for label, m in (("price >= 0", price >= 0.0),
                             (f"price > {SAFE_FLOOR:g}", price > SAFE_FLOOR)):
                st = log_ratio_stats(g, p, days, m)
                rows.append({
                    "anchor": "H", "estimator": "Online-Hochrechnung (Anlage 1 Nr. 5.1)",
                    "area": "DE excl. TenneT (" + "+".join(have) + ")",
                    "series": "onshore", "window_start": min(days.tolist()),
                    "sample": label, **st, "band_lo_mw": np.nan, "band_hi_mw": np.nan,
                    "note": "TenneT excluded and the exclusion stated, per T-D(vii); "
                            f"{ts_sorted.size} quarter-hours where all three areas report",
                })
                st_f = log_ratio_stats(g, f, days, m)
                rows.append({
                    "anchor": "T|H-matched", "estimator": "TSO day-ahead forecast F",
                    "area": "DE excl. TenneT (" + "+".join(have) + ")",
                    "series": "onshore", "window_start": min(days.tolist()),
                    "sample": label, **st_f, "band_lo_mw": np.nan, "band_hi_mw": np.nan,
                    "note": "the SAME quarter-hours and areas as the Anchor H aggregate "
                            "above: this is the like-for-like comparison",
                })
    return rows


def main() -> None:
    head, today = git_head(), date.today().isoformat()
    rows: list[dict] = []
    for area in AREAS:
        for series in SERIES:
            rows += anchor_t(area, series)
    try:
        rows += anchor_h()
    except Exception as exc:                                     # noqa: BLE001
        rows.append({"anchor": "H", "estimator": "Online-Hochrechnung", "area": "",
                     "series": "onshore", "sample": "", "note": f"UNAVAILABLE: {exc}"})
    rows.append({"anchor": "W", "estimator": "weather-based potential (ERA5 / ICON)",
                 "area": "DE", "series": "onshore", "sample": "",
                 "sigma": np.nan, "bias": np.nan,
                 "note": "[UNRESOLVED -- needs P2] no ERA5 or ICON potential series "
                         "exists in this repo and there is no CDS credential"})
    rows.append({"anchor": "Z", "estimator": "exact potential (P3 Arm O)",
                 "area": "", "series": "", "sample": "", "sigma": 0.0, "bias": 0.0,
                 "note": "zero by construction"})

    fields: list[str] = []
    for r in rows:
        r["git_head"], r["run_date"] = head, today
        for k in r:
            if k not in fields:
                fields.append(k)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "error_anchors.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})

    print(f"{'anchor':<7}{'area':<34}{'series':<9}{'sample':<42}"
          f"{'sigma':>9}{'[CI]':>22}{'bias':>9}{'n_qh':>8}{'days':>6}")
    for r in rows:
        if not np.isfinite(r.get("sigma", np.nan)):
            print(f"{r['anchor']:<7}{str(r.get('area','')):<34}"
                  f"{str(r.get('series','')):<9}{str(r.get('sample','')):<42}"
                  f"{'--':>9}{'':>22}{'--':>9}  {r['note'][:60]}")
            continue
        ci = (f"[{r['sigma_lo']:.4f}, {r['sigma_hi']:.4f}]"
              if np.isfinite(r.get("sigma_lo", np.nan)) else "")
        print(f"{r['anchor']:<7}{r['area']:<34}{r['series']:<9}{r['sample']:<42}"
              f"{r['sigma']:>9.4f}{ci:>22}{r['bias']:>9.4f}"
              f"{r.get('n_qh', 0):>8}{r.get('n_days', 0):>6}")
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
