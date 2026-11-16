"""Experiment 2 -- bias-robustness validation (docs/05_exp2_bias_robustness_validation.md).

    python -m src.experiments.exp2_bias_robustness_validation          # re-derive the summaries
    python -m src.experiments.exp2_bias_robustness_validation --fits   # print the long-fit commands

Synthetic cells with a known bias in the potential: the bias dial, bias crossed with noise,
and the bias-robust hull over [-B, B].
"""

from __future__ import annotations

import argparse

from src.experiments._runner import run, show

FITS = ["src.method.potential_error --dial q2a", "src.method.potential_error --dial q2b"] + [
    f"src.method.bias_robust --part v1 --shard {i}/4" for i in range(4)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fits", action="store_true", help="print the long-fit commands only")
    if ap.parse_args().fits:
        show(FITS)
        return
    run("src.experiments.exp2_bias_dial_summary")
    run("src.method.bias_robust_summary")


if __name__ == "__main__":
    main()
