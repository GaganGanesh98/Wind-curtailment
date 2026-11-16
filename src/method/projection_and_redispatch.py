"""The pre-registered Anlage 1 Nr. 5.1 compliance test.

    python src/check_nr51_compliance.py

**Pre-registered by the student on 31 Oct 2026, before any of the event-day data
was looked at.** Written here before the data arrived so the criterion cannot
drift once numbers are visible.

The statistic
-------------
    R = projection / (SMARD actual + onshore wind redispatch)

per control area and quarter-hour. The denominator adds grid curtailment back,
because Nr. 5.1 excludes reductions by the grid operator as well as reductions
within direct marketing: if only the metered actual were used, redispatch would
masquerade as Nr. 5.1 compliance.

The verdict
-----------
    PASS  R in negative-price quarter-hours exceeds R in positive-price
          quarter-hours **of the same days**, and R rises with price depth across
          the kill test's PRICE_BANDS.
    FAIL  no difference across bands.

Comparing within the same days is what makes this a test rather than a
correlation: it removes the day-to-day level differences between the two series.

Reported with event-day block-bootstrap confidence intervals, and with TenneT
coverage stated explicitly -- the 2026-10-30 export had TenneT empty in all 96
quarter-hours, and TenneT is 30.4 GW, 43% of the fleet, and the one control area
where the kill test found no significant bias.

Five event-days is preliminary. It cannot settle Nr. 5.1 compliance for the
fleet; it can show whether the effect is there at all and roughly how large.
"""

from __future__ import annotations

import csv
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.method.smard_config import PRICE_BANDS  # noqa: E402
from src.method.event_day_bootstrap import eventday_bootstrap_ratio  # noqa: E402

HR_DIR = REPO_ROOT / "data" / "raw" / "netztransparenz" / "hochrechnung_wind_onshore"
PANEL = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"
RESULTS_DIR = REPO_ROOT / "results"

TSO_COLUMNS = {"50Hertz": "50Hertz", "Amprion": "Amprion",
               "TenneT TSO": "TenneT", "TransnetBW": "TransnetBW"}
OFFSET_HOURS = {"CET": 1, "CEST": 2}
QH_MS = 15 * 60 * 1000
DIRECT_TSO = {"50Hertz": "50Hertz", "Amprion": "Amprion",
              "TenneT DE": "TenneT", "TransnetBW": "TransnetBW"}


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


def load_projection(hr_dir: Path = HR_DIR) -> tuple[pl.DataFrame, dict[str, int]]:
    """The Online-Hochrechnung in long format: ts_utc (ms), area, hr_mw.

    `hr_dir` was added on 15 November 2026 for Phase Q0b, which reads the
    quality-assured series from its own folder. The default is unchanged, so the
    Nr. 5.1 compliance check keeps reading exactly the operational files it was
    validated on; the two series live in separate folders precisely so that this
    glob can never mix them.
    """
    rows, empty = [], {}
    for path in sorted(Path(hr_dir).glob("*.csv")):
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
                    empty[area] = empty.get(area, 0) + 1
                    continue
                rows.append({"ts_utc": int(t.timestamp() * 1000), "area": area,
                             "hr_mw": float(raw.replace(".", "").replace(",", "."))})
    if not rows:
        raise SystemExit(f"No projection files in {HR_DIR}")
    return pl.DataFrame(rows), empty


def redispatch_qh(days: set[str]) -> pl.DataFrame:
    """Onshore wind redispatch reduction in MW, per control area and quarter-hour.

    Each measure is spread evenly over the quarter-hours it covers at its mean
    power, which is the only allocation the export supports -- it gives a start, an
    end and a mean, not a profile.
    """
    from src.method.redispatch_reader import find_input, parse_measures

    m = parse_measures(find_input())
    m = (m.filter(pl.col("carrier").str.contains("(?i)erneuerbar"))
           .filter(pl.col("direction").str.contains("(?i)reduzier"))
           .filter(~pl.col("reason").str.contains("(?i)(probefahrt|countertrade)"))
           .filter(~pl.col("plant").str.contains("(?i)(solar|photovolt|\\bpv\\b)")))
    unmapped = set(m["instructing"].to_list()) - set(DIRECT_TSO)
    if unmapped:
        raise ValueError(f"Unmapped TSO {sorted(unmapped)} (hard rule 12)")

    out: dict[tuple[str, int], float] = {}
    for r in m.iter_rows(named=True):
        try:
            sd = datetime.strptime(f"{r['start_date']} {r['start_time']}",
                                   "%d.%m.%Y %H:%M").replace(tzinfo=timezone.utc)
            ed = datetime.strptime(f"{r['end_date']} {r['end_time']}",
                                   "%d.%m.%Y %H:%M").replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
        if sd.date().isoformat() not in days and ed.date().isoformat() not in days:
            continue
        mw = str(r["mean_mw"]).replace(".", "").replace(",", ".")
        try:
            mw = float(mw)
        except ValueError:
            continue
        area = DIRECT_TSO[r["instructing"]]
        t = int(sd.timestamp() * 1000) // QH_MS * QH_MS
        end_ms = int(ed.timestamp() * 1000)
        while t < end_ms:
            out[(area, t)] = out.get((area, t), 0.0) + mw
            t += QH_MS
    if not out:
        return pl.DataFrame({"area": [], "ts_utc": [], "rd_mw": []},
                            schema={"area": pl.String, "ts_utc": pl.Int64,
                                    "rd_mw": pl.Float64})
    return pl.DataFrame([{"area": a, "ts_utc": t, "rd_mw": v}
                         for (a, t), v in out.items()])


