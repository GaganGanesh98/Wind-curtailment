#!/usr/bin/env python3
"""Validation suite for `src/censoring/synthetic.py`, the production E1 generator.

    python -m src.censoring.validate_synthetic
    python -m src.censoring.validate_synthetic --cohorts mastr

Ported from `archive/e1_validate.py`, which validated the superseded
`archive/e1_generator.py`. What changed in the port:

* **Check 6 deleted.** It asserted that quarter-hours with a non-negative price
  inside a negative hour MUST be censored. That is the symptom of the archived
  generator's section 51 misreading, so the assertion encoded the bug; a passing
  suite would have locked it in.
* **Replaced by its inverse** (check 5b below): no cohort may be exposed at a
  non-negative quarter-hour price, because `theta <= 0` always and
  `s = 1[p_qh < theta]`.
* **Two identification assertions added** from `identification.py`: `rank(s) == K`
  and no duplicated exposure columns. docs/11 showed both E1 generators passing the
  pre-registered I4 day count while large capacity shares were exactly collinear.

Everything else is carried over: the observation identity, c in [0, 1], the
cohort-sum decomposition, I1, I3 monotonicity, the hourly-clock minimum run, I4,
ground truth present and distinct, seed determinism, confounding monotone in gamma,
the three response shapes ordered, and all five censoring rates reached.

Run it before any modelling and after every change to the generator or the cohort
definitions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.censoring.cohorts import (  # noqa: E402
    HOUR_CLOCK, build_clock_features, exposure_differs_by_day, mastr_cohort_set,
    placeholder_cohort_set, theta_and_exposure, trigger_active,
)
from src.censoring.identification import (  # noqa: E402
    identification_diagnostics, merge_cohorts,
)
from src.censoring.synthetic import (  # noqa: E402
    R_SHAPES, SyntheticConfig, generate,
)

PASS, FAIL = "PASS", "FAIL"
RATES = (0.05, 0.10, 0.20, 0.30, 0.40)
results: list[tuple[str, str, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((PASS if ok else FAIL, name, detail))


def run_checks(cohorts, label: str) -> None:
    cfg = SyntheticConfig(area="DE", censoring_rate=0.20, gamma=0.5,
                          r_shape="logistic", seed=42)
    d = generate(cfg, cohorts)
    s, depth, r, c = d.s, d.depth, d.r_true, d.c_true
    w = cohorts.shares
    price = d.price_eur_mwh
    K, T = s.shape

    # --- 1. the observation model reproduces G (exactly, when noise is off)
    implied = d.a_true_mw * (1.0 - c)
    with np.errstate(divide="ignore", invalid="ignore"):
        rel = np.abs(d.g_obs_mw - implied) / np.maximum(implied, 1.0)
    band = 6 * cfg.observation_noise_mw / max(1.0, float(d.a_true_mw.mean())) + 1e-9
    check("G = A x (1 - c) holds within the noise band",
          float(np.nanquantile(rel, 0.999)) <= band,
          f"p99.9 relative deviation = {float(np.nanquantile(rel, 0.999)):.2e}, "
          f"band = {band:.2e} (observation_noise_mw = {cfg.observation_noise_mw})")

    # --- 2. c is a proper fraction
    check("c_true in [0, 1]", bool(((c >= 0) & (c <= 1)).all()),
          f"min={c.min():.4f} max={c.max():.4f}")

    # --- 3. c = sum_k w_k s_k r_k
    recon = (w[:, None] * s * r).sum(axis=0)
    check("c_true equals the cohort sum",
          bool(np.allclose(c, np.clip(recon, 0, 1), atol=1e-9)),
          f"max abs diff = {float(np.abs(c - np.clip(recon, 0, 1)).max()):.2e}")

    # --- 4. I1: no censoring without an incentive
    no_exp = s.max(axis=0) == 0
    check("I1 -- c = 0 wherever no cohort is exposed",
          bool((c[no_exp] == 0).all()), f"{int(no_exp.sum()):,} unexposed rows")

    # --- 5. no censoring when both price clocks are non-negative
    clock = build_clock_features(d.ts_utc_ns, price)
    both_ok = (price >= 0) & (clock.hour_mean_price >= 0)
    check("no censoring when both price clocks are non-negative",
          bool((c[both_ok] == 0).all()),
          f"{int(both_ok.sum()):,} rows clean on both clocks")

    # --- 5b. REPLACES the deleted check 6. theta <= 0 always, and exposure is
    #     decided on the quarter-hour price on BOTH clocks, so a non-negative
    #     quarter-hour price can never expose any cohort.
    nonneg = price >= 0
    n_bad = int(s[:, nonneg].sum())
    check("no cohort is exposed at a non-negative quarter-hour price",
          n_bad == 0,
          f"{n_bad} cohort-quarter-hours; max(theta) = {float(d.theta.max()):+.3f} "
          f"(must be <= 0); {int(((price >= 0) & (clock.hour_mean_price < 0)).sum()):,} "
          f"non-negative QH sit inside a negative hour and are correctly uncensored")

    # --- 6. G is never above A
    excess = (d.g_obs_mw - d.a_true_mw) / np.maximum(d.a_true_mw, 1.0)
    check("G does not exceed A beyond the noise term",
          float(excess.max()) <= band + 1e-12,
          f"max relative excess = {float(excess.max()):.2e}")

    # --- 7. I3: r* monotone in depth
    ok, det = True, []
    for i in range(K):
        on = s[i] > 0
        if on.sum() < 50:
            det.append(f"{cohorts.ids[i]}: only {int(on.sum())} exposed, skipped")
            continue
        dv, rv = depth[i][on], r[i][on]
        q = np.quantile(dv, np.linspace(0, 1, 9))
        q = np.unique(q)
        if q.size < 3:
            det.append(f"{cohorts.ids[i]}: depth near-constant, skipped")
            continue
        means = [rv[(dv >= q[b]) & (dv <= q[b + 1])].mean() for b in range(q.size - 1)]
        means = [m for m in means if np.isfinite(m)]
        good = bool((np.diff(means) >= -1e-9).all())
        ok &= good
        det.append(f"{cohorts.ids[i]}: {'monotone' if good else 'NOT monotone'}")
    check("I3 -- r* non-decreasing in depth", ok, "; ".join(det))

    # --- 8. the hourly-clock cohorts respect their minimum run
    #
    # Scoped to TRIGGER-ACTIVE quarter-hours, and that scope is the whole point.
    # An hour-clock cohort is also exposed when its trigger is NOT active, at
    # theta = -MP, simply because the price fell below the premium it stands to
    # lose; that is a rational switch-off carrying no run-length condition at all.
    # Section 51's run length governs only whether theta jumps to 0. The ported
    # assertion originally tested every exposed quarter-hour and failed on 1,211
    # rows of the 6 h cohort, every one of them trigger-inactive at theta = -17:
    # the generator was right and the assertion had inherited the archived
    # generator's semantics, where hourly exposure could only come via the trigger.
    ok, det = True, []
    for i, co in enumerate(cohorts):
        if co.clock != HOUR_CLOCK or not co.subject_to_s51:
            continue
        on = s[i] > 0
        act = trigger_active(co, clock)
        if not on.any():
            det.append(f"{co.cohort_id}: never exposed")
            continue
        bad = 0
        for y in np.unique(clock.berlin_year[on & act]):
            need = co.run_length_for_year(int(y))
            if need is None:
                continue
            sel = on & act & (clock.berlin_year == y)
            bad += int((clock.hour_run_length[sel] < need).sum())
        ok &= bad == 0
        n_prem = int((on & ~act).sum())
        det.append(f"{co.cohort_id}: {bad} trigger-active QH below its minimum run "
                   f"({n_prem:,} exposed on the premium instead)")
    check("trigger-active hourly exposure respects the minimum run length", ok,
          "; ".join(det) or "no hour-clock s51 cohorts")

    # --- 9. I4 (kept as an assertion, but no longer the gate -- see docs/12)
    nd, _ = exposure_differs_by_day(s, d.berlin_date)
    differ = s.max(axis=0) != s.min(axis=0)
    check("I4 -- cohort exposure differs on >= 10 event-days", nd >= 10,
          f"{nd} days with differing exposure ({int(differ.sum()):,} QHs)")

    # --- 9b. NEW: rank(s) == K
    rep = identification_diagnostics(s, cohorts.ids, list(w), depth, label=label)
    check("rank(s) == K (no exactly collinear cohorts)",
          rep.exposure.full_rank,
          f"rank {rep.exposure.rank} of {rep.exposure.k}; "
          f"collinear capacity {100 * rep.collinear_capacity_share:.1f}%; "
          + ("; ".join(" == ".join(g.members) for g in rep.groups) or "no duplicates"))

    # --- 9c. NEW: no duplicated exposure columns
    check("no two cohorts share an exposure vector", rep.unique_columns,
          "; ".join(f"{' == '.join(g.members)} ({g.kind})" for g in rep.groups)
          or "all columns unique")

    # --- 10. ground truth present and distinct from the observable
    check("ground-truth arrays present",
          all(getattr(d, a) is not None for a in
              ("a_true_mw", "c_true", "r_true", "s", "depth", "theta")),
          "a_true_mw, c_true, r_true, s, depth, theta")
    cen = c > 0
    gap = float(np.abs(d.a_true_mw[cen] - d.g_obs_mw[cen]).mean()) if cen.any() else 0.0
    check("A and G actually differ on censored rows", gap > 1.0,
          f"mean |A - G| on censored = {gap:.1f} MW over {int(cen.sum()):,} rows")

    # --- 11 / 12. determinism, and seed sensitivity
    d2 = generate(cfg, cohorts)
    check("same seed reproduces the dataset exactly",
          bool(np.array_equal(d.g_obs_mw, d2.g_obs_mw)))
    d3 = generate(SyntheticConfig(area="DE", censoring_rate=0.20, gamma=0.5,
                                  r_shape="logistic", seed=43), cohorts)
    check("different seed gives different data",
          not bool(np.array_equal(d.g_obs_mw, d3.g_obs_mw)))

    # --- 13. confounding monotone in gamma
    corrs = []
    for g in (0.0, 0.5, 1.0):
        dd = generate(SyntheticConfig(area="DE", censoring_rate=0.20, gamma=g,
                                      r_shape="logistic", seed=42), cohorts)
        corrs.append(float(np.corrcoef(dd.forecast_mw, dd.c_true)[0, 1]))
    check("corr(F, c) increases with gamma", corrs[0] < corrs[1] < corrs[2],
          f"gamma 0/0.5/1 -> {corrs[0]:+.3f} / {corrs[1]:+.3f} / {corrs[2]:+.3f}")

    # --- 14. response shapes ordered
    means = {}
    for shape in R_SHAPES:
        dd = generate(SyntheticConfig(area="DE", censoring_rate=0.20, gamma=0.0,
                                      r_shape=shape, seed=42), cohorts)
        on = dd.c_true > 0
        means[shape] = float(dd.c_true[on].mean()) if on.any() else 0.0
    # `half` here is a CONSTANT r* = r_half_level (0.5) whenever exposed -- the shape
    # built to hurt B4 (spec section 6, H2) -- not the archived generator's logistic
    # capped at 50%. So `half` sits ABOVE `logistic` at the depths this panel
    # produces, and the old "step > logistic > half" ordering is a property of the
    # other generator's parameterisation, not an invariant. What is invariant: step
    # is the most aggressive shape, and every shape is non-decreasing in depth
    # (asserted separately as I3).
    check("step is the most aggressive shape",
          means["step"] > means["logistic"] and means["step"] > means["half"],
          " ".join(f"{k}={v:.3f}" for k, v in means.items())
          + "  (half > logistic is expected: half is a flat "
            f"{cfg.r_half_level:.2f}, logistic is centred at "
            f"{cfg.r_depth_half_eur_mwh:.0f} EUR/MWh depth)")

    # --- 15. all five censoring rates reached
    hit, ok = [], True
    for rate in RATES:
        try:
            dd = generate(SyntheticConfig(area="DE", censoring_rate=rate, gamma=0.0,
                                          r_shape="logistic", seed=42), cohorts)
            got = float(dd.diagnostics.get("realised_negative_rate", float("nan")))
            met = abs(got - rate) <= 0.02
            hit.append(f"{rate:.2f}->{got:.3f}{'' if met else ' MISS'}")
            ok &= met
        except Exception as exc:                      # saturation shows up here
            hit.append(f"{rate:.2f}->{type(exc).__name__}")
            ok = False
    check("all five censoring rates reached within tolerance", ok, " ".join(hit))

    print(f"\nDiagnostics for the main cell "
          f"(rate 0.20, gamma 0.5, logistic, seed 42, {label}):")
    for k, v in d.diagnostics.items():
        if isinstance(v, dict):
            print(f"  {k:<32} " + ", ".join(f"{a}={b:.3f}" for a, b in v.items()))
        else:
            print(f"  {k:<32} {v}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cohorts", default="placeholder",
                    choices=["placeholder", "mastr"],
                    help="which cohort set to validate (default: placeholder)")
    ap.add_argument("--merge", action="store_true",
                    help="merge indistinguishable cohorts first (docs/12 step C), "
                         "so the identification assertions can be seen to clear")
    a = ap.parse_args()
    cohorts = (placeholder_cohort_set() if a.cohorts == "placeholder"
               else mastr_cohort_set("DE"))
    label = a.cohorts
    if a.merge:
        probe = generate(SyntheticConfig(area="DE", censoring_rate=0.20, gamma=0.5,
                                         r_shape="logistic", seed=42), cohorts)
        cohorts, _, gmap = merge_cohorts(
            cohorts, np.hstack([probe.s, probe.depth]), probe.theta,
            rule="exposure")
        label = f"{a.cohorts}+merged"
        n = sum(1 for g in gmap if g.is_merge)
        print(f"merged {n} group(s) on the realised (s, depth) block; "
              f"K is now {len(cohorts)}")
    print(f"validating synthetic.py with the {label} cohort set "
          f"({len(cohorts)} cohorts)")
    run_checks(cohorts, label)

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
