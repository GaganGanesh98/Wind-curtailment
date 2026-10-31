"""MaStR ingest: wind units, EEG data, and the cohort capacity shares w_k.

    python src/ingest_mastr.py --download        fetch a dated snapshot
    python src/ingest_mastr.py                   parse the latest snapshot

Source
------
Marktstammdatenregister bulk export, https://download.marktstammdatenregister.de.
Public, no login, licence dl-de/by-2-0. The full export is 67 GB uncompressed, so
only the four tables this project needs are fetched, by HTTP range request into the
zip's central directory: EinheitenWind, AnlagenEegWind, Katalogwerte,
Katalogkategorien -- 307 MB in total. The snapshot is written to
`data/raw/mastr/<YYYY-MM-DD>/` and is append-only (hard rule 1).

What it produces
----------------
`data/processed/mastr_wind_<date>.parquet` -- one row per onshore wind unit in
operation, with capacity, commissioning date, pilot flag, tender-award fields and a
control-area label -- and `results/30_mastr_cohort_shares.csv`, the capacity share
w_k of each rule-table cohort, per control area and for DE.

Two things the reader must know
-------------------------------
1. **The control area is a proxy.** MaStR records the federal state, not the TSO.
   The grid-connection point that would give the TSO directly lives in tables this
   ingest does not fetch. States are mapped to control areas on the conventional
   assignment, and three states are genuinely split between TSOs
   (see `BUNDESLAND_TO_TSO`), so those are assigned to their majority TSO and the
   error is recorded rather than hidden.
2. **Rule 19's STOP condition is evaluated here.** The cohort flag for an award
   value is the presence of a `Zuschlagsnummer`, and the fill rate is measured by
   *capacity* over the group that must carry one -- wind above 750 kW commissioned
   2019-2022 and at least 1 MW from 2023, excluding pilot plants -- never over all
   units, because older and smaller plants legitimately lack one.
"""

from __future__ import annotations

import argparse
import csv
import re
import shutil
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw" / "mastr"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
RESULTS_DIR = REPO_ROOT / "results"

WANTED_MEMBERS = (
    "EinheitenWind.xml", "AnlagenEegWind.xml",
    "Katalogwerte.xml", "Katalogkategorien.xml",
)

# Catalogue codes, read from Katalogwerte.xml in this snapshot (not guessed).
BETRIEBSSTATUS_IN_OPERATION = "35"      # "In Betrieb"
BETRIEBSSTATUS_LABEL = {
    "31": "In Planung", "35": "In Betrieb",
    "37": "Voruebergehend stillgelegt", "38": "Endgueltig stillgelegt",
}

# Federal state -> control area. A PROXY: MaStR gives the state, not the TSO.
# Brandenburg, Lower Saxony and Hesse are genuinely split between control areas;
# each is assigned to its majority TSO and the resulting error is reported.
BUNDESLAND_TO_TSO = {
    "1400": ("Brandenburg", "50Hertz"),
    "1401": ("Berlin", "50Hertz"),
    "1402": ("Baden-Wuerttemberg", "TransnetBW"),
    "1403": ("Bayern", "TenneT"),
    "1404": ("Bremen", "TenneT"),
    "1405": ("Hessen", "TenneT"),
    "1406": ("Hamburg", "50Hertz"),
    "1407": ("Mecklenburg-Vorpommern", "50Hertz"),
    "1408": ("Niedersachsen", "TenneT"),
    "1409": ("Nordrhein-Westfalen", "Amprion"),
    "1410": ("Rheinland-Pfalz", "Amprion"),
    "1411": ("Schleswig-Holstein", "TenneT"),
    "1412": ("Saarland", "Amprion"),
    "1413": ("Sachsen", "50Hertz"),
    "1414": ("Sachsen-Anhalt", "50Hertz"),
    "1415": ("Thueringen", "50Hertz"),
    "1416": ("Ausschliessliche Wirtschaftszone", "OFFSHORE_EEZ"),
}
# States genuinely split between control areas. **[VERIFY]** -- this list is a
# working assumption, not a sourced fact. The right fix is not a better guess but
# the grid-connection point: MaStR's Lokationen / Netzanschlusspunkte tables give
# the actual network operator, and this ingest does not fetch them. Until then the
# per-control-area split is approximate and the affected share is reported.
# Control-area codes as they appear in RegelzoneNetzanschlusspunkt, read from
# Katalogwerte.xml in this snapshot. This is the REAL control area of the grid
# connection point, so it supersedes the federal-state proxy wherever it is present.
REGELZONE_CODE = {
    "1000001": "50Hertz",
    "1000010": "Amprion",
    "1001564": "TenneT",
    "1001572": "TransnetBW",
}

