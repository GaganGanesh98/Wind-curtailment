"""Per-unit AW, reference period, and the share of capacity with MP = 0.

    python src/compute_theta_inputs.py

Award values, by provenance
---------------------------
**Tendered capacity** keeps the BNetzA round value from the Zuschlagsnummer join,
times the §36h correction factor. Hirth's tendered-cohort bids are deliberately
NOT used: they disagree with the BNetzA statistics, notably for 2021-22.

**Non-tendered capacity** — all pre-2016, most of 2016-2020 — takes a **status A**
estimate from Hirth (2026) Table A1, Appendix A2, pp. 26-28, archived at
`docs/literature/hirth_2026_2609.10053v1.pdf`, with a ±15% band:

    up to 2002, market premium   8.0 ct/kWh blended   (0.00 GW: nothing left)
    2003-2011,  market premium   8.5 ct/kWh blended
    2003-2011,  feed-in tariff   8.5 ct/kWh,  0.51 GW, theta = NEVER
    2012-2015,  market premium   8.9 ct/kWh incl. management premium
    2012-2015,  feed-in tariff   8.9 ct/kWh,  0.75 GW, theta = NEVER
    2016-2020,  from 3 MW        7.6 ct/kWh blended

**Named limitation.** These are *blended* values: they hide the split between the
initial (erhöhte Anfangsvergütung) and base tariff. A plant that has dropped to the
base tariff — roughly 5 ct/kWh for this vintage — has MP = 0 against any 2026
market value, so the blended figure overstates the premium for that part of the
fleet. There is no per-plant phase modelling here and none is planned; the
consequence is that the MP = 0 shares below are a **lower bound**.

**Feed-in-tariff capacity has no switch-off incentive at all.** It is paid a fixed
tariff whatever the spot price does, so theta does not exist for it rather than
being 0. Hirth gives 0.51 GW and 0.75 GW against 9.69 GW and 14.25 GW on the market
premium, i.e. 5.0% of each vintage; MaStR does not identify which units these are,
so the share is applied within each vintage band and labelled.

Reference period (EEG Anlage 1 Nr. 2)
-------------------------------------
Monthly MW if the unit was commissioned before 2023 **or** awarded before 2023;
annual JW otherwise. JW = 74.41 EUR/MWh for 2025. For 2026 the year is not over, so
the year-to-date value is used and labelled approximate.
"""

from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.method.ingest_award_values import (  # noqa: E402
    CORRECTION_FACTOR_MAIN, attach_awards, read_rounds, reference_period,
)
from src.method.ingest_market_values import read_published  # noqa: E402
from src.method.ingest_mastr import support_ends  # noqa: E402

AS_OF = date(2026, 10, 31)

PROCESSED_DIR = REPO_ROOT / "data" / "processed"
RESULTS_DIR = REPO_ROOT / "results"
PANEL = PROCESSED_DIR / "panel_qh.parquet"

# Hirth (2026) Table A1, ct/kWh -> EUR/MWh. Status A: a labelled estimate.
HIRTH_A1_AW_EUR_MWH = {"up_to_2002": 80.0, "2003_2011": 85.0,
                       "2012_2015": 89.0, "2016_2020": 76.0}
HIRTH_A1_STATUS = "Hirth (2026) Table A1, own estimate, status A"
STATUS_A_BAND = 0.15
# Feed-in-tariff share within each vintage, from Table A1's own capacities.
HIRTH_A1_FIT_SHARE = {"2003_2011": 0.51 / (9.69 + 0.51), "2012_2015": 0.75 / (14.25 + 0.75)}
JW_2025_EUR_MWH = 74.41
# s.36h correction factors at the ends of rule 19's sensitivity: a good 90% site
# and a poor 60% site.
S36H_LOW, S36H_HIGH = 1.07, 1.42


PROV_TENDERED = "BNetzA round x 1.226"
PROV_HIRTH_MP = "Hirth Table A1 status A, market premium"
PROV_HIRTH_FIT = "Hirth Table A1 status A, feed-in tariff (theta = never)"
PROV_OUT_OF_SUPPORT = "out of support (theta = 0)"
PROV_GAP = "non-tendered post-2020: NO AW (gap)"
PROVENANCES = (PROV_TENDERED, PROV_HIRTH_MP, PROV_HIRTH_FIT, PROV_OUT_OF_SUPPORT,
               PROV_GAP)


