# Limitations and future work

**Limitations**
<!-- generated:h_limitations -->
- **H is not ground truth.** It behaves as if market curtailment is added back (available-power
  estimate), but not every projected-minus-observed difference is voluntary curtailment, and its
  σ = 0.061 (quality-assured series; operational 0.066) is a lower bound on its error.
- **The bias of H at negative prices cannot be measured.** It was measured at positive prices
  only (−0.0326, quality-assured; operational −0.0472); experiment 3 therefore reports how much bias
  each reading survives, not whether it holds.
<!-- /generated -->
<!-- generated:redispatch_caveats -->
- **The redispatch series mixes in solar and offshore.** R is every renewable reduction measure in the
  Netztransparenz export; in the three areas 62% of its energy is distribution-cluster aggregates (which
  carry solar), 27% offshore wind parks and 11% substations (`artifacts/available_power_estimate/redispatch_checks.csv`).
  Q0b's and the kill test's redispatch controls therefore over-subtract, which makes their conclusions
  conservative, and the 3.38% redispatch share of H at negative prices is an upper bound that
  includes non-wind. Open: 1,322 of 7,067 renewable reduction measures fail the check that mean MW times
  duration equals the stated MWh (more than 2% apart).
<!-- /generated -->
<!-- generated:rd_docs07_line -->
- **Sensitive to redispatch** (`docs/11b_redispatch_sensitivity_results.md`, pre-registered rule): λ₁ (M0, M1), λ₂ (M0, M1), λ₆ (M0, M1). Masking removes 54% to 64% of the negative-price quarter-hours, so this is a sensitivity result and the headline verdicts stand.
<!-- /generated -->
- **TenneT is excluded** from every projection aggregate (supervisor minute T-D(vii)); the real
  data cover three of the four control areas.
- **Synthetic results hold on the tested grid only** (σ and b as listed in experiments 1 and 2).
  "σ\* ≥ 0.35" is a lower bound, not a value.
- **The synthetic-to-real gap is unexplained.** Real data are far less informative than the
  synthetic cells at the same noise level; an exploratory diagnostic did not explain it
  (`archive/docs/Q6_results.md`).

**Future work**
- Estimate the bias of H per day from the law's no-exposure quarter-hours (the cancelled Phase K
  idea; its first gate failed, `archive/docs/K_results.md`).
- Validate against ground truth where unit-level availability is published (AEMO, ERCOT).
