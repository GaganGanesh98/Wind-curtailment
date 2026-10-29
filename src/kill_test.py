#!/usr/bin/env python3
"""Step 3 — Analysis 1 (sample size) and Analysis 2 (bias by price band).

Definitions
  wind        = onshore + offshore
  e_t         = actual wind feed-in - TSO day-ahead wind forecast, MW
                (negative = over-forecast)
  negative QH = DE-LU day-ahead price < 0
  event-day   = Berlin-local date with >= 1 negative QH

All CIs are 95% percentile intervals from a 5,000-draw bootstrap that resamples
whole Berlin-local event-days. Seed 42.

Writes results/01_sample_size.csv, results/02_bias_by_price_band.csv,
results/02_robustness_de.csv, results/02_worst_days_de.csv.

Usage:  python src/kill_test.py
"""

from __future__ import annotations

import csv
import os
import sys

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smard_config import (  # noqa: E402
    AREAS,
    AREA_LABEL,
    N_BOOT,
    PRICE_BANDS,
    PROCESSED_DIR,
    RESULTS_DIR,
    SEED,
)
from stats_boot import ci_excludes_zero, eventday_bootstrap_mean  # noqa: E402

WIND_GATE_MW = 10_000.0  # "windy" gate: DE day-ahead wind forecast >= 10 GW
EASTER_DAYS = ["2026-04-05", "2026-04-06"]


def band_mask(price: np.ndarray, lo, hi) -> np.ndarray:
    """Band membership. Bands are lo < p <= hi, with the two exceptions needed
    to make price < 0 exactly equal to the union of the four negative bands."""
    if lo is None:                      # <= -50
        return price <= hi
    if hi is None:                      # > 5
        return price > lo
    if lo == -5.0 and hi == 0.0:        # -5 < p < 0   (0 is not negative)
        return (price > lo) & (price < hi)
    if lo == 0.0 and hi == 5.0:         # 0 <= p <= 5
        return (price >= lo) & (price <= hi)
    return (price > lo) & (price <= hi)


def load() -> pl.DataFrame:
    path = os.path.join(PROCESSED_DIR, "panel_qh.parquet")
    panel = pl.read_parquet(path)
    # keep only quarter-hours where price and the error are both available
    before = panel.height
    panel = panel.filter(
        pl.col("price_eur_mwh").is_not_null() & pl.col("price_eur_mwh").is_not_nan()
        & pl.col("e_mw").is_not_null() & pl.col("e_mw").is_not_nan()
        & pl.col("da_wind_mw").is_not_null() & pl.col("da_wind_mw").is_not_nan()
    )
    print(f"  usable rows {panel.height} of {before} "
          f"(dropped {before - panel.height} for missing price/forecast/actual)")
    return panel


def arrays(panel: pl.DataFrame, area: str):
    a = panel.filter(pl.col("area") == area).sort("ts_utc")
    return (a["price_eur_mwh"].to_numpy(),
            a["e_mw"].to_numpy(),
            a["da_wind_mw"].to_numpy(),
            a["e_id_mw"].to_numpy(),
            a["berlin_date"].to_numpy(),
            a["ts_utc"].to_numpy())


