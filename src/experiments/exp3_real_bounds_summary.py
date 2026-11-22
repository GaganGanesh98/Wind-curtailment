"""Q5 summary, written before any Q5 number was read (`docs/Q5_preregistration.md` section 4).

    python -m src.experiments.exp3_real_bounds_summary

Reads `artifacts/exp3_german_application/monthly_bounds_cells.csv`; writes `artifacts/exp3_german_application/monthly_bounds_summary.csv`.

Headline: of all (functional, month) pairs at `main` defined in BOTH arms, the share
NOT informative under Q5-F and informative under Q5-H. Beside it, deciding nothing:
the share informative under each arm, the reverse transition (counted, not netted),
the same at `low` and `high`, the window arm per setting, and eps, floor-to-residual
ratio and median width per arm. Pairs defined in only one arm are excluded and counted.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import polars as pl

from src.method.read_results import load

REPO_ROOT = Path(__file__).resolve().parents[2]
Q5 = REPO_ROOT / "artifacts" / "exp3_german_application"


def _flag(d: pl.DataFrame) -> pl.DataFrame:
    if d["informative"].dtype == pl.String:
        d = d.with_columns(pl.when(pl.col("informative") == "True").then(True)
                           .when(pl.col("informative") == "False").then(False)
                           .otherwise(None).alias("informative"))
    return d


def transitions(d: pl.DataFrame, setting: str, months: bool) -> dict:
    base = d.filter((pl.col("setting") == setting)
                    & (pl.col("c_hat").str.contains("recalibrated").not_()))
    base = base.filter(pl.col("period") != "window") if months else \
        base.filter(pl.col("period") == "window")
    key = ["period", "lam"]
    f = base.filter(pl.col("potential") == "F").select(key + [pl.col("informative").alias("inf_f")])
    h = base.filter(pl.col("potential") == "H").select(key + [pl.col("informative").alias("inf_h")])
    j = f.join(h, on=key, how="full", coalesce=True)
    both = j.filter(pl.col("inf_f").is_not_null() & pl.col("inf_h").is_not_null())
    neither = j.filter(pl.col("inf_f").is_null() & pl.col("inf_h").is_null()).height
    n = both.height
    up = both.filter(~pl.col("inf_f") & pl.col("inf_h")).height
    down = both.filter(pl.col("inf_f") & ~pl.col("inf_h")).height
    return {
        "setting": setting, "scope": "months" if months else "window",
        # Corrected after the first run: the original single count, "one arm only",
        # also held pairs undefined in BOTH arms. The headline denominator is unchanged.
        "n_pairs_both": n, "n_pairs_one_arm_only": j.height - n - neither,
        "n_pairs_neither_arm": neither,
        "n_become_informative": up, "share_become_informative": up / n if n else np.nan,
        "n_reverse": down, "share_reverse": down / n if n else np.nan,
        "share_informative_F": float(both["inf_f"].mean()) if n else np.nan,
        "share_informative_H": float(both["inf_h"].mean()) if n else np.nan,
        "n_informative_both": both.filter(pl.col("inf_f") & pl.col("inf_h")).height,
        "headline": setting == "main" and months,
    }


def per_arm(d: pl.DataFrame) -> list[dict]:
    rows = []
    plain = d.filter(pl.col("c_hat").str.contains("recalibrated").not_())
    for (pot, setting), g in sorted(plain.group_by(["potential", "setting"]),
                                    key=lambda t: t[0]):
        one = g.unique(subset=["period"], keep="first")
        w = g.filter(pl.col("feasible") & (pl.col("lam") != "L5"))["width"].to_numpy().astype(float)
        rows.append({"potential": pot, "setting": setting,
                     "median_eps": float(one["eps"].median()),
                     "median_floor_ratio": float((one["rms_floor"] / one["rms_point"]).median()),
                     "median_width_excl_L5": float(np.nanmedian(w)) if w.size else np.nan})
    return rows


def main() -> None:
    d = load(Q5 / "monthly_bounds_cells.csv")
    for c in ("eps", "rms_floor", "rms_point", "width"):
        d = d.with_columns(pl.col(c).cast(pl.Float64, strict=False))
    d = _flag(d)
    rows = [transitions(d, s, m) for s in ("main", "low", "high") for m in (True, False)]
    arm = per_arm(d)
    out = Q5 / "monthly_bounds_summary.csv"
    fields: list[str] = []
    for r in rows + arm:
        fields += [k for k in r if k not in fields]
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["table"] + fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({"table": "transitions", **r})
        for r in arm:
            w.writerow({"table": "per_arm", **r})
    with pl.Config(tbl_rows=40, tbl_width_chars=220, float_precision=4):
        print(pl.DataFrame(rows))
        print(pl.DataFrame(arm))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
