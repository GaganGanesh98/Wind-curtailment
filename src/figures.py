"""The figures, 01-09 and 13-17, in reading order (docs/00_start_here.md).

    python -m src.figures                  # writes figures/
    python -m src.figures --out demo/output/figures

Every plotted value is read from a committed file in `artifacts/` (the two motivation figures
also read the archived forecast-bias check in `archive/results/`, and figure 01 the processed
panel). None is typed in. For each figure the script writes a 300-dpi PNG, the exact plotted
data as CSV, and a caption file naming the source files and columns. `tests/test_figures.py`
rebuilds the data tables and compares them with the artifacts and with the committed CSVs.

The data builders return polars frames and do no plotting, so the test can call them without
matplotlib.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polars as pl

from src.method.read_results import load

REPO_ROOT = Path(__file__).resolve().parents[1]
RES = REPO_ROOT / "archive" / "results"          # forecast-bias check (archived); motivation only
ART = REPO_ROOT / "artifacts"
AP, E1, E2, E3 = (ART / "available_power_estimate", ART / "exp1_known_truth_validation",
                  ART / "exp2_bias_robustness_validation", ART / "exp3_german_application")
PANEL = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"
OUT_DIR = REPO_ROOT / "figures"

#: Okabe-Ito, colour-blind safe. One meaning per colour across all figures.
BLUE, ORANGE, GREEN, VERMILION, SKY, PURPLE, GREY = (
    "#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7", "#7F7F7F")

#: Window of the forecast-bias check (archived; the panel now starts 2024-01-01).
KILL_TEST_START = "2025-10-01"
NEG_BANDS = ("<= -50", "-50 to -20", "-20 to -5", "-5 to 0")
Q0B_BANDS = ("band <=-50", "band [-50,-20]", "band [-20,-5]", "band (-5,0)")
Q0B_POSITIVE = "price >= 0"          # the reference set clause A compares against
Q0B_AREA = "50Hertz+Amprion+TransnetBW"
LAMS = ("L1", "L2", "L3", "L4", "L5", "L6", "L7")
LAM_LABEL = {"L1": "λ₁ fleet", "L2": "λ₂ deep", "L3": "λ₃ cohort", "L4": "λ₄ group",
             "L5": "λ₅ energy", "L6": "λ₆ contrast", "L7": "λ₇ member"}


# --------------------------------------------------------------------------- data

def motivation_day() -> str:
    """The kill test's largest-error event-day (rank 1 by total negative-QH error, DE)."""
    worst = pl.read_csv(RES / "02_worst_days_de.csv").filter(pl.col("rank_by_total_error") == 1)
    return worst["berlin_date"][0]


def event_day_data() -> pl.DataFrame:
    """That day, onshore, 50Hertz + Amprion + TransnetBW: forecast F, actual G, projection H.

    Read through Q0b's own loader, so H, F, G and R are exactly the series Q0b used. H is
    published per control area and onshore only; TenneT is excluded from the aggregate
    (T-D(vii)), so all three lines cover the same three-area onshore fleet.
    """
    import contextlib
    import io
    from src.method.available_power import AGG_NAME, load_frames
    with contextlib.redirect_stdout(io.StringIO()):          # the loader prints progress
        agg = load_frames("quality-assured")[AGG_NAME]
    day = motivation_day()
    return (agg.filter(pl.col("berlin_date") == day).sort("ts_utc")
               .select(pl.from_epoch("ts_utc", time_unit="ms").alias("ts_utc"), "berlin_date",
                       pl.col("da_onshore_mw").alias("day_ahead_forecast_mw"),
                       pl.col("act_onshore_mw").alias("actual_mw"),
                       pl.col("hr_mw").alias("projection_h_mw"),
                       pl.col("rd_mw").alias("redispatch_mw"),
                       "price_eur_mwh"))


def forecast_bias_data() -> pl.DataFrame:
    """Kill-test bias by negative price band, DE."""
    b = pl.read_csv(RES / "02_bias_by_price_band.csv").filter(
        (pl.col("area") == "DE") & pl.col("price_band_eur_mwh").is_in(NEG_BANDS))
    order = {k: i for i, k in enumerate(NEG_BANDS)}
    return (b.with_columns(pl.col("price_band_eur_mwh").replace_strict(order).alias("_o"))
             .sort("_o").drop("_o")
             .select(["price_band_eur_mwh", "qhs", "days", "mean_e_mw", "ci_lo_mw", "ci_hi_mw"]))


def forecast_bias_sample() -> pl.DataFrame:
    return pl.read_csv(RES / "01_sample_size.csv").filter(
        pl.col("metric").is_in(["negative QHs (price < 0)", "event-days (>=1 negative QH)"]))


def _kill_test_counts() -> dict:
    s = {r["metric"]: int(r["value"]) for r in forecast_bias_sample().iter_rows(named=True)}
    return {"nq": s["negative QHs (price < 0)"], "nd": s["event-days (>=1 negative QH)"]}


def gap_by_band_data() -> pl.DataFrame:
    """Gap share (P - G - R) / P per negative band, P = projection H or forecast F."""
    sets = (*Q0B_BANDS, Q0B_POSITIVE)
    g = pl.read_csv(AP / "gap_shares.csv").filter(
        (pl.col("series") == "quality-assured") & (pl.col("area") == Q0B_AREA)
        & pl.col("set").is_in(sets))
    order = {k: i for i, k in enumerate(sets)}
    return (g.with_columns(pl.col("set").replace_strict(order).alias("_o"))
             .sort(["_o", "estimator"], descending=[False, True]).drop("_o")
             .select(["set", "estimator", "n_qh", "n_days",
                      *(pl.col(c).cast(pl.Float64) for c in ("gap_share", "ci_lo", "ci_hi"))]))


