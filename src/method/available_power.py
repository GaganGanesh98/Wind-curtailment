"""Q0b: does the Online-Hochrechnung add back market curtailment?

    python -m src.method.available_power

Implements `docs/Q0b_preregistration.md` (commit 06de287) and nothing else: the
statistic, bands, baseline, bootstrap, clauses and verdict rule are all fixed there.
Writes, under `artifacts/Q0b/`:

  q0b_gap_shares.csv   gap share sum(P - G - R)/sum(P) and the mean MW gap, per series,
                       estimator (H or F), area and quarter-hour set, with 95% CIs
  q0b_verdicts.csv     clause A, clause B and the verdict, per series and area
  q0b_h_agreement.csv  sigma and bias of log(G/H) and corr(H, G) on positive-price
                       quarter-hours -- the evidence `docs/Q0_preregistration.md`
                       Amendment 1 rests on

Two series, never pooled (Q0b section 2): the QUALITY-ASSURED projection, which decides,
and the OPERATIONAL one already on disk as Anchor H, reported for comparison.
"""

from __future__ import annotations

import csv
import subprocess
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl

from src.method.projection_and_redispatch import HR_DIR, load_projection, redispatch_qh
from src.method.day_bootstrap import (
    BANDS, N_BOOT, PANEL_PATH, SEED, band_of, bootstrap_day_sums, ci95,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "artifacts" / "Q0b"
PREREG_COMMIT = "06de287"
QS_DIR = (REPO_ROOT / "data" / "raw" / "netztransparenz"
          / "hochrechnung_wind_onshore_qualitaetsgesichert")

SERIES = {
    "quality-assured": (QS_DIR, ("2025-10-01", "2026-10-28")),
    "operational": (HR_DIR, ("2026-09-01", "2026-10-28")),
}
AREAS = ("50Hertz", "Amprion", "TransnetBW", "TenneT")
AGG = ("50Hertz", "Amprion", "TransnetBW")
AGG_NAME = "50Hertz+Amprion+TransnetBW"
BAND_ORDER = tuple(b for b, _, _ in BANDS)      # shallow to deep
THIN_DAYS = 5
MIN_TESTABLE_BANDS = 3


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:                                            # noqa: BLE001
        return "unknown"


# ----------------------------------------------------------------------- data


def load_frames(series: str) -> dict[str, pl.DataFrame]:
    """Per area: price, G, F, H and R on common quarter-hours inside the window."""
    hr_dir, (d0, d1) = SERIES[series]
    hr, empty = load_projection(hr_dir)
    panel = (pl.scan_parquet(PANEL_PATH)
             .filter(pl.col("area").is_in(list(AREAS))
                     & (pl.col("berlin_date") >= d0) & (pl.col("berlin_date") <= d1))
             .select(["ts_utc", "area", "berlin_date", "price_eur_mwh",
                      "act_onshore_mw", "da_onshore_mw"])
             .collect())
    days = set(panel["berlin_date"].unique().to_list())
    rd = redispatch_qh(days)
    out: dict[str, pl.DataFrame] = {}
    for area in AREAS:
        p = panel.filter(pl.col("area") == area).drop("area")
        h = hr.filter(pl.col("area") == area).select(["ts_utc", "hr_mw"])
        r = rd.filter(pl.col("area") == area).select(["ts_utc", "rd_mw"])
        df = (p.join(h, on="ts_utc", how="inner")
               .join(r, on="ts_utc", how="left")
               .with_columns(pl.col("rd_mw").fill_null(0.0))
               .drop_nulls(["price_eur_mwh", "act_onshore_mw", "da_onshore_mw", "hr_mw"])
               .filter(pl.col("act_onshore_mw").is_not_nan()
                       & pl.col("da_onshore_mw").is_not_nan() & pl.col("hr_mw").is_not_nan())
               .sort("ts_utc"))
        out[area] = df
    # The aggregate, on the quarter-hours where all three areas are present, summed.
    parts = [out[a].select(["ts_utc", "berlin_date", "price_eur_mwh",
                            pl.col("act_onshore_mw").alias(f"g_{a}"),
                            pl.col("da_onshore_mw").alias(f"f_{a}"),
                            pl.col("hr_mw").alias(f"h_{a}"),
                            pl.col("rd_mw").alias(f"r_{a}")]) for a in AGG]
    agg = parts[0]
    for q in parts[1:]:
        agg = agg.join(q.drop(["berlin_date", "price_eur_mwh"]), on="ts_utc", how="inner")
    agg = agg.with_columns(
        sum(pl.col(f"g_{a}") for a in AGG).alias("act_onshore_mw"),
        sum(pl.col(f"f_{a}") for a in AGG).alias("da_onshore_mw"),
        sum(pl.col(f"h_{a}") for a in AGG).alias("hr_mw"),
        sum(pl.col(f"r_{a}") for a in AGG).alias("rd_mw"),
    ).select(["ts_utc", "berlin_date", "price_eur_mwh", "act_onshore_mw",
              "da_onshore_mw", "hr_mw", "rd_mw"]).sort("ts_utc")
    out[AGG_NAME] = agg
    out["_empty_cells"] = empty                                   # type: ignore[assignment]
    return out


# ----------------------------------------------------------------- statistics


def _per_day(day_idx: np.ndarray, n_days: int, *cols: np.ndarray) -> np.ndarray:
    out = np.zeros((n_days, len(cols)))
    for j, c in enumerate(cols):
        np.add.at(out[:, j], day_idx, c)
    return out


def gap_share(df: pl.DataFrame, mask: np.ndarray, which: str) -> dict:
    """sum(P - G - R)/sum(P) on `mask`, with an event-day block-bootstrap CI.

    The resampled days are the days carrying at least one quarter-hour of the set,
    which is what the Phase P event-day rule means for a set-specific statistic.
    """
    p = df["hr_mw" if which == "H" else "da_onshore_mw"].to_numpy().astype(float)
    g = df["act_onshore_mw"].to_numpy().astype(float)
    r = df["rd_mw"].to_numpy().astype(float)
    days = df["berlin_date"].to_numpy().astype(str)
    m = np.asarray(mask, dtype=bool)
    n_qh = int(m.sum())
    if n_qh == 0:
        return {"n_qh": 0, "n_days": 0, "gap_share": np.nan, "ci_lo": np.nan,
                "ci_hi": np.nan, "mean_gap_mw": np.nan, "mean_r_mw": np.nan,
                "r_share": np.nan, "thin": True}
    uniq, idx = np.unique(days[m], return_inverse=True)
    num = p[m] - g[m] - r[m]
    S = _per_day(idx, uniq.size, num, p[m])
    boot = bootstrap_day_sums(S, n_boot=N_BOOT, seed=SEED)
    lo, hi = ci95(boot[:, 0] / boot[:, 1]) if uniq.size >= 2 else (np.nan, np.nan)
    return {"n_qh": n_qh, "n_days": int(uniq.size),
            "gap_share": float(S[:, 0].sum() / S[:, 1].sum()),
            "ci_lo": lo, "ci_hi": hi, "mean_gap_mw": float(num.mean()),
            # redispatch's own size, so its share of the gap can be read off rather
            # than asserted (Q0b results section 3)
            "mean_r_mw": float(r[m].mean()), "r_share": float(r[m].sum() / p[m].sum()),
            "thin": bool(uniq.size < THIN_DAYS)}


def clause_a(df: pl.DataFrame, which: str = "H") -> dict:
    """D = share(price < 0) - share(price >= 0), PAIRED over all days (Q0b section 3)."""
    p = df["hr_mw" if which == "H" else "da_onshore_mw"].to_numpy().astype(float)
    g = df["act_onshore_mw"].to_numpy().astype(float)
    r = df["rd_mw"].to_numpy().astype(float)
    price = df["price_eur_mwh"].to_numpy().astype(float)
    days = df["berlin_date"].to_numpy().astype(str)
    neg, pos = price < 0.0, price >= 0.0
    if neg.sum() == 0 or pos.sum() == 0:
        return {"D": np.nan, "D_lo": np.nan, "D_hi": np.nan, "clause_a": None}
    uniq, idx = np.unique(days, return_inverse=True)
    num = p - g - r
    S = _per_day(idx, uniq.size, np.where(neg, num, 0.0), np.where(neg, p, 0.0),
                 np.where(pos, num, 0.0), np.where(pos, p, 0.0))
    boot = bootstrap_day_sums(S, n_boot=N_BOOT, seed=SEED)
    with np.errstate(invalid="ignore", divide="ignore"):
        d_boot = boot[:, 0] / boot[:, 1] - boot[:, 2] / boot[:, 3]
    tot = S.sum(0)
    D = float(tot[0] / tot[1] - tot[2] / tot[3])
    lo, hi = ci95(d_boot)
    return {"D": D, "D_lo": lo, "D_hi": hi,
            "clause_a": bool(np.isfinite(lo) and lo > 0.0) if np.isfinite(lo) else None}


def evaluate(df: pl.DataFrame, series: str, area: str) -> tuple[list[dict], dict]:
    price = df["price_eur_mwh"].to_numpy().astype(float)
    band = band_of(price).astype(str)
    sets = [("price < 0", price < 0.0), ("price >= 0", price >= 0.0),
            ("price > 5", price > 5.0)]
    sets += [(f"band {b}", band == b) for b in BAND_ORDER]

    rows = []
    for which in ("H", "F"):
        for name, m in sets:
            st = gap_share(df, m, which)
            rows.append({"series": series, "area": area, "estimator": which,
                         "set": name, **st,
                         "note": "point estimate, no inference" if st["thin"] and st["n_qh"] else ""})

    a = clause_a(df, "H")
    a_f = clause_a(df, "F")
    band_rows = [r for r in rows if r["estimator"] == "H" and r["set"].startswith("band ")]
    with_data = [r for r in band_rows if r["n_qh"] > 0]
    testable = len(with_data) >= MIN_TESTABLE_BANDS
    pts = [r["gap_share"] for r in with_data]
    nondecreasing = all(pts[i] <= pts[i + 1] for i in range(len(pts) - 1)) if pts else None
    clause_b = (bool(nondecreasing) if testable else None)

    if a["clause_a"] is None or clause_b is None:
        verdict = "INDETERMINATE"
    elif a["clause_a"] and clause_b:
        verdict = "ADDS BACK"
    else:
        verdict = "DOES NOT ADD BACK"
    v = {"series": series, "area": area, **a,
         "F_D": a_f["D"], "F_D_lo": a_f["D_lo"], "F_D_hi": a_f["D_hi"],
         "bands_with_data": len(with_data), "clause_b_testable": testable,
         "band_shares_shallow_to_deep": " | ".join(
             f"{r['set'][5:]}={r['gap_share']:.4f}" for r in with_data),
         "clause_b": clause_b, "verdict": verdict,
         "deciding": bool(series == "quality-assured" and area == AGG_NAME),
         "n_qh": df.height, "n_days": int(df["berlin_date"].n_unique()),
         "n_neg_qh": int((price < 0).sum())}
    return rows, v


def agreement(df: pl.DataFrame, series: str, area: str) -> dict:
    """Evidence for Q0 Amendment 1: how closely H and G agree where nothing is curtailed."""
    price = df["price_eur_mwh"].to_numpy().astype(float)
    g = df["act_onshore_mw"].to_numpy().astype(float)
    h = df["hr_mw"].to_numpy().astype(float)
    days = df["berlin_date"].to_numpy().astype(str)
    m = (price >= 0.0) & (g > 0) & (h > 0)
    x = np.log(g[m] / h[m])
    uniq, idx = np.unique(days[m], return_inverse=True)
    S = _per_day(idx, uniq.size, np.ones_like(x), x, x * x)
    boot = bootstrap_day_sums(S, n_boot=N_BOOT, seed=SEED)
    with np.errstate(invalid="ignore"):
        sd_b = np.sqrt(np.maximum(boot[:, 2] / boot[:, 0] - (boot[:, 1] / boot[:, 0]) ** 2, 0))
    lo, hi = ci95(sd_b)
    return {"series": series, "area": area, "sample": "price >= 0",
            "n_qh": int(m.sum()), "n_days": int(uniq.size),
            "sigma_log_G_over_H": float(x.std()), "sigma_lo": lo, "sigma_hi": hi,
            "bias_log_G_over_H": float(x.mean()),
            "corr_H_G": float(np.corrcoef(h[m], g[m])[0, 1]),
            "corr_dH_dG_lag1": float(np.corrcoef(np.diff(h[m]), np.diff(g[m]))[0, 1])}


def _write(name: str, rows: list[dict], head: str, today: str) -> Path:
    fields: list[str] = []
    for r in rows:
        r.update({"preregistration_commit": PREREG_COMMIT, "git_head": head,
                  "run_date": today})
        for k in r:
            if k not in fields:
                fields.append(k)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    return path


def main() -> None:
    head, today = git_head(), date.today().isoformat()
    shares, verdicts, agree = [], [], []
    for series in SERIES:
        frames = load_frames(series)
        empty = frames.pop("_empty_cells")
        print(f"\n=== {series}  (empty projection cells: {empty})")
        for area, df in frames.items():
            rows, v = evaluate(df, series, area)
            shares += rows
            verdicts.append(v)
            agree.append(agreement(df, series, area))
            print(f"  {area:<28} n={v['n_qh']:>6} neg={v['n_neg_qh']:>5}  "
                  f"D={v['D']:+.4f} [{v['D_lo']:+.4f}, {v['D_hi']:+.4f}]  "
                  f"A={v['clause_a']}  B={v['clause_b']} ({v['bands_with_data']} bands)  "
                  f"-> {v['verdict']}{'   <- DECIDES' if v['deciding'] else ''}")
            print(f"  {'':<28} bands: {v['band_shares_shallow_to_deep']}")
    for name, rows in (("q0b_gap_shares.csv", shares), ("q0b_verdicts.csv", verdicts),
                       ("q0b_h_agreement.csv", agree)):
        print("wrote", _write(name, rows, head, today))


if __name__ == "__main__":
    main()
