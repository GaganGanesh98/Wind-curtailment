"""Switch-off thresholds theta_k,t and exposure s_k,t from the EEG rule table.

Spec: `docs/06_pivot_mechanism_aware_censoring.md` section 3 (v1.5).
Rule source: `data/reference/eeg_negative_price_rules.csv` + `docs/05_eeg_rule_table.md`.

The statutory facts below are already verified from the consolidated texts and are
implemented, not re-derived (CLAUDE_CODE_PROMPT.md, Phase 2):

1. **Two price clocks run at once.** Cohorts under the rule in force from 25 Feb 2025
   (R09) are judged per *quarter-hour* on the quarter-hour price. Every older,
   hour-based cohort is judged per *calendar hour* on the arithmetic mean of that
   hour's four quarter-hour prices (section 100(45) EEG 2023), and then on the run
   length of consecutive such hours. A quarter-hour at -10 EUR/MWh inside an hour
   averaging +5 EUR/MWh triggers one cohort and not the other.

2. **The staircase steps by the CALENDAR YEAR in which prices are negative**, not by
   the plant's commissioning year. Section 51(1) reads "Wenn der Spotmarktpreis
   [im Jahr X] ... negativ ist" -- the year qualifies the price condition. The
   commissioning date decides only which *version* of section 51 applies
   (section 100(46)). The 2023 - Feb 2025 cohort therefore steps 4 h (2023) ->
   3 h (2024, 2025) -> 2 h (2026) -> 1 h (2027+), the same for every plant in it.
   The year is the **Berlin-local** calendar year.

3. **The consequence covers the whole uninterrupted negative period.** Once a run of
   consecutive negative hours reaches the cohort's threshold, every hour of that
   maximal run is triggered, including the hours before the threshold was reached.

4. **Size exemptions are part of the rule.** A cohort below its size threshold never
   triggers, so theta stays at the market-premium value instead of dropping to 0.
   Same for pilot wind (exempt in every version before 25 Feb 2025, none after) and
   for plants commissioned before 1 Jan 2016 (section 24(3) no. 1 EEG 2014).

5. **Section 51a does not enter theta.** It is compensation after the fact (the support
   period is extended), so it does not change the within-quarter-hour incentive.

Two-cohort mode (rule 18 / spec section 3 I4) **pools the response, not the exposure**:
s_k,t and the depth below theta stay per legal cohort; only the response *parameters*
are shared across the cohorts of a macro-cohort. That is strictly stronger than
aggregating exposure into a macro share, and it is exact rather than approximate --
aggregating would force one depth per macro-cohort, which is only correct when every
cohort in it happens to share a threshold. The aggregated share is still computed, for
reporting, by `macro_exposed_share`.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence
from datetime import timezone
from zoneinfo import ZoneInfo

import numpy as np

BERLIN = ZoneInfo("Europe/Berlin")

REPO_ROOT = Path(__file__).resolve().parents[2]
RULE_TABLE_PATH = REPO_ROOT / "data" / "reference" / "eeg_negative_price_rules.csv"

QH_CLOCK = "quarterhour"
HOUR_CLOCK = "hour"
VALID_CLOCKS = (QH_CLOCK, HOUR_CLOCK)

# Macro-cohorts for the rule-18 fallback.
MACRO_QH = "qh_clock"
MACRO_HOUR = "hour_clock"

# The staircase of section 51(1) nos. 1-4 EEG 2023 (rows R05-R08), keyed by the
# calendar year in which the prices are negative. Read straight off the rule table.
STAIRCASE_BY_YEAR: dict[int, int] = {2023: 4, 2024: 3, 2025: 3, 2026: 2}
STAIRCASE_FROM_2027 = 1


def staircase_run_length(year: int) -> int:
    """Run-length threshold in hours for the 2023 - Feb 2025 cohort, by calendar year."""
    if year >= 2027:
        return STAIRCASE_FROM_2027
    if year not in STAIRCASE_BY_YEAR:
        raise ValueError(
            f"No staircase step recorded for calendar year {year}. "
            f"Known: {sorted(STAIRCASE_BY_YEAR)} plus 2027+. "
            "Check data/reference/eeg_negative_price_rules.csv rows R05-R08."
        )
    return STAIRCASE_BY_YEAR[year]


@dataclass(frozen=True)
class Cohort:
    """One plant cohort: a row of the rule table plus its fleet share and award value.

    Attributes
    ----------
    cohort_id : short name used in results tables.
    rule_id : the row of `eeg_negative_price_rules.csv` this cohort follows. Validated
        on construction of a `CohortSet`; an unknown id raises (hard rule 12).
    clock : QH_CLOCK or HOUR_CLOCK.
    run_length_h : hours of consecutive negative periods needed to trigger. An int for
        a fixed threshold, the string "staircase" for the year-dependent section 51(1)
        nos. 1-4 ladder, or None when the cohort never triggers.
    subject_to_s51 : False for cohorts the reduction never reaches (pre-2016 plants,
        pilot wind, size-exempt cohorts). Their theta is the market premium throughout.
    in_support : False once the EEG support period has ended. theta = 0 regardless of
        any trigger, because there is no premium left to lose.
    aw_eur_mwh : award value (anzulegender Wert). PLACEHOLDER in Phase 2 -- real values
        come from MaStR and the tender results in Phase 3 (rule 19: a range, run at
        three settings). None is only valid when in_support is False.
    capacity_share : share of fleet capacity, w_k. Shares across a CohortSet must sum
        to 1.
    macro : MACRO_QH or MACRO_HOUR, used by the two-cohort fallback.
    """

    cohort_id: str
    rule_id: str
    clock: str
    run_length_h: int | str | None
    subject_to_s51: bool
    in_support: bool
    aw_eur_mwh: float | None
    capacity_share: float
    macro: str
    note: str = ""

    def __post_init__(self) -> None:
        if self.clock not in VALID_CLOCKS:
            raise ValueError(f"{self.cohort_id}: clock {self.clock!r} not in {VALID_CLOCKS}")
        if self.macro not in (MACRO_QH, MACRO_HOUR):
            raise ValueError(f"{self.cohort_id}: macro {self.macro!r} unknown")
        if self.subject_to_s51 and self.run_length_h is None and self.clock == HOUR_CLOCK:
            raise ValueError(
                f"{self.cohort_id}: an hour-clock cohort subject to section 51 needs a "
                "run_length_h (int or 'staircase')"
            )
        if self.in_support and self.aw_eur_mwh is None:
            raise ValueError(
                f"{self.cohort_id}: a cohort still in support needs an award value "
                "(placeholder is fine in Phase 2, but it must be stated)"
            )

    def run_length_for_year(self, year: int) -> int | None:
        if self.run_length_h is None:
            return None
        if self.run_length_h == "staircase":
            return staircase_run_length(year)
        return int(self.run_length_h)


@dataclass
class CohortSet:
    """A set of cohorts whose capacity shares sum to 1, validated against the rule table."""

    cohorts: Sequence[Cohort]
    rule_table_path: Path = RULE_TABLE_PATH
    _known_rule_ids: set[str] = field(default_factory=set, repr=False)

    def __post_init__(self) -> None:
        self._known_rule_ids = load_rule_ids(self.rule_table_path)
        unknown = [c.rule_id for c in self.cohorts if c.rule_id not in self._known_rule_ids]
        if unknown:
            # Hard rule 12: fail loudly on an unmapped categorical value, never drop it.
            raise ValueError(
                f"Unknown rule_id(s) {sorted(set(unknown))} -- not in "
                f"{self.rule_table_path}. Known ids: {sorted(self._known_rule_ids)}"
            )
        ids = [c.cohort_id for c in self.cohorts]
        if len(set(ids)) != len(ids):
            raise ValueError(f"Duplicate cohort_id in {ids}")
        total = sum(c.capacity_share for c in self.cohorts)
        if not np.isclose(total, 1.0, atol=1e-9):
            raise ValueError(f"Capacity shares sum to {total!r}, expected 1.0")

    def __len__(self) -> int:
        return len(self.cohorts)

    def __iter__(self):
        return iter(self.cohorts)

    @property
    def ids(self) -> list[str]:
        return [c.cohort_id for c in self.cohorts]

    @property
    def shares(self) -> np.ndarray:
        return np.array([c.capacity_share for c in self.cohorts], dtype=float)

    @property
    def macros(self) -> list[str]:
        return [c.macro for c in self.cohorts]

    def macro_index(self) -> np.ndarray:
        """Index of each cohort's macro-cohort, for parameter tying in two-cohort mode."""
        order = [MACRO_QH, MACRO_HOUR]
        return np.array([order.index(c.macro) for c in self.cohorts], dtype=int)


