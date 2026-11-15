"""P3 synthetic study: do the bounds contain the truth, and how wide are they?

    python -m src.identification.run_p3_synthetic --arm O
    python -m src.identification.run_p3_synthetic --arm D --limit 27

Arm O sets `c_hat = c_true`, so the only error is the discretisation and the geometry;
the pre-registered >= 95% coverage target applies here. Arm D sets
`c_hat = 1 - G/A_hat` with A_hat the shared cross-fitted stage A, which is what real
data gives. `docs/P3_results.md` section 0.8.

Two generator configurations per cell, because the brief asks for cells "where cohort
responses differ along the collinear directions":

  homogeneous   every cohort shares one r* (`r_cohort_offsets=None`)
  split         the two EXACTLY COLLINEAR cohorts are pushed apart, +0.15 and -0.15,
                and no other cohort moves. Their capacity-weighted sum is unchanged
                to first order, so the aggregate the data records is nearly the same
                while the quantity P3 is asked about is completely different. That is
                the sharpest possible test of whether a bound is honest.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
from datetime import date
from pathlib import Path

import numpy as np

from src.censoring.cohorts import placeholder_cohort_set
from src.censoring.identification import duplicate_groups, exposure_rank
from src.censoring.model import cohort_runlength_hours
from src.censoring.synthetic import (
    SyntheticConfig, generate, true_response_per_cohort,
)
from src.identification import functionals as fx
from src.identification.bounds import (
    compress_rows, build_design, epsilon_from_bootstrap, identified_set, in_row_space,
    point_fit, pooled_fit,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "artifacts" / "P3"
PREREG_COMMIT = "1cd4b30"

RATES = (0.10, 0.20, 0.40)
GAMMAS = (0.0, 0.5, 1.0)
SHAPES = ("step", "logistic", "half")
SEEDS = (45, 46, 47)
HETERO = ("homogeneous", "split")
SPLIT_OFFSET = 0.15

#: `docs/P3_results.md` section 0.6: the placeholder analogues of P0's cohorts.
COLLINEAR_PAIR = ("pre2016_out_of_support", "post_feb2025_qh")
L3_COHORT = "wind2016_2020_6h"
L5_COHORT = "wind2023_feb2025_staircase"
L7_COHORT = "pre2016_out_of_support"

#: Coverage allowance for solver tolerance, declared rather than tuned. CLARABEL
#: returns a primal solution to roughly 1e-8; an interval that misses the truth by
#: less than that is a solver artefact, not a failure of the bounds. Anything larger
#: counts as a miss.
TOL_COVER = 1e-6


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:                                            # noqa: BLE001
        return "unknown"


def offsets_for(kind: str, cohort_ids) -> tuple[float, ...] | None:
    if kind == "homogeneous":
        return None
    out = []
    for cid in cohort_ids:
        if cid == COLLINEAR_PAIR[0]:
            out.append(+SPLIT_OFFSET)
        elif cid == COLLINEAR_PAIR[1]:
            out.append(-SPLIT_OFFSET)
        else:
            out.append(0.0)
    return tuple(out)


def _truths(data, design, shares, level, price, potential) -> dict[str, float]:
    """The TRUE value of each functional, from the generator's per-quarter-hour r*.

    Section 0.9: the target is the functional's true value, not its projection onto
    the depth grid, so discretisation error counts against coverage.
    """
    cfg = data.config
    ids = list(design.cohort_ids)
    r_true = np.asarray(data.r_true, dtype=float)
    s = np.asarray(data.s, dtype=float)
    w = np.asarray(shares, dtype=float)
    rows = design.rows
    c_true = np.asarray(data.c_true, dtype=float)
    p = np.asarray(price, dtype=float)
    out: dict[str, float] = {}

    for name, lo, hi in (("L1", -20.0, -5.0), ("L2", -np.inf, -50.0)):
        m = (p[rows] > lo) & (p[rows] <= hi)
        out[name] = float(c_true[rows][m].mean()) if m.any() else float("nan")

    def cohort_truth(cid: str) -> float:
        if cid not in ids:
            return float("nan")
        k = ids.index(cid)
        on = s[k, rows] > 0
        return float(r_true[k, rows][on].mean()) if on.any() else float("nan")

    out["L3"] = cohort_truth(L3_COHORT)
    out["L7"] = cohort_truth(L7_COHORT)

    idx = [ids.index(c) for c in COLLINEAR_PAIR if c in ids]
    if idx:
        any_on = np.zeros(rows.size, dtype=bool)
        for k in idx:
            any_on |= s[k, rows] > 0
        w_g = float(w[idx].sum())
        if any_on.any() and w_g > 0:
            num = sum(w[k] * r_true[k, rows] for k in idx)
            out["L4"] = float(num[any_on].mean() / w_g)
        else:
            out["L4"] = float("nan")
    else:
        out["L4"] = float("nan")
    out["L6"] = out["L3"] - out["L4"]

    # L5: r* is a known function of depth, so the counterfactual truth is exact.
    if L5_COHORT in ids:
        k = ids.index(L5_COHORT)
        neg = p[rows] < 0.0
        cf_depth = np.zeros((len(ids), rows.size))
        cf_depth[k] = np.where(neg, -p[rows], 0.0)
        r_cf = true_response_per_cohort(cf_depth, cfg)[k]
        out["L5"] = float((np.asarray(potential)[rows] * w[k] * r_cf * 0.25 / 1000.0)[neg].sum())
    else:
        out["L5"] = float("nan")
    return out


def run_cell(rate: float, gamma: float, shape: str, seed: int, hetero: str,
             arm: str) -> list[dict]:
    base = placeholder_cohort_set()
    ids = [c.cohort_id for c in base]
    cfg = SyntheticConfig(censoring_rate=rate, gamma=gamma, r_shape=shape, seed=seed,
                          r_cohort_offsets=offsets_for(hetero, ids))
    data = generate(cfg, cohorts=base)

    s = np.asarray(data.s, dtype=float)
    depth = np.asarray(data.depth, dtype=float)
    shares = np.asarray(data.cohorts.shares, dtype=float)
    runlen = cohort_runlength_hours(data)
    price = np.asarray(data.price_eur_mwh, dtype=float)
    design = build_design(s, depth, shares, runlen, cohort_ids=tuple(ids))
    level = fx.run_levels(design, runlen, s)
    rows = design.rows

    if arm == "O":
        c_hat_full = np.asarray(data.c_true, dtype=float)
        potential = np.asarray(data.a_true_mw, dtype=float)
        stage_a_note = "c_hat = c_true (Arm O)"
    else:
        from src.censoring.m2 import fit_shared_stage_a
        sa = fit_shared_stage_a(data, check=False)
        a_hat = np.maximum(np.asarray(sa.a_hat, dtype=float), 1e-9)
        c_hat_full = 1.0 - np.asarray(data.g_obs_mw, dtype=float) / a_hat
        potential = a_hat
        stage_a_note = "c_hat = 1 - G/A_hat, shared cross-fitted stage A (Arm D)"

    c_hat = c_hat_full[rows]
    comp = compress_rows(design.X, c_hat)
    pf = point_fit(design, c_hat, comp)
    if pf["r"] is None:
        return [{"arm": arm, "hetero": hetero, "rate": rate, "gamma": gamma,
                 "r_shape": shape, "seed": seed, "lam": "ALL", "defined": False,
                 "note": f"point fit failed: {pf['status']}"}]
    eps_info = epsilon_from_bootstrap(design, c_hat, np.asarray(data.berlin_date)[rows],
                                      pf["r"])
    eps = eps_info["eps"]
    pooled = pooled_fit(design, c_hat)
    rank_s = exposure_rank(s)
    dups = duplicate_groups(s, ids, shares, depth)
    exact_cap = sum(g.capacity_share for g in dups if g.is_exact)

    specs = {
        "L1": fx.band_mean(design, price, -20.0, -5.0),
        "L2": fx.band_mean(design, price, -np.inf, -50.0),
        "L3": fx.cohort_mean(design, s, depth, level, L3_COHORT),
        "L4": fx.group_mean(design, s, depth, level, shares, COLLINEAR_PAIR),
        "L5": fx.threshold_to_zero_energy(design, s, depth, level, shares, price,
                                          potential, L5_COHORT),
        "L7": fx.cohort_mean(design, s, depth, level, L7_COHORT),
    }
    specs["L6"] = fx.difference(specs["L3"], specs["L4"])
    truths = _truths(data, design, shares, level, price, potential)

    common = {
        "arm": arm, "hetero": hetero, "rate": rate, "gamma": gamma, "r_shape": shape,
        "seed": seed, "eps": eps, "rms_point": pf["rms_residual"],
        "rms_floor": comp.rms_floor, "n_rows": design.n_rows,
        "n_rows_compressed": int(comp.Xu.shape[0]), "n_cols": design.n_cols,
        "n_cohorts": len(ids), "exposure_rank": rank_s.rank,
        "exposure_rank_full": rank_s.full_rank,
        "exact_collinear_capacity": float(exact_cap),
        "censored_share": float(np.mean(np.asarray(data.c_true) > 0)),
        "mean_c_true": float(np.mean(data.c_true)),
        "n_event_days": eps_info["n_days"], "run_levels": design.n_run_levels,
        "stage_a": stage_a_note, "preregistration_commit": PREREG_COMMIT,
    }

    rows_out = []
    for name in ("L1", "L2", "L3", "L4", "L5", "L6", "L7"):
        spec = specs[name]
        truth = truths.get(name, float("nan"))
        row = {**common, "lam": name, "defined": bool(spec.get("defined")),
               "n_qh_lam": int(spec.get("n_qh", 0)), "truth": truth,
               "note": spec.get("note", "")}
        if not spec.get("defined"):
            row.update({"lo": np.nan, "hi": np.nan, "width": np.nan,
                        "covered": None, "covered_one_sided": None,
                        "in_row_space": None, "perp_fraction": np.nan,
                        "pooled_value": np.nan, "pooled_abs_err": np.nan,
                        "pooled_err_exceeds_width": None, "feasible": False,
                        "rank_X": None,
                        "l5_coverage": spec.get("coverage", np.nan),
                        "l5_energy_full_gwh": spec.get("energy_if_full_response_gwh", np.nan),
                        "status_lo": "", "status_hi": ""})
            rows_out.append(row)
            continue
        iv = identified_set(design, c_hat, spec["lam"], eps, comp)
        rs = in_row_space(design.X, spec["lam"])
        pooled_val = (float(spec["lam"] @ pooled["r_expanded"])
                      if pooled.get("r_expanded") is not None else np.nan)
        abs_err = abs(pooled_val - truth) if np.isfinite(pooled_val + truth) else np.nan
        one_sided = (name == "L5" and spec.get("coverage", 1.0) < 1.0)
        slack = TOL_COVER * max(1.0, abs(truth)) if np.isfinite(truth) else 0.0
        covered = (bool(iv["lo"] - slack <= truth <= iv["hi"] + slack)
                   if np.isfinite(truth) and iv["feasible"] else None)
        row.update({
            "lo": iv["lo"], "hi": iv["hi"], "width": iv["width"],
            "feasible": iv["feasible"],
            "covered": None if one_sided else covered,
            "covered_one_sided": (bool(truth >= iv["lo"] - slack)
                                  if np.isfinite(truth) and iv["feasible"] else None),
            "in_row_space": rs["in_row_space"], "perp_fraction": rs["perp_fraction"],
            "rank_X": rs["rank"], "pooled_value": pooled_val, "pooled_abs_err": abs_err,
            "pooled_err_exceeds_width": (bool(abs_err > iv["width"])
                                         if np.isfinite(abs_err + iv["width"]) else None),
            "l5_coverage": spec.get("coverage", np.nan),
            "l5_energy_full_gwh": spec.get("energy_if_full_response_gwh", np.nan),
            "status_lo": iv["status_lo"], "status_hi": iv["status_hi"],
        })
        rows_out.append(row)
    return rows_out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=("O", "D"), default="O")
    ap.add_argument("--limit", type=int, default=0, help="first N cells only")
    ap.add_argument("--gammas", default="", help="comma-separated subset of gammas")
    ap.add_argument("--seeds", default="", help="comma-separated subset of seeds")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    gammas = tuple(float(x) for x in args.gammas.split(",")) if args.gammas else GAMMAS
    seeds = tuple(int(x) for x in args.seeds.split(",")) if args.seeds else SEEDS
    cells = [(r, g, sh, sd, h) for h in HETERO for r in RATES for g in gammas
             for sh in SHAPES for sd in seeds]
    if args.limit:
        cells = cells[:args.limit]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else OUT_DIR / f"p3_synthetic_arm_{args.arm.lower()}.csv"
    head, today = git_head(), date.today().isoformat()
    fh = writer = None
    try:
        for i, (rate, gamma, shape, seed, hetero) in enumerate(cells, 1):
            rows = run_cell(rate, gamma, shape, seed, hetero, args.arm)
            for row in rows:
                row["git_head"], row["run_date"] = head, today
            if writer is None:
                fh = open(out_path, "w", newline="", encoding="utf-8")
                writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
                writer.writeheader()
            for row in rows:
                writer.writerow({k: row.get(k) for k in writer.fieldnames})
            fh.flush()
            w = {r["lam"]: r.get("width") for r in rows}
            print(f"[{i:3d}/{len(cells)}] {hetero:<12} r{int(rate * 100):<3} g{gamma} "
                  f"{shape:<9} s{seed}  cols={rows[0].get('n_cols')} "
                  f"rows={rows[0].get('n_rows_compressed')}/{rows[0].get('n_rows')} "
                  f"eps={rows[0].get('eps'):.5f}  "
                  + " ".join(f"{k}={v:.3f}" for k, v in w.items()
                             if isinstance(v, float) and np.isfinite(v)), flush=True)
    finally:
        if fh is not None:
            fh.close()
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
