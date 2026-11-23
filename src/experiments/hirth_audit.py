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


# ------------------------------------------------------------------ Amendment 1 (23 Nov 2026)
# Written before any audit range was computed. The step 1 blocks above stay as committed.
INFORMATIVE_WIDTH = 0.25               # the pre-registered rule; replaces NOT_DECIDABLE_WIDTH
CROSS_PERIOD_ALWAYS = ("2025",)        # Hirth's 2025: the window's 2025 negative QHs are October only
CROSS_PERIOD_IF_MOSTLY_BEFORE = ("2022 to Oct 2026 pooled",)
PERIOD_SHARES = OUT_DIR / "period_shares.csv"
WINDOW_END = "2026-09-30"


def _hirth_hours(row: dict) -> float:
    import re
    m = re.search(r"([\d,]+) hours", row["quote_or_paraphrase"])
    if m is None:
        raise ValueError(f"{row['claim_id']}: no hour count in the claim text")
    return float(m.group(1).replace(",", ""))


def write_period_shares() -> Path:
    """Share of Hirth's band hours that fall before the window, for the pooled rows.

    Hirth's hours per band come from the claim text (Table 3). The hours inside the window, and
    after it up to the panel's last day, are this sample's negative-price quarter-hours in the
    band divided by 4. That counts quarter-hour prices, not Hirth's hourly prices, so the share
    is an approximation; it is a count of inputs, not a result.
    """
    import numpy as np
    from src.method import real_panel as rp
    p = rp.load_panel(rp.THREE_AREA, "H")
    price, bdate, keep = p["price"], p["bdate"], p["keep"]
    after = bdate > WINDOW_END
    rows = []
    for r in checked_claims():
        if r["period"] not in CROSS_PERIOD_IF_MOSTLY_BEFORE or r["price_band"] not in BANDS:
            continue
        b = BANDS[r["price_band"]]
        m = (price > b.lo) & (price <= b.hi) & (price < 0)
        hh = _hirth_hours(r)
        win, aft = float((m & keep).sum()) / 4.0, float((m & after).sum()) / 4.0
        rows.append({"claim_id": r["claim_id"], "price_band": r["price_band"], "hirth_hours": hh,
                     "window_hours_approx": win, "after_window_hours_approx": aft,
                     "share_before_window": 1.0 - (win + aft) / hh})
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with PERIOD_SHARES.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    return PERIOD_SHARES


def period_shares() -> dict[str, float]:
    with PERIOD_SHARES.open(newline="", encoding="utf-8") as f:
        return {r["claim_id"]: float(r["share_before_window"]) for r in csv.DictReader(f)}


def claim_class(m: dict) -> str:
    """'main', 'cross-period' or '' (not comparable), by Amendment 1."""
    if m["comparable"] != "yes":
        return ""
    if m["period"] in CROSS_PERIOD_ALWAYS:
        return "cross-period"
    if m["period"] in CROSS_PERIOD_IF_MOSTLY_BEFORE:
        return "cross-period" if period_shares()[m["claim_id"]] > 0.5 else "main"
    return "main"


def amended_mapping() -> list[dict]:
    return [{**m, "class": claim_class(m)} for m in mapping()]


def amendment_shares_table() -> str:
    rows = []
    with PERIOD_SHARES.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            s = float(r["share_before_window"])
            rows.append([r["claim_id"], r["price_band"], f"{float(r['hirth_hours']):,.0f}",
                         f"{float(r['window_hours_approx']):,.2f}",
                         f"{float(r['after_window_hours_approx']):,.2f}", f"{s:.3f}",
                         "cross-period" if s > 0.5 else "main"])
    return _md(["claim", "Hirth's band", "Hirth's hours", "hours in the window (QH ÷ 4)",
                "hours after the window (QH ÷ 4)", "share before the window", "class"], rows)


