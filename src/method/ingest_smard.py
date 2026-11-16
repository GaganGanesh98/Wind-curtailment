#!/usr/bin/env python3
"""Step 1 — download the raw SMARD quarter-hour series.

Writes untouched JSON exactly as served, one file per (filter, region, week) to
data/raw/smard/<filter>_<region>/<weekstart_ms>.json. Nothing is transformed
here; data/raw is append-only.

Endpoint shape (SMARD's public chart-data API):
  /app/chart_data/{filter}/{region}/index_quarterhour.json        -> week starts
  /app/chart_data/{filter}/{region}/{filter}_{region}_quarterhour_{ts}.json

Usage:  python src/ingest_smard.py [--force]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smard_config import (  # noqa: E402
    AREAS,
    BERLIN,
    FILTERS,
    OFFSHORE_AREAS,
    OFFSHORE_SERIES,
    ONSHORE_SERIES,
    PERIOD_END_BERLIN,
    PERIOD_START_BERLIN,
    RAW_DIR,
    UTC,
)

BASE = "https://www.smard.de/app/chart_data"
SLEEP = 0.12  # be polite to a public service
TIMEOUT = 60
RETRIES = 4


def jobs() -> list[tuple[str, int, str]]:
    """(series_name, filter_id, region) for every series we need."""
    out: list[tuple[str, int, str]] = []
    for name in ONSHORE_SERIES:
        for area in AREAS:
            out.append((name, FILTERS[name], area))
    for name in OFFSHORE_SERIES:
        for area in OFFSHORE_AREAS:
            out.append((name, FILTERS[name], area))
    # The DE-LU day-ahead price is identical in every SMARD region (verified),
    # so it is fetched once.
    out.append(("price", FILTERS["price"], "DE"))
    return out


def get_json(session: requests.Session, url: str) -> dict | None:
    for attempt in range(RETRIES):
        try:
            r = session.get(url, timeout=TIMEOUT)
        except requests.RequestException as exc:
            if attempt == RETRIES - 1:
                print(f"    ERROR {url}: {exc}", flush=True)
                return None
            time.sleep(1.5 * (attempt + 1))
            continue
        if r.status_code == 200:
            return r.json()
        if r.status_code == 404:
            return None
        if attempt == RETRIES - 1:
            print(f"    ERROR {url}: HTTP {r.status_code}", flush=True)
            return None
        time.sleep(1.5 * (attempt + 1))
    return None


def weeks_for_period(timestamps: list[int], start_ms: int, end_ms: int) -> list[int]:
    """Week-start timestamps whose week overlaps [start_ms, end_ms].

    SMARD chunks are weekly and start Monday 00:00 Berlin, so the chunk
    starting at ts covers [ts, next_ts). The last chunk is open-ended.
    """
    ts = sorted(timestamps)
    keep = []
    for i, t in enumerate(ts):
        nxt = ts[i + 1] if i + 1 < len(ts) else float("inf")
        if t <= end_ms and nxt > start_ms:
            keep.append(t)
    return keep


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="re-download files that already exist")
    # The extended training history (2024-01-01 onwards, brief of 31 Oct 2026) has to
    # be fetchable without editing smard_config: PERIOD_START_BERLIN also defines the
    # panel's range and the kill test's sample, and widening it there would change the
    # panel before the rebuild is actually wanted. data/raw is append-only, so pulling
    # extra weeks into it is safe on its own.
    ap.add_argument("--start", metavar="YYYY-MM-DD",
                    help="override the period start (Berlin local)")
    ap.add_argument("--end", metavar="YYYY-MM-DD",
                    help="override the period end (Berlin local, inclusive day)")
    args = ap.parse_args()

    start = PERIOD_START_BERLIN
    end = PERIOD_END_BERLIN
    if args.start:
        start = datetime.strptime(args.start, "%Y-%m-%d").replace(tzinfo=BERLIN)
    if args.end:
        end = (datetime.strptime(args.end, "%Y-%m-%d")
               .replace(hour=23, minute=45, tzinfo=BERLIN))
    if end < start:
        raise SystemExit(f"end {end} is before start {start}")

    start_ms = int(start.astimezone(UTC).timestamp() * 1000)
    end_ms = int(end.astimezone(UTC).timestamp() * 1000)
    PERIOD_START_BERLIN_EFF, PERIOD_END_BERLIN_EFF = start, end

    print("=" * 72)
    print("STEP 1  ingest_smard.py")
    print(f"period (Berlin) : {PERIOD_START_BERLIN_EFF}  ..  {PERIOD_END_BERLIN_EFF}")
    print(f"period (UTC ms) : {start_ms}  ..  {end_ms}")
    print("=" * 72)

    os.makedirs(RAW_DIR, exist_ok=True)
    session = requests.Session()
    session.headers.update({
        "User-Agent": "msc-thesis-wind-curtailment/1.0 (academic research; RQ1 kill test)",
        "Accept": "application/json",
    })

    manifest = []
    total_files = total_points = total_nulls = 0
    failures = []

    for name, fid, region in jobs():
        tag = f"{fid}_{region}"
        outdir = os.path.join(RAW_DIR, tag)
        os.makedirs(outdir, exist_ok=True)

        idx = get_json(session, f"{BASE}/{fid}/{region}/index_quarterhour.json")
        time.sleep(SLEEP)
        if idx is None or "timestamps" not in idx:
            print(f"[{name:12s} {region:11s}] FAILED: no index", flush=True)
            failures.append((name, region, "no index"))
            continue

        wanted = weeks_for_period(idx["timestamps"], start_ms, end_ms)
        n_files = n_points = n_nulls = 0

        for ts in wanted:
            path = os.path.join(outdir, f"{ts}.json")
            if os.path.exists(path) and not args.force:
                with open(path) as fh:
                    payload = json.load(fh)
            else:
                url = (f"{BASE}/{fid}/{region}/"
                       f"{fid}_{region}_quarterhour_{ts}.json")
                payload = get_json(session, url)
                time.sleep(SLEEP)
                if payload is None:
                    failures.append((name, region, f"week {ts}"))
                    continue
                with open(path, "w") as fh:
                    json.dump(payload, fh)
            series = payload.get("series", [])
            n_files += 1
            n_points += len(series)
            n_nulls += sum(1 for _, v in series if v is None)

        print(f"[{name:12s} {region:11s}] weeks={len(wanted):3d} "
              f"files={n_files:3d} points={n_points:6d} nulls={n_nulls:5d}",
              flush=True)
        manifest.append({
            "series": name, "filter_id": fid, "region": region,
            "weeks_requested": len(wanted), "files": n_files,
            "points": n_points, "nulls": n_nulls,
        })
        total_files += n_files
        total_points += n_points
        total_nulls += n_nulls

    print("-" * 72)
    print(f"TOTAL  series={len(manifest)}  files={total_files}  "
          f"points={total_points}  nulls={total_nulls}")
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for f in failures[:40]:
            print("   ", f)

    with open(os.path.join(RAW_DIR, "_manifest.json"), "w") as fh:
        json.dump({
            "downloaded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "SMARD (Bundesnetzagentur), CC BY 4.0, https://www.smard.de",
            "unit_note": "quarterhour values are MWh per quarter-hour; MW = value * 4",
            "period_start_berlin": str(PERIOD_START_BERLIN),
            "period_end_berlin": str(PERIOD_END_BERLIN),
            "series": manifest,
            "failures": [list(f) for f in failures],
        }, fh, indent=2)
    print(f"manifest -> {RAW_DIR}/_manifest.json")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
