#!/usr/bin/env python3
"""Task 1 (docs/22): re-select M2's smoothing parameter on the widened grid.

The 9 Nov T-B run chose lambda at the top of its CV grid (100.0) in 104 of 135
M2 fits (results/40_m2_lambda_boundary.csv), so the search was clipped, not
converged, and the T-B PASS is provisional. This runner re-runs the inner CV on
the widened LAMBDA_GRID -- (0.0,) + logspace(-6, 4, 21), old grid an exact float
subset -- for every T-B cell, through the UNCHANGED fit, curve and scoring code:
the M2 MethodSpec from tb_methods.build_specs(), the shared stage A, the same
event-day subsets and fit mask as run_tb.score_cell, and
integrated_response_error on the same DEPTH_GRID. Nothing in any of those is
modified; the only code change behind this run is the LAMBDA_GRID constant.

Per cell it records the old selection (from results/21_tb_primary.csv), the new
one, boundary status against the widened grid, and a determinism cross-check:
the first minimum of the new CV log restricted to the old grid points, in old
grid order, must equal the stored chosen_lambda. A cell failing that check means
the cell was not reproduced bit-for-bit and its "unchanged, reuse the existing
score" bookkeeping would be unsound; the run flags it rather than hiding it.

Outputs:
  results/41_tb_lambda_widening.csv    one row per M2 fit (appended as it goes)
  results/42_tb_primary_widened_lambda.csv   (--splice) the 945-row table with
      M2 rows' int_abs_r replaced ONLY where the selection changed (the brief:
      unchanged selection reuses the existing score), chosen_lambda and
      at_grid_boundary updated for all M2 rows to state the new-grid facts.
Then the verdict is recomputed by run_tb.report() on the spliced rows -- the
unchanged scorer, fixed for the CSV path in f2b601f.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.censoring import run_tb as T                     # noqa: E402
from src.censoring.cohorts import mastr_cohort_set        # noqa: E402
from src.censoring.m2 import LAMBDA_GRID                  # noqa: E402
from src.censoring.tb_methods import build_specs, make_shared_stage_a  # noqa: E402

#: The 9 Nov grid, verbatim, for the cross-check and the old-order tie rule.
OLD_GRID = (0.0,) + tuple(np.logspace(-4, 2, 13))

RESULTS = REPO_ROOT / "results"
PRIMARY = RESULTS / "21_tb_primary.csv"
OUT = RESULTS / "41_tb_lambda_widening.csv"
SPLICED = RESULTS / "42_tb_primary_widened_lambda.csv"
N_LEVEL = 50

FIELDS = ["censoring_rate", "gamma", "r_shape", "seed",
          "old_lambda", "new_lambda", "selection_changed",
          "old_edge", "new_edge", "reproduced_old_selection",
          "old_int_abs_r", "new_int_abs_r", "score_used", "seconds"]


def edge_of(lam: float, grid) -> str:
    return ("lambda_max" if lam >= max(grid) - 1e-9 else
            "lambda_min" if lam <= min(grid) else "interior")


def old_m2_rows() -> dict[tuple, dict]:
    out = {}
    with open(PRIMARY, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["method"] == "M2":
                key = (float(r["censoring_rate"]), float(r["gamma"]),
                       r["r_shape"], int(r["seed"]))
                out[key] = r
    if len(out) != 135:
        raise SystemExit(f"expected 135 M2 rows in {PRIMARY.name}, found {len(out)}")
    return out


def first_min_in_order(cv_log: list[dict], grid) -> float:
    """choose_lambda's own tie rule -- min() returns the first minimum in grid
    order -- applied to the subset `grid`, in `grid`'s order."""
    by_lam = {e["lambda"]: e["cv_weighted_sse"] for e in cv_log}
    sub = [(lam, by_lam[lam]) for lam in grid]
    return min(sub, key=lambda t: t[1])[0]


