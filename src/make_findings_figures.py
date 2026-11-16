"""Findings figures F1-F8 for the supervisor share (Phase S5).

    python -m src.make_findings_figures                  # writes figures/findings/
    python -m src.make_findings_figures --out demo/output/findings

Every plotted value is read from a committed file in `results/` or `artifacts/`, or,
for F1 only, from the processed panel that the kill test reads. None is typed in. For
each figure the script writes a 300-dpi PNG, the exact plotted data as CSV, and a
caption file naming the source files and columns. `tests/test_findings_figures.py`
rebuilds the data tables and compares them with the artifacts and with the committed
CSVs.

The data builders (`f1_data` ... `f8_data`) return polars frames and do no plotting,
so the test can call them without matplotlib.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polars as pl

from src.identification.summarise_p3 import load

REPO_ROOT = Path(__file__).resolve().parents[1]
RES = REPO_ROOT / "results"
ART = REPO_ROOT / "artifacts"
PANEL = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"
OUT_DIR = REPO_ROOT / "figures" / "findings"

#: Okabe-Ito, colour-blind safe. One meaning per colour across all figures.
BLUE, ORANGE, GREEN, VERMILION, SKY, PURPLE, GREY = (
    "#0072B2", "#E69F00", "#009E73", "#D55E00", "#56B4E9", "#CC79A7", "#7F7F7F")

#: Kill-test window, `docs/04_rq1_killtest_note_v3.md` (the panel now starts 2024-01-01).
KILL_TEST_START = "2025-10-01"
NEG_BANDS = ("<= -50", "-50 to -20", "-20 to -5", "-5 to 0")
Q0B_BANDS = ("band <=-50", "band [-50,-20]", "band [-20,-5]", "band (-5,0)")
Q0B_POSITIVE = "price >= 0"          # the reference set clause A compares against
Q0B_AREA = "50Hertz+Amprion+TransnetBW"
LAMS = ("L1", "L2", "L3", "L4", "L5", "L6", "L7")
LAM_LABEL = {"L1": "λ₁ fleet", "L2": "λ₂ deep", "L3": "λ₃ cohort", "L4": "λ₄ group",
             "L5": "λ₅ energy", "L6": "λ₆ contrast", "L7": "λ₇ member"}


# --------------------------------------------------------------------------- data

def f1_day() -> str:
    """The kill test's largest-error event-day (rank 1 by total negative-QH error, DE)."""
    worst = pl.read_csv(RES / "02_worst_days_de.csv").filter(pl.col("rank_by_total_error") == 1)
    return worst["berlin_date"][0]


def f1_data() -> pl.DataFrame:
    """That day, onshore, 50Hertz + Amprion + TransnetBW: forecast F, actual G, projection H.

    Read through Q0b's own loader, so H, F, G and R are exactly the series Q0b used. H is
    published per control area and onshore only; TenneT is excluded from the aggregate
    (T-D(vii)), so all three lines cover the same three-area onshore fleet.
    """
    import contextlib
    import io
    from src.potential.q0b_validate_h import AGG_NAME, load_frames
    with contextlib.redirect_stdout(io.StringIO()):          # the loader prints progress
        agg = load_frames("quality-assured")[AGG_NAME]
    day = f1_day()
    return (agg.filter(pl.col("berlin_date") == day).sort("ts_utc")
               .select(pl.from_epoch("ts_utc", time_unit="ms").alias("ts_utc"), "berlin_date",
                       pl.col("da_onshore_mw").alias("day_ahead_forecast_mw"),
                       pl.col("act_onshore_mw").alias("actual_mw"),
                       pl.col("hr_mw").alias("projection_h_mw"),
                       pl.col("rd_mw").alias("redispatch_mw"),
                       "price_eur_mwh"))


def f2_data() -> pl.DataFrame:
    """Kill-test bias by negative price band, DE."""
    b = pl.read_csv(RES / "02_bias_by_price_band.csv").filter(
        (pl.col("area") == "DE") & pl.col("price_band_eur_mwh").is_in(NEG_BANDS))
    order = {k: i for i, k in enumerate(NEG_BANDS)}
    return (b.with_columns(pl.col("price_band_eur_mwh").replace_strict(order).alias("_o"))
             .sort("_o").drop("_o")
             .select(["price_band_eur_mwh", "qhs", "days", "mean_e_mw", "ci_lo_mw", "ci_hi_mw"]))


