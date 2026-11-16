# Q0b — results: the quality-assured projection adds back market curtailment

Pre-registration `docs/Q0b_preregistration.md`, commit **`06de287`**, committed before the
series was fetched and before any number below existed. Every figure is re-derived from
its artifact by `tests/test_reported_numbers.py` under `pytest`.

## 1. Verdict

**ADDS BACK**, on the deciding aggregate and independently in every one of the four
control areas. Both clauses pass everywhere, with all four price bands populated.

| series | area | clause A: D | 95% CI | clause B | bands | verdict |
|---|---|---|---|---|---|---|
| **quality-assured** | **50Hertz + Amprion + TransnetBW** | **+0.2893** | [+0.2484, +0.3344] | **pass** | 4 | **ADDS BACK — decides** |
| quality-assured | 50Hertz | +0.2866 | [+0.2406, +0.3355] | pass | 4 | ADDS BACK |
| quality-assured | Amprion | +0.2944 | [+0.2563, +0.3365] | pass | 4 | ADDS BACK |
| quality-assured | TransnetBW | +0.2861 | [+0.2312, +0.3421] | pass | 4 | ADDS BACK |
| quality-assured | *TenneT, excluded from the aggregate* | *+0.3106* | *[+0.2656, +0.3560]* | *pass* | *4* | *ADDS BACK* |
| operational | 50Hertz + Amprion + TransnetBW | +0.3616 | [+0.2889, +0.4375] | not testable | 2 | INDETERMINATE |

`artifacts/Q0b/q0b_verdicts.csv`, columns `D`, `D_lo`, `D_hi`, `clause_b`,
`bands_with_data`, `verdict`. `D` is the gap share at negative prices minus the gap
share at price ≥ 0, resampled paired over all 391 days of the window.

**The operational series is INDETERMINATE, as the pre-registration predicted** (§7): its
two months contain only the two shallowest bands, so clause B cannot be tested. Clause
A passes there too. It does not decide.

## 2. The four bands, against the forecast

Deciding aggregate, quality-assured series. Gap share = `sum(P − G − R) / sum(P)`, where
`P` is the projection `H` or the day-ahead forecast `F`. `artifacts/Q0b/q0b_gap_shares.csv`,
column `gap_share`, with `ci_lo` and `ci_hi`.

| quarter-hours | projection H | 95% CI | forecast F | event-days |
|---|---|---|---|---|
| price ≥ 0 | 0.0214 | [0.0174, 0.0259] | −0.0101 | 391 |
| price > 5 | 0.0157 | — | −0.0106 | 390 |
| **price < 0** | **0.3107** | [0.2693, 0.3542] | **0.0933** | 99 |
| band (−5, 0) | 0.2469 | [0.2201, 0.2786] | 0.0493 | 99 |
| band (−20, −5] | 0.4025 | [0.3362, 0.4560] | 0.1125 | 38 |
| band (−50, −20] | 0.5453 | [0.4757, 0.5808] | 0.2681 | 20 |
| band ≤ −50 | 0.6799 | [0.5810, 0.7326] | 0.5296 | 12 |

- **Clause B passes strictly**: 0.247, 0.403, 0.545, 0.680, rising at every step. Every
  band carries at least 12 event-days, so none is a point estimate without inference.
- **The projection's negative-price gap is 3.3 times the forecast's** (0.3107 against
  0.0933), and larger in every band.
- **Clause A also passes for the forecast**, but with a smaller D: +0.1033
  [+0.0567, +0.1444] on the aggregate (`F_D` in `q0b_verdicts.csv`). In 50Hertz the
  forecast's CI includes zero ([−0.0028, +0.1117]), and in TenneT the forecast shows no
  difference at all (−0.0018, [−0.0889, +0.0730]).

**Against the pre-registered reading.** `docs/Q0b_preregistration.md` §5 fixed one
reading in advance: a projection gap *far below* the forecast's would mean the
projection follows curtailed output. **That branch is not met — the difference runs the
other way.** The reading did not anticipate the projection exceeding the forecast by a
factor of 3.3, and two explanations fit it, which Q0b cannot separate:

1. **The forecast is partly curtailment-aware.** TSO forecast models are trained on
   recorded output, which includes curtailment, so F may already run below potential in
   the weather that comes with negative prices. Then F's 9.3% understates the true
   switched-off share and the projection's 31% is closer to it.
2. **The projection over-projects at negative prices.** If the reference plants behind
   the extrapolation switch off less than the fleet does, the projection would keep
   rising with depth for a reason other than tracking potential.

Separating these is exactly the question P2 exists to answer with a weather-based
potential. It is recorded here as open, not resolved.

**Context only, not a like-for-like comparison.** Hirth (2026) Fig. 12 reports pooled
wind response rates of 0.25 to 0.61 across his exposed-side profit-margin bands
(`HIRTH_FIG12_WIND_RESPONSE` in `src/censoring/baselines.py`, read from the figure,
`[VERIFY]`). The projection's 0.25 in the shallowest band and 0.68 in the deepest sit in
that range. His bands are by profit margin on exposed capacity, these are by price on the
whole fleet, so the agreement is one of scale, not a test.

