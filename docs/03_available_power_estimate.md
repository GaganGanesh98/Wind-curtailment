# Available-power estimate

**Question.** How good, and how biased, is the best public estimate of available power?

**What was done.**
- The quality-assured Online-Hochrechnung (H, EEG Anlage 1 Nr. 5.1) and the TSO day-ahead
  forecast (F) were compared with metered output at positive prices, where no plant has a
  market reason to switch off: their noise σ and bias, per area.
- A pre-registered test asked whether H adds back market curtailment: does the gap between H
  and output plus redispatch grow at negative prices?

**Pre-registrations.** `archive/docs/Q0_preregistration.md` (commit `b261c9f`, with Amendment
1); `archive/docs/Q0b_preregistration.md` (commit `06de287`). TenneT is excluded from the
aggregate (supervisor minute T-D(vii)).

**Noise and bias at positive prices** (`artifacts/available_power_estimate/h_anchor_by_series.csv`
for H on both series, `artifacts/available_power_estimate/error_anchors.csv` for F on all of DE).
The quality-assured series on the Experiment 3 window is the H anchor; the operational series
covers September and October 2026 only and is reported for comparison. Until 22 Nov 2026 this
table labelled the operational row as quality-assured. A row against G + R is kept in the CSV
but not shown: the redispatch series includes solar and offshore (`docs/07_limitations_and_future_work.md`).

<!-- generated:available_power_anchors -->
| estimate | window | area | quarter-hours | event days | σ | 95% interval | bias | 95% interval |
|---|---|---|---|---|---|---|---|---|
| projection H, quality-assured (primary) | 2025-10-01 to 2026-09-30 | 50Hertz+Amprion+TransnetBW | 32,885 | 364 | 0.0610 | [0.0548, 0.0674] | -0.0326 | [-0.0357, -0.0297] |
| day-ahead forecast F, same quarter-hours | 2025-10-01 to 2026-09-30 | 50Hertz+Amprion+TransnetBW | 32,885 | 364 | 0.2096 | [0.1934, 0.2258] | -0.0212 | [-0.0353, -0.0072] |
| projection H, operational (for comparison) | 2026-09-01 to 2026-10-28 | 50Hertz+Amprion+TransnetBW | 5,131 | 55 | 0.0660 | [0.0511, 0.0800] | -0.0472 | [-0.0562, -0.0387] |
| day-ahead forecast F, same quarter-hours | 2026-09-01 to 2026-10-28 | 50Hertz+Amprion+TransnetBW | 5,131 | 55 | 0.2270 | [0.1678, 0.2874] | +0.0325 | [-0.0069, +0.0790] |
| day-ahead forecast F, all quarter-hours | from 2025-10-01 | DE | 35,577 | 392 | 0.1806 | [0.1657, 0.1952] | -0.0037 | [-0.0149, +0.0078] |
<!-- /generated -->

**Does H add back market curtailment?** D = gap share at negative prices minus gap share at
price ≥ 0, quality-assured series (`artifacts/available_power_estimate/adds_back_verdicts.csv`):

<!-- generated:available_power_adds_back -->
| area | D | 95% interval | verdict |
|---|---|---|---|
| 50Hertz+Amprion+TransnetBW | +0.2893 | [+0.2484, +0.3344] | ADDS BACK |
| 50Hertz | +0.2866 | [+0.2406, +0.3355] | ADDS BACK |
| Amprion | +0.2944 | [+0.2563, +0.3365] | ADDS BACK |
| TransnetBW | +0.2861 | [+0.2312, +0.3421] | ADDS BACK |
| TenneT (excluded from the aggregate) | +0.3106 | [+0.2656, +0.3560] | ADDS BACK |
<!-- /generated -->

**Verdict (quoted):** "**ADDS BACK**, on the deciding aggregate and independently in every one of
the four control areas." H is supporting evidence of potential, not ground truth; its σ is a
lower bound on its error, and its bias was measured at positive prices only.

**Figure.** `figures/03_available_power_gap_by_band.png`.

**Full detail.** `archive/docs/Q0_preregistration.md` §1, `archive/docs/Q0b_results.md`.
