"""Experiment 4, step 4 (reduced): a descriptive estimate of H's bias at negative prices.

    python -m src.method.learned_potential.bias_budget      # writes bias_budget.csv

S2 failed (docs/12b), so no budget B̂ is defined and no reading is classified against these
numbers (docs/12b, "Interpretation fixed before step 4"). As pre-registered and amended:

  b̂_H     mean over Experiment 3's negative-price quarter-hours of log(H / Â), Â = L2's
           out-of-fold median (the model the selection rule chose)
  β̂_Â     mean over the look-alike quarter-hours of log(G / Â), L2's own bias where G is truth
  corrected = b̂_H − β̂_Â, an estimate of the mean of log(H / A) at negative prices; positive
           means H above available power

Units: each area's rows, the pooled area rows, and the three-area aggregate (log of sums).
Arms: trimmed (primary, Amendment 1 C2: target quarter-hours with out-of-fold p <= 0.99; at the
aggregate, mean p over the areas) and untrimmed (sensitivity, C3: relies on extrapolation).
Intervals: day-block bootstrap, 5,000 draws each for the target and the look-alike set, drawn
independently; the corrected interval comes from the difference of the draws.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from src.method.day_bootstrap import bootstrap_day_sums, ci95
from src.method.learned_potential import config as cfg
from src.method.learned_potential.data import ART, load_rows

OUT = ART / "bias_budget.csv"
MODEL = "L2"
STATUS = "descriptive, S2 failed"


def _draws(x: np.ndarray, days: np.ndarray, seed: int) -> tuple[float, np.ndarray, int]:
    uniq, idx = np.unique(days, return_inverse=True)
    S = np.zeros((uniq.size, 2))
    np.add.at(S[:, 0], idx, 1.0)
    np.add.at(S[:, 1], idx, x)
    b = bootstrap_day_sums(S, n_boot=cfg.N_BOOT, seed=seed)
    return float(S[:, 1].sum() / S[:, 0].sum()), b[:, 1] / b[:, 0], int(uniq.size)


def _rows() -> pl.DataFrame:
    a = pl.read_parquet(ART / f"oof_{MODEL}.parquet").select(["area", "ts_utc", "a_hat_mw", "p_domain", "overlap_ok"])
    r = load_rows().filter((pl.col("berlin_date") >= cfg.EVAL_WINDOW[0]) & (pl.col("berlin_date") <= cfg.EVAL_WINDOW[1]))
    s = pl.read_parquet(ART / "domain_scores.parquet").select(["area", "ts_utc", "lookalike", "lookalike_aggregate"])
    return r.join(s, on=["area", "ts_utc"], how="left").join(a, on=["area", "ts_utc"], how="inner")


def estimate() -> pl.DataFrame:
    d = _rows()
    out = []
    target_all = d.filter(pl.col("target"))
    for unit in (*cfg.AREAS, "pooled area rows", "three-area aggregate"):
        if unit == "three-area aggregate":
            agg = (target_all.group_by(["ts_utc", "berlin_date"])
                   .agg(pl.col("h").sum(), pl.col("a_hat_mw").sum(), pl.col("p_domain").mean(), pl.len().alias("n"))
                   .filter(pl.col("n") == len(cfg.AREAS)))
            la = (d.filter(pl.col("lookalike_aggregate")).group_by(["ts_utc", "berlin_date"])
                  .agg(pl.col("g").sum(), pl.col("a_hat_mw").sum(), pl.len().alias("n"))
                  .filter(pl.col("n") == len(cfg.AREAS)))
            tgt = {"untrimmed": agg, "trimmed": agg.filter(pl.col("p_domain") <= cfg.OVERLAP_TRIM_P)}
            n_all = agg.height
        else:
            t = target_all if unit == "pooled area rows" else target_all.filter(pl.col("area") == unit)
            la = d.filter(pl.col("lookalike"))
            if unit != "pooled area rows":
                la = la.filter(pl.col("area") == unit)
            tgt = {"untrimmed": t, "trimmed": t.filter(pl.col("overlap_ok"))}
            n_all = t.height
        la_x = np.log(la["g"].to_numpy() / la["a_hat_mw"].to_numpy())
        beta, beta_d, la_days = _draws(la_x, la["berlin_date"].to_numpy().astype(str), cfg.SEED + 1)
        for arm in ("trimmed", "untrimmed"):
            q = tgt[arm]
            x = np.log(q["h"].to_numpy() / q["a_hat_mw"].to_numpy())
            b, b_d, days = _draws(x, q["berlin_date"].to_numpy().astype(str), cfg.SEED)
            corr_d = b_d - beta_d
            out.append({
                "unit": unit, "arm": "trimmed (primary)" if arm == "trimmed" else "untrimmed (sensitivity, extrapolation)",
                "model": MODEL, "n_target_qh": q.height, "n_target_days": days,
                "share_of_target_kept": q.height / n_all,
                "b_hat_H": b, "b_hat_H_lo": ci95(b_d)[0], "b_hat_H_hi": ci95(b_d)[1],
                "beta_A_lookalike": beta, "beta_lo": ci95(beta_d)[0], "beta_hi": ci95(beta_d)[1],
                "n_lookalike_qh": la.height, "n_lookalike_days": la_days,
                "corrected": b - beta, "corrected_lo": ci95(corr_d)[0], "corrected_hi": ci95(corr_d)[1],
                "status": STATUS})
    return pl.DataFrame(out)


def main() -> None:
    import sys
    if "--arm" in sys.argv[1:]:
        r = arm_readings()
        r.write_csv(ARM_READINGS)
        print(r)
        print(f"wrote {ARM_READINGS}")
        return
    e = estimate()
    e.write_csv(OUT)
    pl.Config.set_tbl_rows(20)
    pl.Config.set_tbl_width_chars(220)
    print(e.select(["unit", "arm", "n_target_qh", "share_of_target_kept", "b_hat_H", "beta_A_lookalike",
                    "corrected", "corrected_lo", "corrected_hi"]))
    print(f"wrote {OUT}")



# ------------------------------------------------- Experiment 3 robustness arm (step 4)

ARM_CELLS = ART / "exp3_with_learned_potential.csv"
ARM_READINGS = ART / "exp3_arm_readings.csv"


def arm_readings() -> pl.DataFrame:
    """Each V0 reading under H (the committed headline cells) and under L2's Â (the arm), with
    the pre-registered agreement rule: same verdict at B = 0 and breakdown moving by less than
    AGREE_BREAKDOWN_TOLERANCE. Descriptive: Â failed S2 (docs/12b)."""
    from src.method.bias_robust import V2_BMAX
    from src.method.bias_robust_summary import V2_RULES
    E3 = ART.parent / "exp3_german_application" / "bias_robust_full_window_cells.csv"
    budgets = [round(i * 0.01, 2) for i in range(int(round(V2_BMAX / 0.01)) + 1)]

    def load(path):
        return (pl.read_csv(path, infer_schema_length=0)
                .with_columns(*(pl.col(c).cast(pl.Float64) for c in ("b", "lo", "hi")),
                              (pl.col("feasible") == "True").alias("feasible"))
                .with_columns(pl.col("b").round(2)))

    def hull(c, lam, B):
        q = c.filter((pl.col("lam") == lam) & (pl.col("b").abs() <= B + 1e-9) & pl.col("feasible"))
        return float(q["lo"].min()), float(q["hi"].max())

    cells = {"H (headline)": load(E3), "learned (L2)": load(ARM_CELLS)}
    out = []
    for lam, (reading, holds) in V2_RULES.items():
        res = {}
        for name, c in cells.items():
            lo, hi = hull(c, lam, 0.0)
            brk = next((B for B in budgets if not holds(*hull(c, lam, B))), None)
            res[name] = (lo, hi, bool(holds(lo, hi)), brk)
        h, a = res["H (headline)"], res["learned (L2)"]
        bh = 0.16 if h[3] is None else h[3]
        ba = 0.16 if a[3] is None else a[3]
        agree = (h[2] == a[2]) and abs(ba - bh) < cfg.AGREE_BREAKDOWN_TOLERANCE - 1e-9
        out.append({"lam": lam, "reading": reading,
                    "H_lo_B0": h[0], "H_hi_B0": h[1], "H_holds_B0": h[2],
                    "H_breakdown": "> 0.15" if h[3] is None else f"{h[3]:.2f}",
                    "A_lo_B0": a[0], "A_hi_B0": a[1], "A_holds_B0": a[2],
                    "A_breakdown": "> 0.15" if a[3] is None else f"{a[3]:.2f}",
                    "agree": agree, "status": STATUS})
    return pl.DataFrame(out)



if __name__ == "__main__":
    main()
