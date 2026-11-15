"""Q0c: three-area onshore market-curtailment volume, against Hirth v2's 2.5 TWh.

    python -m src.potential.q0c_volume

Pre-registration `docs/Q0c_preregistration.md` (commit recorded below). Report only.

V = sum over negative-price quarter-hours of (H - G - R) * 0.25 h, in TWh, on
50Hertz + Amprion + TransnetBW (TenneT excluded under T-D(vii), `docs/Q_STOP_Q0c.md`),
2026-01-01 to 2026-10-28. H, G, R are exactly Q0b's (`q0b_validate_h.load_frames`,
quality-assured series). 95% event-day block bootstrap, 5,000 draws, seed 42.

Verdict (one-sided, pre-registered): INCONSISTENT - Q0c higher if the CI's lower bound
exceeds 2.5 TWh; otherwise NOT TESTABLE at national scale. No "consistent" verdict exists.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

import numpy as np
import polars as pl

from src.potential.q0b_validate_h import AGG_NAME, git_head, load_frames

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / "artifacts" / "Q0c"
PREREG_COMMIT = "60efa6e"
D0, D1 = "2026-01-01", "2026-10-28"   # Berlin dates, ISO strings as in the panel
HIRTH_TWH = 2.5
N_BOOT, SEED = 5000, 42
QH_H = 0.25


def volume(df: pl.DataFrame) -> list[dict]:
    neg = df.filter(pl.col("price_eur_mwh") < 0)
    resid = (neg["hr_mw"] - neg["act_onshore_mw"] - neg["rd_mw"]).to_numpy()
    days = neg["berlin_date"].to_numpy()
    uniq, idx = np.unique(days, return_inverse=True)
    rng = np.random.default_rng(SEED)
    draws = rng.integers(0, len(uniq), size=(N_BOOT, len(uniq)))
    rows = []
    for name, x in (("signed", resid), ("clipped_at_zero", np.clip(resid, 0, None))):
        per_day = np.bincount(idx, weights=x * QH_H, minlength=len(uniq)) / 1e6  # TWh
        point = float(per_day.sum())
        boot = per_day[draws].sum(axis=1)
        lo, hi = (float(v) for v in np.percentile(boot, [2.5, 97.5]))
        rows.append({
            "statistic": name, "volume_twh": point, "ci_lo_twh": lo, "ci_hi_twh": hi,
            "hirth_twh": HIRTH_TWH,
            "verdict": ("INCONSISTENT - Q0c higher" if lo > HIRTH_TWH
                        else "NOT TESTABLE at national scale"),
            "primary": name == "signed",
            "n_neg_qh": int(len(resid)), "n_event_days": int(len(uniq)),
            "share_qh_resid_negative": float((resid < 0).mean()),
            "mean_resid_mw": float(resid.mean()),
        })
    return rows


def main() -> None:
    frames = load_frames("quality-assured")
    agg = frames[AGG_NAME].filter((pl.col("berlin_date") >= D0) & (pl.col("berlin_date") <= D1))
    rows = volume(agg)
    # Coverage: negative-price quarter-hours in each area's frame vs the three-area join.
    cover = {a: frames[a].filter((pl.col("berlin_date") >= D0) & (pl.col("berlin_date") <= D1)
                                 & (pl.col("price_eur_mwh") < 0)).height
             for a in ("50Hertz", "Amprion", "TransnetBW")}
    head, today = git_head(), dt.date.today().isoformat()
    for r in rows:
        r.update({"window_start": D0, "window_end": D1,
                  "region": AGG_NAME, "series": "quality-assured",
                  "n_neg_qh_50Hertz": cover["50Hertz"], "n_neg_qh_Amprion": cover["Amprion"],
                  "n_neg_qh_TransnetBW": cover["TransnetBW"],
                  "first_qh_utc": str(agg["ts_utc"].min()), "last_qh_utc": str(agg["ts_utc"].max()),
                  "n_boot": N_BOOT, "seed": SEED,
                  "preregistration_commit": PREREG_COMMIT, "code_commit": head, "run_date": today})
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "q0c_volume.csv"
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print({k: r[k] for k in ("statistic", "volume_twh", "ci_lo_twh", "ci_hi_twh", "verdict",
                                 "n_neg_qh", "n_event_days", "share_qh_resid_negative")})
    print(cover, "->", path)


if __name__ == "__main__":
    main()