def load_rule_ids(path: Path = RULE_TABLE_PATH) -> set[str]:
    """Rule ids present in the EEG rule table. Raises if the table is missing."""
    if not path.exists():
        raise FileNotFoundError(f"EEG rule table not found at {path}")
    with open(path, newline="", encoding="utf-8") as fh:
        return {row["rule_id"] for row in csv.DictReader(fh)}


# --------------------------------------------------------------------------- clocks


@dataclass(frozen=True)
class ClockFeatures:
    """Everything the rules need from the price series, on both clocks.

    hour_index : for each quarter-hour, the index of the calendar hour it belongs to.
    hour_mean_price : the arithmetic mean of that hour's quarter-hour prices,
        broadcast back to each quarter-hour (section 100(45) EEG 2023).
    hour_run_length : length in hours of the maximal run of consecutive negative
        hours the quarter-hour's calendar hour belongs to; 0 if that hour is not
        negative on the hourly clock.
    qh_run_length : length in quarter-hours of the maximal run of consecutive
        negative quarter-hours this quarter-hour belongs to; 0 if not negative.
    berlin_year : Berlin-local calendar year, which is what the staircase keys on.
    """

    price_qh: np.ndarray
    hour_index: np.ndarray
    hour_mean_price: np.ndarray
    hour_run_length: np.ndarray
    qh_run_length: np.ndarray
    berlin_year: np.ndarray


