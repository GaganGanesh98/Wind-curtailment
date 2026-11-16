"""Power check: can the Oracle pass the gate's own criteria?

**This is a DIAGNOSTIC. It is NOT a gate verdict and must never be filed as one.**
The pre-registered gate judges M1 (`gate_verdict.py`). This script asks a different
question: if the *information ceiling* were the candidate, would the criteria be
satisfiable at all?

The Oracle is fitted on true available power. No estimator that sees only observed
generation can beat it other than by noise. So if the Oracle cannot clear criterion
(b) against B1-B4, or trips the (c) no-harm clause against B2, then those criteria
are not a test M1 failed -- they are unpassable on this design, and M1's failure
carries no information about M1. That is a finding about the benchmark, not a licence
to re-cut the test: no criterion, threshold, seed or grid point is touched here.

Method: identical to `gate_verdict.py`. The same cells, the same pooling, the same
paired event-day bootstrap, the same `paired_abs_bias` / `paired_difference` from
`metrics.py` -- every helper is imported from `gate_verdict`, not reimplemented, so
the only thing that changes is which `a_hat_*` plays the candidate's part. Both
Oracle and M1 rows are computed through that one code path and tagged by `method`,
so the comparison in the write-up is exact rather than copied between two runs.

**Criterion (a) is NOT APPLICABLE and is not evaluated.** (a) compares an estimated
response curve against r*, and the cells store `r_curve_M1` and `r_curve_B3` only.
The Oracle has no response head: it is fitted on true available power and never
identifies a curtailment response. No substitute is improvised for it; the gap is
reported as a gap.
"""

from __future__ import annotations

import argparse
import csv

import numpy as np

from src.censoring import gate_verdict as gv
from src.censoring.metrics import paired_abs_bias, paired_difference

OUT_CSV = gv.RESULTS_DIR / "13_oracle_power_diagnostic.csv"

#: The candidate under test, then M1 for side-by-side context on one code path.
METHODS = ("Oracle", "M1")

NOT_A_VERDICT = ("DIAGNOSTIC ONLY -- not a gate verdict. Candidate substituted for "
                 "M1 to test whether the criterion is passable at the information "
                 "ceiling.")


def _pair_b(sub: list[dict], method: str, rival: str) -> tuple[dict, dict]:
    """The two (b) statistics for `method` against `rival`, exactly as the gate does."""
    sa, sb, days = gv.pool(sub, lambda c, r=rival, m=method: (
        gv.signed_err(c, m), gv.signed_err(c, r), c["censored"], c["berlin_date"]))
    pb = paired_abs_bias(sa, sb, np.ones(sa.shape, dtype=bool), days)
    ca, cb, cdays = gv.pool(sub, lambda c, r=rival, m=method: (
        gv.c_abs_err(c, m), gv.c_abs_err(c, r), c["censored"], c["berlin_date"]))
    pc = paired_difference(ca, cb, np.ones(ca.shape, dtype=bool), cdays)
    return pb, pc


