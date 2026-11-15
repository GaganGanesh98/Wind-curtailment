# Q6 — results: is the real-data floor behavioural heterogeneity?

Pre-registration `docs/Q6_preregistration.md`, commit **`b2f7d95`**, recorded on every row.
Every figure below is re-derived by `tests/test_reported_numbers.py`.

## Q6a — real data: heterogeneity PRESENT

Code `src/potential/q6a_heterogeneity.py`, committed before it ran. Artifact
`artifacts/Q6/q6a_cells.csv`. Region 50Hertz + Amprion + TransnetBW, quality-assured `H`,
2025-10-01 to 2026-10-28: **2,059 negative-price quarter-hours, every one placed in a
cell.** Ten of the sixteen cells are occupied, and eight have at least 5 event-days.

> **In all 8 testable cells, the between-day variance of `c_d` exceeds what Anchor H's
> σ = 0.066 produces on its own, with a 95% interval excluding zero.** A strict majority
> was required. **Verdict: PRESENT.**

This uses the day-constant error, the largest measurement variance that σ = 0.066 can
produce.

| price band | run length | event-days | `c_bar` | `V_between` | `V_meas` | ratio | 95% interval of the excess | break-even σ |
|---|---|---|---|---|---|---|---|---|
| (−5, 0) | 0.25–1 h | 33 | 0.167 | 0.0100 | 0.0030 | 3.3 | [0.0019, 0.0120] | 0.119 |
| (−5, 0) | 1–3 h | 18 | 0.275 | 0.0253 | 0.0023 | 11.0 | [0.0100, 0.0345] | 0.212 |
| (−5, 0) | 3–6 h | 42 | 0.298 | 0.0112 | 0.0022 | 5.2 | [0.0039, 0.0143] | 0.149 |
| (−5, 0) | > 6 h | 30 | 0.282 | 0.0090 | 0.0023 | 4.0 | [0.0033, 0.0100] | 0.131 |
| (−20, −5] | 3–6 h | 12 | 0.386 | 0.0175 | 0.0017 | 10.6 | [0.0029, 0.0272] | 0.209 |
| (−20, −5] | > 6 h | 25 | 0.458 | 0.0132 | 0.0013 | 10.3 | [0.0061, 0.0170] | 0.205 |
| (−50, −20] | > 6 h | 16 | 0.578 | 0.0101 | 0.0008 | 13.0 | [0.0034, 0.0147] | 0.229 |
| ≤ −50 | > 6 h | 12 | 0.712 | 0.0060 | 0.0004 | 16.6 | [0.0019, 0.0089] | 0.257 |
| (−50, −20] | 3–6 h | 4 | 0.426 | 0.0134 | 0.0014 | 9.3 | [−0.0010, 0.0186] | 0.196 |

The last row has fewer than 5 event-days and is outside the verdict. The tenth occupied
cell, (−20, −5] with 1–3 h, has a single event-day and no variance.

### Beside the verdict, deciding nothing

1. **With an error independent across quarter-hours**, `V_meas` is smaller in every
   testable cell (`v_meas_iid`), so the excess only grows.
2. **The break-even σ runs from 0.119 to 0.257** across the testable cells: 1.8 to 3.9
   times Anchor H. **In three cells it is below Anchor T's 0.18.** If `H`'s true error
   against potential were as large as the forecast's, measurement alone would account for
   the variance in those three cells. Q0 Amendment 1 says 0.066 is a lower bound on that
   error. Q6a cannot say how far below the true error it is.
3. **Adding redispatch, `c_d = 1 − (ΣG + ΣR)/ΣH`, does not remove the heterogeneity.**
   That test is also PRESENT in 8 of 8 testable cells. Its between-day variance is
   **larger** in every testable cell, by a factor of up to 25 in the short-run cells.
   Redispatch is itself lumpy from day to day, and it does not absorb the variation.

### What Q6a does not show

The pre-registration's caveats stand. **Heterogeneity is not shown to be behavioural.**
The day-to-day variation is real at Anchor H's measured noise, but it could come from
anything that varies by day and is outside the cell definition: behaviour, the exposed
cohort mix, or `H`'s own error if that is larger than 0.066.
