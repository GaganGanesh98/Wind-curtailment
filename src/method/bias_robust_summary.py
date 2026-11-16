"""Phase V summary: hulls S_B and V0's criteria (`docs/V0_preregistration.md`, `3277ea6`).

    python -m src.method.bias_robust_summary

Reads the raw rows of `run_v_bias_robust` and writes, in `artifacts/exp2_bias_robustness_validation/` (synthetic) and `artifacts/exp3_german_application/` (real):

  bias_robust_coverage.csv  per (B, b*): coverage of S_B over the scored functionals, and whether
                       V0's criterion applies there (B >= |b*|) and passes
  bias_robust_by_functional.csv per (B, b*, functional): coverage, median width, informative count
  bias_robust_width_cost.csv    per (B, functional) at b* = 0: median over cells of
                       width(S_B) / width(S_0)
  bias_robust_full_window_intervals.csv  per (functional, B): S_B on the real full window with H
  breakdown_points.csv  per functional: the smallest B at which its reading breaks

Hull, coverage slack and the informative rule are V0's: S_B = [min lo, max hi] over the
feasible b in G_B; covered when truth lies in [lo - slack, hi + slack] with P3's
slack = 1e-6 * max(1, |truth|); informative when width < 0.25 of the logical maximum.
Written before any V1 number was read; V2's raw rows had been printed by the runner.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import polars as pl

from src.method.synthetic_scoring import TOL_COVER
from src.method.lambda5_truth import true_l5
from src.method.potential_error import BIAS_GRID
from src.method.bias_robust import V2_BMAX, grid, v1_sums

REPO_ROOT = Path(__file__).resolve().parents[2]
V = REPO_ROOT / "artifacts" / "exp2_bias_robustness_validation"          # synthetic (exp 2)
V_REAL = REPO_ROOT / "artifacts" / "exp3_german_application"     # real data (exp 3)
V1_B = (0.0, 0.05, 0.10)
V1_SCORED = ("L1", "L2", "L3", "L4", "L6", "L7")
COVERAGE_FLOOR = 0.95
CELL = ["hetero", "rate", "gamma", "r_shape", "seed"]
N_CELLS = 54

#: V0 section 3: functional -> (reading, test that the reading still HOLDS on S_B)
V2_RULES = {
    "L1": ("informative", lambda lo, hi: (hi - lo) < 0.25),
    "L2": ("lower bound at least 0.5", lambda lo, hi: lo >= 0.5),
    "L3": ("upper bound at most 0.75", lambda lo, hi: hi <= 0.75),
    "L6": ("upper bound at most 0.5", lambda lo, hi: hi <= 0.5),
}


def _num(d: pl.DataFrame, cols) -> pl.DataFrame:
    return d.with_columns(*(pl.col(c).cast(pl.Float64, strict=False) for c in cols if c in d.columns))


def _write(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def v1_hulls() -> pl.DataFrame:
    raw = pl.concat([pl.read_csv(p, infer_schema_length=0)
                     for p in sorted(V.glob("bias_robust_cells_shard*of*.csv"))])
    raw = _num(raw, ("rate", "gamma", "seed", "s", "lo", "hi", "width", "truth",
                     "logical_max_width"))
    raw = raw.with_columns((pl.col("feasible") == "True").alias("feasible"),
                           (pl.col("defined") == "True").alias("defined"),
                           pl.col("s").round(3))
    done = raw.group_by(CELL).agg(pl.col("s").n_unique().alias("k"))
    if done.height != N_CELLS or not (done["k"] == len(v1_sums())).all():
        raise RuntimeError(f"V1 incomplete: {done.height} of {N_CELLS} cells started; "
                           "never summarise a partial run")
    # Erratum (docs/ERRATUM_lambda5.md): lambda-5's stored truth came from the scored
    # potential; use the true-potential truth (Arm O's, same cell) instead.
    raw = raw.join(true_l5(), on=CELL, how="left").with_columns(
        pl.when(pl.col("lam") == "L5").then(pl.col("_l5_true")).otherwise(pl.col("truth"))
          .alias("truth")).drop("_l5_true")
    truths = raw.filter(pl.col("defined")).group_by(CELL + ["lam"]).agg(
        pl.col("truth").n_unique().alias("k"))
    assert (truths["k"] == 1).all(), "a functional's truth moved with the potential"
    out = []
    for bstar in BIAS_GRID:
        for B in V1_B:
            sums = [round(bstar + b, 3) for b in grid(B)]
            sel = raw.filter(pl.col("s").is_in(sums) & pl.col("defined"))
            h = (sel.group_by(CELL + ["lam"])
                    .agg(pl.col("lo").filter(pl.col("feasible")).min().alias("lo"),
                         pl.col("hi").filter(pl.col("feasible")).max().alias("hi"),
                         pl.col("feasible").sum().alias("n_feasible"),
                         pl.len().alias("n_b"),
                         pl.col("truth").first().alias("truth"),
                         pl.col("logical_max_width").first().alias("logical_max_width")))
            out.append(h.with_columns(pl.lit(bstar).alias("b_true"), pl.lit(B).alias("B")))
    h = pl.concat(out).with_columns((pl.col("hi") - pl.col("lo")).alias("width"))
    slack = TOL_COVER * pl.max_horizontal(pl.lit(1.0), pl.col("truth").abs())
    return h.with_columns(
        pl.when(pl.col("n_feasible") > 0)
          .then((pl.col("truth") >= pl.col("lo") - slack) & (pl.col("truth") <= pl.col("hi") + slack))
          .otherwise(None).alias("cov"),
        (pl.col("width") < 0.25 * pl.col("logical_max_width")).alias("informative"))


def v1_tables(h: pl.DataFrame) -> tuple[list[dict], list[dict], list[dict]]:
    cov_rows, fun_rows, cost_rows = [], [], []
    for bstar in BIAS_GRID:
        for B in V1_B:
            g = h.filter((pl.col("b_true") == bstar) & (pl.col("B") == B))
            sc = g.filter(pl.col("lam").is_in(V1_SCORED) & pl.col("cov").is_not_null())
            cov = float(sc["cov"].mean())
            applies = B >= abs(bstar) - 1e-12
            cov_rows.append({"B": B, "b_true": bstar, "n_scored": sc.height,
                             "n_covered": int(sc["cov"].sum()), "coverage": cov,
                             "criterion_applies": applies,
                             "passes": (cov >= COVERAGE_FLOOR) if applies else None})
            for lam in ("L1", "L2", "L3", "L4", "L5", "L6", "L7"):
                q = g.filter(pl.col("lam") == lam)
                qs = q.filter(pl.col("cov").is_not_null())
                fun_rows.append({"B": B, "b_true": bstar, "lam": lam, "n_cells": q.height,
                                 "scored": lam in V1_SCORED,
                                 "n_covered": int(qs["cov"].sum()), "n_scored": qs.height,
                                 "median_width": float(q["width"].median()),
                                 "n_informative": int(q["informative"].fill_null(False).sum())})
    base = h.filter((pl.col("b_true") == 0.0) & (pl.col("B") == 0.0)).select(
        CELL + ["lam", pl.col("width").alias("w0")])
    for B in V1_B:
        j = h.filter((pl.col("b_true") == 0.0) & (pl.col("B") == B)).join(base, on=CELL + ["lam"])
        for lam in ("L1", "L2", "L3", "L4", "L5", "L6", "L7"):
            q = j.filter((pl.col("lam") == lam) & (pl.col("w0") > 0))
            cost_rows.append({"B": B, "lam": lam, "n_cells": q.height,
                              "median_width_ratio": float((q["width"] / q["w0"]).median()),
                              "median_width": float(j.filter(pl.col("lam") == lam)["width"].median())})
    return cov_rows, fun_rows, cost_rows


def v2_tables() -> tuple[list[dict], list[dict]]:
    raw = _num(pl.read_csv(V_REAL / "bias_robust_full_window_cells.csv", infer_schema_length=0),
               ("b", "lo", "hi", "width")).with_columns(pl.col("b").round(2),
                                                       (pl.col("feasible") == "True").alias("feasible"))
    budgets = [round(i * 0.01, 2) for i in range(int(round(V2_BMAX / 0.01)) + 1)]
    iv_rows, bd_rows = [], []
    for lam, (reading, holds) in V2_RULES.items():
        first_break = None
        for B in budgets:
            q = raw.filter((pl.col("lam") == lam) & (pl.col("b").abs() <= B + 1e-9)
                           & pl.col("feasible"))
            lo, hi = float(q["lo"].min()), float(q["hi"].max())
            ok = bool(holds(lo, hi))
            iv_rows.append({"lam": lam, "B": B, "lo": lo, "hi": hi, "width": hi - lo,
                            "n_feasible": q.height, "reading_holds": ok})
            if not ok and first_break is None:
                first_break = B
        at = {r["B"]: r for r in iv_rows if r["lam"] == lam}
        bd_rows.append({"lam": lam, "reading": reading,
                        "holds_at_B0": at[0.0]["reading_holds"],
                        "breakdown_B": first_break if first_break is not None else "> 0.15",
                        "lo_B0": at[0.0]["lo"], "hi_B0": at[0.0]["hi"],
                        "lo_at_break": at[first_break]["lo"] if first_break is not None else None,
                        "hi_at_break": at[first_break]["hi"] if first_break is not None else None,
                        "lo_B015": at[V2_BMAX]["lo"], "hi_B015": at[V2_BMAX]["hi"]})
    return iv_rows, bd_rows


def main() -> None:
    iv, bd = v2_tables()
    _write(V_REAL / "bias_robust_full_window_intervals.csv", iv)
    _write(V_REAL / "breakdown_points.csv", bd)
    for r in bd:
        print(f"V2 {r['lam']}: {r['reading']:<26} holds at 0: {r['holds_at_B0']}  "
              f"breakdown B = {r['breakdown_B']}")
    if len(list(V.glob("bias_robust_cells_shard*of*.csv"))) == 4:
        cov, fun, cost = v1_tables(v1_hulls())
        _write(V / "bias_robust_coverage.csv", cov)
        _write(V / "bias_robust_by_functional.csv", fun)
        _write(V / "bias_robust_width_cost.csv", cost)
        for r in cov:
            flag = "" if not r["criterion_applies"] else ("  PASS" if r["passes"] else "  FAIL")
            print(f"V1 B {r['B']:.2f} b* {r['b_true']:+.3f}: {r['n_covered']}/{r['n_scored']} "
                  f"= {r['coverage']:.3f}{flag}")


if __name__ == "__main__":
    main()
