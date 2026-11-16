"""T-B guards. These run before the experiment, because they decide whether it counts.

The five the supervisor named, plus the behavioural test for guard 3 — the one that
decides whether the experiment is honest. Guard 3 is not testable by reading the code
(any method *could* peek), so it is tested by corrupting the unselected days and
asserting the tuning decision does not move.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.censoring.run_tb import (
    SHAPES,
    event_days,
    fit_mask,
    nested_day_subsets,
    overall,
    score_verdict,
    sign_test,
    sign_test_threshold,
)
from src.censoring.tb_methods import inner_cv_folds


# ------------------------------------------------------------------ the threshold


def test_sign_test_threshold_45_is_30():
    """The pre-registered bar, Amendment 3 A3.1."""
    assert sign_test_threshold(45) == 30
    assert sign_test_threshold(27) == 20
    assert sign_test_threshold(9) == 8


def test_threshold_is_the_smallest_significant_count():
    from scipy.stats import binomtest

    for n in (9, 15, 27, 45):
        k = sign_test_threshold(n)
        assert binomtest(k, n, 0.5, alternative="two-sided").pvalue < 0.05
        assert binomtest(k - 1, n, 0.5, alternative="two-sided").pvalue >= 0.05


# --------------------------------------------------------------------- nesting


def test_subsets_are_nested_20_inside_50_inside_100():
    days = np.array([f"2026-04-{d:02d}" for d in range(1, 29)]
                    + [f"2026-05-{d:02d}" for d in range(1, 29)])
    sub = nested_day_subsets(days, (20, 50, 100, None))
    assert set(sub[20]) <= set(sub[50]) <= set(sub[100]) <= set(sub[None])
    assert len(sub[20]) == 20 and len(sub[50]) == 50
    assert len(sub[100]) == len(days)          # fewer available than requested
    assert len(sub[None]) == len(days)


def test_subsets_are_reproducible_across_separate_runs():
    """The primary and secondary passes are separate runs; nesting must survive that."""
    days = np.array([f"2026-04-{d:02d}" for d in range(1, 26)])
    assert np.array_equal(nested_day_subsets(days, (10,))[10],
                          nested_day_subsets(days, (10, 20))[10])


def test_fit_mask_selects_only_censored_qhs_on_selected_days():
    dates = np.repeat(["d1", "d2", "d3"], 4)
    censored = np.array([1, 1, 0, 0, 1, 0, 0, 0, 1, 1, 1, 0], dtype=bool)
    m = fit_mask(censored, dates, np.array(["d1", "d3"]))
    assert m.tolist() == [True, True, False, False,
                          False, False, False, False,
                          True, True, True, False]
    assert event_days(censored, dates).tolist() == ["d1", "d2", "d3"]


# ------------------------------------------- guard 1: a failure must not vanish


def test_a_failing_method_scores_a_loss_and_does_not_vanish():
    """The bug found on review: isfinite() dropped exactly the cells M2 found hard."""
    rows = []
    for i, (m2_failed, rival_val) in enumerate([(True, 0.05)] * 3
                                               + [(False, 0.05)] * 2):
        for name, failed, val in (("M2", m2_failed, 0.01),
                                  ("B3-CV", False, rival_val)):
            rows.append({"r_shape": "logistic", "method": name,
                         "n_event_days_requested": 50,
                         "censoring_rate": 0.1, "gamma": 0.0, "seed": 45 + i,
                         "failed": failed, "int_abs_r": val})
    v = [x for x in score_verdict(rows, 50)
         if x["r_shape"] == "logistic" and x["rival"] == "B3-CV"][0]
    assert v["n_effective"] == 5, "failed cells must stay in the comparison"
    assert v["n_m2_failed"] == 3
    assert v["wins"] == 2, "M2 wins only where it did not fail"


def test_both_failing_is_excluded_as_uninformative():
    rows = [{"r_shape": "step", "method": m, "n_event_days_requested": 50,
             "censoring_rate": 0.1, "gamma": 0.0, "seed": 45,
             "failed": True, "int_abs_r": float("nan")}
            for m in ("M2", "B3-CV")]
    v = [x for x in score_verdict(rows, 50)
         if x["r_shape"] == "step" and x["rival"] == "B3-CV"][0]
    assert v["n_effective"] == 0 and v["n_nonfinite"] == 1


# ------------------------------------------------- guard 4: ties move the bar


def test_a_tie_is_excluded_and_the_threshold_moves():
    no_ties = sign_test(np.array([-1.0] * 9))
    assert no_ties["n_effective"] == 9 and no_ties["threshold"] == 8
    with_ties = sign_test(np.array([-1.0] * 7 + [0.0, 0.0]))
    assert with_ties["n_ties"] == 2
    assert with_ties["n_effective"] == 7
    assert with_ties["threshold"] == sign_test_threshold(7) == 7
    assert with_ties["pass"] is True
    # and a tie never counts as a win
    assert sign_test(np.array([0.0] * 9))["wins"] == 0


def test_the_half_clause_gates_on_b3cv_only_as_pre_registered():
    """Amendment 3 0.3 names B3-CV alone in the half clause; B6 is reported."""
    def mk(shape, rival, passed, loses):
        return {"n_event_days": 50, "r_shape": shape, "rival": rival,
                "pass": passed, "loses_significantly": loses}
    verdicts = [mk(s, r, True, False) for s in ("logistic", "step")
                for r in ("B3-CV", "B6")]
    verdicts += [mk("half", "B3-CV", False, False),
                 mk("half", "B6", False, True)]      # B6 loses on half
    out = overall(verdicts, 50)
    assert out["VERDICT"] == "PASS", "B6 losing on half must NOT gate"
    assert out["half_reported_only"]["B6"] is False


# ------------------------------------------------ guard 3: the honesty guard


def test_inner_cv_folds_never_leave_the_fit_mask():
    dates = np.repeat([f"d{i}" for i in range(20)], 5)
    mask = np.zeros(100, dtype=bool)
    mask[:30] = True                      # days d0..d5 only
    seen = set()
    for tr, va in inner_cv_folds(dates, mask):
        seen |= set(tr.tolist()) | set(va.tolist())
        assert set(np.unique(dates[tr])).isdisjoint(np.unique(dates[va]))
    assert seen <= set(np.flatnonzero(mask).tolist())


def test_inner_cv_sees_only_selected_days_even_when_others_are_corrupted():
    """GUARD 3, behaviourally. Corrupt the unselected days; tuning must not move.

    This is the test that decides whether T-B is honest. A method whose inner CV
    touched days outside the mask would choose a different hyperparameter once those
    days are replaced with garbage, and would fail here.
    """
    from src.method.exposure import mastr_cohort_set
    from src.method.stage_a.reservation_depth_model import fit_shared_stage_a
    from src.method.stage_a.latent_model import TrainConfig
    from src.method.synthetic import SyntheticConfig, generate
    from src.censoring.tb_methods import fit_b3_cv

    data = generate(SyntheticConfig(censoring_rate=0.20, gamma=0.0, r_shape="logistic",
                                    seed=45), cohorts=mastr_cohort_set("DE"))
    shared = fit_shared_stage_a(data, cfg=TrainConfig(), check=False)
    days = event_days(data.censored, data.berlin_date)
    keep = nested_day_subsets(days, (20,))[20]
    mask = fit_mask(data.censored, data.berlin_date, keep)

    clean = fit_b3_cv(data, mask, shared)

    # Corrupt everything OUTSIDE the selected censored quarter-hours.
    import copy
    dirty = copy.copy(data)
    g = data.g_obs_mw.copy()
    rng = np.random.default_rng(0)
    g[~mask] = rng.uniform(0, 1e5, int((~mask).sum()))
    dirty.g_obs_mw = g
    corrupted = fit_b3_cv(dirty, mask, shared)

    assert corrupted["n_bins"] == clean["n_bins"], (
        "B3-CV's bin choice moved when unselected days were corrupted: its inner CV "
        "is seeing data the other methods were denied, and T-B would be void")


# ----------------------- Amendment 5 A5.2: the shared array, asserted bit-identical


def test_shared_stage_a_is_bit_identical_across_every_response_method():
    """One array per cell, reused by M2, B3-CV, B3@8, B3-H and B6 — not re-fitted.

    If any method quietly built its own A-hat, T-B would no longer be isolating the
    response model, which is the single thing it exists to measure.
    """
    from src.censoring.run_tb import MethodSpec, score_cell
    from src.method.synthetic import SyntheticConfig
    from src.method.exposure import mastr_cohort_set

    seen: dict[str, np.ndarray] = {}
    names = ["M2", "B3-CV", "B6", "B3@8", "B3-H"]

    def recorder(nm):
        def _fit(data, mask, shared_a):
            seen[nm] = np.asarray(shared_a.a_hat).copy()
            return {"a_hat": shared_a.a_hat}
        return _fit

    specs = [MethodSpec(n, recorder(n), lambda f, d, g: np.zeros_like(g))
             for n in names]
    sentinel = {"calls": 0}

    class _A:
        def __init__(self, arr): self.a_hat = arr

    def shared(data):
        sentinel["calls"] += 1
        rng = np.random.default_rng(7)
        return _A(rng.normal(5000.0, 500.0, data.forecast_mw.size))

    cfg = SyntheticConfig(censoring_rate=0.10, gamma=0.0, r_shape="step", seed=45)
    score_cell(cfg, specs, (20, 50), shared, mastr_cohort_set("DE"))

    assert sentinel["calls"] == 1, "stage A must be fitted ONCE per cell, not per level"
    ref = seen[names[0]]
    for n in names[1:]:
        assert np.array_equal(seen[n], ref), f"{n} did not receive the shared array"
        assert not np.shares_memory(seen[n], np.empty(0))


def test_b2_does_not_consume_the_shared_array():
    """A5.2: B2 keeps its own fit. Rewiring it would void the no-harm claim.

    Asserted behaviourally — B2's a_hat must DIFFER from the shared array — rather
    than by inspecting its signature, which would not catch a quiet rewiring.
    """
    from src.method.stage_a.baselines import fit_b2
    from src.method.exposure import mastr_cohort_set
    from src.method.stage_a.reservation_depth_model import fit_shared_stage_a
    from src.method.stage_a.latent_model import TrainConfig
    from src.method.synthetic import SyntheticConfig, generate

    d = generate(SyntheticConfig(censoring_rate=0.10, gamma=0.0, r_shape="step",
                                 seed=45), cohorts=mastr_cohort_set("DE"))
    shared = fit_shared_stage_a(d, cfg=TrainConfig(), check=False)
    b2 = fit_b2(d, TrainConfig())["a_hat"]
    assert not np.array_equal(b2, shared.a_hat)
    assert np.abs(b2 - shared.a_hat).mean() > 1.0


def test_b2_is_absent_from_tb_specs_because_it_has_no_response_curve():
    """Recorded so its absence reads as a decision, not an omission.

    Amendment 3 0.2 lists B2 among the methods, but T-B's metric is
    integrated |r_hat - r*| and B2 estimates A only — it has no response to score.
    B2 belongs to T-A's criterion (c), not to T-B.
    """
    from src.censoring.tb_methods import build_specs

    assert "B2" not in {s.name for s in build_specs()}


# ----------------------------------------------- the --report-only CSV round trip

def _tb_row(shape, method, seed, value, n_requested=50, failed=False):
    """A row shaped like `run()` builds them: real int, real bool, real float."""
    return {
        "censoring_rate": 0.10, "gamma": 0.0, "r_shape": shape, "seed": seed,
        "n_event_days_requested": n_requested, "n_event_days_used": n_requested,
        "method": method, "int_abs_r": value, "failed": failed, "error": "",
    }


def _as_csv_dictreader_would(rows, tmp_path):
    """Round-trip through CSV so every value comes back a string, as DictReader gives."""
    import csv
    p = tmp_path / "rt.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(p, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_score_verdict_is_identical_live_and_from_csv(tmp_path):
    """The --report-only bug. `score_verdict` kept its own copy of the metric that
    compared `n_event_days_requested` against an int and tested `failed` for plain
    truthiness. Live rows carry an int and a bool, so it worked; `csv.DictReader`
    yields "50" and "False", so the filter matched nothing, every cell was dropped,
    and the table printed nan means with 0 wins -- which `overall` then reported as a
    FAIL on a run that had PASSED. One `_metric` now serves both paths.
    """
    from src.censoring.run_tb import score_verdict

    live = []
    for seed in (45, 46, 47, 48, 49):
        live.append(_tb_row("step", "M2", seed, 0.001))
        live.append(_tb_row("step", "B3-CV", seed, 0.009))   # M2 wins every cell
    from_csv = _as_csv_dictreader_would(live, tmp_path)

    v_live = [v for v in score_verdict(live, 50) if v["rival"] == "B3-CV"
              and v["r_shape"] == "step"][0]
    v_csv = [v for v in score_verdict(from_csv, 50) if v["rival"] == "B3-CV"
             and v["r_shape"] == "step"][0]

    assert v_live["n_effective"] == 5, "the live path must see all five cells"
    assert v_csv["n_effective"] == 5, "the CSV path dropped every cell (the bug)"
    assert v_csv["wins"] == v_live["wins"] == 5
    assert v_csv["m2_mean"] == pytest.approx(v_live["m2_mean"])
    assert v_csv["rival_mean"] == pytest.approx(v_live["rival_mean"])


def test_a_failed_fit_from_csv_counts_as_a_loss_not_as_a_success(tmp_path):
    """`failed` arrives as the string "False", which is truthy. Reading it that way
    marked every successful fit as failed; reading it as a plain bool would mark every
    failed one as a success. Both directions are wrong, so the string is parsed."""
    from src.censoring.run_tb import score_verdict

    live = []
    for seed in (45, 46, 47, 48, 49):
        live.append(_tb_row("step", "M2", seed, 0.001))
        live.append(_tb_row("step", "B3-CV", seed, float("nan"), failed=True))
    from_csv = _as_csv_dictreader_would(live, tmp_path)

    v = [x for x in score_verdict(from_csv, 50)
         if x["rival"] == "B3-CV" and x["r_shape"] == "step"][0]
    assert v["n_rival_failed"] == 5, "the rival's failures must be counted as failures"
    assert v["wins"] == 5, "a failed rival loses every cell; M2 wins all five"


def test_the_level_filter_matches_across_types(tmp_path):
    """"50" and 50 must select the same rows, and a different level must select none."""
    from src.censoring.run_tb import _metric

    live = [_tb_row("step", "M2", s, 0.001) for s in (45, 46)]
    from_csv = _as_csv_dictreader_would(live, tmp_path)

    assert len(_metric(live, 50, "step", "M2")) == 2
    assert len(_metric(from_csv, 50, "step", "M2")) == 2
    assert len(_metric(from_csv, 20, "step", "M2")) == 0
