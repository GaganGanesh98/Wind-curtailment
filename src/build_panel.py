#!/usr/bin/env python3
"""Step 2 — build the tidy quarter-hour panel from the raw SMARD JSON.

All timestamps are stored in UTC. Europe/Berlin is used only to derive the
local calendar date that defines event-days, and to run the DST checks.

Writes:
  data/processed/panel_qh.parquet
  results/00_data_quality.csv
  results/00_dst_check.csv

Usage:  python src/build_panel.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smard_config import (  # noqa: E402
    AREAS,
    BERLIN,
    FILTERS,
    MWH_PER_QH_TO_MW,
    OFFSHORE_AREAS,
    PERIOD_END_BERLIN,
    PERIOD_START_BERLIN,
    PROCESSED_DIR,
    RAW_DIR,
    RESULTS_DIR,
    UTC,
)

QH_MS = 15 * 60 * 1000

GEN_SERIES = ["da_onshore", "da_offshore", "id_onshore", "id_offshore",
              "act_onshore", "act_offshore"]


def load_series(filter_id: int, region: str) -> dict[int, float | None]:
    """Read every downloaded week for one series into {timestamp_ms: value}."""
    outdir = os.path.join(RAW_DIR, f"{filter_id}_{region}")
    if not os.path.isdir(outdir):
        return {}
    acc: dict[int, float | None] = {}
    dupes = 0
    for fn in sorted(os.listdir(outdir)):
        if not fn.endswith(".json"):
            continue
        with open(os.path.join(outdir, fn)) as fh:
            payload = json.load(fh)
        for ts, val in payload.get("series", []):
            if ts in acc and acc[ts] != val:
                dupes += 1
            acc[ts] = val
    if dupes:
        print(f"    WARNING {filter_id}_{region}: {dupes} conflicting duplicate "
              f"timestamps across week files", flush=True)
    return acc


def expected_grid(start_ms: int, end_ms: int) -> np.ndarray:
    return np.arange(start_ms, end_ms + QH_MS, QH_MS, dtype=np.int64)


def main() -> int:
    start_ms = int(PERIOD_START_BERLIN.astimezone(UTC).timestamp() * 1000)
    end_ms = int(PERIOD_END_BERLIN.astimezone(UTC).timestamp() * 1000)
    grid = expected_grid(start_ms, end_ms)

    print("=" * 72)
    print("STEP 2  build_panel.py")
    print(f"expected quarter-hours in period: {len(grid)}")
    print("=" * 72)

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # ---- price (one series, identical in every SMARD region) ---------------
    price_raw = load_series(FILTERS["price"], "DE")
    price = np.array([price_raw.get(int(t), np.nan) if price_raw.get(int(t)) is not None
                      else np.nan for t in grid], dtype=float)
    print(f"[price        ] on grid={np.isfinite(price).sum()} "
          f"missing={int(np.isnan(price).sum())}")

    quality_rows = []
    quality_rows.append({
        "area": "(bidding zone)", "series": "price_eur_mwh",
        "source_filter": FILTERS["price"], "unit": "EUR/MWh",
        "expected_qh": len(grid), "present": int(np.isfinite(price).sum()),
        "missing": int(np.isnan(price).sum()), "structural_zero": 0,
    })

    # ---- generation series per area ----------------------------------------
    frames = []
    for area in AREAS:
        cols: dict[str, np.ndarray] = {}
        for name in GEN_SERIES:
            is_offshore = "offshore" in name
            if is_offshore and area not in OFFSHORE_AREAS:
                # Structural zero, not missing: SMARD publishes no offshore
                # series for this control area (HTTP 404) because there is no
                # offshore wind connected there.
                cols[name] = np.zeros(len(grid), dtype=float)
                quality_rows.append({
                    "area": area, "series": name,
                    "source_filter": FILTERS[name], "unit": "MW",
                    "expected_qh": len(grid), "present": 0,
                    "missing": 0, "structural_zero": len(grid),
                })
                continue
            raw = load_series(FILTERS[name], area)
            arr = np.full(len(grid), np.nan, dtype=float)
            for i, t in enumerate(grid):
                v = raw.get(int(t))
                if v is not None:
                    arr[i] = float(v) * MWH_PER_QH_TO_MW
            cols[name] = arr
            quality_rows.append({
                "area": area, "series": name,
                "source_filter": FILTERS[name], "unit": "MW",
                "expected_qh": len(grid), "present": int(np.isfinite(arr).sum()),
                "missing": int(np.isnan(arr).sum()), "structural_zero": 0,
            })
            print(f"[{name:12s} {area:11s}] present={int(np.isfinite(arr).sum()):6d} "
                  f"missing={int(np.isnan(arr).sum()):5d}")

        da_wind = cols["da_onshore"] + cols["da_offshore"]
        id_wind = cols["id_onshore"] + cols["id_offshore"]
        act_wind = cols["act_onshore"] + cols["act_offshore"]
        e = act_wind - da_wind
        e_id = act_wind - id_wind

        berlin_dates = [
            datetime.fromtimestamp(int(t) / 1000, UTC).astimezone(BERLIN).strftime("%Y-%m-%d")
            for t in grid
        ]

        frames.append(pl.DataFrame({
            "ts_utc": grid,
            "area": [area] * len(grid),
            "berlin_date": berlin_dates,
            "price_eur_mwh": price,
            "da_onshore_mw": cols["da_onshore"],
            "da_offshore_mw": cols["da_offshore"],
            "id_onshore_mw": cols["id_onshore"],
            "id_offshore_mw": cols["id_offshore"],
            "act_onshore_mw": cols["act_onshore"],
            "act_offshore_mw": cols["act_offshore"],
            "da_wind_mw": da_wind,
            "id_wind_mw": id_wind,
            "act_wind_mw": act_wind,
            "e_mw": e,
            "e_id_mw": e_id,
        }))

    panel = pl.concat(frames)
    panel = panel.with_columns(
        pl.from_epoch(pl.col("ts_utc"), time_unit="ms").alias("ts_utc_dt")
    )

    # ---- integrity checks ---------------------------------------------------
    print("-" * 72)
    print("INTEGRITY CHECKS")

    # no duplicate (ts, area)
    n_rows = panel.height
    n_unique = panel.select(["ts_utc", "area"]).unique().height
    print(f"  rows={n_rows}  unique (ts,area)={n_unique}  "
          f"{'OK' if n_rows == n_unique else 'FAIL: duplicates'}")

    # the grid itself is contiguous by construction; assert it
    diffs = np.diff(grid)
    print(f"  grid step always 15 min: "
          f"{'OK' if (diffs == QH_MS).all() else 'FAIL'}")
    print(f"  grid covers {len(grid)} QH x {len(AREAS)} areas = "
          f"{len(grid) * len(AREAS)} rows "
          f"{'OK' if n_rows == len(grid) * len(AREAS) else 'FAIL'}")

    # DST check on Berlin-local dates
    de = panel.filter(pl.col("area") == "DE")
    per_day = (de.group_by("berlin_date")
                 .agg(pl.len().alias("n_qh"))
                 .sort("berlin_date"))
    counts = {r["berlin_date"]: r["n_qh"] for r in per_day.iter_rows(named=True)}

    first_day = PERIOD_START_BERLIN.strftime("%Y-%m-%d")
    last_day = PERIOD_END_BERLIN.strftime("%Y-%m-%d")

    def expected_qh(day: str) -> int:
        d = datetime.strptime(day, "%Y-%m-%d").date()
        a = datetime(d.year, d.month, d.day, tzinfo=BERLIN)
        b = a + timedelta(days=1)
        # true elapsed wall-clock span in Berlin, in quarter-hours
        secs = (b.astimezone(UTC) - a.astimezone(UTC)).total_seconds()
        return int(secs // 900)

    dst_rows = []
    bad = []
    for day, n in counts.items():
        exp = expected_qh(day)
        partial = day in (first_day, last_day)
        ok = (n == exp) or partial
        dst_rows.append({"berlin_date": day, "n_qh": n, "expected_qh": exp,
                         "partial_period_edge": partial, "ok": ok})
        if not ok:
            bad.append((day, n, exp))

    special = {d: (counts.get(d), expected_qh(d)) for d in
               ("2025-10-26", "2026-03-29", "2026-10-25")}
    for d, (got, exp) in special.items():
        print(f"  DST day {d}: QHs={got} expected={exp} "
              f"{'OK' if got == exp else 'FAIL'}")
    n_96 = sum(1 for r in dst_rows
               if r["n_qh"] == 96 and not r["partial_period_edge"])
    print(f"  days with exactly 96 QH (non-DST, non-edge): {n_96}")
    print(f"  days failing the QH-count check: {len(bad)} {bad[:5]}")
    print(f"  first day {first_day}: {counts.get(first_day)} QH (full day expected)")
    print(f"  last day  {last_day}: {counts.get(last_day)} QH (full day expected)")

    # ---- write -------------------------------------------------------------
    out = os.path.join(PROCESSED_DIR, "panel_qh.parquet")
    panel.write_parquet(out)
    print("-" * 72)
    print(f"panel -> {out}  ({panel.height} rows, {len(panel.columns)} cols)")

    with open(os.path.join(RESULTS_DIR, "00_data_quality.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, lineterminator="\n", fieldnames=list(quality_rows[0].keys()))
        w.writeheader()
        w.writerows(quality_rows)
    with open(os.path.join(RESULTS_DIR, "00_dst_check.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, lineterminator="\n", fieldnames=list(dst_rows[0].keys()))
        w.writeheader()
        w.writerows(sorted(dst_rows, key=lambda r: r["berlin_date"]))
    print(f"quality -> {RESULTS_DIR}/00_data_quality.csv")
    print(f"dst     -> {RESULTS_DIR}/00_dst_check.csv")

    # ---- usable-sample report ---------------------------------------------
    print("-" * 72)
    print("USABLE SAMPLE (price and e_mw both present)")
    for area in AREAS:
        a = panel.filter(pl.col("area") == area)
        usable = a.filter(
            pl.col("price_eur_mwh").is_not_null()
            & pl.col("price_eur_mwh").is_not_nan()
            & pl.col("e_mw").is_not_null()
            & pl.col("e_mw").is_not_nan()
        ).height
        print(f"  {area:11s} usable={usable:6d} / {a.height}  "
              f"dropped={a.height - usable}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
