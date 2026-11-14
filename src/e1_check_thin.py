"""Is the thin direction thin everywhere, or only at rate 0.20?"""
import sys
sys.path.insert(0, "src")
import pandas as pd
from e1_generator import E1Config, ResponseSpec, default_cohorts, generate, parse_panel_spec

COLS = parse_panel_spec("timestamp=ts_utc_dt,actual_mw=act_wind_mw,forecast_mw=da_wind_mw")
full = pd.read_parquet("/Users/gagan/msc-thesis-wind-curtailment/data/processed/panel_qh.parquet")
qh_c, hr_c = default_cohorts()

print("hourly-clock-only exposure (the thin direction) vs QH-clock-only, DE, logistic, seed 42")
print(f"{'rate':>6} {'gamma':>6} {'both':>8} {'qh_only':>9} {'hourly_only':>12} {'thin_days':>10}")
de = full.loc[full.area == "DE"].copy()
for rate in (0.05, 0.10, 0.20, 0.30, 0.40):
    for gam in (0.0, 0.5, 1.0):
        cfg = E1Config(censoring_rate=rate, gamma=gam,
                       response=ResponseSpec(shape="logistic"), seed=42)
        df, d = generate(de, cfg, COLS)
        sq = df[f"s_{qh_c.name}"].to_numpy(); sh = df[f"s_{hr_c.name}"].to_numpy()
        thin = (sq == 0) & (sh == 1)
        print(f"{rate:>6.2f} {gam:>6.1f} {int(((sq==1)&(sh==1)).sum()):>8,} "
              f"{int(((sq==1)&(sh==0)).sum()):>9,} {int(thin.sum()):>12,} "
              f"{int(df.loc[thin,'day_local'].nunique()):>10,}")

print("\nper-shape conversion: realised QH rate -> energy share (grid means)")
t = pd.read_csv("data/e1/e1_grid_diagnostics.csv")
for shape in ("step", "logistic", "half"):
    s = t[t.response_shape == shape]
    g = s.groupby("target_rate").agg(qh=("realised_rate", "mean"),
                                     en=("energy_censored_share", "mean"))
    g["ratio"] = (g.en / g.qh).round(3)
    print(f"\n  {shape}:")
    print(g.to_string(float_format=lambda v: f"{v:.4f}"))
