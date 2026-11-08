# 14 — The market-value coverage gap: cause, fix, and what it changes

Run 8 Nov 2026 on branch `identification-fix`, while the 81-cell merged regeneration was
still running; read-only with respect to it. Follows `docs/13_theta_audit.md`, which
reported study-window coverage of 69.4%.

**Headline.** The cause was a one-line hard-coding: `read_published` defaulted to
`Monatsmarktwerte_2026.csv` alone, while `Monatsmarktwerte_2025.csv` — all twelve months
of 2025 — had been sitting in the same directory since 1 Nov. Nothing had to be fetched.
Fixed, coverage goes **69.4% → 92.9%** and exposed quarter-hours **1,853 → 2,052**.

**But the identification verdict does not change.** Two of the three recovered months have
**zero negative-price quarter-hours**, so they add coverage and no identifying variation
whatever. The entire gain is October 2025. Tier 1 remains identified at AW `high`, weakly
at `main`, and not identified at `low` or under stress.

**And the task's prior is wrong, for an instructive reason.** The expectation was that
winter months would help because high wind depresses the capture rate. The capture rate is
not what binds: **MP depends on MV's absolute level against the award values**, and a low
capture rate on a high price level still gives a high MV. The month that helped is a
shoulder month, October 2025, with the lowest capture rate in the entire series (0.661).

---

## Step 1 — which months were missing

Study window: 13 months, 2025-10 … 2026-10 (the panel ends 2026-10-28).

| month | published MV before the fix | classification |
|---|---|---|
| 2025-10 | **missing** | **should exist** — file on disk, never read |
| 2025-11 | **missing** | **should exist** — file on disk, never read |
| 2025-12 | **missing** | **should exist** — file on disk, never read |
| 2026-01 … 2026-09 | present | — |
| 2026-10 | missing | **legitimately unavailable** |

**The publication lag, observed rather than assumed.** `Monatsmarktwerte_2026.csv` has an
mtime of 31 Oct 2026 and carries values through **Sep 2026**, so the previous complete month
was available within about a month of its end. Recorded as
`MV_PUBLICATION_LAG_MONTHS = 1`. 2026-10 is doubly unavailable: the month had not ended when
the file was taken, and it is incomplete in the panel too (2,692 of ~2,976 quarter-hours).

So **three of the four gaps were our own**, and one is real.

---

## Step 2 — the data was already on disk

```
data/raw/netztransparenz/
  Monatsmarktwerte_2024.csv     1,062 B   2026-11-01
  Monatsmarktwerte_2025.csv     1,198 B   2026-11-01   <- all 12 months of 2025
  Monatsmarktwerte_2026.csv     1,171 B   2026-10-31   <- the only file read
```

`src/ingest_market_values.py:79` read `PUBLISHED = … / "Monatsmarktwerte_2026.csv"`, a
single hard-coded path, with no glob. The 2025 file contains the rows
`Spotmarktpreis`, `MW Wind an Land`, `MW Wind auf See`, `MW Solar` for Jan–Dec 2025, in the
same format. The three months the audit was missing are in it:

| month | MW Wind an Land | → EUR/MWh |
|---|---|---|
| Okt 2025 | 5,579 ct/kWh | **55.79** |
| Nov 2025 | 8,930 | **89.30** |
| Dez 2025 | 8,349 | **83.49** |

**Nothing was fetched and there is no URL to cite.** The year is parsed from each column
header, not from the filename, so reading every file is safe.

### Validation of the recovered months

The published `Spotmarktpreis` row should equal the panel's simple monthly mean price. It
does, for **32 of the 33** months now read, to within 0.05 EUR/MWh — including all three
recovered months exactly (2025-10: 84.40 = 84.40; 2025-11: 101.88; 2025-12: 93.47). So the
2025 file is the right series for the right months.

> **Flagged, outside this task's scope.** The one mismatch is **2024-06: published 84.45
> against a panel mean of 72.89, +11.56 EUR/MWh**. It is also the only month in the whole
> series where the published market value sits *above* the recomputation (+3.72 rather than
> the usual negative gap). Two anomalies in the same column suggest the 2024 file's June
> entry is wrong or misaligned. 2024 is outside the E1/E2 window — but it is squarely
> inside **E3**'s input range, so this needs resolving before E3 runs. Not touched here.

---

## Step 3 — the fix, and the test that was missing

`read_published()` now globs `Monatsmarktwerte_*.csv` and concatenates, raising if a month
appears twice with different values — a silent overwrite would be worse than the gap. An
explicit `path=` still reads one file, which the tests use. `jw_2026_ytd` already filtered
`year == 2026`, so the added 2025 rows do not disturb it; verified.

`tests/test_market_value_coverage.py`, 5 tests, is the assertion that was absent. The gap
survived because **nothing checked for it**: every month of the study window except the
panel's final one must now have a published market value, and one test pins the actual bug
by asserting that the old single-file default cannot cover the window.

### Coverage, old next to new

| | before | after |
|---|---|---|
| months with a published MV, in window | 9 of 13 | **12 of 13** |
| study-window quarter-hours usable | 26,204 (69.4%) | **35,040 (92.9%)** |
| exposed quarter-hours | 1,853 | **2,052** |
| months with exposed quarter-hours | 9 | **10** |

The 199 added exposed quarter-hours are exactly October 2025's negative-price count.
November and December 2025 have **zero** negative quarter-hours, so they raise coverage and
contribute nothing to identification.

### θ separation, old next to new

Share of exposed quarter-hours with ≥2 distinct θ, and months where θ is identically zero
fleet-wide:

| AW setting | ≥2 distinct, before | after | ≥3, before | after | flat months, before | after |
|---|---|---|---|---|---|---|
| low | 26.6% | **33.7%** | 26.6% | 33.7% | 8 of 9 | 10 of 12 |
| main | 62.5% | **66.2%** | 34.1% | 40.4% | 4 of 9 | 4 of 12 |
| high | 80.1% | **82.0%** | 61.8% | 65.5% | 0 of 9 | 0 of 12 |
| stress | 34.1% | **40.4%** | 27.6% | 34.6% | 7 of 9 | 7 of 12 |

The flat-month denominators are not comparable: 12 now includes November and December 2025,
which have no exposure at all. **Counted over months that actually have exposed
quarter-hours** — ten of them — the flat counts are: low **8 of 10**, main **4 of 10**, high
**0 of 10**, stress **7 of 10**. October 2025 is not flat at any setting.

### Separating quarter-hours per month, by setting

Share of each month's exposed quarter-hours with ≥2 distinct θ.

| month | exposed | low | main | high | stress |
|---|---|---|---|---|---|
| **2025-10** | **199** | **100%** | **100%** | **100%** | **100%** |
| 2025-11 | 0 | — | — | — | — |
| 2025-12 | 0 | — | — | — | — |
| 2026-01 | 10 | 0% | 0% | 100% | 0% |
| 2026-02 | 23 | 0% | 100% | 100% | 0% |
| 2026-03 | 139 | 0% | 100% | 100% | 100% |
| 2026-04 | 492 | 100% | 100% | 100% | 100% |
| 2026-05 | 315 | 0% | 0% | 100% | 0% |
| 2026-06 | 199 | 0% | 100% | 100% | 0% |
| 2026-07 | 306 | 0% | 100% | 100% | 0% |
| 2026-08 | 226 | 0% | 0% | 0% | 0% |
| 2026-09 | 143 | 0% | 0% | 0% | 0% |

At AW `low`, separating months go from **one** (2026-04) to **two** (2025-10 and 2026-04).
Under `stress`, from two to three. That is the whole of the improvement.

### Three-channel attribution, old next to new

Mean number of distinct θ values each counterfactual channel yields, on the separating
exposed quarter-hours.

| channel | low | main | high | stress |
|---|---|---|---|---|
| actual | 4.49 → **4.47** | 3.19 → **3.37** | 3.83 → **3.90** | 3.19 → **3.25** |
| run-length / trigger alone | 2.00 → 2.00 | 2.00 → 2.00 | 2.00 → 2.00 | 2.00 → 2.00 |
| premium spread alone | 7.00 → **7.00** | 4.36 → **4.90** | 6.65 → **6.81** | 5.34 → **5.74** |
| support status alone | 2.00 → 2.00 | 2.00 → 2.00 | 2.00 → 2.00 | 2.00 → 2.00 |

Unchanged in structure: the premium spread remains much the richest channel, and the trigger
and support-status channels remain binary by construction.

---

## Step 4 — does the verdict change? No. And the prior is wrong.

**The verdict does not change.** Identified at AW `high`; weakly identified at `main` with
four of ten exposed months carrying no cohort structure at all; **not identified** at `low`
(two separating months out of ten) or under `stress` (three of ten). Rule 19 requires
stability across all three award settings, and two of the three still fail. Tier 1 remains
something to be decided, not assumed — `docs/06` §3 I4 (v1.9) stands as written.

**The prior — that winter months help because high wind depresses the capture rate — is
wrong here, and the reason is worth keeping.** The mechanism it describes is real, but it
reasons via the *capture rate* when the binding quantity is MV's *absolute level* against
the award values (74.06 – 89.21 EUR/MWh at `main`):

| month | capture rate | MV | negative QH | separates? |
|---|---|---|---|---|
| 2025-10 | **0.661** (lowest in the series) | 55.79 | 199 | yes, at every setting |
| 2025-11 | 0.877 | 89.30 | **0** | no exposure |
| 2025-12 | 0.893 | 83.49 | **0** | no exposure |
| 2026-09 | 0.755 (low) | **109.40** | 143 | **no** — MV above every AW |
| 2026-08 | 0.910 | **115.45** | 226 | **no** — MV above every AW |

September 2026 is the counterexample that settles it: a low capture rate (0.755) on a very
high price level (mean 144.82) still yields MV = 109.40, above every award value, so MP = 0
fleet-wide and the month contributes nothing despite 143 negative quarter-hours. The two
recovered *winter* months were useless for the opposite reason — prices were high and there
were **no negative quarter-hours at all**. What helped was a shoulder month whose MV was far
below every award value.

**The near-rule, and why it is only near.** A month is flat when the applicable reference
value exceeds every award value — but the reference differs by cohort, and that caveat is
load-bearing. At `main` the four flat months (2026-01, -05, -08, -09) are exactly those with
monthly MV above 89.21. November 2025 has MV 89.30, also above it, yet is **not** flat,
because `post_feb2025_qh` settles on the **annual** JW: JW 2025 = 74.41, so that cohort keeps
MP = 14.80 throughout 2025. Any shortcut test on the monthly MV alone would be wrong.

**The forward-looking risk this exposes.** The monthly market value rose through 2026 —
57.18 in April to 115.45 in August and 109.40 in September — while award values are fixed.
As wholesale prices rise relative to them, MP → 0 fleet-wide and cohort structure
disappears. The identification problem is not a quirk of a thin sample; it gets **worse** as
prices rise, and the months with the most negative quarter-hours are not reliably the months
with a live premium. That belongs in the write-up's limitations rather than being discovered
later.

---

## Reproducing

```
python -m src.censoring.theta_audit            # both steps, extended window
python -m pytest tests/test_market_value_coverage.py -q
```

Read-only. DE, no shuffling, `data/raw/` untouched — the 2025 file was read, not modified.