SPLIT_STATES = {"1403", "1405", "1408", "1402"}  # Bayern, Hessen, Niedersachsen, BW

EINHEIT_FIELDS = (
    "EinheitMastrNummer", "EegMaStRNummer", "LokationMaStRNummer", "Inbetriebnahmedatum",
    "Nettonennleistung", "Bruttoleistung", "EinheitBetriebsstatus",
    "DatumEndgueltigeStilllegung", "Bundesland", "WindAnLandOderAufSee",
    "NameWindpark",
)
EEG_FIELDS = (
    "EegMaStRNummer", "Zuschlagsnummer", "AusschreibungZuschlag", "PilotAnlage",
    "InstallierteLeistung", "EegInbetriebnahmedatum", "AnlagenschluesselEeg",
)


# --------------------------------------------------------------------- download


def download_snapshot(snapshot: str) -> Path:
    """Fetch only the wind tables of the bulk export, by HTTP range request."""
    import unzip_http
    from open_mastr.xml_download.utils_download_bulk import gen_xml_download_url

    url = gen_xml_download_url(use_version="current")
    out = RAW_DIR / snapshot
    out.mkdir(parents=True, exist_ok=True)
    print(f"source: {url}")
    rz = unzip_http.RemoteZipFile(url)
    members = [f.filename for f in rz.infolist() if f.filename in WANTED_MEMBERS]
    missing = set(WANTED_MEMBERS) - set(members)
    if missing:
        raise RuntimeError(f"Expected members not in the export: {sorted(missing)}")
    for name in members:
        target = out / name
        with rz.open(name) as src, open(target, "wb") as dst:
            shutil.copyfileobj(src, dst)
        print(f"  {name:<26}{target.stat().st_size / 1e6:9.1f} MB")
    (out / "SOURCE.txt").write_text(
        f"url: {url}\ndownloaded: {snapshot}\n"
        f"licence: dl-de/by-2-0\nmembers: {', '.join(members)}\n", encoding="utf-8"
    )
    return out


# ------------------------------------------------------------------------ parse


def _iter_records(path: Path, record_tag: str, fields: tuple[str, ...]):
    """Stream records out of a UTF-16 MaStR table.

    The files are UTF-16 with one record per `<Tag>...</Tag>`; a regex pass over a
    decoded buffer is enough and avoids holding a 200 MB DOM. Chunked so that peak
    memory stays near the chunk size, with an overlap so no record is cut in half.
    """
    pattern = re.compile(rf"<{record_tag}>(.*?)</{record_tag}>", re.S)
    field_res = {f: re.compile(rf"<{f}>(.*?)</{f}>", re.S) for f in fields}
    buffer = ""
    with path.open("rb") as fh:
        while True:
            raw = fh.read(32 * 1024 * 1024)
            if not raw:
                break
            buffer += raw.decode("utf-16", "replace")
            last = 0
            for m in pattern.finditer(buffer):
                last = m.end()
                body = m.group(1)
                yield {
                    f: (mm.group(1) if (mm := rx.search(body)) else None)
                    for f, rx in field_res.items()
                }
            buffer = buffer[last:]


def load_units(snapshot_dir: Path) -> pl.DataFrame:
    rows = list(_iter_records(snapshot_dir / "EinheitenWind.xml", "EinheitWind",
                              EINHEIT_FIELDS))
    print(f"  EinheitenWind.xml      {len(rows):>9,} records")
    return pl.DataFrame(rows, schema={f: pl.String for f in EINHEIT_FIELDS})


def load_eeg(snapshot_dir: Path) -> pl.DataFrame:
    rows = list(_iter_records(snapshot_dir / "AnlagenEegWind.xml", "AnlageEegWind",
                              EEG_FIELDS))
    print(f"  AnlagenEegWind.xml     {len(rows):>9,} records")
    return pl.DataFrame(rows, schema={f: pl.String for f in EEG_FIELDS})


