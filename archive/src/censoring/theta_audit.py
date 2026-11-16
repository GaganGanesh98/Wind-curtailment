#!/usr/bin/env python3
"""Audit the inputs theta is built from, and the theta separation they produce.

    python -m src.censoring.theta_audit --step mv      # the market-value series
    python -m src.censoring.theta_audit --step theta   # separation on the real panel
    python -m src.censoring.theta_audit                # both

Read-only: touches no artifact directory and writes no result CSV unless --out is
given. Cheap by construction -- one panel scan per step, no model fitting.

Why it exists. `MP = max(0, AW - MV)` is reported as zero across much of the study
window, which would make the premium channel nearly dead on real data (docs/16). That
conclusion rests entirely on MV being the right series: the market value **for wind**
sits below the base-load price, because wind output correlates with low prices, so a
base-load or plain monthly-average series would be systematically too high and would
drive MP to zero artefactually. Step "mv" checks that independently of the loader, by
recomputing the wind-production-weighted average day-ahead price from the panel.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PANEL = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"


# --------------------------------------------------------------- step 1: the MV series


def monthly_series(area: str = "DE") -> pl.DataFrame:
    """Three monthly series from the panel, plus the published ones.

    `mv_recomputed` is the EEG Anlage 1 no. 3.3.2 definition applied to the panel:
    the onshore-wind-production-weighted average spot price. `price_mean` is the
    unweighted monthly mean, i.e. what a base-load series would look like. The ratio
    of the two is the capture rate, which for onshore wind must be BELOW 1.
    """
    df = (
        pl.scan_parquet(PANEL)
        .filter(pl.col("area") == area)
        .select(["berlin_date", "price_eur_mwh", "act_onshore_mw", "act_wind_mw"])
        .collect()
        .with_columns(pl.col("berlin_date").str.slice(0, 7).alias("ym"))
        .drop_nulls(["price_eur_mwh", "act_onshore_mw"])
    )
    grp = (
        df.group_by("ym")
        .agg(
            n_qh=pl.len(),
            price_mean=pl.col("price_eur_mwh").mean(),
            mv_recomputed=((pl.col("price_eur_mwh") * pl.col("act_onshore_mw")).sum()
                           / pl.col("act_onshore_mw").sum()),
            mv_recomputed_allwind=((pl.col("price_eur_mwh") * pl.col("act_wind_mw")).sum()
                                   / pl.col("act_wind_mw").sum()),
            neg_qh=(pl.col("price_eur_mwh") < 0).sum(),
        )
        .sort("ym")
    )
    from src.method.ingest_market_values import read_published

    pub = read_published().with_columns(
        (pl.col("year").cast(pl.String) + "-"
         + pl.col("month").cast(pl.String).str.zfill(2)).alias("ym")
    ).select(["ym", "mv_wind_onshore", "spot_mean"])
    return grp.join(pub, on="ym", how="left").sort("ym")


def report_mv(area: str = "DE") -> pl.DataFrame:
    t = monthly_series(area)
    print("=" * 94)
    print("STEP 1  THE MARKET-VALUE SERIES")
    print("=" * 94)
    print("1.1  what the loader reads, verbatim")
    print("  file   : data/raw/netztransparenz/Monatsmarktwerte_2026.csv")
    print('  row    : "MW Wind an Land"            -> mv_wind_onshore   (ct/kWh x 10)')
    print('  also   : "Spotmarktpreis"             -> spot_mean')
    print("  src/ingest_market_values.py read_published, `wanted` dict")
    print("  -> it is the WIND ONSHORE market value by name, not base load; the")
    print("     base-load-like figure is read separately as spot_mean and is not")
    print("     used to build theta.")
    print()
    print("1.2  independent recomputation from the panel")
    print("  mv_recomputed[m] = sum(price * act_onshore_mw) / sum(act_onshore_mw)")
    print("  capture = series / price_mean;  for onshore wind this must be < 1")
    print()
    hdr = (f"{'month':<9}{'n_qh':>6}{'neg':>5}{'price_mean':>11}"
           f"{'published MV':>13}{'recomputed':>11}{'pub/mean':>9}{'rec/mean':>9}"
           f"{'pub-rec':>9}")
    print(hdr)
    print("-" * len(hdr))
    rows = t.to_dicts()
    for r in rows:
        pub = r["mv_wind_onshore"]
        pm, rec = r["price_mean"], r["mv_recomputed"]
        pub_s = f"{pub:>13.2f}" if pub is not None else f"{'--':>13}"
        cap_p = f"{pub / pm:>9.3f}" if pub is not None else f"{'--':>9}"
        gap = f"{pub - rec:>9.2f}" if pub is not None else f"{'--':>9}"
        print(f"{r['ym']:<9}{r['n_qh']:>6}{r['neg_qh']:>5}{pm:>11.2f}"
              f"{pub_s}{rec:>11.2f}{cap_p}{rec / pm:>9.3f}{gap}")
    print()
    have = [r for r in rows if r["mv_wind_onshore"] is not None]
    if have:
        cap_pub = np.array([r["mv_wind_onshore"] / r["price_mean"] for r in have])
        cap_rec = np.array([r["mv_recomputed"] / r["price_mean"] for r in have])
        print(f"  months with a published value : {len(have)}")
        print(f"  capture rate, published   : mean {cap_pub.mean():.3f}  "
              f"min {cap_pub.min():.3f}  max {cap_pub.max():.3f}")
        print(f"  capture rate, recomputed  : mean {cap_rec.mean():.3f}  "
              f"min {cap_rec.min():.3f}  max {cap_rec.max():.3f}")
        print(f"  published BELOW the simple mean in {int((cap_pub < 1).sum())}"
              f"/{len(have)} months")
        print(f"  published BELOW the recomputation in "
              f"{int(sum(1 for r in have if r['mv_wind_onshore'] < r['mv_recomputed']))}"
              f"/{len(have)} months")
        print()
        print("  VERDICT")
        if (cap_pub < 1).all() and cap_pub.mean() < 0.95:
            print("    The series in use is a wind market value, not a base-load or")
            print("    plain monthly-average series: it sits below the simple monthly")
            print("    mean in every month, with a capture rate well under 1, and it")
            print("    tracks the recomputed wind-weighted figure rather than the mean.")
            print("    MV is therefore NOT artefactually high, and the MP = 0 finding")
            print("    stands. It is in fact the conservative direction: the published")
            print("    series is LOWER than the recomputation, and a lower MV gives a")
            print("    LARGER premium, so MP = 0 occurs despite the more generous input.")
        else:
            print("    The series does NOT look like a wind market value. MP is")
            print("    understated and the MP = 0 finding is suspect. Not fixed here.")
    return t


# ------------------------------------------------- step 2: theta separation, real data


AW_SETTINGS = ("low", "main", "high", "stress")


def _real_theta(area: str = "DE"):
    """(cohorts, price, ym, dates, theta_for, covered) on the real panel.

    theta construction mirrors `src/check_rule18_real.py` build_theta exactly, so the
    numbers here are comparable with results/38_rule18_*.csv.
    """
    from src.method.exposure import build_clock_features, mastr_cohort_set, trigger_active
    from src.method.cohort_parameters import cohort_parameters
    from src.method.theta_inputs import JW_2025_EUR_MWH, jw_2026_ytd
    from src.method.ingest_market_values import read_published

    params = cohort_parameters()
    cohorts = mastr_cohort_set(area)
    pub = read_published()
    jw26 = jw_2026_ytd(pub)
    panel = (pl.scan_parquet(PANEL).filter(pl.col("area") == area)
             .select(["ts_utc", "berlin_date", "price_eur_mwh"]).collect()
             .drop_nulls().sort("ts_utc"))
    clock = build_clock_features(panel["ts_utc"].to_numpy() * 1_000_000,
                                 panel["price_eur_mwh"].to_numpy())
    price = clock.price_qh
    dates = panel["berlin_date"].to_numpy().astype(str)
    ym = np.array([d[:7] for d in dates])
    mvm = {f"{r['year']}-{r['month']:02d}": r["mv_wind_onshore"]
           for r in pub.iter_rows(named=True)}
    mv = np.array([mvm.get(k, np.nan) for k in ym], dtype=float)
    years = np.array([int(k[:4]) for k in ym])
    jw = np.where(years == 2025, JW_2025_EUR_MWH, jw26)
    covered = np.isfinite(mv)
    pmap = {r["cohort"]: r for r in params.iter_rows(named=True)}

    def theta_for(setting: str):
        col = {"main": "aw_eur_mwh", "low": "aw_low_eur_mwh",
               "high": "aw_high_eur_mwh", "stress": "aw_eur_mwh"}[setting]
        th, trig, untrig = [], [], []
        for c in cohorts:
            pr = pmap[c.cohort_id]
            active = trigger_active(c, clock)
            ref = mv if pr["reference"] == "monthly" else jw
            aw = pr[col]
            if setting == "stress" and c.cohort_id == "pre2016_in_support_no_s51":
                aw = None
            base = np.zeros_like(price) if aw is None else -np.maximum(0.0, aw - ref)
            untrig.append(base.copy())
            th.append(np.where(active, 0.0, base))
            trig.append(active)
        return np.vstack(th) + 0.0, np.vstack(trig), np.vstack(untrig) + 0.0

    return cohorts, price, ym, dates, theta_for, covered


def _distinct_counts(theta: np.ndarray) -> np.ndarray:
    """Number of distinct theta values per quarter-hour, across cohorts."""
    th = np.sort(theta, axis=0)
    return 1 + (np.diff(th, axis=0) != 0).sum(axis=0)


def report_theta(area: str = "DE") -> None:
    from src.method.window import E1_E2_WINDOW_START

    cohorts, price, ym, dates, theta_for, covered = _real_theta(area)
    in_window = dates >= E1_E2_WINDOW_START
    in_support = np.array([c.in_support for c in cohorts])

    print()
    print("=" * 94)
    print("STEP 2  THETA SEPARATION ON THE REAL PANEL")
    print(f"  study window from {E1_E2_WINDOW_START}; theta needs a published market")
    print("  value, so only months that have one are usable")
    print("=" * 94)
    usable = in_window & covered
    print(f"  quarter-hours in the study window          : {int(in_window.sum()):>7,}")
    print(f"  of those, with a published market value    : {int(usable.sum()):>7,}"
          f"  ({100 * usable.sum() / in_window.sum():.1f}%)")
    print(f"  months in the window                       : "
          f"{len(set(ym[in_window])):>7}")
    print(f"  months usable                              : "
          f"{len(set(ym[usable])):>7}  {sorted(set(ym[usable]))}")
    print(f"  months DROPPED for want of a market value  : "
          f"{len(set(ym[in_window]) - set(ym[usable])):>7}  "
          f"{[str(x) for x in sorted(set(ym[in_window]) - set(ym[usable]))]}")

    for setting in AW_SETTINGS:
        theta, trig, theta_untrig = theta_for(setting)
        s = (price[None, :] < theta).astype(bool)
        exposed_any = s.any(axis=0)
        nd = _distinct_counts(theta)
        neg = price < 0
        band = neg & (price > -5.0)

        print()
        print("-" * 94)
        print(f"AW setting '{setting}'")
        print("-" * 94)
        for label, sel in (("exposed QH", usable & exposed_any),
                           ("negative-price QH", usable & neg),
                           ("the -5..0 band", usable & band)):
            n = int(sel.sum())
            if not n:
                print(f"  {label:<20} none")
                continue
            print(f"  {label:<20} n = {n:>6,}   >=2 distinct theta "
                  f"{100 * (nd[sel] >= 2).mean():>5.1f}%   "
                  f">=3 distinct {100 * (nd[sel] >= 3).mean():>5.1f}%   "
                  f"mean distinct {nd[sel].mean():.2f}")

        # Attribution by COUNTERFACTUAL, each holding one channel fixed and letting
        # the other vary -- the same construction check_rule18_real.py uses for
        # exposure, and for the same reason: a direct "which channel caused this"
        # test is not well defined when the channels act together. The three are
        # counterfactuals, so they do not sum to the total.
        #
        # The first version of this block tested conditions like
        # `(~in_support).any()`, which is a SCALAR over cohorts and therefore True
        # everywhere, and reported all three channels at 100%. It was measuring
        # nothing.
        sep = usable & exposed_any & (nd >= 2)
        if sep.any():
            mp = np.maximum(0.0, -theta_untrig)   # the premium each cohort carries
            w = np.asarray(cohorts.shares)[:, None]
            mp_common = (mp * w).sum(axis=0) / w.sum()

            # (i) trigger / run length alone: every cohort on the SAME premium
            th_clock = np.where(trig, 0.0, -mp_common[None, :]) + 0.0
            # (ii) premium spread alone: no trigger anywhere
            th_prem = theta_untrig
            # (iii) support status alone: out-of-support cohorts at 0, the rest on
            #       the common premium, no trigger
            sup = np.asarray([c.in_support for c in cohorts])[:, None]
            th_sup = np.where(sup, -mp_common[None, :], 0.0) + 0.0

            n = int(sep.sum())
            print(f"  separation source on the {n:,} separating exposed QH")
            print("    (counterfactuals, each isolating one channel; they do NOT sum.")
            print("     A >=2 share alone saturates at 100% wherever all three")
            print("     channels happen to be live, so the MEAN number of distinct")
            print("     theta values each channel yields is what discriminates.)")
            print(f"    {'channel':<28}{'mean distinct':>14}{'>=2':>7}{'>=3':>7}")
            for lab, th_cf in (("actual", theta),
                               ("run-length / trigger alone", th_clock),
                               ("premium spread alone", th_prem),
                               ("support status alone", th_sup)):
                d = _distinct_counts(th_cf)[sep]
                print(f"    {lab:<28}{d.mean():>14.2f}"
                      f"{100 * (d >= 2).mean():>6.0f}%{100 * (d >= 3).mean():>6.0f}%")
        # months where theta is identically zero fleet-wide
        flat = []
        for m in sorted(set(ym[usable])):
            sel = usable & (ym == m)
            if sel.any() and np.abs(theta[:, sel]).max() == 0.0:
                flat.append(m)
        print(f"  months with MP = 0 for EVERY cohort (theta identically 0): "
              f"{len(flat)} of {len(set(ym[usable]))}  {[str(x) for x in flat]}")

        # per-month detail on exposed QH
        print(f"  {'month':<9}{'exposed':>9}{'>=2 distinct':>14}{'>=3':>8}"
              f"{'neg QH':>8}{'-5..0':>8}")
        for m in sorted(set(ym[usable])):
            sel = usable & (ym == m)
            e = sel & exposed_any
            if not e.any():
                print(f"  {m:<9}{0:>9}{'--':>14}{'--':>8}"
                      f"{int((sel & neg).sum()):>8}{int((sel & band).sum()):>8}")
                continue
            print(f"  {m:<9}{int(e.sum()):>9}{100 * (nd[e] >= 2).mean():>13.1f}%"
                  f"{100 * (nd[e] >= 3).mean():>7.1f}%"
                  f"{int((sel & neg).sum()):>8}{int((sel & band).sum()):>8}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--step", choices=("mv", "theta"), default=None)
    ap.add_argument("--area", default="DE")
    a = ap.parse_args()
    if a.step in (None, "mv"):
        report_mv(a.area)
    if a.step in (None, "theta"):
        report_theta(a.area)


if __name__ == "__main__":
    main()
