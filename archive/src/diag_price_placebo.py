"""4a-proper: does the price predict the forecast error where no incentive exists?

    python src/diag_price_placebo.py

The test-1 question
-------------------
`src/diag_price_logratio.py` (4a-response, `results/15_*`) measured how far output
falls below forecast as the price goes negative. That is the switch-off response, and
RQ1 already established it; it is not evidence that the mechanism story is the right
one.

This script asks the falsification question instead. **Restricted to price >
5 EUR/MWh, where no EEG switch-off incentive exists**, does the price still predict
log(G/F) once F itself is controlled for?

  If YES, the price is a proxy for something in the forecast error that has nothing
  to do with switching off -- scarcity, load, conventional availability, whatever --
  and a model that reads a price response at negative prices may be reading that
  instead. It would undermine the identification.

  If NO, the price carries no information about the forecast error in the region
  where the mechanism is switched off, which is what the mechanism story requires.

The model
---------
    log(G/F) ~ spline(F) + price band + hour-of-day + month

with price bands inside the positive range -- (5,20], (20,50], (50,100], (100,150],
> 150 EUR/MWh -- and **(50,100] as the reference**. The spline in F is what makes this
a test of price *beyond* F: F is the dominant driver of the relative error, and
without it the price bands would simply pick up the wind level they coincide with.
Hour-of-day and month absorb the diurnal and seasonal structure of the forecast error.

Inference is a 95% **event-day block bootstrap**: whole Berlin-local days are
resampled and the model is refitted on each draw. Refitting is exact rather than
approximate -- each day's X'X and X'y are accumulated once, and a draw sums the drawn
days' matrices -- so 5,000 refits cost seconds.

The pre-registered verdict rule, fixed before the numbers were seen
------------------------------------------------------------------
    The price PREDICTS forecast error beyond F if the (5,20] vs (50,100] contrast CI
    excludes 0 in BOTH areas with the SAME sign. Otherwise NO.

Redispatch
----------
Redispatch reduces G for grid reasons, not price reasons, so it has to be dealt with.
Both treatments the decision asked for are reported:

  exclude   drop every quarter-hour touched by a renewable reduction measure.
  add back  add the measure's power back into G.

**The series available is not "onshore wind redispatch", and the add-back is an upper
bound rather than a correction.** The export's `PRIMAERENERGIEART` column has exactly
one value, "Erneuerbar", for all 7,067 reduction measures -- no fuel detail at all --
and the plant names are cluster and substation codes ("AVA Cluster Ganderkesee",
"50H_TEN_CR_S1_ATF"): `onshore` matches none of them and `offshore` four. The only
separation possible is a name filter for solar, which removes 354 measures and leaves
6,713 that are wind, offshore wind, other renewables and any PV whose name does not
say so. Excluding those quarter-hours is therefore conservative and sound -- it
removes wind redispatch and more. Adding them back over-corrects by whatever share is
not onshore wind, which this export cannot reveal. Read the exclusion variant as
primary.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import polars as pl

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.method.projection_and_redispatch import redispatch_qh  # noqa: E402

PANEL = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"
OUT_CSV = REPO_ROOT / "results" / "16_4a_proper_placebo.csv"

AREAS = ("DE", "50Hertz")
BANDS = (("(5,20]", 5.0, 20.0), ("(20,50]", 20.0, 50.0), ("(50,100]", 50.0, 100.0),
         ("(100,150]", 100.0, 150.0), ("> 150", 150.0, None))
REFERENCE = "(50,100]"
CONTRAST = "(5,20]"          # the band the verdict rule turns on
N_BOOT = 5000
SEED = 42
F_FLOOR_FRACTION = 0.02


# ------------------------------------------------------------------ design matrix


def spline_basis(x: np.ndarray, n_knots: int) -> np.ndarray:
    """Cubic B-spline basis on quantile knots, via sklearn, without the bias column."""
    from sklearn.preprocessing import SplineTransformer

    st = SplineTransformer(n_knots=n_knots, degree=3, include_bias=False,
                           knots="quantile")
    return st.fit_transform(x.reshape(-1, 1))


def build_design(df: pl.DataFrame, n_knots: int) -> tuple[np.ndarray, list[str]]:
    """Intercept, spline in F, band dummies (reference dropped), hour, month."""
    f = df["f"].to_numpy()
    cols = [np.ones((df.height, 1))]
    names = ["intercept"]

    sp = spline_basis(f, n_knots)
    cols.append(sp)
    names += [f"spline_F_{i}" for i in range(sp.shape[1])]

    band = df["band"].to_numpy()
    for label, _, _ in BANDS:
        if label == REFERENCE:
            continue
        cols.append((band == label).astype(float).reshape(-1, 1))
        names.append(f"band_{label}")

    hour = df["hour"].to_numpy()
    for h in range(1, 24):                      # hour 0 is the reference
        cols.append((hour == h).astype(float).reshape(-1, 1))
        names.append(f"hour_{h:02d}")

    month = df["month"].to_numpy()
    uniq_m = sorted(set(month.tolist()))
    for m in uniq_m[1:]:                        # first month is the reference
        cols.append((month == m).astype(float).reshape(-1, 1))
        names.append(f"month_{m}")

    return np.hstack(cols), names


def fit_with_eventday_bootstrap(X: np.ndarray, y: np.ndarray, days: np.ndarray,
                                n_boot: int = N_BOOT, seed: int = SEED) -> dict:
    """OLS plus an event-day block bootstrap, refitting exactly on each draw.

    Each day's X'X and X'y are accumulated once; a draw of days is then a weighted
    sum of those, which is algebraically identical to refitting on the resampled rows
    and costs a matrix-vector product instead of a least-squares solve on 34,000 rows.
    """
    uniq, inv = np.unique(days, return_inverse=True)
    n_days, p = len(uniq), X.shape[1]

    xtx = np.zeros((n_days, p, p))
    xty = np.zeros((n_days, p))
    for d in range(n_days):
        m = inv == d
        xd, yd = X[m], y[m]
        xtx[d] = xd.T @ xd
        xty[d] = xd.T @ yd

    def solve(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        try:
            return np.linalg.solve(a, b)
        except np.linalg.LinAlgError:
            return np.linalg.lstsq(a, b, rcond=None)[0]

    beta = solve(xtx.sum(axis=0), xty.sum(axis=0))

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n_days, size=(n_boot, n_days))
    boot = np.empty((n_boot, p))
    singular = 0
    for b in range(n_boot):
        c = np.bincount(idx[b], minlength=n_days).astype(float)
        a = np.tensordot(c, xtx, axes=(0, 0))
        try:
            boot[b] = np.linalg.solve(a, c @ xty)
        except np.linalg.LinAlgError:
            boot[b] = np.linalg.lstsq(a, c @ xty, rcond=None)[0]
            singular += 1

    lo, hi = np.percentile(boot, [2.5, 97.5], axis=0)
    # Two-sided bootstrap p-value per coefficient, floored at 1/n_boot because a
    # bootstrap cannot resolve a p-value finer than its own resolution.
    frac_le = (boot <= 0).mean(axis=0)
    frac_ge = (boot >= 0).mean(axis=0)
    pval = np.clip(2.0 * np.minimum(frac_le, frac_ge), 1.0 / n_boot, 1.0)
    return {"beta": beta, "lo": lo, "hi": hi, "p": pval, "n_days": n_days,
            "n_obs": int(X.shape[0]), "singular_draws": singular}


def holm(pvals: list[float]) -> list[float]:
    """Holm-Bonferroni step-down adjusted p-values, order preserved."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, (m - rank) * pvals[i])
        adj[i] = min(1.0, running)
    return adj