def main() -> int:
    print("=" * 72)
    print("STEP 3  kill_test.py")
    print(f"bootstrap: {N_BOOT} draws, event-day clusters, seed {SEED}")
    print("=" * 72)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    panel = load()

    # DE-level windiness gate, shared by every area so the subsample is the
    # same set of quarter-hours everywhere.
    de = panel.filter(pl.col("area") == "DE").sort("ts_utc")
    de_ts = de["ts_utc"].to_numpy()
    de_gate = de["da_wind_mw"].to_numpy() >= WIND_GATE_MW
    gate_by_ts = dict(zip(de_ts.tolist(), de_gate.tolist()))

    # ================= ANALYSIS 1 — sample size =========================
    print("-" * 72)
    print("ANALYSIS 1  sample size vs pivot thresholds")
    price, e, da, e_id, days, ts = arrays(panel, "DE")
    neg = price < 0.0
    gate = np.array([gate_by_ts.get(int(t), False) for t in ts])

    n_neg_qh = int(neg.sum())
    neg_days = sorted(set(days[neg].tolist()))
    n_neg_days = len(neg_days)
    n_neg_qh_windy = int((neg & gate).sum())
    n_neg_days_windy = len(set(days[neg & gate].tolist()))

    sample_rows = [
        {"metric": "negative QHs (price < 0)", "value": n_neg_qh,
         "pivot_threshold": 150, "passes": n_neg_qh >= 150},
        {"metric": "event-days (>=1 negative QH)", "value": n_neg_days,
         "pivot_threshold": 20, "passes": n_neg_days >= 20},
        {"metric": "negative QHs with DE DA wind forecast >= 10 GW",
         "value": n_neg_qh_windy, "pivot_threshold": 150,
         "passes": n_neg_qh_windy >= 150},
        {"metric": "event-days with DE DA wind forecast >= 10 GW",
         "value": n_neg_days_windy, "pivot_threshold": 20,
         "passes": n_neg_days_windy >= 20},
        {"metric": "total QHs in period (usable, DE)", "value": int(len(price)),
         "pivot_threshold": "", "passes": ""},
    ]
    for r in sample_rows:
        print(f"  {r['metric']:52s} {r['value']:>7}  "
              f"threshold={r['pivot_threshold']!s:>4}  {r['passes']}")
    with open(f"{RESULTS_DIR}/01_sample_size.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, lineterminator="\n", fieldnames=list(sample_rows[0].keys()))
        w.writeheader(); w.writerows(sample_rows)

    # ================= ANALYSIS 2 — bias by price band ==================
    print("-" * 72)
    print("ANALYSIS 2  bias by price band (all areas; DE is the headline)")
    band_rows = []
    for area in AREAS:
        price, e, da, e_id, days, ts = arrays(panel, area)
        for label, lo, hi in PRICE_BANDS:
            m = band_mask(price, lo, hi)
            if m.sum() == 0:
                continue
            mean, clo, chi, n_qh, n_days = eventday_bootstrap_mean(
                e[m], days[m], n_boot=N_BOOT, seed=SEED)
            mean_fc = float(np.nanmean(da[m]))
            band_rows.append({
                "area": AREA_LABEL[area], "price_band_eur_mwh": label,
                "qhs": n_qh, "days": n_days,
                "mean_e_mw": round(mean, 1),
                "ci_lo_mw": round(clo, 1) if np.isfinite(clo) else "",
                "ci_hi_mw": round(chi, 1) if np.isfinite(chi) else "",
                "mean_da_forecast_mw": round(mean_fc, 1),
                "e_over_forecast_pct": round(100.0 * mean / mean_fc, 1)
                                        if mean_fc else "",
                "ci_excludes_zero": ci_excludes_zero(clo, chi),
            })
        if area == "DE":
            print(f"  {'band':12s} {'QHs':>6} {'days':>5} {'mean e':>9} "
                  f"{'CI lo':>9} {'CI hi':>9} {'e/fc':>7}")
            for r in band_rows:
                if r["area"] != "DE":
                    continue
                print(f"  {r['price_band_eur_mwh']:12s} {r['qhs']:>6} "
                      f"{r['days']:>5} {r['mean_e_mw']:>9} {r['ci_lo_mw']:>9} "
                      f"{r['ci_hi_mw']:>9} {r['e_over_forecast_pct']:>6}%")
    with open(f"{RESULTS_DIR}/02_bias_by_price_band.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, lineterminator="\n", fieldnames=list(band_rows[0].keys()))
        w.writeheader(); w.writerows(band_rows)

    # ---- overall negative-QH bias per area (needed by the note and test C) --
    print("-" * 72)
    print("Overall bias in negative QHs, per area")
    overall_rows = []
    for area in AREAS:
        price, e, da, e_id, days, ts = arrays(panel, area)
        m = price < 0.0
        mean, clo, chi, n_qh, n_days = eventday_bootstrap_mean(
            e[m], days[m], n_boot=N_BOOT, seed=SEED)
        mi, cli, chi_i, _, _ = eventday_bootstrap_mean(
            e_id[m], days[m], n_boot=N_BOOT, seed=SEED)
        mean_fc = float(np.nanmean(da[m]))
        overall_rows.append({
            "area": AREA_LABEL[area], "qhs": n_qh, "days": n_days,
            "mean_e_da_mw": round(mean, 1),
            "ci_lo_mw": round(clo, 1), "ci_hi_mw": round(chi, 1),
            "ci_excludes_zero": ci_excludes_zero(clo, chi),
            "mean_da_forecast_mw": round(mean_fc, 1),
            "e_over_forecast_pct": round(100.0 * mean / mean_fc, 1) if mean_fc else "",
            "mean_e_id_mw": round(mi, 1),
            "id_ci_lo_mw": round(cli, 1), "id_ci_hi_mw": round(chi_i, 1),
        })
        print(f"  {AREA_LABEL[area]:11s} QHs={n_qh:5d} days={n_days:4d} "
              f"DA bias={mean:9.1f} [{clo:9.1f},{chi:9.1f}] "
              f"ID bias={mi:9.1f}")
    with open(f"{RESULTS_DIR}/02_overall_negative_qh_bias.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, lineterminator="\n", fieldnames=list(overall_rows[0].keys()))
        w.writeheader(); w.writerows(overall_rows)

    # ---- robustness (DE, negative QHs) -------------------------------------
    print("-" * 72)
    print("ANALYSIS 2  robustness (DE, all negative QHs)")
    price, e, da, e_id, days, ts = arrays(panel, "DE")
    m = price < 0.0
    e_neg, d_neg = e[m], days[m]

    # Per-day error inside negative QHs. "Worst day" can be ranked two ways and
    # the choice changes the answer, so both are reported:
    #   by_mean -- most negative *mean* e on the day (this is what v2 used)
    #   by_sum  -- most negative *total* error contributed on the day
    uniq = np.array(sorted(set(d_neg.tolist())))
    day_sum = np.array([e_neg[d_neg == d].sum() for d in uniq])
    day_n = np.array([int((d_neg == d).sum()) for d in uniq])
    day_mean = day_sum / day_n
    total_err = day_sum.sum()

    order_mean = np.argsort(day_mean)                # v2 definition
    order_sum = np.argsort(day_sum)
    worst5_mean = uniq[order_mean[:5]].tolist()
    worst5_sum = uniq[order_sum[:5]].tolist()
    top5_share_mean = (float(day_sum[order_mean[:5]].sum() / total_err)
                       if total_err else np.nan)
    top5_share_sum = (float(day_sum[order_sum[:5]].sum() / total_err)
                      if total_err else np.nan)
    order = order_sum                                # used for the ranked CSV

    with open(f"{RESULTS_DIR}/02_worst_days_de.csv", "w", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["rank_by_total_error", "berlin_date", "negative_qhs",
                    "sum_e_mw_qh", "mean_e_mw",
                    "share_of_total_negative_qh_error", "rank_by_mean_e"])
        rank_mean = {uniq[i]: r for r, i in enumerate(order_mean, start=1)}
        for rank, i in enumerate(order, start=1):
            w.writerow([rank, uniq[i], day_n[i], round(float(day_sum[i]), 1),
                        round(float(day_mean[i]), 1),
                        round(float(day_sum[i] / total_err), 4) if total_err else "",
                        rank_mean[uniq[i]]])

    def run(label, keep):
        mean, clo, chi, n_qh, n_days = eventday_bootstrap_mean(
            e_neg[keep], d_neg[keep], n_boot=N_BOOT, seed=SEED)
        print(f"  {label:34s} QHs={n_qh:5d} days={n_days:4d} "
              f"mean e={mean:9.1f} [{clo:9.1f}, {chi:9.1f}]")
        return {"variant": label, "qhs": n_qh, "days": n_days,
                "mean_e_mw": round(mean, 1), "ci_lo_mw": round(clo, 1),
                "ci_hi_mw": round(chi, 1),
                "ci_excludes_zero": ci_excludes_zero(clo, chi)}

    rob = [
        run("all negative QHs", np.ones(len(e_neg), dtype=bool)),
        run("without 5-6 Apr 2026", ~np.isin(d_neg, EASTER_DAYS)),
        run("without 5 worst days (by mean e; v2 def)",
            ~np.isin(d_neg, worst5_mean)),
        run("without 5 worst days (by total error)",
            ~np.isin(d_neg, worst5_sum)),
        run("windy only (DE DA forecast >= 10 GW)",
            np.array([gate_by_ts.get(int(t), False) for t in ts[m]])),
    ]
    rob.append({"variant": "top-5-day share of total negative-QH error "
                           "(days ranked by mean e; v2 def), %",
                "qhs": "", "days": "",
                "mean_e_mw": round(100.0 * top5_share_mean, 1), "ci_lo_mw": "",
                "ci_hi_mw": "", "ci_excludes_zero": ""})
    rob.append({"variant": "top-5-day share of total negative-QH error "
                           "(days ranked by total error), %",
                "qhs": "", "days": "",
                "mean_e_mw": round(100.0 * top5_share_sum, 1), "ci_lo_mw": "",
                "ci_hi_mw": "", "ci_excludes_zero": ""})
    print(f"  {'top5 share (ranked by mean e)':34s} "
          f"{100.0 * top5_share_mean:.1f}%   days={worst5_mean}")
    print(f"  {'top5 share (ranked by total err)':34s} "
          f"{100.0 * top5_share_sum:.1f}%   days={worst5_sum}")
    with open(f"{RESULTS_DIR}/02_robustness_de.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, lineterminator="\n", fieldnames=list(rob[0].keys()))
        w.writeheader(); w.writerows(rob)

    print("-" * 72)
    print(f"wrote {RESULTS_DIR}/01_sample_size.csv, "
          f"02_bias_by_price_band.csv, 02_overall_negative_qh_bias.csv, "
          f"02_robustness_de.csv, 02_worst_days_de.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
