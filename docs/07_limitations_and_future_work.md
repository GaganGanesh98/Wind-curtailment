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
