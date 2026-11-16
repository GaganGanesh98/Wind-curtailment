"""Q6a: day-to-day variation of the curtailed share inside matched cells, real data.

    python -m src.potential.q6a_heterogeneity

Pre-registration `docs/Q6_preregistration.md` (commit `b2f7d95`). Three-area region,
quality-assured H, negative-price quarter-hours, 2025-10-01 to 2026-10-28. Cells are
price band x run-length band. Per cell and event-day, c_d = 1 - sum(G)/sum(H).

Primary: V_between (ddof 1) against V_meas = (1 - c_bar)^2 (exp(s^2) - 1) exp(s^2),
s = 0.066, a day-constant error. Event-day bootstrap within the cell, 5,000 draws,
seed 42, of V_between - V_meas. PRESENT if a strict majority of cells with >= 5
event-days have a lower bound above zero.

Beside it: V_meas with an error independent across quarter-hours (delta method), the
break-even sigma, and the same test on c_d = 1 - (sum(G) + sum(R))/sum(H).
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl

from src.method.exposure import build_clock_features
from src.method.day_bootstrap import BANDS
from src.method.available_power import AGG_NAME, PANEL_PATH, git_head, load_frames

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "artifacts" / "Q6" / "q6a_cells.csv"
PREREG_COMMIT = "b2f7d95"
SIGMA_H = 0.066
MIN_DAYS = 5
N_BOOT, SEED = 5000, 42
RUN_BANDS = (("0.25-1h", 0.0, 1.0), ("1-3h", 1.0, 3.0), ("3-6h", 3.0, 6.0),
             (">6h", 6.0, np.inf))          # (lo, hi]


def kappa(sigma: float) -> float:
    """Var(exp(-e)) for e ~ N(0, sigma^2)."""
    return (np.exp(sigma ** 2) - 1.0) * np.exp(sigma ** 2)


def run_length_hours() -> pl.DataFrame:
    """Run length of the negative-price run containing each quarter-hour, on the
    complete national price series (as `run_p3_real.load_panel` builds it)."""
    obs = (pl.scan_parquet(PANEL_PATH).filter(pl.col("area") == "DE")
           .select(["ts_utc", "price_eur_mwh"]).collect()
           .drop_nulls(["price_eur_mwh"]).sort("ts_utc"))
    clock = build_clock_features(obs["ts_utc"].to_numpy().astype("int64") * 1_000_000,
                                 obs["price_eur_mwh"].to_numpy())
    return obs.select("ts_utc").with_columns(
        pl.Series("run_h", clock.qh_run_length / 4.0))


def label(x: float, bands) -> str | None:
    for name, lo, hi in bands:
        if lo < x <= hi:
            return name
    return None


def price_band(p: float) -> str | None:
    for name, lo, hi in BANDS:
        if (p <= hi if np.isinf(lo) else (lo < p <= hi)) and p < 0:
            return name
    return None


def day_table(g: pl.DataFrame) -> dict:
    """Per event-day sums inside one cell."""
    t = (g.group_by("berlin_date")
          .agg(pl.col("act_onshore_mw").sum().alias("G"), pl.col("hr_mw").sum().alias("H"),
               pl.col("rd_mw").sum().alias("R"),
               (pl.col("act_onshore_mw") ** 2).sum().alias("G2"), pl.len().alias("n"))
          .sort("berlin_date"))
    return {k: t[k].to_numpy().astype(float) for k in ("G", "H", "R", "G2", "n")}


def stats(G, H, R, G2, idx: np.ndarray | None = None, with_r: bool = False) -> tuple:
    if idx is not None:
        G, H, R, G2 = G[idx], H[idx], R[idx], G2[idx]
    num = G + R if with_r else G
    c_d = 1.0 - num / H
    c_bar = 1.0 - num.sum() / H.sum()
    v_b = float(np.var(c_d, ddof=1)) if c_d.size > 1 else np.nan
    v_m = (1.0 - c_bar) ** 2 * kappa(SIGMA_H)
    v_iid = float(np.mean((1.0 - c_bar) ** 2 * SIGMA_H ** 2 * G2 / G ** 2))
    return v_b, v_m, v_iid, c_bar, c_d


def break_even_sigma(v_b: float, c_bar: float) -> float:
    """sigma with (1 - c_bar)^2 kappa(sigma) = v_b; kappa(s) = x^2 - x, x = exp(s^2)."""
    k = v_b / (1.0 - c_bar) ** 2
    x = (1.0 + np.sqrt(1.0 + 4.0 * k)) / 2.0
    return float(np.sqrt(np.log(x)))


def main() -> None:
    agg = load_frames("quality-assured")[AGG_NAME]
    agg = agg.filter((pl.col("price_eur_mwh") < 0)
                     & (pl.col("berlin_date") >= "2025-10-01")
                     & (pl.col("berlin_date") <= "2026-10-28"))
    rl = run_length_hours()
    agg = agg.join(rl, on="ts_utc", how="left")
    if agg["run_h"].null_count():
        raise ValueError(f"{agg['run_h'].null_count()} quarter-hours without a run length")
    agg = agg.with_columns(
        pl.col("price_eur_mwh").map_elements(price_band, return_dtype=pl.String).alias("pband"),
        pl.col("run_h").map_elements(lambda x: label(x, RUN_BANDS),
                                     return_dtype=pl.String).alias("rband"))
    if agg["pband"].null_count() or agg["rband"].null_count():
        raise ValueError("a negative-price quarter-hour fell outside every band")

    rng = np.random.default_rng(SEED)
    head, today = git_head(), date.today().isoformat()
    rows = []
    for pb, _, _ in BANDS:
        for rb, _, _ in RUN_BANDS:
            g = agg.filter((pl.col("pband") == pb) & (pl.col("rband") == rb))
            base = {"price_band": pb, "run_band": rb, "n_qh": g.height}
            if g.height == 0:
                rows.append({**base, "n_event_days": 0, "testable": False})
                continue
            t = day_table(g)
            nd = t["G"].size
            for variant, with_r in (("G/H", False), ("(G+R)/H", True)):
                v_b, v_m, v_iid, c_bar, c_d = stats(t["G"], t["H"], t["R"], t["G2"],
                                                    with_r=with_r)
                row = {**base, "variant": variant, "primary": not with_r,
                       "n_event_days": nd, "testable": nd >= MIN_DAYS,
                       "c_bar": c_bar, "c_d_min": float(c_d.min()), "c_d_max": float(c_d.max()),
                       "v_between": v_b, "v_meas": v_m, "v_meas_iid": v_iid,
                       "excess": v_b - v_m if np.isfinite(v_b) else np.nan,
                       "ratio_between_over_meas": v_b / v_m if np.isfinite(v_b) else np.nan,
                       "break_even_sigma": (break_even_sigma(v_b, c_bar)
                                            if np.isfinite(v_b) else np.nan)}
                if nd >= 2:
                    draws = rng.integers(0, nd, size=(N_BOOT, nd))
                    ex = np.empty(N_BOOT)
                    for i in range(N_BOOT):
                        b, m, _, _, _ = stats(t["G"], t["H"], t["R"], t["G2"], draws[i], with_r)
                        ex[i] = b - m
                    lo, hi = np.nanpercentile(ex, [2.5, 97.5])
                    row.update({"excess_ci_lo": float(lo), "excess_ci_hi": float(hi),
                                "heterogeneous": bool(lo > 0)})
                rows.append(row)

    for variant in ("G/H", "(G+R)/H"):
        test = [r for r in rows if r.get("variant") == variant and r.get("testable")]
        k = sum(bool(r.get("heterogeneous")) for r in test)
        verdict = ("NOT TESTABLE" if not test else
                   "PRESENT" if k > len(test) / 2 else "NOT FOUND")
        rows.append({"price_band": "ALL", "run_band": "ALL", "variant": variant,
                     "primary": variant == "G/H", "verdict": verdict,
                     "n_testable_cells": len(test), "n_heterogeneous_cells": k})
        print(f"{variant}: {k} of {len(test)} testable cells heterogeneous -> {verdict}")

    for r in rows:
        r.update({"sigma_h": SIGMA_H, "n_boot": N_BOOT, "seed": SEED,
                  "region": AGG_NAME, "preregistration_commit": PREREG_COMMIT,
                  "git_head": head, "run_date": today})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for r in rows:
        fields += [k for k in r if k not in fields]
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    with pl.Config(tbl_rows=60, tbl_width_chars=260, float_precision=4):
        print(pl.DataFrame([r for r in rows if r.get("variant") == "G/H" and "v_between" in r])
              .select(["price_band", "run_band", "n_qh", "n_event_days", "c_bar", "v_between",
                       "v_meas", "v_meas_iid", "excess_ci_lo", "excess_ci_hi",
                       "break_even_sigma", "heterogeneous"]))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