def f2_sample() -> pl.DataFrame:
    return pl.read_csv(RES / "01_sample_size.csv").filter(
        pl.col("metric").is_in(["negative QHs (price < 0)", "event-days (>=1 negative QH)"]))


def f3_data() -> pl.DataFrame:
    """Q0b gap share (P - G - R) / P per negative band, P = projection H or forecast F."""
    sets = (*Q0B_BANDS, Q0B_POSITIVE)
    g = pl.read_csv(ART / "Q0b" / "q0b_gap_shares.csv").filter(
        (pl.col("series") == "quality-assured") & (pl.col("area") == Q0B_AREA)
        & pl.col("set").is_in(sets))
    order = {k: i for i, k in enumerate(sets)}
    return (g.with_columns(pl.col("set").replace_strict(order).alias("_o"))
             .sort(["_o", "estimator"], descending=[False, True]).drop("_o")
             .select(["set", "estimator", "n_qh", "n_days",
                      *(pl.col(c).cast(pl.Float64) for c in ("gap_share", "ci_lo", "ci_hi"))]))


def f4_data() -> pl.DataFrame:
    """Coverage of the known truth, every synthetic setting with a truth."""
    rows = []
    for arm, f in (("P3 Arm O (exact potential)", "p3_synthetic_arm_o.csv"),
                   ("P3 Arm D (estimated potential)", "p3_synthetic_arm_d.csv")):
        d = load(ART / "P3" / f).filter(pl.col("cov").is_not_null())
        rows.append({"study": "P3", "setting": arm, "n_scored": d.height,
                     "n_covered": int(d["cov"].sum()), "coverage": float(d["cov"].mean()),
                     "source": f"artifacts/P3/{f}, column cov"})
    q1 = (pl.read_csv(ART / "Q1" / "q1_summary_by_level.csv")
            .group_by(["noise", "sigma"]).agg(pl.col("level_coverage").first())
            .sort(["noise", "sigma"], descending=[True, False]))
    for r in q1.iter_rows(named=True):
        rows.append({"study": "Q1", "setting": f"Q1 {r['noise']} σ = {r['sigma']:g}",
                     "n_scored": None, "n_covered": None, "coverage": r["level_coverage"],
                     "source": "artifacts/Q1/q1_summary_by_level.csv, column level_coverage"})
    q6 = (pl.read_csv(ART / "Q6" / "q6b_summary.csv").filter(pl.col("table") == "levels")
            .sort(["sigma", "sigma_r"]))
    for r in q6.iter_rows(named=True):
        rows.append({"study": "Q6b",
                     "setting": f"Q6b σ = {r['sigma']:g}, σ_r = {r['sigma_r']:g}",
                     "n_scored": None, "n_covered": None, "coverage": r["coverage"],
                     "source": "artifacts/Q6/q6b_summary.csv, column coverage"})
    return pl.DataFrame(rows)


def f5_data() -> pl.DataFrame:
    """Median width per functional, Arm O seed 45 (exact) vs Arm D (estimated)."""
    o = load(ART / "P3" / "p3_synthetic_arm_o.csv").filter(pl.col("seed") == 45)
    d = load(ART / "P3" / "p3_synthetic_arm_d.csv")
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


def f6_data() -> pl.DataFrame:
    """Q1 share of cells informative, per functional, against i.i.d. noise σ."""
    return (pl.read_csv(ART / "Q1" / "q1_summary_by_level.csv")
              .filter(pl.col("noise") == "iid")
              .select(["lam", "sigma", "n_cells", "n_informative", "share_informative"])
              .sort(["lam", "sigma"]))


def anchors() -> dict:
    a = pl.read_csv(ART / "Q0" / "q0_anchors.csv")
    h = a.filter((pl.col("anchor") == "H") & pl.col("area").str.starts_with("DE excl. TenneT")
                 & (pl.col("sample") == "price >= 0"))["sigma"]
    t = a.filter((pl.col("anchor") == "T") & (pl.col("area") == "DE")
                 & (pl.col("series") == "onshore") & (pl.col("sample") == "price >= 0"))["sigma"]
    assert h.len() == 1 and t.len() == 1
    return {"H": float(h[0]), "T": float(t[0])}


def anchors_bias_h() -> float:
    a = pl.read_csv(ART / "Q0" / "q0_anchors.csv")
    h = a.filter((pl.col("anchor") == "H") & pl.col("area").str.starts_with("DE excl. TenneT")
                 & (pl.col("sample") == "price >= 0"))["bias"]
    assert h.len() == 1
    return float(h[0])


