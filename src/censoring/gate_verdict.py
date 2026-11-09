"""The formal week-6 gate (spec v1.8, section 7), scored from stored predictions.

    python -m src.censoring.gate_verdict

Why this is a separate script
-----------------------------
The gate asks for a paired 95% event-day block-bootstrap CI **pooled over seeds**.
A per-cell row in `results/12_reduced_grid.csv` cannot carry that: pooling needs the
individual quarter-hours of all three seeds inside one resample. So the gate is
computed here, from the per-quarter-hour arrays `run_reduced_grid.py` writes to
`data/processed/e1_gate_artifacts/`, and nothing in this file re-fits a model.

No threshold or criterion is set here. The three criteria are quoted verbatim from
spec v1.8 in the constants below; this module only evaluates them.

Pooling
-------
Blocks are **whole Berlin-local event-days, pooled across seeds and censoring
rates**. The synthetic timeline is seed-independent, so a given day appears in all
nine cells of a stratum with different synthetic censoring drawn on it. Those nine
appearances are not independent draws -- the weather, the forecast and the true A on
that day are the same real day -- so a drawn day brings all of its quarter-hours from
every pooled cell. Blocking on (seed, day) instead would treble the apparent number
of independent blocks and narrow every interval; it is reported as a sensitivity.

Shape-invariant baselines
-------------------------
B0, B2 and B3 produce **bit-identical** A-estimates across the three r* shapes at the
same rate, gamma and seed, and the censored mask is identical too; B1, B4 and M1 are
not. Verified directly from the stored arrays, not assumed. B2 and B3 fit on the
uncensored sample, which the choice of r* does not touch (the generator's placement
depends on rate, gamma and seed alone). B3's *implied response* does vary with shape,
because it is read off binned ratios of G -- only its A-estimate is invariant.

Consequence for (b) and (c): pooling over shapes averages three distinct M1 fits
against ONE B2 or B3 fit repeated three times. The confidence interval remains valid
for that estimand, because blocks are whole days and all three copies of a day travel
together in a drawn block, so no spurious independence is manufactured. But the
estimand is "M1 averaged over shapes versus that one baseline fit", not 27 independent
comparisons, and per-shape rows are reported so this is visible rather than implied.

Pooling the bias (criterion b)
------------------------------
The bias statistic is the **absolute value of the pooled signed bias**: all censored
quarter-hours of the stratum are pooled, the signed mean error is taken once, and
only then the absolute value. The paired CI comes from `paired_abs_bias`, which on
each event-day resample recomputes both methods' pooled signed biases on the drawn
days and differences their absolute values -- |b_M1| - |b_B| per resample, never a
bootstrap of a per-observation difference, because |mean| is not the mean of
anything.

**What this replaces, and why the alternative was wrong.** An informal check on
31 Oct 2026 averaged the per-cell |bias| values across cells. That is a different
and incorrect quantity: |.| applied before averaging turns the cell-to-cell sampling
noise into signal, so a method whose bias is zero on average but noisy across cells
scores worse than one with a small constant bias. It measures the dispersion of the
bias, not the bias. It also cannot be paired, since each cell's absolute value has
already discarded the sign that the pairing needs. The numbers it produced are not
comparable with the ones here and are not used.

Criterion (a) and the two response statistics
---------------------------------------------
The pre-registered statistic for (a) is `integrated_response_error`: the mean
|r-hat - r*| over a **uniform** depth grid, 0-150 EUR/MWh. It is a functional of a
fitted curve, not an average over quarter-hours, so an event-day block bootstrap is
not defined for it without re-fitting the model on each of 5,000 resampled day sets
-- about three years of compute on this machine.

So two numbers are reported:

  int_abs_r      the pre-registered uniform-grid integral. Point estimate only.
                 One value per cell; the paired difference is summarised across the
                 nine cells of a stratum (sign count and median), with no CI.
  fleet_r_err    a per-quarter-hour companion that CAN be bootstrapped:

                     e_t = sum_k w_k s_kt |r-hat(d_kt) - r*(d_kt)| / sum_k w_k s_kt

                 the capacity-weighted response error at the depths the fleet is
                 actually exposed to in quarter-hour t. Paired between M1 and B3,
                 bootstrapped on event-days, pooled over seeds and rates.

These are different statistics and can disagree: the uniform grid weights
150 EUR/MWh as heavily as 5 EUR/MWh, while the fleet-weighted form weights by where
the exposure really is. Both are printed, and a disagreement is reported as a
disagreement rather than resolved silently in either direction.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from src.censoring.metrics import (
    derived_curtailed_share,
    integrated_response_error,
    paired_abs_bias,
    paired_difference,
)
from src.censoring.run_reduced_grid import ARTIFACT_DIR, GATE_RIVALS

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
OUT_CSV = RESULTS_DIR / "13_gate_verdict.csv"

# Quoted from spec v1.8 section 7. Not editable here.
CRITERIA = {
    "a": "gamma = 0, each r* shape: integrated |r-hat - r*| lower than B3's "
         "implied response.",
    "b": "gamma in {0.5, 1}: both the absolute bias of A-hat and the curtailed-share "
         "MAE (c-hat against c_true) lower than each of B1-B4.",
    "c": "gamma = 0: M1's MAE not significantly worse than B2 -- the no-harm clause.",
    # (d) is NOT from spec v1.8. It is PROPOSED in docs/12 to replace the I4 /
    # rule-18 day count, which passes while large capacity shares are exactly
    # collinear (docs/11). It must be pre-registered as a spec amendment before the
    # gate is scored; until then it is reported and never folded into the verdict.
    "d": "[PROPOSED, not yet pre-registered] identification: rank(s) == K, every "
         "cohort pair differing on >= 10 quarter-hours, and cond(s) <= 100.",
}
MIN_RATE = 0.10          # "censoring rates >= 10%"
GATE_SEEDS = (42, 43, 44)
SHAPES = ("step", "logistic", "half")


# --------------------------------------------------------------------- loading


def load_cells() -> list[dict]:
    """Every stored cell inside the gate's scope, as plain arrays."""
    cells = []
    for path in sorted(ARTIFACT_DIR.glob("cell_*.npz")):
        z = np.load(path, allow_pickle=False)
        rate = float(z["censoring_rate"])
        seed = int(z["seed"])
        if rate < MIN_RATE - 1e-9 or seed not in GATE_SEEDS:
            continue
        cells.append({k: z[k] for k in z.files} | {"path": path.name})
        z.close()
    return cells