def build(snapshot_dir: Path) -> pl.DataFrame:
    """Join units to their EEG record and filter to onshore wind in operation.

    Every filter step prints rows in and rows out with the reason (hard rule 15):
    both Check 2 bugs in the kill test were invisible until those counts existed.
    """
    units = load_units(snapshot_dir)
    eeg = load_eeg(snapshot_dir)

    # Fail loudly on an unmapped categorical value (hard rule 12).
    lage = Counter(units["WindAnLandOderAufSee"].drop_nulls().to_list())
    print(f"  WindAnLandOderAufSee codes: {dict(lage)}")
    status = Counter(units["EinheitBetriebsstatus"].drop_nulls().to_list())
    unmapped = set(status) - set(BETRIEBSSTATUS_LABEL)
    if unmapped:
        raise ValueError(f"Unmapped EinheitBetriebsstatus code(s): {sorted(unmapped)}")

    onshore_code = min(lage, key=lambda c: -lage[c])  # the commonest is onshore
    print(f"  treating WindAnLandOderAufSee={onshore_code} as onshore "
          f"({lage[onshore_code]:,} of {sum(lage.values()):,} units)")

    df = units.with_columns(
        pl.col("Nettonennleistung").cast(pl.Float64, strict=False).alias("net_kw"),
        pl.col("Bruttoleistung").cast(pl.Float64, strict=False).alias("gross_kw"),
        pl.col("Inbetriebnahmedatum").str.strptime(pl.Date, "%Y-%m-%d", strict=False)
          .alias("commissioned"),
    )
    n0 = df.height
    df = df.filter(pl.col("WindAnLandOderAufSee") == onshore_code)
    print(f"  onshore only                {n0:>9,} -> {df.height:>9,}")
    n0 = df.height
    df = df.filter(pl.col("EinheitBetriebsstatus") == BETRIEBSSTATUS_IN_OPERATION)
    print(f"  in operation                {n0:>9,} -> {df.height:>9,}")
    n0 = df.height
    df = df.filter(pl.col("commissioned").is_not_null() & pl.col("net_kw").is_not_null())
    print(f"  has date and capacity       {n0:>9,} -> {df.height:>9,}")

    df = df.join(eeg, on="EegMaStRNummer", how="left")
    matched = df.filter(pl.col("Zuschlagsnummer").is_not_null()
                        | pl.col("AusschreibungZuschlag").is_not_null()).height
    print(f"  joined to AnlagenEegWind    {df.height:>9,} rows, "
          f"{matched:>9,} with any EEG award field")

    unknown_states = set(df["Bundesland"].drop_nulls().to_list()) - set(BUNDESLAND_TO_TSO)
    if unknown_states:
        raise ValueError(f"Unmapped Bundesland code(s): {sorted(unknown_states)}")

    return df.with_columns(
        pl.col("Bundesland").replace_strict(
            {k: v[1] for k, v in BUNDESLAND_TO_TSO.items()}, default=None
        ).alias("control_area"),
        pl.col("Bundesland").replace_strict(
            {k: v[0] for k, v in BUNDESLAND_TO_TSO.items()}, default=None
        ).alias("state"),
        pl.col("Bundesland").is_in(list(SPLIT_STATES)).alias("state_split_between_tsos"),
        (pl.col("PilotAnlage") == "1").alias("pilot"),
        pl.col("Zuschlagsnummer").is_not_null().alias("has_zuschlagsnummer"),
        (pl.col("AusschreibungZuschlag") == "1").alias("tender_awarded"),
    )


# ------------------------------------------- real control area, not the proxy


