"""Experiment 4b, Layer 1: the physical available power P_phys (docs/24).

Pure functions of weather and turbine data; no price, no G, nothing learned. Every constant is
in `config.py`:

- shear exponent from ERA5's 10 m and 100 m speeds, clipped, with a fixed fallback;
- hub-height speed by the power law from 100 m;
- air density sp / (R · t2m) and the density-equivalent speed v · (ρ / ρ0)^(1/3);
- a power curve per turbine from its specific power (rated power / rotor area): zero below
  cut-in and at or above cut-out, the cubic ramp (v³ − v_in³) / (v_r³ − v_in³) in between,
  capped at rated power, with v_r = (2 · specific power / (ρ0 · Cp))^(1/3).
"""

from __future__ import annotations

import numpy as np

from src.method.learned_potential_v2 import config as cfg


def shear_exponent(ws10: np.ndarray, ws100: np.ndarray) -> np.ndarray:
    ws10, ws100 = np.asarray(ws10, float), np.asarray(ws100, float)
    ok = (ws10 >= cfg.SHEAR_MIN_SPEED) & (ws100 >= cfg.SHEAR_MIN_SPEED)
    with np.errstate(divide="ignore", invalid="ignore"):
        a = np.log(np.where(ok, ws100, 1.0) / np.where(ok, ws10, 1.0)) / np.log(10.0)
    return np.where(ok, np.clip(a, *cfg.SHEAR_CLIP), cfg.SHEAR_FALLBACK)


def hub_speed(ws100: np.ndarray, alpha: np.ndarray, hub_m: np.ndarray) -> np.ndarray:
    return np.asarray(ws100, float) * (np.asarray(hub_m, float) / 100.0) ** np.asarray(alpha, float)


def air_density(sp_pa: np.ndarray, t2m_k: np.ndarray) -> np.ndarray:
    return np.asarray(sp_pa, float) / (cfg.R_DRY * np.asarray(t2m_k, float))


def density_equivalent(v: np.ndarray, rho: np.ndarray) -> np.ndarray:
    return np.asarray(v, float) * (np.asarray(rho, float) / cfg.RHO0) ** (1.0 / 3.0)


def specific_power(kw: np.ndarray, rotor_m: np.ndarray) -> np.ndarray:
    """W per m² of swept area."""
    return np.asarray(kw, float) * 1000.0 / (np.pi * (np.asarray(rotor_m, float) / 2.0) ** 2)


def rated_speed(sp_w_m2: np.ndarray) -> np.ndarray:
    return (2.0 * np.asarray(sp_w_m2, float) / (cfg.RHO0 * cfg.CP_DESIGN)) ** (1.0 / 3.0)


def power_curve(v: np.ndarray, v_rated: np.ndarray) -> np.ndarray:
    """Share of rated power at density-equivalent speed v; broadcasts v against v_rated."""
    v = np.asarray(v, float)
    vr = np.asarray(v_rated, float)
    ramp = (v ** 3 - cfg.CUT_IN ** 3) / (vr ** 3 - cfg.CUT_IN ** 3)
    out = np.clip(ramp, 0.0, 1.0)
    return np.where((v < cfg.CUT_IN) | (v >= cfg.CUT_OUT) | ~np.isfinite(v), 0.0, out)


def turbine_power_mw(ws100, alpha, t2m, sp, hub_m, v_rated, kw) -> dict:
    """Per turbine (rows) and hour (columns): P in MW plus the intermediate fields. `alpha` is the
    shear exponent computed on the ERA5 grid (cell and hour) and interpolated to the turbine."""
    v_hub = hub_speed(ws100, alpha, np.asarray(hub_m, float)[:, None])
    rho = air_density(sp, t2m)
    share = power_curve(density_equivalent(v_hub, rho), np.asarray(v_rated, float)[:, None])
    return {"p_mw": share * (np.asarray(kw, float)[:, None] / 1000.0), "alpha": alpha,
            "v_hub": v_hub, "rho": rho}