def exp1_coverage_data() -> pl.DataFrame:
    """Experiment 1: coverage of the known truth, every unbiased synthetic setting."""
    rows = []
    for label, f in (("exact potential", "exact_potential_cells.csv"),
                     ("estimated potential", "estimated_potential_cells.csv")):
        d = load(E1 / f).filter(pl.col("cov").is_not_null())
        rows.append({"study": "arm", "setting": label, "n_scored": d.height,
                     "n_covered": int(d["cov"].sum()), "coverage": float(d["cov"].mean()),
                     "source": f"artifacts/exp1_known_truth_validation/{f}, column cov"})
    q1 = (pl.read_csv(E1 / "noise_dial_summary.csv")
            .group_by(["noise", "sigma"]).agg(pl.col("level_coverage").first())
            .sort(["noise", "sigma"], descending=[True, False]))
    for r in q1.iter_rows(named=True):
        kind = "i.i.d." if r["noise"] == "iid" else "AR(1)"
        rows.append({"study": "noise dial", "setting": f"noise dial, {kind} σ = {r['sigma']:g}",
                     "n_scored": None, "n_covered": None, "coverage": r["level_coverage"],
                     "source": "artifacts/exp1_known_truth_validation/noise_dial_summary.csv, column level_coverage"})
    return pl.DataFrame(rows)


def exp2_coverage_data() -> pl.DataFrame:
    """Experiment 2: coverage under a biased potential, plain set and bias-robust set."""
    q = pl.read_csv(E2 / "bias_dial_coverage.csv")
    plain = q.filter(~((pl.col("dial") == "q2b") & (pl.col("sigma") == 0.0))).select(
        pl.lit("plain set").alias("panel"), "sigma", pl.col("b").alias("b_true"),
        pl.lit(None, dtype=pl.Float64).alias("B"), "n_covered", "n_scored",
        pl.col("level_coverage").alias("coverage"))
    v = pl.read_csv(E2 / "bias_robust_coverage.csv").select(
        pl.lit("bias-robust set").alias("panel"), pl.lit(0.0).alias("sigma"), "b_true", "B",
        "n_covered", "n_scored", "coverage")
    return pl.concat([plain, v]).sort(["panel", "sigma", "B", "b_true"], descending=[True, False, False, False])


def exact_vs_estimated_data() -> pl.DataFrame:
    """Median width per functional, Arm O seed 45 (exact) vs Arm D (estimated)."""
    o = load(E1 / "exact_potential_cells.csv").filter(pl.col("seed") == 45)
    d = load(E1 / "estimated_potential_cells.csv")
    rows = []
    for lam in LAMS:
        if lam == "L5":     # GWh, not a response share; reported in the caption instead
            continue
        mo = o.filter((pl.col("lam") == lam) & pl.col("feasible"))["width"].median()
        md = d.filter((pl.col("lam") == lam) & pl.col("feasible"))["width"].median()
        rows.append({"lam": lam, "label": LAM_LABEL[lam],
                     "median_width_exact": float(mo), "median_width_estimated": float(md),
                     "ratio": float(md) / float(mo)})
    return pl.DataFrame(rows)


def noise_dial_data() -> pl.DataFrame:
    """Noise dial: share of cells informative, per functional, against i.i.d. noise σ."""
    return (pl.read_csv(E1 / "noise_dial_summary.csv")
              .filter(pl.col("noise") == "iid")
              .select(["lam", "sigma", "n_cells", "n_informative", "share_informative"])
              .sort(["lam", "sigma"]))


def anchors() -> dict:
    a = pl.read_csv(AP / "error_anchors.csv")
    h = a.filter((pl.col("anchor") == "H") & pl.col("area").str.starts_with("DE excl. TenneT")
                 & (pl.col("sample") == "price >= 0"))["sigma"]
    t = a.filter((pl.col("anchor") == "T") & (pl.col("area") == "DE")
                 & (pl.col("series") == "onshore") & (pl.col("sample") == "price >= 0"))["sigma"]
    assert h.len() == 1 and t.len() == 1
    return {"H": float(h[0]), "T": float(t[0])}


def h_bias_primary() -> float:
    """H's bias for Experiment 3: quality-assured series, its own window, price >= 0."""
    from src.experiments.available_power_anchors import primary_h
    return float(primary_h()["bias"])


def anchors_bias_h() -> float:
    """The operational row of error_anchors.csv (the bias dial's calibration point)."""
    a = pl.read_csv(AP / "error_anchors.csv")
    h = a.filter((pl.col("anchor") == "H") & pl.col("area").str.starts_with("DE excl. TenneT")
                 & (pl.col("sample") == "price >= 0"))["bias"]
    assert h.len() == 1
    return float(h[0])


FLEET, COHORT = ("L1", "L2"), ("L3", "L4", "L6", "L7")


def width_vs_noise_data() -> pl.DataFrame:
    """Noise dial: median interval width and interquartile range per functional against i.i.d. σ."""
    return (pl.read_csv(E1 / "noise_dial_summary.csv")
              .filter((pl.col("noise") == "iid") & pl.col("lam").is_in(FLEET + COHORT))
              .with_columns(pl.when(pl.col("lam").is_in(FLEET)).then(pl.lit("fleet"))
                              .otherwise(pl.lit("cohort")).alias("group"))
              .select(["group", "lam", "sigma", "n_cells", "median_width", "q25_width",
                       "q75_width"])
              .sort(["group", "lam", "sigma"], descending=[True, False, False]))


V2_THRESHOLD = {"L1": None, "L2": 0.5, "L3": 0.75, "L6": 0.5}


def bias_breakdown_data() -> pl.DataFrame:
    """Phase V2: bias-robust full-window interval S_B against the budget B, with breakdown."""
    iv = pl.read_csv(E3 / "bias_robust_full_window_intervals.csv")
    bd = pl.read_csv(E3 / "breakdown_points.csv", infer_schema_length=0).select(
        "lam", pl.col("breakdown_B").alias("breakdown_B"))
    return iv.join(bd, on="lam").sort(["lam", "B"])




def data_requirement_data() -> pl.DataFrame:
    """Figure 13: per quantity, the σ a narrow range needs and the bias its reading survives.

    Read from artifacts/exp3_data_requirement.parquet (src/experiments/exp3_policy_use.py).
    """
    d = pl.read_parquet(ART / "exp3_data_requirement.parquet")
    bd = d["breakdown_B"].to_list()
    return d.select(
        "lam", "quantity", "sigma_informative", "sigma_top_of_grid", "sigma_label", "sigma_H",
        pl.Series("breakdown_B_value", [None if b in ("no reading", "") else
                                        float(b.lstrip("> ")) for b in bd], dtype=pl.Float64),
        pl.Series("breakdown_above_grid", [b.startswith(">") for b in bd]),
        pl.col("breakdown_B").alias("breakdown_label"),
        pl.col("bias_H").abs().alias("abs_bias_H"))


