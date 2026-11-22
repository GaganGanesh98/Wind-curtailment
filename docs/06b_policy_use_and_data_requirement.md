# Experiment 3 in use: policy questions and data requirement

Derived from stored artifacts only, nothing re-fitted (`src/experiments/exp3_policy_use.py`).
Sources: `artifacts/exp3_data_requirement.parquet` and `artifacts/exp3_policy_use.parquet`,
built from `artifacts/exp1_known_truth_validation/noise_dial_summary.csv`,
`artifacts/exp3_german_application/bias_robust_full_window_cells.csv`, `breakdown_points.csv`,
`results_table.csv`, `artifacts/available_power_estimate/error_anchors.csv` and
`data/reference/eeg_negative_price_rules.csv`. Figure `figures/13_data_requirement.png`.

## Data requirement

<!-- generated:exp3_data_requirement -->
| quantity | highest informative σ (synthetic, best case) | H's measured σ | largest informative B on real data | breakdown B (V0 reading) | accuracy needed |
|---|---|---|---|---|---|
| λ₁ | ≥ 0.35 (top of grid) | 0.066 | 0.03 | 0.04 (informative) | its reading (informative) needs a bias below 0.04; its range stays narrow for a bias up to 0.03 |
| λ₂ | ≥ 0.35 (top of grid) | 0.066 | range not narrow on real data at B = 0 | 0.06 (lower bound at least 0.5) | its reading (lower bound at least 0.5) needs a bias below 0.06 |
| λ₃ | ≤ 0.12 | 0.066 | range not narrow on real data at B = 0 | > 0.15 (upper bound at most 0.75) | its reading (upper bound at most 0.75) survives every tested bias (> 0.15); a narrow range needs σ ≤ 0.12 (synthetic, best case) |
| λ₄ | ≤ 0.033 | 0.066 | range not narrow on real data at B = 0 | no reading | a narrow range needs σ ≤ 0.033 (synthetic, best case) |
| λ₅ | ≤ 0.033 | 0.066 | range not narrow on real data at B = 0 | no reading | a narrow range needs σ ≤ 0.033 (synthetic, best case) |
| λ₆ | ≤ 0.066 | 0.066 | range not narrow on real data at B = 0 | 0.04 (upper bound at most 0.5) | its reading (upper bound at most 0.5) needs a bias below 0.04; a narrow range needs σ ≤ 0.066 (synthetic, best case) |
| λ₇ | not identifiable with perfect data | 0.066 | not identifiable with perfect data | no reading | not identifiable with perfect data |
<!-- /generated -->

- σ is the highest noise level on the Experiment 1 grid at which the quantity is informative in
  at least half the synthetic cells, the rule behind the σ ≤ 0.033 of `docs/06`. It is a best
  case, not a guarantee: real data are far less informative than the synthetic cells at the
  same noise level, and the gap is unexplained (`docs/07_limitations_and_future_work.md`).
- B is the largest bias allowance at which the real-data range is still informative (width
  below a quarter of its widest possible range). The breakdown B is the smallest allowance at
  which the pre-registered reading fails. The reading names the V0 threshold, not the result.
- H's measured σ and bias are from positive-price quarter-hours. Its bias during negative
  prices is not measured.

## Policy use

<!-- generated:exp3_policy_use -->
| quantity | policy question | EEG cohort(s) (rule rows) | current range, full window, B = 0 | verdict | data requirement |
|---|---|---|---|---|---|
| λ₁ | At moderately negative prices (−20 to −5 €/MWh), what share of exposed wind capacity switches off? | all cohorts (R01, R02, R04, R07, R09, R10, R12) | [0.300, 0.508] | fragile (breakdown 0.04) | its reading (informative) needs a bias below 0.04; its range stays narrow for a bias up to 0.03 |
| λ₂ | At deeply negative prices (−50 €/MWh or lower), what share of exposed wind capacity switches off? | all cohorts (R01, R02, R04, R07, R09, R10, R12) | [0.525, 0.860] | robust (breakdown 0.06) | its reading (lower bound at least 0.5) needs a bias below 0.06 |
| λ₃ | Do plants commissioned before 2016, which no negative-price rule reaches, switch off? | pre2016_in_support_no_s51 (R01) | [0.000, 0.579] | robust (breakdown > 0.15) | its reading (upper bound at most 0.75) survives every tested bias (> 0.15); a narrow range needs σ ≤ 0.12 (synthetic, best case) |
| λ₄ | Do plants that earn nothing at any negative price (out of support, or under the post-February-2025 rule) switch off, taken together? | out_of_support+post_feb2025_qh (R01, R09) | [0.002, 0.996] | not identifiable | a narrow range needs σ ≤ 0.033 (synthetic, best case) |
| λ₅ | How much more energy would the 2023 to February 2025 cohort hold back if it lost support at every negative price? | wind2023_feb2025_staircase (R07) | [0.0, 533.2] GWh | not identifiable | a narrow range needs σ ≤ 0.033 (synthetic, best case) |
| λ₆ | Do the pre-2016 plants respond differently from the plants that earn nothing at any negative price? | pre2016_in_support_no_s51+out_of_support+post_feb2025_qh (R01, R09) | [-0.967, 0.398] | fragile (breakdown 0.04) | its reading (upper bound at most 0.5) needs a bias below 0.04; a narrow range needs σ ≤ 0.066 (synthetic, best case) |
| λ₇ | Do out-of-support plants switch off, on their own? | out_of_support (R01) | [0.000, 1.000] | not identifiable | not identifiable with perfect data |
| post-Feb-2025 cohort | Do plants under the post-February-2025 rule, which lose support in every negative quarter-hour, switch off? | post_feb2025_qh (R09) | none | not identifiable | No quantity identifies this cohort. It is exactly collinear with out_of_support on the real window (same exposure in every quarter-hour) and enters only λ₄, merged with it, which has no reading. |
<!-- /generated -->

