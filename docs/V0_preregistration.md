# V0 — bias-robust bounds and breakdown points: pre-registration

**Written and committed 16 November 2026, before the V1/V2 runner existed and before any
bias-robust interval was computed.** Phase V is the last addition; experiments freeze after
it. Role: method validation.

**What was already known when this was written.** Q2 (`docs/Q2_results.md`) showed that a
biased potential breaks coverage at every tested bias. The full-window intervals with H were
already in `docs/C1_conclusions_table.md`. One timing check was run before writing this: a
single real-data full-window scoring at b = 0 (1.4 s), which reproduced the committed Q5 row
exactly. No interval at b ≠ 0 was computed.

## 1. Definition

For a potential estimate P̂ and a bias budget B, the **bias-robust identified set** of a
functional λ is

    S_B(λ) = hull( ⋃_{b ∈ G_B} S(λ; P̂·exp(b)) ),   G_B = { b = k·0.01 : k integer, |b| ≤ B }

where S(λ; P) is the **existing** identified set computed with potential P: ĉ = 1 − G/P, the
same design, the same ε (the 95th percentile of the bootstrap residual norm, recomputed for
each b exactly as the existing code does), the same solver, the same functionals. **The only
new code is the outer loop over b.** For λ₅ the scaled potential is also λ₅'s energy
potential, as in the existing code.

- **Grid resolution 0.01**, fixed. The grid is symmetric, so the sign convention of b does
  not matter.
- **Hull, not union.** The reported set is [min over b of lo, max over b of hi], the convex
  hull of the union. A union of intervals can have gaps; a reported range does not.
- **Infeasible b are skipped and counted.** If no b in G_B gives a feasible set, S_B is
  undefined.
- B = 0 gives G_0 = {0}, and S_0 is the existing identified set, unchanged.

## 2. V1 — synthetic, on the Q2 cells

**Cells.** Q2a exactly: Arm D's 54 cells (seed 45), σ = 0, true bias b* ∈ {−0.100, −0.047,
0.000, +0.033, +0.100}. The estimate handed to the bounds is P̂ = A·exp(b*), as in Q2.
**B ∈ {0, 0.05, 0.10}.**

**Scored functionals: λ₁, λ₂, λ₃, λ₄, λ₆, λ₇.** λ₅ is computed and reported but left out of
the criterion, for a reason found while writing this file: the shared scorer
(`run_p3_synthetic._truths`) computes λ₅'s "truth" from the potential passed to it, so in
P3 Arm D, Q1 and Q2 λ₅'s truth moves with the estimated potential, while every other
functional's truth comes from the generator's true response. That is recorded here and in
the results note; nothing in P3, Q1 or Q2 is changed.

**Coverage** is the existing rule (`cov`: `covered`, with the solver tolerance slack),
applied to S_B against the true value.

**Pre-registered criterion (V1 PASS):** coverage ≥ 0.95 at **every** (B, b*) level with
B ≥ |b*|, over all scored cell-functionals at that level. Those levels are: B = 0 with
b* = 0; B = 0.05 with b* ∈ {−0.047, 0, +0.033}; B = 0.10 with all five b*. Any one level
below 0.95 is **V1 FAIL**, stated plainly.

**Stated before the run, as a prediction, not an assumption:** b* = −0.047 and +0.033 are
not on the 0.01 grid. Coverage there depends on the identified set moving monotonically
with b, so that the hull of the two neighbouring grid points brackets the truth. If it does
not, the criterion fails there and that is reported.

**Also reported, deciding nothing:** coverage at the levels with B < |b*|; the **width cost**
of each B, the median of width(S_B) / width(S_0) per functional at b* = 0, and median
widths per (B, b*); the number of informative S_B per functional (Q0 §5 rule).

**Compute.** The scored potential is A·exp(b* + b), so each cell scores every distinct sum
b* + b once and reuses it. Split into four processes by cell; the split changes no number.

## 3. V2 — real data, full window, projection H

**Arm.** `run_p3_real.run_arm` with the three-area panel and potential H (`load_panel(
THREE_AREA, "H")`), award setting `main`, the full window, plain ĉ (not recalibrated) — the
arm behind the full-window intervals in `docs/C1_conclusions_table.md`. **B from 0 to 0.15
in steps of 0.01** (16 budgets); every b ∈ [−0.15, 0.15] on the 0.01 grid is scored once.

**Functionals: λ₁, λ₂, λ₃, λ₆.** The readings and their breakdown points, each the
**smallest B on the grid** at which the reading no longer holds:

| functional | reading at B = 0 (C1) | breaks when |
|---|---|---|
| λ₁ | informative | width of S_B ≥ 0.25 (Q0 §5) |
| λ₂ | lower bound 0.525 | lower bound of S_B < 0.5 |
| λ₃ | one-sided, at most 0.579 | upper bound of S_B > 0.75 (stops cutting off a quarter of [0, 1]) |
| λ₆ | one-sided, at most 0.398 | upper bound of S_B > 0.5 (stops cutting off a quarter of [−1, 1]) |

If a reading still holds at B = 0.15 its breakdown point is reported as "> 0.15". If a
reading does not hold at B = 0, the run does not reproduce C1, and that is reported instead.

**For scale only (deciding nothing):** Anchor H's measured bias on price ≥ 0 quarter-hours is
−0.0472 (`docs/Q0_preregistration.md` §1). Its bias during negative prices is not measured.

**Reported:** a table (functional, breakdown B, S_B at B = 0, at the breakdown B and at 0.15)
and one figure, F10: S_B against B for the four functionals, breakdown marked. Values from
the artifact only.

## 4. What this does not do

No change to the solver, ε, design, functionals, informativeness rule or any existing
artifact. No existing verdict changes. V1 is synthetic and its bias is a constant
multiplicative shift; V2 says how large a constant bias the real-data readings survive, not
how large H's bias is.