def amendment_class_lines() -> str:
    am = amended_mapping()
    def ids(cls, kind):
        return ", ".join(m["claim_id"] for m in am if m["class"] == cls and m["kind"] == kind) or "none"
    return "\n".join([
        f"- Main class, bounded: {ids('main', 'bounded')}. Plain number: {ids('main', 'plain number')}.",
        f"- Cross-period class, bounded: {ids('cross-period', 'bounded')}. Plain number: "
        f"{ids('cross-period', 'plain number')}.",
        f"- Not decidable, corrected: a range is not decidable when it is not informative, that is "
        f"a width of {INFORMATIVE_WIDTH:.2f} or more of the widest possible range (1 for every "
        f"compared quantity).",
    ])


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


# ------------------------------------------------------------------ step 2: compute
VARIANTS = ("headline", "M0", "M1")
CELLS = OUT_DIR / "claim_cells.csv"
RANGES = OUT_DIR / "claim_ranges.csv"
VERDICTS = OUT_DIR / "claim_verdicts.csv"
MAPPING_CSV = OUT_DIR / "claim_mapping.csv"
COMMAND = "python -m src.experiments.hirth_audit --run"


def v2_grid() -> list[float]:
    k = int(round(V2_BMAX / V2_STEP))
    return [round(i * V2_STEP, 2) for i in range(-k, k + 1)]


def fine_grid() -> list[float]:
    k = int(round(FINE_BMAX / FINE_STEP))
    return [round(i * FINE_STEP, 4) for i in range(-k, k + 1)]


def b_union() -> list[float]:
    return sorted({round(b, 4) for b in v2_grid() + fine_grid()})


def functionals_needed() -> list[tuple[str, str, str]]:
    """(functional key, band key, quantity type) for every compared claim, both weightings."""
    out = {}
    for m in amended_mapping():
        if m["comparable"] != "yes":
            continue
        for wt in ("unweighted", "weighted"):
            out[f"{m['quantity_type']}|{m['band_key']}|{wt}"] = (m["band_key"], m["quantity_type"], wt)
    return [(k, *v) for k, v in sorted(out.items())]


def _band_by_key(key: str) -> Band:
    return next(b for b in BANDS.values() if b.key == key)


def arm_cells(panel: dict, keep, b: float, variant: str, head: str) -> list[dict]:
    """One (variant, b) refit: run_arm's own design, point fit and ε, then the audit's
    functionals. Nothing inside the identified set differs from Experiment 3."""
    import numpy as np
    from src.method import hirth_functionals as hf
    from src.method import functionals as fx
    from src.method.bounds import (build_design, compress_rows, epsilon_from_bootstrap,
                                   identified_set, point_fit)
    f = np.asarray(panel["f"], dtype=float) * np.exp(b)
    price, g, bdate = panel["price"][keep], panel["g"][keep], panel["bdate"][keep]
    f = f[keep]
    theta = panel["theta_for"]("main")[:, keep]
    s = (price[None, :] < theta).astype(float)
    depth = np.maximum(0.0, theta - price[None, :]) * s
    runlen = panel["runlen"][:, keep]
    c_hat_full = 1.0 - g / np.maximum(f, 1e-9)
    design = build_design(s, depth, panel["shares"], runlen, cohort_ids=panel["ids"])
    rows = design.rows
    c_hat = c_hat_full[rows]
    comp = compress_rows(design.X, c_hat)
    pf = point_fit(design, c_hat, comp)
    eps = epsilon_from_bootstrap(design, c_hat, bdate[rows], pf["r"])["eps"]
    p_rows = price[rows]
    out = []
    for fkey, band_key, qt, wt in functionals_needed():
        band = _band_by_key(band_key)
        weight = f if wt == "weighted" else None
        m = (p_rows > band.lo) & (p_rows <= band.hi)
        base = {"variant": variant, "b": b, "functional": fkey, "band": band_key,
                "quantity_type": qt, "weighting": wt, "eps": eps,
                "n_qh": int(m.sum()), "n_event_days": int(np.unique(bdate[rows][m]).size),
                "git_head": head}
        if qt == "exposure_rate":
            e = hf.exposure(design, price, band.lo, band.hi, weight)
            out.append({**base, "lo": e["value"], "hi": e["value"], "feasible": True,
                        "defined": e["defined"]})
            continue
        spec = (hf.curtailment if qt == "curtailment_rate" else hf.response)(
            design, price, band.lo, band.hi, weight)
        if not spec["defined"]:
            out.append({**base, "lo": float("nan"), "hi": float("nan"), "feasible": False,
                        "defined": False})
            continue
        iv = identified_set(design, c_hat, spec["lam"], eps, comp)
        out.append({**base, "lo": iv["lo"], "hi": iv["hi"], "feasible": iv["feasible"],
                    "defined": True})
    return out


