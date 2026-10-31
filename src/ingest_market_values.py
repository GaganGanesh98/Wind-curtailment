"""Monthly market value MV_m for wind onshore: recomputed, and validated.

    python src/ingest_market_values.py

Rule 17 / spec section 3: **the published monthly market value is never a T2
input.** Netztransparenz releases it after the month ends, so using it to build
theta in a day-ahead model leaks. T2 therefore recomputes it from SMARD data
available by D-1, month-to-date, and the published series is used only to check
that the recomputation is right.

Definition (EEG Anlage 1 no. 3.3.2, "tatsaechlicher Monatsmarktwert"): the
generation-weighted average spot price over the month,

    MV_m = sum_t (price_t * wind_onshore_t) / sum_t wind_onshore_t

computed here on the quarter-hour panel, which is the resolution the spot market
has settled in since 1 Oct 2025.

Which resolution applies in which period (block 5, 1 Nov 2026)
--------------------------------------------------------------
From `marktwertberechnung_umstellung.pdf` (Netztransparenz, archived in data/raw),
**page 1**, section "Gesetzliche Grundlage":

* **Legal basis: EEG §100(43)–(45)**, named on page 1. The market-value basis moves
  to 15-minute values at the same time as the SDAC changeover.
* **Up to delivery 2025-09-30:** 60-minute spot prices and a 60-minute
  Online-Hochrechnung. Page 1: "Werte in der Vergangenheit werden im 60 Min Raster
  dargestellt."
* **From delivery 2025-10-01:** 15-minute values only, for both the spot price and
  the Online-Hochrechnung. Page 1: "Ab dem 01.10.2025 werden ausschließlich die
  15 Min Werte … veröffentlicht", and there is **no parallel publication** and **no
  retroactive 15-minute republication** ("Eine rückwirkende 15 Min Veröffentlichung
  … findet nicht statt"). So the pre-October-2025 period is hourly permanently.
* **The changeover falls INSIDE the extended window 2024-01 … 2026-10** — on
  1 Oct 2025 — so both regimes occur in the Test 2 training history.

**The transition-month provision does not bite.** Page 1 ends the section by
deferring the month that contains both resolutions to the statute ("Für die
Berechnung im Monat der Umstellung … verweisen wir auf die entsprechenden Regelungen
im Gesetz"), and the switch date was only "voraussichtlich" 30 Sep 2025. Checked
empirically rather than assumed: in the panel, **745 of 745 calendar hours in October
2025 have a non-zero within-hour price spread** (mean 28.04 €/MWh), and September is
entirely hourly, so the changeover landed exactly on a month boundary and **no month
in this window is mixed**. The §100(43)–(45) text is not on disk, which is therefore
non-blocking here; it would be needed only if a mixed month existed. [VERIFY] if ever
required.

**No 60-minute code path is needed, and this is why.** MV is a ratio of sums, and
pre-October-2025 SMARD serves each quarter-hour its own hour's price (verified: 168
of 168 hours in a 2024 sample week have four identical quarter-hour prices, zero
nulls). With p constant inside each hour and the hourly quantity being the sum of its
four quarter-hourly ones,

    sum_h p_h A_h / sum_h A_h   where A_h = sum_{q in h} a_q
      = sum_h sum_{q in h} p_h a_q / sum_h sum_q a_q
      = sum_q p_{h(q)} a_q / sum_q a_q

so the quarter-hour computation is **algebraically identical** to the statutory
hourly one. (`act_onshore_mw` is MW rather than MWh, but every quarter-hour has the
same duration, so the constant cancels in the ratio.) Rule 17's requirement to use
the formula in force for each month is therefore satisfied by the existing code
without branching — not by coincidence, but because the ratio form is invariant to
the resolution when the price is piecewise-constant on the coarser grid.

NOT YET VALIDATED -- do not use this in theta
---------------------------------------------
The recomputation does not reproduce the published series. It is systematically
HIGHER, by 1.7% in January 2026 and 25.0% in April, and the gap is widest in the
months with the most negative prices. As capture rates against the same monthly
spot mean (which the panel reproduces exactly, so the price series is not the
problem):

    month     published   on SMARD actual   on the day-ahead forecast
    2026-01      86.6%             88.1%                       88.2%
    2026-04      72.8%             91.0%                       84.3%
    2026-09      75.5%             81.2%                       80.2%

A capture rate of 91% for onshore wind in April, a month full of negative prices,
is not credible; 73% is. So the published figure is right and this recomputation
is wrong, and the cause is the generation series, not the price series.

The weighting series is the TSOs' **Online-Hochrechnung** of actual generation, not
SMARD's "Realisierte Erzeugung". **Source: EEG Anlage 1 no. 3.3.2.** (An earlier
version of this docstring credited `marktwertberechnung_umstellung.pdf` with that
statement. Having read the PDF in full on 1 Nov 2026, it does not say it: the PDF is
a two-page FAQ about the 15-minute changeover and says only that the
Online-Hochrechnung series and the spot prices move to 15-minute resolution. The
claim stands; the citation was wrong.) The
published series evidently places more weight on cheap quarter-hours than SMARD's
actual does -- consistent with an extrapolation that does not fully reflect
market-driven switch-off, since switching off during the cheapest quarter-hours is
exactly what RAISES the capture rate of a metered series. Weighting by the
day-ahead forecast instead moves April from 91.0% to 84.3%, so that explains part
of the gap but not all of it.

**Consequence.** Rule 17 requires T2 to recompute MV_m rather than use the
published value, but the recomputation has to reproduce the published value before
it can be trusted, and it does not. Until then theta must not be built on it.
**UNRESOLVED.** To settle it: obtain the Online-Hochrechnung wind-onshore series
from Netztransparenz (the same route as the redispatch export -- a manual download,
or the WebAPI behind the OAuth registration) and recompute on that. If the gap is
really curtailment, the difference between the two is an independent estimate of
market-driven switch-off, which would be worth a result in its own right -- but
that is a hypothesis, not a finding.

Two things this also does NOT settle
-------------------------------
* **[VERIFY] monthly versus annual reference period.** EEG Anlage 1 no. 2 applies
  the monthly value to plants commissioned or awarded before 1 Jan 2023; cohorts
  from 2023 may settle on the annual value, in which case their theta needs a
  year-to-date recomputation instead. Hirth (2026, Table A1) lists post-2023
  onshore as monthly, which conflicts with that reading. Unresolved; the
  year-to-date series is produced here as well so that either reading can be used
  without re-running anything.
* The Netztransparenz **licence** is still UNRESOLVED and must be settled before
  any of this goes in the thesis.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[1]
PANEL = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"
PUBLISHED = REPO_ROOT / "data" / "raw" / "netztransparenz" / "Monatsmarktwerte_2026.csv"
RESULTS_DIR = REPO_ROOT / "results"

# Rule 17: how many days of the current month must be available before the
# month-to-date value is used instead of the previous month's completed one.
MIN_DAYS_MTD = 7

MONTHS_DE = {"Jan": 1, "Feb": 2, "Mär": 3, "Mrz": 3, "Apr": 4, "Mai": 5, "Jun": 6,
             "Jul": 7, "Aug": 8, "Sep": 9, "Okt": 10, "Nov": 11, "Dez": 12}
CT_PER_KWH_TO_EUR_PER_MWH = 10.0


def read_published(path: Path = PUBLISHED) -> pl.DataFrame:
    """The published MW Wind an Land. Semicolon-separated, decimal comma, ct/kWh."""
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")
    text = path.read_text(encoding="utf-8-sig")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    header = [h.strip() for h in lines[0].split(";")]
    months = []
    for h in header[1:]:
        m = re.match(r"([A-Za-zäöüÄÖÜ]{3})\s+(\d{4})", h)
        months.append((MONTHS_DE[m.group(1)], int(m.group(2))) if m else None)

    wanted = {"MW Wind an Land": "mv_wind_onshore", "Spotmarktpreis": "spot_mean"}
    out: dict[str, dict] = {}
    for ln in lines[1:]:
        cells = [c.strip() for c in ln.split(";")]
        if cells[0] not in wanted:
            continue
        for mn, raw in zip(months, cells[1:]):
            if mn is None or not raw:
                continue
            out.setdefault(f"{mn[1]}-{mn[0]:02d}", {"year": mn[1], "month": mn[0]})
            out[f"{mn[1]}-{mn[0]:02d}"][wanted[cells[0]]] = (
                float(raw.replace(".", "").replace(",", ".")) * CT_PER_KWH_TO_EUR_PER_MWH
            )
    return pl.DataFrame(sorted(out.values(), key=lambda r: (r["year"], r["month"])))


def recompute(area: str = "DE") -> pl.DataFrame:
    """MV_m from the panel: generation-weighted mean spot price, per month.

    Also returns the T2-admissible month-to-date series -- the value a model could
    have known by D-1 on each day of the month -- and the year-to-date series, for
    the unresolved annual-reference-period reading.
    """
    df = (
        pl.scan_parquet(PANEL)
        .filter(pl.col("area") == area)
        .select(["berlin_date", "price_eur_mwh", "act_onshore_mw"])
        .collect()
        .with_columns(
            pl.col("berlin_date").str.strptime(pl.Date, "%Y-%m-%d").alias("d")
        )
        .drop_nulls(["price_eur_mwh", "act_onshore_mw"])
        .with_columns(
            (pl.col("price_eur_mwh") * pl.col("act_onshore_mw")).alias("pq"),
        )
    )
    monthly = (
        df.group_by([pl.col("d").dt.year().alias("year"),
                     pl.col("d").dt.month().alias("month")])
          .agg(pl.col("pq").sum().alias("pq"),
               pl.col("act_onshore_mw").sum().alias("q"),
               pl.len().alias("n_qh"))
          .with_columns((pl.col("pq") / pl.col("q")).alias("mv_recomputed"))
          .sort(["year", "month"])
    )
    return monthly


def month_to_date(area: str = "DE") -> pl.DataFrame:
    """The T2 series: MV as known by D-1, month-to-date (rule 17).

    On day 1 of a month there is no month-to-date history, so the previous month's
    completed value is carried in -- which is what spec section 3 specifies.
    """
    df = (
        pl.scan_parquet(PANEL)
        .filter(pl.col("area") == area)
        .select(["berlin_date", "price_eur_mwh", "act_onshore_mw"])
        .collect()
        .with_columns(pl.col("berlin_date").str.strptime(pl.Date, "%Y-%m-%d").alias("d"))
        .drop_nulls(["price_eur_mwh", "act_onshore_mw"])
        .with_columns((pl.col("price_eur_mwh") * pl.col("act_onshore_mw")).alias("pq"))
        .group_by("d").agg(pl.col("pq").sum().alias("pq"),
                           pl.col("act_onshore_mw").sum().alias("q"))
        .sort("d")
        .with_columns(pl.col("d").dt.year().alias("year"),
                      pl.col("d").dt.month().alias("month"))
    )
    # Cumulative within the month, shifted by one day: what was known by D-1.
    df = df.with_columns(
        pl.col("pq").cum_sum().over(["year", "month"]).shift(1).over(["year", "month"])
          .alias("pq_mtd"),
        pl.col("q").cum_sum().over(["year", "month"]).shift(1).over(["year", "month"])
          .alias("q_mtd"),
        pl.col("pq").cum_sum().over("year").shift(1).over("year").alias("pq_ytd"),
        pl.col("q").cum_sum().over("year").shift(1).over("year").alias("q_ytd"),
    )
    monthly_complete = (
        df.group_by(["year", "month"]).agg(pl.col("pq").sum(), pl.col("q").sum())
          .with_columns((pl.col("pq") / pl.col("q")).alias("mv_complete"))
          .sort(["year", "month"])
          .with_columns(pl.col("mv_complete").shift(1).alias("mv_prev_month"))
    )
    # Rule 17 amendment, fixed 31 Oct 2026: a month-to-date value built from one
    # or two days is not a market value, it is noise -- 2026-01-02 read
    # 9.17 EUR/MWh off a single day. T2 therefore uses the PREVIOUS month's
    # recomputed value until at least MIN_DAYS_MTD days of the current month are
    # available, and the same logic carries the previous year's JW through early
    # January for the year-to-date series.
    df = df.with_columns(
        pl.col("d").dt.day().alias("day_of_month"),
        pl.col("d").dt.ordinal_day().alias("day_of_year"),
    )
    return (
        df.join(monthly_complete.select(["year", "month", "mv_prev_month"]),
                on=["year", "month"], how="left")
          .with_columns(
              pl.when((pl.col("q_mtd") > 0) & (pl.col("day_of_month") > MIN_DAYS_MTD))
                .then(pl.col("pq_mtd") / pl.col("q_mtd"))
                .otherwise(pl.col("mv_prev_month"))
                .alias("mv_t2_known_by_d_minus_1"),
              pl.when((pl.col("q_ytd") > 0) & (pl.col("day_of_year") > MIN_DAYS_MTD))
                .then(pl.col("pq_ytd") / pl.col("q_ytd"))
                .otherwise(None)
                .alias("mv_ytd_known_by_d_minus_1"),
              ((pl.col("day_of_month") <= MIN_DAYS_MTD)
               | (pl.col("q_mtd").is_null())).alias("mv_t2_is_carried_forward"),
          )
          .select(["d", "year", "month", "mv_t2_known_by_d_minus_1",
                   "mv_ytd_known_by_d_minus_1", "mv_t2_is_carried_forward"])
    )


def main() -> None:
    print("Market values for wind onshore")
    published = read_published()
    recomputed = recompute()

    cmp = (recomputed.join(published, on=["year", "month"], how="inner")
                     .with_columns(
                         (pl.col("mv_recomputed") - pl.col("mv_wind_onshore"))
                         .alias("diff_eur_mwh"))
                     .with_columns((pl.col("diff_eur_mwh")
                                    / pl.col("mv_wind_onshore")).alias("rel")))
    print("\nRecomputed vs published (EUR/MWh). Published is VALIDATION ONLY:")
    print(f"  {'month':<9}{'recomputed':>12}{'published':>11}{'diff':>9}{'rel':>8}"
          f"{'n_qh':>8}")
    for r in cmp.iter_rows(named=True):
        print(f"  {r['year']}-{r['month']:02d}{r['mv_recomputed']:>12.2f}"
              f"{r['mv_wind_onshore']:>11.2f}{r['diff_eur_mwh']:>9.2f}"
              f"{r['rel']:>8.2%}{r['n_qh']:>8,}")
    if cmp.height:
        worst = cmp.select(pl.col("rel").abs().max()).item()
        print(f"\n  largest absolute relative difference: {worst:.2%}")

    mtd = month_to_date()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "32_market_values.csv", "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cmp.columns, lineterminator="\n")
        w.writeheader()
        w.writerows(cmp.to_dicts())
    mtd.write_parquet(REPO_ROOT / "data" / "processed" / "mv_t2_daily.parquet")
    print("\nWrote results/32_market_values.csv and "
          "data/processed/mv_t2_daily.parquet (the T2 series, month-to-date by D-1)")


if __name__ == "__main__":
    main()
