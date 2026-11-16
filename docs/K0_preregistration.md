# K0 — the statute-anchored bias bridge: data check and pre-registration

**Written and committed 16 November 2026, before any K1–K4 number existed.** The facts in §1
were computed from prices, exposure shares, dates and data coverage only; no y_t (defined in
§2), no covariance, no bridged value was computed before this commit. Every K results file
records this file's commit hash in a `k0_commit` column. Role: method validation. Phase K
changes no existing pre-registration, result, verdict or artifact.

Data are read through existing loaders, unchanged, by `src/potential/k_bridge_data.py`:
`run_p3_real.load_panel(THREE_AREA, "H")` (price, Berlin date, the Q5 window mask, three-area
cohort shares, θ per award setting) and `q0b_validate_h.load_frames("quality-assured")` (per
control area: G, F, H, RD). TenneT is excluded from every aggregate (T-D(vii)): units are
50Hertz + Amprion + TransnetBW, and each of the three areas.

## 1. Data check (facts, not results)

**The series is the statutory projection.** H is the *Online-Hochrechnung qualitätsgesichert
Wind Onshore* (file `data/raw/netztransparenz/hochrechnung_wind_onshore_qualitaetsgesichert/online_hochrechnung_wind_onshore_qs_2025-10-01_2026-10-31_dl2026-11-15.csv`,
sha256 checked by `tests/test_reported_numbers.py`). How this is known:
(i) it was downloaded from the Netztransparenz *Online-Hochrechnung* page, the publication of
EEG Anlage 1 Nr. 5.1, as recorded in `docs/Q0b_preregistration.md` §2; (ii) Anlage 1 Nr. 5.1
defines a projection of *actual generation including curtailed volumes*, and
`results/39_nr51_compliance.csv` shows the operational edition of the same series adding back
curtailment in all four areas; (iii) Q0b found it adds back market curtailment in all three
areas (`docs/Q0b_results.md` §1); (iv) its level is that of the whole onshore fleet (positive-
price gap share of about 2%, Q0b §2), which the *Hochrechnung aus EEG-Anlagen in der
ÜNB-Vermarktung* — the small fixed-tariff fleet the TSOs market — could not be.

| fact | value |
|---|---|
| resolution | PT15M, every area |
| quarter-hours in the file | 38,020, 2025-10-01 to 2026-10-31, 0 empty cells (Q0b §4) |
| analysis window | the Q5 window mask `keep`: 2025-10-01 to 2026-09-30, 34,937 quarter-hours |
| quarter-hours in the window with H, G and RD, per unit | 34,937 in each of the aggregate, 50Hertz, Amprion, TransnetBW (0 missing) |
| final month provisional? | October 2026 cannot be confirmed final from disk (the 2026 market-value file on disk ends in September). It lies outside the window, because `keep` requires a published market value, so no K computation uses it |
| imbalance price (reBAP) on disk | **no**. Anchors are defined without it; this is a limitation (an anchor with a negative imbalance price could hide balancing-driven behaviour). Nothing needing credentials was fetched |

**Event-days in the window** (≥ 1 negative day-ahead quarter-hour; 2,052 negative quarter-hours,
134 negative runs):

| anchors around every negative run (§2 rule, 2-QH buffer) | event-days |
|---|---|
| on both sides | 95 |
| on one side only | 1 |
| none (negative or buffered all day) — excluded from the bridge | 1: 2025-10-04 |

**Negative-run distribution** (the pseudo-event distribution of K1): 134 runs, length in
quarter-hours median 13.5, 10th–90th percentile 1–29, maximum 70; 43 runs of ≤ 4 QH, 32 of 5–16,
59 of > 16. Each run is stored as (start index within its Berlin day, length).

**Non-event days** (no negative quarter-hour): 267. Split by time (rule 4): **fit** = the first
160, 2025-10-01 to 2026-03-28; **held-out** = the last 107, 2026-03-30 to 2026-09-30.

