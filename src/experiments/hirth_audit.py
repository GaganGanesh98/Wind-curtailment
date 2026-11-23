"""Post-hoc audit of Hirth (2026) against the method (docs/22, 23 Nov 2026).

Step 1 (this file as committed with docs/22): declarations only. The claim mapping, the
price bands, the bias grids and the verdict rule are fixed here and printed into
`docs/22_posthoc_hirth_audit_preregistration.md` as generated blocks, so the note and the
code that will run in step 2 cannot drift apart. Nothing in this file computes an
identified set.

Claims are read from `data/reference/hirth_2026_claims.csv`. Only rows with
`checked_by_me == "yes"` are used, and claim values are carried as the CSV's own strings.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CLAIMS = REPO_ROOT / "data" / "reference" / "hirth_2026_claims.csv"
OUT_DIR = REPO_ROOT / "artifacts" / "hirth_audit"
DATE = "23 Nov 2026"

# Bias grids (docs/10 and archive/docs/V0_preregistration.md), unchanged.
V2_STEP, V2_BMAX = 0.01, 0.15          # pre-registered V2 grid
FINE_STEP, FINE_BMAX = 0.0025, 0.06    # post-hoc fine grid of docs/10
NOT_DECIDABLE_WIDTH = 0.75             # doc 44's rule, as given (see docs/22)
MASKS = ("M0", "M1")                   # docs/11, unchanged


@dataclass(frozen=True)
class Band:
    """A price band on the quarter-hour day-ahead price, (lo, hi], as functionals.band_mean."""
    key: str
    lo: float
    hi: float

    def text(self) -> str:
        lo = "−∞" if math.isinf(self.lo) else _num(self.lo)
        return f"({lo}, {_num(self.hi)}]"


def _num(x: float) -> str:
    return f"−{abs(x):g}" if x < 0 else f"{x:g}"


# Hirth's band label (claims CSV `price_band`) -> the band the method uses.
BANDS = {
    "below -100": Band("le_m100", -math.inf, -100.0),
    "-100 to -50": Band("m100_m50", -100.0, -50.0),
    "-50 to -20": Band("m50_m20", -50.0, -20.0),
    "-20 to -10": Band("m20_m10", -20.0, -10.0),
    "-10 to 0": Band("m10_0", -10.0, 0.0),
    "below 0": Band("lt_0", -math.inf, 0.0),
    "below -50": Band("le_m50", -math.inf, -50.0),   # the band of λ₂
}
PLACEBO_BANDS = ("0 to 5 (placebo)", "above 5 (placebo)")

# Calendar overlap of Hirth's period with the Experiment 3 window (2025-10-01 to 2026-09-30).
PERIOD_OVERLAP = {
    "2022": "none",
    "2023": "none",
    "2024": "none",
    "2025": "partial, October to December 2025 only",
    "2026 (to Oct)": "partial, January to September 2026",
    "2022 to Oct 2026 pooled": "partial, the whole window lies inside Hirth's period",
}

QUANTITY = {
    "curtailment_rate": "band mean of ĉ (fleet switched-off share), new band-mean functional",
    "response_rate": "band mean of ĉ divided by band mean of the exposed share e",
    "exposure_rate": "band mean of the exposed share e, a plain number (no bounds)",
}


def checked_claims() -> list[dict]:
    """The claims file's checked rows, values kept as the CSV's strings."""
    if not CLAIMS.exists():
        raise FileNotFoundError(f"{CLAIMS} is missing; Prompt 1 stops (rule 2)")
    with CLAIMS.open(newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["checked_by_me"].strip() == "yes"]
    if not rows:
        raise ValueError("no claim has checked_by_me = yes; Prompt 1 stops (rule 2)")
    return rows


def claim_share(row: dict) -> float:
    """Hirth's value as a share of 1. Every checked row is in per cent."""
    if not row["unit"].startswith("%"):
        raise ValueError(f"{row['claim_id']}: unit {row['unit']!r} is not a per cent")
    return float(row["value"]) / 100.0


