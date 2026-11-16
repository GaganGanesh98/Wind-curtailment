"""Step 4.3b: can block geometry be tuned to match the real event-day share?
Also: how does the cohort-exposure difference decompose by direction?"""
import sys
sys.path.insert(0, "src")
import numpy as np, pandas as pd
from e1_generator import (E1Config, ResponseSpec, default_cohorts, generate,
                          parse_panel_spec)

PANEL = "/Users/gagan/msc-thesis-wind-curtailment/data/processed/panel_qh.parquet"
COLS = parse_panel_spec("timestamp=ts_utc_dt,actual_mw=act_wind_mw,forecast_mw=da_wind_mw")
full = pd.read_parquet(PANEL)
de = full.loc[full.area == "DE"].copy()

print("=" * 78)
print("A. REAL EVENT-DAY GEOMETRY (DE, full panel)")
print("=" * 78)
s = full.loc[full.area == "DE"]
neg = s.loc[s.price_eur_mwh < 0]
per_day = neg.groupby("berlin_date").size()
qh_per_day = s.groupby("berlin_date").size()
print(f"  event-days                        : {len(per_day)} / {s.berlin_date.nunique()}"
      f"  = {100*len(per_day)/s.berlin_date.nunique():.1f}%")
print(f"  negative QH overall               : {100*(s.price_eur_mwh<0).mean():.2f}%")
print(f"  negative QH per event-day: mean {per_day.mean():.1f}  median {per_day.median():.0f}"
      f"  p90 {per_day.quantile(0.9):.0f}  max {per_day.max()}")
print(f"  within-event-day negative share   : mean {100*per_day.mean()/96:.1f}% of the day")
print(f"  identity check: 0.274 x {per_day.mean()/96:.3f} = "
      f"{0.274*per_day.mean()/96:.4f}  (vs observed {(s.price_eur_mwh<0).mean():.4f})")

print()
print("=" * 78)
print("B. GEOMETRY SWEEP (DE, gamma 0.5, logistic, seed 42)")
print("   rate = event_day_share x within_day_negative_share  -- an identity,")
print("   so with max_day_fraction fixed at 0.6 the reachable region is bounded.")
print("=" * 78)
print(f"{'rate':>5} {'blk_med':>8} {'p_2nd':>6} {'realised':>9} {'intens':>7} "
      f"{'ev_share':>9} {'neg/ev_day':>11} {'within_day':>11}")
recs = []
for rate in (0.05, 0.10, 0.20, 0.40):
    for blk, p2 in ((12, 0.25), (24, 0.25), (24, 0.60), (40, 0.60), (60, 0.80)):
        cfg = E1Config(censoring_rate=rate, gamma=0.5,
                       response=ResponseSpec(shape="logistic"), seed=42,
                       block_len_qh_median=blk, p_second_block=p2)
        df, d = generate(de, cfg, COLS)
        ev = df.loc[df.price_negative == 1]
        nd = ev.day_local.nunique()
        per = ev.groupby("day_local").size()
        qhd = df.groupby("day_local").size().mean()
        within = per.mean() / qhd if nd else 0.0
        recs.append(dict(rate=rate, blk=blk, p2=p2, realised=d["realised_rate"],
                         intensity=d["intensity"], ev_share=nd/d["n_days_available"],
                         within=within, energy=d["energy_censored_share"],
                         sep_days=d["cohort_exposure_differs_days"]))
        print(f"{rate:>5.2f} {blk:>8} {p2:>6.2f} {d['realised_rate']:>9.4f} "
              f"{d['intensity']:>7.3f} {100*nd/d['n_days_available']:>8.1f}% "
              f"{per.mean():>11.1f} {100*within:>10.1f}%")
pd.DataFrame(recs).to_csv("data/e1/e1_step4_geometry_sweep.csv", index=False)

print()
print("=" * 78)
print("C. DECOMPOSITION OF COHORT-EXPOSURE DIFFERENCE (DE, 0.20/0.5/logistic/s42)")
print("=" * 78)
cfg = E1Config(censoring_rate=0.20, gamma=0.5,
               response=ResponseSpec(shape="logistic"), seed=42)
df, d = generate(de, cfg, COLS)
qh_c, hr_c = default_cohorts()
sq, sh = df[f"s_{qh_c.name}"].to_numpy(), df[f"s_{hr_c.name}"].to_numpy()
print(f"  both exposed                 : {int(((sq==1)&(sh==1)).sum()):>7,}")
print(f"  QH-clock only (hourly not)   : {int(((sq==1)&(sh==0)).sum()):>7,}   <- plentiful")
print(f"  hourly-clock only (QH not)   : {int(((sq==0)&(sh==1)).sum()):>7,}   <- THIN")
print(f"  neither                      : {int(((sq==0)&(sh==0)).sum()):>7,}")
print(f"  total differing QH            : {int((sq!=sh).sum()):>7,}  "
      f"on {int(df.loc[sq!=sh,'day_local'].nunique())} days")
print("\n  The 'differs on 403 days' figure is dominated by the QH-only direction.")
print("  Unique identification of the HOURLY cohort comes only from the thin set.")


# ---- fine sweep at rate 0.05 (the only rate with a real analogue) ----
TGT_EV, TGT_WI = 0.274, 0.220

print("rate 0.05, gamma 0.5, logistic; averaged over seeds 42,43,44")
print(f"{'blk':>4} {'p2':>5} {'ev_share':>9} {'within':>8} {'|d_ev|':>7} {'|d_wi|':>7} {'joint':>7}")
best = []
for blk in (8, 10, 12, 14, 16, 20):
    for p2 in (0.10, 0.25, 0.40):
        evs, wis = [], []
        for seed in (42, 43, 44):
            cfg = E1Config(censoring_rate=0.05, gamma=0.5,
                           response=ResponseSpec(shape="logistic"), seed=seed,
                           block_len_qh_median=blk, p_second_block=p2)
            df, d = generate(de, cfg, COLS)
            ev = df.loc[df.price_negative == 1]
            nd = ev.day_local.nunique()
            evs.append(nd / d["n_days_available"])
            wis.append(ev.groupby("day_local").size().mean()
                       / df.groupby("day_local").size().mean())
        ev_m, wi_m = float(np.mean(evs)), float(np.mean(wis))
        d_ev, d_wi = abs(ev_m - TGT_EV), abs(wi_m - TGT_WI)
        joint = np.hypot(d_ev / TGT_EV, d_wi / TGT_WI)
        best.append((joint, blk, p2, ev_m, wi_m))
        print(f"{blk:>4} {p2:>5.2f} {100*ev_m:>8.1f}% {100*wi_m:>7.1f}% "
              f"{100*d_ev:>6.1f}pp {100*d_wi:>6.1f}pp {joint:>7.3f}")
best.sort()
print(f"\nbest joint fit: block_len_qh_median={best[0][1]}, p_second_block={best[0][2]} "
      f"-> ev {100*best[0][3]:.1f}% / within {100*best[0][4]:.1f}%  (joint {best[0][0]:.3f})")
print(f"current default (12, 0.25) joint distance = "
      f"{[b[0] for b in best if b[1]==12 and b[2]==0.25][0]:.3f}")
