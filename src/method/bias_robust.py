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
import polars as pl

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


def grid(bmax: float, step: float = STEP) -> list[float]:
    """b on [-bmax, bmax]. The default step is the pre-registered 0.01 (rounded to 2 places,
    exactly as before); a finer post-hoc step (docs/10) is rounded to 4 places."""
    k = int(round(bmax / step))
    places = 2 if step == STEP else 4
    return [round(i * step, places) for i in range(-k, k + 1)]


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


#: Redispatch masks (docs/11_redispatch_sensitivity_preregistration.md, 22 Nov 2026).
MASK_AREAS = ("50Hertz", "Amprion", "TransnetBW")
MASKS = {"M0": "drop QHs with renewable redispatch R > 0 in any of the three areas",
         "M1": "drop QHs with R > 1% of H in any of the three areas (each against its own H)"}
M1_SHARE = 0.01


def redispatch_keep(panel: dict, mask: str) -> np.ndarray:
    """True where a quarter-hour survives `mask`, aligned to the panel. R is the renewable
    'reduzieren' series of `available_power.load_frames` (it includes solar and offshore)."""
    from src.method.available_power import load_frames
    if mask not in MASKS:
        raise ValueError(f"unknown mask {mask!r}; known: {sorted(MASKS)}")
    frames = load_frames("quality-assured")
    ts = pl.DataFrame({"ts_utc": panel["ts_utc"]})
    drop = np.zeros(ts.height, dtype=bool)
    for area in MASK_AREAS:
        j = ts.join(frames[area].select(["ts_utc", "rd_mw", "hr_mw"]), on="ts_utc", how="left")
        if (j["ts_utc"].to_numpy() != panel["ts_utc"]).any():
            raise ValueError("redispatch does not align with the panel")
        r = j["rd_mw"].fill_null(0.0).to_numpy().astype(float)
        h = j["hr_mw"].to_numpy().astype(float)
        drop |= (r > 0.0) if mask == "M0" else (r > M1_SHARE * np.nan_to_num(h, nan=np.inf))
    return ~drop


LEARNED_OOF = REPO_ROOT / "artifacts" / "exp4_learned_potential" / "oof_L2.parquet"


def learned_potential(panel: dict, oof: Path = LEARNED_OOF) -> np.ndarray:
    """Experiment 4's Â for the three-area aggregate, aligned to the panel: the sum over the three
    areas of L2's out-of-fold median (docs/12b). NaN where any area lacks a prediction."""
    a = pl.read_parquet(oof).select(["area", "ts_utc", "a_hat_mw"])
    agg = (a.group_by("ts_utc").agg(pl.col("a_hat_mw").sum(), pl.len().alias("n"))
             .filter(pl.col("n") == len(MASK_AREAS)))
    j = pl.DataFrame({"ts_utc": panel["ts_utc"]}).join(agg, on="ts_utc", how="left")
    if (j["ts_utc"].to_numpy() != panel["ts_utc"]).any():
        raise ValueError("learned potential does not align with the panel")
    return j["a_hat_mw"].fill_null(np.nan).to_numpy().astype(float)


def run_v2(step: float = STEP, bmax: float = V2_BMAX, out: Path | None = None,
           masks: tuple[str, ...] = (), potential: str = "H") -> Path:
    """V2 on the real full window. Defaults are the pre-registered grid and file; `step`,
    `bmax` and `out` exist for the post-hoc fine grid (docs/10), and `masks` for the redispatch
    sensitivity (docs/11); both write elsewhere and leave the default run unchanged."""
    from src.method.real_panel import THREE_AREA, load_panel, run_arm
    out = Path(out) if out is not None else OUT_DIR_REAL / "bias_robust_full_window_cells.csv"
    if potential not in ("H", "learned"):
        raise ValueError(f"unknown potential {potential!r}")
    if ((step, bmax) != (STEP, V2_BMAX) or masks or potential != "H") and out == OUT_DIR_REAL / "bias_robust_full_window_cells.csv":
        raise ValueError("a non-default run must not overwrite the pre-registered V2 artifact")
    panel = load_panel(THREE_AREA, "H")
    if potential == "learned":                       # Experiment 4 robustness arm (docs/12b)
        a_hat = learned_potential(panel)
        panel = {**panel, "f": a_hat,
                 "keep": panel["keep"] & np.isfinite(a_hat) & (np.nan_to_num(a_hat) > 0)}
    OUT_DIR_REAL.mkdir(parents=True, exist_ok=True)
    arms = [(None, panel["keep"])] if not masks else [
        (m, panel["keep"] & redispatch_keep(panel, m)) for m in masks]
    head = git_head()
    fh = writer = None
    try:
        for mask, keep in arms:
            for b in grid(bmax, step):
                scaled = {**panel, "f": np.asarray(panel["f"], dtype=float) * np.exp(b)}
                rows = run_arm(scaled, "main", keep, "window", False)
                for r in rows:
                    r.update({"b": b, "potential": "H" if potential == "H" else "learned (L2)",
                              "v0_commit": V0_COMMIT, "git_head": head})
                    if mask is not None:
                        r["mask"] = mask
                if writer is None:
                    fh = open(out, "w", newline="", encoding="utf-8")
                    writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
                    writer.writeheader()
                for r in rows:
                    writer.writerow({k: r.get(k) for k in writer.fieldnames})
                fh.flush()
                w = {r["lam"]: (r.get("lo"), r.get("hi")) for r in rows if r["lam"] in V2_LAMS}
                print(f"{mask or 'V2'} b {b:+.4f}  " + "  ".join(
                    f"{k}=[{lo:.3f},{hi:.3f}]" for k, (lo, hi) in w.items() if lo is not None),
                    flush=True)
    finally:
        if fh is not None:
            fh.close()
    return out