def run(variants=VARIANTS, bs: list[float] | None = None, out: Path = CELLS) -> Path:
    """Every (variant, b) refit, one raw row per functional. Long: see COMMAND."""
    import time
    from src.method.bias_robust import redispatch_keep
    from src.method.potential_error import git_head
    from src.method.real_panel import THREE_AREA, load_panel
    bs = b_union() if bs is None else bs
    panel = load_panel(THREE_AREA, "H")
    head = git_head()
    out.parent.mkdir(parents=True, exist_ok=True)
    fh = writer = None
    try:
        for v in variants:
            keep = panel["keep"] if v == "headline" else panel["keep"] & redispatch_keep(panel, v)
            for b in bs:
                t0 = time.perf_counter()
                rows = arm_cells(panel, keep, b, v, head)
                if writer is None:
                    fh = open(out, "w", newline="", encoding="utf-8")
                    writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
                    writer.writeheader()
                writer.writerows(rows)
                fh.flush()
                print(f"{v:<8} b {b:+.4f}  {time.perf_counter() - t0:5.1f}s", flush=True)
    finally:
        if fh is not None:
            fh.close()
    return out


ARM_MIN_EVENT_DAYS = 20               # docs/11's arm rule for masked variants


def verdict_at(lo: float, hi: float, v: float, cls: str) -> str:
    """Amendment 1 order: not decidable, then supported (consistent), then outside."""
    if not (hi - lo < INFORMATIVE_WIDTH):
        return "not decidable"
    if lo <= v <= hi:
        return "consistent" if cls == "cross-period" else "supported"
    return "outside"


def _hull(cells: list[dict], B: float) -> tuple[float, float] | None:
    q = [c for c in cells if abs(c["b"]) <= B + 1e-9 and c["feasible"]]
    if not q:
        return None
    return min(c["lo"] for c in q), max(c["hi"] for c in q)


def _load_cells(path: Path = CELLS) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["b"] = round(float(r["b"]), 4)
        r["lo"], r["hi"] = float(r["lo"]), float(r["hi"])
        r["feasible"] = r["feasible"] == "True" and r["defined"] == "True"
        r["n_qh"], r["n_event_days"] = int(r["n_qh"]), int(r["n_event_days"])
    return rows