def _maximal_run_lengths(flag: np.ndarray) -> np.ndarray:
    """For each True element, the length of the maximal True run containing it.

    False elements get 0. This is what "the whole uninterrupted negative period"
    means: an hour three hours into a six-hour run is part of a run of six, and so
    are the first two hours.
    """
    flag = np.asarray(flag, dtype=bool)
    out = np.zeros(flag.shape, dtype=int)
    if flag.size == 0:
        return out
    # Boundaries of runs of equal value.
    change = np.flatnonzero(np.diff(flag.astype(np.int8))) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change, [flag.size]))
    for s, e in zip(starts, ends):
        if flag[s]:
            out[s:e] = e - s
    return out


def build_clock_features(ts_utc_ns: np.ndarray, price_qh: np.ndarray) -> ClockFeatures:
    """Derive both price clocks from a contiguous quarter-hour price series.

    Parameters
    ----------
    ts_utc_ns : int64 UTC timestamps in nanoseconds, strictly increasing, 15-minute
        spacing. (The kill-test panel stores exactly this in `ts_utc`.)
    price_qh : day-ahead price per quarter-hour, EUR/MWh.

    Notes
    -----
    Calendar hours are grouped on UTC. Berlin is a whole number of hours from UTC, so
    the UTC hour partition is the same partition as the Berlin local hour partition --
    only the labels differ, and run lengths depend only on the partition. The Berlin
    local *year* is computed separately, because the staircase keys on it.

    Gaps matter: a run is only "uninterrupted" if the quarter-hours are adjacent in
    time. A gap in the series breaks the run, which this function enforces by
    refusing a non-contiguous input rather than silently bridging it.
    """
    ts = np.asarray(ts_utc_ns, dtype=np.int64)
    p = np.asarray(price_qh, dtype=float)
    if ts.shape != p.shape:
        raise ValueError(f"ts {ts.shape} and price {p.shape} differ")
    if ts.size == 0:
        raise ValueError("empty price series")

    step = 15 * 60 * 1_000_000_000
    if ts.size > 1:
        diffs = np.diff(ts)
        bad = np.flatnonzero(diffs != step)
        if bad.size:
            raise ValueError(
                f"Price series is not contiguous 15-minute data: {bad.size} gap(s), "
                f"first at index {int(bad[0])} (diff {int(diffs[bad[0]])} ns, "
                f"expected {step}). Runs cannot be computed across a gap."
            )

    hour_ns = 3600 * 1_000_000_000
    hour_key = ts // hour_ns
    _, hour_index = np.unique(hour_key, return_inverse=True)
    n_hours = int(hour_index.max()) + 1

    counts = np.bincount(hour_index, minlength=n_hours).astype(float)
    sums = np.bincount(hour_index, weights=p, minlength=n_hours)
    hour_mean = sums / counts
    partial = counts != 4
    if partial.any():
        # Only possible at the ends of the window; the mean of a partial hour is not
        # the statutory hourly contract price, so say so rather than hide it.
        raise ValueError(
            f"{int(partial.sum())} calendar hour(s) do not have 4 quarter-hours "
            "(truncated window?). Trim the series to whole hours first."
        )

    hour_neg = hour_mean < 0.0
    hour_run = _maximal_run_lengths(hour_neg)

    qh_run = _maximal_run_lengths(p < 0.0)

    # Berlin-local calendar year, which is what the staircase keys on. Computed once
    # per calendar hour (a few thousand values) and broadcast back, rather than once
    # per quarter-hour. zoneinfo handles the DST offset, so the year boundary lands at
    # Berlin midnight, not UTC midnight.
    hour_starts = np.unique(hour_key) * 3600
    year_per_hour = np.array(
        [
            dt.replace(tzinfo=timezone.utc).astimezone(BERLIN).year
            for dt in hour_starts.astype("datetime64[s]").astype(object)
        ],
        dtype=int,
    )
    berlin_year = year_per_hour[hour_index]

    return ClockFeatures(
        price_qh=p,
        hour_index=hour_index,
        hour_mean_price=hour_mean[hour_index],
        hour_run_length=hour_run[hour_index],
        qh_run_length=qh_run,
        berlin_year=berlin_year,
    )


