"""The Anlage 1 Nr. 5.1 check on the fleet-level Online-Hochrechnung Wind Onshore.

    python src/check_hochrechnung_onshore.py

Reads every CSV in `data/raw/netztransparenz/hochrechnung_wind_onshore/`, converts
the local CET/CEST stamps to UTC on the file's own `Zeitzone` column, and compares
the series with the SMARD metered onshore actual per control area.

What the check is
-----------------
Anlage 1 Nr. 5.1 requires the projection to ignore reductions by the grid operator
and reductions within direct marketing. So in negative-price quarter-hours the
metered actual should fall away while the projection stays up, and the ratio
projection/actual should rise above its positive-price baseline. The baseline
matters: the projection is not expected to equal the metered actual even with no
curtailment at all, so the test is the *change* in the ratio across price bands,
not its level.

Calibration already in hand: on 2026-10-30, a day with **no negative quarter-hours
at all** (DE-LU price 210.6 to 350.0 EUR/MWh), the ratio was 1.082 for 50Hertz,
1.028 for Amprion and 1.017 for TransnetBW, 1.035 over the three. That is the
curtailment-free baseline against which negative-price quarter-hours are read.

Caveats carried from the sample
-------------------------------
* TenneT was empty in the 2026-10-30 export, so the largest control area is
  missing from the calibration.
* Amprion is published rounded to whole MW, which adds a small, harmless
  quantisation error at these levels.
"""

from __future__ import annotations

import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

HR_DIR = REPO_ROOT / "data" / "raw" / "netztransparenz" / "hochrechnung_wind_onshore"
PANEL = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"
RESULTS_DIR = REPO_ROOT / "results"

TSO_COLUMNS = {"50Hertz": "50Hertz", "Amprion": "Amprion",
               "TenneT TSO": "TenneT", "TransnetBW": "TransnetBW"}
OFFSET_HOURS = {"CET": 1, "CEST": 2}

from src.method.smard_config import PRICE_BANDS  # noqa: E402


DST_HOUR = re.compile(r"(\d{4}-\d{2}-\d{2} )(\d{2})[AB](:\d{2})")


def parse_local_stamp(s: str) -> datetime:
    """Parse a Netztransparenz local timestamp, including the DST fall-back hour.

    On the October changeover the repeated hour is written `02A:00` and `02B:00`
    rather than twice as `02:00`. Stripping the letter is safe and loses nothing,
    because the row's own `Zeitzone` column carries the disambiguation: the A pass is
    CEST (UTC+2) and the B pass CET (UTC+1), so the offset applied by the caller maps
    them to 00:00 and 01:00 UTC respectively -- two distinct instants, in order.
    Verified on 2026-10-25, the only changeover in this sample (8 rows).
    """
    return datetime.strptime(DST_HOUR.sub(r"\1\2\3", s.strip()), "%Y-%m-%d %H:%M")


MISSING_TOKENS = {"", "N.A.", "NA", "N/A", "-"}


def is_missing(raw: str) -> bool:
    """Netztransparenz writes an absent value as `N.A.`, not as an empty cell.

    Worth a named helper because the obvious check fails twice over: grepping the
    file for "NA" finds nothing (the literal is "N.A."), and the German decimal
    cleanup `.replace(".", "")` silently turns "N.A." into "NA" before the float
    conversion, so the error message names a string that does not appear in the file.
    """
    return raw.strip().upper() in MISSING_TOKENS


def load() -> pl.DataFrame:
    """Every file in the directory, converted to UTC. Empty cells are dropped and counted."""
    rows, empty = [], []
    for path in sorted(HR_DIR.glob("*.csv")):
        for rec in csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines(),
                                  delimiter=";"):
            tz = (rec.get("Zeitzone") or "").strip()
            if tz not in OFFSET_HOURS:
                raise ValueError(f"Unmapped Zeitzone {tz!r} in {path.name}")
            t = (parse_local_stamp(rec["Zeit"])
                 - timedelta(hours=OFFSET_HOURS[tz])).replace(tzinfo=timezone.utc)
            for col, area in TSO_COLUMNS.items():
                raw = (rec.get(col) or "").strip()
                if is_missing(raw):
                    empty.append(area)
                    continue
                rows.append({"ts_utc": int(t.timestamp() * 1000), "area": area,
                             "hr_mw": float(raw.replace(".", "").replace(",", ".")),
                             "source_file": path.name})
    if empty:
        from collections import Counter
        print(f"  empty cells (column not exported): {dict(Counter(empty))}")
    if not rows:
        raise SystemExit(f"No data in {HR_DIR}")
    return pl.DataFrame(rows)


def fetch_smard_week(ts_ms: int, areas: list[str]) -> pl.DataFrame:
    """SMARD onshore actual, day-ahead forecast and price for the week holding ts_ms.

    The committed panel stops at 2026-10-28, so a sample day after that has nothing
    to join to. Rather than leave the check unrunnable, fetch that week from SMARD
    directly -- the same endpoint and the same MWh-per-quarter-hour convention
    build_panel.py uses, so the numbers are comparable with the panel's.
    """
    import requests

    from src.method.smard_config import FILTERS, MWH_PER_QH_TO_MW

    base = "https://www.smard.de/app/chart_data"
    sess = requests.Session()
    sess.headers["User-Agent"] = "msc-thesis-research/1.0"

    def week(filt: int, region: str) -> int:
        idx = sess.get(f"{base}/{filt}/{region}/index_quarterhour.json",
                       timeout=60).json()
        return max(t for t in idx["timestamps"] if t <= ts_ms)

    def series(filt: int, region: str, scale: float) -> dict[int, float]:
        w = week(filt, region)
        d = sess.get(f"{base}/{filt}/{region}/{filt}_{region}_quarterhour_{w}.json",
                     timeout=90).json()
        return {int(t): v * scale for t, v in d["series"] if v is not None}

    price = series(FILTERS["price"], "DE-LU", 1.0)
    rows = []
    for area in areas:
        act = series(FILTERS["act_onshore"], area, MWH_PER_QH_TO_MW)
        da = series(FILTERS["da_onshore"], area, MWH_PER_QH_TO_MW)
        for t, a in act.items():
            if t in da and t in price:
                rows.append({"ts_utc": t, "area": area, "act_onshore_mw": a,
                             "da_onshore_mw": da[t], "price_eur_mwh": price[t],
                             "berlin_date": datetime.fromtimestamp(
                                 t / 1000, tz=timezone.utc).strftime("%Y-%m-%d")})
    return pl.DataFrame(rows)