def _write(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def summarise(cells_path: Path = CELLS) -> None:
    """claim_mapping.csv, claim_ranges.csv and claim_verdicts.csv from the raw cells."""
    cells = _load_cells(cells_path)
    am = amended_mapping()
    _write(MAPPING_CSV, [{k: m.get(k, "") for k in
                          ("claim_id", "quantity_type", "period", "price_band", "value", "unit",
                           "scope_note", "comparable", "kind", "class", "band", "band_key",
                           "reason")} for m in am])
    grids = {"V2 0.01": [round(i * V2_STEP, 2) for i in range(int(round(V2_BMAX / V2_STEP)) + 1)],
             "fine 0.0025": [round(i * FINE_STEP, 4) for i in range(int(round(FINE_BMAX / FINE_STEP)) + 1)]}
    on_grid = {"V2 0.01": set(v2_grid()), "fine 0.0025": set(fine_grid())}
    comp_B = first_fine_at_or_above(abs(float(__import__(
        "src.experiments.available_power_anchors", fromlist=["primary_h"]).primary_h()["bias"])))
    present = [v for v in VARIANTS if any(c["variant"] == v for c in cells)]
    arm_days = {v: max((c["n_event_days"] for c in cells if c["variant"] == v
                        and c["band"] == "lt_0" and c["b"] == 0.0), default=0)
                for v in present}
    ranges, verdicts = [], []
    for m in am:
        if m["comparable"] != "yes":
            verdicts.append({"claim_id": m["claim_id"], "class": "", "variant": "",
                             "weighting": "", "hirth_value": m["value"], "hirth_unit": m["unit"],
                             "verdict_B0": "not comparable", "verdict_at_comparison_bias": "",
                             "reason": m["reason"]})
            continue
        v = claim_share(m)
        for var in present:
            for wt in ("unweighted", "weighted"):
                fkey = f"{m['quantity_type']}|{m['band_key']}|{wt}"
                cc = [c for c in cells if c["variant"] == var and c["functional"] == fkey]
                if not cc:
                    raise ValueError(f"no cells for {fkey} {var}; run step 2 first")
                c0 = next(c for c in cc if c["b"] == 0.0)
                row = {"claim_id": m["claim_id"], "class": m["class"], "variant": var,
                       "weighting": wt, "hirth_value": m["value"], "hirth_unit": m["unit"],
                       "n_qh": c0["n_qh"], "n_event_days": c0["n_event_days"],
                       "arm_event_days": arm_days[var]}
                if m["kind"] == "plain number":
                    verdicts.append({**row, "method_value": c0["lo"],
                                     "difference": c0["lo"] - v, "verdict_B0": "plain number",
                                     "verdict_at_comparison_bias": "plain number"})
                    continue
                seqs = {}
                for gname, budgets in grids.items():
                    gc = [c for c in cc if c["b"] in on_grid[gname]]
                    seq = []
                    for B in budgets:
                        h = _hull(gc, B)
                        if h is None:
                            continue
                        lo, hi = h
                        vd = verdict_at(lo, hi, v, m["class"])
                        seq.append((B, lo, hi, vd))
                        ranges.append({"claim_id": m["claim_id"], "class": m["class"],
                                       "variant": var, "weighting": wt, "grid": gname, "B": B,
                                       "lower": lo, "upper": hi,
                                       "informative": hi - lo < INFORMATIVE_WIDTH,
                                       "n_qh": c0["n_qh"], "n_event_days": c0["n_event_days"],
                                       "verdict": vd})
                    seqs[gname] = seq
                v2s, fs = seqs["V2 0.01"], seqs["fine 0.0025"]
                b0 = v2s[0]
                at_c = next(x for x in fs if abs(x[0] - comp_B) < 1e-9)
                def holds_to(seq):
                    last = seq[0][0]
                    for B, _, _, vd in seq:
                        if vd != seq[0][3]:
                            return f"{last:g}"
                        last = B
                    return f"> {last:g}"
                outside_top = v2s[-1][3] == "outside"
                label = ("counts only" if var != "headline" and arm_days[var] < ARM_MIN_EVENT_DAYS
                         else None)
                verdicts.append({**row, "lower_B0": b0[1], "upper_B0": b0[2],
                                 "lower_at_comparison_bias": at_c[1],
                                 "upper_at_comparison_bias": at_c[2],
                                 "comparison_B": comp_B,
                                 "verdict_B0": label or b0[3],
                                 "verdict_at_comparison_bias": label or at_c[3],
                                 "B0_verdict_holds_to_V2": holds_to(v2s),
                                 "B0_verdict_holds_to_fine": holds_to(fs),
                                 "outside_at_largest_B": outside_top,
                                 "claim_level": ("inconsistent" if m["class"] == "cross-period"
                                                 else "contradicted") if outside_top else ""})
    # depends on weighting: unweighted and weighted verdicts differ at B = 0 or at the comparison B
    key = lambda r: (r["claim_id"], r["variant"])
    by = {}
    for r in verdicts:
        if r.get("weighting"):
            by.setdefault(key(r), {})[r["weighting"]] = r
    for r in verdicts:
        pair = by.get(key(r)) if r.get("weighting") else None
        if pair and len(pair) == 2 and r["verdict_B0"] not in ("plain number",):
            u, w = pair["unweighted"], pair["weighted"]
            r["depends_on_weighting"] = (u["verdict_B0"] != w["verdict_B0"]
                                         or u["verdict_at_comparison_bias"] != w["verdict_at_comparison_bias"])
        else:
            r["depends_on_weighting"] = ""
    cols = ["claim_id", "class", "variant", "weighting", "hirth_value", "hirth_unit", "n_qh",
            "n_event_days", "arm_event_days", "lower_B0", "upper_B0", "comparison_B",
            "lower_at_comparison_bias", "upper_at_comparison_bias", "verdict_B0",
            "verdict_at_comparison_bias", "B0_verdict_holds_to_V2", "B0_verdict_holds_to_fine",
            "outside_at_largest_B", "claim_level", "method_value", "difference",
            "depends_on_weighting", "reason"]
    _write(RANGES, ranges)
    _write(VERDICTS, [{k: r.get(k, "") for k in cols} for r in verdicts])


# ------------------------------------------------------------------ step 3: report (docs/23)
EXPOSURE = OUT_DIR / "exposure_check.csv"
EXPOSURE_BANDS = ("le_m50", "lt_0")


def exposure_check(out: Path = EXPOSURE) -> Path:
    """Band mean, minimum and maximum of e on the design rows at b = 0, per variant.

    Written for docs/23 to explain why H1a (response) and H1b (curtailment) share a range:
    the response functional divides the curtailment functional by the band mean of e, so the
    two coincide when that mean is 1. e does not depend on b; the weighted mean uses H."""
    import numpy as np
    from src.method import hirth_functionals as hf
    from src.method.bias_robust import redispatch_keep
    from src.method.bounds import build_design
    from src.method.real_panel import THREE_AREA, load_panel
    panel = load_panel(THREE_AREA, "H")
    rows = []
    for v in VARIANTS:
        keep = panel["keep"] if v == "headline" else panel["keep"] & redispatch_keep(panel, v)
        price, f = panel["price"][keep], np.asarray(panel["f"], dtype=float)[keep]
        theta = panel["theta_for"]("main")[:, keep]
        s = (price[None, :] < theta).astype(float)
        depth = np.maximum(0.0, theta - price[None, :]) * s
        design = build_design(s, depth, panel["shares"], panel["runlen"][:, keep],
                              cohort_ids=panel["ids"])
        e = hf.exposed_share(design)
        p_rows = price[design.rows]
        for key in EXPOSURE_BANDS:
            band = _band_by_key(key)
            m = (p_rows > band.lo) & (p_rows <= band.hi)
            w = f[design.rows][m]
            rows.append({"variant": v, "band": key, "n_qh": int(m.sum()),
                         "mean_e": float(e[m].mean()),
                         "mean_e_weighted": float((w * e[m]).sum() / w.sum()),
                         "min_e": float(e[m].min()), "max_e": float(e[m].max()),
                         "n_qh_e_below_1": int((e[m] < 1.0 - 1e-12).sum())})
    _write(out, rows)
    return out


def _verdicts() -> list[dict]:
    with VERDICTS.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _exposures() -> list[dict]:
    with EXPOSURE.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _f(x: str, d: int = 3) -> str:
    return f"{float(x):.{d}f}"


def _bounded_rows(cls: str) -> list[list[str]]:
    rows = []
    for r in _verdicts():
        if r["class"] != cls or r["verdict_B0"] in ("plain number", "not comparable"):
            continue
        rows.append([r["claim_id"], r["variant"], r["weighting"], f"{r['hirth_value']} %",
                     f"{r['n_qh']} / {r['n_event_days']}",
                     f"[{_f(r['lower_B0'])}, {_f(r['upper_B0'])}]", r["verdict_B0"],
                     f"[{_f(r['lower_at_comparison_bias'])}, {_f(r['upper_at_comparison_bias'])}]",
                     r["verdict_at_comparison_bias"], r["B0_verdict_holds_to_V2"],
                     r["B0_verdict_holds_to_fine"],
                     "yes" if r["depends_on_weighting"] == "True" else "no"])
    return rows


_RESULT_HEADER = ["claim", "variant", "weighting", "Hirth", "band quarter-hours / event days",
                  "range at B = 0", "verdict at B = 0", "range at the comparison B",
                  "verdict at the comparison B", "B = 0 verdict holds to (V2)",
                  "holds to (fine)", "depends on weighting"]


def results_main() -> str:
    return _md(_RESULT_HEADER, _bounded_rows("main"))


def results_cross() -> str:
    return _md(_RESULT_HEADER, _bounded_rows("cross-period"))


def results_plain() -> str:
    rows = [[r["claim_id"], r["class"], r["variant"], r["weighting"], f"{r['hirth_value']} %",
             _f(r["method_value"]), f"{float(r['difference']):+.3f}", r["n_event_days"]]
            for r in _verdicts() if r["verdict_B0"] == "plain number"]
    return _md(["claim", "class", "variant", "weighting", "Hirth", "method's band mean of e",
                "method − Hirth", "event days"], rows)


def results_counts() -> str:
    am = amended_mapping()
    head = {r["claim_id"]: r for r in _verdicts()
            if r["variant"] == "headline" and r["weighting"] == "unweighted"}
    main = [m["claim_id"] for m in am if m["class"] == "main" and m["kind"] == "bounded"]
    def ids(word, at):
        return ", ".join(c for c in main if head[c][at] == word) or "none"
    lines = []
    for at, name in (("verdict_B0", "B = 0"), ("verdict_at_comparison_bias", "the comparison B")):
        lines.append(f"- Main class, headline, unweighted, at {name}: supported {ids('supported', at)}; "
                     f"outside {ids('outside', at)}; not decidable {ids('not decidable', at)}.")
    contra = [r["claim_id"] for r in _verdicts() if r.get("claim_level")]
    lines.append(f"- Contradicted or inconsistent (outside at B = {V2_BMAX:.2f}): "
                 f"{', '.join(sorted(set(contra))) or 'none'}.")
    dw = sorted({r["claim_id"] for r in _verdicts() if r["depends_on_weighting"] == "True"})
    lines.append(f"- Depends on weighting: {', '.join(dw) or 'none'}.")
    lines.append("- Cross-period claims are left out of these counts (Amendment 1).")
    return "\n".join(lines)


def exposure_line() -> str:
    ex = [r for r in _exposures() if r["band"] == "le_m50"]
    parts = [f"{r['variant']} {float(r['mean_e']):.4f} (weighted {float(r['mean_e_weighted']):.4f}, "
             f"minimum {float(r['min_e']):.4f}, {r['n_qh']} quarter-hours)" for r in ex]
    all_one = all(int(r["n_qh_e_below_1"]) == 0 for r in ex)
    tail = ("e is 1 in every such quarter-hour, so the response functional equals the "
            "curtailment functional and H1a and H1b share their ranges by construction."
            if all_one else
            "e is below 1 in some such quarter-hours, so the two functionals differ; the equal "
            "ranges are not explained by e alone.")
    return (f"- **Why H1a and H1b share a range.** Mean exposed share e for price ≤ −50, at b = 0: "
            + "; ".join(parts) + f" (`exposure_check.csv`). " + tail)


def product_table() -> str:
    """Post-hoc, factual: the method's e (H22 row) × Hirth's response (H24), against H23's range."""
    v = {(r["claim_id"], r["variant"], r["weighting"]): r for r in _verdicts()}
    h24 = claim_share(next(m for m in mapping() if m["claim_id"] == "H24"))
    rows = []
    for var in VARIANTS:
        for wt in ("unweighted", "weighted"):
            e = float(v[("H22", var, wt)]["method_value"])
            h23 = v[("H23", var, wt)]
            prod = e * h24
            def where(lo, hi):
                lo, hi = float(lo), float(hi)
                return "inside" if lo <= prod <= hi else ("below" if prod < lo else "above")
            rows.append([var, wt, f"{e:.3f}", f"{prod:.3f}",
                         f"[{_f(h23['lower_B0'])}, {_f(h23['upper_B0'])}]",
                         where(h23["lower_B0"], h23["upper_B0"]),
                         f"[{_f(h23['lower_at_comparison_bias'])}, {_f(h23['upper_at_comparison_bias'])}]",
                         where(h23["lower_at_comparison_bias"], h23["upper_at_comparison_bias"])])
    return _md(["variant", "weighting", "method's e (H22 row)", "e × Hirth's response 0.37",
                "H23 range at B = 0", "product vs range", "H23 range at the comparison B",
                "product vs range"], rows)


def masked_days_note() -> str:
    vs = [r for r in _verdicts() if r["variant"] in ("M0", "M1") and r.get("n_event_days")
          and r["verdict_B0"] != "plain number"]
    arm = {r["variant"]: r["arm_event_days"] for r in vs}
    days: dict[str, list[int]] = {}
    for r in vs:
        if int(r["n_event_days"]) < ARM_MIN_EVENT_DAYS:
            days.setdefault(r["claim_id"], []).append(int(r["n_event_days"]))
    order = sorted(days, key=lambda c: (min(days[c]), int(c[1:].rstrip("ab")), c))
    def span(c):
        a, b = min(days[c]), max(days[c])
        return f"{c} {a}" if a == b else f"{c} {a} to {b}"
    few = [span(c) for c in order if max(days[c]) <= 6]
    more = [span(c) for c in order if max(days[c]) > 6]
    lo = min(min(d) for d in days.values())
    hi = max(max(d) for d in days.values())
    return (f"- **Event days under the masks.** The counts-only rule (fewer than "
            f"{ARM_MIN_EVENT_DAYS} event days) was applied at arm level, as pre-registered in "
            f"docs/11: M0 keeps {arm['M0']} event days and M1 {arm['M1']}, so neither arm is "
            f"counts only and every masked range above is reported as a range. Band by band, "
            f"several masked ranges rest on fewer than {ARM_MIN_EVENT_DAYS} event days "
            f"({lo} to {hi}, M0 and M1 together): {', '.join(few)}; and {', '.join(more)}. "
            f"The per-band counts are in the tables above. No verdict or rule is changed.")


def product_note() -> str:
    m = {x["claim_id"]: x for x in mapping()}
    h22, h24, h23 = (claim_share(m[c]) for c in ("H22", "H24", "H23"))
    return (f"- For reference, Hirth's own exposure rate times his response rate for 2026, "
            f"{h22:.2f} × {h24:.2f} = {h22 * h24:.3f}, against his curtailment rate "
            f"{h23:.2f} (H22, H24, H23; his Table 4 identity).")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true", help="every variant and b (long)")
    ap.add_argument("--summarise", action="store_true")
    ap.add_argument("--exposure-check", action="store_true")
    a = ap.parse_args()
    if a.run:
        run()
    if a.summarise:
        summarise()
    if a.exposure_check:
        exposure_check()
