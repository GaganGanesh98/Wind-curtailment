# Q_STOP_Q0c — a DE-wide projection volume conflicts with the TenneT precondition

**Raised 15 November 2026, before any Q0c or Q5 number existed.** Phase Q hard rule 10:
stop and report when an instruction conflicts with an existing pre-registration or
supervisor minute.

## The conflict

- **The instruction.** Q0c: sum `H − G − redispatch` over negative-price quarter-hours,
  *DE onshore*, and compare with Hirth v2's national 2.5 TWh. Q5: re-run P3's real-data
  arm — which is DE — with the projection as the potential.
- **The minute.** `docs/09` Amendment 4 A4.5, supervisor's decision: T-D(vii) is a
  precondition, not a diagnostic, and **no DE-level aggregate may use the projection
  until TenneT's 0.839 positive-price ratio is explained, or TenneT is excluded and the
  exclusion stated.**

A DE onshore sum of the projection, and a DE `ĉ = 1 − G/H`, are both DE-level
aggregates using the projection. TenneT's ratio is still unexplained.

## What was done instead — the variant the minute itself permits

The minute allows exclusion. Both phases therefore run on **50Hertz + Amprion +
TransnetBW**, with the exclusion stated:

- **Q0c** reports the three-area onshore volume. Against a national figure that supports
  only a one-sided test (`docs/Q0c_preregistration.md` §3).
- **Q5** runs on the same three-area region with **both** potentials, the forecast and
  the projection, so that the only difference between its two arms is the potential
  (`docs/Q5_preregistration.md` §2). P3's published DE results are untouched.

## What is blocked

The **national** comparison Q0c was asked for, and a **DE-wide** Q5.

## The decision this needs — student or supervisor

1. **Explain TenneT's 0.839.** Q0b found a testable candidate: TenneT's redispatch is
   about 13% of its projection even at positive prices, against under 2% elsewhere, and
   a large redispatch term in the ratio's denominator would pull it down
   (`docs/Q0b_results.md` §3, `[VERIFY]`). If that test passes, the precondition is met
   and both phases can be re-run DE-wide.
2. **Authorise TenneT's inclusion** for Q0c and Q5 specifically, with its positive-price
   offset (gap share −0.0691) stated beside every figure.
3. **Accept the three-area results** as they stand.

Nothing in Q0c or Q5 waits on this except the national and DE-wide versions.
