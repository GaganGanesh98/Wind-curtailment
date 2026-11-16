"""Erratum: lambda-5's truth in stored synthetic rows, corrected (`docs/ERRATUM_lambda5.md`).

Until 16 November 2026 `run_p3_synthetic.score_cell` computed lambda-5's TRUE counterfactual
energy from the potential handed to the bounds -- the estimate -- instead of the generator's
true potential. Every other functional's truth was already the generator's. The scorer is now
fixed; this module corrects the rows that were stored before the fix, without refitting:

* the corrected truth of a cell is P3 Arm O's lambda-5 truth for the same cell, because Arm O
  passed the true potential and the cell (generator, design rows, cohorts) is identical in
  every synthetic arm;
* `covered` and `covered_one_sided` are recomputed from the stored interval with P3's rule
  (slack = 1e-6 * max(1, |truth|)); rows whose coverage was undefined stay undefined.

Raw run outputs are left exactly as written; the correction is applied when they are read
(`summarise_p3.load`, `summarise_v`).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
ARM_O = REPO_ROOT / "artifacts" / "exp1_known_truth_validation" / "exact_potential_cells.csv"
CELL = ["hetero", "rate", "gamma", "r_shape", "seed"]
TOL_COVER = 1e-6                                  # run_p3_synthetic.TOL_COVER


@lru_cache(maxsize=1)
def true_l5() -> pl.DataFrame:
    """Arm O's lambda-5 truth per cell: the truth computed from the true potential."""
    d = pl.read_csv(ARM_O, infer_schema_length=0).filter(pl.col("lam") == "L5")
    return d.select(*(pl.col(c).cast(pl.Float64) if c in ("rate", "gamma", "seed") else pl.col(c)
                      for c in CELL),
                    pl.col("truth").cast(pl.Float64).alias("_l5_true"))


def correct_l5(d: pl.DataFrame) -> pl.DataFrame:
    """Replace stored lambda-5 truths by the true-potential truth and re-score coverage.

    Expects `load`'s dtypes (numeric rate/gamma/seed/lo/hi/truth, boolean covered). A frame
    with no synthetic cells or no lambda-5 rows is returned unchanged.
    """
    if not set(CELL + ["lam", "truth", "lo", "hi"]).issubset(d.columns) \
            or d.filter(pl.col("lam") == "L5").height == 0:
        return d
    j = d.join(true_l5(), on=CELL, how="left")
    if j.select(((pl.col("lam") == "L5") & pl.col("_l5_true").is_null()).sum()).item():
        raise ValueError("a lambda-5 row has no Arm O cell to take its true truth from")
    is5 = pl.col("lam") == "L5"
    t = pl.col("_l5_true")
    slack = TOL_COVER * pl.max_horizontal(pl.lit(1.0), t.abs())
    out = j.with_columns(pl.when(is5).then(pl.col("truth")).otherwise(None).alias("truth_as_stored"),
                         pl.when(is5).then(t).otherwise(pl.col("truth")).alias("truth"))
    for col, rule in (("covered", (t >= pl.col("lo") - slack) & (t <= pl.col("hi") + slack)),
                      ("covered_one_sided", t >= pl.col("lo") - slack)):
        if col in out.columns:
            out = out.with_columns(pl.when(is5 & pl.col(col).is_not_null()).then(rule)
                                   .otherwise(pl.col(col)).alias(col))
    return out.drop("_l5_true")
