#!/usr/bin/env python3
"""Step 5 — Check 2 (test C): does grid redispatch explain the negative-price bias?

DATA ACCESS
-----------
This script needs the Netztransparenz redispatch-measures export covering
2025-10-01 .. 2026-10-28. As of 29 Oct 2026 that export is NOT reachable
without credentials:

  * https://ds.netztransparenz.de/api/v1/data/... returns HTTP 401. The FAQ
    requires registering on netztransparenz.de for the "WebAPIReader" role and
    creating a Client in the WebAPI-Portal to obtain a ClientID/ClientSecret
    (OAuth 2.0 client-credentials grant).
  * The "Download CSV" control on the public Redispatch page is an ASP.NET
    WebForms postback with no GET URL.
  * The Datencenter is a Blazor single-page app; download is a browser action.
  * The only anonymous file link covers 2013-2020 only.

So this step is BLOCKED on data the project does not have. It is deliberately
not worked around. Drop a CSV export into data/raw/netztransparenz/ (any
filename ending .csv) and re-run; the parser below is written against the field
names the Redispatch page documents.

Leakage note: redispatch is published after the fact. It is used here ONLY to
stratify the evaluation, never as a model input.

Usage:  python src/redispatch_control.py
Exit 2 = blocked, no input data (this is the expected state).
"""

from __future__ import annotations

import csv
import glob
import os
import re
import sys
from datetime import datetime, timedelta

import numpy as np
import polars as pl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smard_config import (  # noqa: E402
    AREAS, AREA_LABEL, N_BOOT, PROCESSED_DIR, RESULTS_DIR, SEED, UTC,
)
from event_day_bootstrap import ci_excludes_zero, eventday_bootstrap_mean  # noqa: E402

RAW_RD = "data/raw/netztransparenz"
QH = timedelta(minutes=15)

# Plant names that indicate PV. The redispatch export has no clean carrier flag
# below "Erneuerbar", so solar is removed by name, and the removed share is
# logged so the reader can judge it.
SOLAR_RE = re.compile(r"(solar|photovolt|\bpv\b|\bpv[-_ ])", re.IGNORECASE)

# Netztransparenz TSO spellings -> SMARD region codes.
TSO_MAP = {
    "50hertz": "50Hertz", "50hertz transmission": "50Hertz",
    "amprion": "Amprion",
    "tennet": "TenneT", "tennet tso": "TenneT",
    "tennet de": "TenneT", "tennet tso gmbh": "TenneT",
    "transnetbw": "TransnetBW", "transnet bw": "TransnetBW",
}

# Candidate header names, lowercased, for each field we need.
# Only downward measures count. The export also carries upward ones
# ("Wirkleistungseinspeisung erhoehen"), including a handful on renewables.
REDUCE_RE = re.compile(r"reduzier", re.IGNORECASE)

# GRUND_DER_MASSNAHME values to drop. "Probefahrt" is a test run / trial start of a
# reserve power plant, not congestion-driven curtailment, so it does not belong in a
# redispatch control. Cross-border countertrade (DE-DK1/DK2) is also excluded on
# principle; in this export no countertrade row is a renewable reduction, so the
# filter is a no-op for it, but it is kept so a future export cannot slip one in.
EXCLUDE_GRUND_RE = re.compile(r"(probefahrt|countertrade)", re.IGNORECASE)

