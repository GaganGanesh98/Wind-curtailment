"""The ablation ladder: M1 against M1 with one piece removed.

    python -m src.censoring.run_ablations                 default cell
    python -m src.censoring.run_ablations --gamma 1.0     a harder cell
    python -m src.censoring.run_ablations --all-gammas    0, 0.5 and 1.0

Why this script exists
----------------------
A baseline is somebody else's method and answers "is this better than what
exists?". An **ablation** is this method with one component switched off -- same
code, same data, same seed -- and answers "which part is doing the work?". For a
method contribution the second question is the one that has to be answered, and no
external baseline can answer it. Prof. Iliev's rule that the contribution must be a
method, not an application, is a rule about exactly this.

The two are not interchangeable and this project needs both:

  * ablations (here)          -> evidence that the structure earns its place;
  * baselines (baselines.py)  -> evidence that recent work did not already solve it.

The ladder
----------
Every rung differs from the full model in exactly one recorded field, which the
script asserts rather than trusts.

  M1  full model
  A1  no observation model     -- the latent head alone, trained on observed G.
                                  This is numerically the same estimator as B1;
                                  it is listed twice on purpose, because it plays
                                  both roles: the naive baseline, and the ablation
                                  that removes the entire contribution.
  A2  exposure off             -- every cohort exposed in every quarter-hour, depth
                                  measured below zero. Keeps the price signal,
                                  removes the EEG rule table.
  A3  one cohort               -- a single fleet-wide cohort and one response.
  A4  sigmoid response head    -- the pre-v1.6 functional form.
  A5  additive latent head     -- A = F + g(x) instead of F * exp(g(x)).
  A6  no weather proxy         -- the forecast alone anchors the latent head.
  A7  price inside g           -- deliberately broken: the leakage rule turned off.

A7 is the one to read carefully. It should NOT look bad on the headline error --
if it did, the leakage rule would be self-enforcing and would not need a test.
What it should do is damage r-hat, because once A can see the price it can absorb
the curtailment itself and leave the response head nothing to explain.
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import numpy as np

from src.censoring import baselines as bl
from src.censoring.metrics import (
    curtailment_recovery,
    integrated_response_error,
    paired_difference,
    recovery_skill,
    score_method,
)
from src.censoring.model import (
    ABLATION_FULL,
    TAUS,
    Ablation,
    TrainConfig,
    fit_m1,
    m1_response_curve,
)
from src.censoring.run_synthetic import DEPTH_GRID, write_rows
from src.censoring.synthetic import SyntheticConfig, generate, true_response_curve

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results"
FIGURES_DIR = REPO_ROOT / "figures"

LADDER: list[Ablation] = [
    ABLATION_FULL,
    Ablation(label="A2", name="exposure off",
             piece_removed="the EEG rule table (who is exposed)",
             exposure_mode="always_on"),
    Ablation(label="A3", name="one cohort",
             piece_removed="cohort structure", cohort_mode="one"),
    Ablation(label="A4", name="sigmoid head",
             piece_removed="the piecewise-linear response head",
             response_head="sigmoid"),
    Ablation(label="A5", name="additive latent head",
             piece_removed="the multiplicative form", latent_form="additive"),
    Ablation(label="A6", name="no weather proxy",
             piece_removed="the weather proxy", use_weather=False),
    Ablation(label="A7", name="price inside g",
             piece_removed="the leakage rule (deliberately broken)",
             price_in_latent=True),
]


def run_ladder(cfg: SyntheticConfig, train_cfg: TrainConfig) -> dict:
    data = generate(cfg)
    r_true = true_response_curve(cfg, DEPTH_GRID)
    d = data.diagnostics
    print(f"  {d['n_qh']:,} QH on {d['n_days']} days; negative "
          f"{d['realised_negative_rate']:.1%}, censored {d['censored_rate']:.1%}, "
          f"{d['qh_in_0_to_5_band']:,} QH in the 0-5 band")

    fits: dict[str, dict] = {}
    rows: list[dict] = []

    for ab in LADDER:
        differs = ab.differs_from_full()
        assert len(differs) <= 1, f"{ab.label} changes {differs}, not one piece"
        t0 = time.perf_counter()
        fit = fit_m1(data, train_cfg, ablation=ab)
        secs = time.perf_counter() - t0
        fits[ab.label] = fit
        r_hat = m1_response_curve(fit, data, DEPTH_GRID)
        row = score_method(fit, data, DEPTH_GRID, r_hat, r_true, TAUS)
        row.update(ablation=ab.label, ablation_name=ab.name,
                   piece_removed=ab.piece_removed,
                   differs_from_full=";".join(differs) or "-",
                   fit_seconds=round(secs, 1))
        rows.append(row)
        print(f"  {ab.label:<4}{ab.name:<22}{secs:6.1f}s")

    # A1 is the latent head with no observation model at all -- numerically the
    # same estimator as B1, listed under both names because it plays both roles.
    t0 = time.perf_counter()
    a1 = bl.fit_b1(data, train_cfg)
    a1["name"] = "A1"
    a1["c_hat"] = None
    row = score_method(a1, data, DEPTH_GRID, None, r_true, TAUS)
    row.update(ablation="A1", ablation_name="no observation model",
               piece_removed="the whole observation model (= B1)",
               differs_from_full="observation_model",
               fit_seconds=round(time.perf_counter() - t0, 1))
    rows.insert(1, row)
    fits["A1"] = a1
    print(f"  A1  no observation model {row['fit_seconds']:6.1f}s")

    # Anchors for the skill score: the published forecast and our own oracle.
    b0 = bl.fit_b0(data)
    oracle = bl.fit_oracle(data, train_cfg)
    mae = lambda f: float(np.abs(f["a_hat"] - data.a_true_mw)[data.censored].mean())
    mae_b0, mae_oracle = mae(b0), mae(oracle)
    for row in rows:
        row["recovery_skill"] = recovery_skill(
            row["censored_mae_mw"], mae_b0, mae_oracle
        )
        row.update(censoring_rate=cfg.censoring_rate, gamma=cfg.gamma,
                   r_shape=cfg.r_shape, seed=cfg.seed,
                   mae_b0=round(mae_b0, 1), mae_oracle=round(mae_oracle, 1),
                   headroom_mw=round(mae_b0 - mae_oracle, 1))

    err = {k: np.abs(f["a_hat"] - data.a_true_mw) for k, f in fits.items()}
    paired = {
        k: paired_difference(err[k], err["M1"], data.censored, data.berlin_date)
        for k in fits if k != "M1"
    }
    return {"config": cfg, "data": data, "fits": fits, "rows": rows,
            "paired": paired, "r_true": r_true,
            "mae_b0": mae_b0, "mae_oracle": mae_oracle}


def print_ladder(rows: list[dict], paired: dict) -> None:
    head = (f"{'':<4}{'piece removed':<40}{'skill':>7}{'MAE':>8}{'bias':>8}"
            f"{'int|r-r*|':>11}{'c_MAE':>8}{'c_corr':>8}")
    print(head)
    print("-" * len(head))
    for r in rows:
        ire = f"{r['int_abs_r_error']:.4f}" if np.isfinite(r["int_abs_r_error"]) else "-"
        cm = f"{r['c_mae']:.4f}" if np.isfinite(r["c_mae"]) else "-"
        cc = f"{r['c_corr']:.3f}" if np.isfinite(r["c_corr"]) else "-"
        piece = r["piece_removed"] if r["ablation"] != "M1" else "— (full model)"
        print(f"{r['ablation']:<4}{piece:<40}{r['recovery_skill']:>7.3f}"
              f"{r['censored_mae_mw']:>8,.0f}{r['bias_mw']:>8,.0f}{ire:>11}{cm:>8}{cc:>8}")
    print()
    print("Cost of removing each piece (MAE of the ablation minus MAE of the full "
          "model; positive = the piece was earning its place):")
    for k, p in paired.items():
        flag = "SIG" if p["significant"] else "ns "
        print(f"  {k:<4} {p['diff']:>8,.1f} MW  [{p['lo']:>8,.1f}, {p['hi']:>8,.1f}]  {flag}")


def plot_ladder(result: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cfg = result["config"]
    fig, ax = plt.subplots(figsize=(7.6, 4.8))
    ax.plot(DEPTH_GRID, result["r_true"], color="black", lw=2.6, label="r* (true)")
    styles = {"M1": ("#1f77b4", "-", 2.4), "A2": ("#d62728", "--", 1.8),
              "A3": ("#2ca02c", "--", 1.6), "A4": ("#9467bd", ":", 1.6),
              "A5": ("#8c564b", ":", 1.6), "A6": ("#e377c2", "-.", 1.6),
              "A7": ("#ff7f0e", "-", 2.2)}
    from src.censoring.model import m1_response_curve as curve
    for label, (colour, ls, lw) in styles.items():
        if label not in result["fits"]:
            continue
        r = curve(result["fits"][label], result["data"], DEPTH_GRID)
        name = next((a.name for a in LADDER if a.label == label), label)
        ax.plot(DEPTH_GRID, r, color=colour, ls=ls, lw=lw, label=f"{label} {name}")
    ax.set_xlabel("depth below the cohort threshold, EUR/MWh")
    ax.set_ylabel("share of exposed capacity switched off")
    ax.set_title(f"Ablation ladder — {cfg.r_shape} r*, censoring "
                 f"{cfg.censoring_rate:.0%}, gamma {cfg.gamma}, seed {cfg.seed}")
    ax.set_ylim(-0.03, 1.03)
    ax.grid(alpha=0.3)
    ax.legend(frameon=False, fontsize=8, ncol=2)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gamma", type=float, default=0.5)
    ap.add_argument("--all-gammas", action="store_true")
    ap.add_argument("--rate", type=float, default=0.20)
    ap.add_argument("--shape", default="logistic")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--max-epochs", type=int, default=2000)
    args = ap.parse_args()

    train_cfg = TrainConfig(max_epochs=args.max_epochs)
    gammas = (0.0, 0.5, 1.0) if args.all_gammas else (args.gamma,)
    wall0 = time.perf_counter()
    all_rows = []

    for gamma in gammas:
        cfg = SyntheticConfig(censoring_rate=args.rate, gamma=gamma,
                              r_shape=args.shape, seed=args.seed)
        print(f"\nABLATION LADDER — {args.shape} r*, censoring {args.rate:.0%}, "
              f"gamma {gamma}, seed {args.seed}")
        res = run_ladder(cfg, train_cfg)
        print()
        print_ladder(res["rows"], res["paired"])
        print(f"\n  anchors: B0 MAE {res['mae_b0']:,.0f} MW, oracle "
              f"{res['mae_oracle']:,.0f} MW, recoverable headroom "
              f"{res['mae_b0'] - res['mae_oracle']:,.0f} MW")
        all_rows.extend(res["rows"])
        plot_ladder(res, FIGURES_DIR / f"11_ablation_gamma{gamma}.png")

    write_rows(all_rows, RESULTS_DIR / "11_ablation_ladder.csv")
    print(f"\nWrote results/11_ablation_ladder.csv and figures/11_ablation_gamma*.png")
    print(f"Total wall clock: {time.perf_counter() - wall0:.1f}s")


if __name__ == "__main__":
    main()