def f7_data() -> pl.DataFrame:
    """Share informative per functional: Q1 synthetic at Anchor H vs Q5 real with H."""
    q1 = (pl.read_csv(ART / "Q1" / "q1_summary_by_level.csv")
            .filter((pl.col("noise") == "iid") & (pl.col("sigma") == 0.066))
            .select(["lam", pl.col("n_cells").alias("q1_n"),
                     pl.col("n_informative").alias("q1_n_informative"),
                     pl.col("share_informative").alias("q1_share")]))
    q5 = pl.read_csv(ART / "Q5" / "q5_real.csv", infer_schema_length=0)
    # Q5 functional-months: `informative` is True/False where the set is defined and empty
    # where it is not; undefined months are counted separately, never as "not informative".
    q5 = (q5.filter((pl.col("setting") == "main") & (pl.col("period") != "window")
                    & (pl.col("potential") == "H")
                    & pl.col("c_hat").str.contains("recalibrated").not_())
            .group_by("lam").agg(
                pl.len().alias("q5_months"),
                pl.col("informative").is_in(["True", "False"]).sum().alias("q5_n"),
                (pl.col("informative") == "True").sum().alias("q5_n_informative")))
    return (q1.join(q5, on="lam", how="full", coalesce=True)
              .with_columns((pl.col("q5_months") - pl.col("q5_n")).alias("q5_n_undefined"),
                            pl.when(pl.col("q5_n") > 0)
                              .then(pl.col("q5_n_informative") / pl.col("q5_n"))
                              .otherwise(None).alias("q5_share"))
              .sort("lam"))


FLEET, COHORT = ("L1", "L2"), ("L3", "L4", "L6", "L7")


def f9_data() -> pl.DataFrame:
    """Q1 median interval width and interquartile range per functional against i.i.d. σ."""
    return (pl.read_csv(ART / "Q1" / "q1_summary_by_level.csv")
              .filter((pl.col("noise") == "iid") & pl.col("lam").is_in(FLEET + COHORT))
              .with_columns(pl.when(pl.col("lam").is_in(FLEET)).then(pl.lit("fleet"))
                              .otherwise(pl.lit("cohort")).alias("group"))
              .select(["group", "lam", "sigma", "n_cells", "median_width", "q25_width",
                       "q75_width"])
              .sort(["group", "lam", "sigma"], descending=[True, False, False]))


V2_THRESHOLD = {"L1": None, "L2": 0.5, "L3": 0.75, "L6": 0.5}


def f10_data() -> pl.DataFrame:
    """Phase V2: bias-robust full-window interval S_B against the budget B, with breakdown."""
    iv = pl.read_csv(ART / "V" / "v2_robust_intervals.csv")
    bd = pl.read_csv(ART / "V" / "v2_breakdown.csv", infer_schema_length=0).select(
        "lam", pl.col("breakdown_B").alias("breakdown_B"))
    return iv.join(bd, on="lam").sort(["lam", "B"])


def f8_data() -> pl.DataFrame:
    """Q6a between-day variance per testable cell against the measurement-only ceiling."""
    num = ("v_between", "v_meas", "excess_ci_lo", "excess_ci_hi", "sigma_h")
    c = (pl.read_csv(ART / "Q6" / "q6a_cells.csv")
           .filter(pl.col("primary") & pl.col("testable"))
           .with_columns(*(pl.col(k).cast(pl.Float64) for k in num)))
    return (c.with_columns((pl.col("v_meas") + pl.col("excess_ci_lo")).alias("v_between_ci_lo"),
                           (pl.col("v_meas") + pl.col("excess_ci_hi")).alias("v_between_ci_hi"))
             .select(["price_band", "run_band", "n_event_days", "v_between",
                      "v_between_ci_lo", "v_between_ci_hi", "v_meas", "excess_ci_lo",
                      "excess_ci_hi", "sigma_h"]))


# ------------------------------------------------------------------------- figures

