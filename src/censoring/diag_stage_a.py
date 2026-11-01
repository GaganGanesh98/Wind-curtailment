"""Shared stage A: mean-bias as a denominator, and multi-cell accuracy.

    python -m src.censoring.diag_stage_a

Two things, both measurements. **No model is changed by this script.**

**1. Mean-bias, because A_hat is a DENOMINATOR.** The response target is
`y_t = 1 - G_t / A_hat_t`, so what propagates into every c_hat is multiplicative
mean-bias in A_hat, not its MAE. And the estimators in play both target a *median*:
`exp(OLS on logs)` estimates the conditional geometric mean, and pinball loss at
tau = 0.5 estimates the median directly. For a right-skewed quantity the median sits
**below** the mean, so a model that is excellent by MAE can still be systematically
low as a denominator.

Direction, so the sign is not misread: if `A_hat` is biased low then `G/A_hat` is
biased high and **c_hat is biased LOW** — curtailment under-estimated. On uncensored
quarter-hours `G = A` exactly, so `A_hat/A_true` there is a clean read on the bias
with no censoring mixed in.

Reported as `mean(A_hat / A_true)` over uncensored quarter-hours, per cell, with a
95% event-day block-bootstrap CI. The energy-weighted form `sum(A_hat)/sum(A_true)` is
reported beside it, since the two differ when the error correlates with level.

**2. Amendment 6's own numbers under hard rule 20.** A6.1's table (1,238.1 against
1,358.3, and B2's 25 MW edge) came from a single cell with no inference. This
recomputes the same quantities across **9 cells** — 3 censoring rates x 3 seeds at
gamma = 0 — so they can be quoted with a range instead of relabelled.

Only gamma = 0 and the three rates are varied: stage A trains on price > 5 EUR/MWh
quarter-hours, whose membership depends on the censoring rate and the seed but **not**
on the r* shape, so shapes would give identical fits and no extra information.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from src.censoring.cohorts import mastr_cohort_set
from src.censoring.m2 import assert_stage_a_beats_forecast, fit_shared_stage_a
from src.censoring.model import TrainConfig
from src.censoring.synthetic import SyntheticConfig, generate
from src.stats_boot import eventday_bootstrap_mean, eventday_bootstrap_ratio

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_CSV = REPO_ROOT / "results" / "20_stage_a_diagnostics.csv"
RATES = (0.10, 0.20, 0.40)
SEEDS = (42, 43, 44)


def main() -> None:
    cohorts = mastr_cohort_set("DE")
    cfg = TrainConfig()
    rows = []

    print("Shared stage A diagnostics, gamma = 0, 3 rates x 3 seeds = 9 cells.")
    print("No model is changed here.\n")
    hdr = (f"{'rate':>5}{'seed':>5}{'mean(Ahat/Atrue)':>18}{'95% CI':>20}"
           f"{'sum ratio':>11}{'MAE sh.':>9}{'MAE F':>8}{'MAE B2':>8}"
           f"{'mean y|unc':>11}")
    print(hdr)
    print("-" * len(hdr))

    for rate in RATES:
        for seed in SEEDS:
            d = generate(SyntheticConfig(censoring_rate=rate, gamma=0.0,
                                         r_shape="step", seed=seed), cohorts=cohorts)
            sa = fit_shared_stage_a(d, cfg=cfg, check=False)
            a_true = d.a_true_mw
            unc = ~d.censored & (a_true > 0)
            ratio = sa.a_hat[unc] / a_true[unc]
            days = np.asarray(d.berlin_date)[unc]
            m, lo, hi, n, nd = eventday_bootstrap_mean(ratio, days)
            sm, slo, shi, _, _ = eventday_bootstrap_ratio(sa.a_hat[unc], a_true[unc],
                                                          days)
            # The quantity that ACTUALLY propagates. On uncensored QHs G = A exactly,
            # so y = 1 - G/A_hat is the systematic offset the response model inherits
            # where there is no censoring at all. E[A/A_hat] is not 1/E[A_hat/A]
            # (Jensen), so this is measured directly rather than inverted.
            y_unc = 1.0 - a_true[unc] / sa.a_hat[unc]
            ym, ylo, yhi, _, _ = eventday_bootstrap_mean(y_unc, days)

            from src.censoring.baselines import fit_b2
            b2 = fit_b2(d, cfg)["a_hat"]
            mae = lambda a, msk=None: float(np.abs(a - a_true)[
                msk if msk is not None else slice(None)].mean())
            chk = assert_stage_a_beats_forecast(sa.a_hat, d.forecast_mw, a_true,
                                                d.censored, label=f"cell r{rate} s{seed}")

            print(f"{rate:>5.0%}{seed:>5}{m:>18.4f}"
                  f"{f'[{lo:.4f}, {hi:.4f}]':>20}{sm:>11.4f}"
                  f"{mae(sa.a_hat):>9,.0f}{mae(d.forecast_mw):>8,.0f}{mae(b2):>8,.0f}"
                  f"{ym:>11.5f}")
            rows.append({
                "censoring_rate": rate, "seed": seed, "gamma": 0.0,
                "mean_ahat_over_atrue": round(float(m), 6),
                "ci_lo": round(float(lo), 6), "ci_hi": round(float(hi), 6),
                "ci_excludes_one": bool(hi < 1.0 or lo > 1.0),
                "mean_y_uncensored": round(float(ym), 6),
                "y_ci_lo": round(float(ylo), 6), "y_ci_hi": round(float(yhi), 6),
                "y_ci_excludes_zero": bool(yhi < 0.0 or ylo > 0.0),
                "sum_ratio": round(float(sm), 6),
                "sum_ratio_lo": round(float(slo), 6),
                "sum_ratio_hi": round(float(shi), 6),
                "n_qh_uncensored": int(n), "n_days": int(nd),
                "mae_shared_all": round(mae(sa.a_hat), 1),
                "mae_forecast_all": round(mae(d.forecast_mw), 1),
                "mae_b2_all": round(mae(b2), 1),
                "mae_shared_censored": round(mae(sa.a_hat, d.censored), 1),
                "mae_forecast_censored": round(mae(d.forecast_mw, d.censored), 1),
                "mae_b2_censored": round(mae(b2, d.censored), 1),
                "hard_check_passes": chk["passes"],
            })

    arr = lambda k: np.array([r[k] for r in rows], dtype=float)
    print(f"\n{'quantity':<34}{'mean':>10}{'min':>10}{'max':>10}")
    print("-" * 64)
    for label, key in (("mean(A_hat / A_true), uncensored", "mean_ahat_over_atrue"),
                       ("MAE shared stage A, all QH", "mae_shared_all"),
                       ("MAE raw forecast F, all QH", "mae_forecast_all"),
                       ("MAE B2 own fit, all QH", "mae_b2_all"),
                       ("MAE shared, censored QH", "mae_shared_censored"),
                       ("MAE forecast F, censored QH", "mae_forecast_censored"),
                       ("MAE B2 own fit, censored QH", "mae_b2_censored")):
        v = arr(key)
        print(f"{label:<34}{v.mean():>10,.4f}{v.min():>10,.4f}{v.max():>10,.4f}"
              if key.startswith("mean_") else
              f"{label:<34}{v.mean():>10,.1f}{v.min():>10,.1f}{v.max():>10,.1f}")

    sh, f_, b2_ = arr("mae_shared_all"), arr("mae_forecast_all"), arr("mae_b2_all")
    print(f"\nshared beats raw forecast in {int((sh < f_).sum())}/{len(sh)} cells; "
          f"B2's edge over shared: mean {float((sh - b2_).mean()):,.1f} MW, "
          f"range [{float((sh - b2_).min()):,.1f}, {float((sh - b2_).max()):,.1f}]")
    yv = arr("mean_y_uncensored")
    n_y = sum(1 for r in rows if r["y_ci_excludes_zero"])
    print(f"\nOFFSET THAT PROPAGATES: mean(1 - G/A_hat) on UNCENSORED QHs "
          f"averages {yv.mean():+.5f}")
    print(f"  range [{yv.min():+.5f}, {yv.max():+.5f}]; CI excludes 0 in "
          f"{n_y}/{len(rows)} cells.")
    print(f"  In percentage-point terms the response model inherits a "
          f"{100*yv.mean():+.3f} pp offset where there is NO censoring. Compare it")
    print("  with the c_hat magnitudes being estimated before reading any of them.")
    mb = arr("mean_ahat_over_atrue")
    n_excl = sum(1 for r in rows if r["ci_excludes_one"])
    print(f"\nMEAN-BIAS VERDICT: mean(A_hat/A_true) averages {mb.mean():.4f} "
          f"(range [{mb.min():.4f}, {mb.max():.4f}]); its CI excludes 1.0 in "
          f"{n_excl}/{len(rows)} cells.")
    if mb.mean() < 0.99:
        print("  A_hat is materially LOW as a denominator. Since c_hat = 1 - G/A_hat,")
        print("  this biases c_hat DOWNWARD -- curtailment under-estimated. Report")
        print("  this figure beside every c_hat result.")
    elif mb.mean() > 1.01:
        print("  A_hat is materially HIGH as a denominator, biasing c_hat UPWARD.")
    else:
        print("  No material mean-bias; c_hat is not systematically shifted by it.")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {OUT_CSV.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
