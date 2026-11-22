"""Generated text of the amendments to docs/12, with every number read from the constants and
the step 1 artifacts (so the number checker holds them)."""

from __future__ import annotations

import polars as pl

from src.method.learned_potential import config as cfg
from src.method.learned_potential.data import ART


def _overlap() -> dict:
    return {r["unit"]: r for r in pl.read_csv(ART / "domain_overlap.csv").iter_rows(named=True)}


def _diag() -> dict:
    return {r["area"]: r for r in pl.read_csv(ART / "overlap_diagnosis.csv").iter_rows(named=True)}


def amendment1_text() -> str:
    o, d = _overlap(), _diag()
    agg = o["aggregate (mean p over the areas)"]
    pool = o["pooled area rows"]
    h = d["50Hertz"]
    pct = lambda r: f"{r['share_no_overlap'] * 100:.1f}%"           # noqa: E731
    over = [u for u in (*cfg.AREAS, "pooled area rows")
            if o[u]["share_no_overlap"] > cfg.OVERLAP_STOP_SHARE]
    names = " and ".join("the pooled area rows" if u == "pooled area rows" else u for u in over)
    return "\n".join([
        "### Status when written",
        "",
        "Written after step 1 and before any available-power model was fitted. The only model fitted on",
        "real data so far is the domain classifier. No look-alike score, b̂_H or B̂ has been computed.",
        "The amendment responds to the overlap result below and to nothing else.",
        "",
        "### What happened",
        "",
        "The pre-registered stop was crossed. The share of target quarter-hours with domain classifier",
        f"score p > {cfg.OVERLAP_P:g} (no clean quarter-hour resembles them) is:",
        "",
        "| unit | share without overlap |",
        "|---|---|",
        f"| 50Hertz | {pct(o['50Hertz'])} ({o['50Hertz']['n_no_overlap']:,} of {o['50Hertz']['n_target']:,}) |",
        f"| Amprion | {pct(o['Amprion'])} |",
        f"| TransnetBW | {pct(o['TransnetBW'])} |",
        f"| pooled area rows | {pct(pool)} ({pool['n_no_overlap']:,} of {pool['n_target']:,}) |",
        f"| three-area aggregate | {pct(agg)} ({agg['n_no_overlap']:,} of {agg['n_target']:,}) |",
        "",
        "The pre-registration did not name the unit for this check. This amendment does not choose",
        f"the unit after the fact. The check is treated as failed in every unit above "
        f"{cfg.OVERLAP_STOP_SHARE:.0%}, which is",
        f"{names}.",
        "",
        "### Why it happened",
        "",
        "The 50Hertz target quarter-hours without overlap are sunny middays. Their median day-ahead",
        f"solar forecast is {h['median_solar_mw_target_no_overlap'] / 1000:.1f} GW and "
        f"{h['share_rd_positive_target_no_overlap'] * 100:.0f}% of them carry renewable redispatch. "
        "The clean 50Hertz",
        f"quarter-hours have a median solar forecast of {h['median_solar_mw_clean'] / 1000:.0f} GW. "
        "The clean-set rule R = 0 removes these",
        "middays because R includes distribution-cluster redispatch, which is mostly solar (Phase 6).",
        "The learned model therefore has no training labels in the region where the target hours sit.",
        "(Medians and shares: `artifacts/exp4_learned_potential/overlap_diagnosis.csv`, evaluation window.)",
        "",
        "### Changes",
        "",
        f"**C1. The clean-set rule is unchanged.** Clean set: price > {cfg.CLEAN_PRICE_ABOVE:g} €/MWh "
        "and R = 0 in the area.",
        f"Target set: price < {cfg.TARGET_PRICE_BELOW:g}. The overlap threshold (p > {cfg.OVERLAP_P:g}) "
        "is unchanged.",
        "",
        "**C2. Primary estimand: target quarter-hours with overlap.** b̂_H is computed over target",
        f"quarter-hours with out-of-fold p ≤ {cfg.OVERLAP_TRIM_P:g}. Its scope is stated as these "
        "quarter-hours only.",
        f"For 50Hertz this is {h['share_target_with_overlap'] * 100:.1f}% of its negative-price "
        "quarter-hours. The look-alike correction and",
        "the bootstrap are unchanged and run on the same trimmed set.",
        "",
        "**C3. Sensitivity arm: untrimmed.** b̂_H and B̂ are also computed over all target quarter-hours,",
        "as pre-registered. This arm relies on extrapolation and is labelled as such.",
        "",
        "**C4. Reporting rule.** Each reading is classified at the primary B̂. A reading whose verdict",
        "differs between the trimmed and untrimmed B̂ is reported as \"depends on extrapolation\", whatever",
        "the primary verdict says.",
        "",
        "**C5. Per-area reporting.** b̂_H is reported per area and for the pooled area rows. The trimmed",
        "share per area is reported next to each value.",
        "",
        "**C6. Exploratory arm E1, a revised clean rule for 50Hertz, gated by validation test V1.**",
        "",
        "- Revised rule: in 50Hertz, a quarter-hour with R > 0 counts as clean if every redispatch",
        "  measure in it is a distribution-cluster or solar measure, by the plant-name rule in",
        f"  `redispatch_checks`. Price > {cfg.CLEAN_PRICE_ABOVE:g} €/MWh still applies.",
        f"- V1, fixed now: take the positive-price (> {cfg.CLEAN_PRICE_ABOVE:g} €/MWh) 50Hertz "
        "quarter-hours that the revised rule",
        "  adds. Compute the mean of log(G / H) with a day-block 95% bootstrap interval "
        f"({cfg.V1_BOOTSTRAP_DRAWS:,} draws).",
        "  Compute the same for the existing 50Hertz clean set. V1 passes if the interval for the",
        f"  difference between the two lies within ±{cfg.V1_TOLERANCE:g}. Wind output then behaves as "
        "uncurtailed in the",
        "  added quarter-hours.",
        "- If V1 fails, E1 is not run and the result is reported.",
        "- If V1 passes, E1 refits the domain classifier and L2 with the revised clean set and reports",
        "  overlap and b̂_H. E1 is never the primary result and never sets B̂.",
        "- If the plant-name rule cannot be applied to every measure in the added quarter-hours, V1 is",
        "  reported as not possible and E1 is not run.",
        "",
        "### What stays as pre-registered",
        "",
        "Allowed and forbidden inputs, models, hyperparameter grids, folds, look-alike set, metrics,",
        "success criteria S1 to S3, model selection rule and the downstream comparison.",
    ])