## 3. Redispatch is not what produces the gap

Redispatch `R` as a share of `H`, `sum(R) / sum(H)`, quality-assured series
(`artifacts/Q0b/q0b_gap_shares.csv`, column `r_share`, estimator H):

| | price < 0 | price ≥ 0 |
|---|---|---|
| 50Hertz + Amprion + TransnetBW | 3.38% | 1.65% |
| TenneT | 13.55% | 12.79% |

On the deciding aggregate redispatch is a twentieth of the 31% negative-price gap, so
mis-recorded redispatch cannot account for it. **TenneT is different**: its redispatch is
roughly 13% of the projection *at positive prices as well*. That is relevant to the
T-D(vii) precondition. `results/39_nr51_compliance.csv` records TenneT's ratio
`H / (G + R)` at 0.839 on positive prices, and a large `R` in that denominator would pull
the ratio down. On the quality-assured series TenneT's positive-price gap share is
**−0.0691** — the projection sits *below* `G + R` — where every other area sits above.
**`[VERIFY]` — a candidate explanation, not tested here.** T-D(vii) stays
open and TenneT stays excluded from every aggregate.

## 4. The fetch

| | |
|---|---|
| series | *Online-Hochrechnung qualitätsgesichert Wind Onshore* |
| route | the public Netztransparenz page's own date range and "CSV Download", no login; the credentialed WebAPI was not used and the data centre's undocumented API was not scripted |
| range requested | 01.10.2025 to 31.10.2026, timezone ME(S)Z; the series' own bounds are 2012-01-01 to 2026-10-31 |
| file | `data/raw/netztransparenz/hochrechnung_wind_onshore_qualitaetsgesichert/online_hochrechnung_wind_onshore_qs_2025-10-01_2026-10-31_dl2026-11-15.csv`, read-only |
| sha256 | `c5a7f961034886b0ec9a88faaf7eaa40fa3aaf767516d15b68d9fb0f96fad5b4` |
| rows | **38,020** quarter-hours, 2025-10-01 00:00 to 2026-10-31 23:45 — exactly 396 days × 96, plus 4 for each of the two autumn changeovers and minus 4 for the spring one; **0 empty cells** in any area |

The file is in its own folder, deliberately. `src/check_nr51_compliance.py:load_projection`
globs one folder, and the operational files that `results/39` was validated on live in
the other; the loader gained a `hr_dir` argument whose default is unchanged, verified by
hashing its output before and after (`9736de4dbe1cb8dc` both times). The browser
download also left a temporary file in `~/Downloads`, which was copied, not opened in
place.

**Window used: 2025-10-01 to 2026-10-28.** The projection runs to 31 October, but the
redispatch export and the panel both stop on 28 October, and Q0b needs all three.

## 5. What this does to Q1

**σ = 0.066 may be described as "Anchor H, a measured potential estimator"** — the
ADDS BACK branch of `docs/Q0b_preregistration.md` §6 — with Q0 Amendment 1's
lower-bound caveat attached. Nothing in Q1's design moves.

Two facts from the same run that bear on that label, in
`artifacts/Q0b/q0b_h_agreement.csv`:

| series | area | σ of log(G/H), price ≥ 0 | 95% CI | corr(H, G) | n QH | event-days |
|---|---|---|---|---|---|---|
| quality-assured | 50Hertz + Amprion + TransnetBW | **0.0607** | [0.0544, 0.0667] | 0.9954 | 35,474 | 391 |
| operational | 50Hertz + Amprion + TransnetBW | 0.0660 | [0.0511, 0.0800] | 0.9959 | 5,131 | 55 |

- **The anchor is stable across series and period**: 0.061 on thirteen months of the
  quality-assured series against 0.066 on two months of the operational one. The Q1 grid
  point at 0.066 stays where it is; the difference is inside the operational series'
  interval.
- **H and G agree to a correlation of 0.995 or better on the aggregate, and 0.991 to
  0.997 in every area.** This is the measurement Q0 Amendment 1 cites.

## 6. Limitations

1. **The verdict says H rises with depth; it does not say H equals potential.** Clause B
   tests direction, not level, and §2 records that the level exceeds the forecast's by a
   factor Q0b cannot explain.
2. **Redispatch is allocated evenly** across each measure's duration at its mean power,
   the only allocation the export supports (`redispatch_qh`'s docstring). A measure that
   was in fact concentrated inside a negative-price run would be under-counted there.
   On the aggregate the whole of `R` is 3.4% of `H`, which bounds how much that can matter.
3. **TenneT's verdict is reported and does not decide**, under T-D(vii).
4. **The window stops on 28 October 2026** because the redispatch export does.