def criterion_b_power(cells: list[dict], rows: list[dict]) -> dict:
    """(b), gamma in {0.5, 1}: |bias| and curtailed-share MAE against each of B1-B4."""
    verdicts: dict[tuple, bool] = {}
    print(f"\n{'=' * 78}\nCRITERION (b) -- POWER DIAGNOSTIC, NOT A VERDICT")
    print(f"{gv.CRITERIA['b']}\n{'=' * 78}")
    for gamma in (0.5, 1.0):
        sub = [c for c in cells if float(c["gamma"]) == gamma]
        if not sub:
            print(f"\n  gamma = {gamma}: no cells stored -- NOT EVALUATED")
            continue
        shapes = sorted({str(c["r_shape"]) for c in sub})
        print(f"\n  gamma = {gamma}  ({len(sub)} cells over shapes {shapes})")
        for method in METHODS:
            print(f"\n    candidate = {method}")
            print(f"      {'rival':<7}{'|bias| diff':>13}{'95% CI':>22}{'better':>8}"
                  f"{'c-MAE diff':>13}{'95% CI':>24}{'better':>8}")
            ok = True
            for rival in gv.GATE_RIVALS:
                pb, pc = _pair_b(sub, method, rival)
                ok = ok and pb["a_better"] and pc["a_better"]
                ci_b = f"[{pb['lo']:+.2f}, {pb['hi']:+.2f}]"
                ci_c = f"[{pc['lo']:+.5f}, {pc['hi']:+.5f}]"
                print(f"      {rival:<7}{pb['diff']:>13.2f}{ci_b:>22}"
                      f"{str(pb['a_better']):>8}{pc['diff']:>13.5f}{ci_c:>24}"
                      f"{str(pc['a_better']):>8}")
                for stat, p in (("abs_bias_mw", pb), ("curtailed_share_mae", pc)):
                    rows.append(
                        {"criterion": "b", "method": method,
                         "stratum": f"gamma={gamma}", "rival": rival,
                         "statistic": stat,
                         "paired_diff": round(p["diff"], 6),
                         "ci_lo": round(p["lo"], 6), "ci_hi": round(p["hi"], 6),
                         "significant": p["significant"],
                         "candidate_better": p["a_better"],
                         "n_qh": p["n_qh"], "n_days": p["n_days"],
                         "n_cells": len(sub),
                         "note": NOT_A_VERDICT + " Censored QHs; paired event-day "
                                 "bootstrap pooled over seeds, rates and shapes."})
            verdicts[(gamma, method)] = ok
            print(f"      -> gamma {gamma}, {method}: "
                  f"{'would PASS' if ok else 'would FAIL'} (b) "
                  f"(needs better on BOTH statistics against ALL of B1-B4)")

        # Per shape, same split the gate prints, for both candidates.
        for method in METHODS:
            for shape in gv.SHAPES:
                ss = [c for c in sub if str(c["r_shape"]) == shape]
                if not ss:
                    continue
                line = f"      {method:<7}{shape:<9}"
                for rival in gv.GATE_RIVALS:
                    pb, pc = _pair_b(ss, method, rival)
                    mark = ("both" if pb["a_better"] and pc["a_better"]
                            else "bias" if pb["a_better"]
                            else "cmae" if pc["a_better"] else "-")
                    line += f"{rival}:{mark:<6}"
                    rows.append(
                        {"criterion": "b", "method": method,
                         "stratum": f"gamma={gamma},shape={shape}", "rival": rival,
                         "statistic": "abs_bias_mw + curtailed_share_mae",
                         "paired_diff": round(pb["diff"], 6),
                         "ci_lo": round(pb["lo"], 6), "ci_hi": round(pb["hi"], 6),
                         "significant": pb["significant"],
                         "candidate_better": mark == "both",
                         "n_qh": pb["n_qh"], "n_days": pb["n_days"],
                         "n_cells": len(ss),
                         "note": NOT_A_VERDICT + f" Per-shape split; cmae diff "
                                 f"{pc['diff']:+.6f} [{pc['lo']:+.6f}, "
                                 f"{pc['hi']:+.6f}]; B0/B2/B3 are shape-invariant."})
                print(line + "   (which statistic the candidate significantly wins)")
    return verdicts


