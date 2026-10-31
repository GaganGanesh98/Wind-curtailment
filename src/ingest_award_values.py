"""Award values AW_k per cohort, from the BNetzA onshore tender statistics.

    python src/ingest_award_values.py

Source
------
`data/raw/bnetza/Statistik_Onshore_2026-09-14.xlsx`, the Bundesnetzagentur's
round-by-round onshore tender statistics, 05/2017 - 08/2026. Sheet "Uebersicht",
one row per round:

    B  Gebotstermin                                    the round
    N  Zuschlagsmenge (kW)                             awarded volume
    S  Gebotswerte mit Zuschlag (ct/kWh), Min          low end of the bid range
    T  Gebotswerte mit Zuschlag (ct/kWh), Max          high end
    U  Zuschlagswert (ct/kWh), Gew. Mittel             the main value

Mapping units to rounds
-----------------------
MaStR's `Zuschlagsnummer` is `WIN<YY>-<N>/<serial>`: the Nth round of year 20YY.
The round order is read off the workbook's own round dates rather than assumed --
2019 had six rounds and 2020 seven, so a fixed four-per-year rule would be wrong.
`WIN21-3` resolves to 01.09.2021, which matches the worked example given.

Weighting (rule 19, and the student's instruction of 31 Oct 2026)
-----------------------------------------------------------------
Rounds are weighted by **built MaStR capacity**, not by awarded volume. The 2017
rounds in particular were awarded overwhelmingly to Buergerenergie projects whose
realisation rates were 0.7-32%, so awarded volume would give those cheap early
rounds a weight the built fleet never had.

The correction factor
---------------------
A tender bid is the anzulegender Wert at the 100% reference site; a plant's actual
AW is the bid times its site correction factor, which exceeds 1 at poorer sites.
Rule 19 fixes the main run at the mean factor **1.226**. That figure is still
**[VERIFY]** -- it is taken from Hirth (2026) Table A1, itself citing Fachagentur
Wind und Solar (2025), and neither has been checked at source. The sensitivity runs
use the awarded-bid range, because the correction-factor *distribution* is not in
this workbook and is **UNRESOLVED**; a range built from the bid spread alone
therefore understates the true uncertainty, and the results note must say so.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:          # so `python src/...` works like `-m`
    sys.path.insert(0, str(REPO_ROOT))
XLSX = REPO_ROOT / "data" / "raw" / "bnetza" / "Statistik_Onshore_2026-09-14.xlsx"
RESULTS_DIR = REPO_ROOT / "results"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

# Mean site-correction factor. [VERIFY] at Fachagentur Wind und Solar (2025) /
# EEG section 36h before this goes in the thesis; currently second-hand from
# Hirth (2026) Table A1.
CORRECTION_FACTOR_MAIN = 1.226

ZUSCHLAG_RE = re.compile(r"^(?P<scheme>[A-Za-z]{3})(?P<yy>\d{2})-(?P<n>\d+)")
CT_PER_KWH_TO_EUR_PER_MWH = 10.0


def read_rounds() -> pl.DataFrame:
    """One row per tender round, with the awarded-value statistics."""
    import openpyxl

    if not XLSX.exists():
        raise FileNotFoundError(f"{XLSX} not found")
    ws = openpyxl.load_workbook(XLSX, data_only=True)["Übersicht"]
    rows = []
    for r in ws.iter_rows(min_row=9, values_only=True):
        termin, volume, lo, hi, wmean = r[1], r[13], r[18], r[19], r[20]
        if termin is None or wmean is None:
            continue
        d = termin.date() if hasattr(termin, "date") else termin
        rows.append({
            "round_date": d,
            "awarded_kw": float(volume) if volume else None,
            "aw_min_eur_mwh": float(lo) * CT_PER_KWH_TO_EUR_PER_MWH if lo else None,
            "aw_max_eur_mwh": float(hi) * CT_PER_KWH_TO_EUR_PER_MWH if hi else None,
            "aw_wmean_eur_mwh": float(wmean) * CT_PER_KWH_TO_EUR_PER_MWH,
        })
    df = pl.DataFrame(rows).sort("round_date")
    print(f"  {df.height} rounds, {df['round_date'].min()} to {df['round_date'].max()}")
    return df


def round_code_map(rounds: pl.DataFrame) -> dict[str, date]:
    """`WIN<YY>-<N>` -> round date, from the workbook's own ordering.

    Derived, not assumed: the number of rounds per year varies (three in 2017, six
    in 2019, seven in 2020, three in 2021), so the Nth round of a year is the Nth
    date in that year and nothing simpler.
    """
    by_year: dict[int, list[date]] = defaultdict(list)
    for d in rounds["round_date"].to_list():
        by_year[d.year].append(d)
    out = {}
    for year, dates in by_year.items():
        for i, d in enumerate(sorted(dates), start=1):
            out[f"WIN{year % 100:02d}-{i}"] = d
    return out


def attach_awards(units: pl.DataFrame, rounds: pl.DataFrame) -> pl.DataFrame:
    code_to_date = round_code_map(rounds)
    units_total_kw = float(units["net_kw"].sum() or 1.0)

    def parse(z: str | None) -> str | None:
        if not z:
            return None
        m = ZUSCHLAG_RE.match(z)
        if not m:
            return None
        return f"{m.group('scheme').upper()}{m.group('yy')}-{int(m.group('n'))}"

    df = units.with_columns(
        pl.col("Zuschlagsnummer").map_elements(parse, return_dtype=pl.String)
          .alias("round_code")
    )
    have = df.filter(pl.col("round_code").is_not_null())
    codes = Counter(have["round_code"].to_list())
    unmapped = {c: n for c, n in codes.items() if c not in code_to_date}
    if unmapped:
        # Hard rule 12: report, never silently drop. Innovationsausschreibungen
        # (INN..) are a different auction with different values and are not in this
        # onshore workbook, so they are excluded on purpose and counted here.
        cap = float(
            have.filter(pl.col("round_code").is_in(list(unmapped)))["net_kw"].sum() or 0
        )
        print(f"  round codes not in the onshore workbook: {unmapped} "
              f"({cap / 1000:.0f} MW, {cap / float(units_total_kw):.2%} of the fleet)")
        print("    INN.. is an Innovationsausschreibung -- a different auction with "
              "different values, correctly absent from an onshore workbook.")
        print("    WLN.. is an unexplained second prefix alongside WIN for the same "
              "years. NOT assumed to be the same round: [VERIFY] what WLN denotes "
              "before mapping it (hard rule 9).")

    mapping = pl.DataFrame({
        "round_code": list(code_to_date),
        "round_date": list(code_to_date.values()),
    })
    return df.join(mapping, on="round_code", how="left").join(
        rounds.select(["round_date", "aw_min_eur_mwh", "aw_max_eur_mwh",
                       "aw_wmean_eur_mwh"]),
        on="round_date", how="left",
    )


def cohort_award_values(df: pl.DataFrame) -> pl.DataFrame:
    """AW_k per cohort, weighted by BUILT capacity, at three settings."""
    from src.ingest_mastr import cohort_of

    d = df.with_columns(
        pl.struct(["commissioned", "net_kw", "pilot"]).map_elements(
            lambda r: cohort_of(r["commissioned"], r["net_kw"], bool(r["pilot"])),
            return_dtype=pl.String,
        ).alias("cohort")
    )
    rows = []
    for cohort in sorted(set(d["cohort"].to_list())):
        sub = d.filter(pl.col("cohort") == cohort)
        tendered = sub.filter(pl.col("aw_wmean_eur_mwh").is_not_null())
        cap_total = float(sub["net_kw"].sum() or 0.0)
        cap_tendered = float(tendered["net_kw"].sum() or 0.0)
        if cap_tendered == 0:
            rows.append({
                "cohort": cohort, "capacity_mw": round(cap_total / 1000, 1),
                "tendered_capacity_mw": 0.0, "tendered_share": 0.0,
                "aw_main_eur_mwh": None, "aw_low_eur_mwh": None,
                "aw_high_eur_mwh": None,
                "note": "no tendered capacity -- AW is the statutory tariff, "
                        "UNRESOLVED (not in this workbook)",
            })
            continue
        w = tendered["net_kw"].to_numpy()
        wmean = float((tendered["aw_wmean_eur_mwh"].to_numpy() * w).sum() / w.sum())
        lo = float((tendered["aw_min_eur_mwh"].to_numpy() * w).sum() / w.sum())
        hi = float((tendered["aw_max_eur_mwh"].to_numpy() * w).sum() / w.sum())
        rows.append({
            "cohort": cohort,
            "capacity_mw": round(cap_total / 1000, 1),
            "tendered_capacity_mw": round(cap_tendered / 1000, 1),
            "tendered_share": round(cap_tendered / cap_total, 4) if cap_total else 0.0,
            "aw_main_eur_mwh": round(wmean * CORRECTION_FACTOR_MAIN, 2),
            "aw_low_eur_mwh": round(lo * CORRECTION_FACTOR_MAIN, 2),
            "aw_high_eur_mwh": round(hi * CORRECTION_FACTOR_MAIN, 2),
            "aw_uncorrected_wmean_eur_mwh": round(wmean, 2),
            "note": f"built-capacity weighted over {tendered.height} units; "
                    f"x{CORRECTION_FACTOR_MAIN} correction factor [VERIFY]",
        })
    return pl.DataFrame(rows)


def main() -> None:
    print("BNetzA onshore tender statistics")
    rounds = read_rounds()

    snaps = sorted(PROCESSED_DIR.glob("mastr_wind_*.parquet"))
    if not snaps:
        raise SystemExit("No MaStR snapshot. Run src/ingest_mastr.py first.")
    units = pl.read_parquet(snaps[-1])
    print(f"  MaStR snapshot {snaps[-1].name}: {units.height:,} units")

    df = attach_awards(units, rounds)
    matched = df.filter(pl.col("aw_wmean_eur_mwh").is_not_null())
    print(f"  units matched to a round: {matched.height:,} "
          f"({matched['net_kw'].sum() / 1e6:.2f} GW of "
          f"{units['net_kw'].sum() / 1e6:.2f} GW)")

    aw = cohort_award_values(df)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "31_award_values.csv", "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=aw.columns, lineterminator="\n")
        w.writeheader()
        w.writerows(aw.to_dicts())

    print("\nAW_k per cohort, EUR/MWh (main = built-capacity weighted x 1.226):")
    for r in aw.sort("capacity_mw", descending=True).iter_rows(named=True):
        if r["aw_main_eur_mwh"] is None:
            print(f"  {r['cohort']:<30}{r['capacity_mw']:>9,.0f} MW   "
                  f"no tendered capacity -- statutory tariff UNRESOLVED")
        else:
            print(f"  {r['cohort']:<30}{r['capacity_mw']:>9,.0f} MW   "
                  f"main {r['aw_main_eur_mwh']:>6.1f}   "
                  f"[{r['aw_low_eur_mwh']:>6.1f}, {r['aw_high_eur_mwh']:>6.1f}]   "
                  f"tendered {r['tendered_share']:.0%}")

    print("\nRound values by year (uncorrected gew. Mittel, EUR/MWh):")
    by_year = (rounds.with_columns(pl.col("round_date").dt.year().alias("y"))
                     .group_by("y").agg(pl.col("aw_wmean_eur_mwh").mean().alias("m"),
                                        pl.len().alias("n")).sort("y"))
    for y, m, n in by_year.iter_rows():
        print(f"  {y}  {m:6.1f}  ({n} rounds)")

    print("\nWrote results/31_award_values.csv")


if __name__ == "__main__":
    main()
