# Post-hoc: audit of Hirth (2026) with the method, pre-registration

**Post-hoc.** Written on 23 Nov 2026, after the Experiment 3 results were known, and committed
before any audit range was computed. Hirth (2026, arXiv 2609.10053, version of 10 Nov 2026,
`literature/01_closest_work/Hirth_2026_Curtail-at-negative-prices_arXiv-v2.pdf`). Claims from
`data/reference/hirth_2026_claims.csv`, rows with `checked_by_me = yes` only, values as written
there. Code `src/experiments/hirth_audit.py`; the tables below are generated from it.

**Question.** For each of Hirth's published wind claims that the method can express: does
Hirth's value lie inside the identified range, and up to what bias in H does that verdict hold?

## Mapping

<!-- generated:hirth_mapping_counts -->
- Checked claims: 25. Compared with an identified set: 12. Compared as a plain number: 2. Not comparable: 11.
<!-- /generated -->

<!-- generated:hirth_mapping -->
| claim | Hirth's quantity | Hirth's period | Hirth's band | Hirth's value | method band (quarter-hour price) | matching quantity | comparability |
|---|---|---|---|---|---|---|---|
| H1a | response rate | 2025 | below -50 | 50.0 % (stated in words as half) | (−∞, −50] | band mean of ĉ divided by band mean of the exposed share e | period overlap partial, October to December 2025 only |
| H1b | curtailment rate | 2025 | below -50 | 50.0 % (stated in words as half) | (−∞, −50] | band mean of ĉ (fleet switched-off share), new band-mean functional | period overlap partial, October to December 2025 only |
| H2 | exposure rate | 2025 | below 0 | 64.0 % | (−∞, 0] | band mean of the exposed share e, a plain number (no bounds) | period overlap partial, October to December 2025 only |
| H3 | response rate | 2025 | below 0 | 27.0 % | (−∞, 0] | band mean of ĉ divided by band mean of the exposed share e | period overlap partial, October to December 2025 only |
| H4 | curtailment rate | 2025 | below 0 | 17.0 % | (−∞, 0] | band mean of ĉ (fleet switched-off share), new band-mean functional | period overlap partial, October to December 2025 only |
| H5 | curtailment rate | 2022 to Oct 2026 pooled | below -100 | 57.0 % | (−∞, −100] | band mean of ĉ (fleet switched-off share), new band-mean functional | period overlap partial, the whole window lies inside Hirth's period |
| H6 | curtailment rate | 2022 to Oct 2026 pooled | -100 to -50 | 51.0 % | (−100, −50] | band mean of ĉ (fleet switched-off share), new band-mean functional | period overlap partial, the whole window lies inside Hirth's period |
| H7 | curtailment rate | 2022 to Oct 2026 pooled | -50 to -20 | 35.0 % | (−50, −20] | band mean of ĉ (fleet switched-off share), new band-mean functional | period overlap partial, the whole window lies inside Hirth's period |
| H8 | curtailment rate | 2022 to Oct 2026 pooled | -20 to -10 | 22.0 % | (−20, −10] | band mean of ĉ (fleet switched-off share), new band-mean functional | period overlap partial, the whole window lies inside Hirth's period |
| H9 | curtailment rate | 2022 to Oct 2026 pooled | -10 to 0 | 15.0 % | (−10, 0] | band mean of ĉ (fleet switched-off share), new band-mean functional | period overlap partial, the whole window lies inside Hirth's period |
| H10 | curtailment rate | 2022 to Oct 2026 pooled | 0 to 5 (placebo) | 5.0 % | — | not comparable | price ≥ 0, where no cohort is exposed, so the method sets ĉ to 0 by construction and nothing is identified to compare |
| H11 | curtailment rate | 2022 to Oct 2026 pooled | above 5 (placebo) | -1.0 % | — | not comparable | price ≥ 0, where no cohort is exposed, so the method sets ĉ to 0 by construction and nothing is identified to compare |
| H12 | curtailment rate | 2026 (to Oct) | below -100 | 69.0 % | (−∞, −100] | band mean of ĉ (fleet switched-off share), new band-mean functional | period overlap partial, January to September 2026 |
| H13 | exposure rate | 2022 | below 0 | 92.0 % | — | not comparable | period does not overlap the Experiment 3 window |
| H14 | curtailment rate | 2022 | below 0 | 22.0 % | — | not comparable | period does not overlap the Experiment 3 window |
| H15 | response rate | 2022 | below 0 | 24.0 % | — | not comparable | period does not overlap the Experiment 3 window |
| H16 | exposure rate | 2023 | below 0 | 56.0 % | — | not comparable | period does not overlap the Experiment 3 window |
| H17 | curtailment rate | 2023 | below 0 | 18.0 % | — | not comparable | period does not overlap the Experiment 3 window |
| H18 | response rate | 2023 | below 0 | 32.0 % | — | not comparable | period does not overlap the Experiment 3 window |
| H19 | exposure rate | 2024 | below 0 | 57.0 % | — | not comparable | period does not overlap the Experiment 3 window |
| H20 | curtailment rate | 2024 | below 0 | 15.0 % | — | not comparable | period does not overlap the Experiment 3 window |
| H21 | response rate | 2024 | below 0 | 26.0 % | — | not comparable | period does not overlap the Experiment 3 window |
| H22 | exposure rate | 2026 (to Oct) | below 0 | 68.0 % | (−∞, 0] | band mean of the exposed share e, a plain number (no bounds) | period overlap partial, January to September 2026 |
| H23 | curtailment rate | 2026 (to Oct) | below 0 | 25.0 % | (−∞, 0] | band mean of ĉ (fleet switched-off share), new band-mean functional | period overlap partial, January to September 2026 |
| H24 | response rate | 2026 (to Oct) | below 0 | 37.0 % | (−∞, 0] | band mean of ĉ divided by band mean of the exposed share e | period overlap partial, January to September 2026 |
<!-- /generated -->

