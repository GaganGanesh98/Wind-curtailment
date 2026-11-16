"""Supporting power evidence from a reduced-grid results CSV.

Three tables, all descriptive, none of them a verdict:

1. The distribution of `headroom_mw` (= `mae_b0` - `mae_oracle`), the recoverable
   gap between the operational status quo and the information ceiling.
2. The cells where a method's `recovery_skill` exceeds 1.0 -- i.e. it scores better
   than the oracle it is measured against -- broken down by method. The oracle is
   trained on true available power, so a baseline above 1.0 is not a better method;
   it is the noise floor of the comparison showing through.
3. `censored_mae_mw` for M1, so the headroom in table 1 can be read against the
   error it sits inside.

`recovery_skill` = (MAE_B0 - MAE_method) / (MAE_B0 - MAE_oracle), from `metrics.py`.
The denominator is table 1's headroom, so when headroom is small relative to the
error, small MAE differences move the skill score a long way. That is the point of
printing all three together.
"""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

CELL_KEYS = ("censoring_rate", "gamma", "r_shape", "seed")
#: Everything that is not the candidate (M1) and not the ceiling itself.
BASELINES = ("B0", "B1", "B2", "B3", "B4", "B5", "Proxy")


def load(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def cell_of(row: dict) -> tuple:
    return tuple(row[k] for k in CELL_KEYS)


def fnum(row: dict, col: str) -> float | None:
    v = (row.get(col) or "").strip()
    if v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", required=True, help="reduced-grid results CSV to read")
    ap.add_argument("--out", default=None,
                    help="optional CSV to write the tables to")
    ap.add_argument("--expect-cells", type=int, default=81,
                    help="refuse to report on fewer cells than this (0 disables)")
    args = ap.parse_args()

    path = Path(args.csv)
    rows = load(path)
    cells = {cell_of(r) for r in rows}
    methods = sorted({r["method"] for r in rows})
    print(f"read {path}")
    print(f"  {len(rows)} rows, {len(cells)} cells, {len(methods)} methods: "
          f"{', '.join(methods)}")

    kcoh = sorted({(r.get("n_cohorts") or "").strip() for r in rows})
    print(f"  n_cohorts present: {', '.join(k or '(blank)' for k in kcoh)}")

    if args.expect_cells and len(cells) < args.expect_cells:
        raise SystemExit(
            f"Only {len(cells)} of {args.expect_cells} cells in {path.name}. "
            "Refusing to report: a partial grid cannot support a claim. Pass "
            "--expect-cells 0 to override for inspection only.")

    out_rows: list[dict] = []

    # ---------------------------------------------------------------- table 1
    # headroom is a property of the cell, not the method; verify that before
    # collapsing, so an inconsistency is caught rather than averaged away.
    per_cell: dict[tuple, set] = defaultdict(set)
    for r in rows:
        h = fnum(r, "headroom_mw")
        if h is not None:
            per_cell[cell_of(r)].add(round(h, 4))
    bad = {c: v for c, v in per_cell.items() if len(v) > 1}
    head = sorted(next(iter(v)) for v in per_cell.values())

    print(f"\n{'=' * 70}\nTABLE 1  headroom_mw = mae_b0 - mae_oracle, per cell\n"
          f"{'=' * 70}")
    if bad:
        print(f"  *** {len(bad)} cells disagree on headroom across method rows; "
              f"not collapsing ***")
        for c, v in list(bad.items())[:5]:
            print(f"      {c}: {sorted(v)}")
    print(f"  cells            {len(head)}")
    print(f"  min              {min(head):>10,.1f} MW")
    print(f"  median           {statistics.median(head):>10,.1f} MW")
    print(f"  max              {max(head):>10,.1f} MW")
    print(f"  mean             {statistics.fmean(head):>10,.1f} MW")
    out_rows.append({"table": "headroom_mw", "method": "(per cell)",
                     "statistic": "min/median/max/mean", "n": len(head),
                     "value_min": round(min(head), 1),
                     "value_median": round(statistics.median(head), 1),
                     "value_max": round(max(head), 1),
                     "value_mean": round(statistics.fmean(head), 1),
                     "note": "mae_b0 - mae_oracle; the recoverable gap"})

    # ---------------------------------------------------------------- table 2
    print(f"\n{'=' * 70}\nTABLE 2  cells with recovery_skill > 1.0 "
          f"(better than the ceiling)\n{'=' * 70}")
    print(f"  {'method':<8}{'n > 1.0':>9}{'of':>5}{'min':>9}{'median':>9}"
          f"{'max':>9}   kind")
    for m in methods:
        sk = [fnum(r, "recovery_skill") for r in rows if r["method"] == m]
        sk = [v for v in sk if v is not None]
        if not sk:
            continue
        n_above = sum(1 for v in sk if v > 1.0)
        kind = ("candidate" if m == "M1"
                else "ceiling" if m == "Oracle" else "baseline")
        print(f"  {m:<8}{n_above:>9}{len(sk):>5}{min(sk):>9.3f}"
              f"{statistics.median(sk):>9.3f}{max(sk):>9.3f}   {kind}")
        out_rows.append({"table": "recovery_skill_above_1", "method": m,
                         "statistic": "n_above_1 / min / median / max",
                         "n": n_above,
                         "value_min": round(min(sk), 4),
                         "value_median": round(statistics.median(sk), 4),
                         "value_max": round(max(sk), 4),
                         "value_mean": round(statistics.fmean(sk), 4),
                         "note": f"{kind}; {n_above} of {len(sk)} cells above 1.0"})
    n_any = sum(1 for c in cells
                if any((fnum(r, "recovery_skill") or -9e9) > 1.0
                       for r in rows
                       if cell_of(r) == c and r["method"] in BASELINES))
    print(f"\n  cells where ANY of {', '.join(BASELINES)} exceeds 1.0: "
          f"{n_any} of {len(cells)}")
    out_rows.append({"table": "recovery_skill_above_1", "method": "ANY baseline",
                     "statistic": "n_cells_with_any_baseline_above_1", "n": n_any,
                     "value_min": "", "value_median": "", "value_max": "",
                     "value_mean": "",
                     "note": f"of {len(cells)} cells; baselines "
                             f"{'/'.join(BASELINES)}"})

    # ---------------------------------------------------------------- table 3
    print(f"\n{'=' * 70}\nTABLE 3  censored_mae_mw -- the error the headroom sits "
          f"inside\n{'=' * 70}")
    print(f"  {'method':<8}{'min':>12}{'median':>12}{'max':>12}")
    for m in ("M1", "B0", "Oracle"):
        mae = [fnum(r, "censored_mae_mw") for r in rows if r["method"] == m]
        mae = [v for v in mae if v is not None]
        if not mae:
            continue
        print(f"  {m:<8}{min(mae):>12,.1f}{statistics.median(mae):>12,.1f}"
              f"{max(mae):>12,.1f}")
        out_rows.append({"table": "censored_mae_mw", "method": m,
                         "statistic": "min/median/max", "n": len(mae),
                         "value_min": round(min(mae), 1),
                         "value_median": round(statistics.median(mae), 1),
                         "value_max": round(max(mae), 1),
                         "value_mean": round(statistics.fmean(mae), 1),
                         "note": "MAE on censored QHs"})
    m1 = [fnum(r, "censored_mae_mw") for r in rows if r["method"] == "M1"]
    m1 = [v for v in m1 if v is not None]
    if m1 and head:
        frac = statistics.median(head) / statistics.median(m1)
        print(f"\n  median headroom / median M1 censored MAE = "
              f"{statistics.median(head):,.1f} / {statistics.median(m1):,.1f} "
              f"= {frac:.1%}")
        print("  The whole recoverable gap is a small fraction of the error it sits "
              "inside.")
        out_rows.append({"table": "headroom_vs_error", "method": "M1",
                         "statistic": "median_headroom / median_censored_mae",
                         "n": len(m1), "value_min": "", "value_median": round(frac, 6),
                         "value_max": "", "value_mean": "",
                         "note": f"{statistics.median(head):.1f} MW of "
                                 f"{statistics.median(m1):.1f} MW"})

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out_rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(out_rows)
        print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
