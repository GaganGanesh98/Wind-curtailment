"""Is the shared gamma = 0 bias an F-dependent error in the latent head?

    python -m src.censoring.diag_bias_by_forecast [--gamma 0.0] [--allow-partial]

The question
------------
On censored quarter-hours at gamma = 0 every method carries a pooled bias of roughly
-90 MW: M1 -94, B2 -92, B3 -121, B4 -86. A bias that size shared by methods with
completely different censoring assumptions is unlikely to be about censoring at all.
The candidate explanation is the latent head: if A-hat = F * exp(g(x)) is
conditionally biased in F, then every method built on that head inherits the same
error wherever the censored quarter-hours sit in the F distribution, and censored
quarter-hours do not sit uniformly -- the generator places them with weight
exp(gamma * z(F)), and even at gamma = 0 the eligible pool is restricted.

The test
--------
Bias by decile of F on **held-out uncensored** quarter-hours:

  held-out    the validation days of the same event-day split every method trains
              with, recomputed from the stored `berlin_date` and seed 42. Nothing
              here is scored on a day a model saw.
  uncensored  c_true = 0, so A_true = G_obs exactly and the residual is the latent
              head's own forecast error with no censoring in it.

B0 is the raw TSO day-ahead forecast and is included deliberately: it is the latent
head with g == 0. If the per-decile pattern of the fitted methods matches B0's, the
F-dependence is the published forecast's, inherited rather than introduced. If the
fitted methods flatten B0's pattern but keep a level offset, the head is correcting
the shape and missing the level.

What this does not do
---------------------
It does not explain the censored-quarter-hour bias on its own. It establishes
whether an F-dependent component exists and how large it is in the region of F the
censored quarter-hours occupy; the printed overlap table is what connects the two.
It is a diagnostic, not gate evidence.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import numpy as np

from src.censoring.gate_verdict import load_cells, pool
from src.method.stage_a.latent_model import TrainConfig, eventday_split
from src.method.event_day_bootstrap import eventday_bootstrap_mean

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_CSV = REPO_ROOT / "results" / "14_bias_by_forecast_decile.csv"
METHODS = ("B0", "M1", "B1", "B2", "B3", "B4")
N_DECILES = 10


def heldout_uncensored(cell: dict) -> np.ndarray:
    """Validation days of the model's own split, and nothing switched off."""
    cfg = TrainConfig()
    _, val = eventday_split(cell["berlin_date"], cfg.val_fraction, cfg.seed)
    return val & ~np.asarray(cell["censored"], dtype=bool)