**K3's population is empty.** The statutory exposed share at negative prices, e_t = Σ_k w_k s_k,t
(`main` setting, three-area shares), is never below **0.3135** (2,052 negative quarter-hours;
median 1.0). Cohorts whose θ is 0 — out of support, or with the §51 trigger active — are
exposed at every negative price, so no negative quarter-hour has e_t ≤ 0.05. **K3 is NOT
TESTABLE by its own rule**, and K4's δ is an assumption reported as a breakdown, not an
estimate. The 0.05 threshold is not changed.

**Anchors and exposure.** θ is −(market premium) or 0, never positive, so e_t = 0 at every
positive-price quarter-hour by construction; the anchor condition "price > 0 and e_t = 0" is
therefore "price > 0". Stated so it is not mistaken for an extra filter.

## 2. Definitions

- **Units:** the three-area aggregate (sums of H, G, RD) and each of 50Hertz, Amprion,
  TransnetBW. Unless stated, figures and the gate refer to the aggregate.
- **y_t = log(H_t / (G_t + RD_t))**, RD as in Q0b. Quarter-hours with H ≤ 0 or G + RD ≤ 0 are
  dropped and counted.
- **Anchor quarter-hour:** day-ahead price > 0 (hence e_t = 0), not within **2 quarter-hours**
  of any negative-price quarter-hour of the same Berlin day (buffer fixed at 2). No imbalance-
  price condition (not on disk).
- **Bias model.** Within a Berlin day, y_t on anchors is β_t, a Gaussian process with constant
  mean m and covariance by lag k (quarter-hours, same day):
  `C(k) = σ_d² + σ_a² ρ^k + σ_n² 1[k = 0]` (day level, AR(1) path, nugget). On an event-day the
  bias inside a negative run is β_t plus a jump of at most δ.
- **Estimation (rule 4):** on the **fit** non-event days only: m = mean of y; the empirical
  autocovariance γ̂(k), k = 0…95, pooled over all within-day pairs; (σ_d², σ_a², ρ, σ_n²) fitted
  by least squares weighted by pair counts, all ≥ 0 and 0 < ρ < 1. **Check of the pooled fit:**
  it passes if the fitted autocorrelation is within 0.05 of the empirical one at every lag
  1–32. If it fails, the same fit is made separately in terciles of daily mean H (fit-day
  tercile edges), and each day uses its tercile's fit.
- **Bridge on a day:** simple kriging from that day's anchors A only:
  `β̂_t = m + c_tA C_AA⁻¹ (y_A − m)`, `v_t = C(0) − c_tA C_AA⁻¹ c_At`.
- **Band at level 1 − α, α = 0.10:** `β̂_t ± (z·√v_t + δ)`, z = 1.6449. v_t includes the nugget,
  so the band is for the quarter-hour's own bias, the quantity that enters c_t.
- **Map to the curtailed share:** `c_t = 1 − (G̃_t / H_t)·exp(β_t)`, G̃ = G + RD. With
  h_t = z√v_t + δ: `c_lo = 1 − (G̃/H)·exp(β̂ + h)`, `c_hi = 1 − (G̃/H)·exp(β̂ − h)`, both clipped
  to [0, 1].
- **Bridged bounds (K4):** the existing programme (`identification.bounds`: box, monotone in
  depth and run length, same design, functionals λ₁–λ₇, λ₅ with the corrected truth for
  synthetic cells) with the residual measured to the band instead of to a point:
  `RMS( max(0, c_lo − Xr) + max(0, Xr − c_hi) ) ≤ ε`, the root-mean-square distance from Xr to
  the band.
  This reduces to P3's `‖Xr − ĉ‖_rms ≤ ε` when c_lo = c_hi. **ε rule:** P3's (95th percentile of
  the bootstrap residual norm, 5,000 event-day draws, seed 42) computed with the bridged point
  ĉ = 1 − (G̃/H)·exp(β̂). Justification: it keeps P3's sampling-noise term, and the bias
  uncertainty enters through the band instead of being double counted in ε.
- **δ grid:** {0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.15}. **Breakdown δ\*** per
  reading = the smallest grid δ at which it no longer holds, "> 0.15" if none. Readings as V2:
  λ₁ informative (width < 0.25); λ₂ lower bound ≥ 0.5; λ₃ upper bound ≤ 0.75; λ₆ upper bound ≤ 0.5.

## 3. Criteria (fixed here)

### K1 — pseudo-event cross-validation (the gate)