def criterion_c_power(cells: list[dict], rows: list[dict]) -> dict:
    """(c), gamma = 0: the candidate's MAE not significantly worse than B2."""
    print(f"\n{'=' * 78}\nCRITERION (c) -- POWER DIAGNOSTIC, NOT A VERDICT")
    print(f"{gv.CRITERIA['c']}\n{'=' * 78}")
    sub = [c for c in cells if float(c["gamma"]) == 0.0]
    verdicts: dict[str, bool] = {}
    for method in METHODS:
        ok = True
        print(f"\n    candidate = {method}")
        for label, maskfn in (("censored QHs", lambda c: c["censored"]),
                              ("all QHs",
                               lambda c: np.ones(c["a_true"].shape, bool))):
            a, b, days = gv.pool(sub, lambda c, m=maskfn, meth=method: (
                gv.abs_err(c, meth), gv.abs_err(c, "B2"), m(c), c["berlin_date"]))
            p = paired_difference(a, b, np.ones(a.shape, dtype=bool), days)
            worse = bool(p["diff"] > 0 and p["significant"])
            if label == "censored QHs":
                ok = not worse
            print(f"      {label}  ({len(sub)} cells)")
            print(f"        {method} MAE {a.mean():,.1f} MW   B2 MAE {b.mean():,.1f}"
                  f" MW   diff {p['diff']:+.2f}  "
                  f"95% CI [{p['lo']:+.2f}, {p['hi']:+.2f}]")
            print(f"        n={p['n_qh']:,} QH in {p['n_days']} days   "
                  f"{method} significantly WORSE: {worse}")
            rows.append(
                {"criterion": "c", "method": method,
                 "stratum": f"gamma=0 ({label})", "rival": "B2",
                 "statistic": "mae_mw",
                 "paired_diff": round(p["diff"], 6),
                 "ci_lo": round(p["lo"], 6), "ci_hi": round(p["hi"], 6),
                 "significant": p["significant"],
                 "candidate_better": p["a_better"],
                 "n_qh": p["n_qh"], "n_days": p["n_days"], "n_cells": len(sub),
                 "note": NOT_A_VERDICT + " No-harm clause: pass unless the candidate "
                         f"is significantly worse. {method} MAE "
                         f"{a.mean():.4f} MW, B2 MAE {b.mean():.4f} MW."})
        verdicts[method] = ok
        print(f"      -> (c) on the pre-registered sample (censored QHs), {method}: "
              f"{'would PASS' if ok else 'would FAIL'}")
    return verdicts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--allow-partial", action="store_true",
                    help="score whatever cells are on disk (default: require 81)")
    ap.add_argument("--merged", action="store_true",
                    help="read the merged-cohort run in "
                         "data/processed/e1_gate_artifacts_merged (default: the "
                         "unmerged data/processed/e1_gate_artifacts)")
    args = ap.parse_args()

    out_csv = OUT_CSV
    if args.merged:
        gv.ARTIFACT_DIR = gv.MERGED_ARTIFACT_DIR
        out_csv = OUT_CSV.with_name(f"{OUT_CSV.stem}_merged{OUT_CSV.suffix}")

    cells = gv.load_cells()
    print(f"{'=' * 78}")
    print("ORACLE POWER DIAGNOSTIC -- NOT A GATE VERDICT")
    print("The gate's verdict on M1 is results/13_gate_verdict*.csv and is not "
          "changed by\nanything in this file.")
    print(f"{'=' * 78}")
    print(f"scoring artifacts in {gv.ARTIFACT_DIR}")
    print(f"Scope: rates >= {gv.MIN_RATE:.0%}, seeds {gv.GATE_SEEDS}, "
          f"all three r* shapes.")
    print(f"Cells found in {gv.ARTIFACT_DIR.relative_to(gv.REPO_ROOT)}: "
          f"{len(cells)} of 81")
    if len(cells) < 81 and not args.allow_partial:
        raise SystemExit("Incomplete grid. Re-run the grid phase, or pass "
                         "--allow-partial to score a provisional subset.")
    if len(cells) < 81:
        print("  *** PROVISIONAL: not the full grid. ***")

    rows: list[dict] = []
    vb = criterion_b_power(cells, rows)
    vc = criterion_c_power(cells, rows)

    print(f"\n{'=' * 78}\nPOWER SUMMARY -- DIAGNOSTIC, NOT A VERDICT\n{'=' * 78}")
    print("  (a)  NOT APPLICABLE: cells store r_curve_M1 and r_curve_B3 only; the "
          "Oracle\n       has no response head, and no substitute is improvised.")
    for (gamma, method), ok in sorted(vb.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        print(f"  (b)  gamma {gamma:<4} {method:<7} "
              f"{'would PASS' if ok else 'would FAIL'}")
    for method, ok in vc.items():
        print(f"  (c)  gamma 0    {method:<7} "
              f"{'would PASS' if ok else 'would FAIL'}")
    oracle_b = [ok for (_, m), ok in vb.items() if m == "Oracle"]
    if oracle_b and not all(oracle_b):
        print("\n  The information ceiling does not satisfy (b) on this design. A "
              "criterion the\n  Oracle cannot meet is not evidence against M1. "
              "Reported as a limitation of the\n  benchmark; the pre-registered "
              "criteria stand unchanged.")

    gv.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {out_csv.relative_to(gv.REPO_ROOT)}  (diagnostic, not a verdict)")


if __name__ == "__main__":
    main()
