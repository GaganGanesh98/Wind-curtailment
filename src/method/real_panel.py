"""P3 on the real German panel: which functionals the data pins, and which it does not.

    python -m src.method.real_panel

Ex post (T1), as `docs/P3_results.md` section 0.11 records: the published monthly
Netztransparenz market value builds theta, which is correct for a structural question
and would be leakage in a forecast. The forecast-time allow-list in
`src/postauction/leakage.py` governs Phase P *models* and does not bind here.

`c_hat = 1 - G/F` uses the published day-ahead forecast as the potential -- a crude
stand-in, named as one in every table. A stage-A A_hat on the real panel needs the
adapter `docs/P0_preregistration.md` section 10.3 flagged as untracked, and Phase P
has not adopted another session's uncommitted file. The recalibrated arm
(`c_hat` minus its own mean on price > 5 EUR/MWh quarter-hours) is run beside it, so
the reader can see how much of the answer rests on that choice.

Window: Berlin dates from 2025-10-01 (`MTU15_FIRST_DELIVERY_DAY`), as
`docs/P0_preregistration.md` section 3 restricts P1 and P3-on-real-data. Months
without a published market value are dropped, because theta cannot be formed for them
and defaulting it to zero would manufacture exposure.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl

from src.method.exposure import QH_CLOCK, build_clock_features
from src.method.collinearity import duplicate_groups, exposure_rank
from src.method.real_theta import _real_panel_theta
from src.method.window import MTU15_FIRST_DELIVERY_DAY
from src.method import functionals as fx
from src.method.bounds import (
    build_design, compress_rows, epsilon_from_bootstrap, identified_set, in_row_space,
    point_fit,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PANEL = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"
OUT_DIR = REPO_ROOT / "archive" / "artifacts" / "P3"   # P3 real data (F) is archived
PREREG_COMMIT = "1cd4b30"

SETTINGS = ("low", "main", "high")
AREA = "DE"
SAFE_FLOOR = 5.0

#: `docs/P0_preregistration.md` section 7, on the real MaStR cohort set.
L3_COHORT = "pre2016_in_support_no_s51"
L5_COHORT = "wind2023_feb2025_staircase"
L7_COHORT = "out_of_support"
COLLINEAR_PAIR = ("out_of_support", "post_feb2025_qh")


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:                                            # noqa: BLE001
        return "unknown"


THREE_AREA = "50Hertz+Amprion+TransnetBW"
POTENTIALS = ("F", "H")


def _three_area_series(obs: pl.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """G, F and H summed over 50Hertz, Amprion and TransnetBW, aligned to `obs`.

    The quarter-hours are Q0b's (`q0b_validate_h.load_frames`, quality-assured): those
    on which all three areas report G, F and H. Elsewhere the series are NaN, so the
    caller's finiteness mask drops them -- in BOTH potential arms (Q5 pre-registration
    section 2).
    """
    from src.method.available_power import AGG_NAME, load_frames
    agg = load_frames("quality-assured")[AGG_NAME].select(
        ["ts_utc", "act_onshore_mw", "da_onshore_mw", "hr_mw"])
    j = obs.select("ts_utc").join(agg, on="ts_utc", how="left")
    if j.height != obs.height or (j["ts_utc"] != obs["ts_utc"]).any():
        raise ValueError("three-area series do not align with the national panel")
    return tuple(j[c].to_numpy().astype(float)
                 for c in ("act_onshore_mw", "da_onshore_mw", "hr_mw"))


def _region_shares(cohorts, region: str) -> np.ndarray:
    """Capacity share per cohort: P3's national shares, or the three areas' MW summed."""
    if region == AREA:
        return np.array([c.capacity_share for c in cohorts], dtype=float)
    areas = THREE_AREA.split("+")
    with open(REPO_ROOT / "artifacts" / "method_inputs" / "mastr_cohort_shares.csv", newline="",
              encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["area"] in areas]
    mw = {c.cohort_id: 0.0 for c in cohorts}
    for r in rows:
        mw[r["cohort"]] += float(r["capacity_mw"])
    v = np.array([mw[c.cohort_id] for c in cohorts], dtype=float)
    return v / v.sum()


def load_panel(region: str = AREA, potential: str = "F"):
    """Price, potential, output and dates for the window, with theta per setting.

    Defaults reproduce P3 (`region = DE`, `potential = F`). Q5 calls it with the
    three-area region and `potential` F or H; theta, prices and the clock stay national
    (the rules and prices are), and only G, the potential and the shares change.
    """
    if region not in (AREA, THREE_AREA) or potential not in POTENTIALS:
        raise ValueError(f"unknown region {region!r} or potential {potential!r}")
    if region == AREA and potential != "F":
        raise ValueError("a DE-wide projection potential is blocked by T-D(vii) "
                         "(docs/Q_STOP_Q0c.md)")
    cohorts, price_all, mv_mask, dates_all, theta_for = _real_panel_theta()

    obs = (pl.scan_parquet(PANEL).filter(pl.col("area") == AREA)
           .select(["ts_utc", "berlin_date", "price_eur_mwh", "da_onshore_mw",
                    "act_onshore_mw"])
           .collect().drop_nulls(["price_eur_mwh"]).sort("ts_utc"))
    if obs.height != price_all.size:
        raise ValueError(
            f"the panel slice ({obs.height} rows) and _real_panel_theta "
            f"({price_all.size}) disagree; they must be the same quarter-hours")
    np.testing.assert_allclose(obs["price_eur_mwh"].to_numpy(), price_all, atol=1e-9)

    bdate = obs["berlin_date"].to_numpy().astype(str)
    if region == AREA:
        f = obs["da_onshore_mw"].to_numpy().astype(float)
        g = obs["act_onshore_mw"].to_numpy().astype(float)
        finite = np.isfinite(f) & np.isfinite(g) & (f > 0)
    else:
        g, f_da, h = _three_area_series(obs)
        # The same quarter-hours in both arms: every series finite, both potentials > 0.
        finite = (np.isfinite(g) & np.isfinite(f_da) & np.isfinite(h)
                  & (f_da > 0) & (h > 0))
        f = f_da if potential == "F" else h
    keep = (bdate >= MTU15_FIRST_DELIVERY_DAY) & mv_mask & finite
    clock = build_clock_features(obs["ts_utc"].to_numpy().astype("int64") * 1_000_000,
                                 price_all)
    runlen = np.stack([clock.qh_run_length / 4.0 if c.clock == QH_CLOCK
                       else clock.hour_run_length.astype(float) for c in cohorts])
    return {
        "cohorts": cohorts, "theta_for": theta_for, "price": price_all, "f": f, "g": g,
        "bdate": bdate, "keep": keep, "runlen": runlen,
        "shares": _region_shares(cohorts, region),
        "area": region, "potential": potential,
        "ids": tuple(c.cohort_id for c in cohorts),
        "n_dropped_non_finite": int((~finite & (bdate >= MTU15_FIRST_DELIVERY_DAY)
                                     & mv_mask).sum()),
    }


def run_arm(panel, setting: str, sel: np.ndarray, label: str, recalibrate: bool) -> list[dict]:
    """One (award setting, period, c_hat) arm."""
    ids, shares = panel["ids"], panel["shares"]
    price = panel["price"][sel]
    f, g = panel["f"][sel], panel["g"][sel]
    bdate = panel["bdate"][sel]
    theta = panel["theta_for"](setting)[:, sel]
    s = (price[None, :] < theta).astype(float)
    depth = np.maximum(0.0, theta - price[None, :]) * s
    runlen = panel["runlen"][:, sel]

    c_hat_full = 1.0 - g / np.maximum(f, 1e-9)        # f is the potential: F, or H in Q5
    offset = 0.0
    if recalibrate:
        safe = price > SAFE_FLOOR
        offset = float(np.mean(c_hat_full[safe])) if safe.any() else 0.0
        c_hat_full = c_hat_full - offset

    base = {
        "area": panel.get("area", AREA), "setting": setting, "period": label,
        "c_hat": (f"1 - G/{panel.get('potential', 'F')}, recalibrated on price > 5"
                  if recalibrate else f"1 - G/{panel.get('potential', 'F')}"),
        "recalibration_offset": offset, "n_qh_period": int(sel.sum()),
        "n_neg_qh": int((price < 0).sum()),
        "n_event_days": int(np.unique(bdate[price < 0]).size),
        "preregistration_commit": PREREG_COMMIT,
    }
    if not (s > 0).any():
        return [{**base, "lam": "ALL", "defined": False, "note": "no exposed quarter-hour"}]

    design = build_design(s, depth, shares, runlen, cohort_ids=ids)
    level = fx.run_levels(design, runlen, s)
    rows = design.rows
    c_hat = c_hat_full[rows]
    comp = compress_rows(design.X, c_hat)
    pf = point_fit(design, c_hat, comp)
    if pf["r"] is None:
        return [{**base, "lam": "ALL", "defined": False,
                 "note": f"point fit failed: {pf['status']}"}]
    eps_info = epsilon_from_bootstrap(design, c_hat, bdate[rows], pf["r"])
    eps = eps_info["eps"]
    rank_s = exposure_rank(s)
    dups = duplicate_groups(s, list(ids), shares, depth)
    exact_cap = sum(gp.capacity_share for gp in dups if gp.is_exact)
    exact_members = "|".join("+".join(gp.members) for gp in dups if gp.is_exact)

    specs = {
        "L1": fx.band_mean(design, price, -20.0, -5.0),
        "L2": fx.band_mean(design, price, -np.inf, -50.0),
        "L3": fx.cohort_mean(design, s, depth, level, L3_COHORT),
        "L4": fx.group_mean(design, s, depth, level, shares, COLLINEAR_PAIR),
        "L5": fx.threshold_to_zero_energy(design, s, depth, level, shares, price, f,
                                          L5_COHORT),
        "L7": fx.cohort_mean(design, s, depth, level, L7_COHORT),
    }
    specs["L6"] = fx.difference(specs["L3"], specs["L4"])

    common = {
        **base, "eps": eps, "rms_point": pf["rms_residual"], "rms_floor": comp.rms_floor,
        "n_rows": design.n_rows, "n_rows_compressed": int(comp.Xu.shape[0]),
        "n_cols": design.n_cols, "n_cohorts": len(ids),
        "n_cohorts_exposed": design.diagnostics["n_cohorts_exposed"],
        "exposure_rank": rank_s.rank, "exposure_rank_full": rank_s.full_rank,
        "exact_collinear_capacity": float(exact_cap),
        "exact_collinear_members": exact_members,
        "run_levels": design.n_run_levels, "run_split_h": design.run_split,
        "n_event_days_bootstrap": eps_info["n_days"],
    }

    out = []
    for name in ("L1", "L2", "L3", "L4", "L5", "L6", "L7"):
        spec = specs[name]
        row = {**common, "lam": name, "defined": bool(spec.get("defined")),
               "n_qh_lam": int(spec.get("n_qh", 0)), "note": spec.get("note", ""),
               "l5_coverage": spec.get("coverage", np.nan),
               "l5_energy_full_gwh": spec.get("energy_if_full_response_gwh", np.nan)}
        if not spec.get("defined"):
            row.update({"lo": np.nan, "hi": np.nan, "width": np.nan, "feasible": False,
                        "in_row_space": None, "perp_fraction": np.nan, "rank_X": None,
                        "status_lo": "", "status_hi": ""})
            out.append(row)
            continue
        iv = identified_set(design, c_hat, spec["lam"], eps, comp)
        rs = in_row_space(design.X, spec["lam"])
        row.update({"lo": iv["lo"], "hi": iv["hi"], "width": iv["width"],
                    "feasible": iv["feasible"], "in_row_space": rs["in_row_space"],
                    "perp_fraction": rs["perp_fraction"], "rank_X": rs["rank"],
                    "status_lo": iv["status_lo"], "status_hi": iv["status_hi"]})
        out.append(row)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    panel = load_panel()
    keep = panel["keep"]
    bdate = panel["bdate"]
    months = np.array([d[:7] for d in bdate])
    present = sorted(set(months[keep]))
    print(f"window {MTU15_FIRST_DELIVERY_DAY}.. : {int(keep.sum())} quarter-hours, "
          f"{len(present)} months with a published market value, "
          f"{panel['n_dropped_non_finite']} dropped for a missing F or G")
    print(f"months: {', '.join(present)}")

    arms: list[tuple[str, np.ndarray, bool]] = [("window", keep, False),
                                                ("window", keep, True)]
    for m in present:
        sel = keep & (months == m)
        if (panel["price"][sel] < 0).any():
            arms.append((m, sel, False))

    head, today = git_head(), date.today().isoformat()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else OUT_DIR / "p3_real.csv"
    fh = writer = None
    try:
        for setting in SETTINGS:
            for label, sel, recal in arms:
                rows = run_arm(panel, setting, sel, label, recal)
                for r in rows:
                    r["git_head"], r["run_date"] = head, today
                if writer is None:
                    fh = open(out_path, "w", newline="", encoding="utf-8")
                    writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
                    writer.writeheader()
                for r in rows:
                    writer.writerow({k: r.get(k) for k in writer.fieldnames})
                fh.flush()
                tag = f"{setting:<5} {label:<8}{'recal' if recal else '     '}"
                w = {r["lam"]: r.get("width") for r in rows}
                print(f"  {tag} exposed={rows[0].get('n_rows')} cols={rows[0].get('n_cols')} "
                      f"rank_s={rows[0].get('exposure_rank')}/{rows[0].get('n_cohorts')} "
                      f"eps={rows[0].get('eps', float('nan')):.4f} | "
                      + " ".join(f"{k}={v:.3f}" for k, v in w.items()
                                 if isinstance(v, float) and np.isfinite(v)), flush=True)
    finally:
        if fh is not None:
            fh.close()
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
