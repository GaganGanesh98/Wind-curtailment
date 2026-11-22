"""The linear functionals P3 bounds, as coefficient vectors over the response grid.

`docs/P0_preregistration.md` section 7 names six; a seventh is added here and
declared as an addition in `docs/P3_results.md` section 0. Each returns a vector
`lam` with `lam @ r` equal to the quantity, plus the counts and caveats that make the
number readable.

The quantities, and why each one is here:

  L1  fleet switched-off share, price in (-20, -5]  -- an aggregate; should be pinned
  L2  fleet switched-off share, price <= -50         -- the same, where data is thinnest
  L3  response of one named cohort alone           -- a cohort-level claim
  L4  response of the collinear theta = 0 GROUP    -- the combination that IS identified
  L5  curtailed energy if one cohort's threshold moved to 0, GWh -- a policy counterfactual
  L6  L3 - L4                                      -- cohort heterogeneity
  L7  response of ONE MEMBER of the collinear group alone  -- the split that is NOT identified

L4 against L7 is the sharpest statement P3 can make: the same capacity, read as a
group and read as one of its two members. If the group is pinned and the member is
not, "aggregate data identifies the combination and not the split" stops being an
assertion about rank and becomes two numbers.
"""

from __future__ import annotations

import numpy as np

from src.method.bounds import BoundsDesign, _bin_of


def _col(design: BoundsDesign, k: int, j: int, m: int) -> int | None:
    return design.col_of.get((int(k), int(j), int(m)))


def _occupied(design: BoundsDesign, s: np.ndarray, depth: np.ndarray,
              level: np.ndarray, k: int) -> tuple[np.ndarray, np.ndarray]:
    """(row positions, column indices) where cohort k is exposed, on the design rows."""
    on = s[k, design.rows] > 0.0
    r_idx = np.flatnonzero(on)
    jb = _bin_of(depth[k, design.rows], design.depth_edges)
    cols = np.array([_col(design, k, j, m) for j, m
                     in zip(jb[on], level[k, design.rows][on])])
    return r_idx, cols


def run_levels(design: BoundsDesign, runlen: np.ndarray | None,
               s: np.ndarray) -> np.ndarray:
    """Recover the (K, T) run-length level assignment the design was built with."""
    if design.n_run_levels <= 1 or runlen is None or not np.isfinite(design.run_split):
        return np.zeros_like(np.asarray(s), dtype=int)
    return (np.asarray(runlen, dtype=float) > design.run_split).astype(int)


def band_mean(design: BoundsDesign, price: np.ndarray, lo: float, hi: float) -> dict:
    """L1, L2: mean of c over the quarter-hours whose price lies in (lo, hi].

    `lam @ r` is the mean predicted switched-off share over the band, which is the
    fleet's switched-off share there (the whole fleet, not only its exposed part) --
    exposure composition included, as it must be, because a
    cohort that is not exposed contributes nothing to the fleet's response.
    """
    p = np.asarray(price, dtype=float)[design.rows]
    m = (p > lo) & (p <= hi)
    n = int(m.sum())
    if n == 0:
        return {"lam": np.zeros(design.n_cols), "n_qh": 0, "defined": False,
                "note": f"no exposed quarter-hour with price in ({lo}, {hi}]"}
    return {"lam": design.X[m].mean(axis=0), "n_qh": n, "defined": True, "note": ""}


def cohort_mean(design: BoundsDesign, s: np.ndarray, depth: np.ndarray,
                level: np.ndarray, cohort_id: str) -> dict:
    """L3, L7: mean of r_k over the quarter-hours where cohort k is exposed."""
    if cohort_id not in design.cohort_ids:
        return {"lam": np.zeros(design.n_cols), "n_qh": 0, "defined": False,
                "note": f"cohort {cohort_id!r} not in this design"}
    k = design.cohort_ids.index(cohort_id)
    r_idx, cols = _occupied(design, s, depth, level, k)
    if r_idx.size == 0:
        return {"lam": np.zeros(design.n_cols), "n_qh": 0, "defined": False,
                "note": f"cohort {cohort_id!r} is never exposed in this arm"}
    lam = np.zeros(design.n_cols)
    np.add.at(lam, cols, 1.0 / r_idx.size)
    return {"lam": lam, "n_qh": int(r_idx.size), "defined": True, "note": ""}


