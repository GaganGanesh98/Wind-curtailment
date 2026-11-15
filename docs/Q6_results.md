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

## Q6b — synthetic day effect: NOT SUPPORTED

Code `src/identification/run_q6b.py` and `src/identification/summarise_q6b.py`, committed
(`ec77b6a`) before Q6b ran. Artifacts `artifacts/Q6/q6b_day_effect.csv` (3,780 rows: 54
cells × 5 day-effect levels × 2 noise levels × 7 functionals) and
`artifacts/Q6/q6b_summary.csv`.

Q6a found heterogeneity, so Q6b did not start from a weakened hypothesis.

**Port check: passed.** At σ_r = 0, all 756 rows at σ = 0.066 and σ = 0.18 equal their
Q1 rows in every compared field. A deliberate test confirmed the check can fail: with
σ_r = 0.2 on one cell it flagged 51 differing fields across 7 rows.

> **No σ_r meets either signature, let alone both. Verdict: NOT SUPPORTED.**

| σ_r | fleet share informative at Anchor H | S1, inside [0.004, 0.117] | ε, T → H | floor ÷ residual, T → H | S2 |
|---|---|---|---|---|---|
| 0 (control) | 1.000 | no | 0.108 → 0.039 | 0.9966 → 0.9964 | no |
| 0.05 | 1.000 | no | 0.117 → 0.060 | 0.9966 → 0.9950 | no |
| 0.10 | 1.000 | no | 0.143 → 0.097 | 0.9953 → 0.9937 | no |
| 0.20 | 0.667 | no | 0.210 → 0.155 | 0.9935 → 0.9931 | no |
| 0.30 | 0.593 | no | 0.250 → 0.208 | 0.9930 → 0.9926 | no |

Medians over the 54 cells. The fleet share counts informative (cell, functional) pairs
over the 108 defined λ₁ and λ₂ pairs.

- **S1 fails at every level.** The day effect lowers the fleet share from 1 to 0.593 at the
  grid top, five times the band's upper edge. It works through λ₂ first: λ₂ is informative
  in 18 of 54 cells from σ_r = 0.20, while λ₁ stays at 54 of 54 until σ_r = 0.30, where it
  falls to 46.
- **S2 fails at every level.** ε falls from Anchor T to Anchor H at every σ_r, but the
  floor's share falls with it, as in Q1. Q5's signature, a floor share that rises when ε
  falls, does not appear.
- **The day effect raises ε.** At Anchor H, median ε goes from 0.039 at σ_r = 0 to 0.208 at
  σ_r = 0.30. Q5's real ε under `H` was 0.107.
- **Coverage of the realised truth is 100% at every level.** The bounds stay honest under
  the day effect.

**Beside the verdict, deciding nothing.** Against Q5's fleet-only 3 of 11, with Clopper–Pearson
interval [0.060, 0.610], the share at σ_r = 0.30 and Anchor H, 0.593, falls inside it. No
lower level does.

**The σ_r grid is censored at the top for S1**, as Q1's σ\* was. The fleet share is still
falling at 0.30, and Q6b does not say what a larger day effect would give. Extending the
grid would be a pre-registration change. S2 shows no sign of turning anywhere on the grid.

### What Q6 says together

Q6a finds day-to-day variation in the real curtailed share that Anchor H's measured noise
cannot produce. Q6b finds that a common day-level shift in r*, at any level up to 0.30, does
not reproduce Q5's pair of signatures in the synthetic design. On this evidence the real
floor carries day-level variation, and **a common day effect in r\* does not explain Q5.**
Other forms of heterogeneity, such as day effects that differ by cohort, are not tested.