# ------------------------------------------------------------------- data loading


def load_area(panel: pl.DataFrame, area: str, rd: pl.DataFrame,
              treatment: str) -> pl.DataFrame:
    """Positive-price quarter-hours for one area, with the chosen redispatch treatment."""
    df = (panel.filter(pl.col("area") == area)
                .select(["ts_utc", "berlin_date", "price_eur_mwh",
                         "act_wind_mw", "da_wind_mw"])
                .rename({"act_wind_mw": "g", "da_wind_mw": "f"})
                .drop_nulls()
                .filter(pl.col("g").is_finite() & pl.col("f").is_finite()
                        & pl.col("price_eur_mwh").is_finite()))
    floor = F_FLOOR_FRACTION * float(df["f"].median())
    df = df.filter((pl.col("f") > floor) & (pl.col("price_eur_mwh") > 5.0))

    area_rd = rd.filter(pl.col("area") == (area if area != "DE" else "DE_TOTAL"))
    df = (df.join(area_rd.select(["ts_utc", "rd_mw"]), on="ts_utc", how="left")
            .with_columns(pl.col("rd_mw").fill_null(0.0)))
    if treatment == "exclude":
        df = df.filter(pl.col("rd_mw") <= 0.0)
    elif treatment == "add_back":
        df = df.with_columns((pl.col("g") + pl.col("rd_mw")).alias("g"))
    elif treatment != "raw":
        raise ValueError(treatment)

    return (df.filter(pl.col("g") > 0.0)
              .with_columns(
                  (pl.col("g") / pl.col("f")).log().alias("y"),
                  pl.from_epoch("ts_utc", time_unit="ms")
                    .dt.convert_time_zone("Europe/Berlin").dt.hour().alias("hour"),
                  pl.col("berlin_date").str.slice(0, 7).alias("month"),
                  pl.when(pl.col("price_eur_mwh") <= 20).then(pl.lit("(5,20]"))
                    .when(pl.col("price_eur_mwh") <= 50).then(pl.lit("(20,50]"))
                    .when(pl.col("price_eur_mwh") <= 100).then(pl.lit("(50,100]"))
                    .when(pl.col("price_eur_mwh") <= 150).then(pl.lit("(100,150]"))
                    .otherwise(pl.lit("> 150")).alias("band")))


