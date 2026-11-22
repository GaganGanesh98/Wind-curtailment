"""The data-requirement and policy-use tables (docs/06b) say what the artifacts say.

    pytest tests/test_exp3_policy_use.py -q

The numbers in docs/06b's generated tables are also checked cell for cell by
tests/test_reported_numbers.py (docs/06b is an active doc there, so demo/run_demo.sh step 5
checks them).
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest

from src.experiments import exp3_policy_use as pu

REPO_ROOT = Path(__file__).resolve().parents[1]
E3 = REPO_ROOT / "artifacts" / "exp3_german_application"


@pytest.fixture(scope="module")
def req() -> dict[str, dict]:
    return {r["lam"]: r for r in pl.read_parquet(pu.DATA_REQ).iter_rows(named=True)}


@pytest.fixture(scope="module")
def pol() -> pl.DataFrame:
    return pl.read_parquet(pu.POLICY)


def test_table1_reproduces_the_3_3_percent_for_lambda4_and_lambda5(req):
    """σ ≤ 0.033 comes out of noise_dial_summary.csv, not typed in."""
    q1 = pl.read_csv(REPO_ROOT / "artifacts" / "exp1_known_truth_validation"
                     / "noise_dial_summary.csv").filter(pl.col("noise") == "iid")
    for lam in ("L4", "L5"):
        assert req[lam]["sigma_informative"] == 0.033
        assert req[lam]["sigma_label"] == "≤ 0.033"
        rows = q1.filter(pl.col("lam") == lam).sort("sigma")
        ok = [r["sigma"] for r in rows.iter_rows(named=True) if r["n_informative"] >= r["n_cells"] / 2]
        assert max(ok) == 0.033
        # and it is the figure docs/06 quotes from results_table.csv
        t = pl.read_csv(E3 / "results_table.csv", infer_schema_length=None).filter(
            (pl.col("kind") == "quantity") & (pl.col("lam") == lam))
        assert "σ ≤ 0.033" in t["sub_label"][0]


def test_every_verdict_matches_the_breakdown_points(pol):
    bd = {r["lam"]: r["breakdown_B"] for r in
          pl.read_csv(E3 / "breakdown_points.csv", infer_schema_length=0).iter_rows(named=True)}
    bias = abs(pu.h_anchor()["bias"])
    assert abs(bias - 0.0472) < 5e-5
    rows = pol.filter(pl.col("lam") != "")
    assert rows.height == 7
    for r in rows.iter_rows(named=True):
        b = bd.get(r["lam"])
        if b is None:
            want = "not identifiable"
        elif b.startswith(">"):
            want = "robust"
        else:
            # the reading must still hold at B = 0.05, the first grid budget >= 0.0472
            want = "robust" if float(b) > 0.05 + 1e-9 else "fragile"
        assert r["verdict"] == want, r["lam"]
        assert r["breakdown_B"] == (b if b is not None else "no reading"), r["lam"]
    assert dict(zip(rows["lam"], rows["verdict"])) == {
        "L1": "fragile", "L2": "robust", "L3": "robust", "L4": "not identifiable",
        "L5": "not identifiable", "L6": "fragile", "L7": "not identifiable"}


def test_labels_follow_the_agreed_wording(req):
    assert req["L7"]["sigma_label"] == pu.NOT_ID_PERFECT
    assert req["L7"]["largest_informative_B_label"] == pu.NOT_ID_PERFECT
    for lam in ("L2", "L3", "L4", "L5", "L6"):
        assert req[lam]["largest_informative_B_label"] == pu.NOT_NARROW, lam
        assert req[lam]["sigma_label"] != pu.NOT_ID_PERFECT, lam
    assert req["L1"]["largest_informative_B_label"] == "0.03"


def test_largest_informative_B_agrees_with_committed_intervals(req):
    """λ₁'s B from the raw cells equals the committed hull file: informative at 0.03, not 0.04."""
    iv = pl.read_csv(E3 / "bias_robust_full_window_intervals.csv").filter(pl.col("lam") == "L1")
    ok = iv.filter(pl.col("width") < 0.25)["B"].to_list()
    assert max(ok) == req["L1"]["largest_informative_B"] == 0.03


def test_h_sigma_is_the_measured_anchor(req):
    a = pu.h_anchor()
    assert round(a["sigma"], 3) == 0.066
    assert all(r["sigma_H"] == a["sigma"] for r in req.values())


def test_post_feb_2025_row_says_no_quantity_identifies_it(pol):
    r = pol.filter(pl.col("row") == "post-Feb-2025 cohort").row(0, named=True)
    assert r["verdict"] == "not identifiable" and r["rule_ids"] == "R09"
    assert r["data_requirement"].startswith("No quantity identifies this cohort")
    assert "post_feb2025_qh" in pu.collinear_members()
    # no quantity is defined on this cohort alone
    assert all(pu.COHORTS[lam] != ("post_feb2025_qh",) for lam in pu.LAMS)


def test_policy_rows_carry_the_rule_tables_legal_source(pol):
    rr = pu.rules()
    for r in pol.iter_rows(named=True):
        ids = r["rule_ids"].split("|")
        assert r["legal_basis"] == " || ".join(rr[i]["legal_basis"] for i in ids)


def test_stored_artifacts_equal_a_fresh_rebuild():
    for path, f in ((pu.DATA_REQ, pu.data_requirement), (pu.POLICY, pu.policy_use)):
        stored, fresh = pl.read_parquet(path), f()
        assert stored.columns == fresh.columns
        assert stored.equals(fresh), path.name


def test_figure_13_data_matches_committed_csv():
    from src import figures as mf
    committed = pl.read_csv(REPO_ROOT / "figures" / "13_data_requirement_data.csv")
    fresh = pl.read_csv(mf.data_requirement_data().write_csv().encode())
    assert fresh.columns == committed.columns and fresh.height == committed.height
    for c in fresh.columns:
        a, b = fresh[c], committed[c]
        if a.dtype.is_float() or b.dtype.is_float():
            assert ((a.cast(pl.Float64) - b.cast(pl.Float64)).abs().fill_null(0) <= 1e-9).all(), c
        else:
            assert a.cast(pl.String).to_list() == b.cast(pl.String).to_list(), c