FIELD_CANDIDATES = {
    "start_date":  ["beginn_datum", "datum_beginn", "beginn datum", "start_datum"],
    "start_time":  ["beginn_uhrzeit", "uhrzeit_beginn", "beginn uhrzeit", "start_uhrzeit"],
    "end_date":    ["ende_datum", "datum_ende", "ende datum", "end_datum"],
    "end_time":    ["ende_uhrzeit", "uhrzeit_ende", "ende uhrzeit", "end_uhrzeit"],
    "start_dt":    ["beginn", "start", "von", "beginn_der_massnahme"],
    "end_dt":      ["ende", "end", "bis", "ende_der_massnahme"],
    "energy_mwh":  ["gesamte_arbeit_mwh", "gesamte arbeit mwh", "gesamte_arbeit",
                    "arbeit_mwh"],
    "mean_mw":     ["mittlere_leistung_mw", "mittlere leistung mw",
                    "mittlere_leistung"],
    "max_mw":      ["maximale_leistung_mw", "maximale leistung mw"],
    "instructing": ["anweisender_uenb", "anweisender_übertragungsnetzbetreiber",
                    "anweisender uenb", "anweisender_unb", "anweisender ünb"],
    "direction":   ["richtung", "art_der_massnahme", "massnahme"],
    "reason":      ["grund_der_massnahme", "grund", "massnahmengrund"],
    "carrier":     ["primaerenergieart", "primärenergieart", "energietraeger",
                    "energieträger", "erzeugungsart"],
    "plant":       ["betroffene_anlage", "anlage", "name_der_anlage", "kraftwerk",
                    "anlagenname"],
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")


def find_input() -> list[str]:
    """Redispatch exports only.

    This used to glob every CSV in the Netztransparenz folder, which was fine when
    the redispatch export was the only file there. It is not any more -- the
    monthly market values and the Online-Hochrechnung now live alongside it -- and
    the glob picked them up and failed on the column check. Matching the filename
    keeps the kill test reading the file it was validated on.
    """
    return sorted(glob.glob(os.path.join(RAW_RD, "redispatch_*.csv")))


def blocked(msg: str) -> int:
    print("=" * 72)
    print("STEP 5  redispatch_control.py  (Check 2 / test C)")
    print("=" * 72)
    print("BLOCKED — " + msg)
    print()
    print("Needed: Netztransparenz redispatch measures, 2025-10-01 .. 2026-10-28.")
    print("Options:")
    print("  (a) WebAPI ClientID + ClientSecret (register on netztransparenz.de")
    print("      for role 'WebAPIReader', then create a Client in the")
    print("      WebAPI-Portal); base URL")
    print("      https://ds.netztransparenz.de/api/v1/data/{data}/{product}/{from}/{to}")
    print("  (b) a manual CSV export from the public Redispatch page")
    print("      (Von 01.10.2025, Bis 28.10.2026, timezone UTC) placed in")
    print(f"      {RAW_RD}/")
    print()
    print("Not attempted: replaying the ASP.NET postback or driving the SPA in a")
    print("browser. Both would be working around an access restriction.")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(f"{RESULTS_DIR}/04_test_c_BLOCKED.txt", "w") as fh:
        fh.write("Check 2 / test C not computed.\n"
                 "Reason: Netztransparenz redispatch export requires OAuth client "
                 "credentials (HTTP 401) or a browser download; no anonymous URL "
                 "covers 2025-10 .. 2026-10.\n"
                 f"Drop a CSV export in {RAW_RD}/ and re-run.\n")
    return 2


def parse_measures(paths: list[str]) -> pl.DataFrame:
    """Read the export and return one row per measure."""
    rows = []
    header_seen = None
    for path in paths:
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as fh:
            sample = fh.read(8192)
            fh.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
                delim = dialect.delimiter
            except csv.Error:
                delim = ";"
            reader = csv.DictReader(fh, delimiter=delim)
            cols = {norm(c): c for c in (reader.fieldnames or [])}
            header_seen = reader.fieldnames

            def pick(field):
                for cand in FIELD_CANDIDATES[field]:
                    if norm(cand) in cols:
                        return cols[norm(cand)]
                return None

            m = {k: pick(k) for k in FIELD_CANDIDATES}
            missing = [k for k in ("energy_mwh", "instructing", "carrier")
                       if m[k] is None]
            has_start = m["start_dt"] or (m["start_date"] and m["start_time"])
            has_end = m["end_dt"] or (m["end_date"] and m["end_time"])
            if missing or not has_start or not has_end:
                raise SystemExit(
                    "Could not map the required columns in "
                    f"{os.path.basename(path)}.\n"
                    f"  header: {header_seen}\n"
                    f"  unmapped: {missing}"
                    f"{' + start' if not has_start else ''}"
                    f"{' + end' if not has_end else ''}\n"
                    "Edit FIELD_CANDIDATES in src/redispatch_control.py to match."
                )
            for r in reader:
                rows.append({k: (r.get(v) if v else None) for k, v in m.items()})
    print(f"  parsed {len(rows)} measure rows from {len(paths)} file(s)")
    print(f"  header: {header_seen}")
    return pl.DataFrame(rows)


def to_dt(date_s, time_s, combined_s):
    raw = combined_s if combined_s else f"{date_s} {time_s}"
    raw = (raw or "").strip()
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def main() -> int:
    paths = find_input()
    if not paths:
        return blocked(f"no CSV found in {RAW_RD}/")

    print("=" * 72)
    print("STEP 5  redispatch_control.py  (Check 2 / test C)")
    print("=" * 72)
    meas = parse_measures(paths)
    n0 = meas.height

    recs = []
    unmapped_tso: set[str] = set()
    n_solar = n_nonre = n_badtime = n_badtso = n_notreduce = n_badgrund = 0
    reason_rows: dict[str, int] = {}
    excluded_reason_rows: dict[str, int] = {}
    energy_by_tso: dict[str, float] = {}
    for r in meas.iter_rows(named=True):
        carrier = (r["carrier"] or "")
        if "erneuerbar" not in carrier.lower():
            n_nonre += 1
            continue
        if not REDUCE_RE.search(r["direction"] or ""):
            n_notreduce += 1
            continue
        reason = (r.get("reason") or "").strip()
        reason_rows[reason] = reason_rows.get(reason, 0) + 1
        if EXCLUDE_GRUND_RE.search(reason):
            n_badgrund += 1
            excluded_reason_rows[reason] = excluded_reason_rows.get(reason, 0) + 1
            continue
        plant = r["plant"] or ""
        if SOLAR_RE.search(plant):
            n_solar += 1
            continue
        tso = TSO_MAP.get(norm(r["instructing"] or "").replace("_", " ").strip())
        if tso is None:
            tso = TSO_MAP.get((r["instructing"] or "").strip().lower())
        if tso is None:
            n_badtso += 1
            unmapped_tso.add((r["instructing"] or "").strip())
            continue
        start = to_dt(r["start_date"], r["start_time"], r["start_dt"])
        end = to_dt(r["end_date"], r["end_time"], r["end_dt"])
        if start is None or end is None or end <= start:
            n_badtime += 1
            continue
        try:
            energy = float(str(r["energy_mwh"]).replace(".", "").replace(",", ".")
                           if "," in str(r["energy_mwh"]) else r["energy_mwh"])
        except (TypeError, ValueError):
            continue
        recs.append((start, end, energy, tso))
        energy_by_tso[tso] = energy_by_tso.get(tso, 0.0) + energy

    print(f"  kept {len(recs)} renewable reduction measures "
          f"(dropped: non-renewable {n_nonre}, upward/not-reduction {n_notreduce}, "
          f"excluded reason {n_badgrund}, solar-named {n_solar}, "
          f"unmapped TSO {n_badtso}, bad timestamps {n_badtime}; of {n0})")
    if n0:
        print(f"  solar-named share of renewable reduction rows: "
              f"{100.0 * n_solar / max(1, n_solar + len(recs)):.2f}%")

    # ---- sanity checks -----------------------------------------------------
    print("-" * 72)
    print("SANITY CHECKS")
    print("  GRUND_DER_MASSNAHME among renewable reductions (before exclusions):")
    for k, v in sorted(reason_rows.items(), key=lambda t: -t[1]):
        mark = "  EXCLUDED" if EXCLUDE_GRUND_RE.search(k) else ""
        print(f"    {v:6d}  {k}{mark}")
    if excluded_reason_rows:
        print(f"  excluded by reason: {dict(excluded_reason_rows)}")
    print("  renewable reduction energy by instructing TSO:")
    for tso, e in sorted(energy_by_tso.items(), key=lambda t: -t[1]):
        print(f"    {tso:12s} {e / 1e6:7.4f} TWh")
    print(f"    {'TOTAL':12s} {sum(energy_by_tso.values()) / 1e6:7.4f} TWh")

    # ---- spread each measure's energy evenly over its quarter-hours --------
    # MW in each covered quarter-hour = energy / duration_in_hours.
    rd: dict[tuple[int, str], float] = {}
    for start, end, energy, tso in recs:
        dur_h = (end - start).total_seconds() / 3600.0
        if dur_h <= 0:
            continue
        mw = energy / dur_h
        t = start
        while t < end:
            ts_ms = int(t.replace(tzinfo=UTC).timestamp() * 1000)
            rd[(ts_ms, tso)] = rd.get((ts_ms, tso), 0.0) + mw
            t += QH
    if unmapped_tso:
        raise SystemExit(
            "Unmapped instructing-TSO values would silently drop measures: "
            f"{sorted(unmapped_tso)}. Add them to TSO_MAP in "
            "src/redispatch_control.py and re-run.")
    print(f"  redispatch spread over {len(rd)} (quarter-hour, TSO) cells")

    panel = pl.read_parquet(os.path.join(PROCESSED_DIR, "panel_qh.parquet"))
    panel = panel.filter(
        pl.col("price_eur_mwh").is_not_nan() & pl.col("e_mw").is_not_nan()
        & pl.col("da_wind_mw").is_not_nan())

    # DE redispatch = sum over the four control areas
    de_rd: dict[int, float] = {}
    for (ts_ms, tso), v in rd.items():
        de_rd[ts_ms] = de_rd.get(ts_ms, 0.0) + v

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_rows = []
    print("-" * 72)
    print(f"  {'area':11s} {'negQH':>6} {'raw bias':>10} {'excess C':>10} "
          f"{'CI':>24} {'%negQH w/ RD':>13}")
    for area in AREAS:
        a = panel.filter(pl.col("area") == area).sort("ts_utc")
        ts = a["ts_utc"].to_numpy()
        e = a["e_mw"].to_numpy()
        da = a["da_wind_mw"].to_numpy()
        price = a["price_eur_mwh"].to_numpy()
        days = a["berlin_date"].to_numpy()
        if area == "DE":
            rdv = np.array([de_rd.get(int(t), 0.0) for t in ts])
        else:
            rdv = np.array([rd.get((int(t), area), 0.0) for t in ts])

        neg = price < 0.0
        pos = price > 0.0

        # 5 redispatch bins: bin 0 is exactly zero, bins 1-4 are quartiles of
        # the strictly positive values. Quantiles alone would collapse in the
        # areas that are almost redispatch-free.
        nz = rdv[rdv > 0]
        if len(nz) >= 8:
            cuts = np.quantile(nz, [0.25, 0.5, 0.75])
            rbin = np.digitize(rdv, cuts) + 1
            rbin[rdv <= 0] = 0
        else:
            rbin = (rdv > 0).astype(int)

        # forecast-level deciles
        dcuts = np.quantile(da, np.arange(0.1, 1.0, 0.1))
        fbin = np.digitize(da, dcuts)

        key = rbin.astype(np.int64) * 100 + fbin.astype(np.int64)
        pos_mean: dict[int, float] = {}
        for k in np.unique(key[pos]):
            pos_mean[int(k)] = float(e[pos & (key == k)].mean())

        have = np.array([int(k) in pos_mean for k in key]) & neg
        n_dropped = int(neg.sum() - have.sum())
        excess = e[have] - np.array([pos_mean[int(k)] for k in key[have]])

        mean_c, lo_c, hi_c, n_c, nd_c = eventday_bootstrap_mean(
            excess, days[have], N_BOOT, SEED)
        raw, lo_r, hi_r, n_r, nd_r = eventday_bootstrap_mean(
            e[neg], days[neg], N_BOOT, SEED)
        share_rd = 100.0 * float((rdv[neg] > 0).mean()) if neg.sum() else np.nan

        zero_rd = neg & (rdv <= 0)
        if zero_rd.sum() > 0:
            m_z, lo_z, hi_z, n_z, nd_z = eventday_bootstrap_mean(
                e[zero_rd], days[zero_rd], N_BOOT, SEED)
        else:
            m_z = lo_z = hi_z = np.nan; n_z = 0

        out_rows.append({
            "area": AREA_LABEL[area],
            "negative_qhs": n_r, "event_days": nd_r,
            "raw_bias_neg_qh_mw": round(raw, 1),
            "raw_ci_lo_mw": round(lo_r, 1), "raw_ci_hi_mw": round(hi_r, 1),
            "excess_test_c_mw": round(mean_c, 1),
            "excess_ci_lo_mw": round(lo_c, 1) if np.isfinite(lo_c) else "",
            "excess_ci_hi_mw": round(hi_c, 1) if np.isfinite(hi_c) else "",
            "excess_ci_excludes_zero": ci_excludes_zero(lo_c, hi_c),
            "neg_qhs_matched": n_c, "neg_qhs_unmatched_dropped": n_dropped,
            "pct_neg_qh_with_any_re_redispatch": round(share_rd, 1),
            "total_re_redispatch_twh": round(float(rdv.sum()) * 0.25 / 1e6, 3),
            "bias_neg_qh_zero_redispatch_mw": round(m_z, 1) if np.isfinite(m_z) else "",
            "zero_rd_ci_lo_mw": round(lo_z, 1) if np.isfinite(lo_z) else "",
            "zero_rd_ci_hi_mw": round(hi_z, 1) if np.isfinite(hi_z) else "",
            "zero_rd_neg_qhs": n_z,
        })
        print(f"  {AREA_LABEL[area]:11s} {n_r:>6} {raw:>10.1f} {mean_c:>10.1f} "
              f"[{lo_c:>9.1f},{hi_c:>9.1f}] {share_rd:>12.1f}%")

    with open(f"{RESULTS_DIR}/04_redispatch_test_c.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, lineterminator="\n", fieldnames=list(out_rows[0].keys()))
        w.writeheader(); w.writerows(out_rows)
    print("-" * 72)
    print(f"wrote {RESULTS_DIR}/04_redispatch_test_c.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
