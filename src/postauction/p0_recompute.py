"""P0 -- recompute the planning assumptions and the event-day counts from the panel.

    python -m src.postauction.p0_recompute

Writes, under artifacts/P0/:

  p0_planning_recompute.csv   the quantities that replace the planning assumptions
                              (sigma ~ 1,150 MW, rho ~ 0.85, "44%"), with 95%
                              event-day block-bootstrap CIs (5,000 draws, seed 42)
  p0_event_day_counts.csv     negative-price quarter-hours and event-days per price
                              band, per split and per area
  p0_counts_by_month.csv      the same by month, so the S2 deep test set can be
                              located in time
  p0_largest_error_days.csv   the five largest-|error| event-days per area/series,
                              named so P1's "without the five largest-error days"
                              arm is fixed before any model runs

No model is fitted here and no test-set metric is computed: everything is a
descriptive statistic of the day-ahead forecast error e = G - F on the panel.

Definitions (all pre-registered in docs/P0_preregistration.md section 3):

  window        Berlin-local date >= 2025-10-01 (MTU15_FIRST_DELIVERY_DAY), to the
                end of the panel
  negative QH   quarter-hour day-ahead price < 0; event-day = a Berlin date with at
                least one negative QH
  positive QH   price >= 0; safe QH: price > 5
  sigma_pos     sd of e over positive QHs; sigma_pos_matched reweights the within-
                forecast-decile variances by the negative QHs' decile shares
  rho_1         within-day lag-1 autocorrelation of e (consecutive QHs of the same
                Berlin date, event-days only), and the AR(1) effective sample size
                n_eff = n_neg (1 - rho) / (1 + rho)
  daily bias    per event-day mean of e over its negative QHs: mean and between-day sd
  best case     RMSE reduction on negative QHs if the conditional bias were removed:
                  (a) pooled mean bias removed          -- the construction behind "44%"
                  (b) price-band-conditional mean removed (the 4 bands)
                  (c) event-day-conditional mean removed  -- ex post, an upper bound
                  (d) all error above the matched positive-price noise floor removed
                The STOP statistic is (a); P0 section 4 says why.

Every bootstrap is over Berlin-local event-days (or days, for positive-QH
statistics), resampled with replacement, statistics recomputed from per-day
sufficient statistics so the 5,000 draws are exact and fast.
"""

from __future__ import annotations

import csv
import subprocess
from datetime import date

import numpy as np
import polars as pl

from src.method.day_bootstrap import (
    AREAS, ARTIFACTS, BANDS, DEEP_THRESHOLD, N_BOOT, SEED, SERIES, WINDOW_START,
    bootstrap_day_sums, ci95, day_index, load_window,
)

OUT_DIR = ARTIFACTS / "P0"
N_LARGEST = 5
THIN_OVERLAP_MW = 40_000.0       # spec v1.8 I2: report separately above 40 GW forecast
MIN_DEEP_DAYS = 15               # P0 STOP: deep test set below this many event-days
MIN_BEST_CASE = 0.15             # P0 STOP: best-case RMSE reduction (a) below this
# Four planning assumptions this script replaces, verbatim from the Phase P brief.
PLANNING = {"sigma_mw": 1150.0, "rho": 0.85, "bias_mw": -1684.0, "best_case": 0.44}


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


# ------------------------------------------------------------------ sufficient stats


def _sums(e: np.ndarray, idx: np.ndarray, n_days: int) -> np.ndarray:
    """Per-day [n, sum e, sum e^2] for whatever rows are passed."""
    out = np.zeros((n_days, 3))
    np.add.at(out[:, 0], idx, 1.0)
    np.add.at(out[:, 1], idx, e)
    np.add.at(out[:, 2], idx, e * e)
    return out


def _sd_from_sums(S: np.ndarray) -> np.ndarray:
    n, s1, s2 = S[..., 0], S[..., 1], S[..., 2]
    with np.errstate(invalid="ignore", divide="ignore"):
        var = s2 / n - (s1 / n) ** 2
    return np.sqrt(np.maximum(var, 0.0))


