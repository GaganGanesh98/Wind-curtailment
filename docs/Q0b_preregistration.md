# Q0b — does Anchor H add back market curtailment? Pre-registration

**Written and committed 15 November 2026, before the quality-assured series was
fetched and before any Q0b number existed.** The criterion in §4 is the student's,
recorded verbatim; §§2–3 and §§5–7 are the implementation it needs, fixed here so that
none of it can be chosen once a gap is visible. Every Q0b result row records this
file's commit hash.

It changes nothing in `docs/Q0_preregistration.md`. In particular no Q1 or Q2 grid
level, threshold or statistic depends on the Q0b verdict (§6).

---

## 1. Why Q0b exists

Anchor H's σ = 0.066 (`artifacts/Q0/q0_anchors.csv`) is measured on **positive-price**
quarter-hours, where nothing is switched off and `G` is the uncurtailed output. It
therefore says how closely the projection agrees with output *where agreement is
expected*. It says nothing about the property that makes H worth having: that it
tracks **potential** where output falls short of it.

If H is a potential, then on negative-price quarter-hours — where part of the fleet
switches off and `G` falls below what the wind could have produced — H should run
further above `G` than it does at positive prices, and further still as the price gets
deeper. If H is instead an extrapolation of metered output, it falls with `G` and the
gap does not grow. Q0b tests which.

## 2. Data

| | |
|---|---|
| **H** | *Online-Hochrechnung **qualitätsgesichert** Wind Onshore* — the quality-assured series, PT15M, all four control areas |
| **G** | panel `act_onshore_mw`, per control area |
| **R** | onshore wind redispatch reductions, MW per quarter-hour per area, from the Netztransparenz redispatch export, via `src/check_nr51_compliance.py:redispatch_qh` — the reader and filters that produced `results/39_nr51_compliance.csv`, reused unchanged |
| **price** | DE day-ahead quarter-hour price (one bidding zone, the same price in every area) |
| **window** | 2025-10-01 to 2026-10-28, the intersection of the window rule, the panel and the redispatch export |

**Which series, and why it matters.** Netztransparenz publishes two onshore
projections (`datacenter.netztransparenz.de/api/chart/data-points`, read 15 Nov 2026):

| series | first published | resolution | on disk |
|---|---|---|---|
| *betrieblich* (operational, preliminary) | 2026-09-01 | PT15M | **yes** — the Anchor H files |
| *qualitätsgesichert* (quality-assured, final) | 2012-01-01 | PT60M, PT15M | **no** |

The page itself explains the difference: operational values are preliminary for their
month; "as part of the market-value calculation the projection is checked again and
corrected if necessary, and then published as the quality-assured online projection at
the start of the following month". **Anchor H as measured in Q0 is the operational
series**, which is why it covers only 2026-09-01 onwards. The brief asks for the
quality-assured one, which covers the whole window. The two are reported separately
and never pooled.

**How it is fetched.** The public Netztransparenz page for the series offers a date
picker and a "CSV-Datei herunterladen" button with no login, and states that a
quality-assured download "is then immediately possible" once the market values are
out. That public download is the route. The credentialed WebAPI is not used, and the
data centre's undocumented browser API is not scripted. If the page's download turns
out to need credentials after all, Q0b is STOP-noted in `docs/Q_STOP_Q0b.md` and §7
applies.

## 3. The statistic

For a set `S` of quarter-hours in one area:

```
gap_share(S) = sum over S of (H - G - R)  /  sum over S of H
```

**A ratio of sums, not a mean of ratios.** A mean of per-quarter-hour ratios is
dominated by low-wind quarter-hours with a small denominator; the ratio of sums is the
energy-weighted share and is what the projection's role in the market-value formula
actually weights by.

**The share, not the MW gap, is primary — because the MW gap is confounded with level
in exactly the direction that would fake a pass.** Negative-price quarter-hours are
high-wind quarter-hours. Anchor H runs about 4.8% above `G` on positive-price
quarter-hours (bias −0.047 in `log(G/H)`). A projection that runs a constant 4.8% high
everywhere and adds back no curtailment at all would therefore still show a *larger MW
gap* at negative prices, simply because there is more wind. The share removes that:
under a constant proportional bias it is the same at every level. The mean MW gap is
reported beside it and decides nothing.

**Bands.** The four negative-price bands of the brief, which are the kill test's
`smard_config.PRICE_BANDS`: (−5, 0), (−20, −5], (−50, −20], ≤ −50 €/MWh. Assigned by
`src/postauction/common.py:band_of`, which reproduces the kill test's per-band counts
on this panel exactly (DE: 1,461 / 301 / 148 / 149 quarter-hours, against
`results/02_bias_by_price_band.csv`).

