"""docs/22: the Hirth audit mapping is fixed, covers every checked claim and copies values."""

import csv

import pytest

from src.experiments import hirth_audit as ha


def _csv_rows():
    with ha.CLAIMS.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_only_checked_rows_are_mapped():
    checked = {r["claim_id"] for r in _csv_rows() if r["checked_by_me"].strip() == "yes"}
    assert {m["claim_id"] for m in ha.mapping()} == checked


def test_values_are_the_csv_strings():
    by_id = {r["claim_id"]: r for r in _csv_rows()}
    for m in ha.mapping():
        assert m["value"] == by_id[m["claim_id"]]["value"]
        assert m["unit"] == by_id[m["claim_id"]]["unit"]


def test_every_comparable_claim_has_a_band_and_kind():
    for m in ha.mapping():
        if m["comparable"] == "yes":
            assert m["band_key"] and m["kind"] in ("bounded", "plain number")
        else:
            assert m["kind"] == "" and m["reason"]


def test_unchecked_rows_never_appear(tmp_path, monkeypatch):
    rows = _csv_rows()
    rows[0] = {**rows[0], "checked_by_me": "no"}
    p = tmp_path / "claims.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    monkeypatch.setattr(ha, "CLAIMS", p)
    assert rows[0]["claim_id"] not in {m["claim_id"] for m in ha.mapping()}


def test_h1b_band_is_lambda2_band():
    assert ha.BANDS["below -50"].lo == -float("inf") and ha.BANDS["below -50"].hi == -50.0


def test_no_checked_row_stops(tmp_path, monkeypatch):
    p = tmp_path / "claims.csv"
    p.write_text("claim_id,checked_by_me\nX,no\n", encoding="utf-8")
    monkeypatch.setattr(ha, "CLAIMS", p)
    with pytest.raises(ValueError):
        ha.checked_claims()


def test_amendment1_classes():
    am = {m["claim_id"]: m for m in ha.amended_mapping()}
    shares = ha.period_shares()
    for cid, m in am.items():
        if m["comparable"] != "yes":
            assert m["class"] == ""
        elif m["period"] == "2025":
            assert m["class"] == "cross-period"
        elif m["period"] == "2022 to Oct 2026 pooled":
            assert m["class"] == ("cross-period" if shares[cid] > 0.5 else "main")
        else:
            assert m["class"] == "main"


def test_amendment1_threshold_is_the_informativeness_rule():
    assert ha.INFORMATIVE_WIDTH == 0.25