def cnn_trace_data() -> pl.DataFrame:
    """Figure 14: N1's weighted training and validation loss per epoch, every fit (cnn_loss_trace.csv)."""
    t = pl.read_csv(ART / "exp4_learned_potential" / "cnn_loss_trace.csv")
    return t.select(["fit", "layers", "channels", "epoch", "best_epoch", "train_loss_weighted",
                     "val_loss_weighted"])


EXP4 = ART / "exp4_learned_potential"


def exp4_lookalike_data() -> pl.DataFrame:
    """Figure 15: σ and bias of log(G / Â) on look-alike quarter-hours, every model, at the
    aggregate and on the pooled area rows (lookalike_scores.csv, all look-alike)."""
    s = pl.read_csv(EXP4 / "lookalike_scores.csv").filter(
        (pl.col("subset") == "all look-alike")
        & pl.col("unit").is_in(["three-area aggregate", "pooled area rows"])
        & (pl.col("metric").str.starts_with("sigma") | pl.col("metric").str.starts_with("bias")))
    return s.select(["unit", "model", "metric", "value", "lo", "hi", "n_qh", "n_days"]).sort(["unit", "metric", "model"])


def exp4_bias_data() -> pl.DataFrame:
    """Figure 16: corrected b̂_H per unit, trimmed and untrimmed (bias_budget.csv; descriptive)."""
    return pl.read_csv(EXP4 / "bias_budget.csv").select(
        ["unit", "arm", "n_target_qh", "share_of_target_kept", "corrected", "corrected_lo", "corrected_hi", "status"])


def exp4_overlap_data() -> pl.DataFrame:
    """Figure 17: histogram of the domain score p, clean against target quarter-hours, per area,
    evaluation window (domain_scores.parquet)."""
    s = pl.read_parquet(EXP4 / "domain_scores.parquet").filter(
        (pl.col("berlin_date") >= "2025-10-01") & (pl.col("berlin_date") <= "2026-09-30")
        & (pl.col("clean") | pl.col("target")))
    edges = np.linspace(0.0, 1.0, 51)
    rows = []
    for area in ("50Hertz", "Amprion", "TransnetBW"):
        for name, flag in (("clean", "clean"), ("target", "target")):
            p = s.filter((pl.col("area") == area) & pl.col(flag))["p"].to_numpy()
            h, _ = np.histogram(p, bins=edges)
            for lo, hi, n in zip(edges[:-1], edges[1:], h):
                rows.append({"area": area, "set": name, "p_lo": round(float(lo), 2), "p_hi": round(float(hi), 2),
                             "count": int(n), "share": float(n / max(p.size, 1))})
    return pl.DataFrame(rows)


