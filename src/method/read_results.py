"""Summarise a P3 result file into the tables `docs/P3_results.md` reports.

    python -m src.method.read_results artifacts/P3/p3_synthetic_arm_o.csv

Reads a raw per-(cell, functional) CSV, casts the columns the CSV round trip turned
into text, and prints -- and writes -- the three things the brief asks for: coverage
of the truth, the single-common-response comparison, and width against censoring rate
and exposure rank.
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl

BOOL_COLS = ("covered", "covered_one_sided", "in_row_space", "pooled_err_exceeds_width",
             "defined", "feasible", "exposure_rank_full")
NUM_COLS = ("lo", "hi", "width", "truth", "eps", "rms_point", "rms_floor",
            "perp_fraction", "pooled_value", "pooled_abs_err", "l5_coverage",
            "l5_energy_full_gwh", "mean_c_true", "censored_share",
            "exact_collinear_capacity")


def load(path: str | Path) -> pl.DataFrame:
    d = pl.read_csv(path, infer_schema_length=0)
    for c in BOOL_COLS:
        if c in d.columns:
            d = d.with_columns(
                pl.when(pl.col(c) == "True").then(True)
                  .when(pl.col(c) == "False").then(False)
                  .otherwise(None).alias(c))
    for c in NUM_COLS + ("rate", "gamma", "seed", "n_rows", "n_cols", "rank_X",
                         "exposure_rank", "n_qh_lam", "n_event_days",
                         "n_rows_compressed", "run_levels", "n_cohorts"):
        if c in d.columns:
            d = d.with_columns(pl.col(c).cast(pl.Float64, strict=False).alias(c))
    # Erratum (docs/ERRATUM_lambda5.md): stored lambda-5 truths came from the estimated
    # potential; replace them by the true-potential truth before anything is scored.
    from src.method.lambda5_truth import correct_l5
    d = correct_l5(d)
    # L5 is a one-sided claim wherever the counterfactual was clamped (section 0.10).
    if "covered_one_sided" in d.columns:
        d = d.with_columns(
            pl.when((pl.col("lam") == "L5") & (pl.col("l5_coverage") < 1.0))
              .then(pl.col("covered_one_sided")).otherwise(pl.col("covered")).alias("cov"))
    return d


def main() -> None:
    path = Path(sys.argv[1])
    d = load(path)
    cfg = [c for c in ("hetero", "rate", "gamma", "r_shape", "seed", "setting",
                       "month", "area") if c in d.columns]
    print(f"{path}: {d.height} rows, {d.select(cfg).unique().height} cells\n")

    if "status_lo" in d.columns:
        print("solver status:",
              {r["status_lo"]: r["count"] for r in d["status_lo"].value_counts().to_dicts()})

    if "cov" in d.columns and d["cov"].is_not_null().any():
        print("\n== coverage of the truth, per functional")
        print(d.group_by("lam").agg(
            pl.col("cov").sum().alias("covered"),
            pl.col("cov").is_not_null().sum().alias("scored"),
            pl.col("defined").sum().alias("defined"),
            pl.col("width").median().alias("median_width"),
        ).sort("lam"))
        sc = d.filter(pl.col("cov").is_not_null())
        print(f"OVERALL {sc['cov'].sum()} of {sc.height} = {sc['cov'].mean():.4f}")
        miss = d.filter(pl.col("cov") == False)  # noqa: E712
        if miss.height:
            print(f"\n== the {miss.height} misses")
            print(miss.select(cfg + ["lam", "lo", "hi", "width", "truth", "eps"]))

    print("\n== median width, functional x shape, by arm")
    key = ["lam"] + [c for c in ("r_shape", "setting") if c in d.columns]
    piv = [c for c in ("hetero", "month") if c in d.columns]
    w = d.filter(pl.col("defined") & pl.col("feasible"))
    if piv:
        print(w.group_by(key + piv).agg(pl.col("width").median().alias("w"))
               .pivot(values="w", index=key, on=piv[0]).sort(key))
    else:
        print(w.group_by(key).agg(pl.col("width").median().alias("w")).sort(key))

    if "pooled_err_exceeds_width" in d.columns and d["pooled_err_exceeds_width"].is_not_null().any():
        print("\n== single common response function: how often it misses by more than the width")
        print(d.filter(pl.col("pooled_err_exceeds_width").is_not_null()).group_by("lam").agg(
            pl.col("pooled_err_exceeds_width").sum().alias("exceeds"),
            pl.len().alias("n"),
            pl.col("pooled_abs_err").median().alias("median_abs_err"),
            pl.col("width").median().alias("median_width"),
        ).sort("lam"))

    if "rate" in d.columns:
        print("\n== median width against censoring rate")
        print(d.filter(pl.col("defined") & pl.col("feasible"))
               .group_by(["lam", "rate"]).agg(pl.col("width").median().alias("w"))
               .sort(["lam", "rate"]).pivot(values="w", index="lam", on="rate"))

    print("\n== design")
    cols = [c for c in ("exposure_rank", "n_cohorts", "exact_collinear_capacity",
                        "n_cols", "rank_X", "run_levels", "n_rows") if c in d.columns]
    print(d.select(cols).unique().sort(cols[0]))

    print("\n== in the row space of X")
    print(d.filter(pl.col("defined")).group_by("lam").agg(
        pl.col("in_row_space").sum().alias("in_row_space"),
        pl.len().alias("n"),
        pl.col("perp_fraction").median().alias("median_perp_fraction"),
    ).sort("lam"))

    out = path.with_name(path.stem + "_summary.csv")
    summ = d.group_by("lam").agg(
        pl.col("defined").sum().alias("n_defined"),
        pl.col("feasible").sum().alias("n_feasible"),
        (pl.col("cov").sum() if "cov" in d.columns else pl.lit(None)).alias("n_covered"),
        (pl.col("cov").is_not_null().sum() if "cov" in d.columns else pl.lit(None)).alias("n_scored"),
        pl.col("width").median().alias("median_width"),
        pl.col("width").min().alias("min_width"),
        pl.col("width").max().alias("max_width"),
        pl.col("in_row_space").sum().alias("n_in_row_space"),
        (pl.col("pooled_err_exceeds_width").sum()
         if "pooled_err_exceeds_width" in d.columns else pl.lit(None)).alias("n_pooled_exceeds"),
    ).sort("lam")
    summ.write_csv(out)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
