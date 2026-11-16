# Experiment 1 — Known-truth validation

**Question.** Where the truth is known, do the bounds contain it, and how does noise in the
potential widen them?

**What was done.**
- Synthetic cells with a known response: two cohort configurations × three censoring rates ×
  three γ × three response shapes = 54 cells per seed. The bounds are computed with the exact
  potential (three seeds, 162 cells) and with an estimated one (a cross-fitted stage A, seed 45).
- The noise dial: the true potential multiplied by exp(e), e i.i.d. at σ ∈ {0, 0.033, 0.066,
  0.12, 0.18, 0.25, 0.35}, plus one AR(1) arm at σ = 0.18.

**Pre-registrations.** `archive/docs/P0_preregistration.md` §7 (commit `1cd4b30`), gaps filled
in `archive/docs/P3_results.md` §0; the noise dial in `archive/docs/Q0_preregistration.md` §3
(commit `b261c9f`).

**Coverage of the known truth** (`artifacts/exp1_known_truth_validation/`):

<!-- generated:exp1_coverage -->
| setting | covered / scored | coverage |
|---|---|---|
| exact potential | 1127/1127 | 1.000 |
| estimated potential | 378/378 | 1.000 |
| noise dial, i.i.d. σ = 0 | — | 1.000 |
| noise dial, i.i.d. σ = 0.033 | — | 1.000 |
| noise dial, i.i.d. σ = 0.066 | — | 1.000 |
| noise dial, i.i.d. σ = 0.12 | — | 1.000 |
| noise dial, i.i.d. σ = 0.18 | — | 1.000 |
| noise dial, i.i.d. σ = 0.25 | — | 1.000 |
| noise dial, i.i.d. σ = 0.35 | — | 1.000 |
| noise dial, AR(1) σ = 0.18 | — | 0.984 |
<!-- /generated -->

**Cells informative, of 54, by noise level** (`noise_dial_summary.csv`):

<!-- generated:exp1_informative -->
| functional | σ = 0 | σ = 0.066 (H) | σ = 0.18 (F) | σ = 0.35 |
|---|---|---|---|---|
| λ₁ | 54/54 | 54/54 | 54/54 | 50/54 |
| λ₂ | 54/54 | 54/54 | 54/54 | 41/54 |
| λ₃ | 54/54 | 54/54 | 18/54 | 18/54 |
| λ₄ | 54/54 | 24/54 | 18/54 | 14/54 |
| λ₅ | 54/54 | 24/54 | 18/54 | 17/54 |
| λ₆ | 54/54 | 54/54 | 18/54 | 18/54 |
| λ₇ | 18/54 | 9/54 | 9/54 | 0/54 |
<!-- /generated -->

**Verdicts (quoted).**
- Exact potential: "The bounds contain the truth in 1,127 of 1,127 scored cell-functionals on
  the synthetic benchmark — 100% against a pre-registered target of 95%."
- Estimated potential: "Coverage holds: 378 of 378, no misses. The bounds stay honest when ĉ is
  noisy; they simply stop being narrow."
- Noise dial: "σ\* ≥ 0.35 — censored at the top of the pre-registered grid." The AR(1) arm's
  coverage is 0.984 after the λ₅ erratum (`archive/docs/ERRATUM_lambda5.md`).

**Figures.** `figures/04_exp1_coverage.png`, `05_exp1_exact_vs_estimated_potential.png`,
`06_exp1_noise_dial.png`, `07_exp1_width_vs_noise.png`.

**Full detail.** `archive/docs/P3_results.md`, `archive/docs/Q1_results.md`.