- **Days:** the 107 held-out non-event days. **Windows:** 3 per day (seed 42), each drawn
  uniformly from the 134 real runs as (start index, length); redrawn (up to 50 times) if it
  overruns the day or leaves no anchor. Anchors = every quarter-hour not within 2 of the window.
  The same windows serve every unit and the F comparison. 321 windows ≥ 200 per unit.
- **Bridged with δ = 0**, covariance from the fit days. A masked quarter-hour is covered if
  |y_t − β̂_t| ≤ z√v_t.
- **Report, per unit:** coverage = covered share of all masked quarter-hours; median and 90th-
  percentile half-width z√v_t; both by window length — **short ≤ 4 QH, medium 5–16, long > 16**;
  95% intervals from a held-out-day block bootstrap, 5,000 draws, seed 42.
- **PASS** iff, on the three-area aggregate, **0.85 ≤ coverage ≤ 0.95 and median half-width
  < 0.03**. Otherwise **FAIL**, labelled: coverage < 0.85 "error model wrong"; coverage > 0.95
  "band too wide for its level"; median half-width ≥ 0.047 "no gain over the measured global
  bias"; 0.03 ≤ median half-width < 0.047 "gain below the pre-set margin".
- **Reported, deciding nothing:** the same exercise with F in place of H, `y = log(F/(G+RD))`,
  its own covariance fitted on the same fit days.
- On FAIL the phase stops (rule 3) and K1 is written up as a null.

### K2 — synthetic validation (only if K1 passes)

Q2/V's 54 cells, existing arms unchanged. New arm: potential error = day level + AR(1) path +
nugget with the K1-fit covariance and mean; onset jump δ_true ∈ {0, 0.01, 0.03, 0.05} added to
the bias on negative-price quarter-hours; anchors by §2's rule. Bridged bounds at every δ on the
grid. **PASS** iff coverage of the known truth ≥ 0.95 at every (δ, δ_true) with δ ≥ δ_true, and
the median width of λ₁ at (δ = δ_true = 0) is no larger than Phase V's median width at B = 0.05
on the same cells (`artifacts/V/v1_by_functional.csv`, b* = 0). Widths at a level with coverage
< 0.95 are withheld. Diagnostic, deciding nothing: the informative share at δ_true = 0 against
Q5's real-data share.

### K3 — onset-jump placebo (only if K1 passes)

Negative-price quarter-hours with e_t ≤ 0.05; day-cluster means of y_t − β̂_t; jump bracketed in
[mean + log(1 − ē), mean]. Two one-sided tests at 5% of |jump| ≤ 0.02 applied to both ends of
the bracket. Outcomes: **NO JUMP BEYOND 0.02** (both ends' 90% intervals inside [−0.02, 0.02]);
**JUMP DETECTED** (both ends' 95% intervals on the same side of 0; interval reported);
**INCONCLUSIVE** (neither); **NOT TESTABLE** if fewer than 5 event-days qualify. Per §1 the
qualifying count is 0, so K3's outcome is NOT TESTABLE.

### K4 — real data (only if K1 passes)

Full window and monthly, H, main setting, the 96 bridgeable event-days (2025-10-04 excluded; the
one-sided day included and flagged). Bridged intervals λ₁–λ₇ on the δ grid; δ\* for the four
readings beside Phase V's B-breakdown; distribution of β̂ inside negative runs and its mean
against −0.0472; F and H bridged separately and the implied curtailed shares compared (reported
only); for λ₂'s reading, 1,000 random half-samples of event-days (seed 42) and the share in which
its bridged lower bound stays ≥ 0.5, at δ = 0 and at the largest grid δ where the full-sample
reading holds, as a robustness check beside the bootstrap.
The results note states which readings are lower bounds on response (λ₂'s) and which are upper
bounds (λ₃'s, λ₆'s), and that under-reconstruction of curtailed reference plants would bias H
only while curtailing, which anchors cannot see.

## 4. What this does not do

No solver, design, functional, threshold or existing result changes. H is ex post and never a
forecast input (the allow-list test is extended, `tests/test_leakage_postauction.py`). Runs over
about five minutes are not started here; their commands are printed with a `--smoke` flag.
