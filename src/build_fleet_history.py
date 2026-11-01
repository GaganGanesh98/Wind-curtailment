"""Installed onshore capacity per cohort per day, from 2024-01-01 (Stage 1.3 / block 7).

    python src/build_fleet_history.py

Why this cannot reuse `ingest_mastr.build()`
--------------------------------------------
That function filters to `EinheitBetriebsstatus == 35` (in operation), which is right
for a snapshot of today's fleet and **wrong for a history**: it drops every unit that
has since been decommissioned, so the fleet of January 2024 would be reconstructed
without the turbines that were running then and have since come down. The 2026-10-31
snapshot carries **2,599 units with `DatumEndgueltigeStilllegung`** (status code 38),
and those are exactly the ones a history needs.

So presence is decided by dates, not by status:

    present on day d  <=>  commissioned <= d  AND  (decommissioned is null OR
                                                    decommissioned > d)

A unit still in operation has no decommissioning date and is present from
commissioning onwards.

Cohort membership moves with the day
------------------------------------
`cohort_of` already takes `as_of`, and the only term that depends on it is the
out-of-support test — EEG support runs 20 years plus the commissioning year (section
25), so a unit leaves support on a fixed date and moves to `out_of_support` whatever
else is true of it. Every other branch (pre-2016, pilot, the size and vintage
thresholds) is a property of the unit alone.

That is used to vectorise: each unit gets one `base_cohort` and one `support_end`, and
on day d its cohort is `out_of_support` if `support_end < d` and `base_cohort`
otherwise. Asserted equal to `cohort_of` on a sample rather than assumed, because the
whole series depends on it.

This is also the E3 confound made visible: on 1 Jan 2026 the 2005 vintage leaves
support, moving that capacity's threshold from -MP to 0, on the same date as the
staircase steps 3 h -> 2 h.
"""

from __future__ import annotations

import csv
import sys
from datetime import date, timedelta
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.ingest_mastr import (  # noqa: E402
    BUNDESLAND_TO_TSO,
    cohort_of,
    load_eeg,
    load_units,
    support_ends,
)

SNAPSHOT = REPO_ROOT / "data" / "raw" / "mastr" / "2026-10-31"
OUT_CSV = REPO_ROOT / "results" / "23_fleet_history.csv"
OUT_DAILY = REPO_ROOT / "data" / "processed" / "fleet_capacity_daily.parquet"
START = date(2024, 1, 1)
END = date(2026, 10, 31)
AREAS = ("DE", "50Hertz", "Amprion", "TenneT", "TransnetBW")

# Published comparators for the 2024-01-01 sanity check (block 7). Both verified at
# source on 1 Nov 2026, both quoted verbatim, neither taken from memory.
PUBLISHED = (
    # Deutsche WindGuard, "Status des Windenergieausbaus an Land in Deutschland --
    # Jahr 2023", published 16 January 2024, commissioned by BWE and VDMA Power
    # Systems. Table on p. 3: "Kumuliert 31.12.2023 / Kumulierter Bestand
    # 61.010 MW / 28.677 WEA". Archived at
    # docs/literature/windguard_2024_status_windenergieausbau_land_jahr2023.pdf
    ("Deutsche WindGuard, 31.12.2023 kumulierter Bestand", 61_010.0),
    # Bundesnetzagentur, "Growth in renewable energy in 2023", issued 2024-01-05:
    # "Installed onshore wind capacity totalled 60.9 GW at the end of 2023."
    # Preliminary; the release states December was estimated.
    ("Bundesnetzagentur, end-2023 (preliminary)", 60_900.0),
)


def base_cohort(commissioned: date, net_kw: float, pilot: bool) -> str:
    """`cohort_of` with the out-of-support branch removed: the time-invariant part."""
    if commissioned < date(2016, 1, 1):
        return "pre2016_in_support_no_s51"
    if commissioned >= date(2025, 2, 25):
        return "post_feb2025_qh"
    if pilot:
        return "pilot_exempt"
    if commissioned <= date(2020, 12, 31):
        return "wind2016_2020_6h" if net_kw >= 3000.0 else "size_exempt"
    if commissioned <= date(2022, 12, 31):
        return "wind2021_2022_4h" if net_kw >= 500.0 else "size_exempt"
    return "wind2023_feb2025_staircase" if net_kw >= 400.0 else "size_exempt"


def check_decomposition(df: pl.DataFrame, n: int = 4000) -> None:
    """base_cohort + support_end must reproduce cohort_of exactly. Asserted, not assumed."""
    sample = df.head(n)
    for r in sample.iter_rows(named=True):
        for d in (date(2024, 1, 1), date(2025, 6, 30), date(2026, 10, 31)):
            want = cohort_of(r["commissioned"], r["net_kw"], bool(r["pilot"]), as_of=d)
            got = ("out_of_support" if r["support_end"] < d
                   else base_cohort(r["commissioned"], r["net_kw"], bool(r["pilot"])))
            if want != got:
                raise AssertionError(
                    f"decomposition disagrees with cohort_of for unit "
                    f"{r['EinheitMastrNummer']} on {d}: {got!r} vs {want!r}")
    print(f"  decomposition verified against cohort_of on {sample.height:,} units "
          f"x 3 dates")


