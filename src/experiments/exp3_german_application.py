"""Experiment 3 -- German application (docs/06_exp3_german_application.md).

    python -m src.experiments.exp3_german_application           # re-derive the summaries and table
    python -m src.experiments.exp3_german_application --fits    # print the long-fit commands

Real data, 50Hertz + Amprion + TransnetBW, H as the potential: monthly and full-window bounds,
the bias-robust full-window readings and their breakdown points, and the results table.
"""

from __future__ import annotations

import argparse

from src.experiments._runner import run, show

FITS = ["src.experiments.exp3_real_bounds", "src.method.bias_robust --part v2"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fits", action="store_true", help="print the long-fit commands only")
    if ap.parse_args().fits:
        show(FITS)
        return
    run("src.experiments.exp3_real_bounds_summary")
    run("src.method.bias_robust_summary")
    run("src.experiments.exp3_results_table")


if __name__ == "__main__":
    main()
