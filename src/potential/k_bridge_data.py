"""Phase K data: one quarter-hour frame for the statute-anchored bias bridge.

Everything is read through loaders that already exist, unchanged:

* `run_p3_real.load_panel(THREE_AREA, "H")` -- national price, Berlin date, the Q5 window
  mask `keep` (MTU-15 era and months with a published market value), the three-area
  cohort shares and theta per award setting;
* `q0b_validate_h.load_frames("quality-assured")` -- per control area and for the
  50Hertz + Amprion + TransnetBW aggregate: G (`act_onshore_mw`), F (`da_onshore_mw`),
  H (`hr_mw`, quality-assured Online-Hochrechnung) and RD (`rd_mw`, Q0b's redispatch).

The exposed capacity share is e_t = sum_k w_k * 1[price_t < theta_k,t] with the `main`
setting's theta and the three-area shares -- exactly the `s` that `run_arm` builds. H is
ex post: this frame is for identification analysis only, never a day-ahead input.
"""

from __future__ import annotations

import contextlib
import io

import numpy as np
import polars as pl

UNITS = ("50Hertz+Amprion+TransnetBW", "50Hertz", "Amprion", "TransnetBW")
SETTING = "main"


def load_k_frame() -> pl.DataFrame:
    from src.identification.run_p3_real import AREA, PANEL, THREE_AREA, load_panel
    from src.potential.q0b_validate_h import load_frames

    with contextlib.redirect_stdout(io.StringIO()):
        panel = load_panel(THREE_AREA, "H")
        frames = load_frames("quality-assured")
    obs = (pl.scan_parquet(PANEL).filter(pl.col("area") == AREA)
           .select(["ts_utc", "berlin_date", "price_eur_mwh"])
           .collect().drop_nulls(["price_eur_mwh"]).sort("ts_utc"))
    if obs.height != panel["price"].size:
        raise ValueError("panel and load_panel disagree on the quarter-hours")
    theta = panel["theta_for"](SETTING)
    s = (panel["price"][None, :] < theta).astype(float)
    e = (np.asarray(panel["shares"], dtype=float)[:, None] * s).sum(axis=0)
    out = obs.rename({"price_eur_mwh": "price"}).with_columns(
        pl.Series("e_main", e), pl.Series("keep", panel["keep"]))
    for u in UNITS:
        f = frames[u].select("ts_utc", *(pl.col(c).alias(f"{k}_{u}") for c, k in
                                         (("hr_mw", "H"), ("act_onshore_mw", "G"),
                                          ("da_onshore_mw", "F"), ("rd_mw", "RD"))))
        out = out.join(f, on="ts_utc", how="left")
    if out.height != obs.height:
        raise ValueError("joining the projection frames changed the row count")
    return out


BUFFER_QH = 2                      # K0 section 2: anchors keep 2 quarter-hours from any negative one
FIT_SHARE = 0.6                    # K0 section 1: first 60% of non-event days fit, last 40% held out


def anchor_mask(price: np.ndarray, buffer: int = BUFFER_QH) -> np.ndarray:
    """Anchors within one Berlin day: price > 0 and not within `buffer` QH of a negative one."""
    neg = price < 0
    near = np.zeros(price.size, dtype=bool)
    for t in np.flatnonzero(neg):
        near[max(0, t - buffer):min(price.size, t + buffer + 1)] = True
    return (price > 0) & ~near


def negative_runs(price: np.ndarray) -> list[tuple[int, int]]:
    """(start index, length) of each run of negative quarter-hours within one day."""
    out, i, neg = [], 0, price < 0
    while i < price.size:
        if neg[i]:
            j = i
            while j < price.size and neg[j]:
                j += 1
            out.append((i, j - i))
            i = j
        else:
            i += 1
    return out


def k0_facts(frame: pl.DataFrame | None = None) -> dict:
    """The K0 section 1 facts: prices, exposure, dates and coverage only -- never y_t."""
    d = (load_k_frame() if frame is None else frame).filter(pl.col("keep")).sort("ts_utc")
    facts: dict = {"window_qh": d.height,
                   "window_first": d["berlin_date"].min(), "window_last": d["berlin_date"].max()}
    for u in UNITS:
        facts[f"missing_{u}"] = d.height - d.filter(
            pl.col(f"H_{u}").is_not_null() & pl.col(f"G_{u}").is_not_null()
            & pl.col(f"RD_{u}").is_not_null()).height
    classes = {"both": 0, "one side": 0, "none": 0}
    none_days, runs, nonevent = [], [], []
    for (day,), g in d.partition_by("berlin_date", as_dict=True, maintain_order=True).items():
        p = g["price"].to_numpy()
        if not (p < 0).any():
            nonevent.append(day)
            continue
        runs += negative_runs(p)
        a, negi = anchor_mask(p), np.flatnonzero(p < 0)
        before, after = a[:negi[0]].any(), a[negi[-1] + 1:].any()
        c = "both" if before and after else ("one side" if before or after else "none")
        classes[c] += 1
        if c == "none":
            none_days.append(day)
    lengths = np.array([r[1] for r in runs])
    cut = int(round(FIT_SHARE * len(nonevent)))
    neg = d.filter(pl.col("price") < 0)
    facts.update({
        "event_days": sum(classes.values()), "both": classes["both"],
        "one_side": classes["one side"], "none": classes["none"], "none_days": none_days,
        "neg_qh": neg.height, "runs": len(runs), "run_len_median": float(np.median(lengths)),
        "run_len_p10": float(np.percentile(lengths, 10)), "run_len_p90": float(np.percentile(lengths, 90)),
        "run_len_max": int(lengths.max()), "runs_short": int((lengths <= 4).sum()),
        "runs_medium": int(((lengths > 4) & (lengths <= 16)).sum()), "runs_long": int((lengths > 16).sum()),
        "nonevent_days": len(nonevent), "fit_days": cut, "fit_first": nonevent[0],
        "fit_last": nonevent[cut - 1], "heldout_days": len(nonevent) - cut,
        "heldout_first": nonevent[cut], "heldout_last": nonevent[-1],
        "e_neg_min": float(neg["e_main"].min()), "e_neg_median": float(neg["e_main"].median()),
        "e_neg_le_005_qh": int((neg["e_main"] <= 0.05).sum()),
        "run_table": runs, "nonevent_list": nonevent,
    })
    return facts
