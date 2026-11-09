# 19 — The merged gate verdict, and whether this benchmark can discriminate

Scored 9 November 2026 on the completed merged grid, 81 of 81 cells. No criterion,
threshold, seed or grid point of the M2 pre-registration (`docs/09`) or the fallback
decision (`docs/18`) was altered to produce anything below.

Sources, so every number here is traceable:

| what | where |
|---|---|
| merged gate verdict | `results/13_gate_verdict_merged.csv` |
| unmerged gate verdict | `results/13_gate_verdict.csv` |
| Oracle power diagnostic | `results/13_oracle_power_diagnostic_merged.csv` |
| headroom / skill tables | `results/13_power_evidence_merged.csv` |
| per-cell grid rows | `results/12_reduced_grid_merged.csv`, committed on `identification-fix` as `d136882`, **not on this branch** (`results/` is not shared between worktrees) |

The merged artifacts are `data/processed/e1_gate_artifacts_merged/`, 81 `.npz`
written in one run 8 Nov 21:32 – 9 Nov 06:12, 499.6 min wall clock, no failed cell
and no traceback in the run log, `n_cohorts` = 6 on all 729 grid rows.

---

## 0. The headline

**The merged gate FAILS**, on (a) and (b); (c) passes. That is the same overall
outcome as the unmerged gate, but for materially different reasons.

**And the criteria are not unpassable.** The Oracle — the information ceiling —
**passes criterion (b) at both γ on the merged design**, where M1 fails at γ = 0.5.
So M1's (b) failure at γ = 0.5 is a real shortfall against a reachable bar, not an
artifact of a bar nobody could clear. This reverses what the unmerged grid suggested,
and §2 reports both.

**But the merged base is 61.6% pre-MTU15, and that disqualifies these numbers as an
E1/E2 result.** Every merged cell draws 61.6% of its quarter-hours from before
2025-10-01, the era the E1/E2 window rule excludes, where the quarter-hour price is
the hourly price repeated and the exposure indicator has no within-hour texture at
all. The merged score below is therefore **neither a window-compliant E1/E2 result
nor like-for-like against the unmerged verdict**. §1.1 gives the measurement and the
cause. The score and this caveat are reported together, as two findings; nothing was
changed to fix it, because the window question is the student's decision.

---

## 1. The merged verdict, beside the unmerged

### 1.1 A confound that has to be stated first

The two runs **differ in more than K**, so this pair does not measure the effect of
merging 8 cohorts into 6:

| | unmerged | merged |
|---|---|---|
| cohorts K | 8 | 6 |
| synthetic days per cell | 357 | **931** |
| quarter-hours per cell | 34,272 | **89,376** |
| real window drawn from | 2025-10-01 → 2026-10-28 | **2024-01-01** → 2026-10-28 |
| censored QH, (c) sample | 216,150 | **563,538** |
| artifacts written | 31 Oct 23:13 | 8–9 Nov |

The merged run has **2.6× the sample**.