# ------------------------------------------------------------------- theta, exposure


def trigger_active(cohort: Cohort, clock: ClockFeatures) -> np.ndarray:
    """Boolean per quarter-hour: is the cohort's section 51 reduction active?

    A cohort not subject to section 51 (pre-2016, pilot wind, below its size
    threshold) never triggers -- that is the whole point of the size exemptions.
    """
    n = clock.price_qh.size
    if not cohort.subject_to_s51:
        return np.zeros(n, dtype=bool)

    if cohort.clock == QH_CLOCK:
        # Section 51(1) EEG 2023 from 25 Feb 2025: every negative quarter-hour counts,
        # on its own, with no run-length condition.
        return clock.price_qh < 0.0

    # Hour clock: the calendar hour is negative on the mean of its four quarter-hour
    # prices, and belongs to a maximal run at least as long as the threshold. The
    # threshold can change with the Berlin-local calendar year (the staircase).
    active = np.zeros(n, dtype=bool)
    for year in np.unique(clock.berlin_year):
        need = cohort.run_length_for_year(int(year))
        if need is None:
            continue
        in_year = clock.berlin_year == year
        active |= in_year & (clock.hour_mean_price < 0.0) & (clock.hour_run_length >= need)
    return active


def market_premium(aw_eur_mwh: float, mv_eur_mwh: float) -> float:
    """MP = max(0, AW - MV). Spec section 3."""
    return float(max(0.0, aw_eur_mwh - mv_eur_mwh))


