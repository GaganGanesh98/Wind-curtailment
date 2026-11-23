"""Experiment 4b weather inputs: ERA5 and DWD readers, interpolation to turbines, capacity
weighting per control area (docs/24).

ERA5: one NetCDF-4 file per month (`scripts/download_era5_germany.py`), instantaneous fields at
each full UTC hour. The hour [h, h+1) takes the mean of the fields at h and h+1 (at h only when
h+1 is not on disk, which is the period's last hour). Bilinear interpolation to each turbine; a
turbine outside the grid takes the nearest edge point.

DWD: hourly station wind speed (`scripts/download_dwd_hourly_wind.py`), historical and recent
archives merged (recent wins on overlap). The time-stamp lag is fixed before any fit by
`dwd_lag_check`, which uses only ERA5 and DWD.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date, datetime, timezone
from functools import lru_cache

import numpy as np
import polars as pl
from scipy import sparse

from src.method.learned_potential_v2 import config as cfg

HOUR_MS = 3_600_000


# ------------------------------------------------------------------ ERA5
def era5_path(month: str):
    return cfg.ERA5_DIR / f"era5_de_{month.replace('-', '')}.nc"


def era5_months_on_disk() -> list[str]:
    out = []
    for p in sorted(cfg.ERA5_DIR.glob("era5_de_*.nc")):
        s = p.stem.split("_")[-1]
        out.append(f"{s[:4]}-{s[4:]}")
    return out


def read_era5(month: str) -> dict:
    """Arrays of one month: time_ms (T), lat (Y, descending), lon (X), and each variable (T, Y, X)."""
    import xarray as xr
    with xr.open_dataset(era5_path(month), engine="h5netcdf") as ds:
        missing = [v for v in cfg.ERA5_VARS if v not in ds.data_vars]
        if missing:
            raise ValueError(f"{month}: ERA5 variables {missing} missing")
        out = {v: ds[v].values.astype(np.float32) for v in cfg.ERA5_VARS}
        out["time_ms"] = (ds["valid_time"].values.astype("datetime64[ms]").astype(np.int64))
        out["lat"] = ds["latitude"].values.astype(float)
        out["lon"] = ds["longitude"].values.astype(float)
    return out


def check_era5(month: str) -> dict:
    """Grid, hours and missing values of one month (the input check before any fit)."""
    e = read_era5(month)
    y, m = map(int, month.split("-"))
    first = datetime(y, m, 1, tzinfo=timezone.utc)
    nxt = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=timezone.utc)
    want = int((nxt - first).total_seconds() // 3600)
    steps = set(np.diff(e["time_ms"]).tolist())
    return {"month": month, "hours": int(e["time_ms"].size), "hours_expected": want,
            "first_ms": int(e["time_ms"][0]), "first_expected_ms": int(first.timestamp() * 1000),
            "steps_ms": sorted(steps), "n_lat": int(e["lat"].size), "n_lon": int(e["lon"].size),
            "missing": int(sum(np.isnan(e[v]).sum() for v in cfg.ERA5_VARS)),
            "ok": (e["time_ms"].size == want and steps == {HOUR_MS}
                   and int(e["time_ms"][0]) == int(first.timestamp() * 1000)
                   and not any(np.isnan(e[v]).any() for v in cfg.ERA5_VARS))}


def bilinear(lat_grid: np.ndarray, lon_grid: np.ndarray, lat: np.ndarray, lon: np.ndarray) -> sparse.csr_matrix:
    """Sparse (points × cells) weights; cells flattened as (lat index, lon index). Points outside
    the grid are clamped to its edge."""
    la_asc = lat_grid[::-1] if lat_grid[0] > lat_grid[-1] else lat_grid
    ny, nx = lat_grid.size, lon_grid.size
    la = np.clip(lat, la_asc[0], la_asc[-1])
    lo = np.clip(lon, lon_grid[0], lon_grid[-1])
    iy = np.clip(np.searchsorted(la_asc, la) - 1, 0, ny - 2)
    ix = np.clip(np.searchsorted(lon_grid, lo) - 1, 0, nx - 2)
    ty = (la - la_asc[iy]) / (la_asc[iy + 1] - la_asc[iy])
    tx = (lo - lon_grid[ix]) / (lon_grid[ix + 1] - lon_grid[ix])
    if lat_grid[0] > lat_grid[-1]:                       # map ascending index back to file order
        iy0, iy1 = ny - 1 - iy, ny - 1 - (iy + 1)
    else:
        iy0, iy1 = iy, iy + 1
    n = lat.size
    rows = np.repeat(np.arange(n), 4)
    cols = np.stack([iy0 * nx + ix, iy0 * nx + ix + 1, iy1 * nx + ix, iy1 * nx + ix + 1], 1).ravel()
    w = np.stack([(1 - ty) * (1 - tx), (1 - ty) * tx, ty * (1 - tx), ty * tx], 1).ravel()
    return sparse.csr_matrix((w, (rows, cols)), shape=(n, ny * nx))


def hourly_fields(month: str) -> dict:
    """The month's fields averaged to hours [h, h+1): mean of h and h+1, h+1 from the next
    month's file when on disk, else h alone for the last hour."""
    e = read_era5(month)
    y, m = map(int, month.split("-"))
    nxt = f"{y + (m == 12):04d}-{m % 12 + 1:02d}"
    tail = read_era5(nxt) if era5_path(nxt).exists() else None
    out = {"time_ms": e["time_ms"], "lat": e["lat"], "lon": e["lon"]}
    for v in cfg.ERA5_VARS:
        a = e[v]
        b = np.concatenate([a[1:], (tail[v][:1] if tail is not None else a[-1:])], axis=0)
        out[v] = 0.5 * (a + b)
    return out