**Cause, measured rather than inferred.** Commit `451aac1` on this branch ("Stage 1:
panel rebuilt to 2024-01-01", 1 Nov 14:43) moved `PERIOD_START_BERLIN` from
2025-10-01 to 2024-01-01 and rebuilt the shared `data/processed` panel — 495,360 rows
against the previous 188,660. The merged run read that rebuilt panel; the unmerged
artifacts (31 Oct 23:13) predate it by a day. `synthetic.load_base`
(`src/censoring/synthetic.py:235`) keeps every panel quarter-hour with finite
price/forecast/actual and price above the safe floor and applies **no window filter**,
and `run_reduced_grid.py` does not import `window.py`, so nothing clipped the base
back. (An earlier draft of this note attributed the longer window to the market-value
coverage fix `69949c3`. That was wrong: `69949c3` is 8 Nov and concerns monthly market
values, not the panel start.)

### 1.1b The base is 61.6% pre-MTU15, which the E1/E2 window rule excludes

Measured on the artifacts, `real_berlin_date` per cell:

| | unmerged | merged |
|---|---|---|
| quarter-hours before 2025-10-01 | **0.0%** | **61.6%** |
| spread across the 81 cells | — | min = max = 61.6%, identical in every cell |

`src/censoring/window.py` — present on `identification-fix`, **absent on this
branch**, so the constant is not even importable here — sets
`E1_E2_WINDOW_START = MTU15_FIRST_DELIVERY_DAY = "2025-10-01"` and records why:
SDAC 15-minute MTU went live for delivery day 1 Oct 2025, and **before it all four
quarter-hour prices are identical in 15,335 of 15,335 calendar hours** (0.30% flat
afterwards, mean within-hour spread 23.95 EUR/MWh). It states that running E1 or E2
across the boundary "would pool two different market designs", and that in the hourly
regime the two clocks of spec §3 I4 "collapse into one".

Why this matters for exactly this gate: exposure is `s = 1[p_qh < θ]` on the
quarter-hour price. On 61.6% of the merged base that price has **no within-hour
variation whatsoever**, so `s` carries no sub-hourly information there, and the
QH-versus-hourly clock distinction that the cohort structure rests on is not present
in the data. `docs/18` §0 already records that the clock selects the branch of θ; in
the pre-MTU15 regime there is nothing for it to select on.

**So the merged numbers are not a window-compliant E1/E2 result.** They are reported
because the run is real, complete and clean, and because the longer base genuinely
does tighten the bootstrap — but they cannot be filed as the E1/E2 verdict, and they
are not comparable like-for-like with `results/13_gate_verdict.csv`, which is 0.0%
pre-MTU15. Nothing here was rewired, re-run or clipped to repair this.

**Consequence: every merged-vs-unmerged difference below is confounded between the
cohort merge, a 2.6× larger evaluation sample, and a change of market regime across
61.6% of that sample.** Where the merged result is
"significant" and the unmerged is not, the sample size is the more parsimonious
explanation — a 2.6× sample narrows a CI by about √2.6 ≈ 1.6× on its own, and several
CIs below narrow by far more than that. Attributing the change to K 8 → 6 would be
wrong. Isolating it would need the merged design re-run on the unmerged window, or
the reverse; neither was run, and neither is proposed here without a decision.

### 1.2 Verdicts side by side

| criterion | unmerged | merged |
|---|---|---|
| (a) step | FAIL, M1 lower 6/9, p = 0.5078 | **FAIL, M1 lower 0/9, p = 0.0039** |
| (a) logistic | PASS, 9/9, p = 0.0039 | PASS, 9/9, p = 0.0039 |
| (a) half | FAIL, 1/9, p = 0.0391 | FAIL, 3/9, p = 0.5078 |
| **(a) overall** | **FAIL** | **FAIL** |
| (b) γ = 0.5 | FAIL | FAIL |
| (b) γ = 1.0 | FAIL | **PASS** |
| **(b) overall** | **FAIL** | **FAIL** |
| (c) γ = 0 | PASS | PASS |
| **GATE** | **FAIL** | **FAIL** |

The unmerged verdict was **regenerated** with the post-fix code and came out
byte-identical to the file committed on 1 November. The `--merged` plumbing therefore
changed no computation, which is the only claim that re-run was meant to support.

### 1.3 Criterion (b), where merging changes the picture

Pre-registered bar: M1 better than **each** of B1–B4 on **both** the absolute bias of
Â and the curtailed-share MAE. Paired event-day bootstrap, censored quarter-hours,
pooled over seeds, rates and shapes.

**γ = 0.5 — FAILS on both designs, but on different rivals.**

| rival | unmerged \|bias\| diff, 95% CI | merged \|bias\| diff, 95% CI |
|---|---|---|
| B1 | −1539.98 [−1690.82, −1254.38] ✓ | −1118.52 [−1290.00, −944.64] ✓ |
| B2 | −4.75 [−15.41, **+13.19**] ✗ | −13.20 [−15.79, −11.03] ✓ |
| B3 | −12.98 [−23.23, **+20.74**] ✗ | −1.90 [−4.65, **+0.48**] ✗ |
| B4 | −7.39 [−15.32, **+13.91**] ✗ | −10.50 [−13.45, −7.82] ✓ |

On the merged design M1 now wins the bias comparison against B2 and B4 — and the
failure narrows to **two near-misses**: B3's bias CI [−4.65, +0.48] and B2's
curtailed-share MAE CI [−0.00010, **+0.00001**]. Both cross zero by a hair. The gate
is decided by a margin of 0.48 MW on an error of ~1,180 MW, and by 1 × 10⁻⁵ of a
share.

**γ = 1.0 — unmerged FAIL, merged PASS.**

| rival | unmerged \|bias\| diff, 95% CI | merged \|bias\| diff, 95% CI |
|---|---|---|
| B1 | −2678.95 [−2935.66, −2328.16] ✓ | −2448.60 [−2728.04, −2169.17] ✓ |
| B2 | **+19.17** [−39.32, +34.05] ✗ | −18.33 [−20.96, −15.96] ✓ |
| B3 | **+8.23** [−58.56, +47.62] ✗ | −19.05 [−22.37, −16.26] ✓ |
| B4 | **+5.10** [−54.88, +47.66] ✗ | −3.52 [−5.82, −1.41] ✓ |

Unmerged, M1 was nominally *worse* than B2, B3 and B4 on bias with CIs ±40–60 MW
wide. Merged, it is significantly better against all four, with CIs an order of
magnitude tighter. Per §1.1 this is confounded with the 2.6× sample and must not be
read as an effect of merging.

### 1.4 Criterion (a) — unchanged in outcome, and worth a word on why

(a) asks M1's integrated |r̂ − r*| to beat B3's implied response, per shape, by an
exact two-sided sign test over 9 cells needing ≥ 8.

M1 wins 9/9 on **logistic**, where B3's integrated error is ~0.20 — B3's functional
form is simply wrong for a logistic r*. On **step**, B3's error is **0.00167 in all
nine cells** against M1's best of 0.00224: B3's implied step response is very nearly
exact, so M1 is being asked to beat a near-perfect baseline, and loses 0/9 on the
merged grid. On **half** the two are comparable and the sign test is 3/9, p = 0.5078 —
no signal either way.

So (a)'s outcome is governed less by M1's quality than by **whether B3's form happens
to match r\***. That is a property of the criterion as written. It is recorded here,
not changed.

### 1.5 Criterion (c) — passes on both, comfortably

No-harm clause: M1's MAE not significantly worse than B2 at γ = 0.

| | M1 MAE | B2 MAE | diff, 95% CI | sample |
|---|---|---|---|---|
| merged, censored QH | 1,177.8 MW | 1,182.8 MW | −4.95 [−6.37, −3.58] | 563,538 QH / 931 days |
| merged, all QH | 1,189.1 MW | 1,192.3 MW | −3.16 [−4.22, −2.14] | 2,413,152 QH / 931 days |
| unmerged, censored QH | 1,232.7 MW | 1,239.6 MW | −6.93 [−9.10, −4.95] | 216,150 QH / 357 days |

M1 is significantly *better* than B2 on both designs, so the clause passes with room.
The (cell, day) block sensitivity on the merged design gives −4.95 [−5.74, −4.19]
over 19,602 blocks, the same sign and a tighter interval.

---

## 2. The Oracle power diagnostic — **a diagnostic, not a verdict**

`results/13_oracle_power_diagnostic_merged.csv`. The Oracle is fitted on true
available power, so it is the information ceiling: nothing that sees only observed
generation can beat it except by noise. Substituting `a_hat_Oracle` for M1 and
re-scoring asks whether the criteria are satisfiable **at all**. Every helper —
pooling, the paired event-day bootstrap, `paired_abs_bias`, `paired_difference` — is
imported from `gate_verdict.py` rather than reimplemented, and M1 is scored through
the same code path, so the two columns differ only in which Â plays the candidate.

**This is not a gate verdict and must never be filed as one.** The gate's verdict on
M1 is §1.

### 2.1 Criterion (a): NOT APPLICABLE

The cells store `r_curve_M1` and `r_curve_B3` only. The Oracle is fitted on true
available power and has **no response head** — it never identifies a curtailment
response, so there is no curve to integrate against r*. (a) is therefore not
evaluated for the Oracle, and **no substitute statistic was improvised** for it. The
gap is reported as a gap. A consequence worth being explicit about: **the power of
criterion (a) is not tested by this diagnostic at all**, and §1.4's observation about
B3's form is the only evidence here that bears on it.

### 2.2 Criterion (b): the ceiling PASSES, at both γ

| γ | rival | Oracle \|bias\| diff, 95% CI | Oracle c-MAE diff, 95% CI | both? |
|---|---|---|---|---|
| 0.5 | B1 | −1123.15 [−1295.70, −949.22] | −0.01755 [−0.01917, −0.01591] | ✓ |
| 0.5 | B2 | −17.83 [−20.66, −15.33] | −0.00011 [−0.00018, −0.00005] | ✓ |
| 0.5 | B3 | −6.53 [−9.52, −3.86] | −0.00018 [−0.00028, −0.00009] | ✓ |
| 0.5 | B4 | −15.13 [−18.31, −12.22] | −0.00018 [−0.00025, −0.00011] | ✓ |
| 1.0 | B1 | −2458.56 [−2737.18, −2180.15] | −0.04316 [−0.04668, −0.03958] | ✓ |
| 1.0 | B2 | −28.29 [−30.77, −25.98] | −0.00020 [−0.00026, −0.00015] | ✓ |
| 1.0 | B3 | −29.01 [−32.10, −26.25] | −0.00021 [−0.00027, −0.00015] | ✓ |
| 1.0 | B4 | −13.48 [−15.87, −11.21] | −0.00014 [−0.00018, −0.00010] | ✓ |

**The Oracle would pass (b) at γ = 0.5 and at γ = 1.0.** M1, on the same code path,
would fail at γ = 0.5 and pass at γ = 1.0.

So at γ = 0.5 the criterion **discriminates**: the ceiling clears it and M1 does not.
M1's failure there is a real shortfall against a bar that is demonstrably reachable.
The pre-registered criteria stand, and nothing in this section is a reason to touch
them.

### 2.3 But on the unmerged design the ceiling FAILED

The same diagnostic on the complete 81-cell **unmerged** grid
(`results/13_oracle_power_diagnostic.csv`) gives the opposite answer: the Oracle
**fails (b) at both γ**. Against B2 at γ = 0.5 its bias difference is −13.19 MW with
CI [−27.18, **+25.23**]; at γ = 1.0 against B2 it is nominally *worse*, +5.72 MW. On
that design the criterion was effectively unpassable — not because the bar is wrong,
but because the CIs were ±25–50 MW on differences of 5–20 MW.

Both results are reported because together they identify the mechanism: **(b)'s
discriminating power is a function of sample size, not of the bar's height.** On 357
days nothing could clear it, ceiling included. On 931 days the ceiling clears it
comfortably and M1 misses at γ = 0.5 by 0.48 MW. Given §1.1, the merged run's power
cannot be credited to merging; the larger sample is the parsimonious explanation.

**With the qualification of §1.1b, which cuts into the result itself.** The sample
that supplies the power is 61.6% pre-MTU15, a regime where the quarter-hour price has
no within-hour variation and `s` therefore no sub-hourly texture. The demonstration
that (b) is passable at the ceiling is thus established on a base that the E1/E2
window rule excludes. Whether (b) is passable **on a window-compliant base** is not
answered by either run: the compliant one (unmerged, 0.0% pre-MTU15) has 357 days and
could not clear the bar even at the ceiling, and the one that clears it is not
compliant. That question is open, and closing it needs a decision about the window,
not a re-score.

### 2.4 Criterion (c): both pass

| candidate | MAE | B2 MAE | diff, 95% CI | significantly worse? |
|---|---|---|---|---|
| Oracle | 1,178.3 MW | 1,182.8 MW | −4.45 [−6.16, −2.76] | no |
| M1 | 1,177.8 MW | 1,182.8 MW | −4.95 [−6.37, −3.58] | no |

The Oracle clears the no-harm clause, so (c) is passable. Note M1's point estimate is
marginally *better* than the Oracle's here (−4.95 vs −4.45 against the same B2) — a
0.5 MW difference, well inside either CI, and exactly the kind of noise §3 is about.

---

## 3. Supporting power evidence across all 81 cells

`results/13_power_evidence_merged.csv`.

### 3.1 Headroom — the recoverable gap

`headroom_mw` = `mae_b0` − `mae_oracle`: the distance from the operational status quo
(the raw TSO day-ahead forecast) to the information ceiling. Verified identical across
a cell's nine method rows before collapsing.

| | MW |
|---|---|
| cells | 81 |
| min | 92.1 |
| median | 147.7 |
| max | 186.5 |
| mean | 149.2 |

By censoring rate (median): 0.10 → 154.0, 0.20 → 151.5, 0.40 → 145.5. Flat.

### 3.2 The error the headroom sits inside

`censored_mae_mw`, min / median / max over the 81 cells:

| method | min | median | max |
|---|---|---|---|
| M1 | 1,103.9 | 1,309.3 | 1,537.0 |
| B0 | 1,195.7 | 1,455.3 | 1,703.8 |
| Oracle | 1,103.6 | 1,305.1 | 1,519.7 |

**Median headroom ÷ median M1 censored MAE = 147.7 / 1,309.3 = 11.3%.** The entire
recoverable gap — everything that separates doing nothing from perfect information —
is about an eighth of the error it sits inside. M1's median MAE sits 4.2 MW above the
Oracle's, on an error of ~1,300 MW.

### 3.3 Baselines above the ceiling

`recovery_skill` = (MAE_B0 − MAE_method) / (MAE_B0 − MAE_oracle). 1.0 is the Oracle,
0.0 is the raw forecast. A value above 1.0 means a method beat the information
ceiling, which is not a better method — it is the noise floor showing through.

| method | cells > 1.0, of 81 | range of the > 1.0 values | min | median | max | kind |
|---|---|---|---|---|---|---|
| B0 | 0 | — | −0.000 | 0.000 | 0.000 | baseline |
| B1 | 21 | 1.005 – 1.183 | −42.551 | 0.547 | 1.183 | baseline |
| B2 | 21 | 1.011 – 1.041 | 0.822 | 0.980 | 1.041 | baseline |
| B3 | 12 | 1.007 – 1.042 | 0.828 | 0.976 | 1.042 | baseline |
| B4 | 22 | 1.000 – 1.069 | 0.782 | 0.970 | 1.069 | baseline |
| B5 | 36 | 1.000 – 1.169 | 0.825 | 0.999 | 1.169 | baseline |
| Proxy | 18 | 1.003 – 1.147 | −42.243 | 0.533 | 1.147 | baseline |
| M1 | 40 | 1.000 – 1.086 | 0.791 | 0.999 | 1.086 | candidate |
| Oracle | 0 | — | 1.000 | 1.000 | 1.000 | ceiling |

**In 64 of 81 cells at least one of B0–B5 or Proxy scores above 1.0** — by rate:
26/27 at 0.10, 19/27 at 0.20, 19/27 at 0.40.

B1 and Proxy also fail catastrophically in places: B1 is below 0 in 32 cells (worst
−42.55) and Proxy in 34 (worst −42.24), concentrated at rate 0.40, γ = 1.0, shape
`step`. Their medians (0.547, 0.533) are far below their 46-cell values, because the
rate-0.40 cells scored last are where they collapse.

### 3.4 Corrections to the figures quoted from the partial file

The brief for this work quoted four figures from the grid while it was still running.
All four were taken before the rate-0.40 cells existed, and all four understate the
full-grid range:

| quoted from the partial file | full 81 cells |
|---|---|
| headroom 92–146 MW | **92.1–186.5 MW**, median 147.7 |
| censored MAE 1,100–1,200 MW | **M1 1,103.9–1,537.0 MW**, median 1,309.3 |
| B1 at 1.032–1.070 | B1's above-1.0 values run **1.005–1.183** |
| Proxy at 1.108 | Proxy max **1.147** |

---

## 4. Does this benchmark have the power to discriminate?

**Partly, and only in the pooled bootstrap.** Three findings, which point in different
directions and should not be collapsed into one verdict.

**(1) Pooled over 931 days, criterion (b) does discriminate — on a base that is not
window-compliant.** The ceiling passes at both γ and M1 fails at γ = 0.5 (§2.2). That
is exactly the behaviour a working test should show, and it is the strongest evidence
here that (b) is sound as written. It also means M1's γ = 0.5 failure is informative
about M1. But 61.6% of those 931 days precede MTU15 (§1.1b), so what has been shown is
that (b) discriminates **given a base that length**, not that it discriminates on the
window E1/E2 is supposed to use. On the only window-compliant base available — 357
days — it discriminated nothing at all, failing even for perfect information.

**(2) Per cell, it does not discriminate at all.** In 64 of 81 cells some baseline
scores better than the information ceiling (§3.3). A cell cannot tell the ceiling from
a baseline, because the recoverable gap is 11.3% of the error it lives inside (§3.2)
and per-cell noise is larger than the entire quantity being measured. The pooled
bootstrap works only by averaging 931 days of that noise down. So no claim about
method ranking should ever be made from a cell, a shape, or a handful of cells —
including the single-arm, three-cell ablation figures that `docs/18` §1 already flags
as not robust.

**(3) The margins that decide the gate are smaller than the quantities deciding
them.** (b) at γ = 0.5 turns on a bias CI reaching +0.48 MW and a share CI reaching
+1 × 10⁻⁵ (§1.3). A test whose verdict hinges on 0.48 MW out of 1,180 MW is
reproducible only to the extent the bootstrap is, and a different seed set or window
could plausibly flip it. The verdict stands as scored; its *robustness* is what this
observation qualifies, not its correctness.

### What would have to change for the benchmark to discriminate properly

Stated as options for the student's decision. **None of these is adopted here, and
none may be applied to the already-scored gate** — changing the test after seeing the
result is the thing `docs/18` exists to prevent.

1. **Make the headroom larger relative to the error.** The real fix. Headroom is 11.3%
   because B0 (the raw forecast) is already close to the ceiling on this generator.
   Any change that widens the gap — a noisier forecast, a regime where curtailment is
   a larger share of available power — gives every criterion more room. This is a
   change to the *generator*, so it would invalidate comparison with everything scored
   to date and needs a written decision.
2. **Report effect sizes against the headroom, not in MW.** A −13.20 MW difference is
   9% of the median headroom; in MW it looks negligible and in skill terms it is not.
   `recovery_skill` already does this and is already computed per cell. This is a
   reporting change, costs nothing, and would have made §1.3's near-misses legible
   immediately.
3. **Drop "better than *each* of B1–B4 on *both* statistics".** Eight simultaneous
   one-sided requirements with no multiplicity correction is a conjunction that even
   the ceiling fails on 357 days (§2.3). A single pre-registered composite, or an
   explicit correction, would be a better-powered test of the same idea. **This is the
   criterion itself and cannot be changed retroactively.**
4. **Separate sample size from design, and settle the window.** The single most
   useful run would be the merged design restricted to the window-compliant period —
   `berlin_date >= 2025-10-01` — which would at once resolve §1.1's confound, give a
   compliant merged score, and say whether K 8 → 6 does anything on its own. It
   changes no pre-registered quantity; it needs a decision on the window and on
   whether `run_reduced_grid.py` should import `window.py` at all, which it currently
   does not. Note the compliant period is short: a window-compliant merged run would
   have roughly the 357-day sample that could not clear (b) even at the ceiling, so
   this would most likely produce a well-identified *negative* power result rather
   than a pass.

**The honest summary: the gate fails on both designs. The failure is informative at
γ = 0.5 in the sense that the ceiling clears that bar — but it clears it on a base
61.6% of which lies in a market regime the E1/E2 window rule excludes, and where the
exposure indicator has no within-hour texture. On the one window-compliant base there
is, the criterion was unpassable even for perfect information. So this benchmark has
not yet been shown to discriminate between methods on data E1/E2 may legitimately
use: the better-powered run is not compliant and the compliant run is not powered.
That is a finding about the benchmark, to be reported alongside the failure. It is not
a reason to re-cut the test, and no criterion, threshold, seed or grid point was
touched.**

---

## 5. Found while scoring: what was fixed, and what still stands

Items 1 and 4 were resolved on `identification-fix` after this document was first
filed, by the session that ran the grid. Both fixes are recorded here with the commit
that made them; I verified each claim against the repository rather than taking the
report at face value.

1. **The merge map described a key it did not use — now fixed, `7020dbd`.** The grid
   log printed `merge map (keyed on identical theta)`, merged cohort ids carried a
   `theta_` prefix, and each merged cohort's `note` read "merged on identical theta
   from: …". The grouping itself was always **correct**: `merge_cohorts` groups on its
   `key` argument and `run_reduced_grid.py` passes `np.hstack([s, depth])`, the
   realised block `docs/18` §3 requires.

   The mechanism was worse than stale strings. `feature_merge_map` *delegated to*
   `theta_merge_map`, passing `hstack([s, depth])` as that function's `theta`
   argument — so the label was wrong in **100% of production calls**, not merely out
   of date. Two of the four existing tests asserted the wrong strings themselves
   (`note.startswith("merged on identical theta")`,
   `cohort_id.startswith("theta_")`), which is why it survived. The fix maps a rule
   token to its phrase and derives the id prefix, the cohort note and the printed
   header from the token, with `rule` keyword-only and required on `merge_cohorts`;
   four regressions now pin the label to the key, and the suite went 153 → 157. The
   change was verified inert by grouping the real DE panel under all four award
   settings before and after: identical members, member shares, capacity shares and
   dominant cohort in every arm, only `merged_id` differing.

   **Consequence for this document, and it is nil for every number in it.** Merged ids
   are now `exposure_out_of_support+post_feb2025_qh` and
   `exposure_out_of_support+post_feb2025_qh+pre2016_in_support_no_s51`, while the 81
   artifacts on disk still store the old `theta_` ids — so code and artifacts disagree
   on the label until a regeneration. Nothing reads those strings functionally:
   `gate_verdict.py` and `oracle_power_check.py` never reference `cohort_ids` at all,
   and `docs/18` §3's purpose for the note — carrying legal provenance into the
   write-up — is what the fix restores. No value in §1 – §4 depends on a cohort id.

2. **`window.py` is not on this branch and nothing in the grid path imports it.**
   The E1/E2 window constant lives only on `identification-fix`, and
   `run_reduced_grid.py` / `synthetic.load_base` apply no window filter on either
   branch. So the window rule is currently documentation, not an enforced
   precondition, and a grid run picks up whatever the shared panel happens to span.
   That is how a 61.6% pre-MTU15 base reached a gate scoring without anything
   flagging it (§1.1b). **Still stands.** Not fixed here: wiring it is a code change
   on a pre-registered path and the window is the student's call.

3. **The grid is immune to the market-value fix landing mid-run.** `69949c3` was
   committed 8 Nov 22:35, about 25 minutes into the 500-minute run, so part of the
   grid was generated before it and part after — a legitimate worry about internal
   consistency, and the answer is that it does not arise. `SyntheticConfig.mv_eur_mwh`
   is the constant **45.0** (`src/censoring/synthetic.py:89`, passed at `:520`), and
   `synthetic.py` contains no reference to `read_published` or the monthly series at
   all. Only the real-panel path reads published market values. The 81 cells are
   therefore internally consistent across that commit. (This is also why `docs/18`
   §1's "flat placeholder below every award value" caveat applies to the whole grid
   uniformly.)

4. **`results/12_reduced_grid_merged.csv` is now committed — `d136882`, tracked on
   `identification-fix`** (730 lines), with the window confound recorded in its commit
   message. Every §3 number has a home. It is not on this branch, so citing it from
   here still means citing across branches until the two are merged.

5. **`results/39_identification_gate.csv` is stale with respect to `69949c3`, and
   stands as committed deliberately.** The MV fix widened `read_published()`, which
   `run_identification._real_panel_theta` uses to mask the panel to months with a
   published market value (now 96,380 of 99,072 DE quarter-hours, 97.3%). Regenerating
   it today moves the pre-registered I4 day count from 19/55/71/29 to
   **191/244/262/210** at low/main/high/stress, moves the weakest pair from
   `wind2023_feb2025_staircase|wind2021_2022_4h` to `size_exempt|pilot_exempt` at main,
   high and stress, and moves `cond(s)` after merge (39.391 → 31.171 at low). I4 is a
   pre-registered quantity, so the committed file was restored rather than refreshed
   and the discrepancy is recorded in `7020dbd`'s message; refreshing it is the
   student's call.

   **Nothing in this document or in `docs/18` cites a number from that file** — checked:
   `docs/19` references I4 only as the spec clause whose two clocks collapse in the
   hourly regime (§1.1b), and `docs/18` §2 cites the pre-registered threshold of 10
   quarter-hours, not a measured day count. Any *other* text quoting an I4 day count
   from `results/39` is quoting a pre-MV-fix number and should say so.

6. **The 720-row deletion in the repo root's `results/12_reduced_grid.csv` working
   tree is unexplained and unowned.** Not mine, and the session that ran the grid
   reports it is not theirs either and that it has touched nothing in the main
   checkout. It was present before this work began and is untouched by it. This needs
   the student, not another session.

## Nothing pre-registered was changed

No criterion, threshold, seed, λ grid, bins grid or grid point was altered. The only
code change behind this document is `gate_verdict.py --merged`, which selects which
directory is read and tags the output filename; re-running the unmerged gate with it
reproduced the 1 November verdict byte-identically. §2's diagnostic cannot emit a gate
verdict, and §4's options are options, not decisions.