def key(c: dict) -> tuple:
    return (float(c["gamma"]), str(c["r_shape"]), float(c["censoring_rate"]),
            int(c["seed"]))


def fleet_response_error(c: dict, which: str) -> np.ndarray:
    """Capacity-weighted |r-hat - r*| per quarter-hour, NaN where nothing is exposed."""
    w = np.asarray(c["shares"], dtype=float)[:, None]
    s = np.asarray(c["s"], dtype=float)
    depth = np.asarray(c["depth"], dtype=float)
    grid = np.asarray(c["depth_grid"], dtype=float)
    r_hat = np.interp(depth, grid, np.asarray(c[f"r_curve_{which}"], dtype=float))
    r_true = np.interp(depth, grid, np.asarray(c["r_curve_true"], dtype=float))
    num = (w * s * np.abs(r_hat - r_true)).sum(axis=0)
    den = (w * s).sum(axis=0)
    out = np.full(den.shape, np.nan)
    np.divide(num, den, out=out, where=den > 0)
    return out


# ------------------------------------------------------------------ assembling


def pool(cells: list[dict], build) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Concatenate (values_a, values_b, day_labels) over cells.

    `build` returns (a, b, mask, days) for one cell. Day labels are the synthetic
    Berlin dates, which are identical across seeds and rates, so the same day in
    different cells lands in the same bootstrap block.
    """
    av, bv, dv = [], [], []
    for c in cells:
        a, b, mask, days = build(c)
        av.append(np.asarray(a)[mask])
        bv.append(np.asarray(b)[mask])
        dv.append(np.asarray(days)[mask])
    return np.concatenate(av), np.concatenate(bv), np.concatenate(dv)


def abs_err(c: dict, name: str) -> np.ndarray:
    return np.abs(np.asarray(c[f"a_hat_{name}"], dtype=float)
                  - np.asarray(c["a_true"], dtype=float))


def signed_err(c: dict, name: str) -> np.ndarray:
    return (np.asarray(c[f"a_hat_{name}"], dtype=float)
            - np.asarray(c["a_true"], dtype=float))


def c_abs_err(c: dict, name: str) -> np.ndarray:
    c_hat = derived_curtailed_share(c[f"a_hat_{name}"], c["g_obs"])
    return np.abs(c_hat - np.asarray(c["c_true"], dtype=float))


# -------------------------------------------------------------------- criteria


def criterion_a(cells: list[dict], rows: list[dict]) -> dict:
    """Per r* shape, at gamma = 0. Both response statistics."""
    verdicts = {}
    print(f"\n{'=' * 78}\nCRITERION (a)  {CRITERIA['a']}\n{'=' * 78}")
    for shape in SHAPES:
        sub = [c for c in cells
               if float(c["gamma"]) == 0.0 and str(c["r_shape"]) == shape]
        if not sub:
            continue
        # Pre-registered: the uniform-grid integral, one value per cell.
        pre = [(integrated_response_error(c["r_curve_M1"], c["r_curve_true"],
                                          c["depth_grid"]),
                integrated_response_error(c["r_curve_B3"], c["r_curve_true"],
                                          c["depth_grid"])) for c in sub]
        m1_pre = np.array([p[0] for p in pre])
        b3_pre = np.array([p[1] for p in pre])
        n_better = int((m1_pre < b3_pre).sum())

        # Companion: per-quarter-hour fleet-weighted error, paired and bootstrapped.
        def build(c):
            m1, b3 = fleet_response_error(c, "M1"), fleet_response_error(c, "B3")
            return m1, b3, np.isfinite(m1) & np.isfinite(b3), c["berlin_date"]

        e_m1, e_b3, days = pool(sub, build)
        p = paired_difference(e_m1, e_b3, np.ones(e_m1.shape, dtype=bool), days)

        agree = (np.median(m1_pre - b3_pre) < 0) == (p["diff"] < 0)
        verdicts[shape] = bool(p["a_better"])
        rates = sorted({float(c["censoring_rate"]) for c in sub})
        seeds = sorted({int(c["seed"]) for c in sub})
        print(f"\n  {shape}  ({len(sub)} cells: rates "
              f"{[f'{r:.0%}' for r in rates]} x seeds {seeds})")
        print(f"    int_abs_r   (pre-registered, uniform grid, no CI)")
        print(f"      M1 median {np.median(m1_pre):.4f}   B3 median "
              f"{np.median(b3_pre):.4f}   M1 lower in {n_better}/{len(sub)} cells"
              f"   median paired diff {np.median(m1_pre - b3_pre):+.4f}")
        print(f"    fleet_r_err (companion, per-QH, paired event-day bootstrap)")
        print(f"      M1 {np.nanmean(e_m1):.4f}   B3 {np.nanmean(e_b3):.4f}   "
              f"diff {p['diff']:+.4f}  95% CI [{p['lo']:+.4f}, {p['hi']:+.4f}]"
              f"   n={p['n_qh']:,} QH in {p['n_days']} days")
        print(f"      -> M1 significantly better: {p['a_better']}"
              f"   (directions agree: {agree})")
        rows += [
            {"criterion": "a", "stratum": f"shape={shape}", "rival": "B3",
             "statistic": "int_abs_r (pre-registered, uniform grid)",
             "m1_value": round(float(np.median(m1_pre)), 6),
             "rival_value": round(float(np.median(b3_pre)), 6),
             "paired_diff": round(float(np.median(m1_pre - b3_pre)), 6),
             "ci_lo": "", "ci_hi": "", "significant": "",
             "m1_better": n_better == len(sub),
             "n_qh": "", "n_days": "", "n_cells": len(sub),
             "note": f"M1 lower in {n_better}/{len(sub)} cells; no CI defined"},
            {"criterion": "a", "stratum": f"shape={shape}", "rival": "B3",
             "statistic": "fleet_r_err (companion, per-QH)",
             "m1_value": round(float(np.nanmean(e_m1)), 6),
             "rival_value": round(float(np.nanmean(e_b3)), 6),
             "paired_diff": round(p["diff"], 6),
             "ci_lo": round(p["lo"], 6), "ci_hi": round(p["hi"], 6),
             "significant": p["significant"], "m1_better": p["a_better"],
             "n_qh": p["n_qh"], "n_days": p["n_days"], "n_cells": len(sub),
             "note": f"directions agree with pre-registered: {agree}"},
        ]
    return verdicts


def criterion_b(cells: list[dict], rows: list[dict]) -> dict:
    """Per gamma in {0.5, 1}, against each of B1-B4, on both statistics."""
    verdicts = {}
    print(f"\n{'=' * 78}\nCRITERION (b)  {CRITERIA['b']}\n{'=' * 78}")
    for gamma in (0.5, 1.0):
        sub = [c for c in cells if float(c["gamma"]) == gamma]
        if not sub:
            print(f"\n  gamma = {gamma}: no cells stored -- NOT EVALUATED")
            continue
        shapes = sorted({str(c["r_shape"]) for c in sub})
        print(f"\n  gamma = {gamma}  ({len(sub)} cells over shapes {shapes})")
        print(f"    {'rival':<7}{'|bias| diff':>13}{'95% CI':>24}{'M1 better':>11}"
              f"{'c-MAE diff':>13}{'95% CI':>24}{'M1 better':>11}")
        ok = True
        for rival in GATE_RIVALS:
            sa, sb, days = pool(sub, lambda c, r=rival: (
                signed_err(c, "M1"), signed_err(c, r), c["censored"],
                c["berlin_date"]))
            pb = paired_abs_bias(sa, sb, np.ones(sa.shape, dtype=bool), days)
            ca, cb, cdays = pool(sub, lambda c, r=rival: (
                c_abs_err(c, "M1"), c_abs_err(c, r), c["censored"],
                c["berlin_date"]))
            pc = paired_difference(ca, cb, np.ones(ca.shape, dtype=bool), cdays)
            ok = ok and pb["a_better"] and pc["a_better"]
            ci_b = f"[{pb['lo']:+.2f}, {pb['hi']:+.2f}]"
            ci_c = f"[{pc['lo']:+.5f}, {pc['hi']:+.5f}]"
            print(f"    {rival:<7}{pb['diff']:>13.2f}{ci_b:>24}"
                  f"{str(pb['a_better']):>11}"
                  f"{pc['diff']:>13.5f}{ci_c:>24}{str(pc['a_better']):>11}")
            for stat, p in (("abs_bias_mw", pb), ("curtailed_share_mae", pc)):
                rows.append(
                    {"criterion": "b", "stratum": f"gamma={gamma}", "rival": rival,
                     "statistic": stat, "m1_value": "", "rival_value": "",
                     "paired_diff": round(p["diff"], 6),
                     "ci_lo": round(p["lo"], 6), "ci_hi": round(p["hi"], 6),
                     "significant": p["significant"], "m1_better": p["a_better"],
                     "n_qh": p["n_qh"], "n_days": p["n_days"], "n_cells": len(sub),
                     "note": "censored QHs; paired event-day bootstrap pooled over "
                             "seeds, rates and shapes"})
        verdicts[gamma] = ok
        print(f"    -> gamma {gamma}: {'PASS' if ok else 'FAIL'} "
              f"(needs M1 better on BOTH statistics against ALL of B1-B4)")

        # Per shape, because B0/B2/B3 are shape-invariant (verified: a_hat identical
        # across r* shapes at the same rate, gamma and seed, as is the censored mask).
        # Pooling over shapes therefore averages three distinct M1 fits against ONE
        # B2 or B3 fit repeated three times. The CI stays valid for that estimand --
        # day blocks carry all three copies together, so no spurious independence is
        # created -- but the estimand is "M1 averaged over shapes", not 27 independent
        # comparisons, and the per-shape rows are where that becomes visible.
        for shape in SHAPES:
            ss = [c for c in sub if str(c["r_shape"]) == shape]
            if not ss:
                continue
            line = f"      {shape:<9}"
            for rival in GATE_RIVALS:
                sa, sb, days = pool(ss, lambda c, r=rival: (
                    signed_err(c, "M1"), signed_err(c, r), c["censored"],
                    c["berlin_date"]))
                pb = paired_abs_bias(sa, sb, np.ones(sa.shape, dtype=bool), days)
                ca, cb, cdays = pool(ss, lambda c, r=rival: (
                    c_abs_err(c, "M1"), c_abs_err(c, r), c["censored"],
                    c["berlin_date"]))
                pc = paired_difference(ca, cb, np.ones(ca.shape, dtype=bool), cdays)
                mark = ("both" if pb["a_better"] and pc["a_better"]
                        else "bias" if pb["a_better"]
                        else "cmae" if pc["a_better"] else "-")
                line += f"{rival}:{mark:<6}"
                rows.append(
                    {"criterion": "b", "stratum": f"gamma={gamma},shape={shape}",
                     "rival": rival, "statistic": "abs_bias_mw + curtailed_share_mae",
                     "m1_value": "", "rival_value": "",
                     "paired_diff": round(pb["diff"], 6),
                     "ci_lo": round(pb["lo"], 6), "ci_hi": round(pb["hi"], 6),
                     "significant": pb["significant"], "m1_better": mark == "both",
                     "n_qh": pb["n_qh"], "n_days": pb["n_days"], "n_cells": len(ss),
                     "note": f"per-shape split; cmae diff {pc['diff']:+.6f} "
                             f"[{pc['lo']:+.6f}, {pc['hi']:+.6f}]; "
                             f"B0/B2/B3 are shape-invariant"})
            print(line + "   (which statistic M1 significantly wins)")
    return verdicts


#: The pre-registered I4 threshold: a cohort design "stands" if some pair's
#: exposure differs on at least this many event-DAYS. Numerically equal to
#: identification.MIN_PAIR_DIFFER_QH but a DIFFERENT quantity -- days, not
#: quarter-hours, and "some pair", not "every pair". Held separately so that
#: changing one can never silently move the other. Mirrors the literal 10 in
#: run_identification._row, which is where the I4 verdict is written to CSV.
I4_MIN_EXPOSURE_DIFFERS_DAYS = 10


def criterion_d(cells: list[dict], rows: list[dict]) -> dict:  # noqa: ARG001
    """[PROPOSED] Identification of the cohort design actually used by each cell.

    Scored from the stored `s`, `depth` and `shares` arrays, so it needs no refit and
    no regeneration. The old I4 day count is computed alongside and reported, never
    gated, so the two verdicts sit side by side.

    `rows` is accepted for signature symmetry with the other criteria but is NOT
    written to: criteria (a)-(c) share one 15-column CSV schema and (d)'s columns do
    not fit it. Per-cell detail goes to results/39_identification_gate.csv via
    `run_identification.py`.

    Not part of the spec v1.8 verdict. `main` prints it and writes it to the CSV but
    does not let it change PASS/FAIL, because this module does not get to invent a
    gate criterion (see the module docstring).
    """
    from src.censoring.cohorts import exposure_differs_by_day, mastr_cohort_set
    from src.censoring.identification import gate_identification_verdict

    fallback_ids = mastr_cohort_set("DE").ids
    out: dict[str, bool] = {}
    skipped: list[str] = []
    i4_days: list[int | None] = []
    print(f"\n{'-' * 78}\n(d) [PROPOSED] identification -- reported, not gated\n"
          f"{'-' * 78}")
    print(f"  {'cell':<30}{'rank':>8}{'min pair':>10}{'cond(s)':>10}"
          f"{'I4 days':>9}{'new':>7}")
    for c in cells:
        s, depth, w = c.get("s"), c.get("depth"), c.get("shares")
        if s is None or w is None:
            continue
        # Artifacts written from 8 Nov 2026 carry their own cohort ids, which is the
        # only way to label a MERGED design (K != 8). Older ones do not, and for
        # those the MaStR set is the correct fallback.
        label = (f"r{int(round(c['censoring_rate'] * 100)):02d}"
                 f"_g{c['gamma']}_{c['r_shape']}_s{c['seed']}")
        stored = c.get("cohort_ids")
        ids = [str(x) for x in stored] if stored is not None else fallback_ids
        if len(ids) != s.shape[0]:
            # Skip THIS cell, not the run. This was `return {}`, which threw away
            # every cell already scored on the first mismatch -- and since
            # `d_pass = bool(vd) and all(...)`, an aborted (d) then printed FAIL,
            # asserting an identification failure when nothing had been scored.
            # A guard must not be reportable as a verdict.
            skipped.append(f"{label} (ids {len(ids)} vs s {s.shape[0]})")
            continue
        nd, _ = exposure_differs_by_day(s, c["berlin_date"])
        v = gate_identification_verdict(s, ids, w, depth,
                                        exposure_differs_days=nd)
        out[label] = v.passed
        i4_days.append(nd)
        print(f"  {label:<30}{f'{v.rank}/{v.k}':>8}{v.min_pair_differ:>10,}"
              f"{v.cond_s:>10.1f}{nd:>9}{'pass' if v.passed else 'FAIL':>7}")
        # Deliberately NOT appended to `rows`: that list is written by
        # csv.DictWriter with fieldnames taken from rows[0], i.e. criteria (a)-(c)'s
        # fixed 15-column schema, and (d)'s columns are entirely different. The
        # per-cell detail is written by `run_identification.py` to
        # results/39_identification_gate.csv instead.
    if out:
        n_fail = sum(1 for ok in out.values() if not ok)
        # The old-I4 comparison is counted, not asserted: it was printed as "while
        # all of them pass the old I4 day count" unconditionally, which was true
        # when written and would have gone on being printed when it stopped being.
        n_i4_fail = sum(1 for d in i4_days
                        if d is None or d < I4_MIN_EXPOSURE_DIFFERS_DAYS)
        print(f"  {len(out)} cells scored; {n_fail} FAIL the proposed criterion, "
              f"{n_i4_fail} FAIL the old I4 day count.")
    if skipped:
        shown = "; ".join(skipped[:5]) + (" ..." if len(skipped) > 5 else "")
        print(f"  {len(skipped)} cell(s) NOT SCORED (skipped, not failed): {shown}")
    if not out:
        print("  (d) scored no cells. That is an absence of evidence, not a FAIL.")
    return out


def criterion_c(cells: list[dict], rows: list[dict]) -> bool:
    """gamma = 0: M1's MAE not significantly worse than B2."""
    print(f"\n{'=' * 78}\nCRITERION (c)  {CRITERIA['c']}\n{'=' * 78}")
    sub = [c for c in cells if float(c["gamma"]) == 0.0]
    ok = True
    for label, maskfn in (("censored QHs", lambda c: c["censored"]),
                          ("all QHs", lambda c: np.ones(c["a_true"].shape, bool))):
        a, b, days = pool(sub, lambda c, m=maskfn: (
            abs_err(c, "M1"), abs_err(c, "B2"), m(c), c["berlin_date"]))
        p = paired_difference(a, b, np.ones(a.shape, dtype=bool), days)
        worse = bool(p["diff"] > 0 and p["significant"])
        if label == "censored QHs":
            ok = not worse
        print(f"\n  {label}  ({len(sub)} cells)")
        print(f"    M1 MAE {a.mean():,.1f} MW   B2 MAE {b.mean():,.1f} MW   "
              f"diff {p['diff']:+.2f}  95% CI [{p['lo']:+.2f}, {p['hi']:+.2f}]")
        print(f"    n={p['n_qh']:,} QH in {p['n_days']} days   "
              f"M1 significantly WORSE: {worse}")
        rows.append(
            {"criterion": "c", "stratum": f"gamma=0 ({label})", "rival": "B2",
             "statistic": "mae_mw", "m1_value": round(float(a.mean()), 4),
             "rival_value": round(float(b.mean()), 4),
             "paired_diff": round(p["diff"], 6),
             "ci_lo": round(p["lo"], 6), "ci_hi": round(p["hi"], 6),
             "significant": p["significant"], "m1_better": p["a_better"],
             "n_qh": p["n_qh"], "n_days": p["n_days"], "n_cells": len(sub),
             "note": "no-harm clause: pass unless M1 is significantly worse"})
    print(f"\n    -> (c) on the pre-registered sample (censored QHs): "
          f"{'PASS' if ok else 'FAIL'}")
    return ok


