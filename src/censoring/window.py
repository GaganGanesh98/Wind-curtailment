"""The evaluation window for E1 and E2, and why it starts when it does.

This is a market-design boundary, not a configuration preference, so it is a named
constant rather than a date passed around.

Why 1 October 2025
------------------
The day-ahead auction began clearing in **quarter-hours** for delivery day
1 October 2025 (SDAC 15-minute market time unit, all coupled bidding zones). Before
that there was no quarter-hour day-ahead price at all: the quarter-hour series in
`data/processed/panel_qh.parquet` is the hourly price repeated four times.

Verified on the panel, not assumed (src/censoring/check_window.py):

  * before 2025-10-01: **15,335 of 15,335 calendar hours** have all four quarter-hour
    prices identical -- 100.00%, mean within-hour spread 0.000 EUR/MWh;
  * from 2025-10-01: 0.30% flat, mean spread 23.95 EUR/MWh;
  * the switch is sharp at the boundary -- September 2025 is 100% flat, October 2025
    is 0% flat;
  * of the hours containing a negative quarter-hour, **0 of 982** before the boundary
    have mixed sign inside the hour, against 218 of 626 (34.8%) after.

Why that matters for identification. With a flat hour, a quarter-hour is negative
exactly when its hourly mean is negative, so the quarter-hour clock and the hourly
clock **coincide**: a theta = 0 cohort and a theta = -MP cohort cannot be separated
on sub-hourly variation, and the two clocks of spec section 3 I4 collapse into one.
Running E1 or E2 across the boundary would pool two different market designs and
would silently import a stretch of data in which the central identifying contrast
does not exist.

This is NOT the same thing as `src/smard_config.py:23 PERIOD_START_BERLIN`, which
sets the ingestion period. The panel on disk currently runs from 2024-01-01
(1032 Berlin days) while that constant says 2025-10-01, so the panel is wider than
either constant implies and must be restricted explicitly at use.

E3 is different: the transfer test across the 1 January 2026 staircase change lives
entirely inside the hourly regime, so the pre-October-2025 data is the right input
there and this window must NOT be applied to it.
"""

from __future__ import annotations

import numpy as np

#: First delivery day on which the day-ahead auction cleared in quarter-hours.
MTU15_FIRST_DELIVERY_DAY = "2025-10-01"

#: Start of the E1 / E2 evaluation window. Separate name from the market fact above
#: so that a future change of scope cannot be mistaken for a change of market history.
E1_E2_WINDOW_START = MTU15_FIRST_DELIVERY_DAY

__all__ = ["MTU15_FIRST_DELIVERY_DAY", "E1_E2_WINDOW_START",
           "in_e1_e2_window", "restrict_frame"]


def in_e1_e2_window(berlin_date) -> np.ndarray:
    """Boolean mask over Berlin-local date strings ('YYYY-MM-DD')."""
    d = np.asarray(berlin_date).astype(str)
    return d >= E1_E2_WINDOW_START


def restrict_frame(df, date_col: str = "berlin_date"):
    """Restrict a polars frame to the E1/E2 window. Never use this for E3."""
    import polars as pl
    return df.filter(pl.col(date_col) >= E1_E2_WINDOW_START)
