"""Functionals for the post-hoc Hirth audit (docs/22 and its Amendment 1, 23 Nov 2026).

New file: `functionals.py` and λ₁ to λ₇ are not changed. Every functional here is a fixed
coefficient vector `lam` over the response grid, so `lam @ r` is linear in r and the existing
`bounds.identified_set` bounds it.

On the design rows, the row sum of X is the exposed share e_t = Σ_k w_k s_kt, because each row
holds w_k s_kt in the column of cohort k's (depth bin, run level). So e needs no extra input.

- curtailment rate, unweighted: `functionals.band_mean` itself (used directly, not copied).
- curtailment rate, weighted:   Σ_t w_t X_t / Σ_t w_t over the band.
- response rate:                Σ_t w_t X_t / Σ_t w_t e_t over the band (w_t = 1 unweighted).
- exposure rate:                Σ_t w_t e_t / Σ_t w_t, a plain number.

The weights are H per quarter-hour. A constant multiplicative bias scales every weight by the
same factor, which cancels in each ratio.
"""

from __future__ import annotations

import numpy as np

from src.method import functionals as fx
from src.method.bounds import BoundsDesign


def _band(design: BoundsDesign, price: np.ndarray, lo: float, hi: float) -> np.ndarray:
    p = np.asarray(price, dtype=float)[design.rows]
    return (p > lo) & (p <= hi)


def _weights(design: BoundsDesign, weight: np.ndarray | None) -> np.ndarray:
    if weight is None:
        return np.ones(design.rows.size)
    w = np.asarray(weight, dtype=float)[design.rows]
    if not np.all(np.isfinite(w)) or np.any(w <= 0):
        raise ValueError("weights must be finite and positive on every design row")
    return w


def exposed_share(design: BoundsDesign) -> np.ndarray:
    """e_t on the design rows."""
    return design.X.sum(axis=1)


def _undefined(design: BoundsDesign, note: str) -> dict:
    return {"lam": np.zeros(design.n_cols), "n_qh": 0, "defined": False, "note": note}


def curtailment(design: BoundsDesign, price: np.ndarray, lo: float, hi: float,
                weight: np.ndarray | None = None) -> dict:
    """Band mean of c; unweighted it is `functionals.band_mean` exactly."""
    if weight is None:
        return fx.band_mean(design, price, lo, hi)
    m = _band(design, price, lo, hi)
    if not m.any():
        return _undefined(design, f"no exposed quarter-hour with price in ({lo}, {hi}]")
    w = _weights(design, weight)[m]
    return {"lam": (w[:, None] * design.X[m]).sum(axis=0) / w.sum(), "n_qh": int(m.sum()),
            "defined": True, "note": "weighted by H"}


def response(design: BoundsDesign, price: np.ndarray, lo: float, hi: float,
             weight: np.ndarray | None = None) -> dict:
    """Band mean of c divided by the band mean of e (both weighted alike)."""
    m = _band(design, price, lo, hi)
    if not m.any():
        return _undefined(design, f"no exposed quarter-hour with price in ({lo}, {hi}]")
    w = _weights(design, weight)[m]
    den = float((w * exposed_share(design)[m]).sum())
    if den <= 0:
        return _undefined(design, "zero exposed share in the band")
    return {"lam": (w[:, None] * design.X[m]).sum(axis=0) / den, "n_qh": int(m.sum()),
            "defined": True, "note": "weighted by H" if weight is not None else ""}


def exposure(design: BoundsDesign, price: np.ndarray, lo: float, hi: float,
             weight: np.ndarray | None = None) -> dict:
    """Band mean of e: a plain number, no identified set."""
    m = _band(design, price, lo, hi)
    if not m.any():
        return {"value": float("nan"), "n_qh": 0, "defined": False}
    w = _weights(design, weight)[m]
    return {"value": float((w * exposed_share(design)[m]).sum() / w.sum()),
            "n_qh": int(m.sum()), "defined": True}