def group_mean(design: BoundsDesign, s: np.ndarray, depth: np.ndarray,
               level: np.ndarray, shares: np.ndarray, cohort_ids) -> dict:
    """L4: the capacity-weighted response of a GROUP of cohorts.

    Averaged over the quarter-hours where at least one member is exposed, and
    normalised by the group's capacity share, so the number is on the same [0, 1]
    scale as a single cohort's response and the two can be read against each other.
    """
    idx = [design.cohort_ids.index(c) for c in cohort_ids if c in design.cohort_ids]
    if not idx:
        return {"lam": np.zeros(design.n_cols), "n_qh": 0, "defined": False,
                "note": f"none of {list(cohort_ids)} is in this design"}
    w = np.asarray(shares, dtype=float)
    w_grp = float(w[idx].sum())
    any_on = np.zeros(design.rows.size, dtype=bool)
    for k in idx:
        any_on |= s[k, design.rows] > 0.0
    n = int(any_on.sum())
    if n == 0 or w_grp <= 0:
        return {"lam": np.zeros(design.n_cols), "n_qh": 0, "defined": False,
                "note": "the group is never exposed in this arm"}
    lam = np.zeros(design.n_cols)
    for k in idx:
        r_idx, cols = _occupied(design, s, depth, level, k)
        if r_idx.size:
            np.add.at(lam, cols, w[k] / (w_grp * n))
    return {"lam": lam, "n_qh": n, "defined": True,
            "note": f"group capacity share {w_grp:.4f}"}


def threshold_to_zero_energy(design: BoundsDesign, s: np.ndarray, depth: np.ndarray,
                             level: np.ndarray, shares: np.ndarray, price: np.ndarray,
                             potential_mw: np.ndarray, cohort_id: str) -> dict:
    """L5: curtailed energy in GWh if this cohort's threshold moved to 0.

    With theta_k = 0 the cohort is exposed wherever the price is negative and its
    depth becomes |p| -- deeper than the realised depth, since the realised threshold
    is minus a non-negative premium. Energy is `sum_t potential_t * w_k * r_k(|p_t|) *
    0.25 h`, linear in r.

    **Where the counterfactual asks about a (depth bin, run level) cell this cohort
    never occupied, the coefficient is clamped to its deepest occupied bin.** By
    monotonicity the true response there is at least the clamped one, so the whole
    interval returned is a LOWER bound on the counterfactual energy whenever
    `coverage < 1`. The alternative -- inventing a column for an unvisited cell --
    would report a number the data cannot support. The clamped share is returned so
    the caveat travels with the figure.
    """
    if cohort_id not in design.cohort_ids:
        return {"lam": np.zeros(design.n_cols), "defined": False, "n_qh": 0,
                "coverage": float("nan"), "note": f"cohort {cohort_id!r} absent"}
    k = design.cohort_ids.index(cohort_id)
    w = float(np.asarray(shares, dtype=float)[k])
    p = np.asarray(price, dtype=float)[design.rows]
    pot = np.asarray(potential_mw, dtype=float)[design.rows]
    neg = p < 0.0
    if not neg.any() or w <= 0:
        return {"lam": np.zeros(design.n_cols), "defined": False, "n_qh": 0,
                "coverage": float("nan"),
                "note": "no negative-price exposed quarter-hour, or zero capacity"}

    occupied_bins = sorted({j for (kk, j, m) in design.col_of if kk == k})
    if not occupied_bins:
        return {"lam": np.zeros(design.n_cols), "defined": False, "n_qh": 0,
                "coverage": float("nan"),
                "note": f"cohort {cohort_id!r} occupies no column in this arm"}
    deepest = occupied_bins[-1]

    cf_depth = np.where(neg, -p, 0.0)
    jb = _bin_of(cf_depth, design.depth_edges)
    lev = level[k, design.rows]
    lam = np.zeros(design.n_cols)
    energy_total = clamped = 0.0
    for i in np.flatnonzero(neg):
        e = float(pot[i]) * w * 0.25 / 1000.0            # MW -> GWh over a quarter-hour
        if not np.isfinite(e):
            continue
        energy_total += e
        c = _col(design, k, jb[i], lev[i])
        if c is None:
            c = _col(design, k, deepest, lev[i])
            if c is None:
                c = _col(design, k, deepest, 0)
            clamped += e
        if c is not None:
            lam[c] += e
    cov = 1.0 - (clamped / energy_total if energy_total > 0 else 1.0)
    return {"lam": lam, "defined": energy_total > 0, "n_qh": int(neg.sum()),
            "coverage": float(cov), "energy_if_full_response_gwh": float(energy_total),
            "note": ("exact" if cov >= 1.0 - 1e-12 else
                     f"LOWER BOUND: {1 - cov:.1%} of the counterfactual energy sits in "
                     f"(depth, run) cells this cohort never occupied and is clamped to "
                     f"its deepest occupied bin")}


def difference(a: dict, b: dict) -> dict:
    """L6: a - b, defined only where both are."""
    if not (a.get("defined") and b.get("defined")):
        return {"lam": np.zeros_like(a["lam"]), "defined": False, "n_qh": 0,
                "note": "one side undefined"}
    return {"lam": a["lam"] - b["lam"], "defined": True,
            "n_qh": min(a["n_qh"], b["n_qh"]), "note": ""}


def truth_value(spec: str, lam: np.ndarray, r_true_grid: np.ndarray) -> float:
    """lam' r evaluated at a known response vector (synthetic arms only)."""
    return float(np.asarray(lam, dtype=float) @ np.asarray(r_true_grid, dtype=float))
