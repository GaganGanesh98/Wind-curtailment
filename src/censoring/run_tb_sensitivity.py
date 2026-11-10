"""T-B sensitivity arm — reported, decides nothing.

    python -m src.censoring.run_tb_sensitivity              the arm, n = 50
    python -m src.censoring.run_tb_sensitivity --limit 1    one-cell timing probe
    python -m src.censoring.run_tb_sensitivity --verify-cells 3
    python -m src.censoring.run_tb_sensitivity --report-only

Implements `docs/06_pivot_mechanism_aware_censoring.md`, "T-B sensitivity arm --
reported, decides nothing" and the scheduling correction of 1 November 2026. It is
NOT in `docs/09`, gates nothing, and cannot change the pre-registered T-B verdict,
which stands on the unadjusted `y` from `results/21_tb_primary.csv`.

WHY THIS IS A SEPARATE MODULE
-----------------------------
`run_tb.py` is the pre-registered runner and was executing PASS 1 when this was
written. Editing it mid-run risks the registered artefact for no gain. Every
primitive -- the sign tests, the nested subsampling, the verdict rule -- is imported
from it unchanged, so the arm cannot drift from the thing it is a sensitivity of.

WHAT THE OFFSET IS
------------------
`offset_hat = mean(1 - G/A_hat)` over this cell's UNCENSORED quarter-hours only. On
an uncensored quarter-hour nothing was switched off, so the truth is zero and any
non-zero mean is stage-A level bias plus the Jensen term from its spread. It uses no
censored information and so cannot leak the answer.

HOW THE SHIFT IS APPLIED -- and the choice this involves
--------------------------------------------------------
Every method's target is `y = 1 - G/A_hat`, built inside the method from `G` and
`A_hat` (`tb_methods.fit_b3_cv`, `fit_b6`, and M2's stage r). Shifting `G` by
`offset * A_hat` shifts that target by exactly `-offset`:

    1 - (G + offset*A_hat)/A_hat  ==  (1 - G/A_hat) - offset

so the adjustment is applied ONCE, to the observed output, and every method then
derives its own quantities from the corrected output -- including B3's
`residual = max(0, A_hat - G)`, which is where its response actually comes from.

**This is a choice the specification does not pin down**, and it is recorded here
rather than buried. The alternative is to shift only the regression target and leave
B3's residual on the unadjusted `G`. That was rejected because the arm's stated
rationale is the ASYMMETRY between a response confined to the simplex and a binned
mean that can return a negative bin; leaving B3's residual unadjusted would exempt
B3 from the very adjustment whose asymmetry is being tested. The rejected reading
would measure something, but not that.

`A_hat` is fitted on the ORIGINAL `G` and reused unchanged. Refitting stage A on the
corrected output would be circular -- the offset is measured from `A_hat`.

The censored mask is `c_true > 0`, which no change to `G` can touch, so the cells,
the event-days, the subsample and the fit mask are bit-identical to PASS 1.

WHY ONLY ONE ARM IS COMPUTED
----------------------------
The unadjusted arm already exists, in `results/21_tb_primary.csv`. Recomputing it
would spend another full pass to reproduce numbers that are deterministic given the
seeds. So this module computes the ADJUSTED arm only and compares its verdict against
PASS 1's. `--verify-cells N` spot-checks that assumption by recomputing the
unadjusted arm on the first N cells and reporting any disagreement with PASS 1,
which is the cheap version of the check rather than the 135-cell version.
"""

from __future__ import annotations

import argparse
import csv as _csv
import time
import traceback
from dataclasses import replace
from pathlib import Path

import numpy as np

from src.censoring.metrics import integrated_response_error
from src.censoring.run_reduced_grid import Writer
from src.censoring.run_synthetic import DEPTH_GRID
from src.censoring.synthetic import SyntheticConfig, generate, true_response_curve

# Every criterion, threshold and subsampling rule comes from the registered runner.
from src.censoring.run_tb import (
    GAMMAS,
    N_PRIMARY,
    RATES,
    RESULTS_DIR,
    SEEDS,
    SHAPES,
    event_days,
    fit_mask,
    nested_day_subsets,
    overall,
    score_verdict,
)

