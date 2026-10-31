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

# EEG 2023 section 36h(1), read from docs/legal/s36h_EEG2023.pdf on 31 Oct 2026.
# Quality factor (Guetefaktor, site yield over reference yield, %) -> correction
# factor. Linear interpolation between neighbouring values; above 150% the factor
# is 0.79; below 60% it is 1.42, and below 50% it is 1.55 but only for plants in
# the southern region. The factor EXCEEDS 1 at poorer sites, which is why using 1
# understates AW.
S36H_CORRECTION = {
    50: 1.55, 60: 1.42, 70: 1.29, 80: 1.16, 90: 1.07, 100: 1.00,
    110: 0.94, 120: 0.89, 130: 0.85, 140: 0.81, 150: 0.79,
}
# The three settings rule 19 asks for. The main factor 1.226 implies a mean site
# quality of about 75% on this table, which is plausible for the German fleet.
CORRECTION_SETTINGS = {
    "main": CORRECTION_FACTOR_MAIN,   # Hirth (2026) Table A1, from Fachagentur 2025
    "good_site_90pct": S36H_CORRECTION[90],    # 1.07
    "poor_site_60pct": S36H_CORRECTION[60],    # 1.42
}


def s36h_correction(quality_factor_pct: float, southern_region: bool = False) -> float:
    """Correction factor for a quality factor, by section 36h(1) with interpolation."""
    xs = sorted(S36H_CORRECTION)
    if quality_factor_pct >= xs[-1]:
        return S36H_CORRECTION[xs[-1]]
    floor = 50 if southern_region else 60
    if quality_factor_pct <= floor:
        return S36H_CORRECTION[floor]
    import bisect

    i = bisect.bisect_left(xs, quality_factor_pct)
    lo, hi = xs[i - 1], xs[i]
    w = (quality_factor_pct - lo) / (hi - lo)
    return S36H_CORRECTION[lo] + w * (S36H_CORRECTION[hi] - S36H_CORRECTION[lo])


# EEG 2023 Anlage 1 Nr. 2, read from docs/legal/anlage1_EEG2023.pdf on 31 Oct 2026:
# "For electricity from installations that were commissioned before January 1,
# 2023, OR for which the award was granted before January 1, 2023, the market
# premium is calculated based on the ... monthly market value. For electricity
# from other installations ... the annual market value."
#
# So the reference period is per unit, and either condition is enough to keep a
# unit on the monthly value. Hirth (2026, Table A1) lists the post-2023 onshore
# cohorts as monthly; the statute governs, and the discrepancy is noted in the spec.
ANLAGE1_CUTOFF = date(2023, 1, 1)


# The one round the [VERIFY] is about: the bid date was 01.12.2022, but if the
# award counts as granted when the result is announced, it may fall in 2023.
DEC_2022_ROUND_CODE = "WIN22-4"


def reference_period(commissioned: date, round_code: str | None,
                     award_date: date | None,
                     dec_2022_counts_as_2023: bool = False) -> str:
    """"monthly" or "annual" per Anlage 1 Nr. 2.

    Either condition is enough to keep a unit on the monthly value: commissioned
    before 1 Jan 2023, OR awarded before 1 Jan 2023.

    `dec_2022_counts_as_2023` is the open [VERIFY] and moves **only the December
    2022 round**, not every 2022 award -- the February, May and September 2022
    rounds were unambiguously granted in 2022.
    """
    if commissioned < ANLAGE1_CUTOFF:
        return "monthly"
    if award_date is not None:
        if dec_2022_counts_as_2023 and round_code == DEC_2022_ROUND_CODE:
            return "annual"
        if award_date < ANLAGE1_CUTOFF:
            return "monthly"
    return "annual"

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

    # --- Anlage 1 Nr. 2: monthly MW or annual JW, per unit ---
    rows = []
    for dec_as_2023 in (False, True):
        lab = df.with_columns(
            pl.struct(["commissioned", "round_code", "round_date"]).map_elements(
                lambda r: reference_period(r["commissioned"], r["round_code"],
                                           r["round_date"], dec_as_2023),
                return_dtype=pl.String,
            ).alias("ref_period")
        )
        for period, cap, n in (
            lab.group_by("ref_period")
               .agg(pl.col("net_kw").sum().alias("kw"), pl.len().alias("n"))
               .sort("kw", descending=True).iter_rows()
        ):
            rows.append({"dec_2022_counts_as_2023": dec_as_2023,
                         "reference_period": period,
                         "capacity_mw": round(cap / 1000, 1), "units": n})
        if not dec_as_2023:
            lab.select(["EinheitMastrNummer", "commissioned", "net_kw",
                        "round_code", "round_date", "ref_period"]).write_parquet(
                PROCESSED_DIR / "mastr_reference_period.parquet")

    with open(RESULTS_DIR / "33_reference_period.csv", "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    print("\nAnlage 1 Nr. 2 -- monthly MW vs annual JW, per unit:")
    for r in rows:
        tag = "Dec-2022 round = 2023" if r["dec_2022_counts_as_2023"] else "as written"
        print(f"  [{tag:<22}] {r['reference_period']:<8}"
              f"{r['capacity_mw']:>9,.0f} MW  {r['units']:>7,} units")
    monthly_a = next(r["capacity_mw"] for r in rows
                     if not r["dec_2022_counts_as_2023"] and r["reference_period"] == "monthly")
    monthly_b = next(r["capacity_mw"] for r in rows
                     if r["dec_2022_counts_as_2023"] and r["reference_period"] == "monthly")
    print(f"  the open [VERIFY] moves {abs(monthly_a - monthly_b):,.0f} MW "
          f"between the two reference periods")

    print("\nCorrection-factor settings (EEG s.36h(1), docs/legal/s36h_EEG2023.pdf):")
    for k, v in CORRECTION_SETTINGS.items():
        print(f"  {k:<18}{v:.3f}")
    print(f"  the main 1.226 implies a mean quality factor of about 75% on the "
          f"s.36h table (75% -> {s36h_correction(75):.4f})")

    print("\nWrote results/31_award_values.csv, results/33_reference_period.csv")


if __name__ == "__main__":
    main()