def assign_fit(df: pl.DataFrame) -> pl.DataFrame:
    """Split the feed-in-tariff share out of the market-premium slot.

    Table A1 gives the feed-in-tariff share as 5.0% of capacity in each pre-2016
    vintage, but MaStR does not say WHICH units those are. The share is assigned to
    the SMALLEST units in each vintage until that capacity is reached. That is a
    heuristic, not a fact: plants that stayed out of direct marketing are
    overwhelmingly small ones, since direct marketing has been compulsory above
    100 kW since 2016. Only the aggregate share comes from Table A1; the selection
    within the vintage is this project's assumption, and anything depending on
    WHICH units are on a feed-in tariff inherits it.
    """
    keep = []
    for v, share in HIRTH_A1_FIT_SHARE.items():
        sub = (df.filter((pl.col("vintage") == v) & (~pl.col("out_of_support"))
                         & (pl.col("aw_source") == PROV_HIRTH_MP)).sort("net_kw"))
        if sub.height == 0:
            continue
        target = float(sub["net_kw"].sum()) * share
        n = int((sub["net_kw"].cum_sum() <= target).sum()) or 1
        keep.extend(sub["EinheitMastrNummer"].to_list()[:n])
    return df.with_columns(
        pl.when(pl.col("EinheitMastrNummer").is_in(keep))
          .then(pl.lit(PROV_HIRTH_FIT)).otherwise(pl.col("aw_source")).alias("aw_source")
    )


def assert_provenance_complete(df: pl.DataFrame) -> None:
    """Every unit carries exactly one provenance, and they sum to fleet capacity."""
    unknown = set(df["aw_source"].to_list()) - set(PROVENANCES)
    if unknown:
        raise ValueError(f"Unknown provenance label(s): {sorted(unknown)}")
    if df["aw_source"].null_count():
        raise ValueError("Some units carry no provenance at all")
    by = float(df.group_by("aw_source").agg(pl.col("net_kw").sum().alias("kw"))["kw"].sum())
    tot = float(df["net_kw"].sum())
    if abs(by - tot) > 1e-6:
        raise ValueError(f"Provenance capacities sum to {by:,.0f} kW, fleet {tot:,.0f} kW")


def vintage(commissioned: date) -> str:
    if commissioned.year <= 2002:
        return "up_to_2002"
    if commissioned.year <= 2011:
        return "2003_2011"
    if commissioned.year <= 2015:
        return "2012_2015"
    if commissioned.year <= 2020:
        return "2016_2020"
    return "post_2020"


def jw_2026_ytd(published: pl.DataFrame) -> float:
    """Approximate JW 2026: published monthly MW weighted by monthly onshore output.

    Approximate for two reasons, both stated wherever the number is used: the year
    is not over, and the weights are SMARD's metered generation rather than the
    Online-Hochrechnung the statute prescribes.
    """
    gen = (pl.scan_parquet(PANEL).filter(pl.col("area") == "DE")
           .select(["berlin_date", "act_onshore_mw"]).collect()
           .with_columns(pl.col("berlin_date").str.strptime(pl.Date, "%Y-%m-%d").alias("d"))
           .drop_nulls()
           .group_by([pl.col("d").dt.year().alias("year"),
                      pl.col("d").dt.month().alias("month")])
           .agg(pl.col("act_onshore_mw").sum().alias("q")))
    j = published.join(gen, on=["year", "month"], how="inner").filter(pl.col("year") == 2026)
    return float((j["mv_wind_onshore"] * j["q"]).sum() / j["q"].sum())


def build() -> pl.DataFrame:
    units = pl.read_parquet(sorted(PROCESSED_DIR.glob("mastr_wind_*.parquet"))[-1])
    df = attach_awards(units, read_rounds())
    return df.with_columns(
        pl.col("commissioned").map_elements(vintage, return_dtype=pl.String).alias("vintage"),
        # Out of support means no premium left to lose, so there is no AW at all and
        # theta = 0. Checked FIRST: an earlier version assigned these units their
        # vintage's Table A1 value anyway, which handed 11.9 GW -- 16.7% of the
        # fleet -- a market premium it has not earned since its twentieth year.
        pl.col("commissioned").map_elements(
            lambda d: support_ends(d) < AS_OF, return_dtype=pl.Boolean
        ).alias("out_of_support"),
        pl.struct(["commissioned", "round_code", "round_date"]).map_elements(
            lambda r: reference_period(r["commissioned"], r["round_code"], r["round_date"]),
            return_dtype=pl.String).alias("ref_period"),
    ).with_columns(
        pl.when(pl.col("out_of_support")).then(None)
          .when(pl.col("aw_wmean_eur_mwh").is_not_null())
          .then(pl.col("aw_wmean_eur_mwh") * CORRECTION_FACTOR_MAIN)
          .otherwise(pl.col("vintage").replace_strict(HIRTH_A1_AW_EUR_MWH, default=None))
          .alias("aw_eur_mwh"),
        # Rule 19's three settings, per unit. Tendered: the awarded-bid range
        # crossed with the s.36h correction range (good 90% site to poor 60%).
        # Status A: Hirth's blended value +/- 15%.
        pl.when(pl.col("out_of_support")).then(None)
          .when(pl.col("aw_min_eur_mwh").is_not_null())
          .then(pl.col("aw_min_eur_mwh") * S36H_LOW)
          .otherwise(pl.col("vintage").replace_strict(HIRTH_A1_AW_EUR_MWH, default=None)
                     * (1 - STATUS_A_BAND)).alias("aw_low_eur_mwh"),
        pl.when(pl.col("out_of_support")).then(None)
          .when(pl.col("aw_max_eur_mwh").is_not_null())
          .then(pl.col("aw_max_eur_mwh") * S36H_HIGH)
          .otherwise(pl.col("vintage").replace_strict(HIRTH_A1_AW_EUR_MWH, default=None)
                     * (1 + STATUS_A_BAND)).alias("aw_high_eur_mwh"),
        pl.when(pl.col("out_of_support")).then(pl.lit(PROV_OUT_OF_SUPPORT))
          .when(pl.col("aw_wmean_eur_mwh").is_not_null()).then(pl.lit(PROV_TENDERED))
          .when(pl.col("vintage") == "post_2020").then(pl.lit(PROV_GAP))
          .otherwise(pl.lit(PROV_HIRTH_MP)).alias("aw_source"),
    )


