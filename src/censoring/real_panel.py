"""Real-data adapter: the German panel in the shape the M2 code already consumes.

    from src.censoring.real_panel import build_real_panel
    data = build_real_panel(area="DE", start="2024-01-01", end="2026-09-30")

WHY THIS EXISTS
---------------
`fit_m2`, `fit_shared_stage_a` and the baselines were written against the synthetic
generator, but they do not need the synthetic *truth*. `fit_m2` reads exactly eight
things off `data`:

    real_berlin_date, real_hour, forecast_mw, g_obs_mw, price_eur_mwh,
    depth, s, cohorts.shares

none of which is `a_true_mw`, `c_true` or `r_true`. So the real panel can be presented
through the same interface, and T-D and T-E can run the registered estimator
unmodified rather than a re-implementation of it. Before this module, M2 had never
been fitted on real data: `fit_m2` appeared only in the synthetic path and in tests.

The three truth fields are present and set to `None`. Anything that reaches for them
gets an explicit error naming the field, never a silent zero — on real data there is
no true available power and no true response, which is the entire problem the thesis
is about.

ONSHORE ONLY, DELIBERATELY
--------------------------
`forecast_mw` is `da_onshore_mw` and `g_obs_mw` is `act_onshore_mw`. The cohort shares
come from the MaStR **onshore** snapshot (30,440 units), so pairing them with a
wind total that includes offshore would weight an onshore response by a mixed-fleet
capacity. `include_offshore=True` is available for diagnostics and is not the default.

THE MARKET VALUE VARIES BY MONTH -- AND THAT CHANGES THETA
----------------------------------------------------------
`theta_and_exposure` takes ONE market value for the whole series. Over 2024-01..2026-10
the monthly market value moves a long way, and theta is minus the market premium
`max(0, AW - MV)`, so a single scalar would put every cohort at the wrong threshold in
most months -- including collapsing them all to theta = 0 in months where it happens to
exceed AW, which is exactly the identification question T-D(iii) asks about.

So the clock is built ONCE on the full contiguous series -- run lengths must be allowed
to cross month boundaries, or the s.51 trigger is wrong at every boundary -- and
`theta_and_exposure` is then called per month, with only that month's columns copied
into the output. The registered function is not modified.

`mode="T1"` uses the PUBLISHED Netztransparenz monthly series (`Monatsmarktwerte_*.csv`),
which is correct for an ex-post structural check and wrong for a forecast: it is
released after the month ends. `mode="T2"` uses `mv_t2_daily.parquet`, the month-to-date
value knowable by D-1. Rule 17. T-D is T1; T-E is T2.

UNITS
-----
`Monatsmarktwerte_*.csv` is in **ct/kWh** (its own first header cell says so). EUR/MWh
is ten times that. The conversion is applied once, here, and asserted against a sanity
band rather than trusted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from src.method.exposure import (
    build_clock_features,
    mastr_cohort_set,
    theta_and_exposure,
)

BERLIN = ZoneInfo("Europe/Berlin")
REPO_ROOT = Path(__file__).resolve().parents[2]
PANEL_PATH = REPO_ROOT / "data" / "processed" / "panel_qh.parquet"
MV_T2_PATH = REPO_ROOT / "data" / "processed" / "mv_t2_daily.parquet"
RAW_NT = REPO_ROOT / "data" / "raw" / "netztransparenz"

MV_ROW = "MW Wind an Land"          # Marktwert Wind onshore, ct/kWh
MONTHS_DE = {"Jan": 1, "Feb": 2, "Mär": 3, "Mrz": 3, "Apr": 4, "Mai": 5, "Jun": 6,
             "Jul": 7, "Aug": 8, "Sep": 9, "Okt": 10, "Nov": 11, "Dez": 12}
# A published monthly onshore market value outside this band means the file changed
# shape or the units moved; fail rather than propagate it into theta.
MV_SANITY_EUR_MWH = (0.0, 250.0)

SAFE_PRICE_FLOOR = 5.0              # matches SyntheticConfig.safe_price_floor


class _Missing:
    """Stands in for the synthetic truth. Raises on any attempt to use it."""

    __slots__ = ("name",)

    def __init__(self, name: str):
        self.name = name

    def _die(self, *_a, **_k):
        raise AttributeError(
            f"{self.name} does not exist on real data. On the real panel there is no "
            f"true available power and no true response -- that is the problem the "
            f"thesis is about. Any metric that needs {self.name} is a synthetic-only "
            f"metric and must not be reported on real data."
        )

    __array__ = __getitem__ = __len__ = __iter__ = _die
    __bool__ = _die


# ------------------------------------------------------------------ market value


def _read_semicolon(path: Path) -> tuple[list[str], dict[str, list[str]]]:
    raw = path.read_text(encoding="utf-8-sig").splitlines()
    rows = [ln.split(";") for ln in raw if ln.strip()]
    header = [c.strip() for c in rows[0]]
    body = {r[0].strip(): [c.strip() for c in r[1:]] for r in rows[1:] if r}
    return header, body


def _num_de(cell: str) -> float | None:
    """German decimal comma, optional thousands dot."""
    c = cell.strip()
    if not c or c in ("-", "n/a", "N/A"):
        return None
    c = c.replace(".", "").replace(",", ".") if "," in c else c
    try:
        return float(c)
    except ValueError:
        return None


def load_published_monthly_mv() -> dict[tuple[int, int], float]:
    """{(year, month): onshore market value in EUR/MWh} from Netztransparenz.

    The year comes from the HEADER CELLS, never the filename.
    """
    out: dict[tuple[int, int], float] = {}
    paths = sorted(RAW_NT.glob("Monatsmarktwerte_*.csv"))
    if not paths:
        raise FileNotFoundError(f"no Monatsmarktwerte_*.csv under {RAW_NT}")
    for path in paths:
        header, body = _read_semicolon(path)
        if MV_ROW not in body:
            raise ValueError(f"{path.name}: no {MV_ROW!r} row; rows are "
                             f"{sorted(body)[:12]}")
        for cell, val in zip(header[1:], body[MV_ROW]):
            mon, _, yr = cell.partition(" ")
            if mon not in MONTHS_DE:
                raise ValueError(f"{path.name}: unparsable month column {cell!r}")
            ct_kwh = _num_de(val)
            if ct_kwh is None:                       # future months are blank
                continue
            eur_mwh = ct_kwh * 10.0
            lo, hi = MV_SANITY_EUR_MWH
            if not (lo <= eur_mwh <= hi):
                raise ValueError(
                    f"{path.name} {cell}: onshore MV {eur_mwh:.2f} EUR/MWh is outside "
                    f"{MV_SANITY_EUR_MWH}; check the units row of the file")
            out[(int(yr), MONTHS_DE[mon])] = eur_mwh
    return out


def load_t2_monthly_mv() -> dict[tuple[int, int], float]:
    """Month-to-date market value knowable by D-1, from `mv_t2_daily.parquet`.

    One value per (year, month): the LAST daily value of that month, which is the
    most complete month-to-date figure available without using post-month data.
    """
    if not MV_T2_PATH.exists():
        raise FileNotFoundError(
            f"{MV_T2_PATH} missing. mode='T2' needs the D-1 month-to-date series; "
            f"rebuild it or use mode='T1' for an ex-post check.")
    df = (pl.read_parquet(MV_T2_PATH)
            .sort("d")
            .group_by(["year", "month"])
            .agg(pl.col("mv_t2_known_by_d_minus_1").last().alias("mv")))
    return {(int(r["year"]), int(r["month"])): float(r["mv"])
            for r in df.iter_rows(named=True) if r["mv"] is not None}


# -------------------------------------------------------------------- the panel


def _year_month(bdate: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(year, month) from the panel's ISO-8601 `berlin_date` strings.

    The column is stored as text, not as a date, so this slices rather than
    attribute-accesses. Fails loudly on anything that is not `YYYY-MM-DD`.
    """
    d = np.asarray(bdate).astype(str)
    bad = [x for x in d[:1] if len(x) != 10 or x[4] != "-" or x[7] != "-"]
    if bad:
        raise ValueError(f"berlin_date is not ISO-8601 YYYY-MM-DD: {bad[0]!r}")
    years = np.array([int(x[:4]) for x in d], dtype=int)
    months = np.array([int(x[5:7]) for x in d], dtype=int)
    return years, months


