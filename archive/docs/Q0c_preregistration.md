# Q0c — volume triangulation against Hirth v2: pre-registration

**Written and committed 15 November 2026, before any Q0c number was computed.** The
student's instruction asks for the comparison and the meaning of "consistent" to be
fixed first; both are below. Report only: no gap is explained beyond what the data
supports.

## 1. The two figures

**Hirth v2.** arXiv 2609.10053v2 (10 Nov 2026), §5.2, p. 13: market-based curtailment of
**2.5 TWh for wind in the first ten months of 2026**, described as the residual summed
over the hours with a negative day-ahead price. The residual is defined in §5.1, p. 12,
as generation potential minus actual generation minus grid-related curtailment, every
hour. File read: `Literature Review/2609.10053v2.pdf` in the main checkout, sha256 first
16 `9bfd90e7ad8c8739`.

**Q0c.** The same construction with the quality-assured Online-Hochrechnung as the
potential:

```
V = sum over negative-price quarter-hours of (H - G - R) * 0.25 h,   in TWh
```

with `H`, `G` and `R` exactly as in `docs/Q0b_preregistration.md` §2 (`src/potential/q0b_validate_h.py:load_frames`).
95% event-day block bootstrap, 5,000 draws, seed 42, resampling the Berlin-local days
that carry at least one negative-price quarter-hour.

## 2. Every definitional difference, stated before comparing

| | Hirth v2 | Q0c |
|---|---|---|
| **potential** | a weather model: ERA5 100 m wind at 17 grid points, a fleet power curve per technology, calibrated on hours with day-ahead price ≥ 5 €/MWh and imbalance price ≥ −50 €/MWh (§5.1) | the TSO statutory projection under EEG Anlage 1 Nr. 5.1, quality-assured series |
| **resolution** | hourly | quarter-hourly |
| **which periods count** | hours with a negative day-ahead price | quarter-hours with a negative day-ahead quarter-hour price. In the 15-minute market these differ: an hour can average positive while containing negative quarter-hours, and the reverse |
| **technology** | "wind". **`[VERIFY]` that this includes offshore**: his ERA5 inputs include five offshore points, and his cohort table (p. 11) lists offshore parks | **onshore only** |
| **geography** | Germany | **50Hertz + Amprion + TransnetBW only** — see §4 |
| **grid-related curtailment** | TSO-provided series (§5.1) | the Netztransparenz redispatch export, onshore renewable reductions, each measure spread evenly over its duration at its mean power |
| **observed generation** | TSO extrapolation from sample plants, hourly (§5.1, p. 13) | SMARD `act_onshore_mw`, quarter-hourly — the same kind of TSO extrapolation |
| **period** | first ten months of 2026 | **2026-01-01 to 2026-10-28**. The redispatch export and the panel both stop on 28 October, so 29–31 October is missing |
| **sign of hourly residuals** | summed; **whether negative residuals are clipped at zero is not stated in §5.1–5.2** `[VERIFY]`. `docs/06` reads the v1 pipeline as `max(0, Â − G)` | **signed sum** (primary), the same statistic Q0b uses. The sum with each quarter-hour clipped at zero is reported beside it as a definitional sensitivity |
| **"gross"** | the student describes the figure as gross. What §5.1 states is that any estimation error in the potential is attributed to curtailment, so the figure includes the potential model's error | includes the projection's error in the same way |
| **uncertainty** | none reported | 95% event-day interval |

## 3. What "consistent" means — fixed now

Q0c's scope is a **strict subset** of Hirth's: three of four control areas, onshore only,
three days short. Every component it leaves out — TenneT's onshore curtailment, all
offshore curtailment, the last three days — is **non-negative in truth**, because
curtailment cannot be negative. A two-sided comparison is therefore not available
without the excluded parts, and only one direction can be tested:

| result | meaning |
|---|---|
| **INCONSISTENT — Q0c higher** | the CI's **lower** bound for the three-area onshore volume exceeds 2.5 TWh: a subset of Hirth's scope already carries more than his whole |
| **NOT TESTABLE at national scale** | anything else. The point estimate and interval are reported, and nothing is said about agreement |

**No "consistent" verdict is available on this design**, and none will be claimed. That
is stated now so that a three-area figure below 2.5 TWh is not read later as agreement:
it would be what a subset should show whether or not the national figures agree.

## 4. Why only three areas — and what is blocked

The student asked for **DE onshore**. A DE-wide sum of the projection is exactly what
`docs/09` Amendment 4 A4.5 forbids: T-D(vii) is a supervisor precondition that no DE-level
aggregate may use the projection until TenneT's 0.839 positive-price ratio is explained,
or TenneT is excluded and the exclusion stated. It is not explained. **Phase Q hard rule 10
therefore applies to the DE-wide figure**, which is STOP-noted in `docs/Q_STOP_Q0c.md`
with the decision it needs. The rest of Q0c runs as below.

The bias T-D(vii) guards against is not formal here. `artifacts/Q0b/q0b_gap_shares.csv`
shows TenneT's projection sitting **below** `G + R` at positive prices (gap share
−0.0691), where every other area sits above it. A sum of `H − G − R` would carry that
offset straight into the volume.

## 5. What is reported

1. **Primary**: the three-area onshore volume, signed, with its 95% interval and the
   verdict of §3.
2. The same with each quarter-hour clipped at zero — a sensitivity for §2's sign row.
3. **Scale reference, not a scaling**: the three areas hold **41,133 of 71,576 MW, 57.5%**
   of German onshore capacity in the MaStR snapshot (`results/30_mastr_cohort_shares.csv`,
   `capacity_mw`). It is reported so a reader can see the subset's size. Q0c does not
   scale its volume by it, because that would assume TenneT curtails at the three areas'
   rate per megawatt.
4. Negative-price quarter-hours and event-days in the window.
5. **TenneT's own onshore volume is not computed.** It would sit beside the three-area
   figure and invite exactly the sum §4 rules out.
