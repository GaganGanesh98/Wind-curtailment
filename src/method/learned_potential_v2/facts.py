"""Experiment 4b inputs that the pre-registration fixes, and the Phase 0 facts it quotes.

    python -m src.method.learned_potential_v2.facts     # writes artifacts/exp4b_hybrid_potential/phase0_facts.csv

Three things live here because both the pre-registration and the build use them:

- `measures()`: every renewable reduction in the three areas, classified by the plant-name
  rule (solar, offshore, or the onshore-wind proxy) and by the unit check.
- `units()`: every onshore wind unit in the raw MaStR XML, including units decommissioned in
  the period, with its control area.
- `facts()`: the counts docs/24 quotes. They are inputs and counts, not results: no model is
  fitted and nothing is scored.
"""

from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from functools import lru_cache

import polars as pl

from src.method.learned_potential_v2 import config as cfg

FACTS = cfg.ART / "phase0_facts.csv"
HOUR_MS = 3_600_000
QH_MS = 900_000

SOLAR_RE = r"(?i)(solar|photovolt|\bpv\b)"
OFFSHORE_RE = r"(OWP|ffshore)"


def _num(s) -> float:
    """Netztransparenz numbers, as redispatch_checks._num reads them."""
    return float(str(s).replace(".", "").replace(",", "."))


# ------------------------------------------------------------------ redispatch
@lru_cache(maxsize=1)
def measures() -> pl.DataFrame:
    """Renewable reductions instructed by the three TSOs, one row per measure.

    Columns: area, start_ms, end_ms (UTC), kind ("solar", "offshore" or "onshore wind proxy"),
    unit_fail (mean MW × duration and MWh more than the tolerance apart). The export has no
    technology field, so anything not named solar, PV or offshore counts as onshore wind.
    """
    from src.method.projection_and_redispatch import DIRECT_TSO
    from src.method.redispatch_reader import find_input, parse_measures
    m = (parse_measures(find_input())
         .filter(pl.col("carrier").str.contains("(?i)erneuerbar"))
         .filter(pl.col("direction").str.contains("(?i)reduzier"))
         .filter(~pl.col("reason").str.contains("(?i)(probefahrt|countertrade)")))
    rows = []
    for r in m.iter_rows(named=True):
        area = DIRECT_TSO.get(r["instructing"])
        if area not in cfg.AREAS:
            continue
        sd = datetime.strptime(f"{r['start_date']} {r['start_time']}", "%d.%m.%Y %H:%M")
        ed = datetime.strptime(f"{r['end_date']} {r['end_time']}", "%d.%m.%Y %H:%M")
        hours = (ed - sd).total_seconds() / 3600.0
        mwh = _num(r["energy_mwh"])
        rows.append({"area": area,
                     "start_ms": int(sd.replace(tzinfo=timezone.utc).timestamp() * 1000),
                     "end_ms": int(ed.replace(tzinfo=timezone.utc).timestamp() * 1000),
                     "plant": r["plant"] or "",
                     "unit_fail": abs(_num(r["mean_mw"]) * hours - mwh)
                     > cfg.REDISPATCH_TOLERANCE * max(1.0, mwh)})
    d = pl.DataFrame(rows)
    return d.with_columns(
        pl.when(pl.col("plant").str.contains(SOLAR_RE)).then(pl.lit("solar"))
        .when(pl.col("plant").str.contains(OFFSHORE_RE)).then(pl.lit("offshore"))
        .otherwise(pl.lit("onshore wind proxy")).alias("kind"))


def _flag_slots(d: pl.DataFrame, step_ms: int) -> set[tuple[str, int]]:
    out = set()
    for area, s, e in d.select(["area", "start_ms", "end_ms"]).iter_rows():
        t = s // step_ms * step_ms
        while t < e:
            out.add((area, t))
            t += step_ms
    return out


def hour_flags() -> pl.DataFrame:
    """Per (area, UTC hour start ms): rd_any (an onshore-wind proxy measure touches the hour)
    and unit_check_fail (a renewable reduction failing the unit check touches it)."""
    m = measures()
    a = _flag_slots(m.filter(pl.col("kind") == "onshore wind proxy"), HOUR_MS)
    b = _flag_slots(m.filter(pl.col("unit_fail")), HOUR_MS)
    keys = sorted(a | b)
    return pl.DataFrame({"area": [k[0] for k in keys], "hour_ms": [k[1] for k in keys],
                         "rd_any": [k in a for k in keys], "unit_check_fail": [k in b for k in keys]},
                        schema={"area": pl.String, "hour_ms": pl.Int64, "rd_any": pl.Boolean,
                                "unit_check_fail": pl.Boolean})


