"""Redispatch sensitivity of Experiment 3 (docs/11 pre-registration, docs/11b results).

    python -m src.experiments.exp3_redispatch_sensitivity             # summary from the cells
    python -m src.experiments.exp3_redispatch_sensitivity --diagnose  # λ₂ constraint check (needs data)

The summary reads `redispatch_sensitivity_cells.csv` (arms M0, M1) and the headline V2 cells,
forms each arm's bias-robust union per B from the unrounded lo and hi, and applies the
pre-registered decision rule. The diagnosis re-solves λ₂'s minimum at b = 0 with the same
programme as `bounds._solve` (box, depth and run monotonicity, data fit), written out here with
named constraints so their duals can be read; bounds.py is not changed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
E3 = REPO_ROOT / "artifacts" / "exp3_german_application"
CELLS = E3 / "redispatch_sensitivity_cells.csv"
V2 = E3 / "bias_robust_full_window_cells.csv"
SUMMARY = E3 / "redispatch_sensitivity_summary.csv"
DIAG = E3 / "redispatch_sensitivity_l2_diagnosis.csv"
ARMS = ("headline", "M0", "M1")
READINGS = {"L1": ("λ₁ informative (width < 0.25)", lambda lo, hi: hi - lo < 0.25),
            "L2": ("λ₂ ≥ 0.50", lambda lo, hi: lo >= 0.5),
            "L3": ("λ₃ ≤ 0.75", lambda lo, hi: hi <= 0.75),
            "L6": ("λ₆ ≤ 0.50", lambda lo, hi: hi <= 0.5)}
BUDGETS = [round(i * 0.01, 2) for i in range(16)]
MOVE = 0.01                       # pre-registered: a breakdown move of 0.01 or more


def cells(arm: str) -> pl.DataFrame:
    c = pl.read_csv(V2 if arm == "headline" else CELLS, infer_schema_length=0)
    if arm != "headline":
        c = c.filter(pl.col("mask") == arm)
    return (c.with_columns(*(pl.col(x).cast(pl.Float64) for x in ("b", "lo", "hi")),
                           (pl.col("feasible") == "True").alias("feasible"))
             .with_columns(pl.col("b").round(2)))


def hull(c: pl.DataFrame, lam: str, B: float) -> tuple[float, float]:
    q = c.filter((pl.col("lam") == lam) & (pl.col("b").abs() <= B + 1e-9) & pl.col("feasible"))
    return float(q["lo"].min()), float(q["hi"].max())


def sample(arm: str) -> dict:
    r = cells(arm).row(0, named=True)
    return {"n_qh": int(r["n_qh_period"]), "n_neg_qh": int(r["n_neg_qh"]),
            "n_event_days": int(r["n_event_days"])}


def summarise() -> pl.DataFrame:
    rows = []
    base = {}
    for arm in ARMS:
        c = cells(arm)
        for lam, (reading, holds) in READINGS.items():
            lo0, hi0 = hull(c, lam, 0.0)
            brk = next((B for B in BUDGETS if not holds(*hull(c, lam, B))), None)
            row = {"arm": arm, "lam": lam, "reading": reading, "lo_B0": lo0, "hi_B0": hi0,
                   "holds_B0": bool(holds(lo0, hi0)),
                   "breakdown_B": "> 0.15" if brk is None else f"{brk:.2f}", **sample(arm)}
            if arm == "headline":
                base[lam] = row
                row.update({"verdict_change": None, "breakdown_move": None, "sensitive": None})
            else:
                h = base[lam]
                b_this = 0.16 if brk is None else brk
                b_head = 0.16 if h["breakdown_B"].startswith(">") else float(h["breakdown_B"])
                change = row["holds_B0"] != h["holds_B0"]
                move = round(b_this - b_head, 2)
                row.update({"verdict_change": change, "breakdown_move": move,
                            "sensitive": bool(change or abs(move) >= MOVE - 1e-9)})
            rows.append(row)
    return pl.DataFrame(rows, infer_schema_length=None)


def l1_widths() -> list[dict]:
    out = []
    for arm, Bs in (("M0", (0.01, 0.02)), ("M1", (0.04, 0.05))):
        c = cells(arm)
        for B in Bs:
            lo, hi = hull(c, "L1", B)
            out.append({"arm": arm, "B": B, "lo": lo, "hi": hi, "width": hi - lo})
    return out


def l2_l1_gap() -> list[dict]:
    """max and min over b of |λ₂ lower - λ₁ upper|, per arm."""
    out = []
    for arm in ARMS:
        c = cells(arm)
        j = (c.filter(pl.col("lam") == "L1").select("b", pl.col("hi").alias("l1_hi"))
              .join(c.filter(pl.col("lam") == "L2").select("b", pl.col("lo").alias("l2_lo")), on="b"))
        d = (j["l2_lo"] - j["l1_hi"]).abs()
        out.append({"arm": arm, "max_abs_gap": float(d.max()), "min_abs_gap": float(d.min()),
                    "n_b": j.height})
    return out


# ------------------------------------------------------------------- the λ₂ diagnosis

def _arm_problem(arm: str):
    """Everything run_arm builds for (arm, b = 0, setting main, full window), without solving."""
    from src.method import functionals as fx
    from src.method.bias_robust import redispatch_keep
    from src.method.bounds import build_design, compress_rows, epsilon_from_bootstrap, point_fit
    from src.method.real_panel import THREE_AREA, load_panel
    p = load_panel(THREE_AREA, "H")
    sel = p["keep"] if arm == "headline" else p["keep"] & redispatch_keep(p, arm)
    price, f, g, bdate = p["price"][sel], p["f"][sel], p["g"][sel], p["bdate"][sel]
    theta = p["theta_for"]("main")[:, sel]
    s = (price[None, :] < theta).astype(float)
    depth = np.maximum(0.0, theta - price[None, :]) * s
    design = build_design(s, depth, p["shares"], p["runlen"][:, sel], cohort_ids=p["ids"])
    c_hat = (1.0 - g / np.maximum(f, 1e-9))[design.rows]
    comp = compress_rows(design.X, c_hat)
    pf = point_fit(design, c_hat, comp)
    eps = epsilon_from_bootstrap(design, c_hat, bdate[design.rows], pf["r"])["eps"]
    lam2 = fx.band_mean(design, price, -np.inf, -50.0)["lam"]
    lam1 = fx.band_mean(design, price, -20.0, -5.0)["lam"]
    deep_rows = price[design.rows] <= -50.0
    return design, c_hat, comp, eps, lam2, deep_rows, lam1, bdate[design.rows]


def _min_l2(design, comp, eps, lam, depth_mono=True, run_mono=True, sense="min"):
    import cvxpy as cp
    n = design.n_cols
    r = cp.Variable(n)
    box = [r >= 0.0, r <= 1.0]
    cd = [design.A_depth @ r >= 0.0] if depth_mono and design.A_depth.shape[0] else []
    cr = [design.A_run @ r >= 0.0] if run_mono and design.A_run.shape[0] else []
    resid = cp.multiply(np.sqrt(comp.n), comp.Xu @ r - comp.cbar)
    budget = comp.n_rows_original * eps ** 2 - comp.ss_within
    fit = [cp.norm(resid, 2) <= float(np.sqrt(budget))]
    obj = cp.Minimize(lam @ r) if sense == "min" else cp.Maximize(lam @ r)
    prob = cp.Problem(obj, box + cd + cr + fit)
    prob.solve(solver=cp.CLARABEL)
    return prob, r, cd, fit, float(np.sqrt(budget)), resid


def diagnose(tol: float = 1e-6) -> pl.DataFrame:
    from src.method.bounds import compress_rows
    rows = []
    for arm in ARMS:
        design, c_hat, comp, eps, lam, deep, lam1, days = _arm_problem(arm)
        prob, r, cd, fit, rhs, resid = _min_l2(design, comp, eps, lam)
        q1, r1 = _min_l2(design, comp, eps, lam1, sense="max")[:2]
        stored = float(cells(arm).filter((pl.col("lam") == "L2") & (pl.col("b") == 0.0))["lo"][0])
        lam_cols = np.flatnonzero(lam > 0)
        tight_d = np.zeros(0, dtype=int)
        n_tight_touching = 0
        if cd:
            dual = np.asarray(cd[0].dual_value, dtype=float)
            tight_d = np.flatnonzero(dual > tol)
            touch = (np.abs(design.A_depth[tight_d][:, lam_cols]) > 0).any(axis=1)
            n_tight_touching = int(touch.sum())
        no_depth = _min_l2(design, comp, eps, lam, depth_mono=False)[0].value
        no_mono = _min_l2(design, comp, eps, lam, depth_mono=False, run_mono=False)[0].value
        # drop the deep-price rows (price <= -50) from the data fit, same per-row ε
        keep = ~deep
        comp_nd = compress_rows(design.X[keep], c_hat[keep])
        no_deep = _min_l2(design, comp_nd, eps, lam)[0].value
        rows.append({
            "arm": arm, "eps": eps, "l2_lo_resolved": float(prob.value), "l2_lo_stored": stored,
            "fit_norm": float(resid.value is not None and np.linalg.norm(resid.value)),
            "fit_rhs": rhs, "fit_dual": float(fit[0].dual_value),
            "fit_active": bool(abs(np.linalg.norm(resid.value) - rhs) < 1e-4 * max(1.0, rhs)),
            "n_depth_constraints": int(design.A_depth.shape[0]),
            "n_depth_tight": int(tight_d.size), "n_depth_tight_on_l2_columns": n_tight_touching,
            "l2_lo_without_depth_monotonicity": float(no_depth),
            "l2_lo_without_any_monotonicity": float(no_mono),
            "l2_lo_without_deep_price_rows_in_fit": float(no_deep),
            "n_deep_rows": int(deep.sum()),
            "n_deep_event_days": int(np.unique(days[deep]).size),
            "l1_hi_resolved": float(q1.value),
            "l1_at_l2_minimiser": float(lam1 @ r.value),
            "l2_at_l1_maximiser": float(lam @ r1.value),
            "n_columns_in_both_bands": int(((lam > 0) & (lam1 > 0)).sum()),
            "n_l2_columns": int((lam > 0).sum()),
        })
    return pl.DataFrame(rows)


# ------------------------------------------------------------- docs/11b generated blocks

SYM = {"L1": "λ₁", "L2": "λ₂", "L3": "λ₃", "L6": "λ₆"}


def _diag() -> dict:
    return {r["arm"]: r for r in pl.read_csv(DIAG).iter_rows(named=True)}


def removed_share(arm: str) -> float:
    return 1.0 - sample(arm)["n_neg_qh"] / sample("headline")["n_neg_qh"]


def table_samples() -> str:
    dg = _diag()
    out = ["| arm | quarter-hours | negative-price quarter-hours | share of negative-price quarter-hours removed | event days | λ₂ band: quarter-hours / event days |",
           "|---|---|---|---|---|---|"]
    for arm in ARMS:
        s = sample(arm)
        rm = "—" if arm == "headline" else f"{removed_share(arm):.0%}"
        out.append(f"| {arm} | {s['n_qh']:,} | {s['n_neg_qh']:,} | {rm} | {s['n_event_days']} "
                   f"| {dg[arm]['n_deep_rows']} / {dg[arm]['n_deep_event_days']} |")
    return "\n".join(out)


def table_rule() -> str:
    s = pl.read_csv(SUMMARY, infer_schema_length=None)
    dg = _diag()
    out = ["| reading | arm | interval at B = 0 | holds at B = 0 | breakdown B | change against headline | sensitive |",
           "|---|---|---|---|---|---|---|"]
    for r in s.iter_rows(named=True):
        lam = r["lam"]
        days = f" ({dg[r['arm']]['n_deep_event_days']} event days)" if lam == "L2" else ""
        if r["arm"] == "headline":
            change, sens = "—", "—"
        else:
            parts = []
            if r["verdict_change"]:
                parts.append("verdict at B = 0 changes")
            parts.append(f"breakdown {r['breakdown_move']:+.2f}")
            change, sens = "; ".join(parts), ("yes" if r["sensitive"] else "no")
        out.append(f"| {r['reading']} | {r['arm']} | [{r['lo_B0']:.4f}, {r['hi_B0']:.4f}]{days} "
                   f"| {'yes' if r['holds_B0'] else 'no'} | {r['breakdown_B']} | {change} | {sens} |")
    return "\n".join(out)


def table_l1_widths() -> str:
    out = ["| arm | B | λ₁ lower | λ₁ upper | width | width < 0.25 |", "|---|---|---|---|---|---|"]
    for r in l1_widths():
        out.append(f"| {r['arm']} | {r['B']:.2f} | {r['lo']:.7f} | {r['hi']:.7f} | {r['width']:.7f} "
                   f"| {'yes' if r['width'] < 0.25 else 'no'} |")
    return "\n".join(out)


def table_l2_diagnosis() -> str:
    dg = _diag()
    gap = {r["arm"]: r for r in l2_l1_gap()}
    out = ["| arm | λ₂ lower, B = 0 (event days) | without depth monotonicity | without any monotonicity | without the price ≤ −50 rows in the fit | data fit active | λ₁ upper | λ₁ at λ₂'s minimiser | max over b of the λ₂ lower to λ₁ upper gap | columns shared by the two bands |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for arm in ARMS:
        d = dg[arm]
        out.append(f"| {arm} | {d['l2_lo_resolved']:.4f} ({d['n_deep_event_days']}) "
                   f"| {d['l2_lo_without_depth_monotonicity']:.4f} | {d['l2_lo_without_any_monotonicity']:.4f} "
                   f"| {d['l2_lo_without_deep_price_rows_in_fit']:.4f} | {'yes' if d['fit_active'] else 'no'} "
                   f"| {d['l1_hi_resolved']:.4f} | {d['l1_at_l2_minimiser']:.4f} | {gap[arm]['max_abs_gap']:.5f} "
                   f"| {d['n_columns_in_both_bands']} of {d['n_l2_columns']} |")
    return "\n".join(out)


def note() -> str:
    dg = _diag()
    m1 = dg["M1"]
    d_mono = m1["l2_lo_resolved"] - m1["l2_lo_without_depth_monotonicity"]
    d_data = m1["l2_lo_resolved"] - m1["l2_lo_without_deep_price_rows_in_fit"]
    gap = {r["arm"]: r for r in l2_l1_gap()}
    s = pl.read_csv(SUMMARY, infer_schema_length=None).filter(pl.col("arm") != "headline")
    sens = sorted({SYM[r["lam"]] for r in s.iter_rows(named=True) if r["sensitive"]})
    calm = sorted({SYM[r["lam"]] for r in s.iter_rows(named=True)} - set(sens))
    return "\n".join([
        f"- **Verdict under the pre-registered rule.** Sensitive to redispatch: {', '.join(sens)}. "
        f"Not sensitive: {', '.join(calm)}. This is a sensitivity result, not a correction; the "
        f"headline verdicts stay as they are.",
        f"- **The masks remove most of the evidence.** M0 removes {removed_share('M0'):.0%} and M1 "
        f"{removed_share('M1'):.0%} of the negative-price quarter-hours, and what is left is a "
        f"selected subset (windy, congested days go first). A change under masking therefore "
        f"cannot be attributed to grid-curtailment contamination alone.",
        f"- **λ₂ rests on very few days.** Its band keeps {dg['M0']['n_deep_event_days']} event days "
        f"under M0 and {dg['M1']['n_deep_event_days']} under M1, against "
        f"{dg['headline']['n_deep_event_days']} in the headline.",
        f"- **What sets λ₂'s lower bound.** At its minimum the data fit is active in every arm, and "
        f"so are many depth-monotonicity constraints. Removing depth monotonicity lowers M1's bound by "
        f"{d_mono:.4f}; removing the price ≤ −50 rows from the fit lowers it by {d_data:.4f}. "
        f"So under M1 the bound is set by the deep-price data and monotonicity together, with the "
        f"deep-price data the larger part, not by monotonicity alone. "
        + ("The same holds in M0 and the headline." if all(
            dg[a]["l2_lo_resolved"] - dg[a]["l2_lo_without_deep_price_rows_in_fit"]
            > dg[a]["l2_lo_resolved"] - dg[a]["l2_lo_without_depth_monotonicity"]
            for a in ("M0", "headline")) else "This is not so in every other arm; see the table."),
        f"- **The M1 coincidence.** Under M1 λ₂'s lower bound equals λ₁'s upper bound to within "
        f"{gap['M1']['max_abs_gap']:.5f} at every b. No structural link was found: the two bands "
        f"share no design column, the two optima are different solutions (λ₁ at λ₂'s minimiser is "
        f"{m1['l1_at_l2_minimiser']:.4f}), and the gap is {gap['M0']['min_abs_gap']:.4f} or more "
        f"under M0 and {gap['headline']['min_abs_gap']:.4f} or more in the headline. It is "
        f"reported as an unexplained numerical coincidence."])


def docs07_line() -> str:
    s = pl.read_csv(SUMMARY, infer_schema_length=None).filter(pl.col("arm") != "headline")
    parts = []
    for lam in READINGS:
        q = s.filter(pl.col("lam") == lam)
        arms = [r["arm"] for r in q.iter_rows(named=True) if r["sensitive"]]
        if arms:
            parts.append(f"{SYM[lam]} ({', '.join(arms)})")
    return (f"- **Sensitive to redispatch** (`docs/11b_redispatch_sensitivity_results.md`, pre-registered "
            f"rule): {', '.join(parts)}. Masking removes {removed_share('M1'):.0%} to "
            f"{removed_share('M0'):.0%} of the negative-price quarter-hours, so this is a sensitivity "
            f"result and the headline verdicts stand.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--diagnose", action="store_true")
    if ap.parse_args().diagnose:
        d = diagnose()
        d.write_csv(DIAG)
        print(d)
        print(f"wrote {DIAG}")
        return
    s = summarise()
    s.write_csv(SUMMARY)
    print(s)
    print(f"wrote {SUMMARY}")


if __name__ == "__main__":
    main()
