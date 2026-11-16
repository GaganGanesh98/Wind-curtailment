#!/usr/bin/env python3
"""Score the identification of the cohort design: old I4 day count vs the proposed
composite criterion, on the E1 gate artifacts and on the real panel.

    python -m src.method.real_theta

Writes `results/39_identification_gate.csv` (one row per arm, both verdicts side by
side). Nothing here refits a model; it reads stored exposure matrices and rebuilds
theta on the real panel.

Why this is a separate runner. `gate_verdict.py` carries criterion (d) so the gate
prints it, but that script currently cannot reach (d): it raises
`KeyError: 'n_qh'` inside criterion (b) on the artifacts now on disk, with or
without (d) present. That is a pre-existing fault in the committed gate script and
is deliberately NOT fixed here. This runner therefore scores (d) directly.
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
    build_clock_features, exposure_differs_by_day, mastr_cohort_set,
    placeholder_cohort_set, trigger_active,
)
from src.method.collinearity import (  # noqa: E402
    FALLBACK_MODES, MAX_COND_S, MIN_PAIR_DIFFER_QH, fallback_identifiability,
    fallback_partition, format_fallback, format_merge_map, format_report,
    gate_identification_verdict, identification_diagnostics, merge_cohorts,
    theta_merge_map,
)

ARTIFACT_DIR = REPO_ROOT / "data" / "processed" / "e1_gate_artifacts"
MERGED_ARTIFACT_DIR = REPO_ROOT / "data" / "processed" / "e1_gate_artifacts_merged"
PANEL = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"
RESULTS_DIR = REPO_ROOT / "results"
OUT_CSV = RESULTS_DIR / "39_identification_gate.csv"
AW_SETTINGS = ("low", "main", "high", "stress")


def _real_panel_theta():
    """theta per cohort per AW setting on the real DE panel.

    Mirrors `src/check_rule18_real.py` build_theta (the AW-setting construction and
    the restriction to months with a published market value), so the old verdict
    reproduces what `results/38_rule18_settings.csv` recorded.
    """
    from src.method.cohort_parameters import cohort_parameters
    from src.method.theta_inputs import JW_2025_EUR_MWH, jw_2026_ytd
    from src.method.ingest_market_values import read_published

    params = cohort_parameters()
    cohorts = mastr_cohort_set("DE")
    published = read_published()
    jw26 = jw_2026_ytd(published)
    panel = (pl.scan_parquet(PANEL).filter(pl.col("area") == "DE")
             .select(["ts_utc", "berlin_date", "price_eur_mwh"]).collect()
             .with_columns(pl.col("berlin_date").str.strptime(pl.Date, "%Y-%m-%d")
                           .alias("d")).drop_nulls().sort("ts_utc"))
    panel = panel.with_columns(pl.col("d").dt.year().alias("y"),
                               pl.col("d").dt.month().alias("m"))
    clock = build_clock_features(panel["ts_utc"].to_numpy() * 1_000_000,
                                 panel["price_eur_mwh"].to_numpy())
    price = clock.price_qh
    have = {(r["year"], r["month"]) for r in published.iter_rows(named=True)}
    mvm = {(r["year"], r["month"]): r["mv_wind_onshore"]
           for r in published.iter_rows(named=True)}
    ym = list(zip(panel["y"].to_list(), panel["m"].to_list()))
    mv = np.array([mvm.get(k, np.nan) for k in ym])
    jw = np.where(np.array([k[0] for k in ym]) == 2025, JW_2025_EUR_MWH, jw26)
    mask = np.array([k in have for k in ym])
    pmap = {r["cohort"]: r for r in params.iter_rows(named=True)}
    dates = panel["berlin_date"].to_numpy()

    def theta_for(setting: str) -> np.ndarray:
        col = {"main": "aw_eur_mwh", "low": "aw_low_eur_mwh",
               "high": "aw_high_eur_mwh", "stress": "aw_eur_mwh"}[setting]
        rows = []
        for c in cohorts:
            p = pmap[c.cohort_id]
            active = trigger_active(c, clock)
            ref = mv if p["reference"] == "monthly" else jw
            aw = p[col]
            if setting == "stress" and c.cohort_id == "pre2016_in_support_no_s51":
                aw = None
            th = np.zeros_like(price) if aw is None else -np.maximum(0.0, aw - ref)
            rows.append(np.where(active, 0.0, th))
        return np.vstack(rows)

    return cohorts, price, mask, dates, theta_for


def _row(arm: str, stage: str, v, ids_k: int) -> dict:
    return {
        "arm": arm, "stage": stage, "k": v.k, "rank": v.rank,
        "min_pair_differ_qh": v.min_pair_differ,
        "worst_pair": "|".join(v.worst_pair) if v.worst_pair else "",
        "cond_s": round(v.cond_s, 3) if np.isfinite(v.cond_s) else "inf",
        "cond_ws": round(v.cond_ws, 3) if np.isfinite(v.cond_ws) else "inf",
        "collinear_capacity_share": round(v.collinear_capacity_share, 4),
        "i4_exposure_differs_days": v.exposure_differs_days,
        "i4_old_verdict": ("K-cohort stands"
                           if (v.exposure_differs_days or 0) >= 10 else "FALLBACK"),
        "new_verdict": "pass" if v.passed else "FAIL",
        "reasons": "; ".join(v.reasons),
    }


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifact-dir", default=None,
                    help="directory of cell_*.npz (default: e1_gate_artifacts)")
    a = ap.parse_args()
    global ARTIFACT_DIR, OUT_CSV
    if a.artifact_dir:
        ARTIFACT_DIR = Path(a.artifact_dir)
        if not ARTIFACT_DIR.is_absolute():
            ARTIFACT_DIR = REPO_ROOT / ARTIFACT_DIR
        tag = ARTIFACT_DIR.name.replace("e1_gate_artifacts", "").strip("_")
        OUT_CSV = OUT_CSV.with_name(
            f"{OUT_CSV.stem}_{tag or 'alt'}{OUT_CSV.suffix}")
        print(f"scoring artifacts in {ARTIFACT_DIR}")
    rows: list[dict] = []
    print("=" * 78)
    print("IDENTIFICATION: old I4 day count vs the proposed composite criterion")
    print(f"  proposed: rank(s) == K, every pair differing on >= "
          f"{MIN_PAIR_DIFFER_QH} QH, cond(s) <= {MAX_COND_S:.0f}")
    print("=" * 78)

    # ---------------------------------------------------- real panel, four settings
    cohorts, price, mask, dates, theta_for = _real_panel_theta()
    ids, w = cohorts.ids, list(cohorts.shares)
    p = price[mask]
    print(f"\nREAL PANEL (DE), evaluation window = months with a published market "
          f"value: {int(mask.sum()):,} QH\n")
    print(f"{'setting':<9}{'stage':<9}{'K':>4}{'rank':>6}{'minpair':>9}"
          f"{'cond(s)':>10}{'I4 days':>9}{'old':>18}{'new':>7}")
    for setting in AW_SETTINGS:
        theta = theta_for(setting)[:, mask]
        s = (p[None, :] < theta).astype(float)
        depth = np.maximum(0.0, theta - p[None, :]) * s
        nd, _ = exposure_differs_by_day(s, dates[mask])
        before = gate_identification_verdict(s, ids, w, depth,
                                             exposure_differs_days=nd)
        rows.append(_row(f"real_{setting}", "before_merge", before, len(ids)))

        # The tied-response fallback, under each candidate partition. Reported for
        # the UNMERGED design too, so the pre-registered clock partition can be seen
        # going degenerate rather than merely asserted to.
        print(f"  -- fallback, '{setting}', before merge --")
        for mode in FALLBACK_MODES:
            fp = fallback_partition(cohorts, theta, mode)
            print(format_fallback(fallback_identifiability(s, w, fp)))

        merged, theta_m, gmap = merge_cohorts(cohorts, np.hstack([s, depth]), theta,
                                           rule="exposure")
        s_m = (p[None, :] < theta_m).astype(float)
        depth_m = np.maximum(0.0, theta_m - p[None, :]) * s_m
        print(f"  -- fallback, '{setting}', after merge --")
        fb_rows = []
        for mode in FALLBACK_MODES:
            fp = fallback_partition(merged, theta_m, mode)
            fd = fallback_identifiability(s_m, list(merged.shares), fp)
            print(format_fallback(fd))
            fb_rows.append((mode, fd))
        ok = [m for m, fd in fb_rows if fd.identified]
        print(f"    -> identified under: {ok or 'NOTHING'}   "
              f"(pre-registered 'clock' "
              f"{'survives' if 'clock' in ok else 'does NOT survive'} the merge)")

        nd_m, _ = exposure_differs_by_day(s_m, dates[mask])
        after = gate_identification_verdict(s_m, merged.ids, list(merged.shares),
                                            depth_m, exposure_differs_days=nd_m)
        rows.append(_row(f"real_{setting}", "after_merge", after, len(merged)))

        for stage, v in (("before", before), ("after", after)):
            print(f"{setting:<9}{stage:<9}{v.k:>4}{v.rank:>6}{v.min_pair_differ:>9,}"
                  f"{v.cond_s:>10.1f}"
                  f"{(v.exposure_differs_days or 0):>9}"
                  f"{('K-cohort stands' if (v.exposure_differs_days or 0) >= 10 else 'FALLBACK'):>18}"
                  f"{('pass' if v.passed else 'FAIL'):>7}")
        n_theta = sum(1 for g in theta_merge_map(theta, ids, w) if g.is_merge)
        n_feat = sum(1 for g in gmap if g.is_merge)
        print(f"{'':<9}merge map: theta-keyed would merge {n_theta}, "
              f"feature-keyed merges {n_feat}")
        print(format_merge_map(gmap))
        for reason in before.reasons:
            print(f"{'':<9}before: {reason}")
        print()

    # ------------------------------------------------------- E1 gate artifacts
    print("=" * 78)
    print("E1 GATE ARTIFACTS (stored s / depth / shares -- no refit)")
    print("=" * 78)
    paths = sorted(ARTIFACT_DIR.glob("cell_*.npz"))
    if not paths:
        print("  no artifacts on disk; skipping")
    else:
        fallback_ids = mastr_cohort_set("DE").ids
        agg: list[tuple[str, object]] = []
        for path in paths:
            z = np.load(path, allow_pickle=False)
            s, depth, sh = z["s"].astype(float), z["depth"].astype(float), z["shares"]
            mids = ([str(x) for x in z["cohort_ids"]] if "cohort_ids" in z.files
                    else fallback_ids)
            if len(mids) != s.shape[0]:
                print(f"  {path.name}: stored K={s.shape[0]} but cohort set has "
                      f"{len(mids)}; skipping")
                z.close()
                continue
            nd, _ = exposure_differs_by_day(s, z["berlin_date"])
            v = gate_identification_verdict(s, mids, list(sh), depth,
                                            exposure_differs_days=nd)
            agg.append((path.stem, v))
            rows.append(_row(f"e1_{path.stem}", "as_generated", v, len(mids)))
            z.close()
        n_fail = sum(1 for _, v in agg if not v.passed)
        n_old_pass = sum(1 for _, v in agg
                         if (v.exposure_differs_days or 0) >= 10)
        print(f"  cells scored: {len(agg)}")
        print(f"  old I4 day count passes: {n_old_pass}/{len(agg)}")
        print(f"  proposed criterion FAILS: {n_fail}/{len(agg)}")
        if agg:
            ex = agg[0][1]
            print(f"  every cell is identical in design; example "
                  f"({agg[0][0]}):")
            print(f"    rank {ex.rank}/{ex.k}   min pair {ex.min_pair_differ} QH   "
                  f"cond(s) {ex.cond_s:.1f}   I4 days {ex.exposure_differs_days}")
            for r in ex.reasons:
                print(f"    reason: {r}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        wr.writeheader()
        wr.writerows(rows)
    print(f"\nWrote {OUT_CSV.relative_to(REPO_ROOT)}  ({len(rows)} rows)")


if __name__ == "__main__":
    main()