def load_fleet() -> pl.DataFrame:
    units = load_units(SNAPSHOT)
    eeg = load_eeg(SNAPSHOT)

    lage = units["WindAnLandOderAufSee"].drop_nulls().value_counts(sort=True)
    onshore_code = lage.row(0)[0]
    print(f"  onshore code {onshore_code!r}")

    df = units.with_columns(
        pl.col("Nettonennleistung").cast(pl.Float64, strict=False).alias("net_kw"),
        pl.col("Inbetriebnahmedatum").str.strptime(pl.Date, "%Y-%m-%d", strict=False)
          .alias("commissioned"),
        pl.col("DatumEndgueltigeStilllegung")
          .str.strptime(pl.Date, "%Y-%m-%d", strict=False).alias("decommissioned"),
    )
    n0 = df.height
    df = df.filter(pl.col("WindAnLandOderAufSee") == onshore_code)
    print(f"  onshore only                 {n0:>9,} -> {df.height:>9,}")
    n0 = df.height
    df = df.filter(pl.col("commissioned").is_not_null()
                   & pl.col("net_kw").is_not_null())
    print(f"  has date and capacity        {n0:>9,} -> {df.height:>9,}")
    print("  NOTE: operating status is NOT filtered -- a history needs the units that "
          "have since been decommissioned.")
    n_decom = int(df["decommissioned"].is_not_null().sum())
    print(f"  units carrying a decommissioning date: {n_decom:,}")

    df = df.join(eeg, on="EegMaStRNummer", how="left")
    df = df.with_columns(
        pl.col("Bundesland").replace_strict(
            {k: v[1] for k, v in BUNDESLAND_TO_TSO.items()}, default=None
        ).alias("control_area"),
        (pl.col("PilotAnlage") == "1").alias("pilot"),
    )
    df = df.with_columns(
        pl.col("commissioned").map_elements(support_ends, return_dtype=pl.Date)
          .alias("support_end"),
        pl.struct(["commissioned", "net_kw", "pilot"]).map_elements(
            lambda r: base_cohort(r["commissioned"], r["net_kw"], bool(r["pilot"])),
            return_dtype=pl.String).alias("base_cohort"),
    )
    return df.select(["EinheitMastrNummer", "commissioned", "decommissioned",
                      "net_kw", "pilot", "control_area", "support_end",
                      "base_cohort"])


def daily_capacity(df: pl.DataFrame) -> pl.DataFrame:
    """Capacity in MW per (day, area, cohort). Vectorised over units per day."""
    com = df["commissioned"].to_numpy()
    dec = df["decommissioned"].to_numpy()
    sup = df["support_end"].to_numpy()
    kw = df["net_kw"].to_numpy()
    base = df["base_cohort"].to_numpy()
    area = df["control_area"].to_numpy()

    import numpy as np
    out = []
    day = START
    while day <= END:
        d64 = np.datetime64(day)
        present = (com <= d64) & (np.isnat(dec) | (dec > d64))
        if present.any():
            coh = np.where(sup[present] < d64, "out_of_support", base[present])
            mw = kw[present] / 1000.0
            ar = area[present]
            for a in AREAS:
                sel = slice(None) if a == "DE" else (ar == a)
                c, m = (coh, mw) if a == "DE" else (coh[sel], mw[sel])
                for name in np.unique(c):
                    out.append({"day": day.isoformat(), "area": a, "cohort": str(name),
                                "capacity_mw": round(float(m[c == name].sum()), 3)})
        day += timedelta(days=1)
    return pl.DataFrame(out)


def main() -> None:
    print("Fleet history from the 2026-10-31 MaStR snapshot")
    df = load_fleet()
    check_decomposition(df)

    daily = daily_capacity(df)
    OUT_DAILY.parent.mkdir(parents=True, exist_ok=True)
    daily.write_parquet(OUT_DAILY)
    print(f"\n  {daily.height:,} (day, area, cohort) rows -> "
          f"{OUT_DAILY.relative_to(REPO_ROOT)}")

    de = daily.filter(pl.col("area") == "DE")
    tot = (de.group_by("day").agg(pl.col("capacity_mw").sum().alias("mw"))
             .sort("day"))
    print(f"\nDE onshore installed capacity, total")
    for d in ("2024-01-01", "2024-12-31", "2025-12-31", "2026-10-31"):
        r = tot.filter(pl.col("day") == d)
        if r.height:
            print(f"  {d}   {r['mw'][0]:>10,.0f} MW")

    print(f"\nDE capacity by cohort (MW), showing how membership moves")
    piv = (de.filter(pl.col("day").is_in(["2024-01-01", "2025-01-01",
                                          "2026-01-01", "2026-10-31"]))
             .pivot(values="capacity_mw", index="cohort", on="day")
             .sort("cohort"))
    print(piv)

    rows = []
    for d in sorted(set(de["day"].to_list())):
        s = de.filter(pl.col("day") == d)
        rec = {"day": d, "total_mw": round(float(s["capacity_mw"].sum()), 1)}
        for c, m in zip(s["cohort"].to_list(), s["capacity_mw"].to_list()):
            rec[c] = round(float(m), 1)
        rows.append(rec)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted({k for r in rows for k in r})
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["day", "total_mw"]
                           + [k for k in keys if k not in ("day", "total_mw")],
                           restval=0.0, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {OUT_CSV.relative_to(REPO_ROOT)}")
    mine = float(tot.filter(pl.col("day") == "2024-01-01")["mw"][0])
    print(f"\nSANITY CHECK -- computed DE onshore capacity on 2024-01-01: "
          f"{mine:,.0f} MW")
    print(f"  {'published comparator':<46}{'MW':>10}{'difference':>13}{'rel':>9}")
    for name, val in PUBLISHED:
        print(f"  {name:<46}{val:>10,.0f}{mine - val:>+13,.0f}"
              f"{(mine - val) / val:>9.2%}")
    print("  Both comparators are MaStR-derived -- WindGuard's own factsheet notes")
    print("  that late MaStR registrations can shift its Gesamtbestand -- so this")
    print("  checks THIS PIPELINE'S processing of the register, not the register.")


if __name__ == "__main__":
    main()
