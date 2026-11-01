"""Free-parameter counts per (cell, n-level, method), for a run that predates them.

    python -m src.censoring.tb_param_counts --pass primary

The reporting addition of 1 Nov 2026 asks for each method's free-parameter count
beside the stage-r observation count in `results/21_tb_*.csv`. `run_tb.py` now emits
both columns, so **PASS 2 carries them natively** — but PASS 1 was already running
when the column was added and a running process cannot pick up a code change. Rather
than restart a 9.5-hour job for two reporting columns, they are recomputed here and
joined on the cell key.

The counts are deterministic given the cell, the n-level and the shared stage A, so
this reproduces exactly what the run would have written. It does not refit M2: the
M2 family's count is `blocks x knots`, which depends only on the data and the mask
and needs no optimisation. B3-CV's chosen bin count and B6's tree and leaf counts do
need their inner CV, which needs the shared stage A — that is the cost, about 25 s
per cell against the run's 254 s.

**Read the counts across families with care.** A bin count, a simplex-constrained
knot grid and a boosted ensemble's leaf count are not the same kind of quantity. M2's
654 parameters lie on 6 simplexes, so each block spends its mass rather than ranging
freely and the effective dimension is far below the nominal one; B6's 1,400 is
trees x max-leaves, an upper bound that boosting's shrinkage does not reach. The
honest use is to notice the ORDER OF MAGNITUDE against the ~681 observations at
n = 50, not to treat the three numbers as commensurable.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import numpy as np

from src.censoring.cohorts import mastr_cohort_set
from src.censoring.m2 import knot_grid, pool_blocks
from src.censoring.model import TrainConfig
from src.censoring.run_tb import (
    GAMMAS,
    N_PRIMARY,
    N_SECONDARY,
    RATES,
    SEEDS,
    SHAPES,
    event_days,
    fit_mask,
    nested_day_subsets,
)
from src.censoring.synthetic import SyntheticConfig, generate

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"


def m2_param_count(data, mask, atom: bool) -> tuple[int, str]:
    """blocks x knots — needs no fit, only the data and the mask."""
    shares = np.asarray(data.cohorts.shares, dtype=float)
    _, members = pool_blocks(data.s, data.depth, shares)
    knots = knot_grid(data.depth, np.asarray(mask, dtype=bool), with_atom=atom)
    return len(members) * knots.size, f"{len(members)} blocks x {knots.size} knots"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pass", dest="which", choices=("primary", "secondary"),
                    default="primary")
    args = ap.parse_args()
    levels = (N_PRIMARY,) if args.which == "primary" else N_SECONDARY
    out = RESULTS_DIR / (f"21_tb_primary_params.csv" if args.which == "primary"
                         else "22_tb_secondary_params.csv")

    from src.censoring.m2 import fit_shared_stage_a
    from src.censoring.tb_methods import fit_b3_cv, fit_b6, free_params

    cohorts = mastr_cohort_set("DE")
    cfg = TrainConfig()
    cells = [(r, g, sh, sd) for r in RATES for g in GAMMAS
             for sh in SHAPES for sd in SEEDS]
    rows, t0 = [], time.perf_counter()

    for i, (rate, gamma, shape, seed) in enumerate(cells, 1):
        data = generate(SyntheticConfig(censoring_rate=rate, gamma=gamma,
                                        r_shape=shape, seed=seed), cohorts=cohorts)
        sa = fit_shared_stage_a(data, cfg=cfg, check=False)
        days = event_days(data.censored, data.berlin_date)
        subsets = nested_day_subsets(days, levels)
        for lv in levels:
            mask = fit_mask(data.censored, data.berlin_date, subsets[lv])
            base = dict(censoring_rate=rate, gamma=gamma, r_shape=shape, seed=seed,
                        n_event_days_requested=("all" if lv is None else lv),
                        n_fit_qh=int(mask.sum()))
            for name, atom in (("M2", True), ("M2-noPool", True),
                               ("M2-noAtom", False)):
                n, detail = m2_param_count(data, mask, atom)
                rows.append(dict(base, method=name, n_free_params=n,
                                 param_detail=detail))
            for name, fn in (("B3-CV", fit_b3_cv), ("B6", fit_b6)):
                try:
                    fp = free_params(fn(data, mask, sa))
                    rows.append(dict(base, method=name, **fp))
                except Exception as exc:
                    rows.append(dict(base, method=name, n_free_params="",
                                     param_detail=f"FAILED {type(exc).__name__}"))
            for name, nb, edges in (("B3@8", 8, None),
                                    ("B3-H", 8, "hirth")):
                rows.append(dict(base, method=name,
                                 n_free_params="", param_detail="fixed bins; see run"))
        el = time.perf_counter() - t0
        print(f"  [{i:>3}/{len(cells)}] rate {rate:.0%} gamma {gamma} {shape:<9} "
              f"seed {seed}   elapsed {el/60:5.1f}m  eta "
              f"{el/i*(len(cells)-i)/60:5.1f}m", flush=True)

    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {out.relative_to(REPO_ROOT)}")

    sel = [r for r in rows if r["n_event_days_requested"] == N_PRIMARY]
    if sel:
        obs = int(np.median([r["n_fit_qh"] for r in sel]))
        print(f"\nAt n = {N_PRIMARY}: median stage-r observations {obs}")
        for m in ("M2", "B3-CV", "B6"):
            v = [r["n_free_params"] for r in sel
                 if r["method"] == m and isinstance(r["n_free_params"], int)]
            if v:
                print(f"  {m:<8}free params median {int(np.median(v)):>6}  "
                      f"range [{min(v)}, {max(v)}]  "
                      f"params per observation {np.median(v)/obs:.2f}")


if __name__ == "__main__":
    main()
