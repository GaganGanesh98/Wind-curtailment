"""Validate the Netztransparenz market-value files against the panel and the rules.

    python src/validate_market_values.py

Block 4 of the 31 Oct 2026 brief. Two checks.

**(i) Known annual values.** JW Wind an Land must read 7.441 ct/kWh for 2025 -- the
value already in use -- and 6.293 ct/kWh for 2024.

**(ii) The negative-price flags.** Each monthly file carries rows
"Negative Preise (6H)", "(4H)", "(3H)", "(2H)", "(1H)", "(15MIN)" saying whether the
month contained a negative-price run of at least that length. Those flags are
Netztransparenz's own reading of the §51 trigger, so they are an independent check on
this project's trigger logic. Every month the panel covers is compared and **every
mismatch is reported**; the brief's instruction is to stop on one rather than work
around it.

The "(2CT)" row is ignored: it refers to the §51b biogas regime (payment reduced where
the spot price is at or below 2 ct/kWh), not to §51, and it is unverified here.

Two details that matter for reading the files
---------------------------------------------
* **The decimal separator is not consistent between the two file types.** The monthly
  files use a comma ("6,502") and the annual files a dot ("6.293"). Both are parsed.
* **"MW" and "Spotmarktpreis" are the same number** in every file checked, and both
  are the all-technology value. Only "MW Wind an Land" is the onshore wind market
  value. Using "MW" would silently substitute the fleet-wide price for the wind one.

What the flags mean here
------------------------
A calendar hour is negative when the mean of its four quarter-hour prices is below
zero (§100(45) EEG 2023), which is what `build_clock_features` computes. The "(NH)"
flag is then "the month contains a run of at least N consecutive negative hours", and
"(15MIN)" is "the month contains at least one negative quarter-hour". A run that
straddles a month boundary is counted in both months, which is the only reading that
does not depend on where the boundary falls.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.method.exposure import build_clock_features  # noqa: E402

RAW = REPO_ROOT / "data" / "raw" / "netztransparenz"
PANEL = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"
OUT_CSV = REPO_ROOT / "artifacts" / "method_inputs" / "market_value_validation.csv"

MONTHS_DE = {"Jan": 1, "Feb": 2, "Mär": 3, "Mrz": 3, "Apr": 4, "Mai": 5, "Jun": 6,
             "Jul": 7, "Aug": 8, "Sep": 9, "Okt": 10, "Nov": 11, "Dez": 12}
EXPECTED_JW = {2024: 6.293, 2025: 7.441}
HOUR_FLAGS = (("Negative Preise (6H)", 6), ("Negative Preise (4H)", 4),
              ("Negative Preise (3H)", 3), ("Negative Preise (2H)", 2),
              ("Negative Preise (1H)", 1))
QH_FLAG = "Negative Preise (15MIN)"


def read_rows(path: Path) -> tuple[list[str], dict[str, list[str]]]:
    """Header cells and a row map, tolerant of both decimal separators."""
    text = path.read_text(encoding="utf-8-sig")
    rows = [line.split(";") for line in text.splitlines() if line.strip(" ;")]
    header = [c.strip() for c in rows[0]]
    body = {r[0].strip(): [c.strip() for c in r[1:]] for r in rows[1:] if r[0].strip()}
    return header, body


def num(cell: str) -> float | None:
    """ct/kWh as written: monthly files use a comma, annual files a dot."""
    c = cell.strip()
    if not c:
        return None
    return float(c.replace(".", "").replace(",", ".") if "," in c else c)


def load_monthly(path: Path) -> tuple[int, dict]:
    """Year from the HEADER ROW, never the filename, plus the month columns."""
    header, body = read_rows(path)
    years, months = set(), []
    for cell in header[1:]:
        mon, _, yr = cell.strip().partition(" ")
        if mon not in MONTHS_DE:
            raise ValueError(f"{path.name}: unparsable month column {cell!r}")
        years.add(int(yr))
        months.append(MONTHS_DE[mon])
    if len(years) != 1:
        raise ValueError(f"{path.name}: header spans several years {sorted(years)}")
    return years.pop(), {"months": months, "body": body}


def panel_flags() -> dict[tuple[int, int], dict]:
    """Flags recomputed from the panel's DE prices, per (year, month)."""
    df = (pl.scan_parquet(PANEL).filter(pl.col("area") == "DE")
            .select(["ts_utc", "price_eur_mwh"]).sort("ts_utc").collect()
            .filter(pl.col("price_eur_mwh").is_not_null()
                    & pl.col("price_eur_mwh").is_not_nan()))
    ts = df["ts_utc"].to_numpy().astype(np.int64) * 1_000_000
    price = df["price_eur_mwh"].to_numpy()

    # Trim to whole calendar hours: build_clock_features refuses a partial hour
    # rather than averaging three quarter-hours into a statutory hourly price.
    hour_key = ts // (3600 * 1_000_000_000)
    _, counts = np.unique(hour_key, return_counts=True)
    first_full = 0 if counts[0] == 4 else int(counts[0])
    last_full = len(ts) - (0 if counts[-1] == 4 else int(counts[-1]))
    ts, price = ts[first_full:last_full], price[first_full:last_full]

    clock = build_clock_features(ts, price)
    key = (pl.Series("t", ts).cast(pl.Datetime("ns")).dt.replace_time_zone("UTC")
             .dt.convert_time_zone("Europe/Berlin"))
    ym = list(zip(key.dt.year().to_list(), key.dt.month().to_list()))
    ym_arr = np.array([y * 100 + m for y, m in ym])

    out = {}
    for k in np.unique(ym_arr):
        sel = ym_arr == k
        out[(int(k) // 100, int(k) % 100)] = {
            "max_hour_run": int(clock.hour_run_length[sel].max(initial=0)),
            "any_neg_qh": bool((clock.price_qh[sel] < 0).any()),
            "n_neg_qh": int((clock.price_qh[sel] < 0).sum()),
        }
    return out


def main() -> None:
    rows: list[dict] = []
    problems: list[str] = []

    # ---------------------------------------------------------------- check (i)
    print("=" * 78)
    print("CHECK (i)  annual market value, JW Wind an Land")
    print("=" * 78)
    for year, expected in sorted(EXPECTED_JW.items()):
        path = RAW / f"Jahresmarktwerte_{year}.csv"
        header, body = read_rows(path)
        hdr_year = int(header[-1].strip())
        got = num(body["JW Wind an Land"][0])
        ok = hdr_year == year and got is not None and abs(got - expected) < 1e-9
        print(f"  {path.name:<28}header year {hdr_year}   "
              f"JW Wind an Land {got} ct/kWh   expected {expected}   "
              f"{'OK' if ok else 'MISMATCH'}")
        rows.append({"check": "annual_jw", "year": year, "month": "",
                     "quantity": "JW Wind an Land ct/kWh", "file_value": got,
                     "expected": expected, "status": "OK" if ok else "MISMATCH"})
        if not ok:
            problems.append(f"JW {year}: file {got}, expected {expected}")

    # --------------------------------------------------------------- check (ii)
    print(f"\n{'=' * 78}")
    print("CHECK (ii)  monthly negative-price flags vs this project's trigger logic")
    print("=" * 78)
    recomputed = panel_flags()
    covered = sorted(recomputed)
    print(f"  Panel covers {covered[0][0]}-{covered[0][1]:02d} to "
          f"{covered[-1][0]}-{covered[-1][1]:02d} "
          f"({len(covered)} months). Months outside it cannot be checked yet.")

    for year in (2024, 2025, 2026):
        path = RAW / f"Monatsmarktwerte_{year}.csv"
        if not path.exists():
            print(f"\n  {path.name}: not present, skipped")
            continue
        hdr_year, data = load_monthly(path)
        if hdr_year != year:
            problems.append(f"{path.name}: header says {hdr_year}, filed as {year}")
            print(f"\n  {path.name}: HEADER YEAR {hdr_year} != {year} -- MISMATCH")
            continue
        body, months = data["body"], data["months"]
        present = [f for f, _ in HOUR_FLAGS if f in body]
        print(f"\n  {path.name}  (header year {hdr_year})")
        print(f"    flag rows present: {[f.split('(')[1][:-1] for f in present]}"
              + ("  + 15MIN" if QH_FLAG in body else "  (no 15MIN row)"))
        header_line = (f"    {'month':<9}{'neg QH':>8}{'max run h':>11}  "
                       + "".join(f"{f.split('(')[1][:-1]:>7}" for f in present)
                       + f"{'15MIN':>8}")
        print(header_line)
        checked = 0
        for i, m in enumerate(months):
            if (year, m) not in recomputed:
                continue
            r = recomputed[(year, m)]
            checked += 1
            line = (f"    {year}-{m:02d}{r['n_neg_qh']:>8,}"
                    f"{r['max_hour_run']:>11}  ")
            for flag in present:
                cell = body[flag][i] if i < len(body[flag]) else ""
                n = dict(HOUR_FLAGS)[flag]
                if not cell:
                    line += f"{'-':>7}"
                    continue
                ours = "Ja" if r["max_hour_run"] >= n else "Nein"
                agree = cell == ours
                line += f"{(cell if agree else cell + '!' + ours):>7}"
                rows.append({"check": "monthly_flag", "year": year, "month": m,
                             "quantity": flag, "file_value": cell, "expected": ours,
                             "status": "OK" if agree else "MISMATCH"})
                if not agree:
                    problems.append(
                        f"{year}-{m:02d} {flag}: file says {cell}, trigger logic says "
                        f"{ours} (max negative-hour run {r['max_hour_run']} h)")
            if QH_FLAG in body:
                cell = body[QH_FLAG][i] if i < len(body[QH_FLAG]) else ""
                if cell:
                    ours = "Ja" if r["any_neg_qh"] else "Nein"
                    agree = cell == ours
                    line += f"{(cell if agree else cell + '!' + ours):>8}"
                    rows.append({"check": "monthly_flag", "year": year, "month": m,
                                 "quantity": QH_FLAG, "file_value": cell,
                                 "expected": ours,
                                 "status": "OK" if agree else "MISMATCH"})
                    if not agree:
                        problems.append(
                            f"{year}-{m:02d} {QH_FLAG}: file says {cell}, trigger "
                            f"logic says {ours} ({r['n_neg_qh']} negative QH)")
                else:
                    line += f"{'-':>8}"
            else:
                line += f"{'n/a':>8}"
            print(line)
        if checked == 0:
            print("    no month of this file is inside the panel -- NOT CHECKED")

    print(f"\n{'=' * 78}\nVERDICT\n{'=' * 78}")
    if problems:
        print(f"  {len(problems)} MISMATCH(ES):")
        for p in problems:
            print(f"    - {p}")
    else:
        print("  No mismatch on any month the panel covers.")
    uncovered = [f"{y}-{m:02d}" for y in (2024, 2025)
                 for m in range(1, 13) if (y, m) not in recomputed]
    if uncovered:
        print(f"\n  NOT YET CHECKABLE ({len(uncovered)} months, panel does not reach "
              f"them):\n    {uncovered[0]} .. {uncovered[-1]}")
        print("  These need the 2024-01 .. 2025-09 SMARD history and a panel rebuild.")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {OUT_CSV.relative_to(REPO_ROOT)}")
    if problems:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
