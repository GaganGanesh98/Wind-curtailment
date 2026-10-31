"""Is the Netztransparenz "Hochrechnung Windenergie" the Anlage 1 Nr. 5.1 projection?

    python src/check_hochrechnung.py

Why this runs before anything uses the series
---------------------------------------------
EEG Anlage 1 Nr. 5.1 requires the TSOs' online projection to ignore reductions by
the grid operator and reductions within direct marketing -- that is, to be a
curtailment-free potential. If the published series complies, it is an official
quarter-hourly estimate of uncurtailed wind power, which is close to A and would
be a major input to this thesis.

That is exactly why it is checked first. The test is a level comparison against
the SMARD metered actual, per control area:

  ratio ~ 1          the series covers the fleet; run the Nr. 5.1 compliance check
                     (does it fall with the curtailment in negative-price QHs?)
  ratio ~ 1-3%,      it is a small subset, not the fleet projection. Label it and
  region-dependent   do NOT use it for MV/JW or as a proxy for A; keep it only as a
                     candidate for sizing the feed-in-tariff cohort.

Timestamps are local CET/CEST, stated per row in a `Zeitzone` column, and are
converted to UTC on that column rather than by assuming an offset -- the sample
spans both, and a one-hour error would quietly destroy the correlation.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[1]
HR_DIR = REPO_ROOT / "data" / "raw" / "netztransparenz" / "hochrechnung_windenergie"
PANEL = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"
RESULTS_DIR = REPO_ROOT / "results"

# Column name in the file -> area label in the panel.
TSO_COLUMNS = {
    "50Hertz": "50Hertz",
    "Amprion": "Amprion",
    "TenneT TSO": "TenneT",
    "TransnetBW": "TransnetBW",
}
OFFSET_HOURS = {"CET": 1, "CEST": 2}


def load() -> pl.DataFrame:
    rows = []
    for path in sorted(HR_DIR.glob("*.csv")):
        text = path.read_text(encoding="utf-8-sig")
        reader = csv.DictReader(text.splitlines(), delimiter=";")
        for rec in reader:
            tz = (rec.get("Zeitzone") or "").strip()
            if tz not in OFFSET_HOURS:
                raise ValueError(f"Unmapped Zeitzone {tz!r} in {path.name}")
            for col, area in TSO_COLUMNS.items():
                raw = (rec.get(col) or "").strip()
                if not raw:
                    continue
                rows.append({
                    "local": rec["Zeit"].strip(),
                    "offset_h": OFFSET_HOURS[tz],
                    "area": area,
                    "hr_mw": float(raw),
                    "source_file": path.name,
                })
    df = pl.DataFrame(rows)
    return df.with_columns(
        (pl.col("local").str.strptime(pl.Datetime, "%Y-%m-%d %H:%M")
         - pl.duration(hours=pl.col("offset_h"))).alias("ts_utc_dt")
    )


def main() -> None:
    hr = load()
    days = sorted({s.split("_")[-1].replace(".csv", "") for s in
                   hr["source_file"].to_list()})
    print(f"Hochrechnung Windenergie: {hr.height:,} rows, {len(days)} days {days}")

    panel = (
        pl.scan_parquet(PANEL)
        .select(["ts_utc", "area", "act_onshore_mw", "da_onshore_mw",
                 "act_wind_mw", "price_eur_mwh"])
        .collect()
        .with_columns(
            pl.from_epoch(pl.col("ts_utc"), time_unit="ms").alias("ts_utc_dt")
        )
    )
    j = hr.join(panel, on=["ts_utc_dt", "area"], how="inner")
    print(f"matched to the panel: {j.height:,} of {hr.height:,} rows\n")
    if j.height == 0:
        raise SystemExit("No overlap with the panel -- check the time conversion.")

    print(f"{'area':<12}{'HR mean':>10}{'SMARD on.':>11}{'ratio':>9}"
          f"{'corr':>8}{'corr DA':>9}{'HR max':>9}{'n':>7}")
    print("-" * 75)
    out = []
    for area in ("50Hertz", "Amprion", "TenneT", "TransnetBW"):
        sub = j.filter(pl.col("area") == area).drop_nulls(["hr_mw", "act_onshore_mw"])
        if sub.height == 0:
            continue
        hr_v = sub["hr_mw"].to_numpy()
        ac = sub["act_onshore_mw"].to_numpy()
        da = sub["da_onshore_mw"].to_numpy()
        ratio = float(hr_v.sum() / ac.sum()) if ac.sum() else float("nan")
        corr = float(np.corrcoef(hr_v, ac)[0, 1]) if hr_v.std() > 0 else float("nan")
        corr_da = float(np.corrcoef(hr_v, da)[0, 1]) if hr_v.std() > 0 else float("nan")
        print(f"{area:<12}{hr_v.mean():>10,.1f}{ac.mean():>11,.0f}{ratio:>9.4%}"
              f"{corr:>8.3f}{corr_da:>9.3f}{hr_v.max():>9,.1f}{sub.height:>7,}")
        out.append({
            "area": area, "hr_mean_mw": round(float(hr_v.mean()), 3),
            "smard_onshore_mean_mw": round(float(ac.mean()), 1),
            "level_ratio": round(ratio, 6),
            "corr_with_smard_actual": round(corr, 4),
            "corr_with_da_forecast": round(corr_da, 4),
            "hr_max_mw": round(float(hr_v.max()), 3), "n_qh": sub.height,
        })

    tot = j.group_by("ts_utc_dt").agg(pl.col("hr_mw").sum().alias("hr"),
                                      pl.col("act_onshore_mw").sum().alias("ac"))
    de_ratio = float(tot["hr"].sum() / tot["ac"].sum())
    print(f"\nDE total level ratio: {de_ratio:.4%}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "34_hochrechnung_check.csv", "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(out)

    print("\nVerdict")
    if de_ratio > 0.8:
        print("  ratio ~ 1: this looks like the FLEET projection. Proceed to the")
        print("  Anlage 1 Nr. 5.1 compliance check.")
    else:
        print(f"  ratio {de_ratio:.2%}: this is NOT the fleet-level Anlage 1 Nr. 5.1")
        print("  projection. It is a small subset. Label it")
        print('  "EEG-vermarktete Windeinspeisung [VERIFY]"; do NOT use it for MV/JW')
        print("  or as a proxy for A; keep it only as a candidate for sizing the")
        print("  feed-in-tariff cohort.")
    print("\nWrote results/34_hochrechnung_check.csv")


if __name__ == "__main__":
    main()
