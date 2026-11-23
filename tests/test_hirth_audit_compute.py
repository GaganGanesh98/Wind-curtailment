"""docs/22 step 2: the audit's functionals, reproduction against λ₂, and the verdict rule."""

import csv

import numpy as np
import pytest

from src.experiments import hirth_audit as ha
from src.method import functionals as fx
from src.method import hirth_functionals as hf
from src.method.bounds import build_design

E3 = ha.REPO_ROOT / "artifacts" / "exp3_german_application"
have_cells = pytest.mark.skipif(not ha.CELLS.exists(), reason="step 2 not run yet")


def _toy_design(seed=0):
    rng = np.random.default_rng(seed)
    T, K = 400, 3
    price = rng.uniform(-120, 10, T)
    theta = np.vstack([np.zeros(T), np.full(T, -5.0), np.full(T, -30.0)])
    s = (price[None, :] < theta).astype(float)
    depth = np.maximum(0.0, theta - price[None, :]) * s
    d = build_design(s, depth, np.array([0.5, 0.3, 0.2]), cohort_ids=("a", "b", "c"))
    return d, price, rng.uniform(1000, 9000, T)


def test_row_sum_is_exposed_share():
    d, price, _ = _toy_design()
    s_rows = d.X.sum(axis=1)
    assert np.all(s_rows > 0) and np.all(s_rows <= 1 + 1e-12)


def test_unweighted_curtailment_is_band_mean():
    d, price, _ = _toy_design()
    a = hf.curtailment(d, price, -np.inf, -50.0)
    b = fx.band_mean(d, price, -np.inf, -50.0)
    assert np.array_equal(a["lam"], b["lam"])


@pytest.mark.parametrize("bias", [-0.15, -0.0326, 0.05])
@pytest.mark.parametrize("fn", [hf.curtailment, hf.response])
def test_weighted_unchanged_under_constant_bias(fn, bias):
    d, price, h = _toy_design()
    a = fn(d, price, -100.0, -20.0, h)
    b = fn(d, price, -100.0, -20.0, h * np.exp(bias))
    np.testing.assert_allclose(a["lam"], b["lam"], rtol=1e-12, atol=0)


def test_weighted_exposure_unchanged_under_constant_bias():
    d, price, h = _toy_design()
    assert hf.exposure(d, price, -np.inf, 0.0, h)["value"] == pytest.approx(
        hf.exposure(d, price, -np.inf, 0.0, h * np.exp(0.1))["value"], rel=1e-12)


def test_response_is_curtailment_over_exposure():
    d, price, _ = _toy_design()
    r = np.random.default_rng(1).uniform(0, 1, d.n_cols)
    m = (price[d.rows] > -np.inf) & (price[d.rows] <= 0.0)
    want = (d.X[m] @ r).mean() / d.X[m].sum(axis=1).mean()
    assert hf.response(d, price, -np.inf, 0.0)["lam"] @ r == pytest.approx(want, rel=1e-12)


@pytest.mark.parametrize("lo,hi,v,cls,want", [
    (0.30, 0.40, 0.35, "main", "supported"), (0.30, 0.40, 0.35, "cross-period", "consistent"),
    (0.30, 0.40, 0.25, "main", "outside"), (0.30, 0.55, 0.35, "main", "not decidable"),
    (0.30, 0.5499, 0.20, "main", "outside")])
def test_verdict_rule(lo, hi, v, cls, want):
    assert ha.verdict_at(lo, hi, v, cls) == want


# ----------------------------------------------------------- artifacts of the full run
def _cells(**kw):
    with ha.CELLS.open(newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if all(r[k] == v for k, v in kw.items())]


def _exp3(path, **kw):
    with path.open(newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if all(r.get(k) == v for k, v in kw.items())]


@have_cells
@pytest.mark.parametrize("source,variant,step", [
    ("bias_robust_full_window_cells.csv", "headline", 0.01),
    ("posthoc_breakdown_fine_grid.csv", "headline", 0.0025),
    ("redispatch_sensitivity_cells.csv", "M0", 0.01),
    ("redispatch_sensitivity_cells.csv", "M1", 0.01)])
def test_h1b_reproduces_lambda2(source, variant, step):
    """H1b's band is λ₂'s: under the headline ĉ and each mask its range equals Experiment 3's."""
    kw = {"lam": "L2"} if variant == "headline" else {"lam": "L2", "mask": variant}
    want = {round(float(r["b"]), 4): (float(r["lo"]), float(r["hi"]))
            for r in _exp3(E3 / source, **kw)}
    got = {round(float(r["b"]), 4): (float(r["lo"]), float(r["hi"]))
           for r in _cells(variant=variant, functional="curtailment_rate|le_m50|unweighted")}
    assert want, f"no λ₂ rows in {source}"
    for b, (lo, hi) in want.items():
        assert b in got, f"b {b} missing from the audit cells"
        assert got[b] == (lo, hi), f"{source} b {b}: {got[b]} != {(lo, hi)}"


@have_cells
def test_claim_values_are_the_csv_strings():
    by_id = {r["claim_id"]: r for r in ha.checked_claims()}
    with ha.VERDICTS.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            assert r["hirth_value"] == by_id[r["claim_id"]]["value"]
            assert r["hirth_unit"] == by_id[r["claim_id"]]["unit"]


@have_cells
def test_unchecked_rows_never_in_artifacts():
    checked = {r["claim_id"] for r in ha.checked_claims()}
    for path in (ha.VERDICTS, ha.RANGES, ha.MAPPING_CSV):
        with path.open(newline="", encoding="utf-8") as f:
            assert {r["claim_id"] for r in csv.DictReader(f)} <= checked


@have_cells
def test_every_range_verdict_follows_the_rule():
    shares = {r["claim_id"]: ha.claim_share(r) for r in ha.checked_claims()}
    with ha.RANGES.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            want = ha.verdict_at(float(r["lower"]), float(r["upper"]), shares[r["claim_id"]],
                                 r["class"])
            assert r["verdict"] == want
            assert (r["informative"] == "True") == (float(r["upper"]) - float(r["lower"]) < 0.25)


@have_cells
def test_cross_period_never_supported_or_contradicted():
    with ha.VERDICTS.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["class"] == "cross-period":
                assert "supported" not in (r["verdict_B0"], r["verdict_at_comparison_bias"])
                assert r["claim_level"] != "contradicted"


def test_exposed_share_is_one_below_minus_50():
    """docs/23: H1a and H1b share a range because e = 1 wherever price <= -50."""
    import csv
    p = ha.EXPOSURE
    if not p.exists():
        pytest.skip("exposure_check.csv not written")
    rows = [r for r in csv.DictReader(p.open()) if r["band"] == "le_m50"]
    assert {r["variant"] for r in rows} == set(ha.VARIANTS)
    for r in rows:
        assert float(r["min_e"]) == 1.0 and int(r["n_qh_e_below_1"]) == 0
    v = {(r["claim_id"], r["variant"], r["weighting"]): r
         for r in csv.DictReader(ha.VERDICTS.open())}
    for var in ha.VARIANTS:
        for wt in ("unweighted", "weighted"):
            a, b = v[("H1a", var, wt)], v[("H1b", var, wt)]
            assert a["lower_B0"] == b["lower_B0"] and a["upper_B0"] == b["upper_B0"]
