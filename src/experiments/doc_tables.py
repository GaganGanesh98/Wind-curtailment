"""Results tables embedded in the active docs, generated from the committed artifacts.

    python -m src.experiments.doc_tables            # print every table
    python -m src.experiments.doc_tables --write    # refresh the marked blocks in docs/

Each table sits in its doc between `<!-- generated:NAME -->` and `<!-- /generated -->`.
`tests/test_reported_numbers.py` regenerates every block and requires it to match the doc
exactly, so a hand edit to a generated figure fails the suite.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import polars as pl

from src.method.read_results import load

REPO_ROOT = Path(__file__).resolve().parents[2]
ART = REPO_ROOT / "artifacts"
AP, E1, E2, E3 = (ART / "available_power_estimate", ART / "exp1_known_truth_validation",
                  ART / "exp2_bias_robustness_validation", ART / "exp3_german_application")
SYM = {"L1": "λ₁", "L2": "λ₂", "L3": "λ₃", "L4": "λ₄", "L5": "λ₅", "L6": "λ₆", "L7": "λ₇"}
QTY = {"L1": "fleet response at depth (−20, −5] €/MWh", "L2": "fleet response at depth ≤ −50 €/MWh",
       "L3": "pre-2016 cohort response", "L4": "merged θ ≡ 0 group (collinear pair)",
       "L5": "counterfactual energy, GWh (threshold moved to 0)", "L6": "cohort contrast λ₃ − λ₄",
       "L7": "one member of the collinear pair"}


def _md(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def available_power_anchors() -> str:
    a = pl.read_csv(AP / "error_anchors.csv", infer_schema_length=None).with_columns(
        *(pl.col(c).cast(pl.Float64, strict=False) for c in ("sigma", "sigma_lo", "sigma_hi", "bias")))
    h = a.filter((pl.col("anchor") == "H") & pl.col("area").str.starts_with("DE excl. TenneT")
                 & (pl.col("sample") == "price >= 0")).row(0, named=True)
    t = a.filter((pl.col("anchor") == "T") & (pl.col("area") == "DE") & (pl.col("series") == "onshore")
                 & (pl.col("sample") == "price >= 0")).row(0, named=True)
    rows = [[n, r["area"], f"{r['sigma']:.4f}", f"[{r['sigma_lo']:.4f}, {r['sigma_hi']:.4f}]", f"{r['bias']:+.4f}"]
            for n, r in (("projection H (quality-assured)", h), ("day-ahead forecast F", t))]
    return _md(["estimate", "area", "σ", "95% interval", "bias"], rows)


def available_power_adds_back() -> str:
    v = pl.read_csv(AP / "adds_back_verdicts.csv", infer_schema_length=0).filter(
        pl.col("series") == "quality-assured")
    order = {"50Hertz+Amprion+TransnetBW": 0, "50Hertz": 1, "Amprion": 2, "TransnetBW": 3, "TenneT": 4}
    rows = []
    for r in sorted(v.iter_rows(named=True), key=lambda r: order.get(r["area"], 9)):
        area = r["area"] + (" (excluded from the aggregate)" if r["area"] == "TenneT" else "")
        rows.append([area, f"{float(r['D']):+.4f}", f"[{float(r['D_lo']):+.4f}, {float(r['D_hi']):+.4f}]",
                     r["verdict"]])
    return _md(["area", "D", "95% interval", "verdict"], rows)


def exp1_coverage() -> str:
    rows = []
    for name, f in (("exact potential", "exact_potential_cells.csv"),
                    ("estimated potential", "estimated_potential_cells.csv")):
        d = load(E1 / f).filter(pl.col("cov").is_not_null())
        rows.append([name, f"{int(d['cov'].sum())}/{d.height}", f"{float(d['cov'].mean()):.3f}"])
    q = (pl.read_csv(E1 / "noise_dial_summary.csv").filter(pl.col("lam") == "L1")
           .sort(["noise", "sigma"], descending=[True, False]))
    for r in q.iter_rows(named=True):
        kind = "i.i.d." if r["noise"] == "iid" else "AR(1)"
        rows.append([f"noise dial, {kind} σ = {r['sigma']:g}", "—", f"{r['level_coverage']:.3f}"])
    return _md(["setting", "covered / scored", "coverage"], rows)


def exp1_informative() -> str:
    q = pl.read_csv(E1 / "noise_dial_summary.csv").filter(pl.col("noise") == "iid")
    sig = (0.0, 0.066, 0.18, 0.35)
    rows = []
    for lam in SYM:
        cells = []
        for s in sig:
            r = q.filter((pl.col("lam") == lam) & (pl.col("sigma") == s)).row(0, named=True)
            cells.append(f"{r['n_informative']}/{r['n_cells']}")
        rows.append([SYM[lam]] + cells)
    return _md(["functional", "σ = 0", "σ = 0.066 (H)", "σ = 0.18 (F)", "σ = 0.35"], rows)


def exp2_bias_dial() -> str:
    c = pl.read_csv(E2 / "bias_dial_coverage.csv").filter(
        ~((pl.col("dial") == "q2b") & (pl.col("sigma") == 0.0))).sort(["sigma", "b"])
    rows = [[f"{r['sigma']:g}", f"{r['b']:+.3f}", f"{r['n_covered']}/{r['n_scored']}",
             f"{r['level_coverage']:.3f}", str(r["n_informative_and_missed"])] for r in c.iter_rows(named=True)]
    return _md(["σ", "bias b", "covered", "coverage", "informative and missed"], rows)


def exp2_bias_robust() -> str:
    c = pl.read_csv(E2 / "bias_robust_coverage.csv").sort(["b_true", "B"])
    rows = []
    for r in c.iter_rows(named=True):
        applies = str(r["criterion_applies"]).lower() == "true"
        rows.append([f"{r['B']:.2f}", f"{r['b_true']:+.3f}", f"{r['n_covered']}/{r['n_scored']}",
                     f"{r['coverage']:.3f}", "PASS" if applies and str(r["passes"]).lower() == "true"
                     else ("FAIL" if applies else "—")])
    return _md(["budget B", "true bias", "covered", "coverage", "criterion"], rows)


def _fmt(v: float, lam: str) -> str:
    places = 1 if lam == "L5" else 3
    return f"{round(v, places) + 0.0:.{places}f}"


def exp3_results() -> str:
    t = pl.read_csv(E3 / "results_table.csv", infer_schema_length=None).filter(pl.col("kind") == "quantity")
    bd = {r["lam"]: r for r in pl.read_csv(E3 / "breakdown_points.csv", infer_schema_length=0).iter_rows(named=True)}
    rows = []
    for r in t.iter_rows(named=True):
        lam = r["lam"]
        interval = (f"[{_fmt(r['window_lo'], lam)}, {_fmt(r['window_hi'], lam)}]"
                    if r["window_lo"] is not None else "undefined")
        reading = r["window_reading"] or "—"
        breakdown = (f"{bd[lam]['breakdown_B']}" if lam in bd else "—")
        verdict = r["verdict"] + (f"; {r['sub_label']}" if r["sub_label"] else "")
        rows.append([SYM[lam], QTY[lam], interval, reading, breakdown,
                     f"{r['real_H_k']}/{r['real_H_n']}", verdict])
    return _md(["quantity", "what it is", "full-window interval, H", "robust reading",
                "breakdown bias B", "informative months, H", "monthly verdict (C0 rule)"], rows)


TABLES = {"available_power_anchors": available_power_anchors,
          "available_power_adds_back": available_power_adds_back,
          "exp1_coverage": exp1_coverage, "exp1_informative": exp1_informative,
          "exp2_bias_dial": exp2_bias_dial, "exp2_bias_robust": exp2_bias_robust,
          "exp3_results": exp3_results}
BLOCK = re.compile(r"(<!-- generated:([a-z0-9_]+) -->\n)(.*?)(<!-- /generated -->)", re.S)


def refresh(text: str) -> str:
    return BLOCK.sub(lambda m: m.group(1) + TABLES[m.group(2)]() + "\n" + m.group(4), text)


def blocks(text: str) -> dict[str, str]:
    """The tables currently embedded in a doc, by name."""
    return {m.group(2): m.group(3) for m in BLOCK.finditer(text)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    if not ap.parse_args().write:
        for k, f in TABLES.items():
            print(f"\n{k}\n{f()}")
        return
    for p in sorted((REPO_ROOT / "docs").glob("*.md")) + [REPO_ROOT / "README.md"]:
        t = p.read_text(encoding="utf-8")
        u = refresh(t)
        if u != t:
            p.write_text(u, encoding="utf-8")
            print("refreshed", p.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