def fetch_regelzonen(lokation_ids: set[str], snapshot: str) -> dict[str, str]:
    """Map each wind unit's Lokation to its control area, from the register itself.

    `Netzanschlusspunkte` records `RegelzoneNetzanschlusspunkt` -- the control area
    of the grid connection point. That is the real answer, so the federal-state
    proxy in `BUNDESLAND_TO_TSO` is only a fallback for units this does not cover.

    The table is 8.75 GB uncompressed across 61 members and the machine has under
    10 GB free, so nothing is written to disk: each member is streamed, filtered to
    the Lokationen we actually care about, and discarded. Peak memory is one
    member's text.
    """
    import unzip_http
    from open_mastr.xml_download.utils_download_bulk import gen_xml_download_url

    url = gen_xml_download_url(use_version="current")
    rz = unzip_http.RemoteZipFile(url)
    members = sorted(f.filename for f in rz.infolist()
                     if f.filename.startswith("Netzanschlusspunkte_"))
    rec = re.compile(r"<Netzanschlusspunkt>(.*?)</Netzanschlusspunkt>", re.S)
    lok = re.compile(r"<LokationMaStRNummer>(.*?)</LokationMaStRNummer>")
    rz_re = re.compile(r"<RegelzoneNetzanschlusspunkt>(.*?)</RegelzoneNetzanschlusspunkt>")

    out: dict[str, str] = {}
    for i, member in enumerate(members, 1):
        buf = ""
        with rz.open(member) as fh:
            while True:
                chunk = fh.read(16 * 1024 * 1024)
                if not chunk:
                    break
                buf += chunk.decode("utf-16", "replace")
                last = 0
                for m in rec.finditer(buf):
                    last = m.end()
                    body = m.group(1)
                    lm = lok.search(body)
                    if lm and lm.group(1) in lokation_ids:
                        zm = rz_re.search(body)
                        if zm:
                            out[lm.group(1)] = zm.group(1)
                buf = buf[last:]
        if i % 10 == 0 or i == len(members):
            print(f"    {i:>3}/{len(members)} members, {len(out):,} of "
                  f"{len(lokation_ids):,} Lokationen matched", flush=True)
    return out


# ----------------------------------------------------------- rule 19 fill rate


def zuschlagsnummer_fill_rate(df: pl.DataFrame) -> dict:
    """Rule 19's STOP test, measured the way rule 19 specifies.

    The denominator is the capacity of the group that must carry a tender award
    number: wind above 750 kW commissioned 2019-2022 (the EEG 2017 tender exemption
    threshold) and at least 1 MW from 2023 (EEG 2023), excluding pilot plants. A
    fill rate over all units means nothing, because older and smaller plants are
    legitimately outside the tender regime.
    """
    must = df.filter(
        (~pl.col("pilot"))
        & (
            ((pl.col("commissioned") >= date(2019, 1, 1))
             & (pl.col("commissioned") <= date(2022, 12, 31))
             & (pl.col("net_kw") > 750.0))
            | ((pl.col("commissioned") >= date(2023, 1, 1)) & (pl.col("net_kw") >= 1000.0))
        )
    )
    total_kw = float(must["net_kw"].sum() or 0.0)
    filled_kw = float(must.filter(pl.col("has_zuschlagsnummer"))["net_kw"].sum() or 0.0)
    awarded_kw = float(must.filter(pl.col("tender_awarded"))["net_kw"].sum() or 0.0)
    return {
        "group_units": must.height,
        "group_capacity_mw": total_kw / 1000.0,
        "zuschlagsnummer_capacity_mw": filled_kw / 1000.0,
        "zuschlagsnummer_fill_by_capacity": filled_kw / total_kw if total_kw else float("nan"),
        "ausschreibung_zuschlag_capacity_mw": awarded_kw / 1000.0,
        "ausschreibung_zuschlag_fill_by_capacity": awarded_kw / total_kw if total_kw else float("nan"),
        "fill_over_all_units_do_not_use": (
            float(df.filter(pl.col("has_zuschlagsnummer"))["net_kw"].sum() or 0.0)
            / float(df["net_kw"].sum() or 1.0)
        ),
    }


# ------------------------------------------------------------- cohort shares


# EEG section 25: the support claim runs for 20 years PLUS the commissioning year.
# A plant commissioned in 2005 is therefore supported to the end of 2025. Support
# status and section 51 applicability are two different things and must not be
# conflated: a plant commissioned in 2010 is outside section 51 (R01) but still in
# support, so its threshold is minus the market premium, not zero.
SUPPORT_YEARS = 20


def support_ends(commissioned: date) -> date:
    return date(commissioned.year + SUPPORT_YEARS, 12, 31)


