"""B3's bin-count sensitivity, over seeds 42-44, from stored predictions.

    python -m src.censoring.diag_b3_bins

Noise-audit item 2 (1 Nov 2026). `results/10_diag_b3_bins.csv` was a **single-seed**
diagnostic, and its ratios were quoted as though they were estimates: "M1's logistic
advantage falls from 47.9x at 8 bins to 2.7x at 64". One seed cannot support a ratio
to three significant figures. This script recomputes the same comparison over **seeds
42, 43 and 44 at gamma = 0, at every censoring rate** and reports the **mean and range**
per bin count.

**No model is re-fitted.** B3's implied response is a deterministic function of
quantities already stored per cell in `data/processed/e1_gate_artifacts/`:

    residual          = max(0, a_hat_B3 - g_obs)
    exposed_share     = sum_k shares_k * s_kt
    exposed_potential = a_hat_B3 * exposed_share
    margin            = (sum_k shares_k * s_kt * depth_kt) / exposed_share

which is exactly what `fit_b3` feeds to `_binned_response`. So the bin count can be
varied exactly, for free, by rebinning those arrays — the same numbers `fit_b3` would
have produced had it been called with a different `n_bins`.

M1's integrated error does not depend on the bin count at all; it is included per cell
so the ratio has a numerator.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from src.censoring.baselines import _binned_response, b3_response_curve
from src.censoring.gate_verdict import load_cells
from src.censoring.metrics import integrated_response_error

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_CSV = REPO_ROOT / "results" / "19_b3_bins_multiseed.csv"
BIN_COUNTS = (4, 8, 16, 32, 64)


def b3_inputs(cell: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Reconstruct fit_b3's stage-3 inputs exactly, from the stored arrays."""
    a_hat = np.asarray(cell["a_hat_B3"], dtype=float)
    g = np.asarray(cell["g_obs"], dtype=float)
    shares = np.asarray(cell["shares"], dtype=float)[:, None]
    s = np.asarray(cell["s"], dtype=float)
    depth = np.asarray(cell["depth"], dtype=float)

    residual = np.maximum(0.0, a_hat - g)
    exposed_share = (shares * s).sum(axis=0)
    exposed_potential = a_hat * exposed_share
    weighted_depth = (shares * s * depth).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        margin = np.where(exposed_share > 0, weighted_depth / exposed_share, 0.0)
    use = exposed_potential > 0
    return margin[use], residual[use], exposed_potential[use]


def main() -> None:
    cells = [c for c in load_cells() if float(c["gamma"]) == 0.0]
    if not cells:
        raise SystemExit("No stored gamma = 0 cells.")
    shapes = sorted({str(c["r_shape"]) for c in cells})
    seeds = sorted({int(c["seed"]) for c in cells})
    rates = sorted({float(c["censoring_rate"]) for c in cells})
    print(f"gamma = 0, {len(cells)} cells: shapes {shapes}, seeds {seeds}, "
          f"rates {[f'{r:.0%}' for r in rates]}")
    print("No refitting: B3's implied response is rebinned from stored arrays.\n")

    rows, per = [], {}
    for c in cells:
        shape = str(c["r_shape"])
        grid = np.asarray(c["depth_grid"], dtype=float)
        r_true = np.asarray(c["r_curve_true"], dtype=float)
        m1 = integrated_response_error(np.asarray(c["r_curve_M1"], dtype=float),
                                       r_true, grid)
        margin, residual, pot = b3_inputs(c)
        for nb in BIN_COUNTS:
            br = _binned_response(margin, residual, pot, nb, edges=None)
            r_b3 = b3_response_curve({"implied_response": br}, grid)
            b3 = integrated_response_error(r_b3, r_true, grid)
            per.setdefault((shape, nb), []).append((m1, b3))
            rows.append({"r_shape": shape, "n_bins": nb,
                         "censoring_rate": float(c["censoring_rate"]),
                         "seed": int(c["seed"]),
                         "int_abs_r_m1": round(m1, 6),
                         "int_abs_r_b3": round(b3, 6),
                         "ratio_b3_over_m1": round(b3 / m1, 4) if m1 > 0 else "",
                         "m1_better": bool(m1 < b3)})

    hdr = (f"{'shape':<10}{'bins':>5}{'n':>4}{'M1 mean':>10}{'B3 mean':>10}"
           f"{'B3/M1 mean':>12}{'B3/M1 range':>22}{'M1 lower':>10}")
    print(hdr)
    print("-" * len(hdr))
    for shape in shapes:
        for nb in BIN_COUNTS:
            vals = per.get((shape, nb), [])
            if not vals:
                continue
            m1 = np.array([v[0] for v in vals])
            b3 = np.array([v[1] for v in vals])
            ratio = b3 / np.where(m1 > 0, m1, np.nan)
            n_lower = int((m1 < b3).sum())
            print(f"{shape:<10}{nb:>5}{len(vals):>4}{m1.mean():>10.5f}"
                  f"{b3.mean():>10.5f}{np.nanmean(ratio):>12.2f}"
                  f"{f'[{np.nanmin(ratio):.2f}, {np.nanmax(ratio):.2f}]':>22}"
                  f"{f'{n_lower}/{len(vals)}':>10}")
            rows.append({"r_shape": shape, "n_bins": nb, "censoring_rate": "ALL",
                         "seed": "ALL", "int_abs_r_m1": round(float(m1.mean()), 6),
                         "int_abs_r_b3": round(float(b3.mean()), 6),
                         "ratio_b3_over_m1": round(float(np.nanmean(ratio)), 4),
                         "m1_better": f"{n_lower}/{len(vals)}"})
        print()

    print("Reading. The ratio is a mean over cells with its full range beside it; a")
    print("single-seed ratio is not reportable and the superseded figures (47.9x at 8")
    print("bins, 2.7x at 64) came from one seed at one rate. Quote the mean with the")
    print("range, or quote nothing.")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {OUT_CSV.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
