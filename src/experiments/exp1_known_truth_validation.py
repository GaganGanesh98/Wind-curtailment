"""Experiment 1 -- known-truth validation (docs/04_exp1_known_truth_validation.md).

    python -m src.experiments.exp1_known_truth_validation            # re-derive the summaries
    python -m src.experiments.exp1_known_truth_validation --fits     # print the long-fit commands

Synthetic cells with a known truth: exact potential, estimated potential, and the i.i.d. /
AR(1) noise dial. Re-deriving the summaries reproduces the committed files byte for byte.
"""

from __future__ import annotations

import argparse

from src.experiments._runner import run, show

FITS = ["src.method.synthetic_scoring --arm O", "src.method.synthetic_scoring --arm D",
        "src.method.potential_error --dial q1"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fits", action="store_true", help="print the long-fit commands only")
    if ap.parse_args().fits:
        show(FITS)
        return
    run("src.method.read_results", "artifacts/P3/p3_synthetic_arm_o.csv")
    run("src.method.read_results", "artifacts/P3/p3_synthetic_arm_d.csv")
    run("src.experiments.exp1_noise_dial_summary")


if __name__ == "__main__":
    main()