@dataclass
class RealConfig:
    """The slice of `SyntheticConfig` that the shared code actually reads."""
    area: str = "DE"
    safe_price_floor: float = SAFE_PRICE_FLOOR
    mv_mode: str = "T1"
    include_offshore: bool = False
    start: str = ""
    end: str = ""


@dataclass
class RealPanel:
    """The real panel, duck-typed to what `fit_m2` and stage A consume.

    Truth fields exist and refuse to be used. Everything else is real.
    """
    config: RealConfig
    cohorts: object
    ts_utc_ns: np.ndarray
    berlin_date: np.ndarray
    real_berlin_date: np.ndarray
    real_hour: np.ndarray
    forecast_mw: np.ndarray
    price_eur_mwh: np.ndarray
    theta: np.ndarray
    s: np.ndarray
    depth: np.ndarray
    g_obs_mw: np.ndarray
    weather_ms: np.ndarray | None
    mv_by_month: dict
    diagnostics: dict = field(default_factory=dict)

    a_true_mw = _Missing("a_true_mw")
    c_true = _Missing("c_true")
    r_true = _Missing("r_true")

    @property
    def censored(self):
        raise AttributeError(
            "`censored` is a synthetic field (c_true > 0) and has no real-data "
            "counterpart -- whether a quarter-hour was curtailed is the unknown. Use "
            "`exposed_any` for the legal exposure mask, or `price_eur_mwh < 0`.")

    @property
    def exposed_any(self) -> np.ndarray:
        return self.s.max(axis=0) > 0.0

    def __len__(self) -> int:
        return int(self.price_eur_mwh.size)


