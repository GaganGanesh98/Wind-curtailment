"""Phase K: the statute-anchored bias bridge, and K1's pseudo-event cross-validation.

    python -m src.potential.k_bridge --k1            # K1, writes artifacts/K1/
    python -m src.potential.k_bridge --k1 --smoke    # 20 held-out days, 2,000 draws, scratch only

Every choice below is fixed in `docs/K0_preregistration.md` (commit `K0_COMMIT`), which was
committed before this module existed. Nothing here is tuned on event-days: the covariance is
fitted on the K0 'fit' non-event days and K1 is scored on the 'held-out' ones.

Model, per unit (three-area aggregate or one control area), within a Berlin day:
    y_t = log(H_t / (G_t + RD_t)) = beta_t on anchors (no exposure, price > 0)
    beta ~ GP(m, C),  C(k) = s_d + s_a * rho**k + s_n * 1[k = 0]
Bridge: simple kriging from the day's anchors; band beta_hat +/- (z sqrt(v) + delta).
H is ex post: identification analysis only.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
from pathlib import Path

import numpy as np
import polars as pl
from scipy.optimize import least_squares

from src.potential.k_bridge_data import (
    BUFFER_QH, UNITS, anchor_mask, k0_facts, load_k_frame,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_K1 = REPO_ROOT / "artifacts" / "K1"
K0_COMMIT = "299e3f9"
ALPHA = 0.10
Z = 1.6448536269514722                 # Normal quantile 0.95: the two-sided 90% band
MAX_LAG = 99                           # a DST day has 100 quarter-hours
WINDOWS_PER_DAY = 3
MAX_REDRAWS = 50
CHECK_LAGS = range(1, 33)
CHECK_TOL = 0.05
N_BOOT = 5000
SEED = 42
BINS = (("short", 1, 4), ("medium", 5, 16), ("long", 17, 10_000))
PASS_COVERAGE = (0.85, 0.95)
PASS_HALF_WIDTH = 0.03
GLOBAL_BIAS = 0.047


# ------------------------------------------------------------------ the bias series

def y_series(frame: pl.DataFrame, unit: str, potential: str = "H") -> np.ndarray:
    """log(P / (G + RD)); NaN where P <= 0 or G + RD <= 0 (dropped and counted by callers)."""
    p = frame[f"{potential}_{unit}"].to_numpy().astype(float)
    gr = frame[f"G_{unit}"].to_numpy().astype(float) + frame[f"RD_{unit}"].to_numpy().astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        y = np.log(p / gr)
    y[~((p > 0) & (gr > 0))] = np.nan
    return y


# --------------------------------------------------------------------- covariance fit

def cov_model(k: np.ndarray, s_d: float, s_a: float, rho: float, s_n: float) -> np.ndarray:
    k = np.asarray(k, dtype=float)
    return s_d + s_a * rho ** k + s_n * (k == 0)


def empirical_autocov(days: list[np.ndarray], m: float) -> tuple[np.ndarray, np.ndarray]:
    """Pooled within-day autocovariance by lag 0..MAX_LAG and the pair counts."""
    num, cnt = np.zeros(MAX_LAG + 1), np.zeros(MAX_LAG + 1)
    for y in days:
        z = y - m
        ok = np.isfinite(z)
        z0 = np.where(ok, z, 0.0)
        for k in range(min(MAX_LAG + 1, y.size)):
            both = ok[:y.size - k] & ok[k:]
            num[k] += float((z0[:y.size - k] * z0[k:])[both].sum())
            cnt[k] += float(both.sum())
    with np.errstate(invalid="ignore"):
        return num / cnt, cnt


def fit_cov(days: list[np.ndarray]) -> dict:
    """K0 section 2: m, then (s_d, s_a, rho, s_n) by pair-count-weighted least squares."""
    m = float(np.nanmean(np.concatenate(days)))
    g, n = empirical_autocov(days, m)
    lags = np.arange(MAX_LAG + 1)
    use = n > 0
    w = np.sqrt(n[use])

    def resid(p):
        return w * (cov_model(lags[use], *p) - g[use])
    g0 = g[0]
    x0 = [max(g[MAX_LAG // 2], 1e-8) * 0.5, g0 * 0.5, 0.95, g0 * 0.1]
    sol = least_squares(resid, x0, bounds=([0, 0, 1e-6, 0], [np.inf, np.inf, 1 - 1e-6, np.inf]))
    s_d, s_a, rho, s_n = (float(v) for v in sol.x)
    fit_acf = cov_model(lags, s_d, s_a, rho, s_n) / cov_model(0, s_d, s_a, rho, s_n)
    emp_acf = g / g[0]
    dev = max(abs(fit_acf[k] - emp_acf[k]) for k in CHECK_LAGS)
    return {"m": m, "s_d": s_d, "s_a": s_a, "rho": rho, "s_n": s_n, "n_days": len(days),
            "c0": float(s_d + s_a + s_n), "emp_c0": float(g0), "max_acf_dev_1_32": float(dev),
            "check_passes": bool(dev <= CHECK_TOL), "emp_acf": emp_acf, "fit_acf": fit_acf}


# ----------------------------------------------------------------------------- bridge

def bridge(y: np.ndarray, anchors: np.ndarray, targets: np.ndarray, p: dict) -> tuple[np.ndarray, np.ndarray]:
    """Simple kriging of one day: beta_hat and predictive variance v at `targets`."""
    a = np.flatnonzero(anchors & np.isfinite(y))
    t = np.flatnonzero(targets)
    if a.size == 0:
        return np.full(t.size, np.nan), np.full(t.size, np.nan)
    cov = lambda i, j: cov_model(np.abs(i[:, None] - j[None, :]), p["s_d"], p["s_a"], p["rho"], p["s_n"])
    caa, cta = cov(a, a), cov(t, a)
    sol = np.linalg.solve(caa, np.column_stack([y[a] - p["m"], cta.T]))
    beta = p["m"] + cta @ sol[:, 0]
    v = (p["s_d"] + p["s_a"] + p["s_n"]) - np.einsum("ij,ji->i", cta, sol[:, 1:])
    return beta, np.maximum(v, 0.0)


# --------------------------------------------------------------------------------- K1

def _days(frame: pl.DataFrame, dates: list[str]) -> list[pl.DataFrame]:
    parts = frame.partition_by("berlin_date", as_dict=True, maintain_order=True)
    return [parts[(d,)] for d in dates]


def draw_windows(heldout: list[pl.DataFrame], runs: list[tuple[int, int]], rng) -> list[dict]:
    """K0 section 3: 3 windows per held-out day, each a real (start, length), redrawn if bad."""
    out = []
    for g in heldout:
        n, day = g.height, g["berlin_date"][0]
        for j in range(WINDOWS_PER_DAY):
            for _ in range(MAX_REDRAWS):
                s, length = runs[int(rng.integers(len(runs)))]
                if s + length > n:
                    continue
                masked = np.zeros(n, bool)
                masked[s:s + length] = True
                anchors = ~np.convolve(masked, np.ones(2 * BUFFER_QH + 1), "same").astype(bool)
                if anchors.any():
                    out.append({"day": day, "j": j, "start": s, "length": length,
                                "masked": masked, "anchors": anchors})
                    break
    return out


def _bin(length: int) -> str:
    return next(name for name, lo, hi in BINS if lo <= length <= hi)


def run_k1(smoke: bool = False) -> dict:
    frame = load_k_frame().filter(pl.col("keep")).sort("ts_utc")
    facts = k0_facts(frame)
    fit_days = _days(frame, facts["nonevent_list"][:facts["fit_days"]])
    held = _days(frame, facts["nonevent_list"][facts["fit_days"]:])
    if smoke:
        held = held[:20]
    rng = np.random.default_rng(SEED)
    windows = draw_windows(held, facts["run_table"], rng)
    cov_rows, qh_rows = [], []
    for potential in ("H", "F"):
        for u in UNITS:
            ys_fit = [y_series(g, u, potential) for g in fit_days]
            p = fit_cov(ys_fit)
            terciles = None
            if not p["check_passes"]:                       # K0: wind-level split
                hm = np.array([np.nanmean(g[f"H_{u}"].to_numpy()) for g in fit_days])
                edges = np.quantile(hm, [1 / 3, 2 / 3])
                tid = np.digitize(hm, edges)
                terciles = {"edges": edges, "fits": [fit_cov([y for y, t in zip(ys_fit, tid) if t == k])
                                                     for k in range(3)]}
            cov_rows.append({"potential": potential, "unit": u, **{k: p[k] for k in (
                "m", "s_d", "s_a", "rho", "s_n", "c0", "emp_c0", "max_acf_dev_1_32",
                "check_passes", "n_days")}, "tercile_split": terciles is not None,
                **({f"tercile{k}_check": terciles["fits"][k]["check_passes"] for k in range(3)}
                   if terciles else {})})
            hd = {g["berlin_date"][0]: g for g in held}
            for wi, w in enumerate(windows):
                g = hd[w["day"]]
                y = y_series(g, u, potential)
                pp = p
                if terciles is not None:
                    k = int(np.digitize(np.nanmean(g[f"H_{u}"].to_numpy()), terciles["edges"]))
                    pp = terciles["fits"][k]
                tgt = w["masked"] & np.isfinite(y)
                beta, v = bridge(y, w["anchors"], tgt, pp)
                hw = Z * np.sqrt(v)
                for t, b, h in zip(np.flatnonzero(tgt), beta, hw):
                    qh_rows.append({"potential": potential, "unit": u, "window": wi, "day": w["day"],
                                    "start": w["start"], "length": w["length"], "bin": _bin(w["length"]),
                                    "qh": int(t), "y": float(y[t]), "beta_hat": float(b),
                                    "half_width": float(h), "covered": bool(abs(y[t] - b) <= h)})
    return {"cov": cov_rows, "qh": pl.DataFrame(qh_rows), "windows": windows,
            "n_heldout": len(held), "smoke": smoke}


def summarise(qh: pl.DataFrame, n_boot: int = N_BOOT) -> list[dict]:
    rng = np.random.default_rng(SEED)
    rows = []
    for (potential, unit), g in sorted(qh.group_by(["potential", "unit"]), key=lambda t: t[0]):
        days = sorted(g["day"].unique().to_list())
        idx = rng.integers(0, len(days), size=(n_boot, len(days)))     # same draws per bin
        for b in ("all",) + tuple(n for n, *_ in BINS):
            q = g if b == "all" else g.filter(pl.col("bin") == b)
            if q.height == 0:
                continue
            per_day = {d: (q.filter(pl.col("day") == d)["covered"].to_numpy(),
                           q.filter(pl.col("day") == d)["half_width"].to_numpy()) for d in days}
            cov_bs, med_bs, p90_bs = [], [], []
            for r in idx:
                cv = np.concatenate([per_day[days[i]][0] for i in r])
                hw = np.concatenate([per_day[days[i]][1] for i in r])
                if cv.size:
                    cov_bs.append(cv.mean()); med_bs.append(np.median(hw)); p90_bs.append(np.percentile(hw, 90))
            ci = lambda a: (float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5)))
            hw = q["half_width"].to_numpy()
            rows.append({"potential": potential, "unit": unit, "bin": b,
                         "n_windows": q["window"].n_unique(), "n_qh": q.height,
                         "n_days": q["day"].n_unique(), "coverage": float(q["covered"].mean()),
                         "coverage_lo": ci(cov_bs)[0], "coverage_hi": ci(cov_bs)[1],
                         "median_half_width": float(np.median(hw)), "median_hw_lo": ci(med_bs)[0],
                         "median_hw_hi": ci(med_bs)[1], "p90_half_width": float(np.percentile(hw, 90)),
                         "p90_hw_lo": ci(p90_bs)[0], "p90_hw_hi": ci(p90_bs)[1],
                         "k0_commit": K0_COMMIT})
    return rows


def verdict(summary: list[dict]) -> dict:
    a = next(r for r in summary if r["potential"] == "H" and r["unit"] == UNITS[0] and r["bin"] == "all")
    cov, hw = a["coverage"], a["median_half_width"]
    ok = PASS_COVERAGE[0] <= cov <= PASS_COVERAGE[1] and hw < PASS_HALF_WIDTH
    reasons = []
    if cov < PASS_COVERAGE[0]:
        reasons.append("error model wrong (coverage < 0.85)")
    if cov > PASS_COVERAGE[1]:
        reasons.append("band too wide for its level (coverage > 0.95)")
    if hw >= GLOBAL_BIAS:
        reasons.append("no gain over the measured global bias (median half-width >= 0.047)")
    elif hw >= PASS_HALF_WIDTH:
        reasons.append("gain below the pre-set margin (0.03 <= median half-width < 0.047)")
    return {"verdict": "PASS" if ok else "FAIL", "coverage": cov, "median_half_width": hw,
            "reasons": "; ".join(reasons), "k0_commit": K0_COMMIT}


def _write(path: Path, rows: list[dict]) -> None:
    fields: list[str] = []
    for r in rows:
        fields += [k for k in r if k not in fields]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k1", action="store_true")
    ap.add_argument("--smoke", action="store_true", help="20 held-out days, 2,000 draws, scratch output")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    if not args.k1:
        ap.error("only --k1 exists until K1 passes")
    out = Path(args.out) if args.out else (REPO_ROOT / "demo" / "output" / "k1_smoke"
                                           if args.smoke else OUT_K1)
    out.mkdir(parents=True, exist_ok=True)
    res = run_k1(smoke=args.smoke)
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                          text=True).stdout.strip()
    for r in res["cov"]:
        r.update({"k0_commit": K0_COMMIT, "git_head": head})
    _write(out / "k1_covariance.csv", res["cov"])
    res["qh"].with_columns(pl.lit(K0_COMMIT).alias("k0_commit")).write_csv(out / "k1_masked_qh.csv")
    _write(out / "k1_windows.csv", [{k: w[k] for k in ("day", "j", "start", "length")}
                                    | {"bin": _bin(w["length"]), "k0_commit": K0_COMMIT}
                                    for w in res["windows"]])
    summ = summarise(res["qh"], n_boot=2000 if args.smoke else N_BOOT)
    _write(out / "k1_summary.csv", summ)
    v = verdict(summ)
    _write(out / "k1_verdict.csv", [v | {"smoke": args.smoke, "git_head": head}])
    print(f"windows {len(res['windows'])} on {res['n_heldout']} held-out days -> {out}")
    print(f"K1 {'SMOKE ' if args.smoke else ''}verdict: {v['verdict']}  coverage {v['coverage']:.3f}  "
          f"median half-width {v['median_half_width']:.4f}  {v['reasons']}")


if __name__ == "__main__":
    main()


def k1_diagnostics() -> list[dict]:
    """Why the error model failed, from the FIT days only (no held-out or event data):
    pooled empirical vs fitted autocorrelation at chosen lags, and each wind tercile's fit."""
    frame = load_k_frame().filter(pl.col("keep")).sort("ts_utc")
    facts = k0_facts(frame)
    fit_days = _days(frame, facts["nonevent_list"][:facts["fit_days"]])
    rows = []
    for u in UNITS:
        ys = [y_series(g, u, "H") for g in fit_days]
        p = fit_cov(ys)
        for k in (1, 4, 16, 32, 64, 95):
            rows.append({"unit": u, "kind": "acf", "key": k, "empirical": float(p["emp_acf"][k]),
                         "fitted": float(p["fit_acf"][k]), "k0_commit": K0_COMMIT})
        hm = np.array([np.nanmean(g[f"H_{u}"].to_numpy()) for g in fit_days])
        tid = np.digitize(hm, np.quantile(hm, [1 / 3, 2 / 3]))
        for k in range(3):
            q = fit_cov([y for y, t in zip(ys, tid) if t == k])
            rows.append({"unit": u, "kind": "tercile", "key": k, "empirical": q["emp_c0"],
                         "fitted": q["c0"], "n_days": int((tid == k).sum()),
                         "acf_dev_1_32": q["max_acf_dev_1_32"], "check_passes": q["check_passes"],
                         "k0_commit": K0_COMMIT})
    return rows
