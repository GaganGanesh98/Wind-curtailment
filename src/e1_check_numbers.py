"""Step 4: the three numbers that decide E1 viability on real data."""
import sys
sys.path.insert(0, "src")
import pandas as pd
from e1_generator import (E1Config, ResponseSpec, default_cohorts, generate,
                          parse_panel_spec)

PANEL = "/Users/gagan/msc-thesis-wind-curtailment/data/processed/panel_qh.parquet"
COLS = parse_panel_spec("timestamp=ts_utc_dt,actual_mw=act_wind_mw,forecast_mw=da_wind_mw")
AREAS = ["DE", "50Hertz", "Amprion"]
full = pd.read_parquet(PANEL)

print("=" * 78)
print("STEP 4.1  I4 SEPARABILITY   (rate 0.20, gamma 0.5, logistic, seed 42)")
print("=" * 78)
print(f"{'area':<10} {'days_differ':>12} {'qh_differ':>11} {'event_days':>11} "
      f"{'thresh':>7} {'verdict':>8}")
frames = {}
for a in AREAS:
    p = full.loc[full.area == a].copy()
    cfg = E1Config(censoring_rate=0.20, gamma=0.5,
                   response=ResponseSpec(shape="logistic"), seed=42)
    df, diag = generate(p, cfg, COLS)
    frames[a] = (df, diag)
    s_cols = [f"s_{c.name}" for c in default_cohorts()]
    arr = df[s_cols].to_numpy()
    differ = arr.max(axis=1) != arr.min(axis=1)
    n_days = int(df.loc[differ, "day_local"].nunique())
    print(f"{a:<10} {n_days:>12,} {int(differ.sum()):>11,} "
          f"{diag['n_event_days']:>11,} {10:>7} "
          f"{'PASS' if n_days >= 10 else 'FAIL':>8}")

print()
print("=" * 78)
print("STEP 4.2  IDENTIFYING VARIATION IN THE THIN DIRECTION")
print("  rows with: QH price >= 0  AND  hourly mean < 0  AND  hourly cohort exposed")
print("=" * 78)
hourly = [c for c in default_cohorts() if c.clock == "hourly"][0]
print(f"{'area':<10} {'thin_rows':>10} {'of_n_rows':>11} {'share':>9} "
      f"{'thin_days':>10} {'qh>=0 & c>0':>12}")
for a in AREAS:
    df, diag = frames[a]
    thin = ((df["price_eur_mwh"] >= 0)
            & (df["price_hourly_mean_eur_mwh"] < 0)
            & (df[f"s_{hourly.name}"] == 1))
    loose = int(((df["price_eur_mwh"] >= 0) & (df["c_true"] > 0)).sum())
    print(f"{a:<10} {int(thin.sum()):>10,} {len(df):>11,} "
          f"{100*thin.mean():>8.4f}% {int(df.loc[thin,'day_local'].nunique()):>10,} "
          f"{loose:>12,}")
print("\n  stand-in panel reference: 7 rows")

print()
print("=" * 78)
print("STEP 4.3  EVENT-DAY REALISM  (gamma 0.5, logistic, seed 42)")
print("=" * 78)
print("--- real panel, for comparison (full panel, any negative QH = event-day) ---")
for a in AREAS:
    s = full.loc[full.area == a]
    neg = s.loc[s.price_eur_mwh < 0]
    nd, tot = neg.berlin_date.nunique(), s.berlin_date.nunique()
    print(f"  {a:<10} {nd:>4} event-days / {tot:>4} days = {100*nd/tot:>5.1f}%   "
          f"negative QH share = {100*(s.price_eur_mwh<0).mean():.2f}%")

print("\n--- generator, as it stands (block_len_qh_median=12, p_second_block=0.25) ---")
print(f"{'area':<10} {'rate':>6} {'realised':>9} {'intensity':>10} "
      f"{'event_days':>11} {'avail':>6} {'ev_share':>9} {'energy':>8}")
rows = []
for a in AREAS:
    p = full.loc[full.area == a].copy()
    for r in (0.05, 0.10, 0.20, 0.30, 0.40):
        cfg = E1Config(censoring_rate=r, gamma=0.5,
                       response=ResponseSpec(shape="logistic"), seed=42)
        _, d = generate(p, cfg, COLS)
        share = d["n_event_days"] / d["n_days_available"]
        rows.append(dict(area=a, target=r, **d, event_day_share=round(share, 4)))
        print(f"{a:<10} {r:>6.2f} {d['realised_rate']:>9.4f} "
              f"{d['intensity']:>10.3f} {d['n_event_days']:>11,} "
              f"{d['n_days_available']:>6,} {100*share:>8.1f}% "
              f"{d['energy_censored_share']:>8.4f}")
pd.DataFrame(rows).to_csv(
    "data/e1/e1_step4_eventdays.csv",
    index=False)
