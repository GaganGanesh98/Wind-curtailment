# Redispatch sensitivity: pre-registration

Written on 22 Nov 2026 and committed before any masked fit was run. The headline stays as it
is: Experiment 3 with ĉ = 1 − G/H on every quarter-hour of its window.

**Question.** Do Experiment 3's readings depend on the quarter-hours in which grid operators
curtailed renewables? ĉ = 1 − G/H counts grid-ordered curtailment as switched off, because H
adds it back.

**Why masking, not subtracting.** The redispatch series R does not isolate onshore wind. It is
every renewable reduction measure in the Netztransparenz export (`PRIMAERENERGIEART` Erneuerbar,
direction reduzieren), assigned to the instructing TSO. It includes offshore wind parks and
distribution-cluster aggregates that carry solar, so subtracting it from the gap (ĉ_R =
1 − (G + R)/H) would over-subtract. Masking only removes quarter-hours. Because R is broader
than onshore wind, a mask on R drops more quarter-hours than an onshore-only mask would, so it
is conservative.

**Arms.** ĉ = 1 − G/H unchanged in both.
- **M0.** Drop every quarter-hour in which R > 0 in any of 50Hertz, Amprion or TransnetBW.
- **M1.** Drop every quarter-hour in which R exceeds 1% of H in any of the three areas, each area
  against its own H.

R is the series `projection_and_redispatch.redispatch_qh` builds for each area, as used by
`available_power.load_frames`.

**Fixed as in Experiment 3.** Window, areas, award setting `main`, potential H, the seven
functionals, the ε rule (95th percentile over 5,000 event-day bootstrap draws, recomputed on
the masked sample), the pre-registered B grid (b from −0.15 to 0.15 in steps of 0.01, hull over
|b| ≤ B), the informativeness rule and the V0 readings with their breakdown rule.

**Sample.** For each arm, the negative-price quarter-hours and event days left are reported. An
event day is a Berlin date with at least one kept negative-price quarter-hour. If an arm keeps
fewer than 20 event days, only its counts are reported and its ranges are not interpreted.

**Decision rule.** For each V0 reading (λ₁ informative, λ₂ ≥ 0.50, λ₃ ≤ 0.75, λ₆ ≤ 0.50) and each
interpretable arm: if the reading's verdict at B = 0 (holds or not) differs from the headline,
or its breakdown B moves by 0.01 or more, the reading is reported as sensitive to redispatch in
`docs/07_limitations_and_future_work.md`.

**What this cannot show.** The masked quarter-hours are a selected subset, not a random one.
Redispatch happens on windy, congested days, so the quarter-hours left differ in wind, price and
exposure from those dropped. A change under masking can come from that selection as well as from
grid curtailment, and the two are not separated here.

**Output.** `artifacts/exp3_german_application/redispatch_sensitivity_cells.csv` (cells) and a
results note `docs/11b_redispatch_sensitivity_results.md`.
