#!/usr/bin/env python3
"""Step 4 — Check 1: is the SMARD "day-ahead" series really a day-ahead forecast?

Three pieces of evidence:
  (a) documentary  — SMARD's own chart configuration puts filters 123/3791
      under "Prognostizierte Erzeugung Day-Ahead" and 5127/5128 under a
      separate "Prognostizierte Erzeugung Intraday" subcategory (logged by
      ingest; archived in data/raw);
  (b) the share of quarter-hours where day-ahead and intraday are identical --
      if the two series were the same product this would be ~100%;
  (c) the MAE of each -- a later forecast should be clearly more accurate.

Also reports the intraday forecast's own bias in negative quarter-hours.

Writes results/03_da_vs_id.csv, results/03_id_bias_negative_qh.csv.

Usage:  python src/check_da_vs_id.py
"""

from __future__ import annotations

import csv
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smard_config import (  # noqa: E402
    AREAS, AREA_LABEL, N_BOOT, PROCESSED_DIR, RESULTS_DIR, SEED,
)
from stats_boot import ci_excludes_zero, eventday_bootstrap_mean  # noqa: E402

# "identical" allows for SMARD's published rounding (values are MWh/QH to 2dp,
# scaled by 4 here, so 0.01 MWh/QH -> 0.04 MW).
IDENTICAL_TOL_MW = 0.05


def main() -> int:
    print("=" * 72)
    print("STEP 4  check_da_vs_id.py   (Check 1)")
    print("=" * 72)
    panel = pl.read_parquet(os.path.join(PROCESSED_DIR, "panel_qh.parquet"))
    os.makedirs(RESULTS_DIR, exist_ok=True)

    rows = []
    print(f"  {'area':11s} {'QHs':>6} {'DA==ID':>8} {'MAE DA':>9} {'MAE ID':>9} "
          f"{'MAE red.':>9}")
    for area in AREAS:
        a = (panel.filter(pl.col("area") == area)
                  .filter(pl.col("da_wind_mw").is_not_nan()
                          & pl.col("id_wind_mw").is_not_nan()
                          & pl.col("act_wind_mw").is_not_nan())
                  .sort("ts_utc"))
        da = a["da_wind_mw"].to_numpy()
        idf = a["id_wind_mw"].to_numpy()
        act = a["act_wind_mw"].to_numpy()

        same = np.abs(da - idf) <= IDENTICAL_TOL_MW
        mae_da = float(np.mean(np.abs(act - da)))
        mae_id = float(np.mean(np.abs(act - idf)))
        share_same = 100.0 * float(same.mean())
        reduction = 100.0 * (mae_da - mae_id) / mae_da if mae_da else np.nan

        rows.append({
            "area": AREA_LABEL[area], "qhs_compared": int(len(da)),
            "share_da_equals_id_pct": round(share_same, 2),
            "mae_da_mw": round(mae_da, 1), "mae_id_mw": round(mae_id, 1),
            "mae_reduction_id_vs_da_pct": round(reduction, 1),
        })
        print(f"  {AREA_LABEL[area]:11s} {len(da):>6} {share_same:>7.2f}% "
              f"{mae_da:>9.1f} {mae_id:>9.1f} {reduction:>8.1f}%")

    with open(f"{RESULTS_DIR}/03_da_vs_id.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, lineterminator="\n", fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    # ---- how "identical" is defined changes the headline number, so sweep it -
    print("-" * 72)
    print("Share of QHs where day-ahead == intraday, by tolerance")
    tol_rows = []
    tols = [("exact", 0.0), ("<=0.05 MW", 0.05), ("<=1 MW", 1.0),
            ("<=10 MW", 10.0)]
    print(f"  {'area':11s}" + "".join(f"{t[0]:>11}" for t in tols)
          + f"{'<=0.5% rel':>11}")
    for area in AREAS:
        a = (panel.filter(pl.col("area") == area)
                  .filter(pl.col("da_wind_mw").is_not_nan()
                          & pl.col("id_wind_mw").is_not_nan()))
        da = a["da_wind_mw"].to_numpy()
        idf = a["id_wind_mw"].to_numpy()
        diff = np.abs(da - idf)
        row = {"area": AREA_LABEL[area], "qhs_compared": int(len(da))}
        cells = []
        for name, t in tols:
            v = 100.0 * float((diff <= t).mean())
            row[f"share_identical_{name.replace('<=', 'le_').replace(' ', '').replace('%','pct')}_pct"] = round(v, 3)
            cells.append(v)
        rel = 100.0 * float((diff <= 0.005 * np.maximum(np.abs(da), 1.0)).mean())
        row["share_identical_le_0p5pct_relative_pct"] = round(rel, 3)
        tol_rows.append(row)
        print(f"  {AREA_LABEL[area]:11s}"
              + "".join(f"{c:>10.2f}%" for c in cells) + f"{rel:>10.2f}%")
    with open(f"{RESULTS_DIR}/03_da_id_identity_tolerance.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, lineterminator="\n", fieldnames=list(tol_rows[0].keys()))
        w.writeheader(); w.writerows(tol_rows)

    # ---- intraday bias in negative quarter-hours ---------------------------
    print("-" * 72)
    print("Intraday forecast bias in negative QHs (vs day-ahead)")
    bias_rows = []
    print(f"  {'area':11s} {'QHs':>6} {'days':>5} {'DA bias':>10} "
          f"{'ID bias':>10} {'ID CI':>24}")
    for area in AREAS:
        a = (panel.filter(pl.col("area") == area)
                  .filter(pl.col("price_eur_mwh").is_not_nan()
                          & pl.col("e_mw").is_not_nan()
                          & pl.col("e_id_mw").is_not_nan())
                  .filter(pl.col("price_eur_mwh") < 0.0)
                  .sort("ts_utc"))
        e = a["e_mw"].to_numpy()
        e_id = a["e_id_mw"].to_numpy()
        days = a["berlin_date"].to_numpy()
        m_da, lo_da, hi_da, n, nd = eventday_bootstrap_mean(e, days, N_BOOT, SEED)
        m_id, lo_id, hi_id, _, _ = eventday_bootstrap_mean(e_id, days, N_BOOT, SEED)
        bias_rows.append({
            "area": AREA_LABEL[area], "negative_qhs": n, "event_days": nd,
            "mean_e_da_mw": round(m_da, 1),
            "da_ci_lo_mw": round(lo_da, 1), "da_ci_hi_mw": round(hi_da, 1),
            "mean_e_id_mw": round(m_id, 1),
            "id_ci_lo_mw": round(lo_id, 1), "id_ci_hi_mw": round(hi_id, 1),
            "id_ci_excludes_zero": ci_excludes_zero(lo_id, hi_id),
            "residual_bias_share_id_vs_da_pct":
                round(100.0 * m_id / m_da, 1) if m_da else "",
        })
        print(f"  {AREA_LABEL[area]:11s} {n:>6} {nd:>5} {m_da:>10.1f} "
              f"{m_id:>10.1f}   [{lo_id:>9.1f},{hi_id:>9.1f}]")

    with open(f"{RESULTS_DIR}/03_id_bias_negative_qh.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, lineterminator="\n", fieldnames=list(bias_rows[0].keys()))
        w.writeheader(); w.writerows(bias_rows)
    print("-" * 72)
    print(f"wrote {RESULTS_DIR}/03_da_vs_id.csv, "
          f"03_da_id_identity_tolerance.csv, 03_id_bias_negative_qh.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
