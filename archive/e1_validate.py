"""SUPERSEDED 8 Nov 2026 -- ported to `src/censoring/validate_synthetic.py`.

Validates `archive/e1_generator.py`, which is itself superseded (see its header).

Its check 6 ("hourly-clock censoring at a positive quarter-hour price exists")
asserted the symptom of that generator's section 51 misreading, so a passing suite
would have locked the bug in. The port drops check 6 and asserts the inverse.

Kept, not deleted: docs/17 and docs/11 quote this suite's output verbatim.
"""

from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from e1_generator import (
    C_EPS,
    PanelSpec,
    parse_panel_spec,
    QH_PER_HOUR,
    E1Config,
    ResponseSpec,
    default_cohorts,
    generate,
    make_standin_panel,
)

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((PASS if ok else FAIL, name, detail))


def run_checks(panel: pd.DataFrame, cols: PanelSpec | None = None) -> None:
    cols = cols or PanelSpec()
    cfg = E1Config(censoring_rate=0.20, gamma=0.5,
                   response=ResponseSpec(shape="logistic"), seed=0)
    df, diag = generate(panel, cfg, cols)
    cohorts = default_cohorts()

    # --- 1. the observation model reproduces G exactly (up to the noise term)
    implied = df["A_true_mw"] * (1 - df["c_true"])
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.abs(df["G_obs_mw"] - implied) / np.maximum(implied, 1.0)
    check(
        "G = A x (1 - c) holds within the noise band",
        float(np.nanquantile(rel, 0.999)) < 6 * cfg.noise_sigma + 1e-6,
        f"p99.9 relative deviation = {float(np.nanquantile(rel, 0.999)):.4f}",
    )

    # --- 2. c is a proper fraction
    check("c_true in [0, 1]",
          bool(df["c_true"].between(0, 1).all()),
          f"min={df['c_true'].min():.4f} max={df['c_true'].max():.4f}")

    # --- 3. c = sum of w_k * s_k * r_k  (the decomposition is self-consistent)
    recon = sum(df[f"w_{c.name}"] * df[f"r_star_{c.name}"] for c in cohorts)
    check("c_true equals the cohort sum",
          bool(np.allclose(df["c_true"], np.clip(recon, 0, 1), atol=1e-9)),
          f"max abs diff = {float(np.abs(df['c_true'] - np.clip(recon,0,1)).max()):.2e}")

    # --- 4. I1: no censoring without an incentive (the placebo condition)
    no_exposure = sum(df[f"s_{c.name}"] for c in cohorts) == 0
    check("I1 -- c = 0 wherever no cohort is exposed",
          bool((df.loc[no_exposure, "c_true"] == 0).all()),
          f"{int(no_exposure.sum()):,} unexposed rows")

    # --- 5. no censoring when BOTH clocks are non-negative.
    # A quarter-hour with a positive price can still be censored if its hourly
    # mean is negative -- that is exactly how 51 works for pre-2025 cohorts,
    # and it is one of the things that makes the two cohorts separable.
    both_clocks_ok = (df["price_eur_mwh"] >= 0) & (df["price_hourly_mean_eur_mwh"] >= 0)
    check("no censoring when both price clocks are non-negative",
          bool((df.loc[both_clocks_ok, "c_true"] == 0).all()),
          f"{int(both_clocks_ok.sum()):,} rows clean on both clocks")

    qh_pos_but_censored = int(((df["price_eur_mwh"] >= 0) & (df["c_true"] > 0)).sum())
    check("hourly-clock censoring at a positive quarter-hour price exists",
          qh_pos_but_censored > 0,
          f"{qh_pos_but_censored:,} rows -- the identifying variation for I4")

    # --- 6. G is never above A (censoring can only remove output)
    excess = (df["G_obs_mw"] - df["A_true_mw"]) / np.maximum(df["A_true_mw"], 1.0)
    check("G does not exceed A beyond the noise term",
          float(excess.max()) < 6 * cfg.noise_sigma,
          f"max relative excess = {float(excess.max()):.4f}")

    # --- 7. I3: the true response is monotone in price depth
    mono_ok = True
    detail = []
    for c in cohorts:
        d = df.loc[df[f"s_{c.name}"] == 1, [f"depth_{c.name}_eur_mwh", f"r_star_{c.name}"]]
        if d.empty:
            continue
        binned = d.groupby(pd.qcut(d.iloc[:, 0], 8, duplicates="drop"),
                           observed=True).mean()
        diffs = np.diff(binned.iloc[:, 1].to_numpy())
        ok = bool((diffs >= -1e-9).all())
        mono_ok &= ok
        detail.append(f"{c.name}: {'monotone' if ok else 'NOT monotone'}")
    check("I3 -- r* non-decreasing in depth", mono_ok, "; ".join(detail))

    # --- 8. the hourly-clock cohort really does need its minimum run
    hourly = [c for c in cohorts if c.clock == "hourly"]
    ok, detail = True, []
    for c in hourly:
        exposed = df[f"s_{c.name}"] == 1
        runs = df.loc[exposed].groupby(
            [df["area"], (df["price_hourly_mean_eur_mwh"] >= 0).cumsum()]
        )["run_hours_hourly_clock"].max()
        bad = int((runs < c.min_run_hours).sum())
        ok &= bad == 0
        detail.append(f"{c.name}: {bad} runs shorter than {c.min_run_hours} h")
    check("hourly-clock exposure respects the minimum run length", ok, "; ".join(detail))

    # --- 9. I4: the two clocks genuinely disagree somewhere
    s_cols = [f"s_{c.name}" for c in cohorts]
    arr = df[s_cols].to_numpy()
    differ = arr.max(axis=1) != arr.min(axis=1)
    n_days = int(df.loc[differ, "day_local"].nunique())
    check("I4 -- cohort exposure differs on >= 10 event-days",
          n_days >= 10,
          f"{n_days} days with differing exposure ({int(differ.sum()):,} QHs)")

    # --- 10. ground truth is present and distinct from the observable
    truth_cols = ["A_true_mw", "c_true"] + [f"r_star_{c.name}" for c in cohorts]
    check("ground-truth columns present",
          all(c in df.columns for c in truth_cols),
          ", ".join(truth_cols))
    check("A and G actually differ on censored rows",
          bool((df.loc[df["censored"] == 1, "A_true_mw"]
                - df.loc[df["censored"] == 1, "G_obs_mw"]).abs().mean() > 1.0),
          f"mean |A - G| on censored = "
          f"{float((df.loc[df['censored']==1,'A_true_mw'] - df.loc[df['censored']==1,'G_obs_mw']).abs().mean()):.1f} MW")

    # --- 11. determinism: same seed, same data
    df2, _ = generate(panel, cfg, cols)
    check("same seed reproduces the dataset exactly",
          bool(df["G_obs_mw"].equals(df2["G_obs_mw"])))

    # --- 12. different seed gives a different dataset
    cfg3 = E1Config(censoring_rate=0.20, gamma=0.5,
                    response=ResponseSpec(shape="logistic"), seed=1)
    df3, _ = generate(panel, cfg3, cols)
    check("different seed gives different data",
          not bool(df["G_obs_mw"].equals(df3["G_obs_mw"])))

    # --- 13. confounding is monotone in gamma
    corrs = []
    for g in (0.0, 0.5, 1.0):
        _, d = generate(panel, E1Config(censoring_rate=0.20, gamma=g, seed=0), cols)
        corrs.append(d["confounding_corr_F_vs_c"])
    check("corr(F, c) increases with gamma",
          corrs[0] < corrs[1] < corrs[2],
          f"gamma 0/0.5/1 -> {corrs[0]:+.3f} / {corrs[1]:+.3f} / {corrs[2]:+.3f}")

    # --- 14. response shapes behave as specified
    means = {}
    for shape in ("step", "logistic", "half"):
        f, _ = generate(panel, E1Config(censoring_rate=0.20, seed=0,
                                        response=ResponseSpec(shape=shape)),  # type: ignore[arg-type]
                        cols)
        means[shape] = float(f.loc[f["censored"] == 1, "c_true"].mean())
    check("step > logistic > half in mean censoring depth",
          means["step"] > means["logistic"] > means["half"],
          " ".join(f"{k}={v:.3f}" for k, v in means.items()))

    # --- 15. the rate control is monotone and hits its targets
    hit = []
    for r in (0.05, 0.10, 0.20, 0.30, 0.40):
        _, d = generate(panel, E1Config(censoring_rate=r, gamma=0.0, seed=0), cols)
        hit.append((r, d["realised_rate"], d["rate_target_met"]))
    check("all five censoring rates reached within tolerance",
          all(m for _, _, m in hit),
          " ".join(f"{r:.2f}->{a:.3f}" for r, a, _ in hit))

    print(f"\nDiagnostics for the main cell (rate 0.20, gamma 0.5, logistic, seed 0):")
    for k, v in diag.items():
        print(f"  {k:<32} {v}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--panel")
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--cols", help="column mapping, e.g. "
                   "'timestamp=ts_utc_dt,actual_mw=act_wind_mw'")
    p.add_argument("--area", help="keep only this area before validating")
    a = p.parse_args()

    if not a.selftest and not a.panel:
        p.error("give --panel or --selftest")

    cols = parse_panel_spec(a.cols)
    panel = make_standin_panel() if a.selftest else pd.read_parquet(a.panel)
    if a.area:
        panel = panel.loc[panel[cols.area].astype(str) == a.area].copy()
        if panel.empty:
            p.error(f"no rows for area {a.area!r}")

    print(f"panel rows = {len(panel):,}   cols = {cols}")
    run_checks(panel, cols)

    print("\n" + "=" * 78)
    width = max(len(n) for _, n, _ in results)
    for status, name, detail in results:
        print(f"[{status}] {name:<{width}}  {detail}")
    n_fail = sum(1 for s, _, _ in results if s == FAIL)
    print("=" * 78)
    print(f"{len(results) - n_fail}/{len(results)} checks passed")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
