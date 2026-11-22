"""C1 conclusions table: what public German wind data can and cannot tell us.

    python -m src.experiments.exp3_results_table            # writes the CSV and the markdown note
    python -m src.experiments.exp3_results_table --print    # prints the table, writes nothing

Rows, columns and the verdict rule are fixed in `docs/C0_preregistration.md` (commit
`C0_COMMIT`), committed before this script existed. Everything is read from committed
artifacts; nothing is fitted. `tests/test_conclusions_table.py` rebuilds both outputs and
compares them byte for byte, and `tests/test_reported_numbers.py` checks every cell.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
ART = REPO_ROOT / "artifacts"
ARCHIVED_ART = REPO_ROOT / "archive" / "artifacts"   # Q6 is archived; its verdict row stays
CSV_OUT = REPO_ROOT / "artifacts" / "exp3_german_application" / "results_table.csv"
#: Phase 3 (22 Nov 2026), new files: the readings V2 tests, apart from the B = 0 intervals,
#: and the quarter-hours and event days behind each functional in the full window.
READINGS_OUT = REPO_ROOT / "artifacts" / "exp3_german_application" / "readings_table.csv"
SAMPLES_OUT = REPO_ROOT / "artifacts" / "exp3_german_application" / "sample_sizes.csv"
MD_OUT = REPO_ROOT / "archive" / "docs" / "C1_conclusions_table.md"   # the archived C1 note, rebuilt byte for byte
C0_COMMIT = "a67f69a"

GRID = (0.0, 0.033, 0.066, 0.12, 0.18, 0.25, 0.35)
SIGMA_H, SIGMA_T = 0.066, 0.18          # grid levels for Anchor H and Anchor T (0.1806)
# SIGMA_H: the operational series' value; the quality-assured series gives σ 0.0610 and bias −0.0326 (docs/03).

QUANTITY_ROWS = (
    ("L1", "λ₁", "fleet switched-off share, price in (−20, −5] €/MWh",
     "What share of the whole fleet's potential is switched off at moderately negative prices?"),
    ("L2", "λ₂", "fleet switched-off share, price ≤ −50 €/MWh",
     "The same at deeply negative prices?"),
    ("L3", "λ₃", "pre-2016 cohort response",
     "How does one cohort of turbines respond?"),
    ("L4", "λ₄", "merged θ ≡ 0 group response (collinear pair)",
     "How does an exactly collinear pair of cohorts respond together?"),
    ("L5", "λ₅", "counterfactual energy, GWh, staircase cohort's threshold moved to 0",
     "How much more energy would one cohort hold back under a policy change?"),
    ("L6", "λ₆", "cohort contrast λ₃ − λ₄",
     "Do two cohorts respond differently?"),
    ("L7", "λ₇", "one member of the collinear pair alone",
     "How does one member of the collinear pair respond on its own?"),
)
QTY_EVIDENCE = ("P3 + Q1 (artifacts/Q1/q1_summary_by_level.csv); "
                "Q5 (artifacts/Q5/q5_real.csv)")

READ_FRACTION = 0.25          # Q0 section 5's quarter, reused for the one-sided reading

SUPPORTED = "SUPPORTED RANGE"
NOT_ID = "NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE"
NEEDS = "WOULD NEED A MORE ACCURATE ESTIMATE"


def _fmt(v: float, lam: str) -> str:
    places = 1 if lam == "L5" else 3
    v = round(v, places) + 0.0          # + 0.0 turns a rounded -0.0 into 0.0
    return f"{v:.{places}f}"


def _q1() -> pl.DataFrame:
    return pl.read_csv(ART / "exp1_known_truth_validation" / "noise_dial_summary.csv").filter(pl.col("noise") == "iid")


def _q5_main() -> pl.DataFrame:
    d = pl.read_csv(ART / "exp3_german_application" / "monthly_bounds_cells.csv", infer_schema_length=0)
    return d.filter((pl.col("setting") == "main")
                    & pl.col("c_hat").str.contains("recalibrated").not_())


def _syn(q1: pl.DataFrame, lam: str, sigma: float) -> tuple[int, int]:
    r = q1.filter((pl.col("lam") == lam) & (pl.col("sigma") == sigma))
    return int(r["n_informative"][0]), int(r["n_cells"][0])


def _highest(q1: pl.DataFrame, lam: str) -> tuple[str, float | None]:
    ok = [s for s in GRID if (lambda k, n: k >= n / 2)(*_syn(q1, lam, s))]
    if not ok:
        return "not reached at σ = 0", None
    top = max(ok)
    return ("≥ 0.35 (top of grid)" if top == GRID[-1] else f"{top:g}"), top


def _real(q5: pl.DataFrame, lam: str, pot: str) -> tuple[int, int, int]:
    m = q5.filter((pl.col("lam") == lam) & (pl.col("potential") == pot)
                  & (pl.col("period") != "window"))
    n = int(m["informative"].is_in(["True", "False"]).sum())
    return int((m["informative"] == "True").sum()), n, m.height - n


def _narrowest(q5: pl.DataFrame, lam: str) -> dict:
    m = (q5.filter((pl.col("lam") == lam) & (pl.col("potential") == "H")
                   & (pl.col("period") != "window")
                   & pl.col("informative").is_in(["True", "False"]))
           .with_columns(*(pl.col(c).cast(pl.Float64) for c in ("lo", "hi", "width")))
           .sort(["width", "period"]))
    if m.height == 0:
        return {"narrow_month": "", "narrow_lo": None, "narrow_hi": None, "narrow_width": None}
    r = m.row(0, named=True)
    return {"narrow_month": r["period"], "narrow_lo": r["lo"], "narrow_hi": r["hi"],
            "narrow_width": r["width"]}


def _window(q5: pl.DataFrame, lam: str) -> dict:
    w = q5.filter((pl.col("lam") == lam) & (pl.col("potential") == "H")
                  & (pl.col("period") == "window")
                  & pl.col("informative").is_in(["True", "False"]))
    if w.height == 0:
        return {"window_lo": None, "window_hi": None, "window_width": None,
                "window_informative": None, "window_logical_max": None, "window_reading": ""}
    r = w.row(0, named=True)
    out = {"window_lo": float(r["lo"]), "window_hi": float(r["hi"]),
           "window_width": float(r["width"]), "window_informative": r["informative"] == "True",
           "window_logical_max": float(r["logical_max_width"])}
    return {**out, "window_reading": _window_reading(lam, out)}


def _window_reading(lam: str, w: dict) -> str:
    """Descriptive one-sided reading of a full-window interval (not part of the C0 verdict).

    A response share lives in [0, 1] (λ₆, a difference, in [−1, 1]; λ₅ in [0, its
    logical maximum, GWh]). A bound is read one-sided when it excludes at least a quarter of
    that range at its own end -- the same quarter the informativeness rule uses.
    """
    mx = w["window_logical_max"]
    bottom = -1.0 if lam == "L6" else 0.0
    top = bottom + mx
    lo, hi = w["window_lo"], w["window_hi"]
    unit = " GWh" if lam == "L5" else ""
    if w["window_informative"]:
        return f"informative: between {_fmt(lo, lam)} and {_fmt(hi, lam)}{unit}"
    low_cut = lo - bottom >= READ_FRACTION * mx
    high_cut = top - hi >= READ_FRACTION * mx
    if low_cut and high_cut:
        return (f"not informative, but excludes both ends: between {_fmt(lo, lam)} and "
                f"{_fmt(hi, lam)}{unit}")
    if low_cut:
        return f"one-sided: at least {_fmt(lo, lam)}{unit}"
    if high_cut:
        return f"one-sided: at most {_fmt(hi, lam)}{unit}"
    return "no reading: neither bound excludes a quarter of the range"


def quantity_rows() -> list[dict]:
    q1, q5 = _q1(), _q5_main()
    rows = []
    for lam, sym, qty, question in QUANTITY_ROWS:
        tk, tn = _syn(q1, lam, SIGMA_T)
        hk, hn = _syn(q1, lam, SIGMA_H)
        hi_txt, _ = _highest(q1, lam)
        fk, fn, fu = _real(q5, lam, "F")
        rk, rn, ru = _real(q5, lam, "H")
        verdict = SUPPORTED if rn >= 1 and rk >= rn / 2 else NOT_ID
        below = [s for s in GRID if s < SIGMA_H and (lambda k, n: k >= n / 2)(*_syn(q1, lam, s))]
        at_h = hk >= hn / 2
        sub, sub_sigma, literal = "", None, ""
        if verdict == NOT_ID and below and not at_h:
            sub_sigma = max(below)
            sub = f"{NEEDS}: σ ≤ {sub_sigma:g}, within the tested synthetic conditions"
        elif verdict == NOT_ID and below and at_h:
            literal = "would carry the sub-label under the literal reading of C0 §4 rule 3"
        if verdict == SUPPORTED:
            dep = "real-data months with H; projection not ground truth"
        elif sub:
            dep = f"an available-power estimate with σ ≤ {sub_sigma:g} (Q1 synthetic cells)"
        elif not below:
            dep = "collinear split: not informative in half the cells even with exact potential"
        else:
            dep = ("Q1: already informative at Anchor H's σ in synthetic cells; "
                   "real data falls short of that (Q6 explores why)")
        if rn == 0:
            dep += "; undefined in every real month"
        rows.append({
            "row": sym, "kind": "quantity", "question": question, "quantity": qty,
            "evidence": QTY_EVIDENCE,
            "syn_T_k": tk, "syn_T_n": tn, "syn_H_k": hk, "syn_H_n": hn,
            "highest_sigma_half": hi_txt,
            "real_F_k": fk, "real_F_n": fn, "real_F_undefined": fu,
            "real_H_k": rk, "real_H_n": rn, "real_H_undefined": ru,
            **_narrowest(q5, lam), **_window(q5, lam),
            "verdict": verdict, "sub_label": sub, "literal_reading_note": literal,
            "depends_on": dep, "lam": lam, "c0_commit": C0_COMMIT,
        })
    return rows


def evidence_rows() -> list[dict]:
    q1 = _q1()
    head = pl.read_csv(ART / "exp1_known_truth_validation" / "noise_dial_headline.csv")
    pooled_top = (head.filter(pl.col("statistic") == "pooled_rejection_above_half_max_sigma")
                      .with_columns(pl.col("value").cast(pl.Float64, strict=False))
                      .drop_nulls("value").filter(pl.col("value").is_not_nan())["value"].max())

    def rejected(sigma):
        r = q1.filter(pl.col("sigma") == sigma).drop_nulls("pooled_rejection_split")
        k = (r["pooled_rejection_split"] * r["n_split_scored"]).round().cast(pl.Int64).max()
        return int(k), int(r["n_split_scored"].max())

    pt, ph = rejected(SIGMA_T), rejected(SIGMA_H)
    p0 = rejected(0.0)
    s5 = pl.read_csv(ART / "exp3_german_application" / "monthly_bounds_summary.csv").filter(
        (pl.col("table") == "transitions") & (pl.col("setting") == "main")
        & (pl.col("scope") == "months"))
    n5 = int(s5["n_pairs_both"][0])
    f5 = round(float(s5["share_informative_F"][0]) * n5)
    h5 = round(float(s5["share_informative_H"][0]) * n5)
    up, down = int(s5["n_become_informative"][0]), int(s5["n_reverse"][0])
    und5 = int(s5["n_pairs_neither_arm"][0])
    vb = pl.read_csv(ART / "available_power_estimate" / "adds_back_verdicts.csv", infer_schema_length=0).filter(
        (pl.col("series") == "quality-assured") & (pl.col("area") == "50Hertz+Amprion+TransnetBW"))
    d, dlo, dhi = (float(vb[c][0]) for c in ("D", "D_lo", "D_hi"))
    q6a = pl.read_csv(ARCHIVED_ART / "Q6" / "q6a_cells.csv").filter(pl.col("primary") & pl.col("testable"))
    n6, k6 = q6a.height, int(q6a["heterogeneous"].sum())
    q6b = pl.read_csv(ARCHIVED_ART / "Q6" / "q6b_summary.csv", infer_schema_length=0).filter(
        pl.col("table") == "verdict")["verdict"][0]
    q2 = pl.read_csv(ART / "exp2_bias_robustness_validation" / "bias_dial_coverage.csv").filter(pl.col("dial") == "q2a")

    def q2cov(b):
        r = q2.filter((pl.col("b") - b).abs() < 1e-9).row(0, named=True)
        return r["n_covered"], r["n_scored"]

    q2h, q2t = q2cov(-0.047), q2cov(0.033)
    blank = {k: None for k in ("syn_T_k", "syn_T_n", "syn_H_k", "syn_H_n", "real_F_k", "real_F_n",
                               "real_F_undefined", "real_H_k", "real_H_n", "real_H_undefined",
                               "narrow_lo", "narrow_hi", "narrow_width", "window_lo",
                               "window_hi", "window_width", "window_informative")}
    base = {**blank, "kind": "evidence", "narrow_month": "", "sub_label": "",
            "literal_reading_note": "", "lam": "", "c0_commit": C0_COMMIT}
    return [
        {**base, "row": "pooled",
         "question": "Does a single common response fit, as Hirth assumes?",
         "quantity": "pooled-response rejection in split cells (all functionals)",
         "evidence": "Q1 (artifacts/Q1/q1_summary_by_level.csv, q1_headline.csv); P3 §2.3",
         "syn_T_k": pt[0], "syn_T_n": pt[1], "syn_H_k": ph[0], "syn_H_n": ph[1],
         "highest_sigma_half": f"{pooled_top:g} (exact potential only)",
         "verdict": (f"Synthetic only: {p0[0]} of {p0[1]} split cells reject pooling with an exact "
                     f"potential, none from Anchor H's σ on; the test keeps power above half only "
                     f"with an exact potential. Real data: not evaluated."),
         "depends_on": "an exact potential; not evaluated on real data"},
        {**base, "row": "Q5",
         "question": "Does a better available-power estimate help? (F vs H)",
         "quantity": "all functional-months, main setting",
         "evidence": "Q5 (artifacts/Q5/q5_summary.csv)",
         "real_F_k": f5, "real_F_n": n5, "real_F_undefined": und5,
         "real_H_k": h5, "real_H_n": n5, "real_H_undefined": und5,
         "highest_sigma_half": "—",
         "verdict": (f"{up} of {n5} main-setting functional-months become informative when H "
                     f"replaces F; {down} go the other way."),
         "depends_on": "H as the potential; one award setting shown (main)"},
        {**base, "row": "Q0b",
         "question": "Does the projection behave as if market curtailment is added back?",
         "quantity": "gap share D, negative minus non-negative prices",
         "evidence": "Q0b (artifacts/Q0b/q0b_verdicts.csv)",
         "highest_sigma_half": "—",
         "verdict": (f"ADDS BACK on the deciding aggregate (D = {d:+.4f}, 95% CI "
                     f"[{dlo:+.4f}, {dhi:+.4f}]) and in every control area. Supporting "
                     f"evidence, not ground truth."),
         "depends_on": "TenneT excluded (T-D(vii)); not every gap is voluntary curtailment"},
        {**base, "row": "Q6",
         "question": "Does the synthetic uncertainty model explain real data?",
         "quantity": "between-day heterogeneity (Q6a); synthetic day effect (Q6b)",
         "evidence": "Q6 (artifacts/Q6/q6a_cells.csv, q6b_summary.csv)",
         "highest_sigma_half": "—",
         "verdict": (f"Exploratory. Q6a: PRESENT in {k6} of {n6} testable cells. "
                     f"Q6b: {q6b}."),
         "depends_on": "exploratory diagnostic, not a proposition"},
        {**base, "row": "Q2",
         "question": "Do the bounds stay honest if the available-power estimate is biased?",
         "quantity": "coverage of the known truth at σ = 0, biases of Anchor T and Anchor H",
         "evidence": "Q2 (artifacts/Q2/q2_coverage_by_level.csv); added after C0, see note",
         "syn_T_k": q2t[0], "syn_T_n": q2t[1], "syn_H_k": q2h[0], "syn_H_n": q2h[1],
         "highest_sigma_half": "—",
         "verdict": ("Coverage falls below 95% at every non-zero bias level tested, at every "
                     "noise level; intervals stay narrow and miss the truth. Synthetic only."),
         "depends_on": "an unbiased potential; H's bias at negative prices is not measured"},
    ]


def build() -> pl.DataFrame:
    return pl.DataFrame(quantity_rows() + evidence_rows(), infer_schema_length=None)


#: V0 section 3's readings, written as the test they apply (bias_robust_summary.V2_RULES).
READING_TESTED = {"L1": "λ₁ informative (width < 0.25)", "L2": "λ₂ ≥ 0.50",
                  "L3": "λ₃ ≤ 0.75", "L6": "λ₆ ≤ 0.50"}


def readings_rows() -> list[dict]:
    """Per V2 reading: the largest tested B at which it still holds (every smaller B holding
    too), the interval there, and the breakdown B. Read from the committed V2 summaries."""
    iv = pl.read_csv(ART / "exp3_german_application" / "bias_robust_full_window_intervals.csv")
    bd = {r["lam"]: r for r in pl.read_csv(ART / "exp3_german_application" / "breakdown_points.csv",
                                           infer_schema_length=0).iter_rows(named=True)}
    out = []
    for lam, test in READING_TESTED.items():
        q = iv.filter(pl.col("lam") == lam).sort("B")
        holds = None
        for r in q.iter_rows(named=True):
            if not r["reading_holds"]:
                break
            holds = r
        out.append({"lam": lam, "reading_tested": test, "reading_v0": bd[lam]["reading"],
                    "largest_B_holds": None if holds is None else holds["B"],
                    "lo_at_largest_B": None if holds is None else holds["lo"],
                    "hi_at_largest_B": None if holds is None else holds["hi"],
                    "breakdown_B": bd[lam]["breakdown_B"],
                    "lo_B0": float(bd[lam]["lo_B0"]), "hi_B0": float(bd[lam]["hi_B0"]),
                    "tested_up_to_B": float(q["B"].max())})
    return out


def sample_sizes() -> pl.DataFrame:
    """Quarter-hours and event days behind each functional, full window, setting main, H.

    Rebuilds `real_panel.run_arm`'s design (no fit) and selects each functional's rows the way
    `functionals.py` does; the quarter-hour counts must equal `n_qh_lam` in the committed cells.
    λ₆'s count is min(λ₃, λ₄), the convention of `functionals.difference`, so its rows are λ₃'s.
    """
    import numpy as np
    from src.method.bounds import build_design
    from src.method.real_panel import (COLLINEAR_PAIR, L3_COHORT, L7_COHORT, THREE_AREA,
                                       load_panel)
    p = load_panel(THREE_AREA, "H")
    sel = p["keep"]
    price, bdate = p["price"][sel], p["bdate"][sel]
    theta = p["theta_for"]("main")[:, sel]
    s = (price[None, :] < theta).astype(float)
    depth = np.maximum(0.0, theta - price[None, :]) * s
    design = build_design(s, depth, p["shares"], p["runlen"][:, sel], cohort_ids=p["ids"])
    rows = design.rows
    pr, days = price[rows], bdate[rows]
    k = {c: p["ids"].index(c) for c in p["ids"]}
    m3 = s[k[L3_COHORT], rows] > 0
    m4 = np.zeros(rows.size, dtype=bool)
    for c in COLLINEAR_PAIR:
        m4 |= s[k[c], rows] > 0
    masks = {"L1": (pr > -20.0) & (pr <= -5.0), "L2": pr <= -50.0, "L3": m3, "L4": m4,
             "L5": pr < 0.0, "L6": m3 if m3.sum() <= m4.sum() else m4,
             "L7": s[k[L7_COHORT], rows] > 0}
    return pl.DataFrame([{"lam": lam, "n_qh": int(m.sum()), "n_event_days": int(np.unique(days[m]).size)}
                         for lam, m in masks.items()])


def _kn(k, n, u=None) -> str:
    if k is None:
        return "—"
    return f"{k}/{n}" + (f" ({u} undefined)" if u else "")


def _interval(lo, hi, lam, extra="") -> str:
    if lo is None:
        return "undefined"
    return f"[{_fmt(lo, lam)}, {_fmt(hi, lam)}]{extra}"


def _breakdown_section() -> list[str]:
    """Phase V (`docs/V0_preregistration.md`, `docs/V_results.md`): how much constant bias in
    H each full-window reading survives. Read from `artifacts/V/`; descriptive, no verdict."""
    bd = pl.read_csv(ART / "exp3_german_application" / "breakdown_points.csv", infer_schema_length=0)
    v1 = pl.read_csv(ART / "exp2_bias_robustness_validation" / "bias_robust_coverage.csv", infer_schema_length=None).filter(
        pl.col("criterion_applies").cast(pl.String).str.to_lowercase() == "true")
    sym = {"L1": "λ₁", "L2": "λ₂", "L3": "λ₃", "L6": "λ₆"}
    rule = {"L1": "width ≥ 0.25", "L2": "lower bound < 0.5", "L3": "upper bound > 0.75",
            "L6": "upper bound > 0.5"}
    L = ["## Bias breakdown points (Phase V, descriptive, not part of the C0 verdict)\n",
         "Added 16 November 2026 at the student's instruction, after C0; it changes no verdict. "
         "Each full-window reading above is recomputed with a bias-robust interval: the hull of "
         "the identified sets over every constant multiplicative bias |b| ≤ B in the projection, "
         "on a 0.01 grid (`docs/V0_preregistration.md`). The **breakdown point** is the smallest "
         "B at which the reading no longer holds. On synthetic cells this construction covers the "
         f"truth whenever B ≥ |true bias| ({int(v1['n_covered'].min())} of "
         f"{int(v1['n_scored'].max())} at every such level, `docs/V_results.md` V1).\n",
         "| row | reading tested | breaks when | largest B at which it holds | interval there "
         "| breakdown B | interval at B = 0 | interval at B = 0.15 |",
         "|---|---|---|---|---|---|---|---|"]
    rd = {r["lam"]: r for r in readings_rows()}
    for r in bd.iter_rows(named=True):
        lam = r["lam"]
        b0 = f"[{_fmt(float(r['lo_B0']), lam)}, {_fmt(float(r['hi_B0']), lam)}]"
        b15 = f"[{_fmt(float(r['lo_B015']), lam)}, {_fmt(float(r['hi_B015']), lam)}]"
        h = rd[lam]
        hb = "none" if h["largest_B_holds"] is None else f"{h['largest_B_holds']:.2f}"
        hi = ("—" if h["largest_B_holds"] is None
              else f"[{_fmt(h['lo_at_largest_B'], lam)}, {_fmt(h['hi_at_largest_B'], lam)}]")
        L.append(f"| {sym[lam]} | {h['reading_tested']} | {rule[lam]} | {hb} | {hi} "
                 f"| {r['breakdown_B']} | {b0} | {b15} |")
    L.append("\nThe reading tested is the pre-registered threshold, not the B = 0 bound: λ₂'s "
             "lower bound of 0.525 at B = 0 is not what survives to the largest B shown; the "
             "reading λ₂ ≥ 0.50 is. Columns separated on 22 Nov 2026.")
    from src.experiments.available_power_anchors import primary_h
    q, o = primary_h(), primary_h(series="operational")
    L.append("\nFor scale only: the projection's measured bias on price ≥ 0 quarter-hours is "
             f"{q['bias']:.4f} on the quality-assured series Experiment 3 uses (operational "
             f"series {o['bias']:.4f}, `docs/Q0_preregistration.md` §1; corrected 22 Nov 2026, "
             "this sentence previously gave the operational value alone). "
             "Its bias during negative prices is not measured. "
             "Figure: `figures/findings/F10_bias_breakdown.png`.\n".replace("-0.", "−0."))
    return L


def markdown(df: pl.DataFrame) -> str:
    q = [r for r in df.iter_rows(named=True) if r["kind"] == "quantity"]
    e = [r for r in df.iter_rows(named=True) if r["kind"] == "evidence"]
    counts = {v: sum(r["verdict"] == v for r in q) for v in (SUPPORTED, NOT_ID)}
    n_sub = sum(bool(r["sub_label"]) for r in q)
    lit = [r["row"] for r in q if r["literal_reading_note"]]
    L = []
    L.append("# What public German wind data can and cannot tell us about price-driven "
             "curtailment, Oct 2025 – Oct 2026\n")
    L.append(f"Built by `src/build_conclusions_table.py` from committed artifacts under the rule "
             f"in `docs/C0_preregistration.md` (commit `{C0_COMMIT}`). Machine-readable copy: "
             f"`results/C1_conclusions_table.csv`. Nothing here was fitted for this table.\n")
    L.append("Real-data counts are monthly functional-months in the main award setting, "
             "50Hertz + Amprion + TransnetBW, written informative/defined, with undefined months "
             "counted separately. Synthetic counts are Q1 cells informative out of all cells. "
             "Informative means interval width below a quarter of its logically maximal width "
             "(`docs/Q0_preregistration.md` §5).\n")
    L.append("## Quantities\n")
    L.append("| row | quantity | synthetic, Anchor T (σ 0.18) | synthetic, Anchor H (σ 0.066) "
             "| highest σ informative in ≥ half | real, forecast F | real, projection H "
             "| narrowest real interval, H | full window, H | verdict | depends on |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in q:
        verdict = f"**{r['verdict']}**" + (f"; {r['sub_label']}" if r["sub_label"] else "")
        narrow = _interval(r["narrow_lo"], r["narrow_hi"], r["lam"],
                           f" ({r['narrow_month']})" if r["narrow_month"] else "")
        window = _interval(r["window_lo"], r["window_hi"], r["lam"],
                           "" if r["window_lo"] is None else
                           (", informative" if r["window_informative"] else ", not informative"))
        L.append(f"| {r['row']} | {r['quantity']} | {_kn(r['syn_T_k'], r['syn_T_n'])} "
                 f"| {_kn(r['syn_H_k'], r['syn_H_n'])} | {r['highest_sigma_half']} "
                 f"| {_kn(r['real_F_k'], r['real_F_n'], r['real_F_undefined'])} "
                 f"| {_kn(r['real_H_k'], r['real_H_n'], r['real_H_undefined'])} "
                 f"| {narrow} | {window} | {verdict} | {r['depends_on']} |")
    L.append("\nλ₅ intervals are in GWh; all others are response shares (λ₆ a difference of two).\n")
    L.append("## Evidence rows\n")
    L.append("| row | question | evidence | synthetic, Anchor T | synthetic, Anchor H | real, F "
             "| real, H | verdict (from the results note) | depends on |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for r in e:
        L.append(f"| {r['row']} | {r['question']} | {r['evidence']} "
                 f"| {_kn(r['syn_T_k'], r['syn_T_n'])} | {_kn(r['syn_H_k'], r['syn_H_n'])} "
                 f"| {_kn(r['real_F_k'], r['real_F_n'], r['real_F_undefined'])} "
                 f"| {_kn(r['real_H_k'], r['real_H_n'], r['real_H_undefined'])} "
                 f"| {r['verdict']} | {r['depends_on']} |")
    L.append("\nFor the Q2 row the synthetic columns count cell-functionals that cover the known "
             "truth at Anchor T's bias (+0.033) and Anchor H's bias (−0.047, the operational "
             "series' value; the quality-assured series gives −0.0326), σ = 0. The Q2 row "
             "was added on 16 November 2026, after C0, at the student's instruction; C0 fixed four "
             "evidence rows. It carries no verdict under the C0 rule and changes no other row.")
    L.append("\nFor the pooled row the synthetic columns count split cells that reject a single "
             "common response (the most of any functional), not informative cells.\n")
    L.append("## What the verdicts mean\n")
    L.append(f"**{SUPPORTED}** ({counts[SUPPORTED]} of {len(q)} quantities). The quantity is "
             f"informative in at least half of its defined real-data months with the projection "
             f"as the potential. The reported interval is what the data supports; it is a range, "
             f"not a point estimate.\n")
    L.append(f"**{NOT_ID}** ({counts[NOT_ID]} of {len(q)}). With the best public estimate of "
             f"available power, the quantity is informative in fewer than half of its defined "
             f"months. The interval can still be reported, but it does not separate \"most of the "
             f"exposed fleet switches off\" from \"little of it does\".\n")
    L.append(f"**{NEEDS}** ({n_sub} of {len(q)}, a sub-label of the previous category). In Q1's "
             f"synthetic cells the quantity is informative in at least half the cells at a noise "
             f"level below Anchor H's, and not at Anchor H's. The stated level is the largest such "
             f"σ on the tested grid, within the tested synthetic conditions only.\n")
    if lit:
        L.append(f"Under the literal reading of C0 §4 rule 3 (without \"and not at Anchor H\"), "
                 f"{', '.join(lit)} would also carry the sub-label. They are informative in "
                 f"synthetic cells at Anchor H's σ, so the table does not say they need a more "
                 f"accurate estimate.\n")
    L.append("---\n")
    L.append("## Full-window reading (descriptive, not part of the C0 verdict)\n")
    L.append("Added 16 November 2026 at the student's instruction, after C0. It changes no "
             "verdict above. Each row is the single interval for the whole window "
             "(2025-10 to 2026-10, main setting, projection H), not the monthly arms the verdict "
             "counts. **Reading rule, fixed here and applied to every row:** a response share "
             "lies in [0, 1] (λ₆ in [−1, 1]; λ₅ in [0, its logical maximum] GWh); a bound is read "
             "one-sided when it excludes at least a quarter of that range at its own end, the "
             "same quarter the informativeness rule uses.\n")
    L.append("| row | full-window interval, H | width | logical maximum width | reading |")
    L.append("|---|---|---|---|---|")
    for r in q:
        if r["window_lo"] is None:
            L.append(f"| {r['row']} | undefined | — | — | — |")
            continue
        L.append(f"| {r['row']} | {_interval(r['window_lo'], r['window_hi'], r['lam'])} "
                 f"| {_fmt(r['window_width'], r['lam'])} "
                 f"| {_fmt(r['window_logical_max'], r['lam'])} | {r['window_reading']} |")
    L.append("\n**Every reading assumes the projection H is unbiased during negative prices.** "
             "Q2 shows that a biased potential gives intervals that stay narrow and miss the "
             "truth, and H's bias at negative prices has not been measured "
             "(`docs/Q2_results.md` §5). These are readings of the bounds as computed, not "
             "supported ranges.\n")
    L.append("---\n")
    L.extend(_breakdown_section())
    L.append("---\n")
    L.append("## Limitations\n")
    L.append("> - **Synthetic vs real.** Q1 and P3 cells have a known truth and an i.i.d. or AR(1) "
             "noise model; real data has neither. A synthetic count says what the method can "
             "do under those conditions, not what real data will give.")
    L.append("> - **The projection is not ground truth.** Q0b shows the quality-assured "
             "Online-Hochrechnung behaves as if market curtailment is added back. That is "
             "supporting evidence; not every projected-minus-observed difference is voluntary "
             "curtailment, and Anchor H's σ is a lower bound on its error.")
    L.append("> - **TenneT is excluded** from every projection aggregate (supervisor minute "
             "T-D(vii), `docs/Q_STOP_Q0c.md`). Real-data rows cover 50Hertz + Amprion + "
             "TransnetBW only.")
    L.append("> - **Q1 holds on its tested grid only** (σ = 0, 0.033, 0.066, 0.12, 0.18, 0.25, "
             "0.35). There is no universal threshold; \"≥ 0.35\" is a lower bound, not a value.")
    L.append("> - **The propositions A1–A3 were formulated after the experiments**, to organise "
             "them. Each experiment kept its own pre-registered test (`docs/00_OBJECTIVE.md`).")
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", action="store_true", help="print the markdown, write nothing")
    ap.add_argument("--sample-sizes", action="store_true",
                    help="write sample_sizes.csv only (needs data/processed/panel_qh.parquet)")
    args = ap.parse_args()
    if args.sample_sizes:
        sample_sizes().write_csv(SAMPLES_OUT)
        print(f"wrote {SAMPLES_OUT.relative_to(REPO_ROOT)}")
        return
    df = build()
    md = markdown(df)
    if args.print:
        print(md)
        return
    df.write_csv(CSV_OUT)
    pl.DataFrame(readings_rows(), infer_schema_length=None).write_csv(READINGS_OUT)
    MD_OUT.write_text(md, encoding="utf-8")
    print(f"wrote {CSV_OUT.relative_to(REPO_ROOT)}\nwrote {READINGS_OUT.relative_to(REPO_ROOT)}"
          f"\nwrote {MD_OUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