def run(cells, out_path: Path, append: bool) -> None:
    cohorts = mastr_cohort_set("DE")
    m2 = next(s for s in build_specs() if s.name == "M2")
    shared = make_shared_stage_a()
    old = old_m2_rows()

    mode = "a" if append and out_path.exists() else "w"
    with open(out_path, mode, newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if mode == "w":
            w.writeheader()
        for i, (rate, gamma, shape, seed) in enumerate(cells, 1):
            t0 = time.perf_counter()
            orow = old[(rate, gamma, shape, seed)]
            old_lam = float(orow["chosen_lambda"])
            old_score = float(orow["int_abs_r"])

            cfg = T.SyntheticConfig(censoring_rate=rate, gamma=gamma,
                                    r_shape=shape, seed=seed)
            data = T.generate(cfg, cohorts=cohorts)
            r_true = T.true_response_curve(cfg, T.DEPTH_GRID)
            shared_a = shared(data)
            days = T.event_days(data.censored, data.berlin_date)
            keep = T.nested_day_subsets(days, (N_LEVEL,))[N_LEVEL]
            mask = T.fit_mask(data.censored, data.berlin_date, keep)

            fit = m2.fit(data, mask, shared_a)
            new_lam = float(fit["lambda"])
            r_hat = m2.curve(fit, data, T.DEPTH_GRID)
            new_score = float(T.integrated_response_error(r_hat, r_true,
                                                          T.DEPTH_GRID))
            reproduced = (first_min_in_order(fit["cv_log"], OLD_GRID) == old_lam)
            changed = (new_lam != old_lam)
            row = {
                "censoring_rate": rate, "gamma": gamma, "r_shape": shape,
                "seed": seed, "old_lambda": old_lam, "new_lambda": new_lam,
                "selection_changed": changed,
                "old_edge": edge_of(old_lam, OLD_GRID),
                "new_edge": edge_of(new_lam, LAMBDA_GRID),
                "reproduced_old_selection": reproduced,
                "old_int_abs_r": old_score, "new_int_abs_r": new_score,
                "score_used": "rescored" if changed else "existing",
                "seconds": round(time.perf_counter() - t0, 2),
            }
            w.writerow(row)
            fh.flush()
            print(f"  [{i:>3}/{len(cells)}] r{rate:.0%} g{gamma} {shape:<9} s{seed}"
                  f"  {old_lam:g} -> {new_lam:g}"
                  f"  {'CHANGED ' if changed else 'same    '}"
                  f"edge={row['new_edge']:<10} repro={reproduced}"
                  f"  {row['seconds']:.0f}s", flush=True)


def splice() -> None:
    """results/42: unchanged scorer input, new-grid facts, scores per the brief."""
    widened = {(r["censoring_rate"], r["gamma"], r["r_shape"], r["seed"]): r
               for r in csv.DictReader(open(OUT, encoding="utf-8"))}
    if len(widened) != 135:
        raise SystemExit(f"{OUT.name} has {len(widened)} cells, need all 135")
    bad = [k for k, r in widened.items()
           if r["reproduced_old_selection"] != "True"]
    if bad:
        raise SystemExit(f"{len(bad)} cell(s) failed the determinism cross-check; "
                         f"splicing would be unsound: {bad[:5]}")

    with open(PRIMARY, encoding="utf-8") as fh:
        rd = csv.DictReader(fh)
        fields = rd.fieldnames
        rows = list(rd)
    n_spliced = 0
    for r in rows:
        if r["method"] != "M2":
            continue
        k = (r["censoring_rate"], r["gamma"], r["r_shape"], r["seed"])
        wrow = widened[k]
        new_edge = wrow["new_edge"]
        r["at_grid_boundary"] = "" if new_edge == "interior" else new_edge
        r["chosen_lambda"] = wrow["new_lambda"]
        if wrow["selection_changed"] == "True":
            r["int_abs_r"] = wrow["new_int_abs_r"]
            n_spliced += 1
    with open(SPLICED, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"spliced {n_spliced} re-scored M2 cells into {SPLICED.name} "
          f"({len(rows)} rows); unchanged cells keep the existing score")
    print("\nVERDICT on the widened-lambda table, unchanged scorer:")
    T.report(rows, levels=(N_LEVEL,))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="probe: only the first N cells")
    ap.add_argument("--out", default=None, help="override the per-cell CSV path")
    ap.add_argument("--append", action="store_true",
                    help="append to an existing per-cell CSV (crash resume)")
    ap.add_argument("--splice", action="store_true",
                    help="build results/42 and recompute the verdict; no fitting")
    a = ap.parse_args()
    if a.splice:
        splice()
        return
    cells = [(r, g, sh, sd) for r in T.RATES for g in T.GAMMAS
             for sh in T.SHAPES for sd in T.SEEDS]
    if a.append and Path(a.out or OUT).exists():
        done = {(float(r["censoring_rate"]), float(r["gamma"]), r["r_shape"],
                 int(r["seed"]))
                for r in csv.DictReader(open(a.out or OUT, encoding="utf-8"))}
        cells = [c for c in cells if c not in done]
        print(f"resume: {len(done)} done, {len(cells)} to go", flush=True)
    if a.limit:
        cells = cells[: a.limit]
    print(f"widened-grid CV for {len(cells)} cells; grid "
          f"{len(LAMBDA_GRID)} points [{min(LAMBDA_GRID)}, {max(LAMBDA_GRID)}]",
          flush=True)
    run(cells, Path(a.out or OUT), a.append)


if __name__ == "__main__":
    main()