def theta_and_exposure(
    cohorts: CohortSet,
    clock: ClockFeatures,
    mv_eur_mwh: float | Mapping[str, float],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Thresholds, exposure and depth below threshold, per cohort and quarter-hour.

    Returns (theta, s, depth), each of shape (K, T):

        theta[k, t] = 0                      if the trigger is active, or out of support
                    = -max(0, AW_k - MV)     otherwise (the market premium)
        s[k, t]     = 1[price_qh[t] < theta[k, t]]
        depth[k, t] = max(0, theta[k, t] - price_qh[t])   -- 0 where not exposed

    `mv_eur_mwh` is the monthly market value. In Phase 2 it is a scalar placeholder.
    In Phase 3 it is task-dependent (rule 17): T1 may use the published Netztransparenz
    series, T2 must recompute it month-to-date from SMARD data available by D-1,
    because the published series is released after the month ends.

    Exposure uses the **quarter-hour** price on both clocks. The clock decides when the
    *trigger* is active, not which price the plant is paid: a plant whose support has
    been zeroed for the hour still decides quarter-hour by quarter-hour whether this
    quarter-hour's price is below its threshold.
    """
    n = clock.price_qh.size
    k = len(cohorts)
    theta = np.zeros((k, n), dtype=float)

    for i, c in enumerate(cohorts):
        if not c.in_support:
            # No premium left to lose: the plant earns the spot price, so it stops
            # whenever that is below zero.
            theta[i, :] = 0.0
            continue

        mv = mv_eur_mwh[c.cohort_id] if isinstance(mv_eur_mwh, Mapping) else float(mv_eur_mwh)
        mp = market_premium(float(c.aw_eur_mwh), mv)
        theta[i, :] = -mp
        theta[i, trigger_active(c, clock)] = 0.0

    price = clock.price_qh[None, :]
    s = (price < theta).astype(float)
    depth = np.maximum(0.0, theta - price) * s
    return theta, s, depth


def curtailed_share(
    shares: np.ndarray, s: np.ndarray, r: np.ndarray, clip: bool = True
) -> np.ndarray:
    """c_t = sum_k w_k * s_k,t * r_k,t, the switched-off share of the fleet.

    `r` is (K, T) in [0, 1]. Clipped into [0, 1] because (1 - c) multiplies A.
    """
    w = np.asarray(shares, dtype=float)[:, None]
    c = (w * np.asarray(s, dtype=float) * np.asarray(r, dtype=float)).sum(axis=0)
    return np.clip(c, 0.0, 1.0) if clip else c


def macro_exposed_share(cohorts: CohortSet, s: np.ndarray) -> dict[str, np.ndarray]:
    """Capacity-weighted exposed share per macro-cohort, for reporting (rule 18).

    This is the aggregate the two-cohort fallback is described in terms of. The model
    itself does not consume it: pooling there is parameter tying, which keeps each
    cohort's own depth and is therefore exact. See the module docstring.
    """
    out: dict[str, np.ndarray] = {}
    for macro in (MACRO_QH, MACRO_HOUR):
        idx = [i for i, c in enumerate(cohorts) if c.macro == macro]
        if idx:
            w = cohorts.shares[idx][:, None]
            out[macro] = (w * s[idx, :]).sum(axis=0)
        else:
            out[macro] = np.zeros(s.shape[1], dtype=float)
    return out


def exposure_differs_by_day(
    s: np.ndarray, berlin_date: Sequence[str]
) -> tuple[int, np.ndarray]:
    """Pre-registered rule-18 check: event-days on which cohort exposure vectors differ.

    Returns (count, mask over unique days). A day counts when at least one
    quarter-hour in it has two cohorts with different exposure -- that is the
    variation the K-cohort model needs. Fewer than 10 such days and the model
    collapses to two cohorts (spec section 3, I4).
    """
    dates = np.asarray(berlin_date)
    differs_qh = s.max(axis=0) != s.min(axis=0)
    uniq = np.unique(dates)
    mask = np.array([differs_qh[dates == d].any() for d in uniq], dtype=bool)
    return int(mask.sum()), mask


# ------------------------------------------------------- the Phase 2 placeholder set

# PLACEHOLDER award values and market value. Phase 2 only -- the semi-synthetic
# benchmark needs cohorts that differ in the ways the rules make them differ, not real
# money. Phase 3 replaces these with MaStR + tender values under rule 19 (a range, run
# at three settings, keyed to the presence of a Zuschlagsnummer).
PLACEHOLDER_MV_EUR_MWH = 45.0
PLACEHOLDER_AW_EUR_MWH = {
    "pre2016_out_of_support": None,
    "wind2016_2020_6h": 62.0,
    "wind2021_2022_4h": 59.0,
    "wind2023_feb2025_staircase": 71.0,
    "post_feb2025_qh": 74.0,
}


def placeholder_cohort_set(
    shares: Mapping[str, float] | None = None,
    aw: Mapping[str, float | None] | None = None,
) -> CohortSet:
    """Five cohorts spanning both clocks and all three run-length thresholds.

    Chosen so the identifying variation of spec section 3 I4 is actually present:
    one quarter-hour clock cohort, three hour-clock cohorts at 6 h / 4 h / staircase,
    and one cohort section 51 never reaches. All award values are PLACEHOLDERS.
    """
    aw = dict(PLACEHOLDER_AW_EUR_MWH if aw is None else aw)
    w = dict(
        shares
        or {
            "pre2016_out_of_support": 0.10,
            "wind2016_2020_6h": 0.30,
            "wind2021_2022_4h": 0.18,
            "wind2023_feb2025_staircase": 0.27,
            "post_feb2025_qh": 0.15,
        }
    )
    return CohortSet(
        [
            Cohort(
                cohort_id="pre2016_out_of_support",
                rule_id="R01",
                clock=HOUR_CLOCK,
                run_length_h=None,
                subject_to_s51=False,
                in_support=False,
                aw_eur_mwh=aw["pre2016_out_of_support"],
                capacity_share=w["pre2016_out_of_support"],
                macro=MACRO_HOUR,
                note="Commissioned before 1 Jan 2016, section 24(3) no. 1 EEG 2014; "
                "past the 20-year support period, so theta = 0 throughout.",
            ),
            Cohort(
                cohort_id="wind2016_2020_6h",
                rule_id="R02",
                clock=HOUR_CLOCK,
                run_length_h=6,
                subject_to_s51=True,
                in_support=True,
                aw_eur_mwh=aw["wind2016_2020_6h"],
                capacity_share=w["wind2016_2020_6h"],
                macro=MACRO_HOUR,
                note="Wind >= 3 MW commissioned 2016-2020; six consecutive negative hours.",
            ),
            Cohort(
                cohort_id="wind2021_2022_4h",
                rule_id="R04",
                clock=HOUR_CLOCK,
                run_length_h=4,
                subject_to_s51=True,
                in_support=True,
                aw_eur_mwh=aw["wind2021_2022_4h"],
                capacity_share=w["wind2021_2022_4h"],
                macro=MACRO_HOUR,
                note=">= 500 kW commissioned 2021-2022; four consecutive negative hours.",
            ),
            Cohort(
                cohort_id="wind2023_feb2025_staircase",
                rule_id="R07",
                clock=HOUR_CLOCK,
                run_length_h="staircase",
                subject_to_s51=True,
                in_support=True,
                aw_eur_mwh=aw["wind2023_feb2025_staircase"],
                capacity_share=w["wind2023_feb2025_staircase"],
                macro=MACRO_HOUR,
                note="Commissioned 2023 - 24 Feb 2025; 4 h (2023), 3 h (2024-25), "
                "2 h (2026), 1 h (2027+), by the calendar year of the negative prices.",
            ),
            Cohort(
                cohort_id="post_feb2025_qh",
                rule_id="R09",
                clock=QH_CLOCK,
                run_length_h=None,
                subject_to_s51=True,
                in_support=True,
                aw_eur_mwh=aw["post_feb2025_qh"],
                capacity_share=w["post_feb2025_qh"],
                macro=MACRO_QH,
                note="Commissioned or awarded from 25 Feb 2025; every negative "
                "quarter-hour, no run-length condition.",
            ),
        ]
    )


# --------------------------------------------------- the real fleet, from MaStR

MASTR_SHARES_PATH = REPO_ROOT / "artifacts" / "method_inputs" / "mastr_cohort_shares.csv"

# Award values remain PLACEHOLDERS until the tender results are ingested (rule 19:
# a range, three settings, keyed to the Zuschlagsnummer). The capacity SHARES below
# are real -- they key on commissioning date and size, which MaStR gives directly
# and which the Zuschlagsnummer join does not affect.
MASTR_COHORT_SPEC = {
    "out_of_support": dict(
        rule_id="R01", clock=HOUR_CLOCK, run_length_h=None, subject_to_s51=False,
        in_support=False, aw=None, macro=MACRO_HOUR,
        note="Past 20 years plus the commissioning year (EEG s.25): no premium left "
             "to lose, so theta = 0.",
    ),
    "pre2016_in_support_no_s51": dict(
        rule_id="R01", clock=HOUR_CLOCK, run_length_h=None, subject_to_s51=False,
        in_support=True, aw=62.0, macro=MACRO_HOUR,
        note="Commissioned before 1 Jan 2016, still in support. Section 51 never "
             "applies, so theta is minus the market premium throughout.",
    ),
    "wind2016_2020_6h": dict(
        rule_id="R02", clock=HOUR_CLOCK, run_length_h=6, subject_to_s51=True,
        in_support=True, aw=62.0, macro=MACRO_HOUR, note="Wind >= 3 MW, 2016-2020.",
    ),
    "wind2021_2022_4h": dict(
        rule_id="R04", clock=HOUR_CLOCK, run_length_h=4, subject_to_s51=True,
        in_support=True, aw=59.0, macro=MACRO_HOUR, note=">= 500 kW, 2021-2022.",
    ),
    "wind2023_feb2025_staircase": dict(
        rule_id="R07", clock=HOUR_CLOCK, run_length_h="staircase", subject_to_s51=True,
        in_support=True, aw=71.0, macro=MACRO_HOUR,
        note="2023 - 24 Feb 2025; steps by the calendar year of the negative prices.",
    ),
    "post_feb2025_qh": dict(
        rule_id="R09", clock=QH_CLOCK, run_length_h=None, subject_to_s51=True,
        in_support=True, aw=74.0, macro=MACRO_QH,
        note="From 25 Feb 2025: every negative quarter-hour, no run-length condition.",
    ),
    "size_exempt": dict(
        rule_id="R10", clock=HOUR_CLOCK, run_length_h=None, subject_to_s51=False,
        in_support=True, aw=66.0, macro=MACRO_HOUR,
        note="Below its vintage's size threshold: never triggers, so theta stays at "
             "the market premium.",
    ),
    "pilot_exempt": dict(
        rule_id="R12", clock=HOUR_CLOCK, run_length_h=None, subject_to_s51=False,
        in_support=True, aw=66.0, macro=MACRO_HOUR,
        note="Pilot wind, exempt in every version before 25 Feb 2025.",
    ),
}


def mastr_cohort_set(area: str = "DE", path: Path = MASTR_SHARES_PATH) -> CohortSet:
    """Cohorts with REAL capacity shares from the MaStR snapshot.

    Replaces `placeholder_cohort_set`, whose shares were invented. Award values are
    still placeholders and are marked as such; the shares are real.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `python src/ingest_mastr.py` first."
        )
    with open(path, newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["area"] == area]
    if not rows:
        raise ValueError(f"No MaStR cohort shares for area {area!r} in {path}")

    unknown = {r["cohort"] for r in rows} - set(MASTR_COHORT_SPEC)
    if unknown:
        raise ValueError(f"Unmapped MaStR cohort(s) {sorted(unknown)} (hard rule 12)")

    total = sum(float(r["capacity_share"]) for r in rows)
    cohorts = []
    for r in sorted(rows, key=lambda r: r["cohort"]):
        spec = MASTR_COHORT_SPEC[r["cohort"]]
        cohorts.append(Cohort(
            cohort_id=r["cohort"], rule_id=spec["rule_id"], clock=spec["clock"],
            run_length_h=spec["run_length_h"], subject_to_s51=spec["subject_to_s51"],
            in_support=spec["in_support"], aw_eur_mwh=spec["aw"],
            capacity_share=float(r["capacity_share"]) / total, macro=spec["macro"],
            note=spec["note"],
        ))
    return CohortSet(cohorts)