OUT_NAME = "25_tb_sensitivity.csv"
PRIMARY_CSV = "21_tb_primary.csv"
LEVELS = (N_PRIMARY,)          # the verdict is defined at n = 50 and nowhere else
EXTRA_FIELDS = ("n_free_params", "param_detail", "chosen_lambda",
                "chosen_bins", "at_grid_boundary")


# ------------------------------------------------------------------ the offset


def offset_hat_from_uncensored(data, a_hat: np.ndarray) -> float:
    """`mean(1 - G/A_hat)` on the uncensored quarter-hours of this cell."""
    y = 1.0 - np.asarray(data.g_obs_mw, dtype=float) / np.maximum(a_hat, 1e-9)
    keep = (~data.censored) & np.isfinite(y)
    vals = y[keep]
    if vals.size == 0:
        raise ValueError("no uncensored quarter-hours to measure the offset on")
    return float(vals.mean())


def shift_target(data, a_hat: np.ndarray, offset: float):
    """Copy of `data` whose `y = 1 - G/A_hat` is shifted by exactly `-offset`."""
    g = np.asarray(data.g_obs_mw, dtype=float) + offset * np.asarray(a_hat, dtype=float)
    return replace(data, g_obs_mw=g)


# -------------------------------------------------------------------- the cell


def score_cell_arm(cfg: SyntheticConfig, specs, shared_stage_a, cohorts,
                   arms=("y_minus_offset",)) -> list[dict]:
    """One cell, one shared stage A, the requested arms at n = 50.

    `arms` may contain "y" (the unadjusted reproduction, for --verify-cells) and
    "y_minus_offset" (the arm itself).
    """
    data = generate(cfg, cohorts=cohorts)
    r_true = true_response_curve(cfg, DEPTH_GRID)
    shared_a = shared_stage_a(data)             # fitted on the ORIGINAL G, reused
    off = offset_hat_from_uncensored(data, shared_a.a_hat)

    days = event_days(data.censored, data.berlin_date)
    subsets = nested_day_subsets(days, LEVELS)

    by_arm = {"y": data, "y_minus_offset": shift_target(data, shared_a.a_hat, off)}
    rows: list[dict] = []
    for arm in arms:
        d = by_arm[arm]
        for lv in LEVELS:
            keep = subsets[lv]
            mask = fit_mask(data.censored, data.berlin_date, keep)
            base = dict(arm=arm, offset_hat=round(off, 8),
                        censoring_rate=cfg.censoring_rate, gamma=cfg.gamma,
                        r_shape=cfg.r_shape, seed=cfg.seed,
                        n_event_days_requested=("all" if lv is None else lv),
                        n_event_days_used=int(len(keep)),
                        n_event_days_available=int(len(days)),
                        short_of_request=bool(lv is not None and len(keep) < lv),
                        n_fit_qh=int(mask.sum()))
            for spec in specs:
                row = dict(base, method=spec.name)
                t0 = time.perf_counter()
                try:
                    fit = spec.fit(d, mask, shared_a)
                    r_hat = spec.curve(fit, d, DEPTH_GRID)
                    from src.censoring.tb_methods import free_params
                    row.update(
                        int_abs_r=float(integrated_response_error(r_hat, r_true,
                                                                 DEPTH_GRID)),
                        failed=False, error="", **free_params(fit),
                    )
                except Exception as exc:                      # guard 1, as in run_tb
                    row.update(int_abs_r=float("nan"), failed=True,
                               n_free_params="", param_detail="",
                               chosen_lambda="", chosen_bins="", at_grid_boundary="",
                               error=f"{type(exc).__name__}: {exc}"[:200])
                    traceback.print_exc()
                row["seconds"] = round(time.perf_counter() - t0, 2)
                rows.append(row)
    return rows


# --------------------------------------------------------------------- the run