def main() -> None:
    hr = load()
    days = sorted({d[:10] for d in
                   hr.with_columns(pl.from_epoch("ts_utc", time_unit="ms")
                                     .dt.strftime("%Y-%m-%d").alias("d"))["d"]})
    print(f"Online-Hochrechnung Wind Onshore: {hr.height:,} rows, "
          f"{len(days)} day(s) {days[0]} .. {days[-1]}")

    panel = (pl.scan_parquet(PANEL)
             .select(["ts_utc", "area", "act_onshore_mw", "da_onshore_mw",
                      "price_eur_mwh", "berlin_date"])
             .collect())
    j = hr.join(panel, on=["ts_utc", "area"], how="inner").drop_nulls(
        ["hr_mw", "act_onshore_mw", "price_eur_mwh"])
    print(f"matched to the panel: {j.height:,} of {hr.height:,} rows")
    if j.height == 0:
        print("  no overlap with the committed panel (it ends 2026-10-28) -- "
              "fetching that week from SMARD instead")
        panel = fetch_smard_week(int(hr["ts_utc"].min()),
                                 sorted(set(hr["area"].to_list())))
        j = hr.join(panel, on=["ts_utc", "area"], how="inner").drop_nulls(
            ["hr_mw", "act_onshore_mw", "price_eur_mwh"])
        print(f"  matched after fetching: {j.height:,} of {hr.height:,} rows")
    if j.height == 0:
        raise SystemExit("Still no overlap -- check the time conversion.")

    print(f"\n{'area':<12}{'band':<14}{'HR mean':>10}{'SMARD':>10}{'ratio':>8}"
          f"{'corr':>7}{'n':>7}")
    print("-" * 68)
    out = []
    for area in ("50Hertz", "Amprion", "TenneT", "TransnetBW"):
        sub = j.filter(pl.col("area") == area)
        if sub.height == 0:
            continue
        for label, lo, hi in PRICE_BANDS:
            b = sub
            if lo is not None:
                b = b.filter(pl.col("price_eur_mwh") > lo)
            if hi is not None:
                b = b.filter(pl.col("price_eur_mwh") <= hi)
            if b.height == 0:
                continue
            h = b["hr_mw"].to_numpy()
            a = b["act_onshore_mw"].to_numpy()
            ratio = float(h.sum() / a.sum()) if a.sum() else float("nan")
            corr = float(np.corrcoef(h, a)[0, 1]) if h.std() > 0 and a.std() > 0 else float("nan")
            print(f"{area:<12}{label:<14}{h.mean():>10,.0f}{a.mean():>10,.0f}"
                  f"{ratio:>8.3f}{corr:>7.3f}{b.height:>7,}")
            out.append({"area": area, "price_band": label,
                        "hr_mean_mw": round(float(h.mean()), 1),
                        "smard_mean_mw": round(float(a.mean()), 1),
                        "ratio": round(ratio, 4), "corr": round(corr, 4),
                        "n_qh": b.height})

    neg = j.filter(pl.col("price_eur_mwh") < 0)
    print(f"\nnegative-price quarter-hours in the sample: {neg.height:,}")
    if neg.height == 0:
        print("  The Nr. 5.1 check needs negative-price quarter-hours and this")
        print("  sample has none, so it CANNOT be decided yet. What the sample does")
        print("  give is the curtailment-free baseline ratio, which is what the")
        print("  negative-price ratio has to be read against.")
    else:
        from src.method.event_day_bootstrap import eventday_bootstrap_ratio
        print(f"\n{'area':<12}{'ratio neg':>11}{'95% CI':>22}{'ratio pos':>11}"
              f"{'excess':>9}")
        for area in ("50Hertz", "Amprion", "TenneT", "TransnetBW"):
            s_neg = j.filter((pl.col("area") == area) & (pl.col("price_eur_mwh") < 0))
            s_pos = j.filter((pl.col("area") == area) & (pl.col("price_eur_mwh") > 5))
            if s_neg.height == 0 or s_pos.height == 0:
                continue
            r, lo_, hi_, _, _ = eventday_bootstrap_ratio(
                s_neg["hr_mw"].to_numpy(), s_neg["act_onshore_mw"].to_numpy(),
                s_neg["berlin_date"].to_numpy())
            r_pos = float(s_pos["hr_mw"].sum() / s_pos["act_onshore_mw"].sum())
            print(f"{area:<12}{r:>11.3f}  [{lo_:>7.3f}, {hi_:>7.3f}]"
                  f"{r_pos:>11.3f}{r - r_pos:>9.3f}")
        print("\n  A positive excess means the projection stays up while the metered")
        print("  actual falls -- Nr. 5.1 behaviour, and the gap is the curtailment.")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "36_hochrechnung_onshore_check.csv", "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print("\nWrote results/36_hochrechnung_onshore_check.csv")


if __name__ == "__main__":
    main()
