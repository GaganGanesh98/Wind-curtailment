#!/usr/bin/env python3
"""Step 6 — bias-by-price-band figure, one per control area (plus DE).

Reads results/02_bias_by_price_band.csv and writes figures/bias_by_price_band_<area>.png
plus a combined figures/bias_by_price_band_all_areas.png.

Usage:  python src/make_figures.py
"""

from __future__ import annotations

import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from smard_config import AREA_LABEL, AREAS, FIGURES_DIR, PRICE_BANDS, RESULTS_DIR  # noqa: E402

BAND_ORDER = [b[0] for b in PRICE_BANDS]


def load():
    with open(os.path.join(RESULTS_DIR, "02_bias_by_price_band.csv")) as fh:
        return list(csv.DictReader(fh))


def panel(ax, rows, title):
    by = {r["price_band_eur_mwh"]: r for r in rows}
    bands = [b for b in BAND_ORDER if b in by]
    x = range(len(bands))
    means, los, his, labels = [], [], [], []
    for b in bands:
        r = by[b]
        m = float(r["mean_e_mw"])
        lo = float(r["ci_lo_mw"]) if r["ci_lo_mw"] else m
        hi = float(r["ci_hi_mw"]) if r["ci_hi_mw"] else m
        means.append(m); los.append(m - lo); his.append(hi - m)
        labels.append(f"{b}\nn={r['qhs']} / {r['days']}d")

    colors = ["#b2182b" if m < 0 else "#2166ac" for m in means]
    ax.bar(x, means, color=colors, width=0.62, zorder=2)
    ax.errorbar(x, means, yerr=[los, his], fmt="none", ecolor="black",
                elinewidth=1.2, capsize=4, zorder=3)
    ax.axhline(0, color="black", lw=0.9, zorder=4)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("mean $e_t$ = actual − day-ahead forecast (MW)", fontsize=8)
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.grid(axis="y", alpha=0.3, zorder=0)
    ax.tick_params(labelsize=8)


def main() -> int:
    os.makedirs(FIGURES_DIR, exist_ok=True)
    rows = load()
    written = []

    for area in AREAS:
        label = AREA_LABEL[area]
        sub = [r for r in rows if r["area"] == label]
        if not sub:
            continue
        fig, ax = plt.subplots(figsize=(7.4, 4.2))
        panel(ax, sub, f"Day-ahead wind forecast bias by price band — {label}")
        fig.text(0.01, 0.015,
                 "Negative = over-forecast. Whiskers: 95% CI, 5,000-draw "
                 "bootstrap resampling whole Berlin-local event-days. "
                 "n = quarter-hours / event-days.\n"
                 "Source: SMARD (Bundesnetzagentur), CC BY 4.0. "
                 "1 Oct 2025 – 28 Oct 2026, 15-min.",
                 fontsize=5.6, color="#444444")
        fig.tight_layout(rect=(0, 0.055, 1, 1))
        out = os.path.join(FIGURES_DIR,
                           f"bias_by_price_band_{label.replace(' ', '_')}.png")
        fig.savefig(out, dpi=200)
        plt.close(fig)
        written.append(out)
        print(f"  wrote {out}")

    # combined 5-panel overview
    fig, axes = plt.subplots(3, 2, figsize=(13, 12))
    for ax, area in zip(axes.flat, AREAS):
        sub = [r for r in rows if r["area"] == AREA_LABEL[area]]
        if sub:
            panel(ax, sub, AREA_LABEL[area])
    axes.flat[-1].axis("off")
    fig.suptitle("Day-ahead wind forecast bias by day-ahead price band, "
                 "1 Oct 2025 – 28 Oct 2026",
                 fontsize=13, fontweight="bold")
    fig.text(0.02, 0.012,
             "Negative = over-forecast. Whiskers: 95% CI, 5,000-draw bootstrap "
             "resampling whole Berlin-local event-days. n = quarter-hours / "
             "event-days. Source: SMARD (Bundesnetzagentur), CC BY 4.0.",
             fontsize=7, color="#444444")
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    out = os.path.join(FIGURES_DIR, "bias_by_price_band_all_areas.png")
    fig.savefig(out, dpi=180)
    plt.close(fig)
    written.append(out)
    print(f"  wrote {out}")
    print(f"{len(written)} figures written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