def run(cells, arms, out_name: str = OUT_NAME, verbose: bool = True) -> list[dict]:
    from src.censoring.cohorts import mastr_cohort_set
    from src.censoring.tb_methods import build_specs, make_shared_stage_a

    cohorts = mastr_cohort_set("DE")
    specs = build_specs()
    shared = make_shared_stage_a()
    writer = Writer(RESULTS_DIR / out_name, extra_fieldnames=EXTRA_FIELDS)
    rows: list[dict] = []
    t_start = time.perf_counter()
    try:
        for i, (rate, gamma, shape, seed) in enumerate(cells, 1):
            cfg = SyntheticConfig(censoring_rate=rate, gamma=gamma, r_shape=shape,
                                  seed=seed)
            t0 = time.perf_counter()
            try:
                cell_rows = score_cell_arm(cfg, specs, shared, cohorts, arms=arms)
            except Exception:
                print(f"  [{i:>3}/{len(cells)}] CELL FAILED rate {rate} gamma {gamma} "
                      f"{shape} seed {seed}", flush=True)
                traceback.print_exc()
                continue
            for row in cell_rows:
                writer.write(row)
            rows.extend(cell_rows)
            if verbose:
                el = time.perf_counter() - t_start
                off = cell_rows[0]["offset_hat"] if cell_rows else float("nan")
                print(f"  [{i:>3}/{len(cells)}] rate {rate:.0%} gamma {gamma} "
                      f"{shape:<9} seed {seed}  offset {off:+.5f}"
                      f"  {time.perf_counter() - t0:6.1f}s"
                      f"   elapsed {el/60:5.1f}m  eta {el/i*(len(cells)-i)/60:5.1f}m",
                      flush=True)
    finally:
        writer.close()
    return rows


# ------------------------------------------------------------------ comparison


