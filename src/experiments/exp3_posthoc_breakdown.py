"""POST-HOC (22 Nov 2026): Experiment 3's breakdown points on a finer bias grid.

Design fixed in `docs/10_posthoc_breakdown_grid.md`, written after the pre-registered V2
results were known. The V2 result (0.01 grid) stays the headline; this is a refinement.

    python -m src.method.bias_robust --part v2 --step 0.0025 --bmax 0.06 \\
        --out artifacts/exp3_german_application/posthoc_breakdown_fine_grid.csv   # the refit
    python -m src.experiments.exp3_posthoc_breakdown                              # the summary
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
E3 = REPO_ROOT / "artifacts" / "exp3_german_application"
AP = REPO_ROOT / "artifacts" / "available_power_estimate"

DATE = "22 Nov 2026"
STEP = 0.0025                     # fine grid for λ₁, λ₂, λ₆
BMAX = 0.06
FINE_LAMS = ("L1", "L2", "L6")
COARSE_LAMS = ("L3",)             # unchanged: the pre-registered 0.01 grid to 0.15
CELLS = E3 / "posthoc_breakdown_fine_grid.csv"
SUMMARY = E3 / "posthoc_breakdown_fine_grid_summary.csv"
COMMAND = ("python -m src.method.bias_robust --part v2 --step 0.0025 --bmax 0.06 "
           "--out artifacts/exp3_german_application/posthoc_breakdown_fine_grid.csv")


def comparison_values() -> dict[str, float]:
    """|bias| of H to compare with: the brief's value and the Experiment 3 window's value."""
    import polars as pl
    from src.experiments.available_power_anchors import primary_h
    ag = pl.read_csv(AP / "agreement_at_positive_prices.csv").filter(
        (pl.col("series") == "quality-assured") & (pl.col("area") == "50Hertz+Amprion+TransnetBW"))
    return {"quality-assured series, 2025-10-01 to 2026-10-28 (the brief's value)":
                abs(float(ag["bias_log_G_over_H"][0])),
            "quality-assured series, Experiment 3 window (the H anchor)":
                abs(float(primary_h()["bias"]))}


def design_text() -> str:
    """The design, as docs/10 states it (a generated block, so the number checker holds it)."""
    import math
    cv = comparison_values()
    lines = [f"- Fine grid for λ₁, λ₂ and λ₆: b from −{BMAX:.2f} to {BMAX:.2f} in steps of "
             f"{STEP:.4f} ({2 * round(BMAX / STEP) + 1} refits of the V2 full-window arm), hull "
             f"S_B over |b| ≤ B for B = 0 to {BMAX:.2f} in steps of {STEP:.4f}.",
             "- λ₃ unchanged: the pre-registered grid, B = 0.01 to 0.15 in steps of 0.01.",
             "- Readings, hull, informativeness rule, ε rule, window, areas and award setting are V2's.",
             "- Comparison values, |bias| of H at price ≥ 0:"]
    for k, v in cv.items():
        nxt = math.ceil(round(v / STEP, 6)) * STEP
        lines.append(f"  - {v:.4f}, {k}. A reading survives it if it holds at B = {nxt:.4f}, "
                     f"the first fine-grid allowance at or above it.")
    return "\n".join(lines)


def summarise() -> "pl.DataFrame":
    """Per reading: breakdown B and largest holding B on the fine grid (λ₁, λ₂, λ₆) or the
    pre-registered grid (λ₃), and whether the reading survives each comparison value."""
    import math
    import polars as pl
    from src.method.bias_robust_summary import V2_RULES
    fine = (pl.read_csv(CELLS, infer_schema_length=0)
              .with_columns(*(pl.col(c).cast(pl.Float64) for c in ("b", "lo", "hi")),
                            (pl.col("feasible") == "True").alias("feasible"))
              .with_columns(pl.col("b").round(4)))
    coarse = pl.read_csv(E3 / "bias_robust_full_window_intervals.csv")
    cv = comparison_values()
    rows = []
    for lam in FINE_LAMS + COARSE_LAMS:
        reading, holds = V2_RULES[lam]
        if lam in FINE_LAMS:
            budgets = [round(i * STEP, 4) for i in range(int(round(BMAX / STEP)) + 1)]
            seq = []
            for B in budgets:
                q = fine.filter((pl.col("lam") == lam) & (pl.col("b").abs() <= B + 1e-9)
                                & pl.col("feasible"))
                lo, hi = float(q["lo"].min()), float(q["hi"].max())
                seq.append((B, lo, hi, bool(holds(lo, hi))))
            step, grid_name = STEP, f"post-hoc {STEP:.4f}"
        else:
            seq = [(r["B"], r["lo"], r["hi"], bool(r["reading_holds"]))
                   for r in coarse.filter(pl.col("lam") == lam).sort("B").iter_rows(named=True)]
            step, grid_name = 0.01, "pre-registered 0.01"
        largest = None
        brk = None
        for B, lo, hi, ok in seq:
            if ok and brk is None:
                largest = (B, lo, hi)
            elif not ok and brk is None:
                brk = B
        row = {"lam": lam, "reading": reading, "grid": grid_name,
               "largest_B_holds": None if largest is None else largest[0],
               "lo_at_largest_B": None if largest is None else largest[1],
               "hi_at_largest_B": None if largest is None else largest[2],
               "breakdown_B": "" if brk is None else f"{brk:.4f}",
               "breakdown_above_grid": brk is None, "grid_top": seq[-1][0]}
        for i, (name, v) in enumerate(cv.items()):
            need = math.ceil(round(v / step, 6)) * step
            at = [ok for B, lo, hi, ok in seq if abs(B - need) < 1e-9]
            row[f"compare_{i}_value"] = v
            row[f"compare_{i}_needs_B"] = need
            row[f"compare_{i}_survives"] = (bool(at[0]) and (brk is None or brk > need + 1e-9)
                                            if at else None)
        rows.append(row)
    return pl.DataFrame(rows, infer_schema_length=None)


SYM = {"L1": "λ₁", "L2": "λ₂", "L3": "λ₃", "L6": "λ₆"}
TESTED = {"L1": "λ₁ informative (width < 0.25)", "L2": "λ₂ ≥ 0.50", "L3": "λ₃ ≤ 0.75",
          "L6": "λ₆ ≤ 0.50"}


def _hull(lam: str, B: float) -> tuple[float, float]:
    """S_B from the unrounded fine-grid cells (λ₁, λ₂, λ₆) or the V2 intervals (λ₃)."""
    import polars as pl
    if lam in FINE_LAMS:
        c = (pl.read_csv(CELLS, infer_schema_length=0)
               .with_columns(*(pl.col(x).cast(pl.Float64) for x in ("b", "lo", "hi")))
               .with_columns(pl.col("b").round(4))
               .filter((pl.col("lam") == lam) & (pl.col("b").abs() <= B + 1e-9)
                       & (pl.col("feasible") == "True")))
        return float(c["lo"].min()), float(c["hi"].max())
    iv = pl.read_csv(E3 / "bias_robust_full_window_intervals.csv").filter(
        (pl.col("lam") == lam) & ((pl.col("B") - B).abs() < 1e-9)).row(0, named=True)
    return float(iv["lo"]), float(iv["hi"])


def margin(lam: str, lo: float, hi: float) -> float:
    """How far the reading is from failing, in its own unit (positive = holds)."""
    return {"L1": 0.25 - (hi - lo), "L2": lo - 0.5, "L3": 0.75 - hi, "L6": 0.5 - hi}[lam]


def results_table() -> str:
    import polars as pl
    d = pl.read_csv(SUMMARY)
    cv = list(comparison_values().values())
    head = ["reading tested", "grid", "largest B at which it holds", "breakdown B"]
    for v, need in ((cv[0], d["compare_0_needs_B"]), (cv[1], d["compare_1_needs_B"])):
        head.append(f"at bias {v:.4f} in size: holds? (margin at the B it needs)")
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in d.iter_rows(named=True):
        lam = r["lam"]
        cells = [TESTED[lam], r["grid"], f"{r['largest_B_holds']:.4f}",
                 r["breakdown_B"] if r["breakdown_B"] else f"> {r['grid_top']:.2f}"]
        for i in (0, 1):
            need = r[f"compare_{i}_needs_B"]
            m = margin(lam, *_hull(lam, need))
            cells.append(f"{'yes' if r[f'compare_{i}_survives'] else 'no'} at B = {need:.4f} "
                         f"({m:+.7f})")
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def l1_edge_table() -> str:
    rows = ["| B | λ₁ lower | λ₁ upper | width | width < 0.25 |", "|---|---|---|---|---|"]
    for B in (0.0325, 0.0350, 0.0375):
        lo, hi = _hull("L1", B)
        rows.append(f"| {B:.4f} | {lo:.7f} | {hi:.7f} | {hi - lo:.7f} | {'yes' if hi - lo < 0.25 else 'no'} |")
    return "\n".join(rows)


def results_note() -> str:
    cv = comparison_values()
    q = list(cv.values())[1]
    need = __import__("math").ceil(round(q / STEP, 6)) * STEP
    m1 = margin("L1", *_hull("L1", need))
    m6 = margin("L6", *_hull("L6", need))
    m2 = margin("L2", *_hull("L2", need))
    return (f"At the H anchor's bias ({q:.4f}, checked at B = {need:.4f}) λ₁ and λ₆ hold, with "
            f"almost no margin: λ₁'s width is {0.25 - m1:.7f} against 0.25 and λ₆'s upper bound "
            f"{0.5 - m6:.7f} against 0.50, and both break at the next grid step. λ₂'s lower bound "
            f"holds with margin {m2:.4f}. On the pre-registered 0.01 grid λ₁ and λ₆ are reported "
            f"as breaking at 0.04 and that stays the result; this is a post-hoc refinement, and "
            f"the bias during negative prices is still not measured, so no reading is "
            f"unconditionally robust. The hull is formed over the grid's b values only; a bias "
            f"between two grid points is not refitted.")


def docs06_line() -> str:
    import polars as pl
    d = {r["lam"]: r for r in pl.read_csv(SUMMARY).iter_rows(named=True)}
    q = list(comparison_values().values())[1]
    return (f"- Post-hoc (22 Nov 2026, `docs/10_posthoc_breakdown_grid.md`): on a {STEP:.4f} bias "
            f"grid the breakdowns are λ₁ {d['L1']['breakdown_B']}, λ₂ {d['L2']['breakdown_B']} and "
            f"λ₆ {d['L6']['breakdown_B']}, so λ₁ and λ₆ hold at the quality-assured bias of "
            f"{q:.4f}, with almost no margin. The pre-registered 0.01-grid breakdowns stay the result.")


def main() -> None:
    d = summarise()
    d.write_csv(SUMMARY)
    print(d)
    print(f"wrote {SUMMARY}")


if __name__ == "__main__":
    main()