def redispatch_all_days(panel: pl.DataFrame) -> pl.DataFrame:
    """Renewable reduction MW per area and quarter-hour, plus a DE total."""
    days = set(panel["berlin_date"].unique().to_list())
    rd = redispatch_qh(days)
    if rd.height == 0:
        return rd.with_columns(pl.lit("DE_TOTAL").alias("area"))
    de = (rd.group_by("ts_utc").agg(pl.col("rd_mw").sum())
            .with_columns(pl.lit("DE_TOTAL").alias("area")))
    return pl.concat([rd, de.select(rd.columns)], how="vertical")


# -------------------------------------------------------------------------- report


def report(df: pl.DataFrame, label: str, n_knots: int, rows: list[dict],
           area: str, treatment: str, stratum: str) -> dict:
    X, names = build_design(df, n_knots)
    res = fit_with_eventday_bootstrap(X, df["y"].to_numpy(), df["berlin_date"].to_numpy())
    print(f"\n  {label}   n={res['n_obs']:,} QH in {res['n_days']} days"
          + (f"   [{res['singular_draws']} singular draws]"
             if res["singular_draws"] else ""))
    print(f"    {'band (vs ' + REFERENCE + ')':<22}{'coef':>10}{'95% CI':>22}"
          f"{'excl 0':>8}{'n QH':>8}{'p raw':>10}  role")
    out = {}
    for lbl, _, _ in BANDS:
        if lbl == REFERENCE:
            continue
        j = names.index(f"band_{lbl}")
        b, lo, hi = res["beta"][j], res["lo"][j], res["hi"][j]
        pv = float(res["p"][j])
        excl = (lo > 0 and hi > 0) or (lo < 0 and hi < 0)
        n_b = int((df["band"].to_numpy() == lbl).sum())
        # The ONE pre-registered test: the CONTRAST band, 'exclude' treatment, all F.
        confirmatory = (lbl == CONTRAST and treatment == "exclude"
                        and stratum == "all F")
        role = "PRE-REGISTERED" if confirmatory else "exploratory"
        print(f"    {lbl:<22}{b:>+10.5f}{f'[{lo:+.5f}, {hi:+.5f}]':>22}"
              f"{str(excl):>8}{n_b:>8,}{pv:>10.4f}  {role}")
        out[lbl] = {"coef": float(b), "lo": float(lo), "hi": float(hi),
                    "excl": excl, "p": pv}
        rows.append({"area": area, "treatment": treatment, "stratum": stratum,
                     "band": lbl, "reference": REFERENCE, "coef": round(float(b), 6),
                     "ci_lo": round(float(lo), 6), "ci_hi": round(float(hi), 6),
                     "ci_excludes_zero": excl, "p_raw": round(pv, 6),
                     "p_holm": "", "role": role, "n_qh_band": n_b,
                     "n_qh_fit": res["n_obs"], "n_days_fit": res["n_days"]})
    return out