def _read(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return list(_csv.DictReader(fh))


def _coerce(rows: list[dict]) -> list[dict]:
    """CSV strings back into what score_verdict expects."""
    out = []
    for r in rows:
        d = dict(r)
        d["censoring_rate"] = float(r["censoring_rate"])
        d["gamma"] = float(r["gamma"])
        d["seed"] = int(r["seed"])
        d["int_abs_r"] = float(r["int_abs_r"]) if r["int_abs_r"] not in ("", "nan") \
            else float("nan")
        d["failed"] = str(r["failed"]).lower() == "true"
        req = r["n_event_days_requested"]
        d["n_event_days_requested"] = "all" if req == "all" else int(req)
        out.append(d)
    return out


def verify_against_primary(rows: list[dict], n_cells: int) -> None:
    """Report whether the recomputed unadjusted arm reproduces PASS 1 exactly."""
    path = RESULTS_DIR / PRIMARY_CSV
    if not path.exists():
        print(f"  cannot verify: {path.name} not found")
        return
    prim = {(r["censoring_rate"], r["gamma"], r["r_shape"], r["seed"], r["method"]):
            r["int_abs_r"] for r in _read(path)}
    checked = diff = 0
    for r in rows:
        if r["arm"] != "y":
            continue
        key = (f"{r['censoring_rate']}", f"{r['gamma']}", r["r_shape"],
               f"{r['seed']}", r["method"])
        if key not in prim:
            continue
        checked += 1
        a, b = float(r["int_abs_r"]), float(prim[key])
        if not (np.isnan(a) and np.isnan(b)) and abs(a - b) > 1e-12:
            diff += 1
            print(f"    DIFFERS {key}: arm {a:.12f} vs PASS 1 {b:.12f}")
    print(f"\n  determinism check: {checked} rows compared against {PRIMARY_CSV}, "
          f"{diff} differ")
    if checked and not diff:
        print("  the unadjusted arm reproduces PASS 1 exactly; comparing the adjusted "
              "arm against PASS 1 is therefore sound")


def report(rows: list[dict]) -> None:
    """The arm's verdict beside PASS 1's. Reported; gates nothing."""
    adj = [r for r in rows if r["arm"] == "y_minus_offset"]
    offs = sorted({float(r["offset_hat"]) for r in rows})
    print(f"\n{'=' * 100}\nT-B SENSITIVITY ARM at n = {N_PRIMARY} "
          f"(reported, decides nothing)\n{'=' * 100}")
    if offs:
        print(f"  offset_hat across cells: min {offs[0]:+.5f}  "
              f"median {offs[len(offs) // 2]:+.5f}  max {offs[-1]:+.5f}")

    print("\n  --- adjusted arm, y - offset_hat ---")
    v_adj = score_verdict(adj, N_PRIMARY)
    for v in v_adj:
        mark = ("PASS" if v["pass"] else
                "LOSES" if v["loses_significantly"] else "no")
        print(f"  {v['r_shape']:<10}{v['rival']:<11}{v['m2_mean']:>10.5f}"
              f"{v['rival_mean']:>10.5f}  wins {v['wins']:>3}/{v['n_effective']:<3}"
              f" thr {v['threshold']:<3} p {v['p_two_sided']:.4f}  {mark}")
    o_adj = overall(v_adj, N_PRIMARY)

    path = RESULTS_DIR / PRIMARY_CSV
    o_pri = None
    if path.exists():
        pri = _coerce(_read(path))
        o_pri = overall(score_verdict(pri, N_PRIMARY), N_PRIMARY)

    print(f"\n  {'':<46}{'unadjusted (PASS 1)':>22}{'adjusted':>12}")
    keys = list(o_adj["beats_logistic_step"])
    for k in keys:
        a = o_adj["beats_logistic_step"][k]
        b = o_pri["beats_logistic_step"].get(k) if o_pri else None
        print(f"  M2 beats {k:<36}{str(b):>22}{str(a):>12}")
    for k in o_adj["half_not_worse_GATES"]:
        a = o_adj["half_not_worse_GATES"][k]
        b = o_pri["half_not_worse_GATES"].get(k) if o_pri else None
        print(f"  half not worse vs {k:<27}{str(b):>22}{str(a):>12}")
    pv = o_pri["VERDICT"] if o_pri else "unknown"
    print(f"\n  VERDICT{'':<39}{pv:>22}{o_adj['VERDICT']:>12}")
    print(f"  verdict differs between arms: "
          f"{'YES' if o_pri and pv != o_adj['VERDICT'] else 'no'}")
    print("\n  The pre-registered T-B verdict stands on the unadjusted y. This arm "
          "is reported\n  under docs/06 and gates nothing.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="run only the first N cells (timing probe only)")
    ap.add_argument("--verify-cells", type=int, default=0,
                    help="also recompute the UNADJUSTED arm on the first N cells and "
                         "check it reproduces results/21_tb_primary.csv")
    ap.add_argument("--report-only", action="store_true",
                    help="re-report from an existing CSV without refitting")
    args = ap.parse_args()

    cells = [(r, g, sh, sd) for r in RATES for g in GAMMAS
             for sh in SHAPES for sd in SEEDS]
    out = OUT_NAME
    if args.limit:
        cells = cells[:args.limit]
        out = out.replace(".csv", f"_probe{args.limit}.csv")

    if args.report_only:
        rows = _coerce(_read(RESULTS_DIR / out))
        print(f"re-reporting {len(rows):,} rows from {out}")
        report(rows)
        return

    if args.verify_cells:
        n = min(args.verify_cells, len(cells))
        print(f"determinism check on the first {n} cell(s): both arms")
        head = run(cells[:n], arms=("y", "y_minus_offset"),
                   out_name=out.replace(".csv", "_verify.csv"))
        verify_against_primary(head, n)
        rest = cells[n:]
        if not rest:
            report(head)
            return
        print(f"\nproceeding with the adjusted arm on the remaining "
              f"{len(rest)} cell(s)")
        rows = head + run(rest, arms=("y_minus_offset",), out_name=out)
    else:
        print(f"T-B sensitivity arm: {len(cells)} cells, n = {N_PRIMARY}, "
              f"adjusted arm only, writing results/{out}")
        rows = run(cells, arms=("y_minus_offset",), out_name=out)
    report(rows)


if __name__ == "__main__":
    main()