## Quantities

| Hirth's quantity | method quantity | form |
|---|---|---|
| curtailment rate | band mean of ĉ over the exposed quarter-hours whose price lies in the band, built as `functionals.band_mean` | linear in the response r |
| response rate | the same band mean divided by the band mean of the exposed share e = Σ_k w_k s_k | linear in r, since e comes from the law and MaStR and is fixed |
| exposure rate | the band mean of e | a plain number, no identified set |

- **Response rate as a ratio of band means.** Hirth writes curtailment rate = exposure rate ×
  response rate (Table 4), which is a ratio of aggregates. The mean of the per-quarter-hour
  ratios ĉ_t / e_t would also be linear in r; it is not used.
- **e is known and positive.** e is computed from the law and MaStR, award setting `main`, as in
  Experiment 3. Every negative-price quarter-hour of the Experiment 3 sample has e > 0, so the
  ratio is defined in every compared band.
- **New functionals only.** λ₁ to λ₇ and `functionals.py` are not changed. The new band means
  and ratios live in a new file in step 2.
- **Reproduction check.** H1b's band is λ₂'s band. Its identified set under the headline ĉ must
  equal λ₂'s Experiment 3 artifacts exactly at every B. If it does not, step 2 stops.

## Variants

- **Primary: the headline ĉ = 1 − G/H**, Experiment 3 unchanged.
- **Redispatch check: masks M0 and M1**, exactly as `docs/11_redispatch_sensitivity_preregistration.md`
  defines them, ε recomputed on each masked sample, and its arm rule unchanged: an arm with fewer
  than 20 event days reports counts only. G + R is never used.
- Fixed as in Experiment 3: window, the three areas, award setting `main`, potential H, the ε
  rule with event-day block bootstrap, the solver and the hull over |b| ≤ B.

<!-- generated:hirth_design -->
- Bias grids. Pre-registered V2 grid: b from −0.15 to 0.15 in steps of 0.01, hull S_B over |b| ≤ B for B = 0 to 0.15. Post-hoc fine grid (docs/10): b from −0.06 to 0.06 in steps of 0.0025.
- Comparison bias: 0.0326, the size of H's bias on the quality-assured series, Experiment 3 window, price ≥ 0 (`h_anchor_by_series.csv`, the H anchor). On the fine grid the verdict at that bias is read at B = 0.0350, the first allowance at or above it, as in docs/10.
- Not decidable: interval width above 0.75. The widest possible range is 1 for every compared quantity, so this is a width above 0.75.
- Masked variants M0 and M1, caveat: the redispatch export's unit check (mean MW × duration against MWh) fails for 1,322 of 7,067 renewable reduction measures (`redispatch_checks.csv`). It is open.
<!-- /generated -->

## Verdict rule, fixed now

For a bounded claim with Hirth's value v (the CSV value divided by 100) and the hull [lo_B, hi_B]
at allowance B:

| at B | condition, checked in this order |
|---|---|
| not decidable | hi_B − lo_B > 0.75 |
| supported | lo_B ≤ v ≤ hi_B |
| outside | otherwise |

- **Contradicted:** outside at the largest B of the pre-registered grid. The hull only widens
  with B, so this means outside at every B.
- **Reported per claim and variant:** the verdict at B = 0; the verdict at the comparison bias
  (fine grid); the largest B on each grid at which the B = 0 verdict still holds.
- The informativeness rule (width below 0.25 of the widest range) is reported alongside and
  does not enter the verdict.
- Plain numbers (H2, H22): the method's band mean of e next to Hirth's value, and the
  difference. No verdict.

## Comparability gaps, stated, not corrected

| gap | Hirth | the method |
|---|---|---|
| technology and area | onshore and offshore wind, all of Germany (`scope_note`) | onshore wind, 50Hertz + Amprion + TransnetBW |
| period | per claim, table above | 2025-10-01 to 2026-09-30, one window for every claim |
| grid curtailment | subtracted (market-based only) | counted in ĉ; M0 and M1 are the check |
| price | hourly day-ahead price | quarter-hour day-ahead price |
| weighting | shares of potential energy | unweighted means over quarter-hours |
| available power | weather-based fleet model, residual counts model error as curtailment | H, with the bias allowance B |
| exposure | his incentive model | the law and MaStR, award setting `main` |
| band edges | as printed, edges not stated | (lo, hi] on the quarter-hour price; ties at each edge counted in step 2 |

