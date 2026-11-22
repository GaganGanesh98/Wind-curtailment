"""The pre-registered rule-18 count, on real 2026 data.

    python src/check_rule18_real.py

Spec §3 I4 / hard rule 18: before any modelling, count the Berlin-local event-days
on which the cohort exposure vectors s_k actually differ. **Fewer than 10 and the
K-cohort model is abandoned for the two-cohort one**, pooling the response but not
the exposure. This is pre-registered, so it is run once and reported whatever it
says.

Inputs, all real
----------------
* cohort capacity shares from the MaStR snapshot;
* AW per cohort, capacity-weighted from the per-unit provenance in
  `compute_theta_inputs.py` -- BNetzA round values for tendered capacity, Hirth
  Table A1 status A for non-tendered, no AW at all for out-of-support;
* the reference period per cohort (Anlage 1 Nr. 2), with the published monthly MW
  for monthly-reference cohorts and the annual JW for the rest;
* real quarter-hour prices from the panel.

Coverage
--------
The published market values run Jan-Sep 2026 only, so the count covers those nine
months. Oct-Dec 2025 is awaiting the published 2025 monthly values and Oct 2026 is
not published yet; both are excluded and reported, not silently dropped.

Decomposing where the difference comes from
-------------------------------------------
Two cohorts can be exposed differently for two reasons, and the fallback decision
depends on which:

* **clock / run length** -- their §51 triggers differ, because one is on the
  quarter-hour clock and the other on the hourly clock, or because their
  run-length thresholds differ. Tested by setting every θ to 0 and asking whether
  exposure still differs.
* **premium** -- their thresholds differ and the price falls between them. Tested
  by holding the trigger identical across cohorts and asking the same question.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.method.exposure import (  # noqa: E402
    build_clock_features, mastr_cohort_set, trigger_active,
)
from src.method.theta_inputs import (  # noqa: E402
    JW_2025_EUR_MWH, PROV_HIRTH_FIT, PROV_OUT_OF_SUPPORT, assign_fit, build,
    jw_2026_ytd,
)
from src.method.ingest_market_values import read_published  # noqa: E402
from src.method.ingest_mastr import cohort_of  # noqa: E402

PANEL = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"
RESULTS_DIR = REPO_ROOT / "results"


def cohort_parameters() -> pl.DataFrame:
    """Per rule-table cohort: capacity-weighted AW, reference period, FiT share."""
    df = assign_fit(build()).with_columns(
        pl.struct(["commissioned", "net_kw", "pilot"]).map_elements(
            lambda r: cohort_of(r["commissioned"], r["net_kw"], bool(r["pilot"])),
            return_dtype=pl.String).alias("cohort")
    )
    rows = []
    for cohort in sorted(set(df["cohort"].to_list())):
        sub = df.filter(pl.col("cohort") == cohort)
        cap = float(sub["net_kw"].sum() or 0.0)
        with_aw = sub.filter(pl.col("aw_eur_mwh").is_not_null())
        def wmean(col: str):
            v = with_aw.drop_nulls(col)
            if v.height == 0:
                return None
            w = v["net_kw"].to_numpy()
            return float((v[col].to_numpy() * w).sum() / w.sum())

        aw = wmean("aw_eur_mwh")
        monthly_cap = float(sub.filter(pl.col("ref_period") == "monthly")
                               ["net_kw"].sum() or 0.0)
        rows.append({
            "cohort": cohort, "capacity_mw": cap / 1000,
            "aw_eur_mwh": round(aw, 2) if aw else None,
            "aw_low_eur_mwh": (lambda v: round(v, 2) if v else None)(
                wmean("aw_low_eur_mwh")),
            "aw_high_eur_mwh": (lambda v: round(v, 2) if v else None)(
                wmean("aw_high_eur_mwh")),
            "share_monthly_reference": round(monthly_cap / cap, 4) if cap else None,
            "reference": "monthly" if monthly_cap >= cap / 2 else "annual",
            "fit_share": round(float(sub.filter(pl.col("aw_source") == PROV_HIRTH_FIT)
                                     ["net_kw"].sum() or 0.0) / cap, 4) if cap else 0.0,
            "out_of_support_share": round(
                float(sub.filter(pl.col("aw_source") == PROV_OUT_OF_SUPPORT)
                      ["net_kw"].sum() or 0.0) / cap, 4) if cap else 0.0,
        })
    return pl.DataFrame(rows)


def main() -> None:
    params = cohort_parameters()
    cohorts = mastr_cohort_set("DE")
    published = read_published()
    jw26 = jw_2026_ytd(published)

    print("JW 2026 year-to-date, used for annual-reference cohorts")
    print("  = sum over Jan-Sep of (published monthly MW x SMARD monthly onshore")
    print(f"    energy) / total energy = {jw26:.2f} EUR/MWh")
    print(f"  NOT a plain mean of the monthly values, which would give "
          f"{float(published.filter(pl.col('year') == 2026)['mv_wind_onshore'].mean()):.2f}.")
    print("  APPROXIMATE on two counts: the year is not over, and the weights are")
    print("  SMARD metered output rather than the Anlage 1 Nr. 5.1 projection the")
    print(f"  statute prescribes. JW 2025 = {JW_2025_EUR_MWH:.2f} (given).")

    print("\nCohort parameters (real MaStR shares, AW from the provenance):")
    print(f"  {'cohort':<30}{'cap GW':>8}{'AW':>8}{'ref':>9}{'monthly%':>10}{'FiT%':>7}")
    for r in params.sort("capacity_mw", descending=True).iter_rows(named=True):
        aw = f"{r['aw_eur_mwh']:.1f}" if r["aw_eur_mwh"] else "none"
        print(f"  {r['cohort']:<30}{r['capacity_mw'] / 1000:>8.2f}{aw:>8}"
              f"{r['reference']:>9}{r['share_monthly_reference']:>10.0%}"
              f"{r['fit_share']:>7.1%}")

    # --- the panel, restricted to months with a published market value ---
    panel = (pl.scan_parquet(PANEL).filter(pl.col("area") == "DE")
             .select(["ts_utc", "berlin_date", "price_eur_mwh"]).collect()
             .with_columns(pl.col("berlin_date").str.strptime(pl.Date, "%Y-%m-%d")
                             .alias("d"))
             .drop_nulls().sort("ts_utc"))
    have = {(r["year"], r["month"]) for r in published.iter_rows(named=True)}
    panel = panel.with_columns(pl.col("d").dt.year().alias("y"),
                               pl.col("d").dt.month().alias("m"))
    covered = panel.filter(
        pl.struct(["y", "m"]).map_elements(lambda r: (r["y"], r["m"]) in have,
                                           return_dtype=pl.Boolean))
    neg_all = panel.filter(pl.col("price_eur_mwh") < 0).height
    neg_cov = covered.filter(pl.col("price_eur_mwh") < 0).height
    print(f"\nCoverage: {neg_cov:,} of {neg_all:,} negative quarter-hours "
          f"({neg_cov / neg_all:.0%})")
    missing = sorted({(r["y"], r["m"]) for r in panel.iter_rows(named=True)} - have)
    for y, m in missing:
        why = ("awaiting published 2025 MW" if y == 2025 else "MW not yet published")
        n = panel.filter((pl.col("y") == y) & (pl.col("m") == m)
                         & (pl.col("price_eur_mwh") < 0)).height
        print(f"  excluded {y}-{m:02d}: {n:>4} negative QHs -- {why}")

    # Clock features need a contiguous series, so use the whole panel and mask after.
    clock = build_clock_features(panel["ts_utc"].to_numpy() * 1_000_000,
                                 panel["price_eur_mwh"].to_numpy())
    price = clock.price_qh
    mv_by_month = {(r["year"], r["month"]): r["mv_wind_onshore"]
                   for r in published.iter_rows(named=True)}
    ym = list(zip(panel["y"].to_list(), panel["m"].to_list()))
    mv = np.array([mv_by_month.get(k, np.nan) for k in ym])
    jw = np.where(np.array([k[0] for k in ym]) == 2025, JW_2025_EUR_MWH, jw26)

    pmap = {r["cohort"]: r for r in params.iter_rows(named=True)}
    shares = cohorts.shares

    def build_theta(setting: str):
        """theta per cohort under one of rule 19's AW settings.

        "stress" is not an AW setting but a structural what-if: every pre-2016
        in-support cohort is forced to MP = 0, standing in for the possibility
        that most of it sits on the BASE tariff rather than on the blended value
        Table A1 quotes. It is the pessimistic case for identification, because
        the premium is what gates cohort separation.
        """
        col = {"main": "aw_eur_mwh", "low": "aw_low_eur_mwh",
               "high": "aw_high_eur_mwh", "stress": "aw_eur_mwh"}[setting]
        th_list, trig_list, untrig = [], [], []
        for c in cohorts:
            p = pmap[c.cohort_id]
            active = trigger_active(c, clock)
            ref = mv if p["reference"] == "monthly" else jw
            aw = p[col]
            if setting == "stress" and c.cohort_id == "pre2016_in_support_no_s51":
                aw = None
            th = np.zeros_like(price) if aw is None else -np.maximum(0.0, aw - ref)
            untrig.append(th.copy())
            th_list.append(np.where(active, 0.0, th))
            trig_list.append(active)
        return np.vstack(th_list), np.vstack(untrig), np.vstack(trig_list)

    results = {st: build_theta(st) for st in ("main", "low", "high", "stress")}
    theta, theta_untriggered, trig = results["main"]
    s = (price[None, :] < theta).astype(int)

    mask = np.array([k in have for k in ym])
    differs = (s.max(axis=0) != s.min(axis=0)) & mask
    dates = panel["berlin_date"].to_numpy()
    days_differ = sorted(set(dates[differs]))

    # Decomposition. Each counterfactual holds one channel fixed across cohorts and
    # lets the other vary, so the two are comparable with the real `differs`.
    #
    # NOTE a consequence that is easy to miss: theta = 0 when the trigger is active
    # AND when the premium is zero. So where MP = 0 the section 51 trigger changes
    # nothing at all -- it can only create a difference in exposure while a premium
    # is actually live.
    mp = np.maximum(0.0, -theta_untriggered)          # the premium each cohort has
    mp_common = np.average(mp, axis=0, weights=shares)
    th_clock = np.where(trig, 0.0, -mp_common[None, :])   # trigger varies, MP fixed
    s_clock = (price[None, :] < th_clock).astype(int)
    clock_differs = (s_clock.max(axis=0) != s_clock.min(axis=0)) & mask

    th_prem = -mp                                         # MP varies, no trigger
    s_prem = (price[None, :] < th_prem).astype(int)
    prem_differs = (s_prem.max(axis=0) != s_prem.min(axis=0)) & mask

    print("\nRULE 18 -- event-days on which the cohort exposure vectors differ")
    print(f"  quarter-hours with differing exposure: {int(differs.sum()):,}")
    print(f"  EVENT-DAYS with differing exposure:    {len(days_differ):,}")
    print("  pre-registered threshold:              10")
    print(f"  -> {'K-COHORT MODEL STANDS' if len(days_differ) >= 10 else 'TWO-COHORT FALLBACK APPLIES'}")
    both = clock_differs & prem_differs
    print("\n  source of the difference, by quarter-hour (counterfactuals, so they")
    print("  need not sum to the total):")
    print(f"    clock or run length alone: {int((clock_differs & ~prem_differs).sum()):>6,}")
    print(f"    market premium alone:      {int((prem_differs & ~clock_differs).sum()):>6,}")
    print(f"    both channels:             {int(both.sum()):>6,}")
    print(f"    neither (interaction):     "
          f"{int((differs & ~clock_differs & ~prem_differs).sum()):>6,}")
    print("\n  Where the premium is zero, theta = 0 whether or not the section 51")
    print("  trigger is active, so the trigger cannot create a difference at all.")
    print("  The clock channel is only live while a premium is.")

    print("\nRULE 18 UNDER RULE 19's AW SETTINGS, AND THE BASE-TARIFF STRESS CASE")
    print("  (stress = all pre-2016 in-support capacity forced to MP = 0)")
    print(f"\n  {'setting':<10}{'QHs differing':>15}{'EVENT-DAYS':>13}{'verdict':>24}")
    setting_rows = []
    for setting in ("low", "main", "high", "stress"):
        th, _, _ = results[setting]
        ss = (price[None, :] < th).astype(int)
        dd = (ss.max(axis=0) != ss.min(axis=0)) & mask
        nd = len(set(dates[dd]))
        verdict = "K-cohort stands" if nd >= 10 else "TWO-COHORT FALLBACK"
        print(f"  {setting:<10}{int(dd.sum()):>15,}{nd:>13,}{verdict:>24}")
        setting_rows.append({"setting": setting, "qh_differing": int(dd.sum()),
                             "event_days": nd, "threshold": 10, "verdict": verdict})
    with open(REPO_ROOT / "artifacts" / "method_inputs" / "cohort_parameter_settings.csv", "w", newline="",
              encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(setting_rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(setting_rows)
    print("\n  Cohort separation is gated by the premium, so r-hat stability across")
    print("  these settings is the primary real-data identification check (spec I4).")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPO_ROOT / "artifacts" / "method_inputs" / "cohort_parameters.csv", "w", newline="",
              encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["metric", "value"])
        w.writerow(["negative_qh_covered", neg_cov])
        w.writerow(["negative_qh_total", neg_all])
        w.writerow(["qh_differing_exposure", int(differs.sum())])
        w.writerow(["event_days_differing", len(days_differ)])
        w.writerow(["threshold", 10])
        w.writerow(["qh_clock_or_runlength", int(clock_differs.sum())])
        w.writerow(["qh_market_premium", int(prem_differs.sum())])
        w.writerow(["jw_2026_ytd", round(jw26, 2)])
    print("\nWrote results/38_rule18_real.csv")


if __name__ == "__main__":
    main()
