"""Experiment 4b: the onshore fleet per control area and day, from the raw MaStR XML (docs/24).

- Units: `facts.units()` (raw XML, decommissioned units included, control area as Experiment 3
  where the processed table has it, Bundesland proxy otherwise).
- Imputation, fixed in docs/24: hub height and rotor diameter by the median of units commissioned
  in the same year (nearest year with data); coordinates by the mean of units in the same
  municipality key, else postcode, else Bundesland. Each imputed field is flagged.
- Live on day d: commissioned <= d, not finally decommissioned on or before d, and not temporarily
  shut down from a start date on or before d.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache

import numpy as np
import polars as pl

from src.method.learned_potential_v2 import config as cfg
from src.method.learned_potential_v2 import facts
from src.method.learned_potential_v2 import physics as ph


def _by_year_median(u: pl.DataFrame, col: str) -> pl.DataFrame:
    """Fill `col` by the median of the same commissioning year, else the nearest year with data."""
    u = u.with_columns(pl.col("commissioned").dt.year().alias("_y"))
    good = pl.col(col).is_not_null() & (pl.col(col) > 0)
    med = u.filter(good).group_by("_y").agg(pl.col(col).median().alias("_m")).sort("_y")
    years, vals = med["_y"].to_numpy(), med["_m"].to_numpy()
    y = u["_y"].to_numpy()
    nearest = vals[np.abs(y[:, None] - years[None, :]).argmin(axis=1)]
    imputed = ~u.select(good).to_series().to_numpy()
    return u.with_columns(
        pl.Series(col, np.where(imputed, nearest, u[col].fill_null(0.0).to_numpy())),
        pl.Series(f"{col}_imputed", imputed)).drop("_y")


def _coords(u: pl.DataFrame) -> pl.DataFrame:
    """Missing coordinates from the same municipality key, else postcode, else Bundesland."""
    has = pl.col("lon").is_not_null() & pl.col("lat").is_not_null()
    u = u.with_columns((~has).alias("coords_imputed"))
    for key in ("Gemeindeschluessel", "Postleitzahl", "Bundesland"):
        m = (u.filter(has & pl.col(key).is_not_null())
              .group_by(key).agg(pl.col("lon").mean().alias("_lon"), pl.col("lat").mean().alias("_lat")))
        u = (u.join(m, on=key, how="left")
              .with_columns(pl.coalesce("lon", "_lon").alias("lon"), pl.coalesce("lat", "_lat").alias("lat"))
              .drop("_lon", "_lat"))
    return u


@lru_cache(maxsize=1)
def fleet() -> pl.DataFrame:
    """Units live at some point in the period (or on the MaStR snapshot day), imputed, with
    specific power and rated speed."""
    snap = date(2026, 10, 31)
    lo = date.fromisoformat(cfg.PERIOD[0])
    u = facts.units().filter(
        pl.col("area").is_in(list(cfg.AREAS)) & pl.col("commissioned").is_not_null()
        & (pl.col("commissioned") <= snap)
        & (pl.col("decommissioned").is_null() | (pl.col("decommissioned") > lo)))
    u = _coords(_by_year_median(_by_year_median(u, "hub_m"), "rotor_m"))
    if u.filter(pl.col("lon").is_null() | pl.col("lat").is_null()).height:
        raise ValueError("a unit has no coordinates after imputation")
    sp = ph.specific_power(u["kw"].to_numpy(), u["rotor_m"].to_numpy())
    return u.with_columns(pl.Series("specific_power", sp),
                          pl.Series("v_rated", ph.rated_speed(sp))).select(
        "EinheitMastrNummer", "area", "area_is_proxy", "lon", "lat", "hub_m", "rotor_m", "kw",
        "commissioned", "decommissioned", "paused_from", "specific_power", "v_rated",
        "hub_m_imputed", "rotor_m_imputed", "coords_imputed")


def live(f: pl.DataFrame, d: date) -> np.ndarray:
    """Boolean per unit: live on day d."""
    return f.select(
        (pl.col("commissioned") <= d)
        & (pl.col("decommissioned").is_null() | (pl.col("decommissioned") > d))
        & (pl.col("paused_from").is_null() | (pl.col("paused_from") > d))).to_series().to_numpy()


def capacity_mw(f: pl.DataFrame, d: date) -> dict[str, float]:
    m = live(f, d)
    q = f.filter(pl.Series(m))
    return {a: float(q.filter(pl.col("area") == a)["kw"].sum() / 1000.0) for a in cfg.AREAS}


def imputation_shares(f: pl.DataFrame | None = None) -> pl.DataFrame:
    f = fleet() if f is None else f
    rows = []
    for a in (*cfg.AREAS, "all"):
        q = f if a == "all" else f.filter(pl.col("area") == a)
        kw = q["kw"].sum()
        rows.append({"area": a, "units": q.height, **{
            c: float(q.filter(pl.col(c))["kw"].sum() / kw)
            for c in ("hub_m_imputed", "rotor_m_imputed", "coords_imputed", "area_is_proxy")}})
    return pl.DataFrame(rows)
