"""Experiment 4 domain classifier: target (price < 0) against clean, on the allowed inputs only.

    python -m src.method.learned_potential.domain

Cross-fitted leaving one calendar month out: every row's p comes from a classifier that never
saw that month, so no quarter-hour is weighted by a model trained on its own day. Writes, in
artifacts/exp4_learned_potential/:

  domain_scores.parquet   per (area, quarter-hour): p, the month it was held out in, weight w
                          (clean rows), look-alike flags
  clean_target_counts.csv per area and period: rows, valid, clean, target
  domain_overlap.csv      target quarter-hours with p above the overlap threshold, per area,
                          pooled and at the aggregate
  lookalike_days.csv      per Berlin date in the evaluation window: look-alike quarter-hours
                          per area and at the aggregate
"""

from __future__ import annotations

import polars as pl

from src.method.learned_potential import config as cfg
from src.method.learned_potential.data import ART, features, load_rows

SCORES = ART / "domain_scores.parquet"


def _classifier():
    import lightgbm as lgb
    return lgb.LGBMClassifier(objective="binary", random_state=cfg.SEED, verbose=-1,
                              deterministic=True, force_row_wise=True, n_jobs=4,
                              **cfg.DOMAIN_PARAMS)


def cross_fit(d: pl.DataFrame) -> pl.DataFrame:
    """p for every valid row, from a classifier trained on the other months' clean and target rows."""
    lab = d.filter(pl.col("valid") & (pl.col("clean") | pl.col("target")))
    months = sorted(d["month"].unique().to_list())
    parts = []
    for m in months:
        tr = lab.filter(pl.col("month") != m)
        clf = _classifier()
        clf.fit(features(tr).to_numpy(), tr["target"].cast(pl.Int8).to_numpy(),
                categorical_feature=[list(cfg.ALLOWED_FEATURES).index("area")])
        te = d.filter((pl.col("month") == m) & pl.col("valid"))
        p = clf.predict_proba(features(te).to_numpy())[:, 1]
        parts.append(te.select(["area", "ts_utc"]).with_columns(
            pl.Series("p", p), pl.lit(m).alias("p_heldout_month")))
        print(f"  domain fold {m}: trained on {tr.height:,} rows, scored {te.height:,}", flush=True)
    return pl.concat(parts)


def build() -> pl.DataFrame:
    d = load_rows()
    s = d.join(cross_fit(d), on=["area", "ts_utc"], how="left")
    lab = s.filter(pl.col("valid") & (pl.col("clean") | pl.col("target")))
    n_clean, n_target = int(lab["clean"].sum()), int(lab["target"].sum())
    w_raw = (pl.col("p") / (1.0 - pl.col("p"))) * (n_clean / n_target)
    clip = float(s.filter(pl.col("clean")).select(w_raw.quantile(cfg.WEIGHT_CLIP_PERCENTILE / 100.0)).item())
    s = s.with_columns(pl.when(pl.col("clean")).then(pl.min_horizontal(w_raw, pl.lit(clip)))
                         .otherwise(None).alias("w"))
    in_eval = (pl.col("berlin_date") >= cfg.EVAL_WINDOW[0]) & (pl.col("berlin_date") <= cfg.EVAL_WINDOW[1])
    cut = float(s.filter(pl.col("clean") & in_eval)["p"].quantile(1.0 - cfg.LOOKALIKE_TOP_SHARE))
    s = s.with_columns((pl.col("clean") & in_eval & (pl.col("p") >= cut)).alias("lookalike"),
                       pl.lit(clip).alias("w_clip"), pl.lit(cut).alias("p_lookalike_cut"))
    # aggregate look-alike: timestamps clean in all three areas, mean p in the top decile
    agg = (s.filter(in_eval).group_by("ts_utc")
             .agg(pl.col("clean").all().alias("all_clean"), pl.col("p").mean().alias("p_mean"),
                  pl.len().alias("n_areas"))
             .filter(pl.col("all_clean") & (pl.col("n_areas") == len(cfg.AREAS))))
    cut_agg = float(agg["p_mean"].quantile(1.0 - cfg.LOOKALIKE_TOP_SHARE))
    agg_ts = agg.filter(pl.col("p_mean") >= cut_agg)["ts_utc"]
    return s.with_columns(pl.col("ts_utc").is_in(agg_ts.implode()).alias("lookalike_aggregate"),
                          pl.lit(cut_agg).alias("p_lookalike_cut_aggregate"))


def counts(s: pl.DataFrame) -> pl.DataFrame:
    s = s.with_columns(pl.when(pl.col("berlin_date") >= cfg.EVAL_WINDOW[0])
                         .then(pl.lit("evaluation window")).otherwise(pl.lit("history")).alias("period"))
    return (s.group_by(["area", "period"])
             .agg(pl.len().alias("rows"), pl.col("valid").sum().alias("valid"),
                  pl.col("clean").sum().alias("clean"), pl.col("target").sum().alias("target"),
                  pl.col("berlin_date").min().alias("first_date"), pl.col("berlin_date").max().alias("last_date"))
             .sort(["period", "area"]))


