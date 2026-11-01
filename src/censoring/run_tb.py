"""T-B — the sample-size arm. The decisive experiment of the M2 programme.

    python -m src.censoring.run_tb --pass primary     n = 50 only, the verdict
    python -m src.censoring.run_tb --pass secondary   n in {20, 100, all} + arms

Implements Amendment 3 section 0.3 T-B of `docs/09_m2_preregistration.md`.
Nothing here chooses a threshold or a criterion; the pre-registration fixed those
before any M2 number existed, and this module must not be edited to change them.

WHAT THIS MEASURES
------------------
Does a jump-capable, pooled, bin-free response estimator beat cross-validated
binning when switch-off days are scarce? That is the only claim the real data can
reward: the real German signal lives in about five event-days out of 99
(`results/02_robustness_de.csv`), so the scarce-data regime is the realistic one
and `n = all` is the unrealistic one.

This module is written to CATCH M2 OUT, not to confirm it. Four places where a
careless implementation would quietly favour it, and what is done instead:

  1. A method that raises at small n must not vanish from the comparison. Dropping
     its cell removes exactly the cases it finds hard. Failures are recorded and
     scored as losses (`failed=True`, `better=False`).
  2. Every method in a cell sees the SAME subsample of event-days, so the paired
     test is genuinely paired.
  3. Every method's inner cross-validation -- M2's lambda, B3-CV's bin count,
     B6's hyperparameters -- sees ONLY the selected days. Otherwise the baseline
     is tuned on data M2 was denied, or the reverse.
  4. Exact ties are excluded from the sign test and the effective n is reduced,
     rather than being counted for either side. A tie counted as a win is the
     cheapest way to manufacture a result.

WHY SUBSAMPLING IS A FIT MASK, NOT A REGENERATION
-------------------------------------------------
Stage A is fitted on quarter-hours above the safe price floor, which no choice of
event-days touches. Restricting the stage-r fit therefore leaves A-hat bit-identical
across all n-levels, so a difference between n = 20 and n = all is attributable to
the response estimation and nothing else. Regenerating the data per n-level would
confound the two.

The subsets are NESTED -- the 20 lie inside the 50, inside the 100 -- so the
n-levels form a sequence on one cell rather than four unrelated draws.
"""

from __future__ import annotations

import argparse
import time
import traceback
from dataclasses import dataclass
from math import comb
from pathlib import Path

import numpy as np

from src.censoring.metrics import integrated_response_error
from src.censoring.run_reduced_grid import Writer
from src.censoring.run_synthetic import DEPTH_GRID
from src.censoring.synthetic import SyntheticConfig, generate, true_response_curve

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"

# Amendment 3 section 0.1. Seeds disjoint from the gate's 42-44.
RATES = (0.10, 0.20, 0.40)
GAMMAS = (0.0, 0.5, 1.0)
SHAPES = ("step", "logistic", "half")
SEEDS = (45, 46, 47, 48, 49)

N_PRIMARY = 50
N_SECONDARY = (20, 100, None)        # None = every event-day in the cell
SUBSAMPLE_SEED = 42                  # fixes WHICH days, independently of the cell seed

# Amendment 3 section 0.3 T-B. M2 must beat BOTH on logistic AND step, and not be
# significantly worse on half.
PRIMARY_RIVALS = ("B3-CV", "B6")
REPORTED_RIVALS = ("B3@8", "B3-H", "M2-noPool", "M2-noAtom")


# --------------------------------------------------------------- the sign test


