"""Q5: P3's real-data arm on 50Hertz + Amprion + TransnetBW, potential F and then H.

    python -m src.identification.run_q5

Pre-registration `docs/Q5_preregistration.md` (commit `60efa6e`). Everything is P3's
real-data arm (`run_p3_real.run_arm`) except the region and the potential:

  Q5-F   c_hat = 1 - G/F,  F also lambda-5's potential
  Q5-H   c_hat = 1 - G/H,  H (quality-assured Online-Hochrechnung) also lambda-5's

Both arms use the same quarter-hours (`run_p3_real._three_area_series`). H is ex post:
T1 bounds only, never a day-ahead input (`src/postauction/leakage.py`).

Writes `artifacts/Q5/q5_real.csv`, one row per (potential, setting, period, functional),
with the runner's own `informative` flag: width below 0.25 of the logical maximum
(1; 2 for L6; `l5_energy_full_gwh` for L5), Q0 section 5.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import numpy as np

from src.identification.run_p3_real import (
    SETTINGS, THREE_AREA, git_head, load_panel, run_arm,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT = REPO_ROOT / "artifacts" / "Q5" / "q5_real.csv"
PREREG_COMMIT = "60efa6e"
INFORMATIVE_FRACTION = 0.25


def logical_max(row: dict) -> float:
    if row["lam"] == "L6":
        return 2.0
    if row["lam"] == "L5":
        return float(row.get("l5_energy_full_gwh", np.nan))
    return 1.0


def arms(panel) -> list[tuple[str, np.ndarray, bool]]:
    """P3's arm set (`run_p3_real.main`): the window plain and recalibrated, and each
    month with a published market value that carries a negative-price quarter-hour."""
    keep, months = panel["keep"], np.array([d[:7] for d in panel["bdate"]])
    out = [("window", keep, False), ("window", keep, True)]
    for m in sorted(set(months[keep])):
        sel = keep & (months == m)
        if (panel["price"][sel] < 0).any():
            out.append((m, sel, False))
    return out


def main() -> None:
    head, today = git_head(), date.today().isoformat()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fh = writer = None
    try:
        for potential in ("F", "H"):
            panel = load_panel(THREE_AREA, potential)
            print(f"{potential}: {int(panel['keep'].sum())} quarter-hours kept, "
                  f"shares {np.round(panel['shares'], 4).tolist()}", flush=True)
            for setting in SETTINGS:
                for label, sel, recal in arms(panel):
                    rows = run_arm(panel, setting, sel, label, recal)
                    for r in rows:
                        mx = logical_max(r) if r.get("defined") else np.nan
                        w = r.get("width", np.nan)
                        r.update({
                            "potential": potential, "logical_max_width": mx,
                            "informative": (bool(w < INFORMATIVE_FRACTION * mx)
                                            if r.get("defined") and r.get("feasible")
                                            and np.isfinite(w) and np.isfinite(mx) else None),
                            "preregistration_commit": PREREG_COMMIT,
                            "git_head": head, "run_date": today})
                    if writer is None:
                        fh = open(OUT, "w", newline="", encoding="utf-8")
                        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
                        writer.writeheader()
                    for r in rows:
                        writer.writerow({k: r.get(k) for k in writer.fieldnames})
                    fh.flush()
                    print(f"  {potential} {setting:<5} {label:<8}{'recal' if recal else ''} "
                          f"eps={rows[0].get('eps', float('nan')):.4f} "
                          + " ".join(f"{r['lam']}={r['width']:.3f}" for r in rows
                                     if isinstance(r.get("width"), float)
                                     and np.isfinite(r["width"])), flush=True)
    finally:
        if fh is not None:
            fh.close()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
