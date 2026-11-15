"""Q6b summary, written before any Q6b number was read (`docs/Q6_preregistration.md`).

    python -m src.identification.summarise_q6b

Per (sigma_r, sigma): coverage, median eps, median floor ratio rms_floor/rms_point
(one value per cell), and the fleet informative share: informative (cell, functional)
pairs over defined ones, functionals L1 and L2.

S1: at sigma = 0.066 the fleet share lies in [0.004, 0.117] (Clopper-Pearson for 2/59).
S2: from sigma = 0.18 to 0.066 at the same sigma_r, median eps falls and median floor
ratio rises. SUPPORTED if some sigma_r > 0 meets both. Also reported, deciding nothing:
the fleet share against Q5's 3 of 11 and its Clopper-Pearson interval.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import beta

from src.identification.summarise_p3 import load

REPO_ROOT = Path(__file__).resolve().parents[2]
Q6 = REPO_ROOT / "artifacts" / "Q6"
S1_BAND = (0.004, 0.117)
H, T = 0.066, 0.18


def cp(k: int, n: int) -> tuple[float, float]:
    lo = beta.ppf(0.025, k, n - k + 1) if k > 0 else 0.0
    hi = beta.ppf(0.975, k + 1, n - k) if k < n else 1.0
    return float(lo), float(hi)


def main() -> None:
    d = load(Q6 / "q6b_day_effect.csv")
    for c in ("sigma", "sigma_r", "eps", "rms_floor", "rms_point"):
        d = d.with_columns(pl.col(c).cast(pl.Float64, strict=False))
    if d["informative"].dtype == pl.String:
        d = d.with_columns(pl.col("informative").str.to_lowercase().replace(
            {"true": "1", "false": "0", "": None}).cast(pl.Float64).alias("informative"))
    else:
        d = d.with_columns(pl.col("informative").cast(pl.Float64))
    cell = ["hetero", "rate", "gamma", "r_shape"]
    q5_lo, q5_hi = cp(3, 11)
    lv = []
    for (sr, sg), g in sorted(d.group_by(["sigma_r", "sigma"]), key=lambda t: t[0]):
        one = g.filter(pl.col("lam") == "L1")
        fleet = g.filter(pl.col("lam").is_in(["L1", "L2"]) & pl.col("informative").is_not_null())
        share = float(fleet["informative"].mean()) if fleet.height else np.nan
        cov = g.filter(pl.col("cov").is_not_null())
        lv.append({"sigma_r": sr, "sigma": sg, "n_cells": one.unique(subset=cell).height,
                   "coverage": float(cov["cov"].cast(pl.Float64).mean()) if cov.height else np.nan,
                   "median_eps": float(one["eps"].median()),
                   "median_floor_ratio": float((one["rms_floor"] / one["rms_point"]).median()),
                   "fleet_informative": int(fleet["informative"].sum()),
                   "fleet_defined": fleet.height, "fleet_share": share,
                   "s1_in_band": bool(S1_BAND[0] <= share <= S1_BAND[1]) if sg == H else None,
                   "in_q5_fleet_cp_3_of_11": (bool(q5_lo <= share <= q5_hi) if sg == H else None),
                   "L1_informative": int(g.filter((pl.col("lam") == "L1"))["informative"].sum()),
                   "L2_informative": int(g.filter((pl.col("lam") == "L2"))["informative"].sum())})
    by = {(r["sigma_r"], r["sigma"]): r for r in lv}
    verdict_rows, passing = [], []
    for sr in sorted({r["sigma_r"] for r in lv}):
        h, t = by.get((sr, H)), by.get((sr, T))
        if h is None or t is None:
            continue
        s1 = bool(h["s1_in_band"])
        s2 = bool(h["median_eps"] < t["median_eps"]
                  and h["median_floor_ratio"] > t["median_floor_ratio"])
        if sr > 0 and s1 and s2:
            passing.append(sr)
        verdict_rows.append({"sigma_r": sr, "s1": s1, "s2": s2, "both": s1 and s2,
                             "eps_T": t["median_eps"], "eps_H": h["median_eps"],
                             "floor_T": t["median_floor_ratio"],
                             "floor_H": h["median_floor_ratio"],
                             "fleet_share_H": h["fleet_share"]})
    verdict = "SUPPORTED" if passing else "NOT SUPPORTED"
    out = Q6 / "q6b_summary.csv"
    fields: list[str] = ["table"]
    for r in lv + verdict_rows:
        fields += [k for k in r if k not in fields]
    fields += ["verdict", "passing_sigma_r", "q5_fleet_cp_lo", "q5_fleet_cp_hi"]
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in lv:
            w.writerow({"table": "levels", **r})
        for r in verdict_rows:
            w.writerow({"table": "signatures", **r})
        w.writerow({"table": "verdict", "verdict": verdict,
                    "passing_sigma_r": "|".join(str(x) for x in passing),
                    "q5_fleet_cp_lo": q5_lo, "q5_fleet_cp_hi": q5_hi})
    with pl.Config(tbl_rows=40, tbl_width_chars=260, float_precision=4, tbl_cols=20):
        print(pl.DataFrame(lv))
        print(pl.DataFrame(verdict_rows))
    print(f"verdict {verdict}; passing sigma_r {passing}; wrote {out}")


if __name__ == "__main__":
    main()