def sign_test_threshold(n: int, alpha: float = 0.05) -> int:
    """Smallest k with exact two-sided binomial p < alpha under H0: p = 0.5.

    Computed, never hard-coded: the pass bar must follow from n, and n changes
    whenever ties are excluded.
    """
    if n <= 0:
        return 0
    total = 2.0 ** n
    for k in range(n, n // 2, -1):
        tail = sum(comb(n, i) for i in range(k, n + 1)) / total
        if 2.0 * tail >= alpha:
            return k + 1
    return n // 2 + 1


def exact_two_sided_p(k: int, n: int) -> float:
    """P(|X - n/2| >= |k - n/2|) under Binom(n, 1/2)."""
    if n <= 0:
        return 1.0
    total = 2.0 ** n
    hi = max(k, n - k)
    tail = sum(comb(n, i) for i in range(hi, n + 1)) / total
    return min(1.0, 2.0 * tail)


def sign_test(diffs: np.ndarray, alpha: float = 0.05) -> dict:
    """`diffs` = metric(M2) - metric(rival), one per paired cell. Lower is better.

    Exact zeros are TIES: dropped, and the effective n reduced. Counting a tie for
    either side is the cheapest way to manufacture a verdict.
    """
    d = np.asarray(diffs, dtype=float)
    # BUG FIXED 1 Nov 2026. This previously filtered on np.isfinite(d), which
    # defeated guard 1: a single-method failure gives inf - finite = +inf (or -inf
    # the other way), isfinite is False, and the cell was DROPPED -- removing
    # exactly the cases the failing method found hard, which is what guard 1 exists
    # to prevent. Only BOTH failing is uninformative (inf - inf = nan). A +inf is a
    # loss for M2 and a -inf is a win, and `d < 0` already classifies them correctly
    # once they are allowed through.
    informative = ~np.isnan(d)
    ties = int((informative & (d == 0.0)).sum())
    used = d[informative & (d != 0.0)]
    n_eff = used.size
    wins = int((used < 0.0).sum())
    threshold = sign_test_threshold(n_eff, alpha)
    return {
        "n_cells": int(d.size), "n_nonfinite": int(np.isnan(d).sum()), "n_ties": ties,
        "n_m2_failed": int((d == np.inf).sum()),
        "n_rival_failed": int((d == -np.inf).sum()),
        "n_effective": n_eff, "wins": wins, "threshold": threshold,
        "p_two_sided": exact_two_sided_p(wins, n_eff),
        "pass": bool(n_eff > 0 and wins >= threshold),
        "loses_significantly": bool(n_eff > 0 and (n_eff - wins) >= threshold),
    }


# --------------------------------------------------------------- subsampling


def event_days(censored: np.ndarray, berlin_date: np.ndarray) -> np.ndarray:
    """Calendar days carrying at least one censored quarter-hour, sorted."""
    return np.unique(np.asarray(berlin_date)[np.asarray(censored, dtype=bool)])


def nested_day_subsets(days: np.ndarray, levels, seed: int = SUBSAMPLE_SEED) -> dict:
    """{level: selected days}. Nested: the 20 lie inside the 50, inside the 100.

    One permutation, then prefixes. A level larger than the available days takes
    all of them and is flagged by the caller, never silently clipped into a
    different experiment.
    """
    order = np.asarray(days)[np.random.default_rng(seed).permutation(len(days))]
    out = {}
    for lv in levels:
        k = len(order) if lv is None else min(int(lv), len(order))
        out[lv] = np.sort(order[:k])
    return out


def fit_mask(censored: np.ndarray, berlin_date: np.ndarray,
             keep_days: np.ndarray) -> np.ndarray:
    """Censored quarter-hours on the selected event-days: the stage-r fit sample.

    Stage A is unaffected -- it trains above the safe price floor -- so A-hat stays
    bit-identical across n-levels and any difference is the response estimation.
    """
    on_day = np.isin(np.asarray(berlin_date), np.asarray(keep_days))
    return np.asarray(censored, dtype=bool) & on_day


# ------------------------------------------------------------------ the cell


@dataclass
class MethodSpec:
    """Injected wiring. `fit(data, fit_mask, shared_a)` -> fit dict;
    `curve(fit, data, depth_grid)` -> r-hat on the grid.

    Injected rather than imported so this module is testable before B3-CV, B6 and
    the shared stage-A hook exist, and so no method can be special-cased here.
    EVERY fit MUST confine its inner cross-validation to `fit_mask`.
    """
    name: str
    fit: callable
    curve: callable


def score_cell(cfg: SyntheticConfig, specs: list[MethodSpec], levels,
               shared_stage_a: callable, cohorts) -> list[dict]:
    data = generate(cfg, cohorts=cohorts)
    r_true = true_response_curve(cfg, DEPTH_GRID)
    shared_a = shared_stage_a(data)          # once per cell, reused at every level
    days = event_days(data.censored, data.berlin_date)
    subsets = nested_day_subsets(days, levels)

    rows = []
    for lv in levels:
        keep = subsets[lv]
        mask = fit_mask(data.censored, data.berlin_date, keep)
        base = dict(censoring_rate=cfg.censoring_rate, gamma=cfg.gamma,
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
                fit = spec.fit(data, mask, shared_a)
                r_hat = spec.curve(fit, data, DEPTH_GRID)
                # Reporting addition, 1 Nov 2026: the stage-r sample size is already
                # in n_fit_qh; this adds how many parameters the method spent on it.
                from src.censoring.tb_methods import free_params
                row.update(
                    int_abs_r=float(integrated_response_error(r_hat, r_true,
                                                              DEPTH_GRID)),
                    failed=False, error="", **free_params(fit),
                )
            except Exception as exc:                       # guard 1
                row.update(int_abs_r=float("nan"), failed=True,
                           n_free_params="", param_detail="",
                           error=f"{type(exc).__name__}: {exc}"[:200])
                traceback.print_exc()
            row["seconds"] = round(time.perf_counter() - t0, 2)
            rows.append(row)
    return rows


# -------------------------------------------------------------- the verdict


def _safe_mean(vals) -> float:
    """Mean of the finite entries; nan if every fit in the stratum failed."""
    f = [v for v in vals if np.isfinite(v)]
    return float(np.mean(f)) if f else float("nan")


def score_verdict(rows: list[dict], n_level, alpha: float = 0.05) -> list[dict]:
    """Paired sign tests per shape per rival, on one n-level.

    A failed fit scores as a loss for that method, so robustness is part of the
    comparison rather than a way out of it.
    """
    def metric(shape, method):
        out = {}
        for r in rows:
            if r["r_shape"] != shape or r["method"] != method:
                continue
            if r["n_event_days_requested"] != ("all" if n_level is None else n_level):
                continue
            key = (r["censoring_rate"], r["gamma"], r["seed"])
            out[key] = float("inf") if r["failed"] else r["int_abs_r"]
        return out

    verdicts = []
    for shape in SHAPES:
        m2 = metric(shape, "M2")
        for rival in PRIMARY_RIVALS + REPORTED_RIVALS:
            rv = metric(shape, rival)
            keys = sorted(set(m2) & set(rv))
            # inf - inf is nan: both failed, no information, excluded as non-finite
            diffs = np.array([m2[k] - rv[k] for k in keys], dtype=float)
            st = sign_test(diffs, alpha)
            verdicts.append(dict(
                n_event_days=("all" if n_level is None else n_level),
                r_shape=shape, rival=rival, decisive=rival in PRIMARY_RIVALS,
                m2_mean=_safe_mean([m2[k] for k in keys]),
                rival_mean=_safe_mean([rv[k] for k in keys]),
                **st))
    return verdicts


def overall(verdicts: list[dict], n_level) -> dict:
    """Amendment 3 section 0.3 T-B, applied verbatim. No other reading is permitted here."""
    tag = "all" if n_level is None else n_level
    def v(shape, rival):
        for x in verdicts:
            if x["n_event_days"] == tag and x["r_shape"] == shape and x["rival"] == rival:
                return x
        return None

    beats = {(s, r): v(s, r) for s in ("logistic", "step") for r in PRIMARY_RIVALS}
    # CORRECTED 1 Nov 2026. This required "not significantly worse on half" against
    # BOTH primary rivals, which is STRICTER than the pre-registration. Amendment 3
    # section 0.3 T-B reads: "...AND M2 not significantly worse than B3-CV on half,
    # AND M2 lower than B6 in >= threshold of 45 cells on logistic AND step." The
    # half clause names B3-CV ALONE. The pre-registration is binding and frozen, so
    # it is applied verbatim; B6-on-half is reported but does not gate.
    half_gate = {"B3-CV": v("half", "B3-CV")}
    half_reported = {r: v("half", r) for r in PRIMARY_RIVALS if r != "B3-CV"}
    passed = (all(x is not None and x["pass"] for x in beats.values())
              and all(x is not None and not x["loses_significantly"]
                      for x in half_gate.values()))
    return {
        "n_event_days": tag,
        "beats_logistic_step": {f"{s} vs {r}": (x["pass"] if x else None)
                                for (s, r), x in beats.items()},
        "half_not_worse_GATES": {r: ((not x["loses_significantly"]) if x else None)
                                 for r, x in half_gate.items()},
        "half_reported_only": {r: ((not x["loses_significantly"]) if x else None)
                               for r, x in half_reported.items()},
        "VERDICT": "PASS" if passed else "FAIL",
    }


def run(levels, out_name: str, cells=None, verbose: bool = True) -> list[dict]:
    """The cell loop. One shared stage A per cell, reused at every n-level."""
    from src.censoring.cohorts import mastr_cohort_set
    from src.censoring.tb_methods import build_specs, make_shared_stage_a

    cohorts = mastr_cohort_set("DE")
    specs = build_specs()
    shared = make_shared_stage_a()
    cells = cells or [(r, g, sh, sd) for r in RATES for g in GAMMAS
                      for sh in SHAPES for sd in SEEDS]
    writer = Writer(RESULTS_DIR / out_name,
                    extra_fieldnames=("n_free_params", "param_detail"))
    rows: list[dict] = []
    t_start = time.perf_counter()
    try:
        for i, (rate, gamma, shape, seed) in enumerate(cells, 1):
            cfg = SyntheticConfig(censoring_rate=rate, gamma=gamma, r_shape=shape,
                                  seed=seed)
            t0 = time.perf_counter()
            try:
                cell_rows = score_cell(cfg, specs, levels, shared, cohorts)
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
                print(f"  [{i:>3}/{len(cells)}] rate {rate:.0%} gamma {gamma} "
                      f"{shape:<9} seed {seed}  {time.perf_counter() - t0:6.1f}s"
                      f"   elapsed {el/60:5.1f}m  eta {el/i*(len(cells)-i)/60:5.1f}m",
                      flush=True)
    finally:
        writer.close()
    return rows


def report(rows: list[dict], levels) -> None:
    """Sign tests per shape per rival, then the pre-registered verdict, verbatim."""
    for lv in levels:
        tag = "all" if lv is None else lv
        verdicts = score_verdict(rows, lv)
        print(f"\n{'=' * 100}\nT-B at n_event_days = {tag}\n{'=' * 100}")
        print(f"  {'shape':<10}{'rival':<11}{'M2 mean':>10}{'rival':>10}"
              f"{'wins':>7}{'n_eff':>7}{'thr':>5}{'p':>9}{'ties':>6}"
              f"{'M2 fail':>9}{'riv fail':>9}  verdict")
        for v in verdicts:
            mark = ("PASS" if v["pass"] else
                    "LOSES" if v["loses_significantly"] else "no")
            print(f"  {v['r_shape']:<10}{v['rival']:<11}{v['m2_mean']:>10.5f}"
                  f"{v['rival_mean']:>10.5f}{v['wins']:>7}{v['n_effective']:>7}"
                  f"{v['threshold']:>5}{v['p_two_sided']:>9.4f}{v['n_ties']:>6}"
                  f"{v['n_m2_failed']:>9}{v['n_rival_failed']:>9}  "
                  f"{mark}{'  (decisive)' if v['decisive'] else ''}")
        o = overall(verdicts, lv)
        print(f"\n  Pre-registered rule (Amendment 3 section 0.3 T-B), applied verbatim:")
        for k, val in o["beats_logistic_step"].items():
            print(f"    M2 beats {k:<22} {val}")
        for k, val in o["half_not_worse_GATES"].items():
            print(f"    M2 not significantly worse on half vs {k:<8} {val}   [GATES]")
        for k, val in o["half_reported_only"].items():
            print(f"    (reported only) half vs {k:<19} {val}")
        print(f"\n  T-B VERDICT at n = {tag}: {o['VERDICT']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pass", dest="which", choices=("primary", "secondary"),
                    default="primary")
    ap.add_argument("--limit", type=int, default=None,
                    help="run only the first N cells (timing probe only)")
    args = ap.parse_args()
    levels = (N_PRIMARY,) if args.which == "primary" else N_SECONDARY
    out = ("21_tb_primary.csv" if args.which == "primary"
           else "22_tb_secondary.csv")
    cells = [(r, g, sh, sd) for r in RATES for g in GAMMAS
             for sh in SHAPES for sd in SEEDS]
    if args.limit:
        cells = cells[:args.limit]
        out = out.replace(".csv", f"_probe{args.limit}.csv")
    print(f"T-B {args.which}: {len(cells)} cells, levels={levels}, "
          f"writing results/{out}")
    rows = run(levels, out, cells=cells)
    report(rows, levels)


if __name__ == "__main__":
    main()
