"""POST-HOC (22 Nov 2026): Experiment 3's breakdown points on a finer bias grid.

Design fixed in `docs/08_posthoc_breakdown_grid.md`, written after the pre-registered V2
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
    """The design, as docs/08 states it (a generated block, so the number checker holds it)."""
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
