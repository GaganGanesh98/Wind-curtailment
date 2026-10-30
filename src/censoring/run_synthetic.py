"""Run the E1 semi-synthetic benchmark.

    python -m src.censoring.run_synthetic --smoke          one cell, DE, seed 42
    python -m src.censoring.run_synthetic --gate-preview   three r* shapes at 10%
    python -m src.censoring.run_synthetic                  the full grid (not yet)

The full grid (rate x gamma x shape x seeds 42-46) is deliberately not wired up until
the smoke run and the gate preview have been reported and confirmed.
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

import numpy as np

from src.censoring import baselines as bl
from src.censoring.metrics import (
    integrated_response_error,
    paired_difference,
    score_method,
)
from src.censoring.model import TAUS, TrainConfig, fit_m1, m1_response_curve
from src.censoring.synthetic import (
    SyntheticConfig,
    generate,
    true_response_curve,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
FIGURES_DIR = REPO_ROOT / "figures"

DEPTH_GRID = np.linspace(0.0, 80.0, 161)


def run_cell(cfg: SyntheticConfig, train_cfg: TrainConfig | None = None,
             verbose: bool = True) -> dict:
    """Generate one cell of the grid, fit every method, score them all."""
    train_cfg = train_cfg or TrainConfig()
    t0 = time.perf_counter()
    data = generate(cfg)
    gen_s = time.perf_counter() - t0
    if verbose:
        d = data.diagnostics
        print(f"  generated {d['n_qh']:,} QH on {d['n_days']} days in {gen_s:.1f}s; "
              f"negative {d['realised_negative_rate']:.1%}, "
              f"censored {d['censored_rate']:.1%}, "
              f"mean c on censored {d['mean_c_on_censored']:.3f}")

    fits: dict[str, dict] = {}
    timings: dict[str, float] = {"generate": gen_s}

    t0 = time.perf_counter()
    fits["M1"] = fit_m1(data, train_cfg)
    timings["M1"] = time.perf_counter() - t0
    if verbose:
        print(f"  M1        {timings['M1']:6.1f}s  ({fits['M1']['epochs_run']} epochs)")

    for name, fn in bl.ALL_BASELINES.items():
        t0 = time.perf_counter()
        fits[name] = fn(data) if name == "B0" else fn(data, train_cfg)
        timings[name] = time.perf_counter() - t0
        if verbose:
            print(f"  {name:<9} {timings[name]:6.1f}s  "
                  f"({fits[name].get('epochs_run', 0)} epochs)")

    r_true = true_response_curve(cfg, DEPTH_GRID)
    r_hat = {
        "M1": m1_response_curve(fits["M1"], data, DEPTH_GRID),
        "B3": bl.b3_response_curve(fits["B3"], DEPTH_GRID),
    }

    rows = [
        score_method(fits[name], data, DEPTH_GRID, r_hat.get(name), r_true, TAUS)
        for name in ["M1", "B0", "B1", "B2", "B3", "B4", "Oracle"]
    ]
    for row in rows:
        row.update(
            censoring_rate=cfg.censoring_rate, gamma=cfg.gamma,
            r_shape=cfg.r_shape, seed=cfg.seed, area=cfg.area,
            fit_seconds=round(timings[row["method"]], 2),
        )

    # Paired differences against M1, on the censored quarter-hours.
    censored = data.censored
    err = {n: np.abs(f["a_hat"] - data.a_true_mw) for n, f in fits.items()}
    paired = {
        n: paired_difference(err["M1"], err[n], censored, data.berlin_date)
        for n in ["B0", "B1", "B2", "B3", "B4", "Oracle"]
    }

    return {
        "config": cfg, "data": data, "fits": fits, "rows": rows,
        "timings": timings, "paired": paired,
        "r_true": r_true, "r_hat": r_hat,
    }


def gate_check(result: dict) -> dict:
    """The week-6 criterion of spec section 7, evaluated on this cell.

    Pass needs both, on the paired difference with a 95% event-day block-bootstrap CI
    excluding zero:
      (a) integrated |r-hat - r*| lower than B3's implied response;
      (b) MAE of A-hat on censored quarter-hours lower than **each** of B1-B4.

    At a single seed this is a preview, not the gate: the real criterion pools the
    five seeds. A single-seed pass does not establish the gate, and a single-seed
    fail does not settle it either.
    """
    by_method = {r["method"]: r for r in result["rows"]}
    r_m1 = by_method["M1"]["int_abs_r_error"]
    r_b3 = by_method["B3"]["int_abs_r_error"]
    crit_a = bool(np.isfinite(r_m1) and np.isfinite(r_b3) and r_m1 < r_b3)

    beats = {n: result["paired"][n]["a_better"] for n in ["B1", "B2", "B3", "B4"]}
    crit_b = all(beats.values())

    return {
        "criterion_a_r_curve": crit_a,
        "int_abs_r_error_m1": r_m1,
        "int_abs_r_error_b3": r_b3,
        "criterion_b_mae_beats_all": crit_b,
        "beats": beats,
        "pass": bool(crit_a and crit_b),
    }


def plot_response(result: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cfg = result["config"]
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.plot(DEPTH_GRID, result["r_true"], color="black", lw=2.4, label="r* (true)")
    ax.plot(DEPTH_GRID, result["r_hat"]["M1"], color="#1f77b4", lw=2.0,
            label="M1 (mechanism-aware)")
    ax.plot(DEPTH_GRID, result["r_hat"]["B3"], color="#d62728", lw=2.0, ls="--",
            label="B3 implied (Hirth-style)")

    br = result["fits"]["B3"]["implied_response"]
    if br["bin_centre"].size:
        ax.scatter(br["bin_centre"], br["r"], s=22, color="#d62728", zorder=5,
                   label="B3 bins")

    ax.set_xlabel("depth below the cohort threshold, EUR/MWh")
    ax.set_ylabel("share of exposed capacity switched off")
    ax.set_title(
        f"Recovered fleet response — {cfg.r_shape} r*, "
        f"censoring {cfg.censoring_rate:.0%}, gamma {cfg.gamma}, seed {cfg.seed}"
    )
    ax.set_ylim(-0.03, 1.03)
    ax.grid(alpha=0.3)
    ax.legend(frameon=False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def write_rows(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def print_table(rows: list[dict]) -> None:
    head = (f"{'method':<8}{'MAE_cens_MW':>12}{'95% CI':>22}{'rel':>8}"
            f"{'bias_MW':>10}{'MAE_all':>10}{'cov80':>7}{'int|r-r*|':>11}{'s':>7}")
    print(head)
    print("-" * len(head))
    for r in rows:
        ci = f"[{r['censored_mae_lo']:,.0f}, {r['censored_mae_hi']:,.0f}]"
        ire = (f"{r['int_abs_r_error']:.4f}"
               if np.isfinite(r["int_abs_r_error"]) else "-")
        cov = f"{r['coverage80_a']:.2f}" if np.isfinite(r["coverage80_a"]) else "-"
        print(f"{r['method']:<8}{r['censored_mae_mw']:>12,.0f}{ci:>22}"
              f"{r['censored_mae_rel']:>8.3f}{r['censored_bias_mw']:>10,.0f}"
              f"{r['all_mae_mw']:>10,.0f}{cov:>7}{ire:>11}{r['fit_seconds']:>7.1f}")


def run_gamma_diagnostic(train_cfg: TrainConfig, area: str) -> list[dict]:
    """Does the week-6 criterion (b) failure move with gamma?

    Criterion (b) is pre-registered at gamma = 0. That is the one setting in which
    the censored sample is representative of the whole, so deleting it (B2) or
    calibrating around it (B3) costs almost nothing and both land on the oracle.
    This sweep records whether the baselines degrade as the confounding grows while
    M1 holds -- which is the difference the structure is supposed to make.
    """
    rows = []
    for gamma in (0.0, 0.5, 1.0):
        cfg = SyntheticConfig(area=area, censoring_rate=0.20, gamma=gamma,
                              r_shape="logistic", seed=42)
        res = run_cell(cfg, train_cfg, verbose=False)
        d = res["data"]
        for r in res["rows"]:
            p = res["paired"].get(r["method"], {})
            rows.append({
                **r,
                "mean_forecast_censored_mw": float(d.forecast_mw[d.censored].mean()),
                "mean_forecast_all_mw": float(d.forecast_mw.mean()),
                "paired_diff_vs_m1_mw": p.get("diff", float("nan")),
                "paired_lo": p.get("lo", float("nan")),
                "paired_hi": p.get("hi", float("nan")),
                "m1_significantly_better": p.get("a_better", ""),
            })
    return rows


def run_b3_bin_sensitivity(train_cfg: TrainConfig, area: str) -> list[dict]:
    """How much of criterion (a) is the bin count rather than the method?

    B3's implied response is a binned ratio, and the bin count is a free choice I
    made, not something Hirth fixes. If M1's advantage on the response curve
    evaporates as B3 is given more bins, then criterion (a) measures my binning, not
    the two-stage approach. This records it instead of leaving it implicit.
    """
    rows = []
    for shape in ("logistic", "step", "half"):
        cfg = SyntheticConfig(area=area, censoring_rate=0.20, gamma=0.0,
                              r_shape=shape, seed=42)
        data = generate(cfg)
        r_true = true_response_curve(cfg, DEPTH_GRID)
        m1 = fit_m1(data, train_cfg)
        e_m1 = integrated_response_error(
            m1_response_curve(m1, data, DEPTH_GRID), r_true, DEPTH_GRID
        )
        for n_bins in (4, 8, 16, 32, 64):
            f = bl.fit_b3(data, train_cfg, n_bins=n_bins)
            rows.append({
                "r_shape": shape,
                "n_bins": n_bins,
                "int_abs_r_error_m1": round(e_m1, 5),
                "int_abs_r_error_b3": round(
                    integrated_response_error(
                        bl.b3_response_curve(f, DEPTH_GRID), r_true, DEPTH_GRID
                    ), 5),
            })
    for r in rows:
        r["m1_better"] = r["int_abs_r_error_m1"] < r["int_abs_r_error_b3"]
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--smoke", action="store_true", help="one cell, DE, seed 42")
    ap.add_argument("--diagnostics", action="store_true",
                    help="gamma sweep and B3 bin-count sensitivity")
    ap.add_argument("--gate-preview", action="store_true",
                    help="10%% censoring, gamma 0, all three r* shapes, seed 42")
    ap.add_argument("--area", default="DE")
    ap.add_argument("--max-epochs", type=int, default=1000)
    args = ap.parse_args()

    train_cfg = TrainConfig(max_epochs=args.max_epochs)
    wall0 = time.perf_counter()

    if args.smoke:
        cfg = SyntheticConfig(area=args.area, censoring_rate=0.20, gamma=0.0,
                              r_shape="logistic", seed=42)
        print(f"\nSMOKE RUN — {cfg.area}, censoring {cfg.censoring_rate:.0%}, "
              f"gamma {cfg.gamma}, r* {cfg.r_shape}, seed {cfg.seed}\n")
        res = run_cell(cfg, train_cfg)
        print()
        print_table(res["rows"])
        print("\nPaired difference vs M1 on censored QHs "
              "(negative = M1 better, event-day bootstrap):")
        for name, p in res["paired"].items():
            flag = "significant" if p["significant"] else "not significant"
            print(f"  M1 - {name:<7} {p['diff']:>9,.0f} MW  "
                  f"[{p['lo']:>8,.0f}, {p['hi']:>8,.0f}]  {flag}")

        gate = gate_check(res)
        print(f"\nGate preview at this cell: "
              f"{'PLAUSIBLE' if gate['pass'] else 'NOT MET'}")
        print(f"  (a) int|r-r*|  M1 {gate['int_abs_r_error_m1']:.4f} "
              f"vs B3 {gate['int_abs_r_error_b3']:.4f} -> {gate['criterion_a_r_curve']}")
        print(f"  (b) beats B1-B4 on censored MAE -> {gate['beats']}")

        write_rows(res["rows"], RESULTS_DIR / "10_smoke_run.csv")
        res["data"].save_config(RESULTS_DIR / "10_smoke_run_config.json")
        plot_response(res, FIGURES_DIR / "10_response_smoke.png")
        print(f"\nWrote results/10_smoke_run.csv, results/10_smoke_run_config.json, "
              f"figures/10_response_smoke.png")

    if args.gate_preview:
        print(f"\nGATE PREVIEW — censoring 10%, gamma 0, seed 42, all r* shapes\n")
        all_rows, summary = [], {}
        for shape in ("step", "logistic", "half"):
            cfg = SyntheticConfig(area=args.area, censoring_rate=0.10, gamma=0.0,
                                  r_shape=shape, seed=42)
            print(f"--- r* = {shape}")
            res = run_cell(cfg, train_cfg)
            print_table(res["rows"])
            gate = gate_check(res)
            summary[shape] = gate
            print(f"  -> {'PLAUSIBLE' if gate['pass'] else 'NOT MET'}  "
                  f"(a) {gate['criterion_a_r_curve']}  (b) {gate['beats']}\n")
            all_rows.extend(res["rows"])
            plot_response(res, FIGURES_DIR / f"10_response_gate_{shape}.png")

        write_rows(all_rows, RESULTS_DIR / "10_gate_preview.csv")
        (RESULTS_DIR / "10_gate_preview_summary.json").write_text(
            json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
        )
        every = all(g["pass"] for g in summary.values())
        print(f"Week-6 criterion plausible at one seed for all three shapes: {every}")
        print("Wrote results/10_gate_preview.csv, results/10_gate_preview_summary.json")

    if args.diagnostics:
        print("\nDIAGNOSTIC 1 — gamma sweep (20% censoring, logistic r*, seed 42)\n")
        g_rows = run_gamma_diagnostic(train_cfg, args.area)
        write_rows(g_rows, RESULTS_DIR / "10_diag_gamma.csv")
        for gamma in (0.0, 0.5, 1.0):
            sub = [r for r in g_rows if r["gamma"] == gamma]
            f_c = sub[0]["mean_forecast_censored_mw"]
            f_a = sub[0]["mean_forecast_all_mw"]
            print(f"  gamma {gamma}: mean forecast on censored QHs {f_c:,.0f} MW "
                  f"vs {f_a:,.0f} MW overall")
            for r in sub:
                if r["method"] in ("M1", "B2", "B3", "B4", "Oracle"):
                    sig = r["m1_significantly_better"]
                    print(f"    {r['method']:<7} MAE {r['censored_mae_mw']:>7,.0f} MW"
                          + (f"   M1 better: {sig}" if r["method"] != "M1" else ""))

        print("\nDIAGNOSTIC 2 — B3 bin-count sensitivity of criterion (a)\n")
        b_rows = run_b3_bin_sensitivity(train_cfg, args.area)
        write_rows(b_rows, RESULTS_DIR / "10_diag_b3_bins.csv")
        for shape in ("logistic", "step", "half"):
            sub = [r for r in b_rows if r["r_shape"] == shape]
            bins = "  ".join(f"{r['n_bins']}:{r['int_abs_r_error_b3']:.4f}" for r in sub)
            print(f"  {shape:<9} M1 {sub[0]['int_abs_r_error_m1']:.4f}   B3  {bins}")
        print("\nWrote results/10_diag_gamma.csv, results/10_diag_b3_bins.csv")

    if not (args.smoke or args.gate_preview or args.diagnostics):
        raise SystemExit(
            "The full grid is not wired up yet (it waits on confirmation of the "
            "smoke run). Use --smoke, --gate-preview or --diagnostics."
        )

    print(f"\nTotal wall clock: {time.perf_counter() - wall0:.1f}s")


if __name__ == "__main__":
    main()