def cohort_of(commissioned: date, net_kw: float, pilot: bool,
              as_of: date = date(2026, 10, 31)) -> str:
    """Map a unit to a rule-table cohort. Boundaries come from the rule table.

    `data/reference/eeg_negative_price_rules.csv` is the source of every boundary
    here; nothing is invented. Pilot wind is exempt in every version before
    25 Feb 2025 and in none after, so a pilot plant commissioned later is NOT exempt.

    Out of support is checked FIRST and for every vintage, because it overrides
    everything: with no premium left to lose the plant simply stops below zero
    (theta = 0). The first version of this function labelled every pre-2016 plant
    "out of support", which put 50.2% of German onshore capacity in the wrong
    cohort -- plants from 2006-2015 are outside section 51 but still earning a
    premium, and their threshold is minus that premium.
    """
    if support_ends(commissioned) < as_of:
        return "out_of_support"
    if commissioned < date(2016, 1, 1):
        return "pre2016_in_support_no_s51"       # R01: section 51 never applies
    if commissioned >= date(2025, 2, 25):
        return "post_feb2025_qh"                 # R09/R10/R11 by size, below
    if pilot:
        return "pilot_exempt"                    # R12
    if commissioned <= date(2020, 12, 31):
        return "wind2016_2020_6h" if net_kw >= 3000.0 else "size_exempt"   # R02
    if commissioned <= date(2022, 12, 31):
        return "wind2021_2022_4h" if net_kw >= 500.0 else "size_exempt"    # R04
    return "wind2023_feb2025_staircase" if net_kw >= 400.0 else "size_exempt"  # R05-R08