# ------------------------------------------------------------------ DWD
@lru_cache(maxsize=1)
def dwd_stations() -> pl.DataFrame:
    txt = (cfg.DWD_DIR / "recent" / "FF_Stundenwerte_Beschreibung_Stationen.txt").read_bytes().decode("latin-1")
    rows = []
    for line in txt.splitlines()[2:]:
        p = line.split()
        if len(p) >= 6 and p[0].isdigit():
            rows.append({"sid": int(p[0]), "lat": float(p[4]), "lon": float(p[5])})
    return pl.DataFrame(rows)


@lru_cache(maxsize=1)
def dwd_hourly() -> pl.DataFrame:
    """sid, stamp_ms (UTC, as DWD stamps it), ws (m/s; missing dropped), PERIOD ± one day."""
    lo = (date.fromisoformat(cfg.PERIOD[0])).strftime("%Y%m%d") + "00"
    hi = (date.fromisoformat(cfg.PERIOD[1])).strftime("%Y%m%d") + "23"
    frames = []
    for rank, sub in enumerate(("historical", "recent")):
        for z in sorted((cfg.DWD_DIR / sub).glob("*.zip")):
            with zipfile.ZipFile(z) as zf:
                n = next(x for x in zf.namelist() if x.startswith("produkt"))
                df = pl.read_csv(io.BytesIO(zf.read(n)), separator=";", infer_schema_length=0)
            df = df.rename({c: c.strip() for c in df.columns}).select(
                pl.col("STATIONS_ID").str.strip_chars().cast(pl.Int64).alias("sid"),
                pl.col("MESS_DATUM").str.strip_chars().alias("t"),
                pl.col("F").str.strip_chars().cast(pl.Float64).alias("ws"))
            frames.append(df.filter((pl.col("t") >= lo) & (pl.col("t") <= hi) & (pl.col("ws") >= 0))
                          .with_columns(pl.lit(rank).alias("_r")))
    a = pl.concat(frames).sort("_r").unique(["sid", "t"], keep="last")
    return a.with_columns((pl.col("t") + "00").str.to_datetime("%Y%m%d%H%M", time_zone="UTC")
                          .dt.epoch("ms").alias("stamp_ms")).select("sid", "stamp_ms", "ws")


def qualifying_stations(hourly: pl.DataFrame | None = None) -> pl.DataFrame:
    h = dwd_hourly() if hourly is None else hourly
    n_hours = ((date.fromisoformat(cfg.PERIOD[1]) - date.fromisoformat(cfg.PERIOD[0])).days + 1) * 24
    c = h.group_by("sid").agg(pl.len().alias("n")).filter(pl.col("n") / n_hours >= cfg.DWD_MIN_COVERAGE)
    return dwd_stations().join(c.select("sid"), on="sid", how="inner").sort("sid")


def nearest(st_lat, st_lon, lat, lon) -> np.ndarray:
    """Index of the nearest station for each point (equirectangular distance)."""
    k = np.cos(np.radians(51.0))
    d = (np.asarray(lat)[:, None] - np.asarray(st_lat)[None, :]) ** 2 + \
        (k * (np.asarray(lon)[:, None] - np.asarray(st_lon)[None, :])) ** 2
    return d.argmin(axis=1)


def dwd_lag_check(months: list[str]) -> pl.DataFrame:
    """Correlation of DWD speed with ERA5 10 m speed at each qualifying station, for DWD stamp
    lag 0 (stamp = hour start) and 1 (stamp = hour end), pooled over the given ERA5 months."""
    st = qualifying_stations()
    h = dwd_hourly()
    out = []
    for lag in (0, 1):
        xs, ys = [], []
        for month in months:
            e = hourly_fields(month)
            W = bilinear(e["lat"], e["lon"], st["lat"].to_numpy(), st["lon"].to_numpy())
            ws10 = np.hypot(e["u10"], e["v10"]).reshape(e["time_ms"].size, -1)
            at = (W @ ws10.T)                                    # stations × hours
            grid = pl.DataFrame({"sid": np.repeat(st["sid"].to_numpy(), e["time_ms"].size),
                                 "hour_ms": np.tile(e["time_ms"], st.height),
                                 "era5": at.ravel()})
            d = h.with_columns((pl.col("stamp_ms") - lag * HOUR_MS).alias("hour_ms"))
            j = grid.join(d, on=["sid", "hour_ms"], how="inner")
            xs.append(j["era5"].to_numpy()); ys.append(j["ws"].to_numpy())
        x, y = np.concatenate(xs), np.concatenate(ys)
        out.append({"lag_h": lag, "n": int(x.size), "corr": float(np.corrcoef(x, y)[0, 1])})
    return pl.DataFrame(out)