def main() -> None:
    df = assign_fit(build())
    assert_provenance_complete(df)
    published = read_published()
    jw26 = jw_2026_ytd(published)
    print(f"JW 2025 = {JW_2025_EUR_MWH:.2f} EUR/MWh (given); "
          f"JW 2026 year-to-date ~ {jw26:.2f} EUR/MWh (APPROXIMATE: year not over, "
          f"and weighted by SMARD metered output, not the Online-Hochrechnung)")

    print("\nProvenance -- exactly one per unit, partitioning the fleet:")
    tot = float(df["net_kw"].sum()) / 1e6
    for src, cap, n in (df.group_by("aw_source")
                        .agg(pl.col("net_kw").sum().alias("kw"), pl.len().alias("n"))
                        .sort("kw", descending=True).iter_rows()):
        print(f"  {src:<50}{cap / 1e6:6.2f} GW  {n:>7,} units")
    print(f"  {'TOTAL':<50}{tot:6.2f} GW   (checked: they partition the fleet)")

    # --- negative-price quarter-hours per month, the weights for the table ---
    neg = (pl.scan_parquet(PANEL).filter((pl.col("area") == "DE") & (pl.col("price_eur_mwh") < 0))
           .select("berlin_date").collect()
           .with_columns(pl.col("berlin_date").str.strptime(pl.Date, "%Y-%m-%d").alias("d"))
           .group_by([pl.col("d").dt.year().alias("year"), pl.col("d").dt.month().alias("month")])
           .agg(pl.len().alias("neg_qh")).sort(["year", "month"]))

    rows = []
    for m in published.iter_rows(named=True):
        mv, jw = m["mv_wind_onshore"], (jw26 if m["year"] == 2026 else JW_2025_EUR_MWH)
        ref = df.with_columns(
            pl.when(pl.col("ref_period") == "monthly").then(pl.lit(mv))
              .otherwise(pl.lit(jw)).alias("reference")
        ).filter(pl.col("aw_eur_mwh").is_not_null())
        cap = float(ref["net_kw"].sum() or 0.0)
        zero = float(ref.filter(pl.col("aw_eur_mwh") <= pl.col("reference"))
                        ["net_kw"].sum() or 0.0)
        nq = neg.filter((pl.col("year") == m["year"]) & (pl.col("month") == m["month"]))
        rows.append({"year": m["year"], "month": m["month"],
                     "mv_eur_mwh": round(mv, 2), "jw_eur_mwh": round(jw, 2),
                     "capacity_with_aw_mw": round(cap / 1000, 1),
                     "mp_zero_capacity_mw": round(zero / 1000, 1),
                     "mp_zero_share": round(zero / cap, 4) if cap else None,
                     "negative_qh": int(nq["neg_qh"][0]) if nq.height else 0})

    tab = pl.DataFrame(rows)
    with open(REPO_ROOT / "artifacts" / "method_inputs" / "market_premium_zero.csv", "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=tab.columns, lineterminator="\n")
        w.writeheader()
        w.writerows(tab.to_dicts())

    print(f"\nShare of in-support capacity with MP = 0 (theta = 0 de facto),")
    print(f"against the CORRECT reference per unit:\n")
    print(f"  {'month':<9}{'MV':>8}{'JW':>8}{'MP=0 share':>12}{'neg QHs':>10}")
    for r in tab.iter_rows(named=True):
        print(f"  {r['year']}-{r['month']:02d}{r['mv_eur_mwh']:>8.1f}"
              f"{r['jw_eur_mwh']:>8.1f}{r['mp_zero_share']:>12.1%}"
              f"{r['negative_qh']:>10,}")

    tot_neg = int(tab["negative_qh"].sum())
    if tot_neg:
        w_share = float((tab["mp_zero_share"] * tab["negative_qh"]).sum() / tot_neg)
    else:
        w_share = float("nan")
    simple = float(tab["mp_zero_share"].mean())
    print(f"\n  unweighted mean over months:              {simple:.1%}")
    print(f"  WEIGHTED BY NEGATIVE-PRICE QUARTER-HOURS: {w_share:.1%}"
          f"   ({tot_neg:,} negative QHs in the covered months)")
    print("\n  The weighted figure is the one that matters: a month with a high")
    print("  MP = 0 share and no negative prices cannot affect identification,")
    print("  because theta is only ever tested when the price goes below it.")
    print("\nWrote results/35_market_premium_zero.csv")


if __name__ == "__main__":
    main()