CAPTIONS = {
    "F1_problem_schematic": (
        "{day} (Easter Sunday) is the largest-error negative-price event-day of the kill-test "
        "window, not a typical day: it carries {share:.1%} of all negative-quarter-hour "
        "forecast error. Onshore wind, 50Hertz + Amprion + TransnetBW (TenneT excluded, "
        "T-D(vii)): TSO day-ahead forecast F, actual output G and the quality-assured "
        "projection H (Online-Hochrechnung), with the day-ahead price on the right axis. "
        "Shaded: negative-price quarter-hours.",
        "Day chosen as rank 1 in results/02_worst_days_de.csv (columns rank_by_total_error, "
        "share_of_total_negative_qh_error; ranked on DE total wind). Series from "
        "src/potential/q0b_validate_h.load_frames('quality-assured'), the three-area "
        "aggregate Q0b uses: da_onshore_mw, act_onshore_mw, hr_mw, rd_mw, price_eur_mwh. "
        "Inputs data/processed/panel_qh.parquet and data/raw/netztransparenz/"
        "hochrechnung_wind_onshore_qualitaetsgesichert/ are not in git."),
    "F2_forecast_bias_by_price_band": (
        "Kill test: mean forecast error (actual minus day-ahead forecast) by negative price "
        "band, Germany, with 95% event-day bootstrap intervals. Window 2025-10-01 to "
        "2026-10-28.",
        "results/02_bias_by_price_band.csv, rows area = DE, columns price_band_eur_mwh, "
        "mean_e_mw, ci_lo_mw, ci_hi_mw, qhs, days; totals from results/01_sample_size.csv, "
        "column value."),
    "F3_projection_vs_forecast_gap_by_band": (
        "Q0b: share of the potential estimate not produced once redispatch is removed, "
        "(P − G − R) / P, by negative price band and, as reference, over all quarter-hours "
        "with price ≥ 0, for the quality-assured projection H and the day-ahead forecast F. "
        "50Hertz + Amprion + TransnetBW (TenneT excluded), 95% intervals.",
        "artifacts/Q0b/q0b_gap_shares.csv, rows series = quality-assured, area = "
        "50Hertz+Amprion+TransnetBW, set = band ... and price >= 0, columns estimator, "
        "gap_share, ci_lo, ci_hi."),
    "F4_coverage_never_fails": (
        "Coverage of the known truth by the identified sets in every synthetic setting that "
        "has a truth: P3 Arms O and D, every Q1 noise level, every Q6b setting. Dashed line: "
        "the pre-registered 95% target (binding for P3 Arm O).",
        "artifacts/P3/p3_synthetic_arm_o.csv and p3_synthetic_arm_d.csv, column cov (via "
        "src/identification/summarise_p3.load); artifacts/Q1/q1_summary_by_level.csv, column "
        "level_coverage; artifacts/Q6/q6b_summary.csv, rows table = levels, column coverage."),
    "F5_exact_vs_estimated_potential": (
        "P3: median width of the identified set per functional when the potential is exact "
        "(Arm O, seed 45) and when it is estimated (Arm D), log scale.\n"
        "λ₅ is omitted: it is a counterfactual energy in GWh, not a share of potential, so it "
        "cannot sit on this axis.",
        "artifacts/P3/p3_synthetic_arm_o.csv (seed = 45) and p3_synthetic_arm_d.csv, rows "
        "feasible, column width, median per lam."),
    "F6_noise_dial": (
        "Q1: share of the 54 synthetic cells in which each functional is informative, against "
        "i.i.d. noise σ in the potential. Vertical lines: the statutory projection H (σ is a "
        "lower bound on its error) and the TSO day-ahead forecast. λ₄ and λ₅ coincide at most "
        "levels, so they are drawn with different markers and a small horizontal offset. "
        "λ₇, one member of an exactly collinear pair, is not identified even at σ = 0: "
        "informative in {l7_k} of {l7_n} cells.",
        "artifacts/Q1/q1_summary_by_level.csv, rows noise = iid, columns lam, sigma, "
        "share_informative; anchors from artifacts/Q0/q0_anchors.csv, column sigma (H: area "
        "DE excl. TenneT, price >= 0; T: area DE, onshore, price >= 0)."),
    "F7_synthetic_vs_real": (
        "Share informative per functional: synthetic cells at Anchor H's noise (Q1, "
        "σ = 0.066) against real functional-months with H as the potential (Q5, main "
        "setting, monthly arms). Each bar is labelled k/n. Hatched grey bars are real "
        "functional-months where the identified set is undefined (n/a), shown as a share of "
        "all months; they are not counted as uninformative.",
        "artifacts/Q1/q1_summary_by_level.csv, rows noise = iid, sigma = 0.066, column "
        "share_informative; artifacts/Q5/q5_real.csv, rows setting = main, period != window, "
        "potential = H, c_hat not recalibrated; informative True/False defined, empty undefined."),
    "F9_width_vs_noise": (
        "Q1: median width of the identified set (line) and interquartile range (band) across "
        "the 54 synthetic cells, against i.i.d. noise σ in the potential, on the tested grid "
        "only. Left: fleet functionals; right: cohort functionals. Log scale. Vertical lines: "
        "the statutory projection H (σ is a lower bound on its error) and the TSO forecast. "
        "Dashed horizontal line: 0.25, the informative limit for λ₁–λ₄ and λ₇ (λ₆'s is 0.5). "
        "λ₅ is omitted: it is an energy in GWh, not a share of potential.",
        "artifacts/Q1/q1_summary_by_level.csv, rows noise = iid, lam in L1-L4, L6, L7, columns "
        "sigma, median_width, q25_width, q75_width; anchors from artifacts/Q0/q0_anchors.csv as "
        "in F6."),
    "F10_bias_breakdown": (
        "Phase V2: the bias-robust full-window interval with the projection H, main setting, "
        "for the four functionals with a reading in the conclusions table, against the bias "
        "budget B (the hull over every constant multiplicative bias |b| ≤ B on a 0.01 grid). "
        "Dashed line: the bound the reading needs (λ₁: width below 0.25, shown as the "
        "interval itself). Vertical line: the breakdown B, the smallest B at which the reading "
        "no longer holds. Dotted line, for scale only: |−0.0472|, the projection's measured "
        "bias on price ≥ 0 quarter-hours; its bias during negative prices is not measured.",
        "artifacts/V/v2_robust_intervals.csv (columns lam, B, lo, hi, width) and "
        "artifacts/V/v2_breakdown.csv (column breakdown_B); scale line from "
        "artifacts/Q0/q0_anchors.csv, column bias (anchor H, DE excl. TenneT, price >= 0)."),
    "F8_day_heterogeneity": (
        "Q6a: between-day variance of the curtailed share per testable cell (95% interval) "
        "against the variance that measurement error at Anchor H's σ alone would produce.",
        "artifacts/Q6/q6a_cells.csv, rows primary and testable, columns v_between, v_meas, "
        "excess_ci_lo, excess_ci_hi (interval = v_meas + excess CI), price_band, run_band."),
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

    # F1
    if PANEL.exists():
        d = f1_data()
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
        save(fig, "F1_problem_schematic", d, day=d["berlin_date"][0],
             share=float(worst["share_of_total_negative_qh_error"][0]))

    # F2
    d, s = f2_data(), f2_sample()
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
    save(fig, "F2_forecast_bias_by_price_band", d)

    # F3
    d = f3_data()
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
    save(fig, "F3_projection_vs_forecast_gap_by_band", d)

    # F4
    d = f4_data()
    colours = {"P3": BLUE, "Q1": GREEN, "Q6b": PURPLE}
    fig, ax = plt.subplots(figsize=(9, 0.42 * d.height + 1.8))
    y = np.arange(d.height)[::-1]
    ax.scatter(d["coverage"].to_numpy(), y, s=70,
               c=[colours[s] for s in d["study"]], zorder=3)
    ax.axvline(0.95, color=VERMILION, ls="--", lw=1.6, label="95% target")
    ax.set_yticks(y, d["setting"].to_list())
    ax.set_xlim(0.9, 1.01)
    ax.set_xlabel("coverage of the known truth")
    ax.set_title("Coverage never falls below target")
    ax.legend(frameon=False, loc="lower left")
    save(fig, "F4_coverage_never_fails", d)

    # F5
    d = f5_data()
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
    save(fig, "F5_exact_vs_estimated_potential", d)

    # F6
    d, anc = f6_data(), anchors()
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
    for k, ls, lab in (("H", ":", "statutory projection H\n(lower bound)"),
                       ("T", "--", "TSO forecast")):
        ax.axvline(anc[k], color="black", ls=ls, lw=1.3)
        ax.text(anc[k], 1.04, f"{lab}\nσ = {anc[k]:.3f}", ha="center", va="bottom", fontsize=11)
    ax.set_ylim(-0.03, 1.1)
    ax.set_xlabel("noise in the potential, σ")
    ax.set_ylabel("share of cells informative")
    ax.set_title("Noise dial: fleet stays informative, cohorts do not", pad=58)
    ax.legend(frameon=False, fontsize=11, ncol=2, loc="center right")
    l7 = d.filter((pl.col("lam") == "L7") & (pl.col("sigma") == 0.0))
    save(fig, "F6_noise_dial", d.with_columns(pl.lit(anc["H"]).alias("anchor_h_sigma"),
                                              pl.lit(anc["T"]).alias("anchor_t_sigma")),
         l7_k=int(l7["n_informative"][0]), l7_n=int(l7["n_cells"][0]))

    # F7
    d = f7_data()
    fig, ax = plt.subplots(figsize=(11, 6))
    x = np.arange(d.height)
    w = 0.27
    q1s = d["q1_share"].to_numpy()
    ax.bar(x - w, q1s, w, color=SKY, label="synthetic at Anchor H (Q1, cells)")
    q5s = d["q5_share"].to_numpy().astype(float)
    ax.bar(x, np.nan_to_num(q5s), w, color=VERMILION, label="real data with H (Q5, months)")
    und = (d["q5_n_undefined"] / d["q5_months"]).to_numpy()
    ax.bar(x + w, und, w, color="white", edgecolor=GREY, hatch="//",
           label="real data: undefined (n/a)")
    for i, r in enumerate(d.iter_rows(named=True)):
        ax.text(x[i] - w, q1s[i] + 0.02, f"{r['q1_n_informative']}/{r['q1_n']}",
                ha="center", fontsize=10, rotation=90, va="bottom")
        lab = (f"{r['q5_n_informative']}/{r['q5_n']}" if r["q5_n"] else "n/a")
        ax.text(x[i], np.nan_to_num(q5s[i]) + 0.02, lab, ha="center", fontsize=10,
                rotation=90, va="bottom")
        if r["q5_n_undefined"]:
            ax.text(x[i] + w, und[i] + 0.02, f"{r['q5_n_undefined']}/{r['q5_months']} n/a",
                    ha="center", fontsize=10, rotation=90, va="bottom")
    ax.set_xticks(x, [LAM_LABEL[l] for l in d["lam"]], rotation=20)
    ax.set_ylim(0, 1.5)
    ax.set_yticks(np.linspace(0, 1, 6))
    ax.set_ylabel("share informative\n(cells: synthetic; months: real)")
    ax.set_title("Real data is far less informative than the synthetic benchmark")
    ax.legend(frameon=False, loc="upper center", ncol=3, fontsize=11)
    save(fig, "F7_synthetic_vs_real", d)

    # F8
    d = f8_data()
    fig, ax = plt.subplots(figsize=(10, 5.5))
    x = np.arange(d.height)
    v = d["v_between"].to_numpy()
    ax.errorbar(x, v, yerr=[v - d["v_between_ci_lo"].to_numpy(), d["v_between_ci_hi"].to_numpy() - v],
                fmt="o", color=BLUE, ms=9, capsize=5, lw=2, label="between-day variance")
    ax.scatter(x, d["v_meas"].to_numpy(), marker="_", s=600, color=VERMILION, lw=3,
               label=f"measurement only (σ = {d['sigma_h'][0]:g})")
    ax.set_yscale("log")
    ax.set_xticks(x, [f"{p}\n{r}" for p, r in zip(d["price_band"], d["run_band"])], fontsize=11)
    ax.set_xlabel("price band (€/MWh) and run length")
    ax.set_ylabel("variance of curtailed share (log)")
    ax.set_title("Days differ more than measurement error explains")
    ax.legend(frameon=False)
    save(fig, "F8_day_heterogeneity", d)

    # F9
    d, anc = f9_data(), anchors()
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
        for k, lab in (("H", "projection H\n(lower bound)"), ("T", "TSO\nforecast")):
            ax.text(anc[k] + 0.004, 0.03, lab, transform=ax.get_xaxis_transform(),
                    ha="left", va="bottom", fontsize=10)
    fig.suptitle("Intervals widen with noise; cohort intervals cross the informative limit first",
                 fontsize=15)
    save(fig, "F9_width_vs_noise", d.with_columns(pl.lit(anc["H"]).alias("anchor_h_sigma"),
                                                  pl.lit(anc["T"]).alias("anchor_t_sigma")))

    # F10
    if (ART / "V" / "v2_robust_intervals.csv").exists():
        d = f10_data()
        hb = abs(anchors_bias_h())
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
        save(fig, "F10_bias_breakdown", d.with_columns(pl.lit(hb).alias("abs_bias_h_positive_prices")))
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
