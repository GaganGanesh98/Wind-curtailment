# Method

One method, in six steps. Code in `src/method/`; each step names its module.

1. **Exposure from the law.** For each cohort k (commissioning year, support scheme) and
   quarter-hour t, the §51 EEG threshold θ_k,t is −(market premium) or 0, and the cohort is
   exposed when the day-ahead price is below it: s_k,t = 1[price_t < θ_k,t]. Depth below the
   threshold and run length are recorded too (`exposure.py`, `real_theta.py`,
   `theta_inputs.py`; statute in `docs/sources/`).
2. **Curtailed share from H.** With G the metered output and H the quality-assured
   Online-Hochrechnung as the potential, ĉ_t = 1 − G_t / H_t (`real_panel.py`,
   `available_power.py`). TenneT is excluded from every aggregate.
3. **Min/max programme with monotonicity.** The identified set of a linear functional λ′r of
   the cohort responses r is [min, max] of λ′r subject to ‖X r − ĉ‖ ≤ ε (root mean square),
   0 ≤ r ≤ 1, and r non-decreasing in depth and run length; X is the exposure-weighted design
   and ε is the 95th percentile of the residual norm over 5,000 event-day bootstrap draws
   (`bounds.py`, `functionals.py`, `collinearity.py`).
4. **The informativeness rule.** An interval is informative when its width is below a quarter
   of its logically maximal width: 1 for a response share, 2 for a difference of two, the full
   counterfactual energy for λ₅ (pre-registered in `archive/docs/Q0_preregistration.md` §5).
5. **The bias-robust union over [−B, B].** For a bias budget B, the reported set is the hull of
   the identified sets computed with the potential scaled by exp(b), for every b on a 0.01 grid
   with |b| ≤ B (`bias_robust.py`, `bias_robust_summary.py`; pre-registered in
   `archive/docs/V0_preregistration.md`, commit `3277ea6`).
6. **Breakdown points.** For each reading (for example, a lower bound of at least 0.5), the
   breakdown point is the smallest B at which the bias-robust set no longer supports it.

The seven functionals λ₁–λ₇ are defined in `archive/docs/P0_preregistration.md` §7 and
`archive/docs/P3_results.md` §0.6–0.7; plain-English names are in `docs/06_exp3_german_application.md`.
