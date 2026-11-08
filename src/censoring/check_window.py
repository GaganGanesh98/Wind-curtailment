"""Step F: is the quarter-hour price just the hourly price repeated before 1 Oct 2025?"""
import sys
sys.path.insert(0, ".")
import numpy as np, polars as pl

df = (pl.scan_parquet("data/processed/panel_qh.parquet")
      .filter(pl.col("area") == "DE")
      .select(["ts_utc", "berlin_date", "price_eur_mwh"]).collect().sort("ts_utc"))
n = df.height
price = df["price_eur_mwh"].to_numpy()
date = df["berlin_date"].to_numpy()
# group into calendar hours of 4 QH; the series is contiguous 15-min
assert n % 4 == 0, n
h_price = price.reshape(-1, 4)
h_date = date.reshape(-1, 4)[:, 0]
flat = np.ptp(h_price, axis=1) == 0.0          # all four QH identical
spread = np.ptp(h_price, axis=1)

print(f"DE panel: {n:,} QH = {h_price.shape[0]:,} calendar hours")
print(f"range {date[0]} .. {date[-1]}")
print()
print(f"{'window':<34}{'hours':>9}{'flat hours':>12}{'share flat':>12}"
      f"{'mean spread':>13}")
for label, sel in (
    ("ALL", np.ones_like(h_date, bool)),
    ("before 2025-10-01", h_date < "2025-10-01"),
    ("from 2025-10-01 (study window)", h_date >= "2025-10-01"),
    ("  2025-09 (last month before)", (h_date >= "2025-09-01") & (h_date < "2025-10-01")),
    ("  2025-10 (first month after)", (h_date >= "2025-10-01") & (h_date < "2025-11-01")),
):
    k = int(sel.sum())
    f = int(flat[sel].sum())
    print(f"{label:<34}{k:>9,}{f:>12,}{100*f/k:>11.2f}%{spread[sel].mean():>13.3f}")

pre = h_date < "2025-10-01"
post = ~pre
print()
print(f"  before 1 Oct 2025: {100*flat[pre].mean():.2f}% of hours have all four")
print(f"    quarter-hour prices IDENTICAL -> no sub-hourly day-ahead variation.")
print(f"  from 1 Oct 2025 : {100*flat[post].mean():.2f}% flat.")
# the decisive consequence: can theta=0 and theta=-MP cohorts ever separate?
print()
print("  Consequence for identification. With a flat hour, a quarter-hour is")
print("  negative iff its hourly mean is negative, so the quarter-hour clock and")
print("  the hourly clock coincide and the only remaining separation is the")
print("  MP spread (depth thresholds), not the clock.")
for label, sel in (("before 2025-10-01", pre), ("from 2025-10-01", post)):
    neg_qh = (h_price < 0).any(axis=1) & sel
    # hours where SOME but not all QH are negative = sub-hourly sign variation
    mixed = ((h_price < 0).any(axis=1) & ~(h_price < 0).all(axis=1)) & sel
    print(f"    {label:<20} hours with any negative QH: {int(neg_qh.sum()):>6,}"
          f"   of those, MIXED sign within the hour: {int(mixed.sum()):>5,}"
          f" ({100*mixed.sum()/max(1,neg_qh.sum()):.1f}%)")
