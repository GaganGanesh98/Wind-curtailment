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

import sys
from pathlib import Path

import numpy as np
import polars as pl

import pytest

from src.identification.summarise_p3 import load

REPO_ROOT = Path(__file__).resolve().parents[1]
P3 = REPO_ROOT / "artifacts" / "P3"
Q0 = REPO_ROOT / "artifacts" / "Q0"


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
