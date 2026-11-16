"""Phase Q: the potential-accuracy dial, run through P3's scorer unchanged.

    python -m src.method.potential_error --dial q1            # the variance dial
    python -m src.method.potential_error --dial q1 --check-port --limit 2

`docs/Q0_preregistration.md` fixes everything here; nothing below is a choice made
with sight of a result. The potential handed to the share estimator is

    P_t = A_t * exp(e_t),     e_t ~ Normal(mu, sigma^2)
    c_hat_t = 1 - G_t / P_t

and every other piece -- generator, cohorts, design, bounds, epsilon, solver,
functionals, coverage rule -- is P3's, reached through `score_cell`, the degradation
hook split out of `run_p3_synthetic.run_cell`. That split was verified to reproduce
committed Arm O rows bit-for-bit before this module was written.

Q1 (`--dial q1`) sets mu = 0 and walks sigma over Q0 section 3's seven levels, plus
one correlated-noise arm at sigma = 0.180 with AR(1) rho = 0.989. `mu = 0` is
MEDIAN-unbiased, not mean-unbiased (Q0 section 2), so Q1 carries variance only.

**Stage A is not used.** The dial perturbs the TRUE potential, so the shared
cross-fitted stage A and its cache (P3 section 2.4) play no part, and the brief's
instruction to re-verify the cache before relying on it does not arise: nothing here
relies on it.

**The noise seed is common across cells.** Q0 section 2 fixes it as
`42 + 1000*round(1000*sigma) + round(1000*b)`, which does not involve the cell, so
the 54 cells at one grid level share one noise sequence. That is common random
numbers across cells; it is what was pre-registered and is stated wherever the
spread across cells is read.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import time
from datetime import date
from pathlib import Path

import numpy as np

from src.method.synthetic_scoring import (
    GAMMAS, HETERO, RATES, SHAPES, prepare_cell, score_cell,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PREREG_COMMIT = "b261c9f"          # docs/Q0_preregistration.md

SEED_GEN = 45                      # Q0 section 6: Arm D's generator seed
SIGMA_GRID = (0.000, 0.033, 0.066, 0.120, 0.180, 0.250, 0.350)
BIAS_GRID = (-0.100, -0.047, 0.000, 0.033, 0.100)
CROSS_SIGMA = (0.000, 0.066, 0.180)
CROSS_BIAS = (-0.100, 0.000, 0.100)
AR1 = {"sigma": 0.180, "rho": 0.989}
INFORMATIVE_FRACTION = 0.25        # Q0 section 5
P_FLOOR = 1e-9                     # as Arm D: a potential is never divided by zero

ANCHORS = {0.000: "Z", 0.066: "H", 0.180: "T"}


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:                                            # noqa: BLE001
        return "unknown"


def noise_seed(sigma: float, mu: float) -> int:
    """Q0 section 2, verbatim: 42 + 1000*round(1000*sigma) + round(1000*b)."""
    return 42 + 1000 * int(round(1000 * sigma)) + int(round(1000 * mu))


def draw_noise(n: int, order: np.ndarray, sigma: float, mu: float, kind: str,
               rho: float = 0.0) -> np.ndarray:
    """Log-scale noise e_t, laid out in TIME order so AR(1) runs along the clock."""
    if sigma == 0.0:
        return np.full(n, float(mu))
    rng = np.random.default_rng(noise_seed(sigma, mu))
    z = rng.standard_normal(n)
    if kind == "iid":
        e_time = sigma * z
    elif kind == "ar1":
        e_time = np.empty(n)
        e_time[0] = sigma * z[0]                 # stationary start
        k = sigma * np.sqrt(1.0 - rho * rho)
        for t in range(1, n):
            e_time[t] = rho * e_time[t - 1] + k * z[t]
    else:
        raise ValueError(f"unknown noise kind {kind!r}")
    e = np.empty(n)
    e[order] = e_time + mu
    return e


def logical_max_width(lam: str, row: dict) -> float:
    """Q0 section 5: 1 for a response, 2 for a difference, full energy for L5."""
    if lam == "L6":
        return 2.0
    if lam == "L5":
        v = row.get("l5_energy_full_gwh")
        return float(v) if v is not None and np.isfinite(v) else float("nan")
    return 1.0


def score_under_potential(prep: dict, sigma: float, mu: float, kind: str,
                          rho: float, dial: str) -> list[dict]:
    data = prep["data"]
    a = np.asarray(data.a_true_mw, dtype=float)
    g = np.asarray(data.g_obs_mw, dtype=float)
    order = np.argsort(np.asarray(data.ts_utc_ns), kind="stable")
    e = draw_noise(a.size, order, sigma, mu, kind, rho)
    p = np.maximum(a * np.exp(e), P_FLOOR)
    c_hat = 1.0 - g / p
    extra = {
        "dial": dial, "sigma": sigma, "mu": mu, "noise": kind,
        "rho": rho if kind == "ar1" else 0.0,
        "noise_seed": noise_seed(sigma, mu) if sigma > 0 else "",
        "anchor": ANCHORS.get(round(sigma, 3), "") if kind == "iid" and mu == 0 else "",
        "preregistration_commit": PREREG_COMMIT,
    }
    note = (f"P = A*exp(e), e ~ N({mu:+.3f}, {sigma:.3f}^2) {kind}"
            + (f" rho={rho}" if kind == "ar1" else ""))
    rows = score_cell(prep, c_hat, p, arm="Q", stage_a_note=note, extra=extra)
    for r in rows:
        mx = logical_max_width(r["lam"], r)
        w = r.get("width", np.nan)
        r["logical_max_width"] = mx
        r["width_over_max"] = (w / mx if np.isfinite(w) and np.isfinite(mx) and mx > 0
                               else np.nan)
        r["informative"] = (bool(r["width_over_max"] < INFORMATIVE_FRACTION)
                            if np.isfinite(r["width_over_max"]) else None)
    return rows


def plan(dial: str) -> list[tuple[float, float, str, float]]:
    """(sigma, mu, kind, rho) per scoring, as Q0 sections 3 and 4 fix them."""
    if dial == "q1":
        return ([(s, 0.0, "iid", 0.0) for s in SIGMA_GRID]
                + [(AR1["sigma"], 0.0, "ar1", AR1["rho"])])
    if dial == "q2a":
        return [(0.0, b, "iid", 0.0) for b in BIAS_GRID]
    if dial == "q2b":
        return [(s, b, "iid", 0.0) for s in CROSS_SIGMA for b in CROSS_BIAS]
    raise ValueError(dial)


def port_check(rows: list[dict]) -> list[str]:
    """Q0 section 3's dead-end guard: sigma = 0 must reproduce P3 Arm O.

    Compared against the seed-45 rows of `artifacts/P3/p3_synthetic_arm_o.csv` by
    key. Not bit-for-bit: Arm O hands over c_true itself, while sigma = 0 hands over
    1 - G/A, which equals c_true only to floating-point rounding. The tolerance is
    therefore the solver's, not zero.
    """
    import polars as pl

    from src.method.read_results import load

    ref = load(REPO_ROOT / "artifacts" / "P3" / "p3_synthetic_arm_o.csv")
    out = []
    for r in rows:
        if r.get("sigma") != 0.0 or r.get("mu") != 0.0 or r.get("noise") != "iid":
            continue
        m = ref.filter((pl.col("hetero") == r["hetero"]) & (pl.col("rate") == r["rate"])
                       & (pl.col("gamma") == r["gamma"]) & (pl.col("r_shape") == r["r_shape"])
                       & (pl.col("seed") == r["seed"]) & (pl.col("lam") == r["lam"]))
        if m.height != 1:
            out.append(f"no Arm O row for {r['hetero']}/{r['rate']}/{r['gamma']}/"
                       f"{r['r_shape']}/{r['lam']}")
            continue
        for col in ("lo", "hi", "width", "truth"):
            a, b = float(r[col]), float(m[col][0])
            if np.isfinite(a) or np.isfinite(b):
                tol = 1e-6 * max(1.0, abs(b))
                if not abs(a - b) <= tol:
                    out.append(f"{r['hetero']}/{r['rate']}/{r['gamma']}/{r['r_shape']}/"
                               f"{r['lam']} {col}: sigma=0 gives {a!r}, Arm O {b!r}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dial", choices=("q1", "q2a", "q2b"), default="q1")
    ap.add_argument("--limit", type=int, default=0, help="first N cells only (probe)")
    ap.add_argument("--check-port", action="store_true",
                    help="also compare sigma = 0 with P3 Arm O and fail on a mismatch")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    cells = [(r, g, sh, SEED_GEN, h) for r in RATES for g in GAMMAS
             for h in HETERO for sh in SHAPES]
    if args.limit:
        cells = cells[:args.limit]
    steps = plan(args.dial)

    out_dir = REPO_ROOT / "artifacts" / ("Q1" if args.dial == "q1" else "Q2")
    out_dir.mkdir(parents=True, exist_ok=True)
    names = {"q1": "q1_variance_dial.csv", "q2a": "q2a_bias_dial.csv",
             "q2b": "q2b_crossed.csv"}
    out_path = Path(args.out) if args.out else out_dir / names[args.dial]
    head, today = git_head(), date.today().isoformat()

    print(f"dial {args.dial}: {len(cells)} cells x {len(steps)} potentials = "
          f"{len(cells) * len(steps)} scorings -> {out_path}", flush=True)
    fh = writer = None
    port_rows: list[dict] = []
    try:
        for i, (rate, gamma, shape, seed, hetero) in enumerate(cells, 1):
            t0 = time.perf_counter()
            prep = prepare_cell(rate, gamma, shape, seed, hetero)
            line = []
            for sigma, mu, kind, rho in steps:
                rows = score_under_potential(prep, sigma, mu, kind, rho, args.dial)
                for r in rows:
                    r["git_head"], r["run_date"] = head, today
                if writer is None:
                    fh = open(out_path, "w", newline="", encoding="utf-8")
                    fields = list(rows[0])
                    writer = csv.DictWriter(fh, fieldnames=fields)
                    writer.writeheader()
                for r in rows:
                    writer.writerow({k: r.get(k) for k in writer.fieldnames})
                fh.flush()
                if args.check_port:
                    port_rows += rows
                l1 = next((r for r in rows if r["lam"] == "L1"), {})
                w = l1.get("width")
                line.append(f"{sigma:.3f}{'r' if kind == 'ar1' else ''}"
                            f"{mu:+.2f}:" + (f"{w:.3f}" if isinstance(w, float)
                                             and np.isfinite(w) else "--"))
            print(f"[{i:2d}/{len(cells)}] {hetero:<12} r{int(rate * 100):<3} g{gamma} "
                  f"{shape:<9} {time.perf_counter() - t0:5.1f}s  L1 width: "
                  + " ".join(line), flush=True)
    finally:
        if fh is not None:
            fh.close()

    if args.check_port:
        bad = port_check(port_rows)
        if bad:
            print(f"\nPORT CHECK FAILED ({len(bad)}):")
            for b in bad[:20]:
                print("  " + b)
            raise SystemExit(1)
        print(f"\nport check: sigma = 0 reproduces P3 Arm O on every compared row")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
