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
    paired_abs_bias,
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

# Depth grid for the r-hat metric, fixed across every cell so cells are comparable.
# 0-150 EUR/MWh covers 98.4% of exposed cohort-quarter-hours (the old 0-80 grid
# covered 95.9%); beyond it both curves are saturated and the integral adds nothing.
DEPTH_GRID = np.linspace(0.0, 150.0, 301)
METHODS = ["M1", "B0", "B1", "B2", "B3", "B4", "B5", "Proxy", "Oracle"]
GATE_RIVALS = ["B1", "B2", "B3", "B4"]


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
        for name in METHODS
    ]
    for row in rows:
        row.update(
            censoring_rate=cfg.censoring_rate, gamma=cfg.gamma,
            r_shape=cfg.r_shape, seed=cfg.seed, area=cfg.area,
            fit_seconds=round(timings[row["method"]], 2),
        )

    # Paired comparisons against M1 on the censored quarter-hours: absolute error
    # for the MAE tests, signed error for the bias tests.
    censored = data.censored
    err = {n: np.abs(f["a_hat"] - data.a_true_mw) for n, f in fits.items()}
    signed = {n: f["a_hat"] - data.a_true_mw for n, f in fits.items()}
    paired = {
        n: paired_difference(err["M1"], err[n], censored, data.berlin_date)
        for n in METHODS if n != "M1"
    }
    paired_bias = {
        n: paired_abs_bias(signed["M1"], signed[n], censored, data.berlin_date)
        for n in METHODS if n != "M1"
    }

    return {
        "config": cfg, "data": data, "fits": fits, "rows": rows,
        "timings": timings, "paired": paired, "paired_bias": paired_bias,
        "r_true": r_true, "r_hat": r_hat,
    }