# ------------------------------------------------------------------ MaStR
UNIT_FIELDS = ("EinheitMastrNummer", "LokationMaStRNummer", "EinheitBetriebsstatus", "Bundesland",
               "Laengengrad", "Breitengrad", "Postleitzahl", "Gemeindeschluessel", "Nabenhoehe",
               "Rotordurchmesser", "Nettonennleistung", "Inbetriebnahmedatum",
               "DatumEndgueltigeStilllegung", "DatumBeginnVoruebergehendeStilllegung",
               "WindAnLandOderAufSee", "Typenbezeichnung")
ONSHORE = "888"
STATUS_PLANNED = "31"


@lru_cache(maxsize=1)
def units() -> pl.DataFrame:
    """Every onshore unit in the raw XML that is not only planned, with its control area:
    the register's grid-connection control area where the processed table has it (as in
    Experiment 3), the Bundesland proxy otherwise (`area_is_proxy`)."""
    from src.method.ingest_mastr import BUNDESLAND_TO_TSO, SPLIT_STATES
    rows = []
    for _, el in ET.iterparse(cfg.MASTR_DIR / "EinheitenWind.xml"):
        if el.tag == "EinheitWind":
            rows.append({f: el.findtext(f) for f in UNIT_FIELDS})
            el.clear()
    u = pl.DataFrame(rows, schema={f: pl.String for f in UNIT_FIELDS}).filter(
        (pl.col("WindAnLandOderAufSee") == ONSHORE) & (pl.col("EinheitBetriebsstatus") != STATUS_PLANNED))
    num = lambda c: pl.col(c).cast(pl.Float64, strict=False)
    u = u.with_columns(
        num("Laengengrad").alias("lon"), num("Breitengrad").alias("lat"),
        num("Nabenhoehe").alias("hub_m"), num("Rotordurchmesser").alias("rotor_m"),
        num("Nettonennleistung").alias("kw"),
        pl.col("Inbetriebnahmedatum").str.to_date(strict=False).alias("commissioned"),
        pl.col("DatumEndgueltigeStilllegung").str.to_date(strict=False).alias("decommissioned"),
        pl.col("DatumBeginnVoruebergehendeStilllegung").str.to_date(strict=False).alias("paused_from"))
    proc = pl.read_parquet(cfg.MASTR_PROCESSED).select(
        "EinheitMastrNummer", pl.col("control_area").alias("_ca"),
        pl.col("control_area_is_proxy").alias("_proxy"))
    state_tso = {k: v[1] for k, v in BUNDESLAND_TO_TSO.items()}
    u = u.join(proc, on="EinheitMastrNummer", how="left").with_columns(
        pl.coalesce(pl.col("_ca"), pl.col("Bundesland").replace_strict(state_tso, default=None))
        .alias("area"),
        pl.when(pl.col("_ca").is_not_null()).then(pl.col("_proxy"))
        .otherwise(pl.col("Bundesland").is_in(list(SPLIT_STATES))).alias("area_is_proxy"))
    return u.drop("_ca", "_proxy")


def live_in_period(u: pl.DataFrame) -> pl.DataFrame:
    lo, hi = (datetime.strptime(x, "%Y-%m-%d").date() for x in cfg.PERIOD)
    return u.filter(pl.col("area").is_in(list(cfg.AREAS)) & pl.col("commissioned").is_not_null()
                    & (pl.col("commissioned") <= hi)
                    & (pl.col("decommissioned").is_null() | (pl.col("decommissioned") > lo)))


# ------------------------------------------------------------------ DWD
def dwd_coverage() -> pl.DataFrame:
    """Per station: hours in PERIOD (UTC) with a valid wind speed, and the share."""
    lo = cfg.PERIOD[0].replace("-", "") + "00"
    hi = cfg.PERIOD[1].replace("-", "") + "23"
    frames = []
    for sub in ("historical", "recent"):
        for z in sorted((cfg.DWD_DIR / sub).glob("*.zip")):
            with zipfile.ZipFile(z) as zf:
                n = next(x for x in zf.namelist() if x.startswith("produkt"))
                df = pl.read_csv(io.BytesIO(zf.read(n)), separator=";", infer_schema_length=0)
            df = df.rename({c: c.strip() for c in df.columns}).select(
                pl.col("STATIONS_ID").str.strip_chars().cast(pl.Int64).alias("sid"),
                pl.col("MESS_DATUM").str.strip_chars().alias("t"),
                pl.col("F").str.strip_chars().cast(pl.Float64).alias("F"))
            frames.append(df.filter((pl.col("t") >= lo) & (pl.col("t") <= hi)))
    a = pl.concat(frames).unique(["sid", "t"], keep="last")
    n_hours = (datetime.strptime(cfg.PERIOD[1], "%Y-%m-%d")
               - datetime.strptime(cfg.PERIOD[0], "%Y-%m-%d")).days * 24 + 24
    return a.group_by("sid").agg((pl.col("F") >= 0).sum().alias("n_valid")).with_columns(
        (pl.col("n_valid") / n_hours).alias("coverage"), pl.lit(n_hours).alias("n_hours"))


