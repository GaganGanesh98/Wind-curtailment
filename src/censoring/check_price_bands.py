"""Verify the price-band and window figures docs/16 quotes as fact.

Three claims, all checked on the real DE panel:

  1. "1,461 of 2,059 negative quarter-hours sit in -5 to 0 EUR/MWh" -- correct, with
     the band OPEN at -5. Exactly 8 quarter-hours sit at -5.00, so the half-open
     [-5, 0) reading gives 1,469. The two differ by more than rounding, so the
     convention has to be stated wherever the figure is quoted. And -5..0 really is
     the most populated band, in every window tested.
  2. "393 days, 99 event-days" for the E1/E2 window -- exact.
  3. "Nothing in src/censoring/ currently computes rank or conditioning" -- no longer
     true; identification.py does.

Note the denominator: 2,059 negative quarter-hours is the E1/E2 window total (from
2025-10-01). The rule-18 evaluation window, restricted to months with a published
market value, has 1,853 -- which is what results/38_rule18_real.csv records as
negative_qh_covered against negative_qh_total = 2059.
"""
import sys
sys.path.insert(0, ".")
import numpy as np, polars as pl
from src.censoring.cohorts import build_clock_features, mastr_cohort_set, trigger_active
from src.censoring.window import E1_E2_WINDOW_START
from src.ingest_market_values import read_published

panel = (pl.scan_parquet("data/processed/panel_qh.parquet")
         .filter(pl.col("area") == "DE")
         .select(["ts_utc", "berlin_date", "price_eur_mwh"]).collect()
         .with_columns(pl.col("berlin_date").str.strptime(pl.Date, "%Y-%m-%d").alias("d"))
         .drop_nulls().sort("ts_utc"))
panel = panel.with_columns(pl.col("d").dt.year().alias("y"), pl.col("d").dt.month().alias("m"))
price_all = panel["price_eur_mwh"].to_numpy()
ym = list(zip(panel["y"].to_list(), panel["m"].to_list()))
have = {(r["year"], r["month"]) for r in read_published().iter_rows(named=True)}
cov = np.array([k in have for k in ym])
dates = panel["berlin_date"].to_numpy()

print("CLAIM 1: 'the kill test shows that band is the most populated")
print("          (1,461 of 2,059 negative quarter-hours sit in -5 to 0 EUR/MWh)'")
print("  results/38_rule18_real.csv records negative_qh_total = 2059,")
print("  negative_qh_covered = 1853 -- so 2,059 is the rule-18 window's total.\n")
for label, sel in (("rule-18 window (months with a published MV)", cov),
                   ("E1/E2 window (from 2025-10-01)", dates >= E1_E2_WINDOW_START),
                   ("whole panel on disk", np.ones_like(cov))):
    p = price_all[sel]
    neg = p < 0
    band = neg & (p >= -5.0)
    print(f"  {label}")
    print(f"    negative QH          = {int(neg.sum()):>6,}")
    print(f"    of those in [-5, 0)  = {int(band.sum()):>6,}  "
          f"({100*band.sum()/max(1,neg.sum()):.1f}%)")
    # is it really the MOST populated band?
    edges = [-np.inf, -100, -50, -20, -10, -5, 0]
    names = ["< -100", "-100..-50", "-50..-20", "-20..-10", "-10..-5", "-5..0"]
    counts = [int(((p >= lo) & (p < hi)).sum()) for lo, hi in zip(edges[:-1], edges[1:])]
    top = names[int(np.argmax(counts))]
    print(f"    by band: " + "  ".join(f"{n}={c:,}" for n, c in zip(names, counts)))
    print(f"    most populated band  = {top}\n")

print("CLAIM 2: 'Use the study window from 1 Oct 2025 (393 days, 99 event-days)'")
w = dates >= E1_E2_WINDOW_START
sub = price_all[w]
nd = len(set(dates[w]))
evd = len(set(dates[w][sub < 0]))
print(f"  days in window = {nd}   event-days (any negative QH) = {evd}")
print(f"  -> matches '393 days, 99 event-days': {nd == 393 and evd == 99}")

print("\nCLAIM 3: 'Nothing in src/censoring/ currently computes rank or conditioning.'")
import subprocess
r = subprocess.run(["grep", "-rln", "matrix_rank\\|cond(", "src/censoring/"],
                   capture_output=True, text=True)
print("  files that now do:", r.stdout.split() or "none")
