"""Shared configuration for the RQ1 kill test.

SMARD filter IDs were read from SMARD's own chart configuration
(https://www.smard.de/app/chart_configuration/market_data_configuration.json,
fetched 29 Oct 2026, archived at
data/raw/smard_market_data_configuration_2026-10-29.json). They are NOT guessed.

Unit note: SMARD's quarterhour series are MWh *per quarter-hour*. Verified by
checking that the hourly series equals the sum of its four quarter-hours.
Power in MW = value * 4. Prices (filter 4169) are EUR/MWh and are NOT scaled.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")
UTC = ZoneInfo("UTC")

SEED = 42
N_BOOT = 5_000

# Analysis period, defined in Berlin local time (inclusive of both endpoints).
# Extended to 2024-01-01 on 1 Nov 2026 (Stage 1.1) for the Test 2 training history
# and E1 v2's base panel (docs/08 Amendment 2, docs/09 Amendment 3 section 0.1).
# Before 2025-10-01 the day-ahead price is HOURLY: SMARD serves it at quarter-hour
# resolution as the hourly value repeated four times (verified: 168 of 168 hours in a
# 2024 sample week have four identical quarter-hour prices, zero nulls), which is
# exactly what EEG section 100(45) requires for the section 51 clock in that period.
PERIOD_START_BERLIN = datetime(2024, 1, 1, 0, 0, tzinfo=BERLIN)
PERIOD_END_BERLIN = datetime(2026, 10, 28, 23, 45, tzinfo=BERLIN)

# SMARD region codes, exactly as the chart configuration spells them.
# "DE" is the exact sum of the four control areas (verified quarter-hour by
# quarter-hour); "DE-LU" additionally contains Luxembourg (~0.2% larger).
AREAS = ["DE", "50Hertz", "Amprion", "TenneT", "TransnetBW"]

# Pretty names for tables/figures.
AREA_LABEL = {
    "DE": "DE",
    "50Hertz": "50Hertz",
    "Amprion": "Amprion",
    "TenneT": "TenneT DE",
    "TransnetBW": "TransnetBW",
}

# Offshore wind exists only in 50Hertz and TenneT. Confirmed two ways:
#  (1) the chart configuration lists regions DE, DE-AT-LU, 50Hertz, TenneT,
#      DE-LU for every offshore series;
#  (2) empirically, filters 3791 / 5128 / 1225 return HTTP 404 for Amprion and
#      TransnetBW while every onshore filter returns HTTP 200.
# Offshore is therefore treated as exactly 0 in Amprion and TransnetBW.
OFFSHORE_AREAS = ["DE", "50Hertz", "TenneT"]

FILTERS = {
    "da_onshore":  123,   # Prognostizierte Erzeugung Day-Ahead / Wind Onshore
    "da_offshore": 3791,  # Prognostizierte Erzeugung Day-Ahead / Wind Offshore
    "id_onshore":  5127,  # Prognostizierte Erzeugung Intraday  / Wind Onshore
    "id_offshore": 5128,  # Prognostizierte Erzeugung Intraday  / Wind Offshore
    "act_onshore": 4067,  # Realisierte Erzeugung / Wind Onshore
    "act_offshore": 1225, # Realisierte Erzeugung / Wind Offshore
    "price":       4169,  # Markt / Grosshandelspreise / Deutschland-Luxemburg
    # Added 22 Nov 2026 for Experiment 4 (docs/12); fetched only with --series da_solar.
    "da_solar":    125,   # Prognostizierte Erzeugung Day-Ahead / Photovoltaik
}

#: Regions for the day-ahead solar forecast (filter 125 is published per control area).
SOLAR_AREAS = ["DE", "50Hertz", "Amprion", "TransnetBW"]
#: Series not in the default job list: fetched only when named with --series.
OPT_IN_SERIES = {"da_solar": SOLAR_AREAS}

ONSHORE_SERIES = ["da_onshore", "id_onshore", "act_onshore"]
OFFSHORE_SERIES = ["da_offshore", "id_offshore", "act_offshore"]

# MWh per quarter-hour -> MW
MWH_PER_QH_TO_MW = 4.0

# Price bands. Each tuple is (label, lo, hi) with the band defined as
# lo < p <= hi, except the open ends. They partition the real line, and the
# first four are exactly the "negative quarter-hours" (price < 0).
PRICE_BANDS = [
    ("<= -50",     None,  -50.0),
    ("-50 to -20", -50.0, -20.0),
    ("-20 to -5",  -20.0,  -5.0),
    ("-5 to 0",     -5.0,   0.0),   # -5 < p < 0  (0 itself is not negative)
    ("0 to 5",       0.0,   5.0),   #  0 <= p <= 5
    ("> 5",          5.0,  None),
]

RAW_DIR = "data/raw/smard"
PROCESSED_DIR = "data/processed"
RESULTS_DIR = "results"
FIGURES_DIR = "figures"