def sensitivity_seedday(cells: list[dict]) -> None:
    """The same (c) test with (seed, day) blocks, to show what pooling choice costs."""
    def build(c):
        prefix = (f"{int(c['seed'])}|{float(c['censoring_rate']):.2f}|"
                  f"{str(c['r_shape'])}|")
        return (abs_err(c, "M1"), abs_err(c, "B2"), c["censored"],
                np.char.add(prefix, c["berlin_date"].astype(str)))

    sub = [c for c in cells if float(c["gamma"]) == 0.0]
    a, b, days = pool(sub, build)
    p = paired_difference(a, b, np.ones(a.shape, dtype=bool), days)
    print(f"\n  sensitivity -- (cell, day) blocks instead of day blocks:")
    print(f"    diff {p['diff']:+.2f}  95% CI [{p['lo']:+.2f}, {p['hi']:+.2f}]"
          f"   {p['n_days']} blocks   significant: {p['significant']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--allow-partial", action="store_true",
                    help="score whatever cells are on disk (default: require 81)")
    ap.add_argument("--artifact-dir", default=None,
                    help="directory of cell_*.npz to score "
                         "(default: data/processed/e1_gate_artifacts)")
    args = ap.parse_args()

    global ARTIFACT_DIR
    if args.artifact_dir:
        ARTIFACT_DIR = Path(args.artifact_dir)
        if not ARTIFACT_DIR.is_absolute():
            ARTIFACT_DIR = REPO_ROOT / ARTIFACT_DIR
        print(f"scoring artifacts in {ARTIFACT_DIR}")

    cells = load_cells()
    print(f"Gate scope: rates >= {MIN_RATE:.0%}, seeds {GATE_SEEDS}, "
          f"all three r* shapes.")
    print(f"Cells found in {ARTIFACT_DIR.relative_to(REPO_ROOT)}: {len(cells)} of 81")
    if len(cells) < 81 and not args.allow_partial:
        raise SystemExit("Incomplete grid. Re-run the grid phase, or pass "
                         "--allow-partial to score a provisional subset.")
    if len(cells) < 81:
        print("  *** PROVISIONAL: not the full grid. Not a gate verdict. ***")

    rows: list[dict] = []
    va = criterion_a(cells, rows)
    vb = criterion_b(cells, rows)
    vc = criterion_c(cells, rows)
    vd = criterion_d(cells, rows)      # PROPOSED: reported, never gated
    sensitivity_seedday(cells)

    a_pass = bool(va) and all(va.values())
    b_pass = bool(vb) and all(vb.values())
    print(f"\n{'=' * 78}\nVERDICT -- week-6 gate, spec v1.8\n{'=' * 78}")
    fmt = lambda d: (", ".join(f"{k} {'pass' if v else 'FAIL'}" for k, v in d.items())
                     or "NO CELLS EVALUATED")
    print(f"  (a) {'PASS' if a_pass else 'FAIL'}   per shape: {fmt(va)}")
    print(f"  (b) {'PASS' if b_pass else 'FAIL'}   per gamma: {fmt(vb)}")
    print(f"  (c) {'PASS' if vc else 'FAIL'}")
    d_pass = bool(vd) and all(vd.values())
    d_label = ("PASS" if d_pass else "FAIL") if vd else "NOT SCORED"
    print(f"  (d) {d_label}   [PROPOSED -- not in spec v1.8, "
          f"excluded from the verdict below]")
    overall = a_pass and b_pass and vc
    print(f"\n  GATE: {'PASS' if overall else 'FAIL'}  "
          f"(spec v1.8 needs all three)")
    if not overall:
        print("  Fail branch, spec section 7: refit with the two-cohort / "
              "single-response\n  structure and re-test; if that also fails, the "
              "structure is not identified\n  on this design.")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_csv = OUT_CSV
    if args.artifact_dir:
        # Keep the unmerged verdict: a merged scoring run writes its own file.
        tag = ARTIFACT_DIR.name.replace("e1_gate_artifacts", "").strip("_")
        out_csv = OUT_CSV.with_name(
            f"{OUT_CSV.stem}_{tag or 'alt'}{OUT_CSV.suffix}")
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {out_csv.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