# ------------------------------------------------------------------ area aggregation
def area_month(month: str, fleet: pl.DataFrame, dwd_lag_h: int) -> pl.DataFrame:
    """Per area and hour of the month: P_phys, C and every allowed weather input."""
    from src.method.learned_potential_v2 import fleet as fl
    from src.method.learned_potential_v2 import physics as ph
    e = hourly_fields(month)
    T = e["time_ms"].size
    grid = {v: e[v].reshape(T, -1) for v in cfg.ERA5_VARS}
    grid["alpha"] = ph.shear_exponent(np.hypot(grid["u10"], grid["v10"]), np.hypot(grid["u100"], grid["v100"]))
    W = bilinear(e["lat"], e["lon"], fleet["lat"].to_numpy(), fleet["lon"].to_numpy())
    kw = fleet["kw"].to_numpy()
    hub, vr = fleet["hub_m"].to_numpy(), fleet["v_rated"].to_numpy()
    areas = fleet["area"].to_numpy()
    commissioned = fleet["commissioned"].to_numpy()
    st = qualifying_stations()
    s_idx = nearest(st["lat"].to_numpy(), st["lon"].to_numpy(), fleet["lat"].to_numpy(), fleet["lon"].to_numpy())
    D = dwd_matrix(st, e["time_ms"], dwd_lag_h)                 # stations × hours
    days = e["time_ms"] // (24 * HOUR_MS)
    rows = []
    for day in np.unique(days):
        d = datetime.fromtimestamp(int(day) * 86400, timezone.utc).date()
        cols = np.flatnonzero(days == day)
        f = {v: W @ grid[v][cols].T for v in (*cfg.ERA5_VARS, "alpha")}   # turbines × day's hours
        ws100, ws10 = np.hypot(f["u100"], f["v100"]), np.hypot(f["u10"], f["v10"])
        tp = ph.turbine_power_mw(ws100, f["alpha"], f["t2m"], f["sp"], hub, vr, kw)
        alive = fl.live(fleet, d)
        new = alive & (commissioned > np.datetime64(d) - np.timedelta64(cfg.NEW_CAPACITY_DAYS, "D"))
        for a in cfg.AREAS:
            m = alive & (areas == a)
            w = kw[m]
            C = w.sum() / 1000.0
            wm = lambda x: (w @ x[m]) / w.sum()
            su, sv = wm(f["u100"]), wm(f["v100"])
            st_w = np.bincount(s_idx[m], weights=w, minlength=st.height)
            Dm = D[:, cols]
            ok = ~np.isnan(Dm)
            den = ok.T.astype(float) @ st_w
            dws = np.where(den > 0, np.where(ok, Dm, 0.0).T @ st_w / np.maximum(den, 1e-12), np.nan)
            feats = {"p_phys_mw": tp["p_mw"][m].sum(0),
                     "era5_ws100": wm(ws100), "era5_ws_hub": wm(tp["v_hub"]),
                     "era5_dir_sin": su / np.maximum(np.hypot(su, sv), 1e-9),
                     "era5_dir_cos": sv / np.maximum(np.hypot(su, sv), 1e-9),
                     "era5_rho": wm(tp["rho"]), "era5_gust": wm(f["i10fg"]),
                     "era5_gust_ratio": wm(f["i10fg"] / np.maximum(ws10, cfg.SHEAR_MIN_SPEED)),
                     "era5_shear": wm(f["alpha"]), "era5_t2m": wm(f["t2m"]), "dwd_ws": dws}
            share_new = float(kw[new & (areas == a)].sum() / 1000.0 / C)
            for k, c in enumerate(cols):
                rows.append({"area": a, "hour_ms": int(e["time_ms"][c]), "c_mw": C,
                             "new_cap_share": share_new, **{n: float(v[k]) for n, v in feats.items()}})
    return pl.DataFrame(rows).with_columns((pl.col("p_phys_mw") / pl.col("c_mw")).alias("p_phys_cf"))


def dwd_matrix(st: pl.DataFrame, hours_ms: np.ndarray, lag_h: int) -> np.ndarray:
    """Stations × hours of DWD speed for the hours [h, h+1) given, NaN where missing. A DWD value
    stamped s belongs to the hour starting s − lag_h."""
    dw = (dwd_hourly().with_columns((pl.col("stamp_ms") - lag_h * HOUR_MS).alias("hour_ms"))
          .filter(pl.col("hour_ms").is_between(int(hours_ms[0]), int(hours_ms[-1]))
                  & pl.col("sid").is_in(st["sid"].implode())))
    D = np.full((st.height, hours_ms.size), np.nan)
    si = {s: i for i, s in enumerate(st["sid"].to_list())}
    ti = {t: i for i, t in enumerate(hours_ms.tolist())}
    for s, t, v in dw.select("sid", "hour_ms", "ws").iter_rows():
        j = ti.get(t)
        if j is not None:
            D[si[s], j] = v
    return D