Verdicts come from each reading's breakdown point against H's measured bias, not from the
informativeness rule, so a one-sided bound can be robust while the full range is wide (λ₂).

A verdict is robust when the reading still holds at B = 0.05, the first tested allowance at or
above H's measured bias of 0.0472, fragile when it breaks at or below that, and not identifiable
when the quantity has no reading.

EEG rule rows referred to above, with the rule table's legal source column:

<!-- generated:exp3_policy_rules -->
| rule | commissioned | trigger | legal source (legal_basis column) |
|---|---|---|---|
| R01 | … to 2015-12-31 | none - section 51 not applicable | Section 24(3) no. 1 EEG 2014 (in force 1 Aug 2014 - 31 Dec 2016, BGBl. I 2014 S. 1066) excludes installations commissioned before 1 Jan 2016. Continued by section 100(1) EEG 2017 as enacted by Art. 1 EEAusG, G. v. 13.10.2016, BGBl. I S. 2258. |
| R02 | 2016-01-01 to 2020-12-31 | >=6 consecutive hours | Section 24(1) EEG 2014, 'Verringerung der Foerderung bei negativen Preisen' (in force 1 Aug 2014 - 31 Dec 2016, BGBl. I 2014 S. 1066): six consecutive negative hours on the EPEX Spot SE hourly contracts for the DE/AT price zone. Exemptions in section 24(3) no. 2 (wind below 3 MW), with section 32(1) sentence 1 EEG 2014 for aggregation. Renumbered to section 51 EEG from 1 Jan 2017 with the same six-hour trigger, and retained for these installations by the EEG 2021 transitional provision. |
| R04 | 2021-01-01 to 2022-12-31 | >=4 consecutive hours | Section 51(1) EEG 2021 in the version in force 1 Jan 2021 - 31 Dec 2022 (Art. 1 EEG2021-EG, G. v. 21.12.2020, BGBl. I S. 3138); exemption in section 51(2) no. 1. |
| R07 | 2023-01-01 to 2025-02-24 | >=2 consecutive hours (applies in calendar year 2026) | Section 51(1) no. 3 EEG 2023 in the version in force 1 Jan 2023 - 24 Feb 2025. Keyed to the CALENDAR YEAR in which the spot price is negative, not to the installation's commissioning year: section 51(1) reads 'Wenn der Spotmarktpreis [im Jahr X] ... negativ ist', so the year qualifies the price condition. The commissioning date decides only WHICH VERSION of section 51 applies (section 100(46) EEG 2023). THIS IS THE STEP IN FORCE FOR THIS COHORT FROM 1 JAN 2026, I.E. INSIDE THE KILL-TEST SAMPLE. |
| R09 | 2025-02-25 to … | any quarter-hour with a negative spot price | Section 51(1) EEG 2023 as amended by Art. 4 EnWGEUVAendG, G. v. 21.02.2025, BGBl. 2025 I Nr. 51, in force 25 Feb 2025. Also applies where the anzulegender Wert was set in a tender with a bid date from 25 Feb 2025. |
| R10 | 2025-02-25 to … | exempt until the end of the calendar year in which a smart metering system is installed | Section 51(2) sentence 1 no. 1 EEG 2023. Installation size is determined by applying section 24 (aggregation of installations). |
| R12 | … to … | exempt (versions in force before 25 Feb 2025) | Section 24(3) no. 3 EEG 2014 exempts 'Demonstrationsprojekte'. From 1 Jan 2017 the exemption is recast as pilot wind: section 51(3) nos. 3-4 EEG 2017, section 51(2) nos. 2-3 EEG 2021 and EEG 2023 pre-2025 (pilot wind onshore per section 3 no. 37(b) EEG, pilot wind offshore per section 3 no. 6 WindSeeG). No such exemption appears in the version in force from 25 Feb 2025. |
<!-- /generated -->
