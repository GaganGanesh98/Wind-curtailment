"""Q2 summary: the bias dial and the crossed grid, as `docs/Q0_preregistration.md` §4 asks.

    python -m src.experiments.exp2_bias_dial_summary

Written on 16 November 2026 while the Q2 runs were in progress and before any Q2 number
was read. It applies Q1's reduction (`summarise_q1.by_level`) unchanged to Q2's rows,
grouped by (dial, sigma, bias), and adds the one count Q1 did not need: how often an
interval is **informative and misses the truth** -- a narrow interval in the wrong place,
the failure a bias can cause and a variance cannot.

Reads `artifacts/Q2/q2a_bias_dial.csv` (sigma = 0, five biases) and
`artifacts/Q2/q2b_crossed.csv` (sigma in {0, 0.066, 0.18} x b in {-0.10, 0, +0.10});
writes beside them:

  q2_summary_by_level.csv   per (dial, sigma, b, functional): coverage, widths, share
                            informative, informative-and-missed
  q2_coverage_by_level.csv  per (dial, sigma, b): the coverage guard, all functionals

Hard rule 4, as in Q1: at a level whose coverage of the known truth is below 95%, the
bounds are broken there; widths and the informative *share* are withheld
(`widths_reported = False`). The informative and informative-and-missed **counts** are
still written, because they are what shows how the bounds broke.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import polars as pl

from src.method.read_results import load

REPO_ROOT = Path(__file__).resolve().parents[2]
Q2 = REPO_ROOT / "artifacts" / "Q2"
COVERAGE_FLOOR = 0.95
FUNCTIONALS = ("L1", "L2", "L3", "L4", "L5", "L6", "L7")
FILES = {"q2a": "q2a_bias_dial.csv", "q2b": "q2b_crossed.csv"}


def _load(name: str) -> pl.DataFrame:
    d = load(Q2 / FILES[name])
    for c in ("sigma", "mu", "width_over_max", "logical_max_width"):
        if c in d.columns:
            d = d.with_columns(pl.col(c).cast(pl.Float64, strict=False))
    if d["informative"].dtype == pl.String:
        d = d.with_columns(pl.when(pl.col("informative") == "True").then(True)
                           .when(pl.col("informative") == "False").then(False)
                           .otherwise(None).alias("informative"))
    return d.with_columns(pl.lit(name).alias("dial"))


def by_level(d: pl.DataFrame) -> tuple[list[dict], list[dict]]:
    rows, cov_rows = [], []
    for (dial, sigma, mu), g in sorted(d.group_by(["dial", "sigma", "mu"]),
                                       key=lambda t: t[0]):
        scored = g.filter(pl.col("cov").is_not_null())
        coverage = float(scored["cov"].mean()) if scored.height else float("nan")
        ok = bool(np.isfinite(coverage) and coverage >= COVERAGE_FLOOR)
        cov_rows.append({"dial": dial, "sigma": sigma, "b": mu, "n_scored": scored.height,
                         "n_covered": int(scored["cov"].sum()), "level_coverage": coverage,
                         "level_coverage_ok": ok,
                         "n_informative_and_missed": int(scored.filter(
                             pl.col("informative").fill_null(False) & ~pl.col("cov")).height)})
        for lam in FUNCTIONALS:
            q = g.filter((pl.col("lam") == lam) & pl.col("defined"))
            qs = q.filter(pl.col("cov").is_not_null())
            w = q.filter(pl.col("feasible"))["width"].to_numpy().astype(float)
            w = w[np.isfinite(w)]
            inf = q.filter(pl.col("informative").is_not_null())
            missed = qs.filter(pl.col("informative").fill_null(False) & ~pl.col("cov"))
            rows.append({
                "dial": dial, "sigma": sigma, "b": mu, "lam": lam, "n_cells": q.height,
                "level_coverage": coverage, "level_coverage_ok": ok,
                "lam_n_scored": qs.height, "lam_n_covered": int(qs["cov"].sum()),
                "lam_coverage": float(qs["cov"].mean()) if qs.height else float("nan"),
                "widths_reported": ok,
                "median_width": float(np.median(w)) if ok and w.size else float("nan"),
                "q25_width": float(np.percentile(w, 25)) if ok and w.size else float("nan"),
                "q75_width": float(np.percentile(w, 75)) if ok and w.size else float("nan"),
                "share_informative": (float(inf["informative"].mean())
                                      if ok and inf.height else float("nan")),
                "n_informative": int(inf["informative"].sum()) if inf.height else 0,
                "n_informative_and_missed": missed.height,
            })
    return rows, cov_rows


def _write(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    d = pl.concat([_load(n) for n in FILES], how="diagonal_relaxed")
    rows, cov_rows = by_level(d)
    _write(Q2 / "q2_summary_by_level.csv", rows)
    _write(Q2 / "q2_coverage_by_level.csv", cov_rows)
    for r in cov_rows:
        flag = "" if r["level_coverage_ok"] else "   BELOW 95%: widths withheld"
        print(f"{r['dial']}  sigma {r['sigma']:.3f}  b {r['b']:+.3f}  coverage "
              f"{r['n_covered']}/{r['n_scored']} = {r['level_coverage']:.3f}  "
              f"informative-and-missed {r['n_informative_and_missed']}{flag}")
    print(f"wrote {Q2 / 'q2_summary_by_level.csv'}\nwrote {Q2 / 'q2_coverage_by_level.csv'}")


if __name__ == "__main__":
    main()
