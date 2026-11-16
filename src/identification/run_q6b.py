"""Q6b: a day-level random effect in r*, scored at Anchor H's and Anchor T's noise.

    python -m src.identification.run_q6b --levels 0 --check-port      # first
    python -m src.identification.run_q6b --levels 0.05,0.1,0.2,0.3 --append

Pre-registration `docs/Q6_preregistration.md` section Q6b (commit `b2f7d95`).

On each of Q1's 54 cells (`run_p3_synthetic.prepare_cell`, generator seed 45), after
the cell is prepared:

    r*_k,t = clip(r*_k,t + u_d(t), 0, 1)   where s_k,t > 0 and depth_k,t > 0
    u_d ~ N(0, sigma_r^2), one per synthetic Berlin day, common to all cohorts,
    seed 7_000_000 + round(1000 * sigma_r), common across cells

then c_true and G = A (1 - c_true) are recomputed. Prices, exposure, depth, run lengths
and the bounds design are unchanged. Scoring is Q1's (`run_q_dial.score_under_potential`):
P = A exp(e), e i.i.d. N(0, sigma^2), sigma in {0.066, 0.18}, Q1's noise seed.

Port check: at sigma_r = 0 every row must equal its Q1 row.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import time
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl

from src.method.exposure import curtailed_share
from src.method.synthetic_scoring import GAMMAS, HETERO, RATES, SHAPES, prepare_cell
from src.method.potential_error import SEED_GEN, git_head, score_under_potential
from src.method.read_results import load

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "artifacts" / "Q6" / "q6b_day_effect.csv"
Q1_ROWS = REPO_ROOT / "artifacts" / "Q1" / "q1_variance_dial.csv"
PREREG_COMMIT = "b2f7d95"
SIGMA_R_GRID = (0.0, 0.05, 0.10, 0.20, 0.30)
NOISE = (0.066, 0.18)
PORT_COLS = ("lo", "hi", "width", "eps", "rms_point", "rms_floor", "truth", "covered",
             "informative", "pooled_err_exceeds_width")


def u_seed(sigma_r: float) -> int:
    return 7_000_000 + int(round(1000 * sigma_r))


def with_day_effect(prep: dict, sigma_r: float) -> dict:
    """A copy of the prepared cell with the day effect in r*, c_true and G."""
    if sigma_r == 0.0:
        return prep
    data = prep["data"]
    days, inv = np.unique(np.asarray(data.berlin_date), return_inverse=True)
    u = np.random.default_rng(u_seed(sigma_r)).normal(0.0, sigma_r, size=days.size)[inv]
    r = np.asarray(data.r_true, dtype=float)
    s, depth = prep["s"], prep["depth"]
    on = (s > 0) & (depth > 0)
    r_new = np.where(on, np.clip(r + u[None, :], 0.0, 1.0), 0.0)
    c_new = curtailed_share(prep["shares"], s, r_new)
    if data.config.observation_noise_mw > 0:
        raise ValueError("Q6b assumes the generator's default zero observation noise")
    g_new = np.asarray(data.a_true_mw, dtype=float) * (1.0 - c_new)
    return {**prep, "data": dataclasses.replace(data, r_true=r_new, c_true=c_new,
                                                g_obs_mw=g_new)}


def port_check(rows: list[dict]) -> list[str]:
    q1 = load(Q1_ROWS).with_columns(pl.col("sigma").cast(pl.Float64, strict=False))
    q1 = q1.filter(pl.col("noise") == "iid")
    key = ("hetero", "rate", "gamma", "r_shape", "lam")
    idx = {}
    for r in q1.iter_rows(named=True):
        idx[tuple(str(r[k]) for k in key) + (round(r["sigma"], 3),)] = r
    bad = []
    for r in rows:
        k = tuple(str(r[c]) for c in key) + (round(r["sigma"], 3),)
        ref = idx.get(k)
        if ref is None:
            bad.append(f"no Q1 row for {k}")
            continue
        for c in PORT_COLS:
            a, b = r.get(c), ref.get(c)
            fa = isinstance(a, (float, int, np.floating)) and not isinstance(a, bool)
            if fa or isinstance(b, float):
                try:
                    af, bf = float(a), float(b)
                except (TypeError, ValueError):
                    if str(a) != str(b) and not (a in (None, "") and b in (None, "")):
                        bad.append(f"{k} {c}: {a!r} vs {b!r}")
                    continue
                if not (af == bf or (np.isnan(af) and np.isnan(bf))):
                    bad.append(f"{k} {c}: {a!r} vs {b!r}")
            elif str(a) != str(b) and not (a in (None, "") and b in (None, "")):
                bad.append(f"{k} {c}: {a!r} vs {b!r}")
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", default=",".join(str(x) for x in SIGMA_R_GRID))
    ap.add_argument("--check-port", action="store_true")
    ap.add_argument("--append", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    levels = tuple(float(x) for x in args.levels.split(","))
    cells = [(r, g, sh, SEED_GEN, h) for r in RATES for g in GAMMAS
             for h in HETERO for sh in SHAPES]
    if args.limit:
        cells = cells[:args.limit]
    head, today = git_head(), date.today().isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if args.append else "w"
    fh = open(OUT, mode, newline="", encoding="utf-8")
    writer = None
    port_rows: list[dict] = []
    try:
        for i, (rate, gamma, shape, seed, hetero) in enumerate(cells, 1):
            t0 = time.perf_counter()
            prep = prepare_cell(rate, gamma, shape, seed, hetero)
            line = []
            for sr in levels:
                pr = with_day_effect(prep, sr)
                for sigma in NOISE:
                    rows = score_under_potential(pr, sigma, 0.0, "iid", 0.0, "q6b")
                    for r in rows:
                        r.update({"sigma_r": sr, "u_seed": u_seed(sr) if sr > 0 else "",
                                  "preregistration_commit": PREREG_COMMIT,
                                  "git_head": head, "run_date": today})
                    if writer is None:
                        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
                        if not args.append:
                            writer.writeheader()
                    for r in rows:
                        writer.writerow({k: r.get(k) for k in writer.fieldnames})
                    fh.flush()
                    if args.check_port and sr == 0.0:
                        port_rows += rows
                    l1 = next((r for r in rows if r["lam"] == "L1"), {})
                    w = l1.get("width")
                    line.append(f"{sr:.2f}/{sigma:.3f}:" + (f"{w:.3f}" if isinstance(w, float)
                                                           and np.isfinite(w) else "--"))
            print(f"[{i:2d}/{len(cells)}] {hetero:<12} r{int(rate * 100):<3} g{gamma} "
                  f"{shape:<9} {time.perf_counter() - t0:5.1f}s L1 " + " ".join(line),
                  flush=True)
    finally:
        fh.close()
    if args.check_port:
        bad = port_check(port_rows)
        if bad:
            print(f"\nPORT CHECK FAILED ({len(bad)}):")
            for b in bad[:30]:
                print("  " + b)
            raise SystemExit(1)
        print(f"\nport check: sigma_r = 0 reproduces Q1 on all {len(port_rows)} rows")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
