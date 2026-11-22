"""Phase V: bias-robust bounds, the outer loop over a bias grid (`docs/V0_preregistration.md`).

    python -m src.method.bias_robust --part v1 --shard 0/4   # synthetic, 1 of 4
    python -m src.method.bias_robust --part v2               # real data

Written after V0 was committed (`3277ea6`). Nothing inside the identified set changes: V1
calls Q's `score_under_potential` (P3's `score_cell`) and V2 calls P3's `run_arm`, each with
the potential scaled by exp(b). This module only loops over b and writes one raw row per
(cell, scored potential, functional); `summarise_v.py` forms the hulls S_B and applies V0's
criteria.

V1 scores every distinct sum s = b* + b once per cell, because the potential handed to the
bounds is A * exp(b*) * exp(b) = A * exp(s). V2 scores b on [-0.15, 0.15] once.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import numpy as np

from src.method.synthetic_scoring import GAMMAS, HETERO, RATES, SHAPES, prepare_cell
from src.method.potential_error import BIAS_GRID, SEED_GEN, git_head, score_under_potential

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "artifacts" / "exp2_bias_robustness_validation"          # synthetic (exp 2)
OUT_DIR_REAL = REPO_ROOT / "artifacts" / "exp3_german_application"     # real data (exp 3)
V0_COMMIT = "3277ea6"
STEP = 0.01
V1_BMAX = 0.10
V2_BMAX = 0.15
V2_LAMS = ("L1", "L2", "L3", "L6")


def grid(bmax: float) -> list[float]:
    k = int(round(bmax / STEP))
    return [round(i * STEP, 2) for i in range(-k, k + 1)]


def v1_sums() -> list[float]:
    """Every distinct b* + b over the Q2a biases and the B = 0.10 grid, rounded to 1e-3."""
    return sorted({round(bs + b, 3) for bs in BIAS_GRID for b in grid(V1_BMAX)})


def run_v1(shard: int, n_shards: int) -> Path:
    cells = [(r, g, sh, SEED_GEN, h) for r in RATES for g in GAMMAS
             for h in HETERO for sh in SHAPES]          # run_q_dial's order
    mine = [c for i, c in enumerate(cells) if i % n_shards == shard]
    sums = v1_sums()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"bias_robust_cells_shard{shard}of{n_shards}.csv"
    head = git_head()
    print(f"V1 shard {shard}/{n_shards}: {len(mine)} cells x {len(sums)} potentials -> {out}",
          flush=True)
    fh = writer = None
    try:
        for i, (rate, gamma, shape, seed, hetero) in enumerate(mine, 1):
            t0 = time.perf_counter()
            prep = prepare_cell(rate, gamma, shape, seed, hetero)
            for s in sums:
                rows = score_under_potential(prep, 0.0, s, "iid", 0.0, "v1")
                for r in rows:
                    r.update({"s": s, "v0_commit": V0_COMMIT, "git_head": head})
                if writer is None:
                    fh = open(out, "w", newline="", encoding="utf-8")
                    writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
                    writer.writeheader()
                for r in rows:
                    writer.writerow({k: r.get(k) for k in writer.fieldnames})
            fh.flush()
            print(f"[{i:2d}/{len(mine)}] {hetero:<12} r{int(rate * 100):<3} g{gamma} {shape:<9} "
                  f"{time.perf_counter() - t0:6.1f}s", flush=True)
    finally:
        if fh is not None:
            fh.close()
    return out


def run_v2() -> Path:
    from src.method.real_panel import THREE_AREA, load_panel, run_arm
    panel = load_panel(THREE_AREA, "H")
    OUT_DIR_REAL.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR_REAL / "bias_robust_full_window_cells.csv"
    head = git_head()
    fh = writer = None
    try:
        for b in grid(V2_BMAX):
            scaled = {**panel, "f": np.asarray(panel["f"], dtype=float) * np.exp(b)}
            rows = run_arm(scaled, "main", scaled["keep"], "window", False)
            for r in rows:
                r.update({"b": b, "potential": "H", "v0_commit": V0_COMMIT, "git_head": head})
            if writer is None:
                fh = open(out, "w", newline="", encoding="utf-8")
                writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
                writer.writeheader()
            for r in rows:
                writer.writerow({k: r.get(k) for k in writer.fieldnames})
            fh.flush()
            w = {r["lam"]: (r.get("lo"), r.get("hi")) for r in rows if r["lam"] in V2_LAMS}
            print(f"b {b:+.2f}  " + "  ".join(f"{k}=[{lo:.3f},{hi:.3f}]" for k, (lo, hi)
                                              in w.items() if lo is not None), flush=True)
    finally:
        if fh is not None:
            fh.close()
    return out


def demo(out: Path, b_true: float = -0.047, budget: float = 0.05) -> Path:
    """One synthetic cell with a known bias, end to end, in seconds (demo/run_demo.sh).

    The potential carries a constant bias b_true; the plain set (B = 0) and the bias-robust
    hull for `budget` are printed beside the known truth, per functional.
    """
    rate, gamma, shape, seed, hetero = 0.10, 0.0, "step", SEED_GEN, "homogeneous"
    prep = prepare_cell(rate, gamma, shape, seed, hetero)
    rows = {}
    for b in grid(budget):
        for r in score_under_potential(prep, 0.0, round(b_true + b, 3), "iid", 0.0, "demo"):
            if r.get("defined") and r.get("feasible"):
                rows.setdefault(r["lam"], []).append((b, r["lo"], r["hi"], r["truth"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"cell: {hetero}, rate {rate}, gamma {gamma}, {shape}, seed {seed}; "
             f"true bias {b_true:+.3f}, budget B = {budget}"]
    lines.append(f"{'functional':<11}{'truth':>9}   {'plain set (B = 0)':<22}{'covered':>8}   "
                 f"{'bias-robust set':<22}{'covered':>8}")
    for lam in ("L1", "L2", "L3", "L4", "L6", "L7"):           # lambda-5 left out, as in V0
        v = rows[lam]
        truth = v[0][3]
        plain = next((lo, hi) for b, lo, hi, _ in v if abs(b) < 1e-9)
        lo, hi = min(x[1] for x in v), max(x[2] for x in v)
        slack = 1e-6 * max(1.0, abs(truth))
        cov = lambda a, z: "yes" if a - slack <= truth <= z + slack else "NO"
        lines.append(f"{lam:<11}{truth:>9.4f}   [{plain[0]:.4f}, {plain[1]:.4f}]{'':<4}{cov(*plain):>8}   "
                     f"[{lo:.4f}, {hi:.4f}]{'':<4}{cov(lo, hi):>8}")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=("v1", "v2", "demo"), required=True)
    ap.add_argument("--shard", default="0/1", help="i/n: run cells with index % n == i (V1)")
    args = ap.parse_args()
    if args.part == "demo":
        demo(REPO_ROOT / "demo" / "output" / "bias_robust_cell.txt")
        return
    if args.part == "v1":
        i, n = (int(x) for x in args.shard.split("/"))
        print(f"wrote {run_v1(i, n)}")
    else:
        print(f"wrote {run_v2()}")


if __name__ == "__main__":
    main()
