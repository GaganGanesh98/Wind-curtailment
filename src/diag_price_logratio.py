"""Real-data diagnostic: how does log(G/F) move with the day-ahead price?

    python src/diag_price_logratio.py

Item 4a of the 31 Oct 2026 decision list. Light, independent of the E1 grid, and
needed before the E1-MNAR arm can be pre-registered sensibly: that arm has to choose
a placement weight, and the choice should be informed by what the real relationship
between price and the output shortfall actually looks like, not by what makes E1
convenient.

The quantities
--------------
G is the metered actual wind, F the TSO day-ahead forecast, both quarter-hourly, in
MW (`da_wind_mw`, `act_wind_mw`: onshore plus offshore; the onshore-only variant is
printed too, because the EEG switch-off rules bear on onshore capacity).

  ratio       sum(G) / sum(F) over the quarter-hours of a price band. This is the
              headline, because it needs no sample restriction: zeroed quarter-hours
              are included at their true value of zero, which is exactly where the
              interesting behaviour is. Event-day block-bootstrap CI.
  mean log    mean of log(G/F), on G > 0 only. Reported because it is the quantity
              named in the decision list and because it weights quarter-hours
              equally rather than by size, but it necessarily **discards the zeroed
              quarter-hours**, which is a selection on the outcome. The share
              discarded is printed beside it; where that share is large the mean log
              is the less trustworthy of the two.
  zero share  share of quarter-hours with G = 0, and with G < 0.1 F.

The confounding this is really about
------------------------------------
Negative prices occur when it is windy, so the price band and F are correlated: the
"<= -50" band is not a random sample of quarter-hours but a high-F sample. Any
F-dependence in the forecast's own error therefore shows up as an apparent price
response. So the price bands are also crossed with F terciles, computed **within
each area**, and the > 5 EUR/MWh band is the reference: whatever the ratio does
there at high F is the forecast's behaviour, not a switch-off response.

What this is not
----------------
It is not an estimate of r. The shortfall it measures contains, in unknown
proportions: price-driven switch-off, grid-operator redispatch (not price-driven at
all), and the day-ahead forecast's own conditional bias. Separating those is the
thesis. `r_desc` below is a descriptive contrast against the > 5 band, labelled as
such, and is not to be quoted as a response curve.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.smard_config import PRICE_BANDS  # noqa: E402
from src.stats_boot import eventday_bootstrap_mean, eventday_bootstrap_ratio  # noqa: E402

PANEL = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"
OUT_CSV = REPO_ROOT / "results" / "15_price_logratio.csv"
AREAS = ("DE", "50Hertz", "Amprion", "TenneT", "TransnetBW")
F_FLOOR_FRACTION = 0.02   # drop F below 2% of the area's median F: log(G/F) explodes


def band_filter(df: pl.DataFrame, lo, hi) -> pl.DataFrame:
    if lo is not None:
        df = df.filter(pl.col("price_eur_mwh") > lo)
    if hi is not None:
        df = df.filter(pl.col("price_eur_mwh") <= hi)
    return df


def summarise(df: pl.DataFrame) -> dict:
    """Ratio, mean log and the zero shares for one subsample."""
    g = df["g"].to_numpy()
    f = df["f"].to_numpy()
    d = df["berlin_date"].to_numpy()
    ratio, r_lo, r_hi, n, n_days = eventday_bootstrap_ratio(g, f, d)

    pos = g > 0
    if pos.sum() >= 2:
        lg, l_lo, l_hi, _, _ = eventday_bootstrap_mean(
            np.log(g[pos] / f[pos]), d[pos])
    else:
        lg = l_lo = l_hi = float("nan")

    return {"ratio": ratio, "ratio_lo": r_lo, "ratio_hi": r_hi,
            "mean_log": lg, "log_lo": l_lo, "log_hi": l_hi,
            "zero_share": float((g <= 0).mean()) if g.size else float("nan"),
            "near_zero_share": float((g < 0.1 * f).mean()) if g.size else float("nan"),
            "log_dropped_share": float((~pos).mean()) if g.size else float("nan"),
            "mean_price": float(df["price_eur_mwh"].mean()) if df.height else float("nan"),
            "mean_f_mw": float(f.mean()) if f.size else float("nan"),
            "n_qh": n, "n_days": n_days}


def area_frame(panel: pl.DataFrame, area: str, onshore: bool) -> pl.DataFrame:
    gcol = "act_onshore_mw" if onshore else "act_wind_mw"
    fcol = "da_onshore_mw" if onshore else "da_wind_mw"
    df = (panel.filter(pl.col("area") == area)
                .select(["berlin_date", "price_eur_mwh", gcol, fcol])
                .rename({gcol: "g", fcol: "f"})
                .drop_nulls()
                # SMARD gaps arrive as NaN floats, not nulls, so drop_nulls alone
                # leaves them in: the bootstrap filters them but the plain means and
                # shares would not, and the two would then describe different samples.
                .filter(pl.col("g").is_finite() & pl.col("f").is_finite()
                        & pl.col("price_eur_mwh").is_finite()))
    floor = F_FLOOR_FRACTION * float(df["f"].median())
    return df.filter(pl.col("f") > floor)


def main() -> None:
    panel = pl.read_parquet(PANEL)
    rows: list[dict] = []

    for onshore in (False, True):
        tag = "onshore" if onshore else "wind (on+offshore)"
        print(f"\n{'=' * 104}\nG/F by price band -- {tag}\n{'=' * 104}")
        for area in AREAS:
            df = area_frame(panel, area, onshore)
            ref = summarise(band_filter(df, 5.0, None))
            print(f"\n{area}   {df.height:,} usable QH   "
                  f"reference band (> 5 EUR/MWh) ratio {ref['ratio']:.4f}")
            print(f"  {'band':<13}{'n QH':>8}{'days':>6}{'mean p':>9}{'mean F':>9}"
                  f"{'G/F':>8}{'95% CI':>18}{'r_desc':>8}{'mean log':>10}"
                  f"{'zero%':>7}{'<0.1F%':>8}")
            print("  " + "-" * 100)
            for label, lo, hi in PRICE_BANDS:
                sub = band_filter(df, lo, hi)
                if sub.height == 0:
                    continue
                s = summarise(sub)
                r_desc = (1.0 - s["ratio"] / ref["ratio"]
                          if np.isfinite(ref["ratio"]) and ref["ratio"] else float("nan"))
                ci = f"[{s['ratio_lo']:.4f}, {s['ratio_hi']:.4f}]"
                print(f"  {label:<13}{s['n_qh']:>8,}{s['n_days']:>6}"
                      f"{s['mean_price']:>9,.1f}{s['mean_f_mw']:>9,.0f}"
                      f"{s['ratio']:>8.4f}{ci:>18}{r_desc:>8.3f}"
                      f"{s['mean_log']:>10.4f}{s['zero_share']:>7.1%}"
                      f"{s['near_zero_share']:>8.1%}")
                rows.append({"series": tag, "area": area, "price_band": label,
                             "f_tercile": "all", "r_desc_vs_pos_band": round(r_desc, 5),
                             **{k: (round(v, 6) if isinstance(v, float) else v)
                                for k, v in s.items()}})

    # The confounding check: price band crossed with F tercile, DE and 50Hertz.
    print(f"\n{'=' * 104}\nPrice band x F tercile -- is the price response just high F?"
          f"\n{'=' * 104}")
    print("  The > 5 row of each tercile is the reference: what the forecast does at")
    print("  that wind level with no price incentive. A real switch-off response has")
    print("  to show up as the negative bands falling BELOW their own tercile's > 5.")
    for area in ("DE", "50Hertz"):
        df = area_frame(panel, area, onshore=True)
        cuts = np.percentile(df["f"].to_numpy(), [33.333, 66.667])
        df = df.with_columns(
            pl.when(pl.col("f") <= cuts[0]).then(pl.lit("low F"))
              .when(pl.col("f") <= cuts[1]).then(pl.lit("mid F"))
              .otherwise(pl.lit("high F")).alias("tercile"))
        print(f"\n{area} (onshore)   F terciles at {cuts[0]:,.0f} / {cuts[1]:,.0f} MW")
        print(f"  {'tercile':<9}{'band':<13}{'n QH':>8}{'days':>6}{'mean F':>9}"
              f"{'G/F':>8}{'95% CI':>18}{'vs own >5':>11}{'zero%':>7}")
        print("  " + "-" * 89)
        for terc in ("low F", "mid F", "high F"):
            t = df.filter(pl.col("tercile") == terc)
            ref = summarise(band_filter(t, 5.0, None))
            for label, lo, hi in PRICE_BANDS:
                sub = band_filter(t, lo, hi)
                if sub.height < 4:
                    continue
                s = summarise(sub)
                vs = (1.0 - s["ratio"] / ref["ratio"]
                      if np.isfinite(ref["ratio"]) and ref["ratio"] else float("nan"))
                ci = f"[{s['ratio_lo']:.4f}, {s['ratio_hi']:.4f}]"
                print(f"  {terc:<9}{label:<13}{s['n_qh']:>8,}{s['n_days']:>6}"
                      f"{s['mean_f_mw']:>9,.0f}{s['ratio']:>8.4f}{ci:>18}"
                      f"{vs:>11.3f}{s['zero_share']:>7.1%}")
                rows.append({"series": "onshore", "area": area, "price_band": label,
                             "f_tercile": terc, "r_desc_vs_pos_band": round(vs, 5),
                             **{k: (round(v, 6) if isinstance(v, float) else v)
                                for k, v in s.items()}})

    print("\nCaveats, restated because the table invites over-reading")
    print("  * The shortfall mixes price-driven switch-off, grid redispatch and the")
    print("    forecast's own conditional bias. r_desc is a contrast, not a response.")
    print("  * mean log drops every zeroed quarter-hour -- a selection on the outcome.")
    print("    Read the ratio column where the zero share is material.")
    print("  * Onshore and offshore are pooled in the first table because E1's base")
    print("    panel pools them; the onshore table is the one the EEG rules apply to.")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {OUT_CSV.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
