"""Experiment 3 in use: the data each quantity needs, and the policy question it answers.

    python -m src.experiments.exp3_policy_use          # writes both parquet artifacts

Derived only from stored artifacts; nothing is re-fitted. Writes

  artifacts/exp3_data_requirement.parquet  per quantity: the highest synthetic noise level σ at
      which it is informative (Experiment 1 noise dial, best case), H's measured σ, the largest
      bias allowance B at which its real-data range is informative, and the breakdown point of
      its reading
  artifacts/exp3_policy_use.parquet        per quantity, plus one row for the post-February-2025
      cohort: the policy question, the EEG rule rows, the current range, the verdict and the
      data requirement

The tables in `docs/06b_policy_use_and_data_requirement.md` are generated from these by
`src/experiments/doc_tables.py`, and figure 13 by `src/figures.py`.

Rules, all reused rather than restated:
- σ: informative in at least half the synthetic cells, the C0 rule `exp3_results_table._highest`
  applies to Experiment 1's i.i.d. noise dial. This is what gives "σ ≤ 0.033" in docs/06.
- B: the hull over |b| ≤ B of the committed real-data cells, informative when its width is
  below 0.25 of the logical maximum (Q0 section 5), as in `bias_robust_summary`.
- Verdict: from the breakdown point of each reading (V0 section 3) against H's measured bias.
  Robust when the reading still holds at the first grid budget at or above |bias|;
  fragile when it breaks at or below that; not identifiable when the quantity has no reading.
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import polars as pl

from src.experiments.exp3_results_table import GRID, _highest, _q1

REPO_ROOT = Path(__file__).resolve().parents[2]
ART = REPO_ROOT / "artifacts"
E3 = ART / "exp3_german_application"
DATA_REQ = ART / "exp3_data_requirement.parquet"
POLICY = ART / "exp3_policy_use.parquet"
RULES_CSV = REPO_ROOT / "data" / "reference" / "eeg_negative_price_rules.csv"

LAMS = ("L1", "L2", "L3", "L4", "L5", "L6", "L7")
SYM = {"L1": "λ₁", "L2": "λ₂", "L3": "λ₃", "L4": "λ₄", "L5": "λ₅", "L6": "λ₆", "L7": "λ₇"}
STEP = 0.01
INFORMATIVE_FRACTION = 0.25
NOT_ID_PERFECT = "not identifiable with perfect data"
NOT_NARROW = "range not narrow on real data at B = 0"
ROBUST, FRAGILE, NOT_ID = "robust", "fragile", "not identifiable"
#: the only quantity not informative in half the synthetic cells even with the exact potential
PERFECT_FAIL = "L7"

#: cohort ids per quantity, as `real_panel` defines them (L3_COHORT, COLLINEAR_PAIR, L5_COHORT,
#: L7_COHORT); the fleet quantities weigh every cohort by its exposure.
FLEET = "all cohorts"
COHORTS = {"L1": FLEET, "L2": FLEET, "L3": ("pre2016_in_support_no_s51",),
           "L4": ("out_of_support", "post_feb2025_qh"), "L5": ("wind2023_feb2025_staircase",),
           "L6": ("pre2016_in_support_no_s51", "out_of_support", "post_feb2025_qh"),
           "L7": ("out_of_support",)}
POST_FEB_2025 = "post_feb2025_qh"

QUESTION = {
    "L1": "At moderately negative prices (−20 to −5 €/MWh), what share of exposed wind capacity "
          "switches off?",
    "L2": "At deeply negative prices (−50 €/MWh or lower), what share of exposed wind capacity "
          "switches off?",
    "L3": "Do plants commissioned before 2016, which no negative-price rule reaches, switch off?",
    "L4": "Do plants that earn nothing at any negative price (out of support, or under the "
          "post-February-2025 rule) switch off, taken together?",
    "L5": "How much more energy would the 2023 to February 2025 cohort hold back if it lost "
          "support at every negative price?",
    "L6": "Do the pre-2016 plants respond differently from the plants that earn nothing at any "
          "negative price?",
    "L7": "Do out-of-support plants switch off, on their own?",
    "post": "Do plants under the post-February-2025 rule, which lose support in every negative "
            "quarter-hour, switch off?",
}


# --------------------------------------------------------------------------- inputs

def _cells() -> pl.DataFrame:
    return (pl.read_csv(E3 / "bias_robust_full_window_cells.csv", infer_schema_length=0)
              .with_columns(*(pl.col(c).cast(pl.Float64) for c in
                              ("b", "lo", "hi", "l5_energy_full_gwh")),
                            (pl.col("feasible") == "True").alias("feasible"))
              .with_columns(pl.col("b").round(2)))


def _breakdowns() -> dict[str, dict]:
    return {r["lam"]: r for r in pl.read_csv(E3 / "breakdown_points.csv",
                                             infer_schema_length=0).iter_rows(named=True)}


def h_anchor() -> dict:
    """H's measured σ and bias for Experiment 3: the quality-assured series on its own window,
    price >= 0 (h_anchor_by_series.csv, primary row). Until 22 Nov 2026 this read the
    operational row of error_anchors.csv (σ 0.0660, bias −0.0472) by mistake."""
    from src.experiments.available_power_anchors import primary_h
    r = primary_h()
    return {"sigma": float(r["sigma"]), "bias": float(r["bias"])}


def first_grid_at_or_above(x: float) -> float:
    """The first B on the 0.01 grid at or above x (0.0326 -> 0.04)."""
    return float(np.ceil(round(x / STEP, 6)) * STEP)


def rule_ids(lam_or_post: str) -> list[str]:
    from src.method.exposure import MASTR_COHORT_SPEC
    c = (COHORTS[lam_or_post] if lam_or_post != "post" else (POST_FEB_2025,))
    if c == FLEET:
        return sorted({v["rule_id"] for v in MASTR_COHORT_SPEC.values()})
    return sorted({MASTR_COHORT_SPEC[k]["rule_id"] for k in c})


def rules() -> dict[str, dict]:
    with open(RULES_CSV, newline="", encoding="utf-8") as fh:
        return {r["rule_id"]: r for r in csv.DictReader(fh)}


def collinear_members() -> list[str]:
    """The exactly collinear cohorts on the real full window, as the committed cells record."""
    m = _cells()["exact_collinear_members"].unique().to_list()
    if len(m) != 1:
        raise ValueError(f"expected one collinear group in the cells, found {m}")
    return m[0].split("+")


# ----------------------------------------------------------------------- table 1

def largest_informative_B(cells: pl.DataFrame, lam: str) -> float | None:
    """Largest B on the 0.01 grid with every smaller B also informative; None if not at B = 0."""
    a = cells.filter((pl.col("lam") == lam) & pl.col("feasible"))
    if lam == "L6":
        mx = 2.0
    elif lam == "L5":
        mx = float(a.filter(pl.col("b") == 0.0)["l5_energy_full_gwh"][0])
    else:
        mx = 1.0
    bmax = float(cells["b"].abs().max())
    best = None
    for i in range(int(round(bmax / STEP)) + 1):
        B = round(i * STEP, 2)
        q = a.filter(pl.col("b").abs() <= B + 1e-9)
        if float(q["hi"].max()) - float(q["lo"].min()) < INFORMATIVE_FRACTION * mx:
            best = B
        else:
            break
    return best


def data_requirement() -> pl.DataFrame:
    q1, cells, bd, h = _q1(), _cells(), _breakdowns(), h_anchor()
    rows = []
    for lam in LAMS:
        sig_txt, sig = _highest(q1, lam)
        top = sig is not None and sig == GRID[-1]
        b_inf = largest_informative_B(cells, lam)
        b = bd.get(lam)
        if lam == PERFECT_FAIL:
            sig_label = b_label = NOT_ID_PERFECT
        else:
            sig_label = (f"≥ {sig:g} (top of grid)" if top else f"≤ {sig:g}")
            b_label = NOT_NARROW if b_inf is None else f"{b_inf:.2f}"
        if b is None:
            bd_label, reading = "no reading", ""
        else:
            bd_label, reading = b["breakdown_B"], b["reading"]
        if lam == PERFECT_FAIL:
            needs = NOT_ID_PERFECT
        else:
            parts = []
            if b is not None:
                parts.append(f"its reading ({reading}) needs a bias below {bd_label}"
                             if not bd_label.startswith(">") else
                             f"its reading ({reading}) survives every tested bias ({bd_label})")
            if b_inf is not None:
                parts.append(f"its range stays narrow for a bias up to {b_inf:.2f}")
            if not top:
                parts.append(f"a narrow range needs σ ≤ {sig:g} (synthetic, best case)")
            needs = "; ".join(parts)
        rows.append({"lam": lam, "quantity": SYM[lam],
                     "sigma_informative": sig, "sigma_top_of_grid": top,
                     "sigma_label": sig_label, "sigma_rule_text": sig_txt,
                     "sigma_H": h["sigma"], "bias_H": h["bias"],
                     "largest_informative_B": b_inf, "largest_informative_B_label": b_label,
                     "reading": reading, "breakdown_B": bd_label,
                     "needs": needs})
    return pl.DataFrame(rows, infer_schema_length=None)


# ----------------------------------------------------------------------- table 2

def verdict(breakdown_B: str | None, bias: float) -> str:
    """V0 breakdown against |bias|: robust if the reading holds at the first grid B >= |bias|."""
    if breakdown_B in (None, "", "no reading"):
        return NOT_ID
    need = first_grid_at_or_above(abs(bias))
    if breakdown_B.startswith(">"):
        return ROBUST
    return ROBUST if float(breakdown_B) > need + 1e-9 else FRAGILE


def _range(lam: str) -> str:
    t = pl.read_csv(E3 / "results_table.csv", infer_schema_length=None).filter(
        (pl.col("kind") == "quantity") & (pl.col("lam") == lam)).row(0, named=True)
    p = 1 if lam == "L5" else 3
    f = lambda v: f"{round(float(v), p) + 0.0:.{p}f}"                       # noqa: E731
    return f"[{f(t['window_lo'])}, {f(t['window_hi'])}]" + (" GWh" if lam == "L5" else "")


def policy_use() -> pl.DataFrame:
    req = {r["lam"]: r for r in data_requirement().iter_rows(named=True)}
    rr, h = rules(), h_anchor()
    rows = []
    for key in LAMS + ("post",):
        ids = rule_ids(key)
        if key == "post":
            members = collinear_members()
            assert POST_FEB_2025 in members, members
            other = [m for m in members if m != POST_FEB_2025]
            rows.append({
                "row": "post-Feb-2025 cohort", "lam": "", "question": QUESTION["post"],
                "cohorts": POST_FEB_2025, "rule_ids": "|".join(ids),
                "legal_basis": " || ".join(rr[i]["legal_basis"] for i in ids),
                "range": "none", "breakdown_B": "", "verdict": NOT_ID,
                "data_requirement": (
                    "No quantity identifies this cohort. It is exactly collinear with "
                    f"{' and '.join(other)} on the real window (same exposure in every "
                    "quarter-hour) and enters only λ₄, merged with it, which has no reading."),
            })
            continue
        r = req[key]
        c = COHORTS[key]
        rows.append({
            "row": SYM[key], "lam": key, "question": QUESTION[key],
            "cohorts": c if c == FLEET else "+".join(c), "rule_ids": "|".join(ids),
            "legal_basis": " || ".join(rr[i]["legal_basis"] for i in ids),
            "range": _range(key), "breakdown_B": r["breakdown_B"],
            "verdict": verdict(r["breakdown_B"], h["bias"]),
            "data_requirement": r["needs"],
        })
    return pl.DataFrame(rows, infer_schema_length=None)


def main() -> None:
    d = data_requirement()
    d.write_parquet(DATA_REQ)
    p = policy_use()
    p.write_parquet(POLICY)
    for r in d.iter_rows(named=True):
        print(f"{r['quantity']}: σ {r['sigma_label']:<26} B {r['largest_informative_B_label']:<40}"
              f" breakdown {r['breakdown_B']:<10} {r['needs']}")
    for r in p.iter_rows(named=True):
        print(f"{r['row']:<22} {r['verdict']:<17} {r['range']}")
    print(f"wrote {DATA_REQ}\nwrote {POLICY}")


if __name__ == "__main__":
    main()