def cohort_shares(df: pl.DataFrame) -> pl.DataFrame:
    rows = []
    with_cohort = df.with_columns(
        pl.struct(["commissioned", "net_kw", "pilot"]).map_elements(
            lambda r: cohort_of(r["commissioned"], r["net_kw"], bool(r["pilot"])),
            return_dtype=pl.String,
        ).alias("cohort")
    )
    for area in ["DE", "50Hertz", "Amprion", "TenneT", "TransnetBW"]:
        sub = with_cohort if area == "DE" else with_cohort.filter(
            pl.col("control_area") == area
        )
        total = float(sub["net_kw"].sum() or 0.0)
        for cohort, cap in (
            sub.group_by("cohort").agg(pl.col("net_kw").sum().alias("kw"))
            .sort("cohort").iter_rows()
        ):
            rows.append({
                "area": area, "cohort": cohort,
                "capacity_mw": round(cap / 1000.0, 1),
                "capacity_share": round(cap / total, 6) if total else float("nan"),
                "units": int(sub.filter(pl.col("cohort") == cohort).height),
            })
    return pl.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--regelzone", action="store_true",
                    help="stream Netzanschlusspunkte for the REAL control area")
    ap.add_argument("--snapshot", default=None)
    args = ap.parse_args()

    snapshot = args.snapshot or date.today().isoformat()
    if args.download:
        download_snapshot(snapshot)

    snapshot_dir = RAW_DIR / snapshot
    if not snapshot_dir.exists():
        available = sorted(p.name for p in RAW_DIR.glob("*")) if RAW_DIR.exists() else []
        raise SystemExit(f"No snapshot at {snapshot_dir}. Available: {available}. "
                         "Run with --download.")

    print(f"MaStR snapshot {snapshot}")
    df = build(snapshot_dir)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = PROCESSED_DIR / f"mastr_wind_{snapshot}.parquet"
    df.write_parquet(out)
    print(f"\nwrote {out}  ({df.height:,} onshore units in operation, "
          f"{df['net_kw'].sum() / 1e6:.1f} GW)")

    print("\nControl area (PROXY from Bundesland):")
    for area, cap, n in (
        df.group_by("control_area")
          .agg(pl.col("net_kw").sum().alias("kw"), pl.len().alias("n"))
          .sort("kw", descending=True).iter_rows()
    ):
        print(f"  {str(area):<14}{cap / 1e6:7.2f} GW  {n:>7,} units")
    split_cap = float(df.filter(pl.col("state_split_between_tsos"))["net_kw"].sum() or 0)
    print(f"  of which in states genuinely split between TSOs: "
          f"{split_cap / 1e6:.2f} GW "
          f"({split_cap / float(df['net_kw'].sum()) * 100:.1f}% -- assigned to the "
          f"majority TSO, so the per-area split is approximate)")

    if args.regelzone:
        print("\nResolving the real control area from Netzanschlusspunkte "
              "(streamed, nothing written to disk)...")
        ids = set(df["LokationMaStRNummer"].drop_nulls().to_list())
        mapping = fetch_regelzonen(ids, snapshot)
        codes = Counter(mapping.values())
        print(f"  Regelzone codes found: {dict(codes)}")
        rz_df = pl.DataFrame(
            {"LokationMaStRNummer": list(mapping), "regelzone_code": list(mapping.values())}
        )
        df = df.join(rz_df, on="LokationMaStRNummer", how="left")
        unmapped = set(codes) - set(REGELZONE_CODE)
        if unmapped:
            raise ValueError(f"Unmapped Regelzone code(s): {sorted(unmapped)}")
        df = df.with_columns(
            pl.col("regelzone_code").replace_strict(REGELZONE_CODE, default=None)
              .alias("regelzone"),
        ).with_columns(
            # The register's own answer where it exists, the state proxy otherwise.
            pl.coalesce(["regelzone", "control_area"]).alias("control_area_final"),
            pl.col("regelzone").is_null().alias("control_area_is_proxy"),
        )
        cov = float(df.filter(pl.col("regelzone").is_not_null())["net_kw"].sum() or 0)
        total = float(df["net_kw"].sum())
        print(f"  covered: {cov / 1e6:.2f} GW of {total / 1e6:.2f} GW "
              f"({cov / total:.1%} by capacity)")
        wrong = float(df.filter(pl.col("regelzone").is_not_null()
                                & (pl.col("regelzone") != pl.col("control_area")))
                        ["net_kw"].sum() or 0)
        print(f"  the federal-state PROXY was wrong for {wrong / 1e6:.2f} GW "
              f"({wrong / cov:.1%} of the covered capacity). The 31.7% figure "
              f"reported earlier was capacity EXPOSED to the proxy in split states, "
              f"not capacity the proxy got wrong.")
        # Cohort shares and everything downstream now key on the real control area.
        df = df.drop("control_area").rename({"control_area_final": "control_area"})
        df.write_parquet(out)
        print(f"  rewrote {out} with regelzone_code")

    fr = zuschlagsnummer_fill_rate(df)
    print("\nRule 19 -- Zuschlagsnummer fill rate")
    print(f"  group that must carry one: {fr['group_units']:,} units, "
          f"{fr['group_capacity_mw'] / 1000:.2f} GW")
    print(f"  with a Zuschlagsnummer:    {fr['zuschlagsnummer_capacity_mw'] / 1000:.2f} GW"
          f"  = {fr['zuschlagsnummer_fill_by_capacity']:.1%} by capacity")
    print(f"  with AusschreibungZuschlag:{fr['ausschreibung_zuschlag_capacity_mw'] / 1000:.2f} GW"
          f"  = {fr['ausschreibung_zuschlag_fill_by_capacity']:.1%} by capacity")
    print(f"  (fill over ALL units, which rule 19 says not to use: "
          f"{fr['fill_over_all_units_do_not_use']:.1%})")

    shares = cohort_shares(df)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "30_mastr_cohort_shares.csv", "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=shares.columns, lineterminator="\n")
        w.writeheader()
        w.writerows(shares.to_dicts())
    with open(RESULTS_DIR / "30_mastr_zuschlagsnummer_fill.csv", "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fr), lineterminator="\n")
        w.writeheader()
        w.writerow(fr)

    print("\nCohort capacity shares, DE:")
    for r in shares.filter(pl.col("area") == "DE").sort("capacity_share",
                                                        descending=True).iter_rows(named=True):
        print(f"  {r['cohort']:<30}{r['capacity_mw']:>9,.0f} MW  "
              f"{r['capacity_share']:>7.1%}  {r['units']:>7,} units")

    print("\nWrote results/30_mastr_cohort_shares.csv and "
          "results/30_mastr_zuschlagsnummer_fill.csv")

    if fr["zuschlagsnummer_fill_by_capacity"] < 0.50:
        print("\n" + "=" * 72)
        print("STOP (hard rule 19). The Zuschlagsnummer join is treated as broken:")
        print(f"  {fr['zuschlagsnummer_fill_by_capacity']:.1%} of the capacity that "
              "must carry an award number actually has one.")
        print("  Award values AW_k cannot be taken from MaStR, and rule 19 forbids")
        print("  substituting the commissioning year. Cohort SHARES above are")
        print("  unaffected -- they key on commissioning date and size, not on the")
        print("  award. Decide how to source AW_k before theta is built.")
        print("=" * 72)
        sys.exit(2)


if __name__ == "__main__":
    main()
