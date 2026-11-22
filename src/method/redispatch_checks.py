"""What the renewable redispatch series R contains, and whether its rows are internally
consistent (22 Nov 2026, Phase 6 prep; diagnosis in docs/07).

    python -m src.method.redispatch_checks      # writes artifacts/available_power_estimate/redispatch_checks.csv

R (`projection_and_redispatch.redispatch_qh`) is every Netztransparenz measure with
PRIMAERENERGIEART "Erneuerbar" and direction "reduzieren", minus test runs, countertrade and
plants named solar or PV, assigned to the instructing TSO. The export has no finer technology
field, so R is not onshore wind alone. This module records, from the 2025-10-01 to 2026-10-28
export only:

  unit_check   measures whose mean MW x duration differs from the stated MWh by more than 2%
               (all renewable reductions in the export, every TSO)
  composition  for 50Hertz + Amprion + TransnetBW, the share of R's energy by plant-name pattern:
               offshore wind parks (OWP / offshore), distribution-cluster aggregates (_CR_),
               substations (UW), other named plants
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORT = (REPO_ROOT / "data" / "raw" / "netztransparenz"
          / "redispatch_2025-10-01_2026-10-28_UTC_dl2026-10-29.csv")
OUT = REPO_ROOT / "artifacts" / "available_power_estimate" / "redispatch_checks.csv"
TOLERANCE = 0.02
THREE = ("50Hertz", "Amprion", "TransnetBW")


def _num(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def _kind(plant: str) -> str:
    p = f" {plant} "
    if "OWP" in p or "ffshore" in p:
        return "offshore wind park (OWP)"
    if "_CR_" in p:
        return "distribution-cluster aggregate (_CR_)"
    if " UW " in p:
        return "substation (UW)"
    return "other named plant"


def checks(path: Path = EXPORT) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh, delimiter=";"))
    re_red = [r for r in rows if "rneuerbar" in r["PRIMAERENERGIEART"]
              and "reduz" in r["RICHTUNG"].lower()
              and not any(x in r["GRUND_DER_MASSNAHME"].lower() for x in ("probefahrt", "countertrade"))]
    tz = {r["ZEITZONE_VON"] for r in rows} | {r["ZEITZONE_BIS"] for r in rows}
    bad = 0
    for r in re_red:
        s = datetime.strptime(f"{r['BEGINN_DATUM']} {r['BEGINN_UHRZEIT']}", "%d.%m.%Y %H:%M")
        e = datetime.strptime(f"{r['ENDE_DATUM']} {r['ENDE_UHRZEIT']}", "%d.%m.%Y %H:%M")
        hours = (e - s).total_seconds() / 3600.0
        energy = _num(r["GESAMTE_ARBEIT_MWH"])
        if abs(_num(r["MITTLERE_LEISTUNG_MW"]) * hours - energy) > TOLERANCE * max(1.0, energy):
            bad += 1
    out = [{"check": "unit_check", "item": "mean MW x duration vs MWh, more than 2% apart",
            "count": bad, "of": len(re_red), "share": bad / len(re_red),
            "note": f"renewable reductions, every TSO; timestamps all in {sorted(tz)}"}]
    three = [r for r in re_red if r["ANWEISENDER_UENB"] in THREE
             and not any(x in r["BETROFFENE_ANLAGE"].lower() for x in ("solar", "photovolt"))
             and " pv " not in f" {r['BETROFFENE_ANLAGE'].lower()} "]
    total = sum(_num(r["GESAMTE_ARBEIT_MWH"]) for r in three)
    kinds: dict[str, list[float]] = {}
    for r in three:
        kinds.setdefault(_kind(r["BETROFFENE_ANLAGE"]), []).append(_num(r["GESAMTE_ARBEIT_MWH"]))
    for k, v in sorted(kinds.items(), key=lambda kv: -sum(kv[1])):
        out.append({"check": "composition", "item": k, "count": len(v), "of": len(three),
                    "share": sum(v) / total, "note": "share of three-area R energy (MWh)"})
    return out


def main() -> None:
    rows = checks()
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