def build_real_panel(area: str = "DE", start: str = "2024-01-01",
                     end: str = "2026-09-30", mode: str = "T1",
                     include_offshore: bool = False,
                     panel_path: Path = PANEL_PATH) -> RealPanel:
    """Load the panel for one control area and attach theta, exposure and depth.

    `start`/`end` are inclusive Berlin calendar dates. `mode` is "T1" (published
    monthly market value, ex post) or "T2" (month-to-date, knowable by D-1).
    """
    if mode not in ("T1", "T2"):
        raise ValueError(f"mode must be 'T1' or 'T2', got {mode!r}")
    if not panel_path.exists():
        raise FileNotFoundError(f"{panel_path} missing; rebuild the panel first")

    # `berlin_date` is an ISO-8601 STRING column in the panel, so lexicographic
    # comparison is calendar comparison. Parsed first anyway, to reject a malformed
    # bound rather than silently selecting nothing.
    d0 = datetime.strptime(start, "%Y-%m-%d").date()
    d1 = datetime.strptime(end, "%Y-%m-%d").date()
    if d1 < d0:
        raise ValueError(f"end {end} precedes start {start}")
    df = (pl.read_parquet(panel_path)
            .filter(pl.col("area") == area)
            .filter((pl.col("berlin_date") >= d0.isoformat())
                    & (pl.col("berlin_date") <= d1.isoformat()))
            .sort("ts_utc"))
    if df.height == 0:
        raise ValueError(f"no rows for area={area!r} between {start} and {end}")

    fc_col = "da_wind_mw" if include_offshore else "da_onshore_mw"
    g_col = "act_wind_mw" if include_offshore else "act_onshore_mw"
    for col in (fc_col, g_col, "price_eur_mwh", "ts_utc", "berlin_date"):
        if col not in df.columns:
            raise ValueError(f"panel has no column {col!r}; columns are {df.columns}")

    ts_ms = df["ts_utc"].to_numpy().astype("int64")
    step = np.unique(np.diff(ts_ms))
    if step.size != 1 or step[0] != 15 * 60 * 1000:
        raise ValueError(
            f"panel is not a contiguous 15-minute series for area={area!r}: "
            f"observed step(s) {step[:5].tolist()} ms. The s.51 run-length clock is "
            f"only defined on a contiguous series, so this must be fixed upstream "
            f"rather than interpolated here.")
    ts_ns = ts_ms * 1_000_000

    price = df["price_eur_mwh"].to_numpy().astype(float)
    forecast = df[fc_col].to_numpy().astype(float)
    g_obs = df[g_col].to_numpy().astype(float)
    bdate = df["berlin_date"].to_numpy()

    hour = np.array([datetime.fromtimestamp(t / 1000, tz=BERLIN).hour for t in ts_ms],
                    dtype=int)

    for name, arr in (("price", price), (fc_col, forecast), (g_col, g_obs)):
        n_nan = int(np.isnan(arr).sum())
        if n_nan:
            raise ValueError(
                f"{name} has {n_nan} missing values in {area} {start}..{end}. Hard "
                f"rule: do not fill these silently -- a gap in price moves the trigger "
                f"clock and a gap in output moves stage A.")

    # ---- theta per month, on one clock built over the whole contiguous series
    cohorts = mastr_cohort_set(area)
    clock = build_clock_features(ts_ns, price)
    mv_by_month = (load_published_monthly_mv() if mode == "T1"
                   else load_t2_monthly_mv())

    years, months = _year_month(bdate)
    k, n = len(cohorts), price.size
    theta = np.zeros((k, n), dtype=float)
    s = np.zeros((k, n), dtype=float)
    depth = np.zeros((k, n), dtype=float)

    present = sorted({(int(y), int(m)) for y, m in zip(years, months)})
    missing = [ym for ym in present if ym not in mv_by_month]
    if missing:
        raise ValueError(
            f"mode={mode}: no market value for {missing}. theta is minus the market "
            f"premium, so a missing month cannot be defaulted -- it would silently set "
            f"those cohorts to theta = 0 and manufacture exposure. Obtain that month's "
            f"value or narrow the date range.")

    for ym in present:
        sel = (years == ym[0]) & (months == ym[1])
        th_m, s_m, dp_m = theta_and_exposure(cohorts, clock, mv_by_month[ym])
        theta[:, sel] = th_m[:, sel]
        s[:, sel] = s_m[:, sel]
        depth[:, sel] = dp_m[:, sel]

    cfg = RealConfig(area=area, mv_mode=mode, include_offshore=include_offshore,
                     start=start, end=end)
    diagnostics = {
        "n_qh": int(n),
        "n_cohorts": int(k),
        "n_months": len(present),
        "n_negative_price_qh": int((price < 0).sum()),
        "n_exposed_qh": int((s.max(axis=0) > 0).sum()),
        "n_exposed_days": int(np.unique(bdate[s.max(axis=0) > 0]).size),
        "mv_min_eur_mwh": min(mv_by_month[ym] for ym in present),
        "mv_max_eur_mwh": max(mv_by_month[ym] for ym in present),
        "forecast_col": fc_col,
        "g_obs_col": g_col,
    }
    return RealPanel(
        config=cfg, cohorts=cohorts, ts_utc_ns=ts_ns, berlin_date=bdate,
        real_berlin_date=bdate, real_hour=hour, forecast_mw=forecast,
        price_eur_mwh=price, theta=theta, s=s, depth=depth, g_obs_mw=g_obs,
        weather_ms=None, mv_by_month={str(k_): v for k_, v in mv_by_month.items()},
        diagnostics=diagnostics,
    )