def main() -> None:
    panel = pl.read_parquet(PANEL)
    rd = redispatch_all_days(panel)
    rows: list[dict] = []
    verdict_inputs: dict[str, dict] = {}

    notes = {"exclude": "  (PRIMARY -- conservative, but see the band counts)",
             "raw": "  (redispatch left IN G: biases the low bands DOWN)",
             "add_back": "  (UPPER BOUND, over-inclusive: biases the low bands UP)"}
    for treatment in ("exclude", "raw", "add_back"):
        print(f"\n{'=' * 92}\n4a-proper: log(G/F) ~ spline(F) + price band + hour "
              f"+ month,  price > 5 EUR/MWh\nredispatch treatment: {treatment}"
              + notes[treatment] + f"\n{'=' * 92}")
        for area in AREAS:
            df = load_area(panel, area, rd, treatment)
            print(f"\n{area}")
            res = report(df, "all F", 6, rows, area, treatment, "all F")
            if treatment == "exclude":
                verdict_inputs[area] = res

            f = df["f"].to_numpy()
            cuts = np.percentile(f, [33.333, 66.667])
            df = df.with_columns(
                pl.when(pl.col("f") <= cuts[0]).then(pl.lit("low F"))
                  .when(pl.col("f") <= cuts[1]).then(pl.lit("mid F"))
                  .otherwise(pl.lit("high F")).alias("tercile"))
            for terc in ("low F", "mid F", "high F"):
                sub = df.filter(pl.col("tercile") == terc)
                fr = sub["f"].to_numpy()
                report(sub, f"{terc} (F {fr.min():,.0f}-{fr.max():,.0f} MW)",
                       4, rows, area, treatment, terc)

    print(f"\n{'=' * 92}\nPRE-REGISTERED VERDICT\n{'=' * 92}")
    print(f"  Rule: price PREDICTS forecast error beyond F if the {CONTRAST} vs "
          f"{REFERENCE} contrast\n        CI excludes 0 in BOTH areas with the SAME "
          f"sign. Otherwise NO.")
    print(f"  Evaluated on the 'exclude' treatment, all-F stratum.\n")
    signs = []
    for area in AREAS:
        c = verdict_inputs[area][CONTRAST]
        sign = "+" if c["coef"] > 0 else "-"
        signs.append(sign if c["excl"] else None)
        print(f"    {area:<10}coef {c['coef']:+.5f}  CI [{c['lo']:+.5f}, "
              f"{c['hi']:+.5f}]  excludes 0: {c['excl']}  sign {sign}")
    same = signs[0] is not None and signs[0] == signs[1]
    print(f"\n  VERDICT: {'YES -- price predicts forecast error beyond F' if same else 'NO'}")
    if same:
        print("  The price carries information about the forecast error in a region")
        print("  with NO switch-off incentive. A price response fitted at negative")
        print("  prices may be reading this instead of the mechanism. This is a")
        print("  threat to the identification and must be carried into the design.")
    else:
        print("  The price does not predict the forecast error beyond F where no")
        print("  incentive exists -- in both areas with the same sign, which is what")
        print("  the rule requires. This is the result the mechanism story needs.")
    rows.append({"area": "VERDICT", "treatment": "exclude", "stratum": "all F",
                 "band": CONTRAST, "reference": REFERENCE, "coef": "",
                 "ci_lo": "", "ci_hi": "",
                 "ci_excludes_zero": "YES" if same else "NO", "p_raw": "",
                 "p_holm": "", "role": "PRE-REGISTERED VERDICT", "n_qh_band": "",
                 "n_qh_fit": "", "n_days_fit": ""})

    # ---- Holm adjustment over the EXPLORATORY family (noise-audit item 3) ----
    expl = [r for r in rows if r.get("role") == "exploratory"]
    if expl:
        adj = holm([float(r["p_raw"]) for r in expl])
        for r, a in zip(expl, adj):
            r["p_holm"] = round(a, 6)
        n_raw = sum(1 for r in expl if float(r["p_raw"]) < 0.05)
        n_adj = sum(1 for r in expl if float(r["p_holm"]) < 0.05)
        print(f"\n{'=' * 92}\nMULTIPLE TESTING (noise-audit item 3)\n{'=' * 92}")
        print(f"  Exploratory family: {len(expl)} tests "
              f"(band x stratum x treatment x area, excluding the pre-registered one).")
        print(f"  Significant at 0.05 unadjusted: {n_raw}.  After Holm: {n_adj}.")
        surv = sorted((r for r in expl if float(r["p_holm"]) < 0.05),
                      key=lambda r: float(r["p_holm"]))
        if surv:
            print(f"\n  {'area':<10}{'treatment':<10}{'stratum':<9}{'band':<11}"
                  f"{'coef':>10}{'p raw':>10}{'p Holm':>10}")
            for r in surv[:25]:
                print(f"  {r['area']:<10}{r['treatment']:<10}{r['stratum']:<9}"
                      f"{r['band']:<11}{float(r['coef']):>+10.5f}"
                      f"{float(r['p_raw']):>10.4f}{float(r['p_holm']):>10.4f}")
        else:
            print("  Nothing in the exploratory family survives Holm adjustment.")
        for band in ("> 150", "(20,50]"):
            fam = [r for r in expl if r["band"] == band]
            if not fam:
                continue
            kept = [r for r in fam if float(r["p_holm"]) < 0.05]
            print(f"\n  {band} band: {len(kept)} of {len(fam)} exploratory tests "
                  f"survive Holm -> "
                  + ("NOT ROBUST after adjustment" if not kept
                     else f"{len(kept)} robust"))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {OUT_CSV.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
