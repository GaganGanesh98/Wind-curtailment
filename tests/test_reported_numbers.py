"""Every figure quoted in a results note, re-derived from the artifacts, under pytest.

    pytest tests/test_reported_numbers.py -q
    python tests/test_reported_numbers.py        # the same checks, as a CLI

Phase Q hard rule 7: *"The P3 script that re-derives quoted figures from artifacts
moves into `tests/` and runs under `pytest`, extended to cover Q notes. A wrong figure
in a results note must fail the suite. This is rule 7 because it has now caught ten
wrong figures across two phases; it stops being something to remember."*

It was `src/identification/check_p3_numbers.py` until 15 November 2026 and is moved
here unchanged in substance. The original run caught six wrong figures in
`docs/P3_results.md`'s first version, recorded in that note's correction section
rather than quietly fixed.

Each entry is (where in the document, computation, quoted value, tolerance). **The
tolerance is the rounding the document uses, never a band widened to make a check
pass.** Each becomes its own parametrised test, so a failure names the figure.

A note whose artifact is absent is SKIPPED rather than failed: the artifacts are
large CSVs produced by long runs, and a fresh clone has not got them. A note whose
artifact is present must match it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import polars as pl

import pytest

from src.identification.summarise_p3 import load

REPO_ROOT = Path(__file__).resolve().parents[1]
P3 = REPO_ROOT / "artifacts" / "P3"
Q0 = REPO_ROOT / "artifacts" / "Q0"
Q0B = REPO_ROOT / "artifacts" / "Q0b"
Q1D = REPO_ROOT / "artifacts" / "Q1"
Q0C = REPO_ROOT / "artifacts" / "Q0c"
Q5D = REPO_ROOT / "artifacts" / "Q5"
Q6D = REPO_ROOT / "artifacts" / "Q6"
TBL = REPO_ROOT / "artifacts" / "TB_lambda"
QS_FILE = (REPO_ROOT / "data" / "raw" / "netztransparenz"
           / "hochrechnung_wind_onshore_qualitaetsgesichert"
           / "online_hochrechnung_wind_onshore_qs_2025-10-01_2026-10-31_dl2026-11-15.csv")
QS_SHA256 = "c5a7f961034886b0ec9a88faaf7eaa40fa3aaf767516d15b68d9fb0f96fad5b4"


def _checks_arm_d(dd: pl.DataFrame, o: pl.DataFrame):
    """Section 2.4, including the Arm O comparison it is quoted against."""
    scored = dd.filter(pl.col("cov").is_not_null())
    o45 = o.filter(pl.col("seed") == 45)
    fs = dd.filter(pl.col("lam") == "L1").with_columns(
        (pl.col("rms_floor") / pl.col("rms_point")).alias("fs"))

    def med(df, lam, **eq):
        q = df.filter((pl.col("lam") == lam) & pl.col("feasible"))
        for k, v in eq.items():
            q = q.filter(pl.col(k) == v)
        return float(q["width"].median())

    out = [
        ("S2.4 cells", dd.select(["hetero", "rate", "gamma", "r_shape", "seed"]).unique().height, 54, 0),
        ("S2.4 solves all optimal", int((dd["status_lo"] == "optimal").sum()), 378, 0),
        ("S2.4 covered", int(scored["cov"].sum()), 378, 0),
        ("S2.4 scored", scored.height, 378, 0),
        ("S2.4 width L1", med(dd, "L1"), 0.096, 5e-4),
        ("S2.4 width L2", med(dd, "L2"), 0.178, 5e-4),
        ("S2.4 width L3", med(dd, "L3"), 0.541, 5e-4),
        ("S2.4 width L4", med(dd, "L4"), 0.712, 5e-4),
        ("S2.4 width L6", med(dd, "L6"), 1.206, 5e-4),
        ("S2.4 width L7", med(dd, "L7"), 1.000, 5e-4),
        ("S2.4 width L5 GWh", med(dd, "L5"), 12218.0, 1.0),
        ("S2.4 Arm O seed-45 width L1", med(o45, "L1"), 7.0e-7, 5e-8),
        ("S2.4 Arm O seed-45 width L7", med(o45, "L7"), 0.467, 5e-4),
        ("S2.4 eps step", float(dd.filter(pl.col("r_shape") == "step")["eps"].median()), 0.035, 5e-4),
        ("S2.4 eps half", float(dd.filter(pl.col("r_shape") == "half")["eps"].median()), 0.083, 5e-4),
        ("S2.4 eps logistic", float(dd.filter(pl.col("r_shape") == "logistic")["eps"].median()), 0.121, 5e-4),
        ("S2.4 floor share min", float(fs["fs"].min()), 0.982, 1e-3),
        ("S2.4 floor share max", float(fs["fs"].max()), 0.999, 1e-3),
        ("S2.4 floor share mean", float(fs["fs"].mean()), 0.995, 1e-3),
        ("S2.4 pooled exceeds width, any",
         int(dd["pooled_err_exceeds_width"].sum()), 0, 0),
    ]
    return out


def _checks(o: pl.DataFrame, r: pl.DataFrame):
    scored = o.filter(pl.col("cov").is_not_null())
    win = r.filter((pl.col("period") == "window")
                   & ~pl.col("c_hat").str.contains("recal"))
    main = win.filter(pl.col("setting") == "main")
    months = r.filter((pl.col("period") != "window") & (pl.col("lam") == "L1"))
    fs = r.filter(pl.col("lam") == "L1").with_columns(
        (pl.col("rms_floor") / pl.col("rms_point")).alias("fs"))
    wide = r.filter(pl.col("period") == "window").with_columns(
        pl.col("c_hat").str.contains("recal").alias("rc"))
    a = wide.filter(~pl.col("rc")).sort(["setting", "lam"])["width"].to_numpy()
    b = wide.filter(pl.col("rc")).sort(["setting", "lam"])["width"].to_numpy()

    def med(df, **eq):
        q = df
        for k, v in eq.items():
            q = q.filter(pl.col(k) == v)
        return float(q.filter(pl.col("feasible"))["width"].median())

    def cell(lam, col):
        return float(main.filter(pl.col("lam") == lam)[col][0])

    out = [
        ("S2.1 scored cell-functionals", scored.height, 1127, 0),
        ("S2.1 covered", int(scored["cov"].sum()), 1127, 0),
        ("S2.1 solver optimal", int((o["status_lo"] == "optimal").sum()), 1096, 0),
        ("S2.1 solver optimal_inaccurate",
         int((o["status_lo"] == "optimal_inaccurate").sum()), 31, 0),
        ("S2.1 median width L1", med(o, lam="L1"), 7.7e-7, 5e-9),
        ("S2.1 median width L2", med(o, lam="L2"), 1.5e-6, 5e-8),
        ("S2.1 median width L3", med(o, lam="L3"), 4.7e-6, 5e-8),
        ("S2.1 median width L4", med(o, lam="L4"), 1.3e-5, 5e-7),
        ("S2.1 median width L5", med(o, lam="L5"), 0.28, 5e-3),
        ("S2.1 median width L6", med(o, lam="L6"), 1.5e-5, 5e-7),
        ("S2.1 median width L7", med(o, lam="L7"), 0.47, 5e-3),
        ("S2.2 L1 logistic", med(o, lam="L1", r_shape="logistic"), 0.0048, 5e-5),
        ("S2.2 L2 logistic", med(o, lam="L2", r_shape="logistic"), 0.0083, 5e-5),
        ("S2.2 L3 logistic", med(o, lam="L3", r_shape="logistic"), 0.0278, 5e-5),
        ("S2.2 L4 logistic", med(o, lam="L4", r_shape="logistic"), 0.0632, 5e-5),
        ("S2.2 L6 logistic", med(o, lam="L6", r_shape="logistic"), 0.0715, 5e-5),
        ("S2.2 L7 logistic", med(o, lam="L7", r_shape="logistic"), 0.4681, 5e-5),
        ("S2.2 L7 half", med(o, lam="L7", r_shape="half"), 1.0, 1e-6),
        ("S2.2 L5 logistic GWh", med(o, lam="L5", r_shape="logistic"), 1541.0, 1.0),
        ("S2.2 L7 step split",
         med(o.filter(pl.col("hetero") == "split"), lam="L7", r_shape="step"),
         0.225, 5e-4),
        ("S2.2 eps logistic",
         float(o.filter(pl.col("r_shape") == "logistic")["eps"].median()), 0.0062, 5e-5),
        ("S2.3 L7 width at rate 0.10", med(o.filter(pl.col("rate") == 0.1), lam="L7"),
         0.489, 5e-4),
        ("S2.3 L7 width at rate 0.40", med(o.filter(pl.col("rate") == 0.4), lam="L7"),
         0.456, 5e-4),
        ("S2.3 exposure rank is constant", int(o["exposure_rank"].n_unique()), 1, 0),
        ("S2.3 exposure rank value", int(o["exposure_rank"][0]), 4, 0),
        ("S3.1 exposed quarter-hours", int(main["n_rows"][0]), 2052, 0),
        ("S3.1 L1 hi", cell("L1", "hi"), 0.310, 5e-4),
        ("S3.1 L2 lo", cell("L2", "lo"), 0.079, 5e-4),
        ("S3.1 L2 hi", cell("L2", "hi"), 0.857, 5e-4),
        ("S3.1 L3 hi", cell("L3", "hi"), 0.648, 5e-4),
        ("S3.1 L4 hi", cell("L4", "hi"), 0.566, 5e-4),
        ("S3.1 L6 lo", cell("L6", "lo"), -0.565, 5e-4),
        ("S3.1 L7 hi", cell("L7", "hi"), 0.906, 5e-4),
        ("S3.1 L5 hi GWh", cell("L5", "hi"), 839.3, 0.05),
        ("S3.1 L5 full-response GWh", cell("L5", "l5_energy_full_gwh"), 839.3, 0.05),
        ("S3.1 L3 width at low", med(win.filter(pl.col("setting") == "low"), lam="L3"),
         0.524, 5e-4),
        ("S3.1 L3 width at high", med(win.filter(pl.col("setting") == "high"), lam="L3"),
         0.938, 5e-4),
        ("S1 narrowest real width",
         float(r.filter(pl.col("feasible"))["width"].min()), 0.0815, 5e-5),
        ("S3.1 max recalibration delta", float(np.nanmax(np.abs(b - a))), 0.038, 5e-4),
        ("S3.2 floor share, window low",
         float(fs.filter((pl.col("period") == "window")
                         & (pl.col("setting") == "low"))["fs"].max()), 0.942, 1e-3),
        ("S3.2 floor share, window high",
         float(fs.filter((pl.col("period") == "window")
                         & (pl.col("setting") == "high"))["fs"].min()), 0.886, 1e-3),
        ("S3.2 floor share, min over all arms", float(fs["fs"].min()), 0.299, 1e-3),
        ("S3.2 floor share, max over all arms", float(fs["fs"].max()), 1.000, 1e-3),
        ("S3.2 floor share, median over all arms",
         float(fs["fs"].median()), 0.905, 1e-3),
        ("S3.2 2026-04 floor share, main",
         float(fs.filter((pl.col("period") == "2026-04")
                         & (pl.col("setting") == "main"))["fs"][0]), 0.715, 1e-3),
        ("S3.3 months with a negative quarter-hour",
         int(months.filter(pl.col("setting") == "main").height), 10, 0),
    ]
    for st, n in (("low", 2), ("main", 6), ("high", 7)):
        out.append((f"S3.3 months with exposure rank >= 2, {st}",
                    int((months.filter(pl.col("setting") == st)["exposure_rank"] >= 2).sum()),
                    n, 0))
    for lam in ("L1", "L3", "L4", "L5", "L6"):
        out.append((f"S2.3 pooled exceeds width, split, {lam}",
                    int(o.filter((pl.col("lam") == lam) & (pl.col("hetero") == "split"))
                        ["pooled_err_exceeds_width"].sum()), 53, 0))
        out.append((f"S2.3 pooled exceeds width, homogeneous, {lam}",
                    int(o.filter((pl.col("lam") == lam)
                                 & (pl.col("hetero") == "homogeneous"))
                        ["pooled_err_exceeds_width"].sum()), 0, 0))
    return out


def _q0_checks(a: pl.DataFrame):
    """`docs/Q0_preregistration.md` section 1 -- the measured anchors."""
    def one(anchor, area, series, sample, col):
        q = a.filter((pl.col("anchor") == anchor) & (pl.col("area") == area)
                     & (pl.col("series") == series) & (pl.col("sample") == sample))
        if q.height != 1:
            raise AssertionError(f"{anchor}/{area}/{series}/{sample}: {q.height} rows")
        return float(q[col][0])

    de = ("T", "DE", "onshore")
    agg = "DE excl. TenneT (50Hertz+Amprion+TransnetBW)"
    return [
        ("Q0 Anchor T, DE onshore, price>=0, sigma", one(*de, "price >= 0", "sigma"), 0.1806, 5e-5),
        ("Q0 Anchor T, DE onshore, price>=0, bias", one(*de, "price >= 0", "bias"), -0.0037, 5e-5),
        ("Q0 Anchor T, DE onshore, price>5, sigma", one(*de, "price > 5", "sigma"), 0.1787, 5e-5),
        ("Q0 Anchor T, DE onshore, in band, sigma",
         one(*de, "price >= 0, in the negative-QH forecast band", "sigma"), 0.1603, 5e-5),
        ("Q0 Anchor T, DE total, price>=0, sigma",
         one("T", "DE", "total", "price >= 0", "sigma"), 0.1608, 5e-5),
        ("Q0 Anchor H, aggregate, price>=0, sigma",
         one("H", agg, "onshore", "price >= 0", "sigma"), 0.0660, 5e-5),
        ("Q0 Anchor H, aggregate, price>=0, bias",
         one("H", agg, "onshore", "price >= 0", "bias"), -0.0472, 5e-5),
        ("Q0 Anchor T matched to H, price>=0, sigma",
         one("T|H-matched", agg, "onshore", "price >= 0", "sigma"), 0.2270, 5e-5),
        ("Q0 Anchor T matched to H, price>=0, bias",
         one("T|H-matched", agg, "onshore", "price >= 0", "bias"), 0.0325, 5e-5),
        ("Q0 Anchor Z sigma", float(a.filter(pl.col("anchor") == "Z")["sigma"][0]), 0.0, 0.0),
        ("Q0 Anchor H sample size, aggregate",
         one("H", agg, "onshore", "price >= 0", "n_qh"), 5131, 0),
        ("Q0 Anchor H event-days, aggregate",
         one("H", agg, "onshore", "price >= 0", "n_days"), 55, 0),
        # section 1.1 -- the forecast band and the remaining Anchor T rows
        ("Q0 negative-QH forecast band, low edge",
         one(*de, "price >= 0", "band_lo_mw"), 2129.0, 0.5),
        ("Q0 negative-QH forecast band, high edge",
         one(*de, "price >= 0", "band_hi_mw"), 36674.0, 0.5),
        ("Q0 Anchor T, DE onshore, price>5, bias", one(*de, "price > 5", "bias"), -0.0031, 5e-5),
        ("Q0 Anchor T, DE onshore, in band, bias",
         one(*de, "price >= 0, in the negative-QH forecast band", "bias"), -0.0051, 5e-5),
        ("Q0 Anchor T, DE total, price>=0, bias",
         one("T", "DE", "total", "price >= 0", "bias"), 0.0098, 5e-5),
        ("Q0 Anchor T, DE onshore, price>=0, n_qh", one(*de, "price >= 0", "n_qh"), 35577, 0),
        ("Q0 Anchor T, DE onshore, price>=0, n_days", one(*de, "price >= 0", "n_days"), 392, 0),
        # section 1.1 -- per control area
        ("Q0 Anchor T, 50Hertz, sigma", one("T", "50Hertz", "onshore", "price >= 0", "sigma"), 0.3165, 5e-5),
        ("Q0 Anchor T, 50Hertz, bias", one("T", "50Hertz", "onshore", "price >= 0", "bias"), -0.0730, 5e-5),
        ("Q0 Anchor T, Amprion, sigma", one("T", "Amprion", "onshore", "price >= 0", "sigma"), 0.3071, 5e-5),
        ("Q0 Anchor T, Amprion, bias", one("T", "Amprion", "onshore", "price >= 0", "bias"), 0.0216, 5e-5),
        ("Q0 Anchor T, TenneT, sigma", one("T", "TenneT", "onshore", "price >= 0", "sigma"), 0.2313, 5e-5),
        ("Q0 Anchor T, TenneT, bias", one("T", "TenneT", "onshore", "price >= 0", "bias"), -0.0036, 5e-5),
        ("Q0 Anchor T, TransnetBW, sigma", one("T", "TransnetBW", "onshore", "price >= 0", "sigma"), 0.5213, 5e-5),
        ("Q0 Anchor T, TransnetBW, bias", one("T", "TransnetBW", "onshore", "price >= 0", "bias"), 0.0034, 5e-5),
        # section 1.2 -- Anchor H per area
        ("Q0 Anchor H, 50Hertz, sigma", one("H", "50Hertz", "onshore", "price >= 0", "sigma"), 0.0865, 5e-5),
        ("Q0 Anchor H, 50Hertz, bias", one("H", "50Hertz", "onshore", "price >= 0", "bias"), -0.0727, 5e-5),
        ("Q0 Anchor H, Amprion, sigma", one("H", "Amprion", "onshore", "price >= 0", "sigma"), 0.0884, 5e-5),
        ("Q0 Anchor H, Amprion, bias", one("H", "Amprion", "onshore", "price >= 0", "bias"), -0.0027, 5e-5),
        ("Q0 Anchor H, TransnetBW, sigma", one("H", "TransnetBW", "onshore", "price >= 0", "sigma"), 0.0885, 5e-5),
        ("Q0 Anchor H, TransnetBW, bias", one("H", "TransnetBW", "onshore", "price >= 0", "bias"), -0.0841, 5e-5),
        ("Q0 Anchor H, TenneT (excluded), sigma", one("H", "TenneT", "onshore", "price >= 0", "sigma"), 0.0709, 5e-5),
        ("Q0 Anchor H, TenneT (excluded), bias", one("H", "TenneT", "onshore", "price >= 0", "bias"), -0.0532, 5e-5),
        ("Q0 Anchor H, aggregate, price>5, sigma", one("H", agg, "onshore", "price > 5", "sigma"), 0.0541, 5e-5),
        ("Q0 Anchor H, aggregate, price>5, bias", one("H", agg, "onshore", "price > 5", "bias"), -0.0424, 5e-5),
        # section 1.3 -- the like-for-like comparison and the ratio it rests on
        ("Q0 matched T sigma CI low",
         one("T|H-matched", agg, "onshore", "price >= 0", "sigma_lo"), 0.1678, 5e-5),
        ("Q0 matched T sigma CI high",
         one("T|H-matched", agg, "onshore", "price >= 0", "sigma_hi"), 0.2874, 5e-5),
        ("Q0 the projection is 3.4x tighter than the forecast",
         one("T|H-matched", agg, "onshore", "price >= 0", "sigma")
         / one("H", agg, "onshore", "price >= 0", "sigma"), 3.44, 0.005),
    ]


def _q0_from_arm_d(d: pl.DataFrame):
    """`docs/Q0_preregistration.md` section 5 -- which band is the most populated."""
    med = {r["lam"]: r["n"] for r in
           d.group_by("lam").agg(pl.col("n_qh_lam").median().alias("n")).iter_rows(named=True)}
    return [
        ("Q0 lambda-1 median exposed quarter-hours", med["L1"], 3347, 0),
        ("Q0 lambda-2 median exposed quarter-hours", med["L2"], 1132, 0),
        ("Q0 Arm D cell count",
         d.select(["hetero", "rate", "gamma", "r_shape", "seed"]).unique().height, 54, 0),
    ]


def _q0b_checks(sh: pl.DataFrame, v: pl.DataFrame, ag: pl.DataFrame):
    """`docs/Q0b_results.md` and `docs/Q0_preregistration.md` Amendment 1."""
    agg = "50Hertz+Amprion+TransnetBW"
    QA, OP = "quality-assured", "operational"

    def share(area, est, set_, col="gap_share", series=QA):
        q = sh.filter((pl.col("series") == series) & (pl.col("area") == area)
                      & (pl.col("estimator") == est) & (pl.col("set") == set_))
        if q.height != 1:
            raise AssertionError(f"{series}/{area}/{est}/{set_}: {q.height} rows")
        return float(q[col][0])

    def verdict(area, col, series=QA):
        q = v.filter((pl.col("series") == series) & (pl.col("area") == area))
        return q[col][0]

    def agree(area, col, series=QA):
        q = ag.filter((pl.col("series") == series) & (pl.col("area") == area))
        return float(q[col][0])

    out = [
        ("Q0b decides: aggregate verdict is ADDS BACK",
         float(verdict(agg, "verdict") == "ADDS BACK"), 1.0, 0),
        ("Q0b aggregate D", float(verdict(agg, "D")), 0.2893, 5e-5),
        ("Q0b aggregate D CI low", float(verdict(agg, "D_lo")), 0.2484, 5e-5),
        ("Q0b aggregate D CI high", float(verdict(agg, "D_hi")), 0.3344, 5e-5),
        ("Q0b aggregate bands with data", float(verdict(agg, "bands_with_data")), 4, 0),
        ("Q0b operational aggregate is INDETERMINATE",
         float(verdict(agg, "verdict", OP) == "INDETERMINATE"), 1.0, 0),
        ("Q0b operational aggregate bands", float(verdict(agg, "bands_with_data", OP)), 2, 0),
        ("Q0b operational aggregate D", float(verdict(agg, "D", OP)), 0.3616, 5e-5),
        ("Q0b operational aggregate D low", float(verdict(agg, "D_lo", OP)), 0.2889, 5e-5),
        ("Q0b operational aggregate D high", float(verdict(agg, "D_hi", OP)), 0.4375, 5e-5),
        ("Q0b forecast aggregate D", float(verdict(agg, "F_D")), 0.1033, 5e-5),
        ("Q0b forecast aggregate D low", float(verdict(agg, "F_D_lo")), 0.0567, 5e-5),
        ("Q0b forecast aggregate D high", float(verdict(agg, "F_D_hi")), 0.1444, 5e-5),
        ("Q0b forecast 50Hertz D low", float(verdict("50Hertz", "F_D_lo")), -0.0028, 5e-5),
        ("Q0b forecast 50Hertz D high", float(verdict("50Hertz", "F_D_hi")), 0.1117, 5e-5),
        ("Q0b forecast TenneT D", float(verdict("TenneT", "F_D")), -0.0018, 5e-5),
        ("Q0b forecast TenneT D low", float(verdict("TenneT", "F_D_lo")), -0.0889, 5e-5),
        ("Q0b forecast TenneT D high", float(verdict("TenneT", "F_D_hi")), 0.0730, 5e-5),
        ("Q0b H negative-price share", share(agg, "H", "price < 0"), 0.3107, 5e-5),
        ("Q0b H negative share CI low", share(agg, "H", "price < 0", "ci_lo"), 0.2693, 5e-5),
        ("Q0b H negative share CI high", share(agg, "H", "price < 0", "ci_hi"), 0.3542, 5e-5),
        ("Q0b H price>=0 share", share(agg, "H", "price >= 0"), 0.0214, 5e-5),
        ("Q0b H price>=0 CI low", share(agg, "H", "price >= 0", "ci_lo"), 0.0174, 5e-5),
        ("Q0b H price>=0 CI high", share(agg, "H", "price >= 0", "ci_hi"), 0.0259, 5e-5),
        ("Q0b H price>5 share", share(agg, "H", "price > 5"), 0.0157, 5e-5),
        ("Q0b F negative-price share", share(agg, "F", "price < 0"), 0.0933, 5e-5),
        ("Q0b F price>=0 share", share(agg, "F", "price >= 0"), -0.0101, 5e-5),
        ("Q0b F price>5 share", share(agg, "F", "price > 5"), -0.0106, 5e-5),
        ("Q0b H is 3.3x F at negative prices",
         share(agg, "H", "price < 0") / share(agg, "F", "price < 0"), 3.33, 0.005),
        ("Q0b price>=0 days", share(agg, "H", "price >= 0", "n_days"), 391, 0),
        ("Q0b price>5 days", share(agg, "H", "price > 5", "n_days"), 390, 0),
        ("Q0b negative-price days", share(agg, "H", "price < 0", "n_days"), 99, 0),
        # redispatch's own size (section 3)
        ("Q0b R share, aggregate, negative", share(agg, "H", "price < 0", "r_share"), 0.0338, 5e-5),
        ("Q0b R share, aggregate, price>=0", share(agg, "H", "price >= 0", "r_share"), 0.0165, 5e-5),
        ("Q0b R share, TenneT, negative", share("TenneT", "H", "price < 0", "r_share"), 0.1355, 5e-5),
        ("Q0b R share, TenneT, price>=0", share("TenneT", "H", "price >= 0", "r_share"), 0.1279, 5e-5),
        ("Q0b TenneT positive-price gap share", share("TenneT", "H", "price >= 0"), -0.0691, 5e-5),
        ("Q0b every other area sits above at positive prices",
         float(all(share(a, "H", "price >= 0") > 0 for a in ("50Hertz", "Amprion", "TransnetBW", agg))),
         1.0, 0),
        # Amendment 1 A1.1 and Q0b section 5 -- the agreement evidence
        ("Q0b QS sigma, aggregate", agree(agg, "sigma_log_G_over_H"), 0.0607, 5e-5),
        ("Q0b QS sigma CI low", agree(agg, "sigma_lo"), 0.0544, 5e-5),
        ("Q0b QS sigma CI high", agree(agg, "sigma_hi"), 0.0667, 5e-5),
        ("Q0b operational sigma, aggregate", agree(agg, "sigma_log_G_over_H", OP), 0.0660, 5e-5),
        ("Q0b operational sigma CI low", agree(agg, "sigma_lo", OP), 0.0511, 5e-5),
        ("Q0b operational sigma CI high", agree(agg, "sigma_hi", OP), 0.0800, 5e-5),
        ("Q0b QS corr(H,G), aggregate", agree(agg, "corr_H_G"), 0.9954, 5e-5),
        ("Q0b operational corr(H,G), aggregate", agree(agg, "corr_H_G", OP), 0.9959, 5e-5),
        ("Q0b QS corr of changes, aggregate", agree(agg, "corr_dH_dG_lag1"), 0.899, 5e-4),
        ("Q0b QS corr(H,G), 50Hertz", agree("50Hertz", "corr_H_G"), 0.9944, 5e-5),
        ("Q0b QS corr(H,G), Amprion", agree("Amprion", "corr_H_G"), 0.9968, 5e-5),
        ("Q0b QS corr(H,G), TransnetBW", agree("TransnetBW", "corr_H_G"), 0.9972, 5e-5),
        ("Q0b QS corr(H,G), TenneT", agree("TenneT", "corr_H_G"), 0.9914, 5e-5),
        ("Q0b QS corr of changes, 50Hertz", agree("50Hertz", "corr_dH_dG_lag1"), 0.873, 5e-4),
        ("Q0b QS corr of changes, Amprion", agree("Amprion", "corr_dH_dG_lag1"), 0.927, 5e-4),
        ("Q0b QS corr of changes, TransnetBW", agree("TransnetBW", "corr_dH_dG_lag1"), 0.955, 5e-4),
        ("Q0b QS corr of changes, TenneT", agree("TenneT", "corr_dH_dG_lag1"), 0.877, 5e-4),
    ]
    for area, d, lo, hi in (("50Hertz", 0.2866, 0.2406, 0.3355),
                            ("Amprion", 0.2944, 0.2563, 0.3365),
                            ("TransnetBW", 0.2861, 0.2312, 0.3421),
                            ("TenneT", 0.3106, 0.2656, 0.3560)):
        out += [(f"Q0b {area} verdict ADDS BACK",
                 float(verdict(area, "verdict") == "ADDS BACK"), 1.0, 0),
                (f"Q0b {area} D", float(verdict(area, "D")), d, 5e-5),
                (f"Q0b {area} D low", float(verdict(area, "D_lo")), lo, 5e-5),
                (f"Q0b {area} D high", float(verdict(area, "D_hi")), hi, 5e-5)]
    for b, h, hlo, hhi, f, nd in (("(-5,0)", 0.2469, 0.2201, 0.2786, 0.0493, 99),
                                  ("[-20,-5]", 0.4025, 0.3362, 0.4560, 0.1125, 38),
                                  ("[-50,-20]", 0.5453, 0.4757, 0.5808, 0.2681, 20),
                                  ("<=-50", 0.6799, 0.5810, 0.7326, 0.5296, 12)):
        out += [(f"Q0b H band {b}", share(agg, "H", f"band {b}"), h, 5e-5),
                (f"Q0b H band {b} CI low", share(agg, "H", f"band {b}", "ci_lo"), hlo, 5e-5),
                (f"Q0b H band {b} CI high", share(agg, "H", f"band {b}", "ci_hi"), hhi, 5e-5),
                (f"Q0b F band {b}", share(agg, "F", f"band {b}"), f, 5e-5),
                (f"Q0b band {b} event-days", share(agg, "H", f"band {b}", "n_days"), nd, 0)]
    return out


def _amendment1_checks():
    """`docs/Q0_preregistration.md` A1.4 -- the values traced to results/36 and /34."""
    import csv as _csv
    r36 = {r["area"]: r for r in _csv.DictReader(open(REPO_ROOT / "results" / "36_hochrechnung_onshore_check.csv"))}
    r34 = {r["area"]: r for r in _csv.DictReader(open(REPO_ROOT / "results" / "34_hochrechnung_check.csv"))}
    hr = sum(float(r36[a]["hr_mean_mw"]) for a in r36)
    sm = sum(float(r36[a]["smard_mean_mw"]) for a in r36)
    ex = {a: float(r36[a]["hr_mean_mw"]) - float(r36[a]["smard_mean_mw"]) for a in r36}
    return [
        ("A1.4 three-area pooled ratio is the 1.035", hr / sm, 1.0347, 5e-5),
        ("A1.4 50Hertz excess MW", ex["50Hertz"], 46.8, 0.05),
        ("A1.4 Amprion excess MW", ex["Amprion"], 59.9, 0.05),
        ("A1.4 TransnetBW excess MW", ex["TransnetBW"], 11.8, 0.05),
        ("A1.4 results/36 has no TenneT row", float("TenneT" in r36 or "TenneT DE" in r36), 0.0, 0),
        ("A1.4 results/36 Amprion corr", float(r36["Amprion"]["corr"]), 0.9992, 5e-5),
        ("A1.4 results/34 TenneT corr (the wrong series)",
         float(r34["TenneT"]["corr_with_smard_actual"]), 0.9923, 5e-5),
        ("A1.4 results/34 Amprion corr", float(r34["Amprion"]["corr_with_smard_actual"]), 0.9695, 5e-5),
    ]


def _qs_file_checks():
    """Q0b section 4: the fetched raw file is the one the results were computed on."""
    import hashlib
    if not QS_FILE.exists():
        return []
    raw = QS_FILE.read_bytes()
    n_rows = raw.decode("utf-8-sig").strip().count("\n")      # header excluded by count
    return [
        ("Q0b raw file sha256 matches", float(hashlib.sha256(raw).hexdigest() == QS_SHA256), 1.0, 0),
        ("Q0b raw file quarter-hours", n_rows, 38020, 0),
    ]


def _q1_checks():
    """`docs/Q1_results.md`."""
    lv = pl.read_csv(Q1D / "q1_summary_by_level.csv")
    hd = pl.read_csv(Q1D / "q1_headline.csv")
    raw = load(Q1D / "q1_variance_dial.csv").with_columns(
        pl.col("sigma").cast(pl.Float64, strict=False))

    def L(sig, lam, col, noise="iid"):
        q = lv.filter((pl.col("noise") == noise) & ((pl.col("sigma") - sig).abs() < 1e-9)
                      & (pl.col("lam") == lam))
        if q.height != 1:
            raise AssertionError(f"{noise}/{sig}/{lam}: {q.height} rows")
        return float(q[col][0])

    def H(stat, lam):
        q = hd.filter((pl.col("statistic") == stat) & (pl.col("lam") == lam))
        return float(q["value"][0])

    out = [("Q1 rows", raw.height, 3024, 0),
           ("Q1 sigma* (censored at the grid top)", H("sigma_star", "L1"), 0.35, 1e-9)]
    grid = (0.0, 0.033, 0.066, 0.12, 0.18, 0.25, 0.35)
    table = {  # section 3, n_informative
        "L1": (54, 54, 54, 54, 54, 54, 50), "L2": (54, 54, 54, 54, 54, 54, 41),
        "L3": (54, 54, 54, 34, 18, 18, 18), "L4": (54, 54, 24, 18, 18, 18, 14),
        "L5": (54, 52, 24, 18, 18, 18, 17), "L6": (54, 54, 54, 24, 18, 18, 18),
        "L7": (18, 14, 9, 9, 9, 6, 0)}
    for lam, ns in table.items():
        for sig, n in zip(grid, ns):
            out.append((f"Q1 {lam} informative cells at {sig}", L(sig, lam, "n_informative"), n, 0))
    for sig in grid:
        out.append((f"Q1 coverage at {sig}", L(sig, "L1", "level_coverage"), 1.0, 0))
    out.append(("Q1 AR(1) coverage", L(0.18, "L1", "level_coverage", "ar1"), 1.0, 0))
    iqr = {  # section 3, median [q25, q75]
        (0.033, "L1"): (0.008, 0.006, 0.014), (0.033, "L3"): (0.056, 0.022, 0.077),
        (0.033, "L4"): (0.142, 0.066, 0.184), (0.033, "L6"): (0.158, 0.074, 0.204),
        (0.066, "L1"): (0.017, 0.013, 0.029), (0.066, "L3"): (0.114, 0.045, 0.145),
        (0.066, "L4"): (0.280, 0.110, 0.343), (0.066, "L6"): (0.311, 0.134, 0.396),
        (0.18, "L1"): (0.048, 0.038, 0.083), (0.18, "L3"): (0.335, 0.102, 0.387),
        (0.18, "L4"): (0.503, 0.153, 0.674), (0.18, "L6"): (0.738, 0.248, 0.896),
        (0.35, "L1"): (0.110, 0.066, 0.189), (0.35, "L3"): (0.607, 0.163, 0.672),
        (0.35, "L4"): (0.548, 0.249, 0.987), (0.35, "L6"): (1.040, 0.405, 1.402)}
    for (sig, lam), (m, a, b) in iqr.items():
        out += [(f"Q1 {lam} median width at {sig}", L(sig, lam, "median_width"), m, 5e-4),
                (f"Q1 {lam} q25 width at {sig}", L(sig, lam, "q25_width"), a, 5e-4),
                (f"Q1 {lam} q75 width at {sig}", L(sig, lam, "q75_width"), b, 5e-4)]
    at_033 = {"L1": 0.0, "L3": 0.222, "L4": 0.185, "L5": 0.0, "L6": 0.296}
    for lam in ("L1", "L3", "L4", "L5", "L6"):
        out.append((f"Q1 {lam} pooled rejection at 0", L(0.0, lam, "pooled_rejection_split"), 0.667, 5e-4))
        out.append((f"Q1 {lam} pooled rejection at 0.033",
                    L(0.033, lam, "pooled_rejection_split"), at_033[lam], 5e-4))
        for sig in grid[2:]:
            out.append((f"Q1 {lam} pooled rejection at {sig}",
                        L(sig, lam, "pooled_rejection_split"), 0.0, 0))
        out.append((f"Q1 {lam} secondary statistic", H("pooled_rejection_above_half_max_sigma", lam), 0.0, 0))
    out.append(("Q1 split cells scored per functional", L(0.0, "L1", "n_split_scored"), 27, 0))
    for sig, f in zip(grid, (0.372, 0.996, 0.996, 0.996, 0.997, 0.995, 0.994)):
        out.append((f"Q1 floor ratio at {sig}", L(sig, "L1", "median_floor_ratio"), f, 5e-4))
    for sig, e in ((0.033, 0.019), (0.18, 0.108), (0.35, 0.226)):
        out.append((f"Q1 median eps at {sig}", L(sig, "L1", "median_eps"), e, 5e-4))
    out.append(("Q1 AR(1) median eps", L(0.18, "L1", "median_eps", "ar1"), 0.114, 5e-4))
    out.append(("Q1 AR(1) L1 informative cells", L(0.18, "L1", "n_informative", "ar1"), 52, 0))
    for lam, dv, tol in (("L1", 0.048, 5e-4), ("L2", 0.090, 5e-4), ("L3", 0.247, 5e-4),
                         ("L4", 0.160, 5e-4), ("L6", 0.433, 5e-4), ("L7", 0.021, 5e-4),
                         ("L5", 3118.0, 0.5)):
        out.append((f"Q1 AR(1) minus iid width {lam}",
                    H("ar1_minus_iid_median_width_at_0.18", lam), dv, tol))
    # section 2 -- the solver statuses and the port check's scale
    st = pl.concat([raw.select(["noise", "sigma", pl.col("status_lo").alias("s")]),
                    raw.select(["noise", "sigma", pl.col("status_hi").alias("s")])])
    inacc = st.filter(pl.col("s") == "optimal_inaccurate")
    out += [("Q1 inaccurate solves at 0", inacc.filter(pl.col("sigma") == 0.0).height, 20, 0),
            ("Q1 inaccurate solves at 0.25", inacc.filter(pl.col("sigma") == 0.25).height, 1, 0),
            ("Q1 inaccurate solves elsewhere",
             inacc.filter(~pl.col("sigma").is_in([0.0, 0.25])).height, 0, 0),
            ("Q1 infeasible solves", st.filter(pl.col("s").str.contains("infeasible")).height, 0, 0)]
    return out


def _open_list_checks():
    """`docs/R1_reconciliation.md` section 6 item 6: TenneT correlation, re-measured."""
    ag = pl.read_csv(Q0B / "q0b_h_agreement.csv")
    out = []
    for series, n, c in (("operational", 5422, 0.9913), ("quality-assured", 35673, 0.9914)):
        q = ag.filter((pl.col("series") == series) & (pl.col("area") == "TenneT")
                      & (pl.col("sample") == "price >= 0"))
        out += [(f"R1 open-6 TenneT {series} QHs", q["n_qh"][0], n, 0),
                (f"R1 open-6 TenneT {series} corr", q["corr_H_G"][0], c, 5e-5)]
    return out


def _q0c_checks():
    """`docs/Q0c_results.md`."""
    v = pl.read_csv(Q0C / "q0c_volume.csv")

    def V(stat, col):
        q = v.filter(pl.col("statistic") == stat)
        if q.height != 1:
            raise AssertionError(f"Q0c {stat}: {q.height} rows")
        return q[col][0]

    out = []
    for stat, (p, lo, hi) in (("signed", (1.644, 1.162, 2.200)),
                              ("clipped_at_zero", (1.664, 1.187, 2.216))):
        out += [(f"Q0c {stat} volume TWh", V(stat, "volume_twh"), p, 5e-4),
                (f"Q0c {stat} CI lo", V(stat, "ci_lo_twh"), lo, 5e-4),
                (f"Q0c {stat} CI hi", V(stat, "ci_hi_twh"), hi, 5e-4),
                (f"Q0c {stat} verdict is NOT TESTABLE",
                 float(V(stat, "verdict") == "NOT TESTABLE at national scale"), 1.0, 0)]
    out += [("Q0c negative-price QHs", V("signed", "n_neg_qh"), 1860, 0),
            ("Q0c event-days", V("signed", "n_event_days"), 92, 0),
            ("Q0c QHs with negative residual", V("signed", "share_qh_resid_negative"), 0.055, 5e-4)]
    for a in ("50Hertz", "Amprion", "TransnetBW"):
        out.append((f"Q0c {a} negative-price QHs", V("signed", f"n_neg_qh_{a}"), 1860, 0))
    return out


def _q5_checks():
    """`docs/Q5_results.md`."""
    sm = pl.read_csv(Q5D / "q5_summary.csv")
    raw = load(Q5D / "q5_real.csv")

    def T(setting, scope, col):
        q = sm.filter((pl.col("table") == "transitions") & (pl.col("setting") == setting)
                      & (pl.col("scope") == scope))
        return float(q[col][0])

    def A(pot, setting, col):
        q = sm.filter((pl.col("table") == "per_arm") & (pl.col("potential") == pot)
                      & (pl.col("setting") == setting))
        return float(q[col][0])

    out = [("Q5 rows", raw.height, 504, 0)]
    for st, n, up, dn, f, h in (("main", 59, 2, 5, 0.102, 0.051),
                                ("low", 59, 3, 4, 0.085, 0.068),
                                ("high", 53, 3, 2, 0.057, 0.075)):
        out += [(f"Q5 {st} pairs in both", T(st, "months", "n_pairs_both"), n, 0),
                (f"Q5 {st} become informative", T(st, "months", "n_become_informative"), up, 0),
                (f"Q5 {st} reverse", T(st, "months", "n_reverse"), dn, 0),
                (f"Q5 {st} share informative F", T(st, "months", "share_informative_F"), f, 5e-4),
                (f"Q5 {st} share informative H", T(st, "months", "share_informative_H"), h, 5e-4),
                (f"Q5 {st} one-arm-only pairs", T(st, "months", "n_pairs_one_arm_only"), 0, 0),
                (f"Q5 {st} window become informative", T(st, "window", "n_become_informative"), 1, 0),
                (f"Q5 {st} window reverse", T(st, "window", "n_reverse"), 0, 0),
                (f"Q5 {st} window pairs", T(st, "window", "n_pairs_both"), 7, 0)]
    out += [("Q5 headline share", T("main", "months", "share_become_informative"), 0.034, 5e-4),
            ("Q5 main reverse share", T("main", "months", "share_reverse"), 0.085, 5e-4),
            ("Q5 low share", T("low", "months", "share_become_informative"), 0.051, 5e-4),
            ("Q5 low reverse share", T("low", "months", "share_reverse"), 0.068, 5e-4),
            ("Q5 high share", T("high", "months", "share_become_informative"), 0.057, 5e-4),
            ("Q5 high reverse share", T("high", "months", "share_reverse"), 0.038, 5e-4),
            ("Q5 main informative both", T("main", "months", "n_informative_both"), 1, 0),
            ("Q5 main neither arm", T("main", "months", "n_pairs_neither_arm"), 11, 0)]
    for pot, st, e, fl, w in (("F", "main", 0.267, 0.924, 0.943), ("H", "main", 0.107, 0.963, 1.000),
                              ("F", "low", 0.267, 0.936, 0.942), ("H", "low", 0.107, 0.963, 1.000),
                              ("F", "high", 0.267, 0.918, 0.977), ("H", "high", 0.107, 0.930, 0.908)):
        out += [(f"Q5 {pot} {st} median eps", A(pot, st, "median_eps"), e, 5e-4),
                (f"Q5 {pot} {st} floor ratio", A(pot, st, "median_floor_ratio"), fl, 5e-4),
                (f"Q5 {pot} {st} median width", A(pot, st, "median_width_excl_L5"), w, 5e-4)]
    plain = raw.filter((pl.col("setting") == "main")
                       & ~pl.col("c_hat").str.contains("recalibrated"))

    def W(pot, period, lam):
        q = plain.filter((pl.col("potential") == pot) & (pl.col("period") == period)
                         & (pl.col("lam") == lam))
        return float(q["width"][0])
    for period, lam, wf, wh in (("window", "L1", 0.474, 0.208), ("2025-10", "L1", 0.156, 0.148),
                                ("2026-01", "L3", 0.070, 0.532), ("2026-01", "L4", 0.075, 0.569),
                                ("2026-01", "L6", 0.144, 1.101), ("2026-01", "L7", 0.124, 0.945),
                                ("2026-02", "L3", 0.148, 0.269), ("2026-04", "L1", 0.571, 0.175),
                                ("2026-04", "L2", 0.983, 0.196)):
        out += [(f"Q5 width F {period} {lam}", W("F", period, lam), wf, 5e-4),
                (f"Q5 width H {period} {lam}", W("H", period, lam), wh, 5e-4)]
    months = plain.filter((pl.col("period") != "window") & (pl.col("lam") == "L1")
                          & (pl.col("potential") == "H") & pl.col("defined"))
    out += [("Q5 H L1 defined months", months.height, 8, 0),
            ("Q5 H L1 informative months",
             months.filter(pl.col("informative").cast(pl.String) == "true").height
             + months.filter(pl.col("informative").cast(pl.String) == "True").height, 2, 0)]
    return out


def _q6a_checks():
    """`docs/Q6_results.md`, Q6a."""
    d = pl.read_csv(Q6D / "q6a_cells.csv", infer_schema_length=0)

    def C(pb, rb, col, variant="G/H"):
        q = d.filter((pl.col("price_band") == pb) & (pl.col("run_band") == rb)
                     & (pl.col("variant") == variant))
        if q.height != 1:
            raise AssertionError(f"Q6a {pb}/{rb}/{variant}: {q.height} rows")
        return float(q[col][0])

    def V(variant, col):
        q = d.filter((pl.col("price_band") == "ALL") & (pl.col("variant") == variant))
        return q[col][0]

    out = []
    for variant in ("G/H", "(G+R)/H"):
        out += [(f"Q6a {variant} verdict PRESENT", float(V(variant, "verdict") == "PRESENT"), 1.0, 0),
                (f"Q6a {variant} testable cells", float(V(variant, "n_testable_cells")), 8, 0),
                (f"Q6a {variant} heterogeneous cells", float(V(variant, "n_heterogeneous_cells")), 8, 0)]
    gh = d.filter((pl.col("variant") == "G/H") & (pl.col("price_band") != "ALL"))
    out += [("Q6a quarter-hours in cells", gh["n_qh"].cast(pl.Float64).sum(), 2059, 0),
            ("Q6a occupied cells", gh.height, 10, 0)]
    table = (("(-5,0)", "0.25-1h", 33, 0.167, 0.0100, 0.0030, 3.3, 0.0019, 0.0120, 0.119),
             ("(-5,0)", "1-3h", 18, 0.275, 0.0253, 0.0023, 11.0, 0.0100, 0.0345, 0.212),
             ("(-5,0)", "3-6h", 42, 0.298, 0.0112, 0.0022, 5.2, 0.0039, 0.0143, 0.149),
             ("(-5,0)", ">6h", 30, 0.282, 0.0090, 0.0023, 4.0, 0.0033, 0.0100, 0.131),
             ("[-20,-5]", "3-6h", 12, 0.386, 0.0175, 0.0017, 10.6, 0.0029, 0.0272, 0.209),
             ("[-20,-5]", ">6h", 25, 0.458, 0.0132, 0.0013, 10.3, 0.0061, 0.0170, 0.205),
             ("[-50,-20]", ">6h", 16, 0.578, 0.0101, 0.0008, 13.0, 0.0034, 0.0147, 0.229),
             ("<=-50", ">6h", 12, 0.712, 0.0060, 0.0004, 16.6, 0.0019, 0.0089, 0.257),
             ("[-50,-20]", "3-6h", 4, 0.426, 0.0134, 0.0014, 9.3, -0.0010, 0.0186, 0.196))
    for pb, rb, nd, cb, vb, vm, ratio, lo, hi, be in table:
        k = f"Q6a {pb} {rb}"
        out += [(f"{k} days", C(pb, rb, "n_event_days"), nd, 0),
                (f"{k} c_bar", C(pb, rb, "c_bar"), cb, 5e-4),
                (f"{k} V_between", C(pb, rb, "v_between"), vb, 5e-5),
                (f"{k} V_meas", C(pb, rb, "v_meas"), vm, 5e-5),
                (f"{k} ratio", C(pb, rb, "ratio_between_over_meas"), ratio, 0.05),
                (f"{k} CI lo", C(pb, rb, "excess_ci_lo"), lo, 5e-5),
                (f"{k} CI hi", C(pb, rb, "excess_ci_hi"), hi, 5e-5),
                (f"{k} break-even sigma", C(pb, rb, "break_even_sigma"), be, 5e-4)]
        if nd >= 5:
            out += [(f"{k} iid V_meas smaller", float(C(pb, rb, "v_meas_iid") < C(pb, rb, "v_meas")), 1.0, 0),
                    (f"{k} (G+R) V_between larger",
                     float(C(pb, rb, "v_between", "(G+R)/H") > C(pb, rb, "v_between")), 1.0, 0)]
    out.append(("Q6a C(-20,-5] 1-3h single day", C("[-20,-5]", "1-3h", "n_event_days"), 1, 0))
    testable = [r for r in table if r[2] >= 5]
    out += [("Q6a break-even below 0.18", float(sum(r[9] < 0.18 for r in testable)), 3, 0)]
    ratios = [C(pb, rb, "v_between", "(G+R)/H") / C(pb, rb, "v_between") for pb, rb, nd, *_ in testable]
    out.append(("Q6a max (G+R) variance factor (up to 25)", float(max(ratios) <= 25.0 and max(ratios) > 24.0), 1.0, 0))
    return out


def _q6b_checks():
    """`docs/Q6_results.md`, Q6b."""
    sm = pl.read_csv(Q6D / "q6b_summary.csv")
    raw = load(Q6D / "q6b_day_effect.csv")
    lv = sm.filter(pl.col("table") == "levels")
    sg = sm.filter(pl.col("table") == "signatures")
    vd = sm.filter(pl.col("table") == "verdict")

    def Lv(sr, sig, col):
        q = lv.filter(((pl.col("sigma_r") - sr).abs() < 1e-9) & ((pl.col("sigma") - sig).abs() < 1e-9))
        return float(q[col][0])

    out = [("Q6b rows", raw.height, 3780, 0),
           ("Q6b verdict NOT SUPPORTED", float(vd["verdict"][0] == "NOT SUPPORTED"), 1.0, 0),
           ("Q6b no sigma_r meets S1", float(sg["s1"].cast(pl.String).str.to_lowercase().eq("true").sum()), 0, 0),
           ("Q6b no sigma_r meets S2", float(sg["s2"].cast(pl.String).str.to_lowercase().eq("true").sum()), 0, 0),
           ("Q6b Q5 fleet CP lo", vd["q5_fleet_cp_lo"][0], 0.060, 5e-4),
           ("Q6b Q5 fleet CP hi", vd["q5_fleet_cp_hi"][0], 0.610, 5e-4)]
    table = ((0.0, 1.000, 0.108, 0.039, 0.9966, 0.9964), (0.05, 1.000, 0.117, 0.060, 0.9966, 0.9950),
             (0.10, 1.000, 0.143, 0.097, 0.9953, 0.9937), (0.20, 0.667, 0.210, 0.155, 0.9935, 0.9931),
             (0.30, 0.593, 0.250, 0.208, 0.9930, 0.9926))
    for sr, share, et, eh, ft, fh in table:
        out += [(f"Q6b {sr} fleet share H", Lv(sr, 0.066, "fleet_share"), share, 5e-4),
                (f"Q6b {sr} eps T", Lv(sr, 0.18, "median_eps"), et, 5e-4),
                (f"Q6b {sr} eps H", Lv(sr, 0.066, "median_eps"), eh, 5e-4),
                (f"Q6b {sr} floor T", Lv(sr, 0.18, "median_floor_ratio"), ft, 5e-5),
                (f"Q6b {sr} floor H", Lv(sr, 0.066, "median_floor_ratio"), fh, 5e-5),
                (f"Q6b {sr} coverage H", Lv(sr, 0.066, "coverage"), 1.0, 0),
                (f"Q6b {sr} coverage T", Lv(sr, 0.18, "coverage"), 1.0, 0),
                (f"Q6b {sr} fleet defined", Lv(sr, 0.066, "fleet_defined"), 108, 0)]
    out += [("Q6b L2 at 0.20", Lv(0.20, 0.066, "L2_informative"), 18, 0),
            ("Q6b L2 at 0.30", Lv(0.30, 0.066, "L2_informative"), 18, 0),
            ("Q6b L1 at 0.20", Lv(0.20, 0.066, "L1_informative"), 54, 0),
            ("Q6b L1 at 0.30", Lv(0.30, 0.066, "L1_informative"), 46, 0),
            ("Q6b 0.30 inside Q5 fleet CP", float(0.060 <= Lv(0.30, 0.066, "fleet_share") <= 0.610), 1.0, 0),
            ("Q6b 0.20 outside Q5 fleet CP", float(Lv(0.20, 0.066, "fleet_share") > 0.610), 1.0, 0)]
    return out


def _tb_lambda_checks():
    """`docs/TB_lambda_sensitivity.md`."""
    import hashlib
    from scipy.stats import binomtest
    w = pl.read_csv(TBL / "41_tb_lambda_widening.csv")
    sp = pl.read_csv(TBL / "42_tb_primary_widened_lambda.csv", infer_schema_length=0)
    out = [("TB-lambda fits", w.height, 135, 0),
           ("TB-lambda reproduced", float(w["reproduced_old_selection"].sum()), 135, 0),
           ("TB-lambda changed", float(w["selection_changed"].sum()), 108, 0),
           ("TB-lambda at new top", float((w["new_edge"] == "lambda_max").sum()), 77, 0),
           ("TB-lambda interior", float((w["new_edge"] == "interior").sum()), 58, 0),
           ("TB-lambda spliced rows", sp.height, 945, 0),
           ("TB-lambda verdict FAIL",
            float("T-B VERDICT at n = 50: FAIL" in (TBL / "42_verdict_report.txt").read_text()), 1.0, 0)]
    for f, h in (("21_tb_primary.csv", "a8d38855b7ea2b22"),
                 ("21_tb_primary_report_20261110.txt", "ed9f694d24036fc6")):
        p = REPO_ROOT / "results" / f
        if p.exists():
            got = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
            out.append((f"TB-lambda {f} untouched", float(got == h), 1.0, 0))
    d = sp.filter(pl.col("n_event_days_requested") == "50").with_columns(
        pl.col("int_abs_r").cast(pl.Float64))
    k = ["censoring_rate", "gamma", "r_shape", "seed"]
    m2 = d.filter(pl.col("method") == "M2").select(k + [pl.col("int_abs_r").alias("m2")])
    for rival, shape, wins in (("B3-CV", "step", 45), ("B6", "step", 45), ("B3-CV", "logistic", 42),
                               ("B6", "logistic", 45), ("B3-CV", "half", 15), ("B6", "half", 32)):
        j = m2.join(d.filter(pl.col("method") == rival).select(k + [pl.col("int_abs_r").alias("r")]),
                    on=k).filter(pl.col("r_shape") == shape)
        out.append((f"TB-lambda {shape} M2 vs {rival} wins", float((j["m2"] < j["r"]).sum()), wins, 0))
    out.append(("TB-lambda half sign-test p", binomtest(15, 45).pvalue, 0.036, 5e-4))
    for shape, mean in (("step", 0.000129), ("logistic", 0.011271), ("half", 0.011705)):
        out.append((f"TB-lambda M2 mean {shape}",
                    float(m2.filter(pl.col("r_shape") == shape)["m2"].mean()), mean, 5e-7))
    b3 = d.filter((pl.col("method") == "B3-CV") & (pl.col("r_shape") == "half"))
    out.append(("TB-lambda B3-CV half mean", float(b3["int_abs_r"].mean()), 0.010641, 5e-7))
    rep = REPO_ROOT / "results" / "21_tb_primary_report_20261110.txt"
    if rep.exists():
        lines = rep.read_text().splitlines()

        def wins_in(shape, rival):
            for ln in lines:
                f = ln.split()
                if len(f) > 8 and f[0] == shape and f[1] == rival:
                    return float(f[4]), float(f[7])   # wins, p (f[8] is ties)
            raise AssertionError(f"no {shape}/{rival} line in the committed report")
        for shape, rival, wn, p in (("step", "B3-CV", 45, 0.0), ("step", "B6", 45, 0.0),
                                    ("logistic", "B3-CV", 41, 0.0), ("logistic", "B6", 45, 0.0),
                                    ("half", "B3-CV", 22, 1.0), ("half", "B6", 36, 0.0001)):
            got_w, got_p = wins_in(shape, rival)
            out += [(f"TB committed {shape} vs {rival} wins", got_w, wn, 0),
                    (f"TB committed {shape} vs {rival} p", got_p, p, 5e-5)]
        out.append(("TB committed verdict PASS",
                    float("T-B VERDICT at n = 50: PASS" in rep.read_text()), 1.0, 0))
    old = REPO_ROOT / "results" / "21_tb_primary.csv"
    if old.exists():
        o = pl.read_csv(old, infer_schema_length=0).filter(
            (pl.col("method") == "M2") & (pl.col("n_event_days_requested") == "50")).select(
            k + [pl.col("int_abs_r").cast(pl.Float64).alias("old")])
        j = o.join(m2, on=k)
        for shape, mean, (wo, be, sa) in (("step", 0.000125, (10, 33, 2)),
                                           ("logistic", 0.011759, (9, 20, 16)),
                                           ("half", 0.011064, (22, 14, 9))):
            q = j.filter(pl.col("r_shape") == shape)
            out += [(f"TB-lambda old M2 mean {shape}", float(q["old"].mean()), mean, 5e-7),
                    (f"TB-lambda {shape} worse", float((q["m2"] > q["old"]).sum()), wo, 0),
                    (f"TB-lambda {shape} better", float((q["m2"] < q["old"]).sum()), be, 0),
                    (f"TB-lambda {shape} same", float((q["m2"] == q["old"]).sum()), sa, 0)]
    return out


#: Plain-language guides, Phase S4. They report no new figure: every number in them
#: must already appear in a docs note. Text between the skip markers (the measured
#: demo step times) is exempt, and so are paths and code in backticks.
GUIDES = ("README.md", "docs/00_START_HERE.md")
_SKIP = re.compile(r"<!-- numbers-check: skip -->.*?<!-- /numbers-check -->", re.S)
_CODE = re.compile(r"```.*?```|`[^`\n]*`|\]\([^)]*\)", re.S)
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text: str) -> set[str]:
    return {m.group().rstrip(",") for m in _NUM.finditer(text)}


def _guide_checks():
    """README.md and docs/00_START_HERE.md: each number is traced to a docs note."""
    guides = {g: REPO_ROOT / g for g in GUIDES}
    if not all(p.exists() for p in guides.values()):
        return []
    sources = [p for p in sorted((REPO_ROOT / "docs").glob("*.md"))
               if p.resolve() not in {g.resolve() for g in guides.values()}]
    known = set().union(*(_numbers(p.read_text(encoding="utf-8")) for p in sources))
    out = []
    for g, p in guides.items():
        text = _CODE.sub(" ", _SKIP.sub(" ", p.read_text(encoding="utf-8")))
        for n in sorted(_numbers(text)):
            out.append((f"guide {g} number {n} appears in a docs note", float(n in known), 1.0, 0))
    return out


def _c1_checks():
    """`docs/C1_conclusions_table.md`: every table cell and every prose line, re-derived.

    The note is rebuilt from the artifacts by `src/build_conclusions_table.py`; each table
    cell of the committed note must equal the rebuilt cell (one check per cell), and every
    other line must match too. A hand edit to any figure in the note fails here.
    """
    from src import build_conclusions_table as bct
    note = REPO_ROOT / "docs" / "C1_conclusions_table.md"
    if not note.exists() or not (Q5D / "q5_real.csv").exists():
        return []
    have = note.read_text(encoding="utf-8").splitlines()
    want = bct.markdown(bct.build()).splitlines()
    out = [("C1 note line count", len(have), len(want), 0)]
    header = None
    for i, (h, w) in enumerate(zip(have, want)):
        if w.startswith("| row "):
            header = [c.strip() for c in w.strip("|").split("|")]
        if w.startswith("| ") and not w.startswith("| row ") and header:
            hc = [c.strip() for c in h.strip("|").split("|")]
            wc = [c.strip() for c in w.strip("|").split("|")]
            for col, a, b in zip(header, hc, wc):
                out.append((f"C1 {wc[0]} / {col}", float(a == b), 1.0, 0))
            out.append((f"C1 {wc[0]} cell count", len(hc), len(wc), 0))
        else:
            out.append((f"C1 line {i + 1}", float(h == w), 1.0, 0))
    return out


def _q2_prose(cov: pl.DataFrame, s: pl.DataFrame) -> list:
    """The figures `docs/Q2_results.md` quotes in prose (sections 1 and 4)."""
    def lvl(dial, sg, b):
        return cov.filter((pl.col("dial") == dial) & (pl.col("sigma") == sg)
                          & ((pl.col("b") - b).abs() < 1e-9)).row(0, named=True)
    h, t = lvl("q2a", 0.0, -0.047), lvl("q2a", 0.0, 0.033)
    l1 = s.filter((pl.col("dial") == "q2a") & ((pl.col("b") + 0.047).abs() < 1e-9)
                  & (pl.col("lam") == "L1")).row(0, named=True)
    return [("Q2 prose Anchor H bias covered 126", h["n_covered"], 126, 0),
            ("Q2 prose Anchor H bias coverage 0.333", h["level_coverage"], 0.333, 5e-4),
            ("Q2 prose Anchor T bias covered 162", t["n_covered"], 162, 0),
            ("Q2 prose Anchor T bias coverage 0.429", t["level_coverage"], 0.429, 5e-4),
            ("Q2 prose lambda1 at b-0.047 informative 54", l1["n_informative"], 54, 0),
            ("Q2 prose lambda1 at b-0.047 missed 54", l1["n_informative_and_missed"], 54, 0),
            ("Q2 prose b-0.10 coverage s0 0.310", lvl("q2b", 0.0, -0.1)["level_coverage"], 0.310, 5e-4),
            ("Q2 prose b-0.10 coverage s0.066 0.511", lvl("q2b", 0.066, -0.1)["level_coverage"], 0.511, 5e-4),
            ("Q2 prose b-0.10 coverage s0.18 0.860", lvl("q2b", 0.18, -0.1)["level_coverage"], 0.860, 5e-4),
            ("Q2 prose no crossed level reaches 95% with bias",
             float((cov.filter((pl.col("dial") == "q2b") & (pl.col("b") != 0))["level_coverage"]
                    < 0.95).all()), 1.0, 0)]


def _q2_checks():
    """`docs/Q2_results.md`: every table cell parsed from the note against the artifacts,
    plus the figures quoted in the prose."""
    q2 = REPO_ROOT / "artifacts" / "Q2"
    note = REPO_ROOT / "docs" / "Q2_results.md"
    if not (q2 / "q2_summary_by_level.csv").exists() or not note.exists():
        return []
    cov = pl.read_csv(q2 / "q2_coverage_by_level.csv")
    s = pl.read_csv(q2 / "q2_summary_by_level.csv", infer_schema_length=None)
    lam_of = {"λ₁": "L1", "λ₂": "L2", "λ₃": "L3", "λ₄": "L4", "λ₅": "L5", "λ₆": "L6", "λ₇": "L7"}
    out, sigma, bs = [], None, None
    for line in note.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("| q2a ") or line.startswith("| q2b "):
            dial, sg, b = cells[0], float(cells[1]), float(cells[2])
            r = cov.filter((pl.col("dial") == dial) & (pl.col("sigma") == sg)
                           & ((pl.col("b") - b).abs() < 1e-9)).row(0, named=True)
            k, n = (int(x) for x in cells[3].split("/"))
            tag = f"Q2 cov {dial} s{sg:g} b{b:+.3f}"
            out += [(f"{tag} covered", r["n_covered"], k, 0), (f"{tag} scored", r["n_scored"], n, 0),
                    (f"{tag} coverage", r["level_coverage"], float(cells[4]), 5e-4),
                    (f"{tag} informative-and-missed", r["n_informative_and_missed"], int(cells[5]), 0),
                    (f"{tag} widths flag", float(r["level_coverage_ok"]),
                     float(cells[6] == "reported"), 0)]
        elif re.fullmatch(r"σ = [0-9.]+( \(.*\))?:", line.strip()):
            sigma = float(line.split()[2].rstrip(":"))
        elif line.startswith("| functional |") and sigma is not None:
            bs = [float(c.split()[1]) for c in cells[1:]]
        elif cells and cells[0] in lam_of and bs is not None:
            for b, c in zip(bs, cells[1:]):
                k, m = (int(x) for x in c.split("/"))
                r = s.filter((pl.col("sigma") == sigma) & ((pl.col("b") - b).abs() < 1e-9)
                             & (pl.col("lam") == lam_of[cells[0]])).row(0, named=True)
                tag = f"Q2 s{sigma:g} b{b:+.3f} {lam_of[cells[0]]}"
                out += [(f"{tag} informative", r["n_informative"], k, 0),
                        (f"{tag} informative-and-missed", r["n_informative_and_missed"], m, 0)]
    rows_a = pl.read_csv(q2 / "q2a_bias_dial.csv", infer_schema_length=0)
    rows_b = pl.read_csv(q2 / "q2b_crossed.csv", infer_schema_length=0)
    q0 = pl.read_csv(Q0 / "q0_anchors.csv").filter(
        (pl.col("anchor") == "H") & pl.col("area").str.starts_with("DE excl")
        & (pl.col("sample") == "price >= 0"))
    q1 = pl.read_csv(Q1D / "q1_summary_by_level.csv").filter(pl.col("noise") == "iid")
    z = s.filter((pl.col("b") == 0) & (pl.col("dial") == "q2b")).join(
        q1.select(["sigma", "lam", pl.col("n_informative").alias("q1")]), on=["sigma", "lam"])
    out += [("Q2 q2a rows", rows_a.height, 1890, 0), ("Q2 q2b rows", rows_b.height, 3402, 0),
            ("Q2 prereg commit on every row",
             float(set(rows_a["preregistration_commit"]) | set(rows_b["preregistration_commit"])
                   == {"b261c9f"}), 1.0, 0),
            ("Q2 Anchor H bias quoted", float(q0["bias"][0]), -0.0472, 5e-5),
            ("Q2 unbiased rows reproduce Q1 (21 functional-levels)",
             float(z.height == 21 and (z["n_informative"] == z["q1"]).all()), 1.0, 0),
            *_q2_prose(cov, s),
            ("Q2 every biased level below 95%",
             float((cov.filter(pl.col("b") != 0)["level_coverage"] < 0.95).all()), 1.0, 0)]
    return out


def _v1_checks():
    """`docs/V_results.md` V1: both tables parsed from the note, plus the prose figures."""
    vd = REPO_ROOT / "artifacts" / "V"
    note = REPO_ROOT / "docs" / "V_results.md"
    if not (vd / "v1_coverage.csv").exists() or not note.exists():
        return []
    cov = pl.read_csv(vd / "v1_coverage.csv", infer_schema_length=None)
    fun = pl.read_csv(vd / "v1_by_functional.csv", infer_schema_length=None)
    lam_of = {"λ₁": "L1", "λ₂": "L2", "λ₃": "L3", "λ₄": "L4", "λ₆": "L6", "λ₇": "L7"}
    out, section = [], None
    for line in note.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line
        if not line.startswith("| ") or line.startswith("| B |") or line.startswith("| functional |"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if section and section.startswith("## V1") and cells[0][0].isdigit():
            B, b = float(cells[0]), float(cells[1])
            r = cov.filter(((pl.col("B") - B).abs() < 1e-9)
                           & ((pl.col("b_true") - b).abs() < 1e-9)).row(0, named=True)
            k, n = (int(x) for x in cells[2].split("/"))
            tag = f"V1 B{B:.2f} b{b:+.3f}"
            applies = str(r["criterion_applies"]) == "True"
            out += [(f"{tag} covered", r["n_covered"], k, 0), (f"{tag} scored", r["n_scored"], n, 0),
                    (f"{tag} coverage", r["coverage"], float(cells[3]), 5e-4),
                    (f"{tag} applies", float(applies), float(cells[4] == "yes"), 0),
                    (f"{tag} result", float(applies and str(r["passes"]) == "True"),
                     float(cells[5] == "PASS"), 0)]
        elif section and section.startswith("## V1") and cells[0] in lam_of:
            B = float(cells[1])
            r = fun.filter((pl.col("lam") == lam_of[cells[0]]) & (pl.col("b_true") == 0)
                           & ((pl.col("B") - B).abs() < 1e-9)).row(0, named=True)
            mw = float(cells[2])
            tol = 0.5 * 10 ** (-3) if "e" not in cells[2] else abs(mw) * 0.01
            tag = f"V1 b*0 {lam_of[cells[0]]} B{B:.2f}"
            ki, ni = (int(x) for x in cells[3].split("/"))
            kc, nc = (int(x) for x in cells[4].split("/"))
            out += [(f"{tag} median width", r["median_width"], mw, tol),
                    (f"{tag} informative", r["n_informative"], ki, 0), (f"{tag} cells", r["n_cells"], ni, 0),
                    (f"{tag} covered", r["n_covered"], kc, 0), (f"{tag} scored", r["n_scored"], nc, 0)]
    raw = pl.concat([pl.read_csv(f, infer_schema_length=0, columns=["hetero", "rate", "gamma", "r_shape",
                                                                     "seed", "s", "v0_commit"])
                     for f in sorted(vd.glob("v1_raw_shard*of4.csv"))])
    per_cell = raw.group_by(["hetero", "rate", "gamma", "r_shape", "seed"]).agg(pl.col("s").n_unique())
    applies = cov.filter(pl.col("criterion_applies").cast(pl.String).str.to_lowercase() == "true")
    q2 = pl.read_csv(REPO_ROOT / "artifacts" / "Q2" / "q2_coverage_by_level.csv").filter(
        (pl.col("dial") == "q2a") & ((pl.col("b") + 0.047).abs() < 1e-9))
    q2l5 = pl.read_csv(REPO_ROOT / "artifacts" / "Q2" / "q2_summary_by_level.csv").filter(
        (pl.col("dial") == "q2a") & ((pl.col("b") + 0.047).abs() < 1e-9) & (pl.col("lam") == "L5"))
    out += [("V1 54 cells", per_cell.height, 54, 0),
            ("V1 70 potentials in every cell", float((per_cell["s"] == 70).all()), 1.0, 0),
            ("V1 V0 commit on every raw row", float(set(raw["v0_commit"]) == {"3277ea6"}), 1.0, 0),
            ("V1 applicable levels", applies.height, 9, 0),
            ("V1 PASS: every applicable level 324/324",
             float(applies.height == 9 and (applies["n_covered"] == 324).all()
                   and (applies["n_scored"] == 324).all()), 1.0, 0),
            ("V1 Q2 126 of 378 at b*-0.047", q2["n_covered"][0], 126, 0),
            ("V1 Q2 lambda5 covered rows 18", q2l5["lam_n_covered"][0], 18, 0),
            ("V1 126 - 18 = 108", q2["n_covered"][0] - q2l5["lam_n_covered"][0], 108, 0)]
    return out


def _v2_checks():
    """`docs/V_results.md` V2: the breakdown table parsed from the note, plus reproduction."""
    vd = REPO_ROOT / "artifacts" / "V"
    note = REPO_ROOT / "docs" / "V_results.md"
    if not (vd / "v2_breakdown.csv").exists() or not note.exists():
        return []
    bd = {r["lam"]: r for r in pl.read_csv(vd / "v2_breakdown.csv", infer_schema_length=0).iter_rows(named=True)}
    lam_of = {"λ₁": "L1", "λ₂": "L2", "λ₃": "L3", "λ₆": "L6"}
    out, section = [], None

    def iv(cell, lo, hi, tag):
        if cell == "—":
            return [(f"{tag} absent", float(lo is None or lo == ""), 1.0, 0)]
        a, b = (float(x) for x in cell.strip("[]").split(","))
        return [(f"{tag} lo", float(lo), a, 5e-4), (f"{tag} hi", float(hi), b, 5e-4)]
    for line in note.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line
        if not (section and section.startswith("## V2") and line.startswith("| λ")):
            continue
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        r, tag = bd[lam_of[c[0]]], f"V2 {lam_of[c[0]]}"
        out.append((f"{tag} breakdown", float(c[3] == r["breakdown_B"]
                                               or (c[3] != "> 0.15" and r["breakdown_B"] != "> 0.15"
                                                   and abs(float(c[3]) - float(r["breakdown_B"])) < 1e-9)), 1.0, 0))
        out.append((f"{tag} holds at B=0", float(r["holds_at_B0"] == "True"), 1.0, 0))
        out += iv(c[4], r["lo_B0"], r["hi_B0"], f"{tag} B0")
        out += iv(c[5], r["lo_at_break"], r["hi_at_break"], f"{tag} at break")
        out += iv(c[6], r["lo_B015"], r["hi_B015"], f"{tag} B0.15")
    raw = pl.read_csv(vd / "v2_real_raw.csv", infer_schema_length=0).with_columns(
        pl.col("b").cast(pl.Float64))
    q5 = pl.read_csv(Q5D / "q5_real.csv", infer_schema_length=0).filter(
        (pl.col("setting") == "main") & (pl.col("potential") == "H") & (pl.col("period") == "window")
        & pl.col("c_hat").str.contains("recalibrated").not_())
    j = raw.filter(pl.col("b") == 0).join(q5.select(["lam", pl.col("lo").alias("qlo"), pl.col("hi").alias("qhi")]),
                                          on="lam")
    q0 = pl.read_csv(Q0 / "q0_anchors.csv").filter(
        (pl.col("anchor") == "H") & pl.col("area").str.starts_with("DE excl") & (pl.col("sample") == "price >= 0"))
    out += [("V2 31 scorings", raw["b"].n_unique(), 31, 0),
            ("V2 b=0 reproduces Q5 window H, all functionals",
             float(j.height == 7 and (j["lo"] == j["qlo"]).all() and (j["hi"] == j["qhi"]).all()), 1.0, 0),
            ("V2 scale: H bias -0.0472", float(q0["bias"][0]), -0.0472, 5e-5)]
    hv = pl.read_csv(vd / "v2_robust_intervals.csv")

    def holds(lam, B):
        return float(hv.filter((pl.col("lam") == lam) & ((pl.col("B") - B).abs() < 1e-9))
                     ["reading_holds"][0])
    out += [("V2 prose L1 survives 0.03", holds("L1", 0.03), 1.0, 0),
            ("V2 prose L6 survives 0.03", holds("L6", 0.03), 1.0, 0),
            ("V2 prose L2 survives 0.05", holds("L2", 0.05), 1.0, 0),
            ("V2 prose L3 survives 0.15", holds("L3", 0.15), 1.0, 0)]
    return out


def _collect():
    """All checks whose artifacts are on disk, as (id, got, want, tol)."""
    out, skipped = [], []
    try:
        o = load(P3 / "p3_synthetic_arm_o.csv")
        r = load(P3 / "p3_real.csv")
        out += _checks(o, r)
        d = P3 / "p3_synthetic_arm_d.csv"
        if d.exists():
            dd = load(d)
            out += _checks_arm_d(dd, o)
            out += _q0_from_arm_d(dd)
        else:
            skipped.append("P3 Arm D")
    except FileNotFoundError:
        skipped.append("P3")
    q = Q0 / "q0_anchors.csv"
    if q.exists():
        out += _q0_checks(load(q))
    else:
        skipped.append("Q0 anchors")
    if (Q0B / "q0b_verdicts.csv").exists():
        out += _q0b_checks(load(Q0B / "q0b_gap_shares.csv"),
                           load(Q0B / "q0b_verdicts.csv"),
                           load(Q0B / "q0b_h_agreement.csv"))
        out += _amendment1_checks()
        out += _open_list_checks()
    else:
        skipped.append("Q0b")
    out += _qs_file_checks()
    if (Q0C / "q0c_volume.csv").exists():
        out += _q0c_checks()
    else:
        skipped.append("Q0c")
    if (Q5D / "q5_summary.csv").exists():
        out += _q5_checks()
    else:
        skipped.append("Q5")
    if (Q6D / "q6a_cells.csv").exists():
        out += _q6a_checks()
    else:
        skipped.append("Q6a")
    if (Q6D / "q6b_summary.csv").exists():
        out += _q6b_checks()
    else:
        skipped.append("Q6b")
    if (TBL / "42_tb_primary_widened_lambda.csv").exists():
        out += _tb_lambda_checks()
    else:
        skipped.append("T-B lambda sensitivity")
    if (Q1D / "q1_summary_by_level.csv").exists():
        out += _q1_checks()
    else:
        skipped.append("Q1")
    out += _guide_checks()
    out += _c1_checks()
    out += _q2_checks()
    out += _v1_checks()
    out += _v2_checks()
    return out, skipped


_CHECKS, _SKIPPED = _collect()


@pytest.mark.parametrize("name,got,want,tol",
                         _CHECKS or [("no artifacts on disk", 0, 0, 0)],
                         ids=[c[0] for c in _CHECKS] or ["skipped"])
def test_quoted_figure_reproduces(name, got, want, tol):
    """A figure quoted in a results note must still come out of the artifact."""
    if not _CHECKS:
        pytest.skip("no results artifacts on disk; nothing to re-derive")
    assert abs(float(got) - float(want)) <= tol, (
        f"{name}: the artifact gives {got!r}, the note quotes {want!r}. Correct the "
        f"note (and record the correction), or re-run the analysis -- do not widen "
        f"the tolerance.")


def test_the_checker_is_actually_checking_something():
    """A guard against the suite passing because every artifact vanished."""
    if _SKIPPED == ["P3", "Q0 anchors"]:
        pytest.skip("no artifacts on disk at all")
    assert len(_CHECKS) >= 50, f"only {len(_CHECKS)} checks collected; skipped {_SKIPPED}"


def main() -> None:
    checks, skipped = _collect()
    bad = 0
    for name, got, want, tol in checks:
        good = abs(float(got) - float(want)) <= tol
        bad += not good
        print(f"{'ok  ' if good else 'FAIL'}  {name:<48} {got!r:>24}  quoted {want!r}")
    if skipped:
        print("skipped (artifact absent):", ", ".join(skipped))
    print(f"\n{bad} mismatch(es)" if bad else
          f"\nevery quoted figure reproduces ({len(checks)} checks)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