**Positive-price baseline: price ≥ 0.** Matching Q0's Anchor T and the brief's wording.
It is also the conservative choice: it includes the 0–5 band, where Hirth (2026)
Table 3 finds 4.2% wind curtailment and `docs/06` measured the operational projection's
ratio already elevated (50Hertz 1.098 at 0–5 against 1.040 above 5), so the ≥ 0
baseline gap is the *larger* of the two and clause A the harder to pass. Price > 5 is
reported beside it and decides nothing.

**Inference.** 95% event-day block bootstrap, 5,000 draws, seed 42, Berlin-local days,
no shuffling. The difference in clause A is resampled **paired**: each drawn day brings
both its negative-price sums and its positive-price sums, so the interval respects the
day structure both sides share.

## 4. The criterion — student's, verbatim

> **H counts as adding back market curtailment if the negative-price gap exceeds the
> positive-price gap with a CI excluding zero, AND rises monotonically with depth
> across the bands.**

Operationalised, before any number:

- **Clause A.** `D = gap_share(price < 0) − gap_share(price ≥ 0)`. **Passes iff the 95%
  CI of D lies entirely above zero.**
- **Clause B.** The four band shares are **non-decreasing from shallow to deep**:
  `g(−5,0) ≤ g(−20,−5] ≤ g(−50,−20] ≤ g(≤−50)`, on point estimates. "Monotonically"
  is read as non-decreasing; with continuous data an exact tie is not expected, and a
  tie does not break it.
  - A band with no quarter-hours cannot enter. **If fewer than three bands have data,
    clause B is NOT TESTABLE.**
  - A band with fewer than five event-days still enters clause B on its point estimate,
    and is labelled *point estimate, no inference* wherever it appears (the reporting
    rule `docs/09` Amendment 4 A4.5 set for the thin −20 to −5 band).

**Verdict, per area and for the aggregate:**

| | |
|---|---|
| **ADDS BACK** | A passes and B passes |
| **DOES NOT ADD BACK** | A fails, or B fails with at least three bands testable |
| **INDETERMINATE** | A's interval cannot be formed, or B is not testable |

**Which result decides.** The aggregate over **50Hertz + Amprion + TransnetBW** decides
Anchor H's status. **TenneT is excluded from it and reported on its own**: `docs/09`
Amendment 4 A4.5 makes T-D(vii) a precondition — no DE-level aggregate may use the
projection while TenneT's 0.839 positive-price ratio is unexplained — and nothing here
explains it. The four per-area verdicts are reported and do not decide.

## 5. The comparison with the forecast — reported, decides nothing

Two forms, both requested:

1. **The kill test as published.** `results/02_bias_by_price_band.csv`,
   `e_over_forecast_pct` per band and area — onshore plus offshore, `G − F` as a share
   of `F`, its own sample. Quoted as it stands.
2. **The matched form.** On exactly the quarter-hours that enter Q0b, onshore, the
   same statistic with `F` in place of `H`: `sum(F − G − R) / sum(F)` per band. This is
   the like-for-like figure, because the forecast is also uncurtailed by construction —
   it is frozen before the auction and cannot see the price.

**A reading fixed now.** If H adds back curtailment, its negative-price gap share
should be of the same order as the forecast's, since both are meant to describe the
uncurtailed fleet. A negative-price gap for H far below the forecast's would say H
follows the curtailed output.

## 6. What the verdict does to Q1 — and what it does not

**Nothing in Q1's design moves under any verdict.** The σ = 0.066 grid point is a
grid point and stays. What changes is only the *label* Q1's write-up may attach to it:

| Q0b verdict | how Q1 may describe σ = 0.066 |
|---|---|
| ADDS BACK | "Anchor H, a measured potential estimator" — with Q0 Amendment 1's lower-bound caveat |
| DOES NOT ADD BACK | "the noise level of the operational projection against output" — **not** a potential estimator, and not described as one |
| INDETERMINATE | "Anchor H" with the verdict stated beside it |

## 7. If the quality-assured series cannot be fetched

`docs/Q_STOP_Q0b.md` records what was tried. Q0b is then computed on the **operational**
series already on disk (2026-09-01 to 2026-10-28, about 58 days), labelled as that
series everywhere, and its verdict carries the label *operational series only*. Its
negative-price sample is thin — `docs/06` records nine days carrying a negative
quarter-hour in this window — so INDETERMINATE is the likely outcome there, and it is
stated as likely now so that it cannot be read later as a surprise.