# ------------------------------------------------------------------ clean hours
def clean_hour_counts() -> pl.DataFrame:
    """Hourly clean-hour counts per area and span: Experiment 4's rule against 4b's rule.

    Experiment 4's rule, as hours: every quarter-hour has price > 5, G > 0, F > 0 and no
    renewable reduction other than solar-named plants. 4b: price > 5 and G > 0 in every
    quarter-hour, no onshore-wind proxy measure and no unit-check failure touching the hour.
    """
    from src.method.learned_potential.data import PANEL
    m = measures()
    e4_qh = _flag_slots(m.filter(pl.col("kind") != "solar"), QH_MS)
    p = (pl.scan_parquet(PANEL)
         .filter(pl.col("area").is_in(list(cfg.AREAS)) & (pl.col("berlin_date") >= cfg.PERIOD[0])
                 & (pl.col("berlin_date") <= cfg.PERIOD[1]))
         .select(["ts_utc", "area", "berlin_date", "price_eur_mwh", "act_onshore_mw",
                  "da_onshore_mw"]).collect())
    e4 = pl.DataFrame({"area": [k[0] for k in e4_qh], "ts_utc": [k[1] for k in e4_qh]},
                      schema={"area": pl.String, "ts_utc": pl.Int64}).with_columns(pl.lit(True).alias("r4"))
    p = (p.join(e4, on=["area", "ts_utc"], how="left")
          .with_columns(pl.col("r4").fill_null(False), (pl.col("ts_utc") // HOUR_MS * HOUR_MS).alias("hour_ms")))
    h = p.group_by(["area", "hour_ms"]).agg(
        pl.col("berlin_date").first(),
        ((pl.col("price_eur_mwh") > cfg.CLEAN_PRICE_ABOVE) & (pl.col("act_onshore_mw") > 0)).all().alias("base"),
        ((pl.col("price_eur_mwh") > cfg.CLEAN_PRICE_ABOVE) & (pl.col("act_onshore_mw") > 0)
         & (pl.col("da_onshore_mw") > 0) & ~pl.col("r4")).all().alias("clean_e4"))
    h = (h.join(hour_flags(), on=["area", "hour_ms"], how="left")
          .with_columns(pl.col("rd_any").fill_null(False), pl.col("unit_check_fail").fill_null(False))
          .with_columns((pl.col("base") & ~pl.col("rd_any")).alias("clean_4b_before_unit_check"),
                        (pl.col("base") & ~pl.col("rd_any") & ~pl.col("unit_check_fail")).alias("clean_4b")))
    spans = (("history", cfg.PERIOD[0], "2025-09-30"), ("evaluation window", *cfg.EVAL_WINDOW))
    out = []
    for name, lo, hi in spans:
        q = h.filter((pl.col("berlin_date") >= lo) & (pl.col("berlin_date") <= hi))
        out.append(q.group_by("area").agg(
            pl.len().alias("hours"), pl.col("clean_e4").sum().alias("clean_e4"),
            pl.col("clean_4b_before_unit_check").sum().alias("clean_4b_before_unit_check"),
            pl.col("clean_4b").sum().alias("clean_4b")).with_columns(pl.lit(name).alias("span")))
    return pl.concat(out).sort(["span", "area"], descending=[True, False])


# ------------------------------------------------------------------ facts
def facts() -> list[dict]:
    out = []
    add = lambda k, unit, v: out.append({"fact": k, "unit": unit, "value": v})
    m = measures()
    add("measures_renewable_reductions", "three areas", m.height)
    for k in ("solar", "offshore", "onshore wind proxy"):
        add(f"measures_{k.replace(' ', '_')}", "three areas", m.filter(pl.col("kind") == k).height)
    add("measures_unit_check_fail", "three areas", int(m["unit_fail"].sum()))
    add("measures_first_day", "three areas", datetime.fromtimestamp(m["start_ms"].min() / 1000, timezone.utc).date().isoformat())
    add("measures_last_day", "three areas", datetime.fromtimestamp(m["end_ms"].max() / 1000, timezone.utc).date().isoformat())
    u = live_in_period(units())
    lo = datetime.strptime(cfg.PERIOD[0], "%Y-%m-%d").date()
    for area in (*cfg.AREAS, "all"):
        q = u if area == "all" else u.filter(pl.col("area") == area)
        kw = q["kw"].sum()
        add("units_live", area, q.height)
        add("gw_live", area, round(kw / 1e6, 2))
        dec = q.filter(pl.col("decommissioned").is_not_null())
        add("units_decommissioned_in_period", area, dec.height)
        add("gw_decommissioned_in_period", area, round(dec["kw"].sum() / 1e6, 2))
        for name, expr in (("coordinates", pl.col("lon").is_null() | pl.col("lat").is_null()),
                           ("hub_height", pl.col("hub_m").is_null() | (pl.col("hub_m") <= 0)),
                           ("rotor_diameter", pl.col("rotor_m").is_null() | (pl.col("rotor_m") <= 0))):
            add(f"missing_{name}_capacity_share", area, round(float(q.filter(expr)["kw"].sum() / kw), 4))
        add("area_proxy_capacity_share", area, round(float(q.filter(pl.col("area_is_proxy"))["kw"].sum() / kw), 4))
    c = dwd_coverage()
    add("dwd_stations_with_data", "Germany", c.height)
    add("dwd_stations_min_coverage", "Germany", c.filter(pl.col("coverage") >= cfg.DWD_MIN_COVERAGE).height)
    for r in clean_hour_counts().iter_rows(named=True):
        for k in ("hours", "clean_e4", "clean_4b_before_unit_check", "clean_4b"):
            add(f"{k}|{r['span']}", r["area"], r[k])
    return out


def write() -> None:
    cfg.ART.mkdir(parents=True, exist_ok=True)
    rows = facts()
    with FACTS.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["fact", "unit", "value"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {FACTS} ({len(rows)} rows)")


def _read() -> dict[tuple[str, str], str]:
    with FACTS.open(newline="", encoding="utf-8") as fh:
        return {(r["fact"], r["unit"]): r["value"] for r in csv.DictReader(fh)}


def _md(header, rows) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return "\n".join(out + ["| " + " | ".join(map(str, r)) + " |" for r in rows])


def redispatch_text() -> str:
    f = _read()
    g = lambda k: int(f[(k, "three areas")])
    return (f"- Renewable reductions instructed by the three TSOs, {f[('measures_first_day', 'three areas')]} "
            f"to {f[('measures_last_day', 'three areas')]}: {g('measures_renewable_reductions'):,}. "
            f"Named solar or PV: {g('measures_solar'):,}. Named offshore: {g('measures_offshore'):,}. "
            f"Counted as onshore wind (the proxy): {g('measures_onshore_wind_proxy'):,}. Failing the "
            f"unit check: {g('measures_unit_check_fail'):,} of {g('measures_renewable_reductions'):,}.")


def fleet_text() -> str:
    f = _read()
    rows = []
    for a in (*cfg.AREAS, "all"):
        pct = lambda k: f"{float(f[(k, a)]):.2%}"
        rows.append([a, f"{int(f[('units_live', a)]):,}", f[("gw_live", a)],
                     f"{int(f[('units_decommissioned_in_period', a)]):,} ({f[('gw_decommissioned_in_period', a)]} GW)",
                     pct("missing_coordinates_capacity_share"), pct("missing_hub_height_capacity_share"),
                     pct("missing_rotor_diameter_capacity_share"), pct("area_proxy_capacity_share")])
    return _md(["area", "units live in the period", "GW", "decommissioned in the period",
                "no coordinates", "no hub height", "no rotor diameter", "area by Bundesland proxy, split state"],
               rows)


def clean_text() -> str:
    f = _read()
    rows = []
    for span in ("history", "evaluation window"):
        for a in cfg.AREAS:
            g = lambda k: f"{int(f[(f'{k}|{span}', a)]):,}"
            rows.append([span, a, g("hours"), g("clean_e4"), g("clean_4b_before_unit_check"), g("clean_4b")])
    return _md(["span", "area", "hours", "clean, Experiment 4's rule", "clean, 4b before the unit check",
                "clean, 4b"], rows)


def dwd_text() -> str:
    f = _read()
    return (f"- DWD stations with data in the period: {int(f[('dwd_stations_with_data', 'Germany')])}; "
            f"with at least {cfg.DWD_MIN_COVERAGE:.0%} of hours valid: "
            f"{int(f[('dwd_stations_min_coverage', 'Germany')])}.")


if __name__ == "__main__":
    write()
