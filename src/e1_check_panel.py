"""Step 1: inspect the real panel. Read-only."""
import os
import pandas as pd
import pyarrow.parquet as pq

PANEL = "/Users/gagan/msc-thesis-wind-curtailment/data/processed/panel_qh.parquet"

print("=" * 78)
print("STEP 1 - REAL PANEL INSPECTION")
print("=" * 78)
print(f"full path   : {PANEL}")
print(f"file size   : {os.path.getsize(PANEL):,} bytes "
      f"({os.path.getsize(PANEL)/1e6:.1f} MB)")

pf = pq.ParquetFile(PANEL)
print(f"row count   : {pf.metadata.num_rows:,}")
print(f"row groups  : {pf.metadata.num_row_groups}")

df = pd.read_parquet(PANEL)
print(f"loaded shape: {df.shape}")

print("\n--- columns and dtypes ---")
for c in df.columns:
    print(f"  {c:<22} {str(df[c].dtype):<22} nulls={df[c].isna().sum():>8,}")

print("\n--- timestamp columns ---")
for c in ("ts_utc", "ts_utc_dt"):
    s = df[c]
    print(f"  {c}: dtype={s.dtype}  min={s.min()}  max={s.max()}")
    tz = getattr(s.dtype, "tz", None)
    print(f"      timezone-aware? {tz is not None}   tz={tz!r}")

# is ts_utc epoch ms consistent with ts_utc_dt?
recon = pd.to_datetime(df["ts_utc"], unit="ms")
print(f"  ts_utc (as epoch ms) == ts_utc_dt ? {bool((recon == df['ts_utc_dt']).all())}")
print(f"  ts_utc_dt spacing (unique diffs within area DE): "
      f"{sorted(df.loc[df.area=='DE','ts_utc_dt'].sort_values().diff().dropna().unique())[:3]}")

print("\n--- distinct area values ---")
print(df["area"].value_counts().to_string())

print("\n--- summary stats: wind actual / DA forecast / price, by area ---")
for col in ("act_wind_mw", "da_wind_mw", "price_eur_mwh"):
    print(f"\n  == {col} ==")
    g = df.groupby("area")[col].describe(percentiles=[0.5, 0.99])
    print(g[["count", "mean", "std", "min", "50%", "99%", "max"]].to_string(
        float_format=lambda v: f"{v:,.1f}"))

print("\n--- MW sanity check (DE wind actual should peak ~40 GW, not ~10 GW) ---")
de = df[df.area == "DE"]
print(f"  DE act_wind_mw   max = {de['act_wind_mw'].max():,.0f} MW "
      f"= {de['act_wind_mw'].max()/1000:,.1f} GW")
print(f"  DE act_wind_mw  p99 = {de['act_wind_mw'].quantile(0.99):,.0f} MW")
print(f"  DE act_wind_mw mean = {de['act_wind_mw'].mean():,.0f} MW")
print(f"  DE da_wind_mw    max = {de['da_wind_mw'].max():,.0f} MW")

print("\n--- E1 base: rows with price > 5 EUR/MWh, by area ---")
clean = df[df["price_eur_mwh"] > 5.0]
tot = df.groupby("area").size()
cl = clean.groupby("area").size()
nn = clean.dropna(subset=["act_wind_mw", "da_wind_mw"]).groupby("area").size()
out = pd.DataFrame({"rows_total": tot, "rows_price_gt_5": cl,
                    "and_wind_nonnull": nn})
out["pct_clean"] = (100 * out["rows_price_gt_5"] / out["rows_total"]).round(1)
print(out.to_string())

print("\n--- distinct Berlin-local days covered by the clean rows, by area ---")
d = clean.groupby("area")["berlin_date"].nunique().rename("clean_days")
dall = df.groupby("area")["berlin_date"].nunique().rename("days_in_panel")
dd = pd.concat([dall, d], axis=1)
# also: days with >= 88 clean QH (the generator's min_qh_per_day default)
cnt = clean.groupby(["area", "berlin_date"]).size()
dd["days_ge_88_clean_qh"] = cnt[cnt >= 88].reset_index().groupby("area").size()
dd["days_ge_88_clean_qh"] = dd["days_ge_88_clean_qh"].fillna(0).astype(int)
print(dd.to_string())

print("\n--- negative-price reality check (for step 4.3 event-day realism) ---")
for a in ("DE", "50Hertz", "Amprion"):
    s = df[df.area == a]
    neg = s[s["price_eur_mwh"] < 0]
    print(f"  {a:<10} negative QH = {len(neg):>6,}  "
          f"({100*len(neg)/len(s):.2f}%)   "
          f"event-days = {neg['berlin_date'].nunique():>4} / "
          f"{s['berlin_date'].nunique()} days "
          f"({100*neg['berlin_date'].nunique()/s['berlin_date'].nunique():.1f}%)")
