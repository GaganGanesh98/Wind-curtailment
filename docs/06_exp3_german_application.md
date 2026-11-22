# Experiment 3 — German application

**Question.** On real data, which readings hold, and how much bias in H does each survive?

**What was done.**
- 50Hertz + Amprion + TransnetBW, 2025-10-01 to 2026-09-30, award setting `main`, H as the
  potential: identified sets for λ₁–λ₇ on the full window and on each month with a published
  market value and a negative-price quarter-hour.
  The window ends on 2026-09-30 because October 2026 has no published market value. The
  October end date in the caption of figure `02` belongs to the forecast-bias check, not here.
- The bias-robust full-window sets for B from 0 to 0.15, and the breakdown point of each reading.
- The monthly verdict per quantity by the rule pre-registered in C0.

**Pre-registrations.** `archive/docs/Q5_preregistration.md` (commit `60efa6e`);
`archive/docs/V0_preregistration.md` (commit `3277ea6`); `archive/docs/C0_preregistration.md`
(commit `a67f69a`).

**Results** (`artifacts/exp3_german_application/results_table.csv`, `breakdown_points.csv`;
λ₅ in GWh):

<!-- generated:exp3_results -->
| quantity | what it is | full-window interval, H | robust reading | breakdown bias B | informative months, H | monthly verdict (C0 rule) |
|---|---|---|---|---|---|---|
| λ₁ | fleet response at depth (−20, −5] €/MWh | [0.300, 0.508] | informative: between 0.300 and 0.508 | 0.04 | 2/8 | NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE |
| λ₂ | fleet response at depth ≤ −50 €/MWh | [0.525, 0.860] | one-sided: at least 0.525 | 0.06 | 1/3 | NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE |
| λ₃ | pre-2016 cohort response | [0.000, 0.579] | one-sided: at most 0.579 | > 0.15 | 0/9 | NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE |
| λ₄ | merged θ ≡ 0 group (collinear pair) | [0.002, 0.996] | no reading: neither bound excludes a quarter of the range | — | 0/10 | NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE; WOULD NEED A MORE ACCURATE ESTIMATE: σ ≤ 0.033, within the tested synthetic conditions |
| λ₅ | counterfactual energy, GWh (threshold moved to 0) | [0.0, 533.2] | no reading: neither bound excludes a quarter of the range | — | 0/10 | NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE; WOULD NEED A MORE ACCURATE ESTIMATE: σ ≤ 0.033, within the tested synthetic conditions |
| λ₆ | cohort contrast λ₃ − λ₄ | [-0.967, 0.398] | one-sided: at most 0.398 | 0.04 | 0/9 | NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE |
| λ₇ | one member of the collinear pair | [0.000, 1.000] | no reading: neither bound excludes a quarter of the range | — | 0/10 | NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE |
<!-- /generated -->

Readings: λ₁ is a fleet response; λ₂'s reading is a lower bound on response, λ₃'s and λ₆'s are
upper bounds. Breakdown points are reported for the four readings pre-registered in V0.
λ₃'s result is an upper bound of 0.579. The 0.75 in its V0 reading is the pre-registered
threshold at which that reading breaks, not a result.

**Verdicts (quoted).**
- Monthly: "**NOT IDENTIFIABLE WITH TODAY'S BEST PUBLIC ESTIMATE** (7 of 7)."
- Robust readings: "λ₁'s informative full-window reading and λ₆'s one-sided bound survive a
  constant bias of up to 0.03 in the projection, and break at 0.04. λ₂'s lower bound survives up
  to 0.05 and breaks at 0.06. λ₃'s one-sided bound survives the whole tested range."
<!-- generated:h_scale_line -->
- For scale only: H's measured bias on price ≥ 0 quarter-hours is −0.0326 (quality-assured series, Experiment 3 window; operational series −0.0472; against G + R −0.0003); its bias during negative prices is not measured.
<!-- /generated -->

**Figure.** `figures/09_exp3_bias_breakdown.png`.

**Full detail.** `archive/docs/Q5_results.md`, `archive/docs/V_results.md` (V2),
`archive/docs/C1_conclusions_table.md`.