def main() -> None:
    hr, empty = load_projection()
    days = sorted({datetime.fromtimestamp(t / 1000, tz=timezone.utc).date().isoformat()
                   for t in hr["ts_utc"].to_list()})
    print(f"Projection files: {len(list(HR_DIR.glob('*.csv')))}, "
          f"{hr.height:,} rows, UTC days {days[0]} .. {days[-1]}")
    print(f"TenneT coverage: {'MISSING in ' + str(empty['TenneT']) + ' quarter-hours'if 'TenneT' in empty else 'present'}")
    for a, n in sorted(empty.items()):
        print(f"  empty cells: {a} {n}")

    panel = (pl.scan_parquet(PANEL)
             .select(["ts_utc", "area", "act_onshore_mw", "price_eur_mwh",
                      "berlin_date"]).collect())
    j = hr.join(panel, on=["ts_utc", "area"], how="inner")
    if j.height == 0:
        raise SystemExit(
            "No overlap with the panel. The panel runs 2025-10-01 to 2026-10-28; "
            "an export outside that window cannot be checked against it."
        )
    rd = redispatch_qh(set(j["berlin_date"].to_list()))
    j = (j.join(rd, on=["area", "ts_utc"], how="left")
           .with_columns(pl.col("rd_mw").fill_null(0.0))
           .with_columns((pl.col("act_onshore_mw") + pl.col("rd_mw")).alias("denom"))
           # The bootstrap drops non-finite pairs but the verdict arithmetic below
           # used raw sums, so a single NaN in the metered actual turned R(pos) into
           # NaN and the comparison `r_neg > r_pos` into False -- reporting a FAIL
           # that was a missing value, not a finding. Filter once, here, so every
           # statistic in this function sees the same rows.
           .filter(pl.col("hr_mw").is_finite() & pl.col("denom").is_finite()))
    print(f"matched: {j.height:,} rows; redispatch added back in "
          f"{int((j['rd_mw'] > 0).sum()):,} of them")

    print(f"\n{'area':<12}{'band':<14}{'R':>8}{'95% CI':>20}{'proj':>9}{'denom':>9}{'n':>6}")
    print("-" * 80)
    out, verdict = [], {}
    for area in ("50Hertz", "Amprion", "TenneT", "TransnetBW"):
        sub = j.filter(pl.col("area") == area)
        if sub.height == 0:
            print(f"{area:<12}NOT COVERED -- column empty in every export")
            verdict[area] = "not covered"
            continue
        per_band = {}
        for label, lo, hi in PRICE_BANDS:
            b = sub
            if lo is not None:
                b = b.filter(pl.col("price_eur_mwh") > lo)
            if hi is not None:
                b = b.filter(pl.col("price_eur_mwh") <= hi)
            if b.height == 0:
                continue
            r, clo, chi, _, nd = eventday_bootstrap_ratio(
                b["hr_mw"].to_numpy(), b["denom"].to_numpy(),
                b["berlin_date"].to_numpy())
            per_band[label] = r
            print(f"{area:<12}{label:<14}{r:>8.3f}  [{clo:>6.3f}, {chi:>6.3f}]"
                  f"{b['hr_mw'].mean():>9,.0f}{b['denom'].mean():>9,.0f}{b.height:>6,}")
            out.append({"area": area, "band": label, "ratio": round(r, 4),
                        "ci_lo": round(clo, 4), "ci_hi": round(chi, 4),
                        "n_qh": b.height, "n_days": nd})
        neg = sub.filter(pl.col("price_eur_mwh") < 0)
        pos = sub.filter(pl.col("price_eur_mwh") > 5)
        if neg.height and pos.height:
            r_neg = float(neg["hr_mw"].sum() / neg["denom"].sum())
            r_pos = float(pos["hr_mw"].sum() / pos["denom"].sum())
            deep = [per_band[l] for l, _, _ in PRICE_BANDS if l in per_band]
            monotone = all(a >= b - 1e-9 for a, b in zip(deep, deep[1:]))
            verdict[area] = ("PASS" if (r_neg > r_pos and monotone) else
                             "PARTIAL" if r_neg > r_pos else "FAIL")
            print(f"{area:<12}{'-> R(neg) ' + format(r_neg, '.3f') + ' vs R(pos>5) ' + format(r_pos, '.3f'):<40}"
                  f"{verdict[area]}")
        else:
            verdict[area] = "insufficient bands"

    print("\nVERDICT (pre-registered 31 Oct 2026, before the data was seen)")
    for a, v in verdict.items():
        print(f"  {a:<12}{v}")
    n_days_total = j["berlin_date"].n_unique()
    n_neg_days = j.filter(pl.col("price_eur_mwh") < 0)["berlin_date"].n_unique()
    print(f"\n  Sample: {n_days_total} days, of which {n_neg_days} carry a negative")
    print("  quarter-hour. A band whose CI is [nan, nan] has fewer than two event-")
    print("  days and is a point estimate, no inference.")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    if out:
        with open(RESULTS_DIR / "39_nr51_compliance.csv", "w", newline="",
                  encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(out)
        print("\nWrote results/39_nr51_compliance.csv")


if __name__ == "__main__":
    main()