def decile_edges(values: np.ndarray) -> np.ndarray:
    """Interior decile boundaries, deduplicated so flat regions cannot make a gap."""
    qs = np.percentile(values, np.linspace(0, 100, N_DECILES + 1))
    qs[0], qs[-1] = -np.inf, np.inf
    return np.unique(qs)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gamma", type=float, default=0.0)
    ap.add_argument("--allow-partial", action="store_true")
    args = ap.parse_args()

    cells = [c for c in load_cells() if float(c["gamma"]) == args.gamma]
    if not cells:
        raise SystemExit(f"No stored cells at gamma = {args.gamma}.")
    if len(cells) < 27 and not args.allow_partial:
        raise SystemExit(f"Only {len(cells)} of 27 cells at gamma = {args.gamma}. "
                         "Pass --allow-partial for a provisional read.")
    print(f"gamma = {args.gamma}, {len(cells)} cells "
          f"{'(PROVISIONAL subset)' if len(cells) < 27 else ''}")

    # Pool F and the day labels once on the held-out uncensored sample.
    f_pool, _, days = pool(cells, lambda c: (c["forecast"], c["forecast"],
                                             heldout_uncensored(c),
                                             c["berlin_date"]))
    edges = decile_edges(f_pool)
    which = np.clip(np.digitize(f_pool, edges[1:-1]), 0, len(edges) - 2)
    print(f"held-out uncensored quarter-hours pooled: {f_pool.size:,} "
          f"in {len(np.unique(days))} days")

    # Where the censored quarter-hours actually sit in the same F bins.
    f_cens, _, _ = pool(cells, lambda c: (c["forecast"], c["forecast"],
                                          np.asarray(c["censored"], dtype=bool),
                                          c["berlin_date"]))
    cens_which = np.clip(np.digitize(f_cens, edges[1:-1]), 0, len(edges) - 2)
    cens_share = np.bincount(cens_which, minlength=len(edges) - 1) / f_cens.size

    bias = {}
    for m in METHODS:
        err, _, _ = pool(cells, lambda c, mm=m: (
            np.asarray(c[f"a_hat_{mm}"], dtype=float)
            - np.asarray(c["a_true"], dtype=float),
            c["forecast"], heldout_uncensored(c), c["berlin_date"]))
        bias[m] = err

    rows = []
    header = (f"\n{'bin':<5}{'F range (MW)':>20}{'n':>9}{'cens%':>7}"
              + "".join(f"{m:>10}" for m in METHODS))
    print(header)
    print("-" * len(header))
    for b in range(len(edges) - 1):
        sel = which == b
        if not sel.any():
            continue
        lo = f_pool[sel].min()
        hi = f_pool[sel].max()
        line = (f"{b:<5}{f'{lo:,.0f}-{hi:,.0f}':>20}{int(sel.sum()):>9,}"
                f"{cens_share[b]:>7.1%}")
        for m in METHODS:
            v = float(bias[m][sel].mean())
            line += f"{v:>10,.0f}"
            rows.append({"gamma": args.gamma, "f_bin": b,
                         "f_lo_mw": round(float(lo), 1), "f_hi_mw": round(float(hi), 1),
                         "n_qh": int(sel.sum()),
                         "censored_share_in_bin": round(float(cens_share[b]), 5),
                         "method": m, "bias_mw": round(v, 2)})
        print(line)

    # Overall held-out uncensored bias, with a CI, and the F-dependence summary.
    print(f"\n{'method':<8}{'held-out bias MW':>18}{'95% CI':>24}"
          f"{'spread across bins':>20}{'corr(bias, F)':>15}"
          f"{'cens-weighted':>15}")
    print("-" * 100)
    centres = np.array([f_pool[which == b].mean() for b in range(len(edges) - 1)
                        if (which == b).any()])
    for m in METHODS:
        mean, lo, hi, n, nd = eventday_bootstrap_mean(bias[m], days)
        per_bin = np.array([bias[m][which == b].mean()
                            for b in range(len(edges) - 1) if (which == b).any()])
        w = np.array([cens_share[b] for b in range(len(edges) - 1)
                      if (which == b).any()])
        corr = (float(np.corrcoef(per_bin, centres)[0, 1])
                if per_bin.std() > 0 else float("nan"))
        print(f"{m:<8}{mean:>18,.1f}{f'[{lo:+,.1f}, {hi:+,.1f}]':>24}"
              f"{per_bin.max() - per_bin.min():>20,.0f}{corr:>15.3f}"
              f"{float((per_bin * w).sum() / w.sum()):>15,.1f}")
        rows.append({"gamma": args.gamma, "f_bin": "ALL", "f_lo_mw": "",
                     "f_hi_mw": "", "n_qh": n,
                     "censored_share_in_bin": "", "method": m,
                     "bias_mw": round(mean, 2)})

    print("\n  'spread across bins'  max minus min of the per-bin bias: the size of")
    print("                        the F-dependent component.")
    print("  'corr(bias, F)'       sign and strength of that dependence.")
    print("  'cens-weighted'       the per-bin biases reweighted to where the")
    print("                        CENSORED quarter-hours sit. Compare it with the")
    print("                        censored-QH bias from the gate: if the two agree,")
    print("                        the censored bias is the held-out F-dependent")
    print("                        error seen through the censoring placement, and")
    print("                        not something the censoring model is doing.")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {OUT_CSV.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