def demo(out: Path, b_true: float = -0.047, budget: float = 0.05, digits: int = 3) -> Path:
    """One synthetic cell with a known bias, end to end, in seconds (demo/run_demo.sh).

    The potential carries a constant bias b_true; the plain set (B = 0) and the bias-robust
    hull for `budget` are printed beside the known truth, per functional. b_true = -0.047 is
    the bias dial's grid point, the operational series' value; the quality-assured series gives σ 0.0610 and bias −0.0326 (docs/03).
    `digits` is how b_true + b is rounded: 3 for the pre-registered cell, 4 for `demo_measured`.
    """
    rate, gamma, shape, seed, hetero = 0.10, 0.0, "step", SEED_GEN, "homogeneous"
    prep = prepare_cell(rate, gamma, shape, seed, hetero)
    rows = {}
    for b in grid(budget):
        for r in score_under_potential(prep, 0.0, round(b_true + b, digits), "iid", 0.0, "demo"):
            if r.get("defined") and r.get("feasible"):
                rows.setdefault(r["lam"], []).append((b, r["lo"], r["hi"], r["truth"]))
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"cell: {hetero}, rate {rate}, gamma {gamma}, {shape}, seed {seed}; "
             f"true bias {b_true:+.{digits}f}, budget B = {budget}"]
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


def demo_measured(out: Path, budget: float = 0.05) -> Path:
    """Not pre-registered, illustration only: the demo cell at the quality-assured measured
    bias of H (the Experiment 3 H anchor, read from its artifact), rounded to 4 places."""
    from src.experiments.available_power_anchors import primary_h
    return demo(out, b_true=round(float(primary_h()["bias"]), 4), budget=budget, digits=4)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", choices=("v1", "v2", "demo", "demo-measured"), required=True)
    ap.add_argument("--shard", default="0/1", help="i/n: run cells with index % n == i (V1)")
    ap.add_argument("--step", type=float, default=STEP, help="V2 b-grid step (default 0.01)")
    ap.add_argument("--bmax", type=float, default=V2_BMAX, help="V2 b-grid half-width (0.15)")
    ap.add_argument("--out", default=None, help="V2 output file (default: the pre-registered one)")
    ap.add_argument("--masks", default="", help="comma-separated redispatch masks, e.g. M0,M1 (docs/11)")
    ap.add_argument("--potential", default="H", choices=("H", "learned"),
                    help="H (default) or Experiment 4's learned potential, L2's A-hat (docs/12b)")
    args = ap.parse_args()
    if args.part == "demo":
        demo(REPO_ROOT / "demo" / "output" / "bias_robust_cell.txt")
        return
    if args.part == "demo-measured":
        demo_measured(REPO_ROOT / "demo" / "output" / "bias_robust_cell_measured_bias.txt")
        return
    if args.part == "v1":
        i, n = (int(x) for x in args.shard.split("/"))
        print(f"wrote {run_v1(i, n)}")
    else:
        masks = tuple(m for m in args.masks.split(",") if m)
        print(f"wrote {run_v2(args.step, args.bmax, args.out, masks, args.potential)}")


if __name__ == "__main__":
    main()