CAPTIONS = {
    "01_motivation_event_day": (
        "Motivation. {day} (Easter Sunday) is the largest-error negative-price event-day of the "
        "forecast-bias check, not a typical day: it carries {share:.1%} of all negative-quarter-hour "
        "forecast error. The forecast-bias check covers 2025-10-01 to 2026-10-28, all of Germany "
        "including TenneT, {nq:,} negative-price quarter-hours on {nd} event days; that is not "
        "Experiment 3's window (2025-10-01 to 2026-09-30, three areas). Plotted here: onshore "
        "wind, 50Hertz + Amprion + TransnetBW (TenneT excluded): TSO "
        "day-ahead forecast F, actual output G and the quality-assured projection H "
        "(Online-Hochrechnung), with the day-ahead price on the right axis. Shaded: "
        "negative-price quarter-hours.",
        "Day chosen as rank 1 in archive/results/02_worst_days_de.csv (columns "
        "rank_by_total_error, share_of_total_negative_qh_error; ranked on DE total wind). "
        "Series from src/method/available_power.load_frames('quality-assured'): da_onshore_mw, "
        "act_onshore_mw, hr_mw, rd_mw, price_eur_mwh. Inputs data/processed/panel_qh.parquet "
        "and data/raw/netztransparenz/hochrechnung_wind_onshore_qualitaetsgesichert/ are not in git."),
    "02_motivation_forecast_bias_by_band": (
        "Motivation. Mean forecast error (actual minus day-ahead forecast) by negative price "
        "band, Germany (all four control areas, TenneT included), with 95% event-day bootstrap "
        "intervals. Window 2025-10-01 to 2026-10-28, the forecast-bias check's window, not "
        "Experiment 3's (which ends 2026-09-30 and covers three areas): {nq:,} negative-price "
        "quarter-hours on {nd} event days. A forecast-versus-generation discrepancy, not a causal "
        "measure of voluntary curtailment.",
        "archive/results/02_bias_by_price_band.csv, rows area = DE, columns price_band_eur_mwh, "
        "mean_e_mw, ci_lo_mw, ci_hi_mw, qhs, days; totals from archive/results/01_sample_size.csv, "
        "column value."),
    "03_available_power_gap_by_band": (
        "Available-power estimate: share of the potential estimate not produced once redispatch "
        "is removed, (P − G − R) / P, by negative price band and, as reference, over all "
        "quarter-hours with price ≥ 0, for the quality-assured projection H and the day-ahead "
        "forecast F. 50Hertz + Amprion + TransnetBW (TenneT excluded), 95% intervals.",
        "artifacts/available_power_estimate/gap_shares.csv, rows series = quality-assured, "
        "area = 50Hertz+Amprion+TransnetBW, set = band ... and price >= 0, columns estimator, "
        "gap_share, ci_lo, ci_hi."),
    "04_exp1_coverage": (
        "Experiment 1: coverage of the known truth by the identified sets with an unbiased "
        "potential — exact potential, estimated potential, and every level of the noise dial. "
        "Dashed line: the pre-registered 95% target (binding for the exact-potential arm). "
        "With a biased potential coverage fails; see figure 08.",
        "artifacts/exp1_known_truth_validation/exact_potential_cells.csv and "
        "estimated_potential_cells.csv, column cov (via src/method/read_results.load); "
        "artifacts/exp1_known_truth_validation/noise_dial_summary.csv, column level_coverage."),
    "05_exp1_exact_vs_estimated_potential": (
        "Experiment 1: median width of the identified set per functional when the potential is "
        "exact (seed 45) and when it is estimated, log scale.\n"
        "λ₅ is omitted: it is a counterfactual energy in GWh, not a share of potential, so it "
        "cannot sit on this axis.",
        "artifacts/exp1_known_truth_validation/exact_potential_cells.csv (seed = 45) and "
        "estimated_potential_cells.csv, rows feasible, column width, median per lam."),
    "06_exp1_noise_dial": (
        "Experiment 1: share of the 54 synthetic cells in which each functional is informative, "
        "against i.i.d. noise σ in the potential. Vertical lines: the statutory projection H "
        "(σ is a lower bound on its error; the operational series' value; the quality-assured series gives σ 0.0610 and bias −0.0326 (docs/03)) and the TSO day-ahead forecast. λ₄ and λ₅ coincide "
        "at most levels, so they are drawn with different markers and a small horizontal "
        "offset. λ₇, one member of an exactly collinear pair, is not identified even at σ = 0: "
        "informative in {l7_k} of {l7_n} cells.",
        "artifacts/exp1_known_truth_validation/noise_dial_summary.csv, rows noise = iid, columns "
        "lam, sigma, share_informative; anchors from artifacts/available_power_estimate/"
        "error_anchors.csv, column sigma (H: area DE excl. TenneT, price >= 0; T: area DE, "
        "onshore, price >= 0)."),
    "07_exp1_width_vs_noise": (
        "Experiment 1: median width of the identified set (line) and interquartile range (band) "
        "across the 54 synthetic cells, against i.i.d. noise σ in the potential, on the tested "
        "grid only. Left: fleet functionals; right: cohort functionals. Log scale. Vertical "
        "lines: the statutory projection H (σ is a lower bound on its error; the operational series' value; the quality-assured series gives σ 0.0610 and bias −0.0326 (docs/03)) and the TSO "
        "forecast. Dashed horizontal line: 0.25, the informative limit for λ₁–λ₄ and λ₇ (λ₆'s "
        "is 0.5). λ₅ is omitted: it is an energy in GWh, not a share of potential.",
        "artifacts/exp1_known_truth_validation/noise_dial_summary.csv, rows noise = iid, lam in "
        "L1-L4, L6, L7, columns sigma, median_width, q25_width, q75_width; anchors from "
        "artifacts/available_power_estimate/error_anchors.csv as in figure 06."),
    "08_exp2_coverage_under_bias": (
        "Experiment 2: coverage of the known truth when the potential carries a constant "
        "multiplicative bias b. Left: the plain identified set, at σ = 0 (circles) and with "
        "noise σ = 0.066 (the operational series' value; the quality-assured series gives σ 0.0610 and bias −0.0326 (docs/03)) and 0.18 (other markers). Right: the bias-robust set for budget B "
        "(hull over |b| ≤ B), against the true bias. Dashed line: the 95% target. λ₅ is left "
        "out of the right panel, as pre-registered.",
        "artifacts/exp2_bias_robustness_validation/bias_dial_coverage.csv (columns dial, sigma, "
        "b, n_covered, n_scored, level_coverage) and bias_robust_coverage.csv (columns B, b_true, "
        "n_covered, n_scored, coverage)."),
    "09_exp3_bias_breakdown": (
        "Experiment 3: the bias-robust full-window interval with the projection H, main setting, "
        "for the four functionals with a reading, against the bias budget B (the hull over every "
        "constant multiplicative bias |b| ≤ B on a 0.01 grid). Dashed line: the bound the reading "
        "needs (λ₁: width below 0.25, shown as the interval itself). Vertical line: the breakdown "
        "B, the smallest B at which the reading no longer holds. Dotted line, for scale only: "
        "|{hb:.4f}|, the projection's measured bias on price ≥ 0 quarter-hours, quality-assured "
        "series on the Experiment 3 window (operational series |{hb_op:.4f}|); its bias during "
        "negative prices is not measured.",
        "artifacts/exp3_german_application/bias_robust_full_window_intervals.csv (columns lam, B, "
        "lo, hi, width) and breakdown_points.csv (column breakdown_B); scale line from "
        "artifacts/available_power_estimate/error_anchors.csv, column bias (anchor H, DE excl. "
        "TenneT, price >= 0)."),
    "13_data_requirement": (
        "Experiment 3, the accuracy each quantity needs. Left: the highest noise level σ at "
        "which the quantity is informative in at least half the synthetic cells (Experiment 1, "
        "i.i.d. noise; synthetic, best case, not a guarantee: real data are far less "
        "informative than the synthetic cells at the same σ). Vertical line: H's measured σ, "
        "quality-assured series on the Experiment 3 window. "
        "Right: the breakdown bias B of the quantity's pre-registered reading on real data. "
        "Vertical line: |bias| of H on price ≥ 0 quarter-hours; its bias during negative prices "
        "is not measured. Arrows mark values at or beyond the top of the tested grid.",
        "artifacts/exp3_data_requirement.parquet (columns sigma_informative, sigma_H, "
        "breakdown_B, bias_H), built from artifacts/exp1_known_truth_validation/"
        "noise_dial_summary.csv, artifacts/exp3_german_application/breakdown_points.csv and "
        "artifacts/available_power_estimate/error_anchors.csv."),
    "14_exp4_n1_loss_curves": (
        "Experiment 4, N1 (temporal CNN): importance-weighted pinball loss per epoch for each fit, "
        "training (dashed) and validation (solid; the last 28 days of the training span). The "
        "vertical line marks the epoch early stopping kept. Top row: the four pre-window selection "
        "fits (layers × channels); then the twelve monthly folds with the chosen 2 × 16 "
        "configuration. Training loss falls in every fit; validation loss moves up and down from "
        "epoch to epoch (all {n} fits are 'unstable' under the rule in docs/12b). Descriptive only.",
        "artifacts/exp4_learned_potential/cnn_loss_trace.csv (columns fit, layers, channels, epoch, "
        "best_epoch, train_loss_weighted, val_loss_weighted), written by models_cnn --loss-trace, "
        "which reproduced every stored fit bit for bit."),
    "15_exp4_lookalike_error": (
        "Experiment 4: error of each potential on look-alike quarter-hours (clean quarter-hours that "
        "the domain classifier finds most like negative-price ones), with day-block 95% intervals. "
        "Left: σ of log(G / Â); right: mean of log(G / Â). Top: three-area aggregate; bottom: "
        "pooled area rows. F is the TSO day-ahead forecast, H the quality-assured projection, L1 and "
        "L2 the LightGBM models (L2 importance-weighted), N1 the temporal CNN. Dashed lines on the "
        "right: the S2 tolerance ±{tol}.",
        "artifacts/exp4_learned_potential/lookalike_scores.csv (subset all look-alike; units "
        "three-area aggregate and pooled area rows; columns model, metric, value, lo, hi)."),
    "16_exp4_bias_descriptive": (
        "Experiment 4, descriptive only (S2 failed, so no budget B̂ is defined and no reading is "
        "judged against these numbers): the corrected mean of log(H / A) at negative prices, i.e. "
        "b̂_H = mean log(H / Â) minus L2's look-alike bias, with day-block 95% intervals, per area, "
        "pooled and at the aggregate. Filled: trimmed to target quarter-hours with overlap "
        "(primary); open: untrimmed (sensitivity, relies on extrapolation). It cannot separate H "
        "adding back more than was curtailed from Â falling short at negative prices.",
        "artifacts/exp4_learned_potential/bias_budget.csv (columns unit, arm, corrected, "
        "corrected_lo, corrected_hi)."),
    "17_exp4_overlap": (
        "Experiment 4: distribution of the cross-fitted domain classifier's score p (probability "
        "that a quarter-hour belongs to the negative-price target set, from price-free inputs only), "
        "for clean and target quarter-hours in the evaluation window, per area. Shares within each "
        "set, bins of 0.02. Dotted line: the overlap threshold p = {thr}; target quarter-hours "
        "beyond it have no clean look-alike. 50Hertz has the largest mass there.",
        "artifacts/exp4_learned_potential/domain_scores.parquet (columns area, berlin_date, clean, "
        "target, p)."),
}


