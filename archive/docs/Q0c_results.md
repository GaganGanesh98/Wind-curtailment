# Q0c — results: three-area onshore volume against Hirth v2

Pre-registration `docs/Q0c_preregistration.md`, commit **`60efa6e`**, recorded on every row.
Code `src/potential/q0c_volume.py`. Artifact `artifacts/Q0c/q0c_volume.csv`. Every figure
below is re-derived by `tests/test_reported_numbers.py`. Report only: no gap is explained.

## 1. Verdict: NOT TESTABLE at national scale

| | volume, TWh | 95% event-day interval |
|---|---|---|
| **signed sum, primary** | **1.644** | [1.162, 2.200] |
| each quarter-hour clipped at zero | 1.664 | [1.187, 2.216] |
| Hirth v2 §5.2, wind, Germany | 2.5 | none reported |

The interval's lower bound, 1.162 TWh, does not exceed 2.5 TWh, so the pre-registered
INCONSISTENT verdict is not reached. **Under §3 of the pre-registration that leaves NOT
TESTABLE, and no agreement is claimed.** A subset of Hirth's scope coming in below his
whole is what a subset should show, whatever the national figures are.

## 2. What the figure covers

| | |
|---|---|
| region | 50Hertz + Amprion + TransnetBW; TenneT excluded under T-D(vii), `docs/Q_STOP_Q0c.md` |
| capacity share of German onshore | 41,133 of 71,576 MW, 57.5% (`results/30_mastr_cohort_shares.csv`) — a scale reference, not a scaling |
| window | 2026-01-01 to 2026-10-28, Berlin dates |
| negative-price quarter-hours | 1,860, on 92 event-days |
| quarter-hours lost in the join | none: each area's frame and the raw panel both hold 1,860 |
| quarter-hours with `H − G − R` below zero | 5.5% |

The clipped and signed sums differ by 0.02 TWh. On this region and window, the sign
convention in the pre-registration's §2 row does not move the figure materially.

## 3. Every definitional difference, still standing

Each row of `docs/Q0c_preregistration.md` §2 applies unchanged. The two `[VERIFY]` items
there remain open, and neither changes the verdict, because the test is one-sided against
a subset whichever way they resolve:

1. whether Hirth's "wind" includes offshore;
2. whether his hourly residuals are clipped at zero.

## 4. Blocked

The **DE onshore** figure the student asked for is not computed. It waits on the decision
in `docs/Q_STOP_Q0c.md`. TenneT's own volume is not computed either (pre-registration §5
item 5).