def map_claim(row: dict) -> dict:
    """The step 1 mapping of one checked claim: what it is compared with, or why not."""
    qt, band_label, period = row["quantity_type"], row["price_band"], row["period"]
    overlap = PERIOD_OVERLAP.get(period)
    base = {"claim_id": row["claim_id"], "quantity_type": qt, "period": period,
            "price_band": band_label, "value": row["value"], "unit": row["unit"],
            "scope_note": row["scope_note"], "kind": "", "band": "", "band_key": ""}
    if qt == "volume":
        return {**base, "comparable": "no", "reason": "volume, out of scope"}
    if overlap is None:
        raise ValueError(f"{row['claim_id']}: period {period!r} has no overlap entry")
    if overlap == "none":
        return {**base, "comparable": "no",
                "reason": "period does not overlap the Experiment 3 window"}
    if band_label in PLACEBO_BANDS:
        return {**base, "comparable": "no",
                "reason": ("price ≥ 0, where no cohort is exposed, so the method sets ĉ to 0 by "
                           "construction and nothing is identified to compare")}
    if band_label not in BANDS:
        raise ValueError(f"{row['claim_id']}: band {band_label!r} is not mapped")
    band = BANDS[band_label]
    kind = {"curtailment_rate": "bounded", "response_rate": "bounded",
            "exposure_rate": "plain number"}[qt]
    return {**base, "comparable": "yes", "kind": kind, "band": band.text(),
            "band_key": band.key, "quantity": QUANTITY[qt],
            "reason": f"period overlap {overlap}"}


def mapping() -> list[dict]:
    return [map_claim(r) for r in checked_claims()]


def first_fine_at_or_above(v: float) -> float:
    return math.ceil(round(v / FINE_STEP, 6)) * FINE_STEP


# ------------------------------------------------------------------ generated blocks
def _md(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def mapping_table() -> str:
    """docs/22: one row per checked claim."""
    rows = []
    for m in mapping():
        rows.append([m["claim_id"], m["quantity_type"].replace("_", " "), m["period"],
                     m["price_band"], f"{m['value']} {m['unit']}",
                     m["band"] or "—", m.get("quantity", "not comparable"), m["reason"]])
    return _md(["claim", "Hirth's quantity", "Hirth's period", "Hirth's band",
                "Hirth's value", "method band (quarter-hour price)", "matching quantity",
                "comparability"], rows)


def mapping_counts() -> str:
    m = mapping()
    n = len(m)
    b = sum(x["kind"] == "bounded" for x in m)
    p = sum(x["kind"] == "plain number" for x in m)
    return (f"- Checked claims: {n}. Compared with an identified set: {b}. Compared as a plain "
            f"number: {p}. Not comparable: {n - b - p}.")


def design_text() -> str:
    """docs/22: grids, the comparison bias and the masked variant's caveat, from artifacts."""
    import polars as pl
    from src.experiments.available_power_anchors import primary_h
    bias = abs(float(primary_h()["bias"]))
    rc = pl.read_csv(REPO_ROOT / "artifacts" / "available_power_estimate" / "redispatch_checks.csv",
                     infer_schema_length=None)
    unit = rc.filter(pl.col("check") == "unit_check").row(0, named=True)
    nb = first_fine_at_or_above(bias)
    return "\n".join([
        f"- Bias grids. Pre-registered V2 grid: b from −{V2_BMAX:.2f} to {V2_BMAX:.2f} in steps "
        f"of {V2_STEP:.2f}, hull S_B over |b| ≤ B for B = 0 to {V2_BMAX:.2f}. Post-hoc fine grid "
        f"(docs/10): b from −{FINE_BMAX:.2f} to {FINE_BMAX:.2f} in steps of {FINE_STEP:.4f}.",
        f"- Comparison bias: {bias:.4f}, the size of H's bias on the quality-assured series, "
        f"Experiment 3 window, price ≥ 0 (`h_anchor_by_series.csv`, the H anchor). On the fine "
        f"grid the verdict at that bias is read at B = {nb:.4f}, the first allowance at or above "
        f"it, as in docs/10.",
        f"- Not decidable: interval width above {NOT_DECIDABLE_WIDTH:.2f}. The widest possible "
        f"range is 1 for every compared quantity, so this is a width above "
        f"{NOT_DECIDABLE_WIDTH:.2f}.",
        f"- Masked variants M0 and M1, caveat: the redispatch export's unit check (mean MW × "
        f"duration against MWh) fails for {int(unit['count']):,} of {int(unit['of']):,} renewable "
        f"reduction measures (`redispatch_checks.csv`). It is open.",
    ])