def overlap(s: pl.DataFrame) -> pl.DataFrame:
    in_eval = (pl.col("berlin_date") >= cfg.EVAL_WINDOW[0]) & (pl.col("berlin_date") <= cfg.EVAL_WINDOW[1])
    t = s.filter(pl.col("target") & in_eval)
    rows = []
    for name, q in [(a, t.filter(pl.col("area") == a)) for a in cfg.AREAS] + [("pooled area rows", t)]:
        rows.append({"unit": name, "n_target": q.height,
                     "n_no_overlap": int((q["p"] > cfg.OVERLAP_P).sum()),
                     "share_no_overlap": float((q["p"] > cfg.OVERLAP_P).mean()),
                     "p_median": float(q["p"].median()), "p_q90": float(q["p"].quantile(0.9)),
                     "p_max": float(q["p"].max())})
    agg = t.group_by("ts_utc").agg(pl.col("p").mean().alias("p"), pl.len().alias("n"))
    agg = agg.filter(pl.col("n") == len(cfg.AREAS))
    rows.append({"unit": "aggregate (mean p over the areas)", "n_target": agg.height,
                 "n_no_overlap": int((agg["p"] > cfg.OVERLAP_P).sum()),
                 "share_no_overlap": float((agg["p"] > cfg.OVERLAP_P).mean()),
                 "p_median": float(agg["p"].median()), "p_q90": float(agg["p"].quantile(0.9)),
                 "p_max": float(agg["p"].max())})
    return pl.DataFrame(rows)


def lookalike_days(s: pl.DataFrame) -> pl.DataFrame:
    e = s.filter(pl.col("lookalike") | pl.col("lookalike_aggregate"))
    per = (e.group_by(["berlin_date", "area"]).agg(pl.col("lookalike").sum().alias("n"))
             .pivot(on="area", index="berlin_date", values="n").fill_null(0))
    for a in cfg.AREAS:
        if a not in per.columns:
            per = per.with_columns(pl.lit(0).alias(a))
    aggn = (e.filter(pl.col("lookalike_aggregate")).select(["berlin_date", "ts_utc"]).unique()
              .group_by("berlin_date").agg(pl.len().alias("aggregate")))
    return (per.join(aggn, on="berlin_date", how="left").fill_null(0)
               .select(["berlin_date", *cfg.AREAS, "aggregate"]).sort("berlin_date"))


def main() -> None:
    import sys
    ART.mkdir(parents=True, exist_ok=True)
    if "--diagnose" in sys.argv[1:]:
        d = overlap_diagnosis()
        d.write_csv(DIAGNOSIS)
        print(d)
        print(f"wrote {DIAGNOSIS}")
        return
    s = build()
    s.select(["area", "ts_utc", "berlin_date", "month", "valid", "clean", "target", "p",
              "p_heldout_month", "w", "w_clip", "lookalike", "lookalike_aggregate",
              "p_lookalike_cut", "p_lookalike_cut_aggregate"]).write_parquet(SCORES)
    counts(s).write_csv(ART / "clean_target_counts.csv")
    o = overlap(s)
    o.write_csv(ART / "domain_overlap.csv")
    lookalike_days(s).write_csv(ART / "lookalike_days.csv")
    print(o)
    print(f"wrote {SCORES} and three CSVs in {ART}")



# ------------------------------------------------- overlap diagnosis (Amendment 1)

DIAGNOSIS = ART / "overlap_diagnosis.csv"


def overlap_diagnosis() -> pl.DataFrame:
    """Per area, evaluation window: the target quarter-hours without overlap against the clean
    quarter-hours. Reads the committed step 1 scores; nothing is refitted (Amendment 1)."""
    from src.method.learned_potential.data import load_rows
    s = pl.read_parquet(SCORES).select(["area", "ts_utc", "p"])
    d = load_rows().join(s, on=["area", "ts_utc"], how="left").filter(
        (pl.col("berlin_date") >= cfg.EVAL_WINDOW[0]) & (pl.col("berlin_date") <= cfg.EVAL_WINDOW[1]))
    rows = []
    for a in cfg.AREAS:
        q = d.filter(pl.col("area") == a)
        t = q.filter(pl.col("target"))
        no = t.filter(pl.col("p") > cfg.OVERLAP_P)
        cl = q.filter(pl.col("clean"))
        rows.append({"area": a, "n_target": t.height, "n_target_no_overlap": no.height,
                     "n_target_overlap": t.height - no.height,
                     "share_target_with_overlap": (t.height - no.height) / t.height,
                     "median_solar_mw_target_no_overlap": float(no["f_solar_mw"].median()),
                     "share_rd_positive_target_no_overlap": float((no["rd"] > 0).mean()),
                     "median_solar_mw_clean": float(cl["f_solar_mw"].median()),
                     "n_clean": cl.height})
    return pl.DataFrame(rows)



if __name__ == "__main__":
    main()
