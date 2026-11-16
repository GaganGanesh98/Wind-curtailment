"""Bias of each E1 method by hour-of-day on censored quarter-hours, gamma = 0.

    python -m src.censoring.diag_bias_by_hour [--allow-partial]

One table. **No model is re-fitted here**: the A-estimates come from the stored
per-quarter-hour arrays in `data/processed/e1_gate_artifacts/`.

Why the hour has to be recovered rather than read
-------------------------------------------------
E1's timeline is a *relabelling*. The generator takes real quarter-hours with price
above the safe floor, in time order, and lays them on a synthetic contiguous grid, so
`berlin_date` and the synthetic timestamp are bookkeeping and their hour-of-day is an
artefact of the reordering. The meaningful hour is the one each base quarter-hour
actually came from, which carries the diurnal structure of the wind forecast error.

`load_base` keeps the real date but, until now, discarded the real hour. It is now
carried through as `real_hour` -- a pure passthrough that consumes no randomness, so
it cannot change any generated quantity. This script recovers it by regenerating each
cell's data (generation only, no fitting, a second or two per cell) and pairing it
with the stored predictions.

**The pairing is verified, not assumed.** For every cell the regenerated `a_true`,
`g_obs`, `c_true` and censored mask are asserted equal to the stored arrays. If the
regeneration ever drifted out of step with the stored fits, the assertion fails and
nothing is reported -- which is the only way this table can be trusted, since it joins
two artefacts by position.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from src.method.exposure import mastr_cohort_set
from src.censoring.gate_verdict import load_cells
from src.method.synthetic import SyntheticConfig, generate
from src.method.event_day_bootstrap import eventday_bootstrap_mean

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_CSV = REPO_ROOT / "results" / "17_bias_by_hour.csv"
METHODS = ("B0", "M1", "B1", "B2", "B3", "B4", "B5", "Proxy", "Oracle")


def real_hours_for(cell: dict, cohorts) -> np.ndarray:
    """Regenerate the cell's data and return the real Berlin hour, alignment checked."""
    cfg = SyntheticConfig(censoring_rate=float(cell["censoring_rate"]),
                          gamma=float(cell["gamma"]),
                          r_shape=str(cell["r_shape"]),
                          seed=int(cell["seed"]))
    d = generate(cfg, cohorts=cohorts)
    for name, regen, stored in (("a_true", d.a_true_mw, cell["a_true"]),
                                ("g_obs", d.g_obs_mw, cell["g_obs"]),
                                ("c_true", d.c_true, cell["c_true"])):
        if not np.allclose(regen.astype(np.float32), np.asarray(stored), atol=0,
                           rtol=0, equal_nan=True):
            raise SystemExit(
                f"{cell['path']}: regenerated {name} does not match the stored array. "
                "The table would join two artefacts that are out of step; refusing.")
    if not np.array_equal(d.censored, np.asarray(cell["censored"], dtype=bool)):
        raise SystemExit(f"{cell['path']}: censored mask mismatch; refusing.")
    return d.real_hour


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--allow-partial", action="store_true")
    args = ap.parse_args()

    cells = [c for c in load_cells() if float(c["gamma"]) == 0.0]
    if not cells:
        raise SystemExit("No stored gamma = 0 cells.")
    if len(cells) < 27 and not args.allow_partial:
        raise SystemExit(f"Only {len(cells)} of 27 gamma = 0 cells. "
                         "Pass --allow-partial for a provisional read.")
    rates = sorted({float(c['censoring_rate']) for c in cells})
    print(f"gamma = 0, {len(cells)} of 27 cells, rates {[f'{r:.0%}' for r in rates]}"
          + ("   *** PROVISIONAL ***" if len(cells) < 27 else ""))

    cohorts = mastr_cohort_set("DE")
    err = {m: [] for m in METHODS}
    hours, days = [], []
    for c in cells:
        h = real_hours_for(c, cohorts)
        mask = np.asarray(c["censored"], dtype=bool)
        hours.append(h[mask])
        days.append(np.asarray(c["berlin_date"])[mask])
        for m in METHODS:
            e = (np.asarray(c[f"a_hat_{m}"], dtype=float)
                 - np.asarray(c["a_true"], dtype=float))
            err[m].append(e[mask])
    hours = np.concatenate(hours)
    days = np.concatenate(days)
    err = {m: np.concatenate(v) for m, v in err.items()}
    print(f"censored quarter-hours pooled: {hours.size:,} "
          f"in {len(np.unique(days))} event-days\n")

    head = f"{'hour':<6}{'n':>8}" + "".join(f"{m:>9}" for m in METHODS)
    print(head)
    print("-" * len(head))
    rows = []
    for h in range(24):
        sel = hours == h
        if not sel.any():
            continue
        line = f"{h:02d}:00{int(sel.sum()):>8,}"
        for m in METHODS:
            line += f"{err[m][sel].mean():>9,.0f}"
            rows.append({"gamma": 0.0, "hour": h, "n_qh": int(sel.sum()),
                         "method": m, "bias_mw": round(float(err[m][sel].mean()), 2)})
        print(line)

    print(f"\n{'method':<9}{'pooled bias MW':>16}{'95% CI':>24}"
          f"{'spread over hours':>19}{'worst hour':>12}")
    print("-" * 80)
    for m in METHODS:
        mean, lo, hi, n, nd = eventday_bootstrap_mean(err[m], days)
        per_h = np.array([err[m][hours == h].mean() for h in range(24)
                          if (hours == h).any()])
        hrs = [h for h in range(24) if (hours == h).any()]
        worst = hrs[int(np.argmax(np.abs(per_h)))]
        print(f"{m:<9}{mean:>16,.1f}{f'[{lo:+,.1f}, {hi:+,.1f}]':>24}"
              f"{per_h.max() - per_h.min():>19,.0f}{f'{worst:02d}:00':>12}")
        rows.append({"gamma": 0.0, "hour": "ALL", "n_qh": n, "method": m,
                     "bias_mw": round(mean, 2)})

    print("\n  The diurnal spread is the quantity of interest: a method whose bias")
    print("  swings across the day is making an hour-dependent error, which no")
    print("  pooled number shows. Compare the spread with the pooled bias.")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {OUT_CSV.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