def identifying_months(panel: RealPanel) -> list[dict]:
    """Per month: the rank of the exposure design and how many cohorts separate.

    T-D(iii). Two cohorts are separable only where their (s, depth) columns differ;
    identical columns are collinear and only their capacity-weighted average is
    recoverable. With MV >= AW for every cohort the premium is zero everywhere, every
    theta collapses to 0, and the design has rank 1 -- one fleet response, no hierarchy.
    """
    years, months = _year_month(panel.berlin_date)
    out = []
    for ym in sorted({(int(y), int(m)) for y, m in zip(years, months)}):
        sel = (years == ym[0]) & (months == ym[1])
        s_m, d_m = panel.s[:, sel], panel.depth[:, sel]
        exposed = s_m.max(axis=1) > 0
        # Rank of the stacked exposure/depth design for this month.
        rank = int(np.linalg.matrix_rank(np.vstack([s_m, d_m]))) if sel.sum() else 0
        # One signature per COHORT: cohorts sharing a signature are collinear, so only
        # their capacity-weighted average is recoverable. This is what pool_blocks sees.
        cohort_sig = {tuple(np.concatenate([s_m[i], d_m[i]]))
                      for i in range(s_m.shape[0])}
        out.append(dict(
            year=ym[0], month=ym[1], n_qh=int(sel.sum()),
            mv_eur_mwh=panel.mv_by_month.get(str(ym)),
            n_cohorts_exposed=int(exposed.sum()),
            n_separable_cohorts=len(cohort_sig),
            design_rank=rank,
            identified=bool(len(cohort_sig) > 1 and exposed.sum() > 1),
        ))
    return out