- Claims that share a band but differ in period (H5 and H12, H3 and H24, H4 and H23) meet the
  same interval, because the window is fixed.
- Price 0 lies in the band (−10, 0] and (−∞, 0], but no cohort is exposed there, so those bands
  hold negative-price quarter-hours only.

## Deviations from doc 44, and a disclosure

- Doc 44 made ĉ_R = 1 − (G + R)/H the primary variant. Replaced by the headline ĉ with masks M0
  and M1, by the student's decision of 23 Nov 2026, because R includes solar and offshore
  (`docs/07_limitations_and_future_work.md`).
- Doc 44 compared at H's bias over a window running to the end of October 2026 (docs/10).
  Replaced by the Experiment 3 window's H anchor, by the same decision.
- Doc 44 calls its not-decidable threshold the complement of the informativeness rule. It is
  not: the complement of a width below 0.25 is a width of 0.25 or more. The threshold is kept
  as doc 44 gives it.
- **Disclosure.** While this note was written, the number of quarter-hours per band, the ties at
  each band edge and the band mean of e on the Experiment 3 sample were printed once, to confirm
  that e > 0 in every negative-price quarter-hour. No ĉ band mean, identified set or verdict was
  computed.

## Step 2 outputs

In the folder artifacts/hirth_audit, not yet created: claim_mapping.csv, claim_ranges.csv
(claim × variant × B × lower × upper × informative flag × quarter-hours × event days) and
claim_verdicts.csv.

## Amendment 1 (23 Nov 2026), before any range was computed

Written after the student's decisions of 23 Nov 2026 on the four open choices, and committed
before any ĉ band mean, identified set or verdict was computed. Nothing above is edited; where
this amendment and the text above differ, this amendment holds.

**1. Response rate.** Approved as written: the band mean of ĉ divided by the band mean of e.

**2. Two classes.** Claims for Hirth's 2025 are cross-period: the window's 2025 negative-price
quarter-hours are in October only, because November and December have none. The pooled rows
(2022 to October 2026) are cross-period if more than half of Hirth's hours in the band fall
before the window. Hirth's hours are his Table 3 counts; the hours in the window, and after it
up to the panel's last day, are this sample's negative-price quarter-hours in the band divided
by 4. That counts quarter-hour prices against his hourly prices, so the share is approximate
(`artifacts/hirth_audit/period_shares.csv`).

<!-- generated:hirth_amend_shares -->
| claim | Hirth's band | Hirth's hours | hours in the window (QH ÷ 4) | hours after the window (QH ÷ 4) | share before the window | class |
|---|---|---|---|---|---|---|
| H5 | below -100 | 44 | 17.00 | 0.00 | 0.614 | cross-period |
| H6 | -100 to -50 | 62 | 20.25 | 0.00 | 0.673 | cross-period |
| H7 | -50 to -20 | 176 | 37.00 | 0.00 | 0.790 | cross-period |
| H8 | -20 to -10 | 167 | 34.75 | 0.00 | 0.792 | cross-period |
| H9 | -10 to 0 | 1,413 | 404.00 | 1.75 | 0.713 | cross-period |
<!-- /generated -->

<!-- generated:hirth_amend_classes -->
- Main class, bounded: H12, H23, H24. Plain number: H22.
- Cross-period class, bounded: H1a, H1b, H3, H4, H5, H6, H7, H8, H9. Plain number: H2.
- Not decidable, corrected: a range is not decidable when it is not informative, that is a width of 0.25 or more of the widest possible range (1 for every compared quantity).
<!-- /generated -->

- Cross-period claims get their ranges as planned. Their verdict words are **consistent**
  (inside) and **inconsistent** (outside even at the largest B), never supported or
  contradicted, and they are left out of every summary count.
- H1b is cross-period, and its reproduction check against λ₂ still applies.

**3. Weighting.** A secondary column for every compared claim: the same band mean, ratio or
exposure share with each quarter-hour weighted by H. It is a new fixed-weight functional in a
new file. A constant multiplicative bias scales every weight by the same factor, so the weighted
functional does not change with b; a test checks this. The unweighted column stays primary. A
claim whose verdict differs between the two columns at a reported B is marked **depends on
weighting**.

**4. Not-decidable threshold, corrected.** The 0.75 above was wrong. A range is not decidable
when it is not informative by the pre-registered rule. The correction was made before any range
was computed. The verdict order is now: not decidable, then supported (or consistent), then
outside.

**5. Why the method's exposed share can differ from Hirth's.** His exposure rate is a share of
potential energy, covers onshore and offshore wind in all of Germany, and comes from his own
cohort thresholds. The method's is an unweighted mean over quarter-hours, onshore only, three
areas, with thresholds from the law and MaStR (award setting `main`).
