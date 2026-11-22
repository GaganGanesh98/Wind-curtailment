"""P3 synthetic study: do the bounds contain the truth, and how wide are they?

    python -m src.method.synthetic_scoring --arm O
    python -m src.method.synthetic_scoring --arm D --limit 27
    python -m src.method.synthetic_scoring --smoke   # one cell, prints truth vs set

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

from src.method.exposure import placeholder_cohort_set
from src.method.collinearity import duplicate_groups, exposure_rank
from src.method.stage_a.latent_model import cohort_runlength_hours
from src.method.synthetic import (
    SyntheticConfig, generate, true_response_per_cohort,
)
from src.method import functionals as fx
from src.method.bounds import (
    compress_rows, build_design, epsilon_from_bootstrap, identified_set, in_row_space,
    point_fit, pooled_fit,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "artifacts" / "exp1_known_truth_validation"
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


#: Stage A depends on the price process and NOT on the response shape or the cohort
#: offsets, so one fit serves all six cells that share (rate, gamma, seed). It is
#: trained on price > 5 EUR/MWh quarter-hours, where no cohort is exposed and
#: `g_obs == a_true` whatever r* is, and it predicts from the forecast, the weather
#: proxy and the hour -- none of which the shape touches. `docs/09` Amendment 6
#: states the same property for E1 v2's stage A.
#:
#: VERIFIED, not assumed, before this cache was introduced: fitting stage A
#: independently for (step, homogeneous), (half, homogeneous) and (step, split) at
#: rate 0.10, gamma 0, seed 45 gives a BIT-IDENTICAL `a_hat` in all three, on an
#: identical safe mask of 78,075 quarter-hours. The guard below re-checks the price
#: series on every cache hit, so a cell that does not in fact share the process
#: raises instead of silently reusing the wrong array.
_STAGE_A_CACHE: dict[tuple, tuple[bytes, object]] = {}


def _price_key(price: np.ndarray) -> bytes:
    import hashlib
    return hashlib.sha256(np.ascontiguousarray(price, dtype=np.float64).tobytes()).digest()


def _shared_stage_a(data, rate: float, gamma: float, seed: int):
    """One stage A per price process, with the process checked on every reuse."""
    from src.method.stage_a.reservation_depth_model import fit_shared_stage_a

    key = (round(float(rate), 6), round(float(gamma), 6), int(seed))
    phash = _price_key(data.price_eur_mwh)
    hit = _STAGE_A_CACHE.get(key)
    if hit is not None:
        cached_hash, sa = hit
        if cached_hash != phash:
            raise AssertionError(
                f"stage-A cache key {key} was built on a different price series. The "
                "cache rests on stage A depending only on the price process; if that "
                "has stopped being true the cache is wrong and must be removed, not "
                "widened.")
        return sa, True
    sa = fit_shared_stage_a(data, check=False)
    _STAGE_A_CACHE[key] = (phash, sa)
    return sa, False


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


def prepare_cell(rate: float, gamma: float, shape: str, seed: int,
                 hetero: str) -> dict:
    """The deterministic part of a cell: generate, then build the bounds design.

    Split out of `run_cell` on 15 November 2026 for Phase Q, which needs to score the
    SAME cell under many potentials without regenerating it. Nothing here depends on
    which potential the share estimator will be handed.
    """
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
    return {"rate": rate, "gamma": gamma, "shape": shape, "seed": seed,
            "hetero": hetero, "data": data, "ids": ids, "s": s, "depth": depth,
            "shares": shares, "runlen": runlen, "price": price, "design": design,
            "level": level, "rows": rows}


def score_cell(prep: dict, c_hat_full: np.ndarray, potential: np.ndarray, *,
               arm: str, stage_a_note: str, extra: dict | None = None) -> list[dict]:
    """THE DEGRADATION HOOK. Score one prepared cell under a given share estimate.

    `c_hat_full` is the curtailed-share estimate on every quarter-hour and `potential`
    the potential it was formed from (it also builds lambda-5's energy coefficients
    and truth, exactly as in P3). Arm O passes `c_true` and `a_true`; Arm D passes
    `1 - G/A_hat` and `A_hat`; Phase Q passes `1 - G/P` and `P` for a degraded `P`.
    One scoring path for all three is the point: Phase Q hard rule 1 forbids a
    parallel path, and a dial built on a copy of the scorer would not be a dial on
    THIS scorer.

    `extra` is merged into every row last, so a caller can add its own columns and
    override `preregistration_commit`.
    """
    rate, gamma, shape, seed, hetero = (prep["rate"], prep["gamma"], prep["shape"],
                                        prep["seed"], prep["hetero"])
    data, ids, s, depth = prep["data"], prep["ids"], prep["s"], prep["depth"]
    shares, price, design = prep["shares"], prep["price"], prep["design"]
    level, rows = prep["level"], prep["rows"]

    c_hat = c_hat_full[rows]
    comp = compress_rows(design.X, c_hat)
    pf = point_fit(design, c_hat, comp)
    if pf["r"] is None:
        return [{"arm": arm, "hetero": hetero, "rate": rate, "gamma": gamma,
                 "r_shape": shape, "seed": seed, "lam": "ALL", "defined": False,
                 "note": f"point fit failed: {pf['status']}", **(extra or {})}]
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
    # The TRUE potential, never the estimate: until 16 Nov 2026 this passed `potential`, so
    # lambda-5's truth moved with the estimated potential (docs/ERRATUM_lambda5.md).
    truths = _truths(data, design, shares, level, price,
                     np.asarray(data.a_true_mw, dtype=float))

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
        **(extra or {}),
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


def run_cell(rate: float, gamma: float, shape: str, seed: int, hetero: str,
             arm: str) -> list[dict]:
    """Arm O or Arm D on one cell: `prepare_cell`, choose the share, `score_cell`."""
    prep = prepare_cell(rate, gamma, shape, seed, hetero)
    data = prep["data"]
    if arm == "O":
        c_hat_full = np.asarray(data.c_true, dtype=float)
        potential = np.asarray(data.a_true_mw, dtype=float)
        stage_a_note = "c_hat = c_true (Arm O)"
    else:
        sa, reused = _shared_stage_a(data, rate, gamma, seed)
        a_hat = np.maximum(np.asarray(sa.a_hat, dtype=float), 1e-9)
        c_hat_full = 1.0 - np.asarray(data.g_obs_mw, dtype=float) / a_hat
        potential = a_hat
        stage_a_note = ("c_hat = 1 - G/A_hat, shared cross-fitted stage A (Arm D"
                        + (", stage A reused across shape/config)" if reused else ")"))

    return score_cell(prep, c_hat_full, potential, arm=arm, stage_a_note=stage_a_note)


def smoke(out_path: Path) -> None:
    """One small synthetic cell end to end, with a known truth (`docs/P3_results.md` Arm O)."""
    rate, gamma, shape, seed, hetero = 0.20, 0.5, "logistic", 45, "homogeneous"
    rows = run_cell(rate, gamma, shape, seed, hetero, "O")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in writer.fieldnames})
    print(f"cell: {hetero}, censoring rate {rate}, gamma {gamma}, shape {shape}, seed {seed}, "
          f"Arm O (exact potential)")
    print(f"{'functional':<11}{'true value':>12}   {'identified set':<26}{'covered':>8}")
    for r in rows:
        if not r.get("defined"):
            print(f"{r['lam']:<11}{'':>12}   {'undefined':<26}")
            continue
        cov = r["covered"] if r["covered"] is not None else r["covered_one_sided"]
        iv = f"[{r['lo']:.4f}, {r['hi']:.4f}]"
        print(f"{r['lam']:<11}{r['truth']:>12.4f}   {iv:<26}{str(cov):>8}")
    scored = [r for r in rows if r.get("defined")]
    n_cov = sum(bool(r["covered"] if r["covered"] is not None else r["covered_one_sided"])
                for r in scored)
    print(f"coverage: {n_cov} of {len(scored)} defined functionals contain the truth")
    print(f"wrote {out_path}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=("O", "D"), default="O")
    ap.add_argument("--limit", type=int, default=0, help="first N cells only")
    ap.add_argument("--gammas", default="", help="comma-separated subset of gammas")
    ap.add_argument("--seeds", default="", help="comma-separated subset of seeds")
    ap.add_argument("--out", default="")
    ap.add_argument("--smoke", action="store_true",
                    help="one Arm O cell; print truth, identified set and coverage; "
                         "write to demo/output/ unless --out is given, never to artifacts/")
    args = ap.parse_args()
    if args.smoke:
        smoke(Path(args.out) if args.out else REPO_ROOT / "demo" / "output" / "p3_smoke_cell.csv")
        return

    gammas = tuple(float(x) for x in args.gammas.split(",")) if args.gammas else GAMMAS
    seeds = tuple(int(x) for x in args.seeds.split(",")) if args.seeds else SEEDS
    # Ordered so that the cells sharing a (rate, gamma, seed) price process -- and
    # therefore a stage A -- are adjacent, which is what makes the cache pay.
    cells = [(r, g, sh, sd, h) for r in RATES for g in gammas for sd in seeds
             for h in HETERO for sh in SHAPES]
    if args.limit:
        cells = cells[:args.limit]

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = Path(args.out) if args.out else (OUT_DIR / ("exact_potential_cells.csv" if args.arm == "O" else "estimated_potential_cells.csv"))
    head, today = git_head(), date.today().isoformat()
    fh = writer = None
    try:
        for i, (rate, gamma, shape, seed, hetero) in enumerate(cells, 1):
            rows = run_cell(rate, gamma, shape, seed, hetero, args.arm)
            for row in rows:
                row["git_head"], row["run_date"] = head, today
            if writer is None:
                fh = open(out_path, "w", newline="", encoding="utf-8")
                writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
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