def _rmse_from_sums(S: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.sqrt(S[..., 2] / S[..., 0])


def _mean_from_sums(S: np.ndarray) -> np.ndarray:
    with np.errstate(invalid="ignore", divide="ignore"):
        return S[..., 1] / S[..., 0]


def _lag1_sums(e: np.ndarray, idx: np.ndarray, ts: np.ndarray, n_days: int) -> np.ndarray:
    """Per-day sums over consecutive within-day pairs: [n, Sx, Sy, Sxx, Syy, Sxy]."""
    same_day = idx[1:] == idx[:-1]
    consecutive = (ts[1:] - ts[:-1]) == 15 * 60 * 1000
    ok = same_day & consecutive
    x, y, d = e[:-1][ok], e[1:][ok], idx[:-1][ok]
    out = np.zeros((n_days, 6))
    for j, v in enumerate((np.ones_like(x), x, y, x * x, y * y, x * y)):
        np.add.at(out[:, j], d, v)
    return out


def _rho_from_sums(S: np.ndarray) -> np.ndarray:
    n, sx, sy, sxx, syy, sxy = (S[..., j] for j in range(6))
    with np.errstate(invalid="ignore", divide="ignore"):
        cov = sxy / n - (sx / n) * (sy / n)
        vx = sxx / n - (sx / n) ** 2
        vy = syy / n - (sy / n) ** 2
        return cov / np.sqrt(vx * vy)


# ------------------------------------------------------------------------ one area


def recompute(area: str, series: str) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    f_col, g_col = SERIES[series]
    df_all = load_window(area)
    # The panel stores missing output as float NaN in places, which `is_not_null`
    # does not catch. Drop and COUNT, never fill: a dropped quarter-hour is reported.
    finite = (pl.col(f_col).is_not_null() & pl.col(g_col).is_not_null()
              & pl.col(f_col).is_not_nan() & pl.col(g_col).is_not_nan())
    df = df_all.filter(finite)
    n_dropped = df_all.height - df.height
    price = df["price_eur_mwh"].to_numpy()
    f = df[f_col].to_numpy()
    g = df[g_col].to_numpy()
    e = g - f
    ts = df["ts_utc"].to_numpy().astype("int64")
    band = df["band"].to_numpy().astype(str)
    neg = price < 0
    pos = ~neg
    deep = price <= DEEP_THRESHOLD
    days_all, idx_all = day_index(df["berlin_date"].to_numpy())
    n_days_all = days_all.size
    event_day_mask = np.zeros(n_days_all, dtype=bool)
    event_day_mask[np.unique(idx_all[neg])] = True
    n_event_days = int(event_day_mask.sum())

    rows: list[dict] = []
    base = {"area": area, "series": series, "window_start": WINDOW_START,
            "n_boot": N_BOOT, "seed": SEED}
    rows.append({**base, "quantity": "n_qh_dropped_missing_F_or_G", "value": float(n_dropped),
                 "ci_lo": np.nan, "ci_hi": np.nan, "n_qh": int(df_all.height),
                 "n_days": int(np.unique(df_all["berlin_date"].to_numpy()).size),
                 "planning_assumption": None,
                 "note": "window rows whose F or G is null/NaN, excluded from every statistic"})

    def add(quantity: str, value: float, lo: float, hi: float, n_qh: int, n_days: int,
            note: str = "", planning: float | None = None) -> None:
        rows.append({**base, "quantity": quantity, "value": value, "ci_lo": lo,
                     "ci_hi": hi, "n_qh": n_qh, "n_days": n_days,
                     "planning_assumption": planning, "note": note})

    # --- (1) residual sd on positive-price QHs -------------------------------------
    # Day blocks for positive-QH statistics are ALL days (every day has positive QHs).
    S_pos = _sums(e[pos], idx_all[pos], n_days_all)
    boot = bootstrap_day_sums(S_pos)
    add("sigma_pos_mw", float(_sd_from_sums(S_pos.sum(0))), *ci95(_sd_from_sums(boot)),
        int(pos.sum()), n_days_all, "sd of G-F over price >= 0 QHs",
        planning=PLANNING["sigma_mw"])
    safe = price > 5.0
    S_safe = _sums(e[safe], idx_all[safe], n_days_all)
    boot = bootstrap_day_sums(S_safe)
    add("sigma_safe_mw", float(_sd_from_sums(S_safe.sum(0))), *ci95(_sd_from_sums(boot)),
        int(safe.sum()), n_days_all, "sd of G-F over price > 5 QHs")
    S_neg = _sums(e[neg], idx_all[neg], n_days_all)
    boot = bootstrap_day_sums(S_neg)
    add("sigma_neg_mw", float(_sd_from_sums(S_neg.sum(0))), *ci95(_sd_from_sums(boot)),
        int(neg.sum()), n_event_days, "sd of G-F over negative-price QHs (event-day blocks)")

    # Matched to negative-QH forecast levels: deciles of F over the window, weights =
    # the negative QHs' decile shares, pooled within-decile variance on positive QHs.
    edges = np.quantile(f, np.linspace(0, 1, 11)[1:-1])
    dec = np.digitize(f, edges)                       # 0..9
    w = np.bincount(dec[neg], minlength=10) / max(1, neg.sum())
    S_dec = np.stack([_sums(e[pos & (dec == d)], idx_all[pos & (dec == d)], n_days_all)
                      for d in range(10)], axis=1)   # (days, 10, 3)
    full = S_dec.sum(0)                               # (10, 3)
    sd_matched = float(np.sqrt(np.sum(w * _sd_from_sums(full) ** 2)))
    rng = np.random.default_rng(SEED)
    draws = rng.integers(0, n_days_all, size=(N_BOOT, n_days_all))
    boot_dec = S_dec[draws].sum(axis=1)               # (B, 10, 3)
    sd_b = np.sqrt(np.nansum(w * np.nan_to_num(_sd_from_sums(boot_dec)) ** 2, axis=1))
    add("sigma_pos_matched_mw", sd_matched, *ci95(sd_b), int(pos.sum()), n_days_all,
        "within-F-decile sd on price >= 0 QHs, reweighted to the negative QHs' decile shares",
        planning=PLANNING["sigma_mw"])
    add("share_neg_qh_above_40gw_forecast", float((f[neg] > THIN_OVERLAP_MW).mean()),
        np.nan, np.nan, int(neg.sum()), n_event_days,
        "spec I2 thin-overlap region; count = share x n_qh")

    # --- (2) within-day lag-1 autocorrelation and the effective sample size ---------
    ev_rows = event_day_mask[idx_all]
    L_ev = _lag1_sums(e[ev_rows], idx_all[ev_rows], ts[ev_rows], n_days_all)
    L_ev = L_ev[event_day_mask]                       # event-day blocks only
    rho = float(_rho_from_sums(L_ev.sum(0)))
    boot = bootstrap_day_sums(L_ev)
    lo, hi = ci95(_rho_from_sums(boot))
    add("rho_lag1_within_day_event_days", rho, lo, hi, int(L_ev[:, 0].sum()), n_event_days,
        "corr(e_t, e_t+1) over consecutive QHs of the same Berlin date, event-days",
        planning=PLANNING["rho"])
    L_neg = _lag1_sums(e[neg], idx_all[neg], ts[neg], n_days_all)[event_day_mask]
    rho_neg = float(_rho_from_sums(L_neg.sum(0)))
    boot = bootstrap_day_sums(L_neg)
    add("rho_lag1_within_negative_runs", rho_neg, *ci95(_rho_from_sums(boot)),
        int(L_neg[:, 0].sum()), n_event_days,
        "corr over consecutive negative-price QHs only")
    n_neg = int(neg.sum())
    for name, r in (("n_eff_ar1_from_rho_event_days", rho),
                    ("n_eff_ar1_from_rho_negative_runs", rho_neg)):
        n_eff = n_neg * (1 - r) / (1 + r) if np.isfinite(r) else np.nan
        add(name, float(n_eff), np.nan, np.nan, n_neg, n_event_days,
            "n_neg (1-rho)/(1+rho); the event-day count is the honest unit")

    # --- (3) daily mean bias on negative QHs ----------------------------------------
    S_ev = S_neg[event_day_mask]
    daily_mean = S_ev[:, 1] / S_ev[:, 0]
    add("mean_bias_neg_pooled_mw", float(_mean_from_sums(S_ev.sum(0))),
        *ci95(_mean_from_sums(bootstrap_day_sums(S_ev))), n_neg, n_event_days,
        "QH-weighted mean of G-F over negative QHs (kill-test construction)",
        planning=PLANNING["bias_mw"])
    rng = np.random.default_rng(SEED)
    draws = rng.integers(0, n_event_days, size=(N_BOOT, n_event_days))
    dm_b = daily_mean[draws]
    add("mean_daily_bias_neg_mw", float(daily_mean.mean()), *ci95(dm_b.mean(axis=1)),
        n_neg, n_event_days, "mean over event-days of the day's mean G-F on its negative QHs")
    add("between_day_sd_daily_bias_neg_mw", float(daily_mean.std(ddof=1)),
        *ci95(dm_b.std(axis=1, ddof=1)), n_neg, n_event_days,
        "sd across event-days of the daily mean bias")
    within = np.sqrt(np.maximum(S_ev[:, 2] / S_ev[:, 0] - daily_mean ** 2, 0))
    add("within_day_sd_neg_mw_median", float(np.median(within)), np.nan, np.nan,
        n_neg, n_event_days, "median over event-days of the within-day sd of G-F on negative QHs")

    # --- (4) best-case RMSE reduction on negative QHs -------------------------------
    rmse = float(_rmse_from_sums(S_ev.sum(0)))
    boot_S = bootstrap_day_sums(S_ev)
    add("rmse_F_neg_mw", rmse, *ci95(_rmse_from_sums(boot_S)), n_neg, n_event_days,
        "RMSE of F on negative QHs")
    # (a) pooled mean removed: residual sd / RMSE
    red_a = 1.0 - float(_sd_from_sums(S_ev.sum(0))) / rmse
    red_a_b = 1.0 - _sd_from_sums(boot_S) / _rmse_from_sums(boot_S)
    add("best_case_rmse_reduction_a_pooled_bias", red_a, *ci95(red_a_b), n_neg,
        n_event_days, "1 - sd(e|neg)/RMSE(e|neg): the '44%' construction. P0 STOP statistic",
        planning=PLANNING["best_case"])
    # (b) band-conditional mean removed
    S_band = np.stack([_sums(e[neg & (band == b)], idx_all[neg & (band == b)], n_days_all)
                       for b, _, _ in BANDS], axis=1)[event_day_mask]   # (ev, 4, 3)
    def _red_b(Sb, Stot):
        # residual SS after removing each band's mean: sum_b (S2_b - S1_b^2/n_b)
        with np.errstate(invalid="ignore", divide="ignore"):
            ss = np.nansum(Sb[..., 2] - Sb[..., 1] ** 2 / Sb[..., 0], axis=-1)
            return 1.0 - np.sqrt(ss / Stot[..., 0]) / _rmse_from_sums(Stot)
    red_b = float(_red_b(S_band.sum(0), S_ev.sum(0)))
    draws = rng.integers(0, n_event_days, size=(N_BOOT, n_event_days))
    red_b_b = _red_b(S_band[draws].sum(1), S_ev[draws].sum(1))
    add("best_case_rmse_reduction_b_band_bias", red_b, *ci95(red_b_b), n_neg, n_event_days,
        "price-band-conditional mean removed (4 bands)")
    # (c) event-day-conditional mean removed (ex post upper bound)
    def _red_c(Sd, Stot):
        with np.errstate(invalid="ignore", divide="ignore"):
            ss = np.sum(Sd[..., 2] - Sd[..., 1] ** 2 / Sd[..., 0], axis=-1)
            return 1.0 - np.sqrt(ss / Stot[..., 0]) / _rmse_from_sums(Stot)
    red_c = float(_red_c(S_ev, S_ev.sum(0)))
    red_c_b = _red_c(S_ev[draws], S_ev[draws].sum(1))
    add("best_case_rmse_reduction_c_daily_bias", red_c, *ci95(red_c_b), n_neg, n_event_days,
        "event-day-conditional mean removed; ex post, not reachable at forecast time")
    # (d) everything above the positive-price noise floor removed: the most generous
    # reading, in which the matched positive-QH sd is the irreducible weather noise and
    # all remaining negative-QH error is "conditional bias" of some kind.
    red_d = 1.0 - sd_matched / rmse
    red_d_b = 1.0 - sd_b / _rmse_from_sums(boot_S)   # independent day draws, same seed
    add("best_case_rmse_reduction_d_noise_floor", red_d, *ci95(red_d_b), n_neg, n_event_days,
        "1 - sigma_pos_matched/RMSE(e|neg): all error above the positive-price noise floor removed")
    add("stop_p0_best_case_below_15pct", float(red_a < MIN_BEST_CASE), np.nan, np.nan,
        n_neg, n_event_days, f"1 if (a) < {MIN_BEST_CASE:.2f}")

    # --- (5) counts: bands, deep set, splits -------------------------------------------
    counts: list[dict] = []
    def cnt(label: str, m: np.ndarray, note: str = "") -> None:
        counts.append({"area": area, "series": series, "set": label,
                       "n_qh": int(m.sum()), "n_event_days": int(np.unique(idx_all[m]).size),
                       "note": note})
    cnt("negative_all", neg, "price < 0")
    for b, _, _ in BANDS:
        cnt(f"band {b}", neg & (band == b))
    cnt("S2_test_deep (<= -20)", deep, "S2 test set; P0 STOP if < 15 event-days")
    cnt("S2_train_shallow_negative (-20, 0)", neg & ~deep, "negative QHs available to S2 training")
    cnt("S2_train_all (> -20)", ~deep, "all QHs available to S2 training")
    cnt("S1_negative_event_days", neg, "leave-one-event-day-out folds = event-days")
    cnt("negative_forecast_above_40gw", neg & (f > THIN_OVERLAP_MW), "thin-overlap arm")
    cnt("positive_all", pos, "S3 placebo pool before matching")
    cnt("positive_safe (> 5)", safe, "S3 primary placebo pool")
    cnt("positive_0_to_5", pos & ~safe, "Hirth's 0-5 band, consistency only")
    counts.append({"area": area, "series": series, "set": "stop_p0_deep_days_below_15",
                   "n_qh": int(np.unique(idx_all[deep]).size < MIN_DEEP_DAYS),
                   "n_event_days": int(np.unique(idx_all[deep]).size),
                   "note": "1 if the deep test set has fewer than 15 event-days"})

    # by month
    months = np.array([d[:7] for d in df["berlin_date"].to_numpy().astype(str)])
    by_month: list[dict] = []
    for mth in sorted(set(months)):
        mm = months == mth
        row = {"area": area, "series": series, "month": mth,
               "n_qh": int(mm.sum()), "neg_qh": int((mm & neg).sum()),
               "neg_event_days": int(np.unique(idx_all[mm & neg]).size),
               "deep_qh": int((mm & deep).sum()),
               "deep_event_days": int(np.unique(idx_all[mm & deep]).size)}
        for b, _, _ in BANDS:
            row[f"qh {b}"] = int((mm & neg & (band == b)).sum())
        by_month.append(row)

    # largest-|error| event-days, by |sum of e over negative QHs|
    order = np.argsort(-np.abs(S_ev[:, 1]))[:N_LARGEST]
    ev_days = days_all[event_day_mask]
    largest = [{"area": area, "series": series, "rank": i + 1, "berlin_date": str(ev_days[j]),
                "neg_qh": int(S_ev[j, 0]), "sum_error_mwh": float(S_ev[j, 1] * 0.25),
                "mean_error_mw": float(S_ev[j, 1] / S_ev[j, 0]),
                "share_of_total_neg_abs_error": float(abs(S_ev[j, 1]) / np.abs(S_ev[:, 1]).sum())}
               for i, j in enumerate(order)]
    return rows, counts, by_month, largest


def write(path, rows: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    head = git_head()
    all_rows, all_counts, all_months, all_largest = [], [], [], []
    for area in AREAS:
        for series in SERIES:
            r, c, m, l = recompute(area, series)
            for x in r + c + m + l:
                x["git_head"] = head
                x["run_date"] = date.today().isoformat()
            all_rows += r; all_counts += c; all_months += m; all_largest += l
            print(f"{area:<11}{series:<8} done")
    write(OUT_DIR / "p0_planning_recompute.csv", all_rows)
    write(OUT_DIR / "p0_event_day_counts.csv", all_counts)
    write(OUT_DIR / "p0_counts_by_month.csv", all_months)
    write(OUT_DIR / "p0_largest_error_days.csv", all_largest)

    # console summary, DE onshore and DE total
    print(f"\n{'quantity':<44}{'DE onshore':>14}{'[CI]':>26}{'DE total':>14}{'[CI]':>26}{'planning':>10}")
    rows_by = {(r["series"], r["quantity"]): r for r in all_rows if r["area"] == "DE"}
    for q in [r["quantity"] for r in all_rows if r["area"] == "DE" and r["series"] == "onshore"]:
        a, b = rows_by[("onshore", q)], rows_by[("total", q)]
        fmt = lambda r: (f"{r['value']:>14.4g}", f"[{r['ci_lo']:.4g}, {r['ci_hi']:.4g}]" if np.isfinite(r["ci_lo"]) else "")
        pa, pb = fmt(a), fmt(b)
        pl_ = "" if a["planning_assumption"] is None else f"{a['planning_assumption']:.4g}"
        print(f"{q:<44}{pa[0]}{pa[1]:>26}{pb[0]}{pb[1]:>26}{pl_:>10}")
    print("\nEvent-day counts (DE onshore):")
    for c in all_counts:
        if c["area"] == "DE" and c["series"] == "onshore":
            print(f"  {c['set']:<40}{c['n_qh']:>8} QH {c['n_event_days']:>5} days  {c['note']}")
    print("\nLargest-error event-days (DE onshore):")
    for l in all_largest:
        if l["area"] == "DE" and l["series"] == "onshore":
            print(f"  {l['rank']} {l['berlin_date']} neg_qh={l['neg_qh']:>3} "
                  f"mean_err={l['mean_error_mw']:>9.1f} MW share={l['share_of_total_neg_abs_error']:.3f}")


if __name__ == "__main__":
    main()