def _style(plt) -> None:
    plt.rcParams.update({
        "font.size": 14, "axes.labelsize": 14, "axes.titlesize": 15,
        "xtick.labelsize": 13, "ytick.labelsize": 13, "legend.fontsize": 12,
        "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 100,
    })


def _band_label(b: str) -> str:
    return {"<= -50": "≤ −50", "-50 to -20": "−50 to −20", "-20 to -5": "−20 to −5",
            "-5 to 0": "−5 to 0", "band <=-50": "≤ −50", "band [-50,-20]": "−50 to −20",
            "band [-20,-5]": "−20 to −5", "band (-5,0)": "−5 to 0"}[b]


def make_all(out: Path) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    _style(plt)
    out.mkdir(parents=True, exist_ok=True)
    written = []

    def save(fig, name: str, data: pl.DataFrame, **fmt) -> None:
        fig.tight_layout()
        fig.savefig(out / f"{name}.png", dpi=300)
        plt.close(fig)
        data.write_csv(out / f"{name}_data.csv")
        cap, src = CAPTIONS[name]
        cap = cap.format(**fmt)
        (out / f"{name}_caption.txt").write_text(f"{name}\n\n{cap}\n\nSource: {src}\n",
                                                  encoding="utf-8")
        written.extend(out / f"{name}{s}" for s in (".png", "_data.csv", "_caption.txt"))

    # figure
    if PANEL.exists():
        d = event_day_data()
        worst = pl.read_csv(RES / "02_worst_days_de.csv").filter(pl.col("rank_by_total_error") == 1)
        fig, ax = plt.subplots(figsize=(11, 5.5))
        t = d["ts_utc"].to_numpy()
        neg = d["price_eur_mwh"].to_numpy() < 0
        for i in np.flatnonzero(neg):
            ax.axvspan(t[i], t[i] + np.timedelta64(15, "m"), color=GREY, alpha=0.12, lw=0)
        ax.plot(t, d["day_ahead_forecast_mw"].to_numpy() / 1000, color=BLUE, lw=2.2,
                label="day-ahead forecast F")
        ax.plot(t, d["projection_h_mw"].to_numpy() / 1000, color=GREEN, lw=2.2,
                label="quality-assured projection H")
        ax.plot(t, d["actual_mw"].to_numpy() / 1000, color=VERMILION, lw=2.2,
                label="actual output G")
        ax.set_ylabel("onshore wind, GW")
        ax.set_xlabel("time (UTC)")
        ax2 = ax.twinx()
        ax2.plot(t, d["price_eur_mwh"].to_numpy(), color=GREY, lw=1.4, ls="--",
                 label="day-ahead price")
        ax2.axhline(0, color=GREY, lw=0.8)
        ax2.set_ylabel("price, €/MWh")
        ax2.spines["top"].set_visible(False)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        shade = Patch(facecolor=GREY, alpha=0.25, label="negative price")
        ax.legend(h1 + h2 + [shade], l1 + l2 + ["negative price"], loc="lower left",
                  frameon=False, fontsize=11)
        ax.set_title(f"{d['berlin_date'][0]}, Easter Sunday: the largest-error event-day "
                     "(three areas, onshore)")
        save(fig, "01_motivation_event_day", d, day=d["berlin_date"][0],
             share=float(worst["share_of_total_negative_qh_error"][0]), **_kill_test_counts())

    # figure
    d, s = forecast_bias_data(), forecast_bias_sample()
    n_qh = int(s.filter(pl.col("metric") == "negative QHs (price < 0)")["value"][0])
    n_d = int(s.filter(pl.col("metric") == "event-days (>=1 negative QH)")["value"][0])
    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = np.arange(d.height)
    m = d["mean_e_mw"].to_numpy()
    ax.errorbar(x, m, yerr=[m - d["ci_lo_mw"].to_numpy(), d["ci_hi_mw"].to_numpy() - m],
                fmt="o", color=BLUE, ms=9, capsize=6, lw=2)
    ax.axhline(0, color=GREY, lw=1)
    ax.set_xticks(x, [f"{_band_label(b)}\n({q:,} QHs)" for b, q in
                      zip(d["price_band_eur_mwh"], d["qhs"])])
    ax.set_xlabel("day-ahead price band, €/MWh")
    ax.set_ylabel("actual − forecast, MW")
    ax.set_title(f"Forecast over-predicts more as prices fall ({n_qh:,} QHs, {n_d} event-days)")
    save(fig, "02_motivation_forecast_bias_by_band", d, **_kill_test_counts())

    # figure
    d = gap_by_band_data()
    sets = (*Q0B_BANDS, Q0B_POSITIVE)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    for k, (est, col, lab) in enumerate((("H", GREEN, "projection H"),
                                         ("F", BLUE, "day-ahead forecast F"))):
        q = d.filter(pl.col("estimator") == est)
        pos = {s: i for i, s in enumerate(sets)}
        x = np.array([pos[s] for s in q["set"]], dtype=float) + (k - 0.5) * 0.25
        x[q["set"].to_numpy() == Q0B_POSITIVE] += 0.4          # set the reference apart
        v = q["gap_share"].to_numpy()
        ax.errorbar(x, v, yerr=[v - q["ci_lo"].to_numpy(), q["ci_hi"].to_numpy() - v],
                    fmt="o", color=col, ms=9, capsize=5, lw=2, label=lab)
    ticks = np.arange(len(sets), dtype=float)
    ticks[-1] += 0.4
    ax.axvline((ticks[-2] + ticks[-1]) / 2, color=GREY, lw=0.8, ls=":")
    ax.set_xticks(ticks, [_band_label(b) for b in Q0B_BANDS] + ["all ≥ 0\n(reference)"])
    ax.axhline(0, color=GREY, lw=1)
    ax.set_xlabel("day-ahead price band, €/MWh")
    ax.set_ylabel("share of potential not produced\n(redispatch removed)")
    ax.set_title("Gap between potential estimate and output, by band")
    ax.legend(frameon=False)
    save(fig, "03_available_power_gap_by_band", d)

    # figure
    d = exp1_coverage_data()
    colours = {"arm": BLUE, "noise dial": GREEN}
    fig, ax = plt.subplots(figsize=(9, 0.42 * d.height + 1.8))
    y = np.arange(d.height)[::-1]
    ax.scatter(d["coverage"].to_numpy(), y, s=70,
               c=[colours[s] for s in d["study"]], zorder=3)
    ax.axvline(0.95, color=VERMILION, ls="--", lw=1.6, label="95% target")
    ax.set_yticks(y, d["setting"].to_list())
    ax.set_xlim(0.9, 1.01)
    ax.set_xlabel("coverage of the known truth")
    ax.set_title("With an unbiased potential, coverage never falls below target")
    ax.legend(frameon=False, loc="lower left")
    save(fig, "04_exp1_coverage", d)

    # figure
    d = exact_vs_estimated_data()
    fig, ax = plt.subplots(figsize=(9, 5.5))
    x = np.arange(d.height)
    ax.bar(x - 0.2, d["median_width_exact"].to_numpy(), 0.4, color=SKY, label="exact potential (Arm O)")
    ax.bar(x + 0.2, d["median_width_estimated"].to_numpy(), 0.4, color=ORANGE,
           label="estimated potential (Arm D)")
    ax.set_yscale("log")
    ax.set_xticks(x, d["label"].to_list(), rotation=20)
    ax.set_ylabel("median interval width (log)")
    ax.set_title("Estimating the potential widens every interval")
    ax.legend(frameon=False)
    save(fig, "05_exp1_exact_vs_estimated_potential", d)

    # figure
    d, anc = noise_dial_data(), anchors()
    fig, ax = plt.subplots(figsize=(10, 6))
    cyc = [BLUE, ORANGE, GREEN, VERMILION, SKY, PURPLE, GREY]
    marks = ["o", "s", "^", "D", "v", "P", "X"]
    offset = {"L4": -0.003, "L5": 0.003}                 # λ₄ and λ₅ overlap; nudge apart
    for lam, col, mk in zip(LAMS, cyc, marks):
        q = d.filter(pl.col("lam") == lam)
        if q.height:
            ax.plot(q["sigma"].to_numpy() + offset.get(lam, 0.0),
                    q["share_informative"].to_numpy(), marker=mk, ms=8,
                    ls="--" if lam == "L5" else "-", color=col, lw=2, label=LAM_LABEL[lam])
    for k, ls, lab in (("H", ":", "statutory projection H,\noperational (lower bound)"),
                       ("T", "--", "TSO forecast")):
        ax.axvline(anc[k], color="black", ls=ls, lw=1.3)
        ax.text(anc[k], 1.04, f"{lab}\nσ = {anc[k]:.3f}", ha="center", va="bottom", fontsize=11)
    ax.set_ylim(-0.03, 1.1)
    ax.set_xlabel("noise in the potential, σ")
    ax.set_ylabel("share of cells informative")
    ax.set_title("Noise dial: fleet stays informative, cohorts do not", pad=58)
    ax.legend(frameon=False, fontsize=11, ncol=2, loc="center right")
    l7 = d.filter((pl.col("lam") == "L7") & (pl.col("sigma") == 0.0))
    save(fig, "06_exp1_noise_dial", d.with_columns(pl.lit(anc["H"]).alias("anchor_h_sigma"),
                                              pl.lit(anc["T"]).alias("anchor_t_sigma")),
         l7_k=int(l7["n_informative"][0]), l7_n=int(l7["n_cells"][0]))

    # figure
    d, anc = width_vs_noise_data(), anchors()
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.8), sharey=True)
    styles = {"L1": (BLUE, "o"), "L2": (ORANGE, "s"), "L3": (GREEN, "^"),
              "L4": (VERMILION, "D"), "L6": (PURPLE, "P"), "L7": (GREY, "X")}
    for ax, group, lams, title in ((axes[0], "fleet", FLEET, "fleet functionals"),
                                   (axes[1], "cohort", COHORT, "cohort functionals")):
        for lam in lams:
            q = d.filter(pl.col("lam") == lam)
            col, mk = styles[lam]
            s = q["sigma"].to_numpy()
            ax.fill_between(s, q["q25_width"].to_numpy(), q["q75_width"].to_numpy(),
                            color=col, alpha=0.15, lw=0)
            ax.plot(s, q["median_width"].to_numpy(), marker=mk, ms=7, color=col, lw=2,
                    label=LAM_LABEL[lam])
        ax.axhline(0.25, color="black", ls=(0, (4, 3)), lw=1)
        for k, ls in (("H", ":"), ("T", "--")):
            ax.axvline(anc[k], color="black", ls=ls, lw=1.2)
        ax.set_yscale("log")
        ax.set_xlabel("noise in the potential, σ")
        ax.set_title(title)
        ax.legend(frameon=False, fontsize=11, loc="center right")
    axes[0].set_ylabel("interval width (log)")
    for ax in axes:
        for k, lab in (("H", "projection H, operational\n(lower bound)"), ("T", "TSO\nforecast")):
            ax.text(anc[k] + 0.004, 0.03, lab, transform=ax.get_xaxis_transform(),
                    ha="left", va="bottom", fontsize=10)
    fig.suptitle("Intervals widen with noise; cohort intervals cross the informative limit first",
                 fontsize=15)
    save(fig, "07_exp1_width_vs_noise", d.with_columns(pl.lit(anc["H"]).alias("anchor_h_sigma"),
                                                  pl.lit(anc["T"]).alias("anchor_t_sigma")))

    # exp 2: coverage under bias
    d = exp2_coverage_data()
    fig, (axl, axr) = plt.subplots(1, 2, figsize=(13, 5.5), sharey=True)
    for sg, mk, col in ((0.0, "o", BLUE), (0.066, "s", ORANGE), (0.18, "^", PURPLE)):
        q = d.filter((pl.col("panel") == "plain set") & (pl.col("sigma") == sg)).sort("b_true")
        axl.plot(q["b_true"].to_numpy(), q["coverage"].to_numpy(), marker=mk, ms=8, lw=1.5,
                 color=col, label=f"σ = {sg:g}")
    for B, mk, col in ((0.0, "o", GREY), (0.05, "s", SKY), (0.10, "D", GREEN)):
        q = d.filter((pl.col("panel") == "bias-robust set") & (pl.col("B") == B)).sort("b_true")
        axr.plot(q["b_true"].to_numpy(), q["coverage"].to_numpy(), marker=mk, ms=8, lw=1.5,
                 color=col, label=f"B = {B:g}")
    for ax, title in ((axl, "plain identified set"), (axr, "bias-robust set, budget B")):
        ax.axhline(0.95, color=VERMILION, ls="--", lw=1.4)
        levels = sorted(d["b_true"].unique().to_list())
        ax.set_xticks(levels, [f"{b:+.3f}" if b else "0" for b in levels], fontsize=12)
        ax.set_xlabel("true bias b")
        ax.set_title(title)
        ax.legend(frameon=False, loc="lower right")
    axl.set_ylabel("coverage of the known truth")
    axl.set_ylim(0, 1.05)
    fig.suptitle("A biased potential breaks coverage; the bias-robust set restores it within its budget",
                 fontsize=15)
    save(fig, "08_exp2_coverage_under_bias", d)

    # figure
    if (E3 / "bias_robust_full_window_intervals.csv").exists():
        d = bias_breakdown_data()
        hb = abs(h_bias_primary())
        fig, axes = plt.subplots(2, 2, figsize=(12, 8.5), sharex=True)
        for ax, lam, col in zip(axes.flat, ("L1", "L2", "L3", "L6"),
                                (BLUE, ORANGE, GREEN, PURPLE)):
            q = d.filter(pl.col("lam") == lam)
            B = q["B"].to_numpy()
            ax.fill_between(B, q["lo"].to_numpy(), q["hi"].to_numpy(), color=col, alpha=0.25,
                            lw=0)
            ax.plot(B, q["lo"].to_numpy(), color=col, lw=2)
            ax.plot(B, q["hi"].to_numpy(), color=col, lw=2)
            thr = V2_THRESHOLD[lam]
            if thr is not None:
                ax.axhline(thr, color="black", ls="--", lw=1.2)
            bk = q["breakdown_B"][0]
            if bk not in ("> 0.15",):
                ax.axvline(float(bk), color=VERMILION, lw=2)
                what = " (width ≥ 0.25)" if lam == "L1" else ""
                ax.text(float(bk) + 0.003, 0.5, f"breakdown\nB = {float(bk):g}{what}",
                        transform=ax.get_xaxis_transform(), va="center", fontsize=11,
                        color=VERMILION, bbox={"facecolor": "white", "alpha": 0.85, "lw": 0})
            else:
                ax.text(0.98, 0.45, "no breakdown up to B = 0.15", transform=ax.transAxes,
                        ha="right", va="center", fontsize=11)
            ax.axvline(hb, color=GREY, ls=":", lw=1.4)
            ax.set_title(LAM_LABEL[lam])
            ax.set_ylabel("bias-robust interval")
        for ax in axes[1]:
            ax.set_xlabel("bias budget B")
        fig.suptitle("Full-window readings with H: how much constant bias they survive",
                     fontsize=15)
        save(fig, "09_exp3_bias_breakdown", d.with_columns(pl.lit(hb).alias("abs_bias_h_positive_prices")),
             hb=hb, hb_op=abs(anchors_bias_h()))

    # figure 13
    if (ART / "exp3_data_requirement.parquet").exists():
        d = data_requirement_data()
        fig, (axl, axr) = plt.subplots(1, 2, figsize=(14, 6.2), sharey=True)
        ys = np.arange(d.height)[::-1]
        labels = [LAM_LABEL[l] for l in d["lam"]]
        box = {"facecolor": "white", "alpha": 0.85, "lw": 0, "pad": 1.5}
        for ax, xmax in ((axl, 0.40), (axr, 0.17)):
            ax.set_xlim(0, xmax)
            ax.set_ylim(-0.6, d.height + 0.1)          # a free band on top for the H label
            ax.set_yticks(ys, labels)
        for y, r in zip(ys, d.iter_rows(named=True)):
            s = r["sigma_informative"]
            if s is None:
                axl.plot(0.004, y, marker="X", ms=12, color=VERMILION, clip_on=False)
                axl.text(0.014, y, "not identifiable with perfect data", va="center",
                         fontsize=11, color=VERMILION)
            else:
                axl.barh(y, s, height=0.6, color=BLUE)
                axl.text(s + 0.006, y, ("≥ " if r["sigma_top_of_grid"] else "≤ ") + f"{s:g}"
                         + (" →" if r["sigma_top_of_grid"] else ""), va="center", fontsize=11,
                         bbox=box)
            b = r["breakdown_B_value"]
            if r["lam"] == "L7":
                axr.plot(0.002, y, marker="X", ms=12, color=VERMILION, clip_on=False)
                axr.text(0.007, y, "not identifiable with perfect data", va="center",
                         fontsize=11, color=VERMILION)
            elif b is None:
                axr.plot(0.002, y, marker="o", ms=9, mfc="white", color=GREY, clip_on=False)
                axr.text(0.007, y, "no reading", va="center", fontsize=11, color=GREY)
            else:
                axr.barh(y, b, height=0.6, color=ORANGE)
                axr.text(b + 0.003, y, r["breakdown_label"] + (" →" if r["breakdown_above_grid"]
                                                                 else ""),
                         va="center", fontsize=11, bbox=box)
        sh, bh = float(d["sigma_H"][0]), float(d["abs_bias_H"][0])
        axl.axvline(sh, color="black", ls="--", lw=1.4)
        axl.text(sh + 0.004, d.height - 0.35, f"H, σ = {sh:.3f}", fontsize=11, va="center")
        axr.axvline(bh, color="black", ls="--", lw=1.4)
        axr.text(bh + 0.002, d.height - 0.35, f"H, |bias| = {bh:.3f}", fontsize=11,
                 va="center")
        axl.set_xlabel("highest informative noise σ (synthetic, best case)")
        axr.set_xlabel("breakdown bias B of the reading (real data)")
        axl.set_title("noise a narrow range tolerates")
        axr.set_title("bias the reading survives")
        save(fig, "13_data_requirement", d)

    # figure 14
    if (ART / "exp4_learned_potential" / "cnn_loss_trace.csv").exists():
        from matplotlib.ticker import MaxNLocator
        d = cnn_trace_data()
        fits = d.select(["fit", "layers", "channels"]).unique(maintain_order=True).rows()
        fig, axes = plt.subplots(4, 4, figsize=(15, 12), sharex=True)
        for ax, (fit, lay, ch) in zip(axes.flat, fits):
            q = d.filter((pl.col("fit") == fit) & (pl.col("layers") == lay) & (pl.col("channels") == ch)).sort("epoch")
            ax.plot(q["epoch"], q["train_loss_weighted"], ls="--", color=GREY, lw=1.8, label="training")
            ax.plot(q["epoch"], q["val_loss_weighted"], marker="o", ms=4, color=BLUE, lw=2, label="validation")
            ax.axvline(int(q["best_epoch"][0]), color=VERMILION, lw=1.4)
            ax.set_title(f"selection {lay} × {ch}" if fit == "selection" else f"fold {fit}", fontsize=12)
            ax.tick_params(labelsize=10)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        for ax in axes[-1]:
            ax.set_xlabel("epoch", fontsize=12)
        for ax in axes[:, 0]:
            ax.set_ylabel("weighted pinball loss", fontsize=11)
        axes[0, 0].legend(frameon=False, fontsize=10)
        n = len(fits)
        save(fig, "14_exp4_n1_loss_curves", d, n=n)

    # figures 15-17 (Experiment 4)
    if (EXP4 / "lookalike_scores.csv").exists():
        d = exp4_lookalike_data()
        models = ["F", "H", "L1", "L2", "N1"]
        cols = {"F": GREY, "H": GREEN, "L1": BLUE, "L2": SKY, "N1": ORANGE}
        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        for i, unit in enumerate(["three-area aggregate", "pooled area rows"]):
            for j, met in enumerate(["sigma", "bias"]):
                ax = axes[i, j]
                for k, m in enumerate(models):
                    q = d.filter((pl.col("unit") == unit) & (pl.col("model") == m) & pl.col("metric").str.starts_with(met))
                    if q.height == 0:
                        continue
                    r = q.row(0, named=True)
                    ax.errorbar(k, r["value"], yerr=[[r["value"] - r["lo"]], [r["hi"] - r["value"]]],
                                fmt="o", ms=9, capsize=6, lw=2, color=cols[m])
                ax.set_xticks(range(len(models)), models)
                if met == "bias":
                    ax.axhline(0, color=GREY, lw=1)
                    for v in (-0.02, 0.02):
                        ax.axhline(v, color="black", ls="--", lw=1)
                    ax.set_ylabel("mean of log(G / Â)")
                else:
                    ax.set_ylabel("σ of log(G / Â)")
                    ax.set_ylim(bottom=0)
                ax.set_title(unit)
        save(fig, "15_exp4_lookalike_error", d, tol=0.02)

    if (EXP4 / "bias_budget.csv").exists():
        d = exp4_bias_data()
        units = ["50Hertz", "Amprion", "TransnetBW", "pooled area rows", "three-area aggregate"]
        fig, ax = plt.subplots(figsize=(11, 5.5))
        for k, u in enumerate(units):
            for off, arm, filled in ((-0.12, "trimmed", True), (0.12, "untrimmed", False)):
                r = d.filter((pl.col("unit") == u) & pl.col("arm").str.starts_with(arm)).row(0, named=True)
                ax.errorbar(k + off, r["corrected"], yerr=[[r["corrected"] - r["corrected_lo"]],
                                                          [r["corrected_hi"] - r["corrected"]]],
                            fmt="o", ms=9, capsize=6, lw=2, color=VERMILION,
                            mfc=VERMILION if filled else "white",
                            label=(("trimmed (primary)" if filled else "untrimmed (sensitivity)") if k == 0 else None))
        ax.axhline(0, color=GREY, lw=1)
        ax.set_xticks(range(len(units)), ["50Hertz", "Amprion", "TransnetBW", "pooled\narea rows", "three-area\naggregate"])
        ax.set_ylabel("corrected mean of log(H / A)")
        ax.set_title("Descriptive only: H against the learned potential at negative prices (S2 failed)")
        ax.legend(frameon=False)
        save(fig, "16_exp4_bias_descriptive", d)

    if (EXP4 / "domain_scores.parquet").exists():
        d = exp4_overlap_data()
        fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), sharey=True)
        for ax, area in zip(axes, ["50Hertz", "Amprion", "TransnetBW"]):
            for name, col in (("clean", BLUE), ("target", VERMILION)):
                q = d.filter((pl.col("area") == area) & (pl.col("set") == name))
                ax.bar(q["p_lo"].to_numpy(), q["share"].to_numpy(), width=0.02, align="edge",
                       color=col, alpha=0.55, label=name)
            ax.axvline(0.99, color="black", ls=":", lw=1.4)
            ax.set_title(area)
            ax.set_xlabel("domain score p")
        axes[0].set_ylabel("share of the set")
        axes[0].legend(frameon=False)
        save(fig, "17_exp4_overlap", d, thr=0.99)
    return written


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT_DIR))
    args = ap.parse_args()
    for p in make_all(Path(args.out)):
        if p.suffix == ".png":
            print(p)


if __name__ == "__main__":
    main()
