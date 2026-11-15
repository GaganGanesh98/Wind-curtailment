"""Q1 summary: the variance dial, reduced to what `docs/Q0_preregistration.md` asks for.

    python -m src.identification.summarise_q1

Written before any Q1 number was read, so the reduction cannot be shaped by them.
Reads `artifacts/Q1/q1_variance_dial.csv`; writes, beside it:

  q1_summary_by_level.csv   per (noise kind, sigma, functional): coverage, median and
                            interquartile width, share informative, pooled-response
                            rejection rate in `split` cells, floor-to-residual ratio
  q1_headline.csv           sigma*, the secondary statistic per functional, the
                            coverage guard per level, and the AR(1) comparison

The rules are Q0's, applied mechanically:

* **Coverage is the guard rail (hard rule 4).** A noise level whose coverage of the
  known truth is below 95% has broken bounds, and its widths are withheld here --
  `widths_reported = False` -- not merely flagged.
* **Informative** is the runner's own column: width below 0.25 of the functional's
  logically maximal width (Q0 section 5).
* **sigma\\*** is the largest i.i.d. grid level at which L1 is informative in at least
  half of the cells. If L1 is informative at no level, including 0, it is undefined,
  and Q0 section 3's dead-end rule applies.
* **The secondary statistic** -- the largest sigma at which the pooled-response
  rejection rate in `split` cells stays above half -- is reported **per functional**,
  because Q0 section 5 does not name the functional it is computed on. No single number
  is claimed for it.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import polars as pl

from src.identification.summarise_p3 import load

REPO_ROOT = Path(__file__).resolve().parents[2]
Q1 = REPO_ROOT / "artifacts" / "Q1"
COVERAGE_FLOOR = 0.95
HALF = 0.5
FUNCTIONALS = ("L1", "L2", "L3", "L4", "L5", "L6", "L7")


def _load() -> pl.DataFrame:
    d = load(Q1 / "q1_variance_dial.csv")
    for c in ("sigma", "mu", "rho", "width_over_max", "logical_max_width"):
        if c in d.columns:
            d = d.with_columns(pl.col(c).cast(pl.Float64, strict=False))
    if d["informative"].dtype == pl.String:
        d = d.with_columns(pl.when(pl.col("informative") == "True").then(True)
                           .when(pl.col("informative") == "False").then(False)
                           .otherwise(None).alias("informative"))
    return d.with_columns((pl.col("rms_floor") / pl.col("rms_point")).alias("floor_ratio"))


def by_level(d: pl.DataFrame) -> list[dict]:
    rows = []
    for (kind, sigma), g in sorted(d.group_by(["noise", "sigma"]), key=lambda t: (t[0][0], t[0][1])):
        scored = g.filter(pl.col("cov").is_not_null())
        coverage = float(scored["cov"].mean()) if scored.height else float("nan")
        ok = bool(np.isfinite(coverage) and coverage >= COVERAGE_FLOOR)
        for lam in FUNCTIONALS:
            q = g.filter((pl.col("lam") == lam) & pl.col("defined"))
            qs = q.filter(pl.col("cov").is_not_null())
            w = q.filter(pl.col("feasible"))["width"].to_numpy().astype(float)
            w = w[np.isfinite(w)]
            split = q.filter((pl.col("hetero") == "split")
                             & pl.col("pooled_err_exceeds_width").is_not_null())
            inf = q.filter(pl.col("informative").is_not_null())
            rows.append({
                "noise": kind, "sigma": sigma, "lam": lam,
                "n_cells": q.height,
                "level_coverage": coverage, "level_coverage_ok": ok,
                "lam_coverage": float(qs["cov"].mean()) if qs.height else float("nan"),
                "widths_reported": ok,
                "median_width": float(np.median(w)) if ok and w.size else float("nan"),
                "q25_width": float(np.percentile(w, 25)) if ok and w.size else float("nan"),
                "q75_width": float(np.percentile(w, 75)) if ok and w.size else float("nan"),
                "share_informative": (float(inf["informative"].mean())
                                      if ok and inf.height else float("nan")),
                "n_informative": int(inf["informative"].sum()) if inf.height else 0,
                "pooled_rejection_split": (float(split["pooled_err_exceeds_width"].mean())
                                           if split.height else float("nan")),
                "n_split_scored": split.height,
                "median_floor_ratio": float(q["floor_ratio"].median()) if q.height else float("nan"),
                "median_eps": float(q["eps"].median()) if q.height else float("nan"),
            })
    return rows


def headline(rows: list[dict]) -> list[dict]:
    iid = [r for r in rows if r["noise"] == "iid"]
    out = []

    l1 = sorted((r for r in iid if r["lam"] == "L1"), key=lambda r: r["sigma"])
    passing = [r["sigma"] for r in l1
               if r["widths_reported"] and np.isfinite(r["share_informative"])
               and r["share_informative"] >= HALF]
    sigma_star = max(passing) if passing else float("nan")
    contiguous = bool(passing) and passing == [r["sigma"] for r in l1][:len(passing)]
    out.append({"statistic": "sigma_star", "lam": "L1", "value": sigma_star,
                "note": ("largest iid level with L1 informative in >= half the cells"
                         + ("" if contiguous or not passing else
                            "; NOTE the passing levels are not a contiguous run from 0"))})

    for lam in FUNCTIONALS:
        ls = sorted((r for r in iid if r["lam"] == lam), key=lambda r: r["sigma"])
        ok = [r["sigma"] for r in ls if np.isfinite(r["pooled_rejection_split"])
              and r["pooled_rejection_split"] > HALF]
        out.append({"statistic": "pooled_rejection_above_half_max_sigma", "lam": lam,
                    "value": max(ok) if ok else float("nan"),
                    "note": "secondary statistic, per functional (Q0 section 5 names none)"})

    for r in (r for r in iid if r["lam"] == "L1"):
        out.append({"statistic": "level_coverage", "lam": "ALL", "sigma": r["sigma"],
                    "value": r["level_coverage"],
                    "note": "guard rail; below 0.95 the level's widths are withheld"})

    ar = {r["lam"]: r for r in rows if r["noise"] == "ar1"}
    iid18 = {r["lam"]: r for r in iid if abs(r["sigma"] - 0.18) < 1e-9}
    for lam in FUNCTIONALS:
        if lam in ar and lam in iid18:
            a, b = ar[lam]["median_width"], iid18[lam]["median_width"]
            out.append({"statistic": "ar1_minus_iid_median_width_at_0.18", "lam": lam,
                        "value": a - b if np.isfinite(a + b) else float("nan"),
                        "note": "Q0 predicted correlated noise widens LESS (negative)"})
    return out


def _write(path: Path, rows: list[dict]) -> None:
    fields: list[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def main() -> None:
    d = _load()
    cells = d.select(["hetero", "rate", "gamma", "r_shape", "seed"]).unique().height
    print(f"{d.height} rows, {cells} cells, levels "
          f"{sorted(set(zip(d['noise'].to_list(), d['sigma'].to_list())))}")
    rows = by_level(d)
    head = headline(rows)
    _write(Q1 / "q1_summary_by_level.csv", rows)
    _write(Q1 / "q1_headline.csv", head)
    with pl.Config(tbl_rows=80, tbl_width_chars=200, float_precision=4):
        print(pl.DataFrame(rows).select(["noise", "sigma", "lam", "level_coverage",
                                         "median_width", "q25_width", "q75_width",
                                         "share_informative", "pooled_rejection_split",
                                         "median_floor_ratio"]))
        print(pl.DataFrame(head))
    print(f"wrote {Q1 / 'q1_summary_by_level.csv'} and {Q1 / 'q1_headline.csv'}")


if __name__ == "__main__":
    main()
