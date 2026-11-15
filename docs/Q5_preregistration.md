# Q5 — real-data bounds with the projection as the potential: pre-registration

**Written and committed 15 November 2026, before Q5 was run and before any Q5 number
existed.** Q5 runs **after Q1 finishes**, as the student instructed, so that Q1 places the
projection's anchor on the dial first.

## 1. The question

P3's real-data arm found nothing identified, with `ĉ = 1 − G/F` and the day-ahead forecast
as the potential (`docs/P3_results.md` §3). Q0b established that the quality-assured
projection `H` adds back market curtailment, and Q0 Amendment 1 measures its agreement
with output at σ ≈ 0.06 against the forecast's 0.18. Q5 asks: **with `H` in place of `F`,
how many of P3's real-data intervals become informative?**

**`H` is ex post.** This is a T1 identification question, bounds only. `H` is never a
day-ahead input: it is on the Phase P forecast-time forbidden list
(`src/postauction/leakage.py`, prefix `hochrechnung`), which
`tests/test_leakage_postauction.py` enforces.

## 2. Design

**Everything is P3's real-data arm except the potential and the region.** Same seven
functionals, same `low` / `main` / `high` award settings, same months — the twelve with a
published monthly market value, 2025-10 to 2026-09, of which the ten carrying a
negative-price quarter-hour each get a month arm — same window arm, same bounds, ε rule,
depth grid, run-length levels and solver (`docs/P3_results.md` §0).

**The region is 50Hertz + Amprion + TransnetBW.** A DE-wide `ĉ = 1 − G/H` is blocked by
T-D(vii); `docs/Q_STOP_Q0c.md` records the conflict and the decision it needs. On the
three-area region:

| | |
|---|---|
| `G`, `F`, `H` | the sum of the three areas' `act_onshore_mw`, `da_onshore_mw` and quality-assured projection, on quarter-hours where all three report |
| cohort shares `w_k` | the three areas' MaStR capacity per cohort, summed and normalised (`results/30_mastr_cohort_shares.csv`) |
| θ, exposure, depth | exactly P3's: the national price, the national monthly market value and the national capacity-weighted award value per cohort. The rules and prices are national, so exposure per cohort is identical in every area; only `w_k` differs |

**Two arms on that region, differing only in the potential:**

- **Q5-F**: `ĉ = 1 − G/F`, `F` also λ₅'s potential — P3's construction, moved to the
  three-area region.
- **Q5-H**: `ĉ = 1 − G/H`, `H` also λ₅'s potential.

Q5-F exists so that a change between the arms can be attributed to the potential. A
comparison of Q5-H with P3's published DE results would confound the potential with the
region.

**Port check, before Q5 is run.** The loader is generalised rather than copied, and with
`region = DE` and `potential = F` it must reproduce committed rows of
`artifacts/P3/p3_real.csv` bit-for-bit. A mismatch stops Q5.

## 3. The informativeness threshold — Q0's, unchanged

A functional is **informative** in a (setting, month) arm when its interval width is below
**0.25** of its logically maximal width: 1 for λ₁–λ₄ and λ₇, 2 for λ₆, and the
full-response energy `l5_energy_full_gwh` for λ₅ (`docs/Q0_preregistration.md` §5).

## 4. The headline — fixed now

> **The share of functional-months that become informative**: of all (functional, month)
> pairs at the **`main`** award setting that are defined in **both** arms, the share that
> are **not** informative under Q5-F and **are** informative under Q5-H.

Reported beside it, deciding nothing:

1. The share informative under each arm separately, so a pair informative under both is
   visible and not counted as a change.
2. The reverse transition — informative under F, not under H — counted, not netted.
3. The same three numbers at `low` and `high`.
4. The window arm per setting, which is not a month and is not in the headline.
5. ε, the floor-to-residual ratio and the median width per arm, so P3's mechanism can be
   traced: if `H` helps, the floor share should fall.

Pairs defined in only one arm are excluded from the denominator and counted.

## 5. What this cannot show

1. **A three-area result says nothing about TenneT**, which holds 42.5% of German onshore
   capacity.
2. **Informative is not correct.** On real data there is no truth to cover; a narrow
   interval is narrow, and may still be wrong if `H` is biased. Q0b established that `H`
   rises with depth, not that its level is right, and found it running 3.3 times the
   forecast's gap at negative prices.
3. **Q0 Amendment 1's lower-bound caveat applies.** If `H`'s error against true potential
   is larger than its agreement with output, Q1 places it further up the dial than 0.06.
