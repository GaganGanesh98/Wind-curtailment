"""Phase P -- post-auction forecasting of observed feed-in G (docs/P0_preregistration.md).

Forecast time is 12:57 CET on D-1, after the day-ahead auction. Everything in this
package is bound by the forecast-time allow-list in `src/postauction/leakage.py`,
which `tests/test_leakage_postauction.py` enforces.
"""