def gate_check(result: dict) -> dict:
    """The week-6 criterion of spec section 7 as revised in v1.6, on ONE cell.

    The full criterion has three parts and spans several cells:

      (a) gamma = 0, all three r* shapes: integrated |r-hat - r*| below B3's.
      (b) gamma in {0.5, 1}: |bias of A-hat| AND the curtailed-energy error both
          below each of B1-B4.
      (c) gamma = 0: M1's MAE not significantly WORSE than B2 (the no-harm clause).

    This function evaluates whichever parts apply to the cell it is given, and says
    which it could not judge. All tests are paired with a 95% event-day block
    bootstrap; the real criterion pools seeds 42-46, so a single seed is a preview
    and settles nothing on its own.

    On (b): the curtailed-energy error equals |bias| * n_censored * 0.25 exactly, so
    the two conditions rank methods identically and (b) is in substance one test.
    Both are reported because the gate asks for both.
    """
    by_method = {r["method"]: r for r in result["rows"]}
    gamma = result["config"].gamma
    out: dict = {"gamma": gamma, "r_shape": result["config"].r_shape}

    # (a) response-curve recovery, judged at gamma = 0.
    if gamma == 0.0:
        r_m1 = by_method["M1"]["int_abs_r_error"]
        r_b3 = by_method["B3"]["int_abs_r_error"]
        out["a_applies"] = True
        out["criterion_a"] = bool(np.isfinite(r_m1) and np.isfinite(r_b3) and r_m1 < r_b3)
        out["int_abs_r_error_m1"] = r_m1
        out["int_abs_r_error_b3"] = r_b3
    else:
        out["a_applies"] = False
        out["criterion_a"] = None

    # (b) bias and curtailed energy, judged at gamma > 0.
    if gamma > 0.0:
        beats_bias = {n: result["paired_bias"][n]["a_better"] for n in GATE_RIVALS}
        # The energy condition is the SAME paired bootstrap, not a bare point
        # comparison: the gate says every test is paired with a 95% event-day CI.
        # Because the curtailed-energy error is |bias| * n_censored * 0.25 and both
        # methods see the same drawn days in every bootstrap replicate, this test is
        # identical to the bias test by construction -- which is exactly why the two
        # conditions in (b) are one test reported two ways (spec section 7).
        beats_energy = dict(beats_bias)
        m1_energy = by_method["M1"]["energy_abs_error_mwh"]
        out["b_applies"] = True
        out["criterion_b"] = bool(all(beats_bias.values()) and all(beats_energy.values()))
        out["beats_bias"] = beats_bias
        out["beats_energy"] = beats_energy
        out["m1_energy_mwh"] = m1_energy
    else:
        out["b_applies"] = False
        out["criterion_b"] = None

    # (c) no-harm against deletion, judged at gamma = 0.
    if gamma == 0.0:
        p = result["paired"]["B2"]
        worse = bool(np.isfinite(p["diff"]) and p["diff"] > 0 and p["significant"])
        out["c_applies"] = True
        out["criterion_c"] = not worse
        out["m1_minus_b2_mae"] = p["diff"]
        out["m1_minus_b2_ci"] = [p["lo"], p["hi"]]
    else:
        out["c_applies"] = False
        out["criterion_c"] = None

    judged = [out[k] for k in ("criterion_a", "criterion_b", "criterion_c")
              if out[k] is not None]
    out["pass_judged_parts"] = bool(judged) and all(judged)
    return out


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
    head = (f"{'method':<8}{'bias_MW':>9}{'95% CI':>20}{'energy_err':>12}{'rel':>7}"
            f"{'MAE_cens':>10}{'MAE_rel':>8}{'cov80':>7}{'int|r-r*|':>11}{'s':>7}")
    print(head)
    print("-" * len(head))
    for r in rows:
        ci = f"[{r['bias_lo']:,.0f}, {r['bias_hi']:,.0f}]"
        ire = (f"{r['int_abs_r_error']:.4f}"
               if np.isfinite(r["int_abs_r_error"]) else "-")
        cov = f"{r['coverage80_a']:.2f}" if np.isfinite(r["coverage80_a"]) else "-"
        rel = (f"{r['energy_rel_error']:.3f}"
               if np.isfinite(r["energy_rel_error"]) else "-")
        print(f"{r['method']:<8}{r['bias_mw']:>9,.0f}{ci:>20}"
              f"{r['energy_abs_error_mwh']:>12,.0f}{rel:>7}"
              f"{r['censored_mae_mw']:>10,.0f}{r['censored_mae_rel']:>8.3f}"
              f"{cov:>7}{ire:>11}{r['fit_seconds']:>7.1f}")


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
        print("\nPaired vs M1 on censored QHs (negative = M1 better, event-day "
              "bootstrap). |bias| is the headline, MAE is secondary:")
        for name in METHODS:
            if name == "M1":
                continue
            pb, pm = res["paired_bias"][name], res["paired"][name]
            print(f"  M1 - {name:<7} |bias| {pb['diff']:>8,.1f} "
                  f"[{pb['lo']:>8,.1f}, {pb['hi']:>8,.1f}] "
                  f"{'SIG' if pb['significant'] else 'ns '}   "
                  f"MAE {pm['diff']:>8,.1f} "
                  f"[{pm['lo']:>8,.1f}, {pm['hi']:>8,.1f}] "
                  f"{'SIG' if pm['significant'] else 'ns '}")

        gate = gate_check(res)
        print(f"\nGate parts judged at this cell (gamma {gate['gamma']}):")
        print(f"  (a) int|r-r*| M1 {gate['int_abs_r_error_m1']:.4f} vs "
              f"B3 {gate['int_abs_r_error_b3']:.4f} -> {gate['criterion_a']}")
        print(f"  (b) not judged here (needs gamma > 0)")
        print(f"  (c) no-harm vs B2: M1-B2 MAE {gate['m1_minus_b2_mae']:,.1f} MW "
              f"-> {gate['criterion_c']}")

        write_rows(res["rows"], RESULTS_DIR / "10_smoke_run.csv")
        res["data"].save_config(RESULTS_DIR / "10_smoke_run_config.json")
        plot_response(res, FIGURES_DIR / "10_response_smoke.png")
        print(f"\nWrote results/10_smoke_run.csv, results/10_smoke_run_config.json, "
              f"figures/10_response_smoke.png")

    if args.gate_preview:
        print("\nGATE PREVIEW (spec v1.6) — 10% censoring, seed 42, "
              "3 r* shapes x gamma {0, 0.5, 1}\n")
        all_rows, summary = [], {}
        for shape in ("step", "logistic", "half"):
            for gamma in (0.0, 0.5, 1.0):
                cfg = SyntheticConfig(area=args.area, censoring_rate=0.10,
                                      gamma=gamma, r_shape=shape, seed=42)
                print(f"--- r* = {shape}, gamma = {gamma}")
                res = run_cell(cfg, train_cfg, verbose=False)
                print_table(res["rows"])
                g = gate_check(res)
                summary[f"{shape}_gamma{gamma}"] = g
                parts = []
                if g["a_applies"]:
                    parts.append(f"(a) {g['criterion_a']}")
                if g["b_applies"]:
                    parts.append(f"(b) {g['criterion_b']} "
                                 f"bias {g['beats_bias']} energy {g['beats_energy']}")
                if g["c_applies"]:
                    parts.append(f"(c) {g['criterion_c']}")
                print("  -> " + "  ".join(parts) + "\n")
                all_rows.extend(res["rows"])
                if gamma == 0.0:
                    plot_response(res, FIGURES_DIR / f"10_response_gate_{shape}.png")

        write_rows(all_rows, RESULTS_DIR / "10_gate_preview.csv")
        (RESULTS_DIR / "10_gate_preview_summary.json").write_text(
            json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
        )
        a_all = all(v["criterion_a"] for v in summary.values() if v["a_applies"])
        b_all = all(v["criterion_b"] for v in summary.values() if v["b_applies"])
        c_all = all(v["criterion_c"] for v in summary.values() if v["c_applies"])
        print(f"At one seed:  (a) {a_all}   (b) {b_all}   (c) {c_all}")
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
