"""Re-derive every figure quoted in `docs/P3_results.md` from the artifacts.

    python -m src.identification.check_p3_numbers        # exits non-zero on a mismatch

Hard rule 20 says every number in a results note cites the artifact file and column it
came from. This module is the other half of that rule: it recomputes each quoted
figure and fails loudly if the document and the artifact have drifted apart. Running
it the first time found four wrong figures in the note's own first version, which are
recorded in that note's correction section rather than quietly fixed.

Each entry is (where in the document, computation, quoted value, tolerance). The
tolerance is the rounding the document uses, never a band chosen to make a check pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import polars as pl

from src.identification.summarise_p3 import load

REPO_ROOT = Path(__file__).resolve().parents[2]
P3 = REPO_ROOT / "artifacts" / "P3"


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


def main() -> None:
    o = load(P3 / "p3_synthetic_arm_o.csv")
    r = load(P3 / "p3_real.csv")
    checks = _checks(o, r)
    arm_d = P3 / "p3_synthetic_arm_d.csv"
    if arm_d.exists():
        checks += _checks_arm_d(load(arm_d), o)
    else:
        print("note: Arm D artifact absent, section 2.4 not checked")
    bad = 0
    for name, got, want, tol in checks:
        good = abs(float(got) - float(want)) <= tol
        bad += not good
        print(f"{'ok  ' if good else 'FAIL'}  {name:<48} {got!r:>24}  quoted {want!r}")
    print(f"\n{bad} mismatch(es)" if bad else "\nevery quoted figure reproduces")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
