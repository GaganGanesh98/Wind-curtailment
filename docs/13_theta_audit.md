# 13 — Theta audit: the market-value series, and whether tier 1 is identified

Run 8 Nov 2026 on branch `identification-fix`, while the 81-cell merged regeneration was
still running. Read-only with respect to that run: no artifact directory touched, no
result CSV of its overwritten, one panel scan per step. New analysis file
`src/censoring/theta_audit.py`.

**Headline.** The market-value series is the right one, so the MP = 0 finding stands and
is if anything conservative. But tier 1 — the K-cohort model — is **not robustly
identified on real data**: θ is identically zero fleet-wide, meaning no cohort structure
of any kind exists, in **8 of 9** usable months at AW `low`, **4 of 9** at `main`, **7 of
9** under the base-tariff stress case, and 0 of 9 at `high`. At `low` every separating
quarter-hour falls in a single month. Which tier the thesis runs on is a supervisor
decision, not something the gate will settle.

**What is new here and what is not.** Spec v1.8 already states that separation is gated by
the market premium, that "the §51 clock **never** separates cohorts on its own", and that
"the low setting at 19 days is far closer to [the threshold] than the headline 55
suggests". This audit does not discover that; it quantifies how much closer, at month
resolution, and adds the coverage and series checks v1.8 assumed. Where it corrects
something, it says so.

---

## Step 1 — the market-value series

### 1.1 What the loader reads, verbatim

| | |
|---|---|
| file | `data/raw/netztransparenz/Monatsmarktwerte_2026.csv` |
| row selected | **`"MW Wind an Land"`** → `mv_wind_onshore` |
| also read | **`"Spotmarktpreis"`** → `spot_mean` (not used to build θ) |
| units | ct/kWh × 10 → EUR/MWh |
| code | `src/ingest_market_values.py` `read_published`, the `wanted` dict |

It is the **wind onshore** market value by name, not a base-load or generic monthly
average. The base-load-like figure is read separately as `spot_mean` and never reaches θ.

### 1.2 Independent recomputation from the panel

`MV_recomputed[m] = Σ(price × act_onshore_mw) / Σ(act_onshore_mw)` — the EEG Anlage 1
Nr. 3.3.2 definition applied to the panel. Capture = series ÷ simple monthly mean, which
for onshore wind must be below 1. Only 2026-01…2026-09 have a published value.

| month | neg QH | price_mean | published MV | recomputed | pub/mean | rec/mean | pub − rec |
|---|---|---|---|---|---|---|---|
| 2026-01 | 10 | 110.09 | 95.36 | 96.95 | 0.866 | 0.881 | −1.59 |
| 2026-02 | 23 | 96.58 | 87.23 | 88.13 | 0.903 | 0.913 | −0.90 |
| 2026-03 | 139 | 99.29 | 75.37 | 79.63 | 0.759 | 0.802 | −4.26 |
| 2026-04 | 492 | 78.52 | 57.18 | 71.46 | 0.728 | 0.910 | −14.28 |
| 2026-05 | 315 | 97.54 | 95.34 | 101.47 | 0.977 | 1.040 | −6.13 |
| 2026-06 | 199 | 109.52 | 78.55 | 87.68 | 0.717 | 0.801 | −9.13 |
| 2026-07 | 306 | 105.45 | 86.01 | 93.83 | 0.816 | 0.890 | −7.82 |
| 2026-08 | 226 | 126.89 | 115.45 | 124.02 | 0.910 | 0.977 | −8.57 |
| 2026-09 | 143 | 144.82 | 109.40 | 117.57 | 0.755 | 0.812 | −8.17 |

Capture rate, published: mean **0.826**, range 0.717–0.977. Published below the simple
mean in **9 of 9** months; below the recomputation in **9 of 9**.

### Verdict — the series is right, and the error is conservative

It tracks the recomputed wind-weighted figure, not the simple mean, and sits below both in
every month. MV is **not** artefactually high, so **the MP = 0 finding stands**. Note the
direction: the published series is *lower* than the recomputation, and a lower MV gives a
*larger* premium, so MP = 0 occurs **despite** the more generous input. Using the
recomputation instead would make MP = 0 more common, not less.

Two things to carry forward rather than treat as settled. The repo already knows the
recomputation does not reproduce the published series and that the published one is right
on a capture-rate argument (`ingest_market_values.py` header, **UNRESOLVED**); nothing here
changes that. And the recomputed capture rate for 2026-05 is **1.040** — above 1, which for
onshore wind is implausible and is a further flag on the recomputation, not on the
published series.

### 1.3 The T2 market-value channel — a latent leakage gap

Spec v1.2 (`docs/06:268`) makes MV task-dependent: the published monthly value is correct
for T1 ex-post, but for T2 it is leakage, so T2 must recompute month-to-date from data
available by D−1.

* The T2-admissible series **is** produced: `mv_t2_known_by_d_minus_1`, written to
  `data/processed/mv_t2_daily.parquet` (`ingest_market_values.py:203, 245`).
* It has **no reader anywhere** in `src/` or `tests/`. Every θ-building consumer reads
  `read_published()`: `compute_theta_inputs.py:203`, `check_rule18_real.py:110`,
  `run_identification.py`, `ingest_award_values.py:340`.
* The published value **is** correctly guarded as a *latent-head feature*:
  `"market_value_published"` and `"marktwert_published"` are on `FORBIDDEN_FEATURES`
  (`model.py:67`, "released after month end"), with
  `test_published_market_value_is_on_the_forbidden_list` enforcing it.

**So the guard covers the feature channel and not the θ channel.** θ is a structural input,
not a listed feature, and nothing stops a T2 fit from building θ on the published monthly
value. No T2 model has been fitted on real data yet, so this is **latent, not live** — but
it would not be caught when one is. `test_theta_provenance_is_recorded_so_it_can_be_checked_per_task`
only pins the Phase-2 placeholder (`mv_eur_mwh == 45.0`), not the task-dependence.

Recommended, not done here: extend the leakage test to assert that a T2 θ build reads
`mv_t2_known_by_d_minus_1` and never `read_published`.

---

## Step 2 — θ separation on the real panel

### Coverage first, because it bounds everything else

| | |
|---|---|
| quarter-hours in the study window (from `MTU15_FIRST_DELIVERY_DAY`) | 37,732 |
| of those, with a published market value | **26,204 (69.4%)** |
| months in the window | 13 |
| months usable | **9** — 2026-01 … 2026-09 |
| months dropped for want of a market value | 4 — 2025-10, 2025-11, 2025-12, 2026-10 |

**Every I4 and gate figure on real data is computed on nine months of 2026, not on the
393-day window the spec states.** Exposed quarter-hours and negative-price quarter-hours
coincide exactly at **1,853**, which is the expected consequence of θ ≤ 0.

### Distinct θ values across cohorts, as a share of exposed quarter-hours

| AW setting | exposed QH | ≥2 distinct | ≥3 distinct | mean distinct | in −5…0: ≥2 | months θ ≡ 0 fleet-wide |
|---|---|---|---|---|---|---|
| low | 1,853 | **26.6%** | 26.6% | 1.93 | 15.9% | **8 of 9** |
| main | 1,853 | 62.5% | 34.1% | 2.37 | 57.2% | **4 of 9** |
| high | 1,853 | 80.1% | 61.8% | 3.26 | 73.9% | 0 of 9 |
| stress | 1,853 | **34.1%** | 27.6% | 1.75 | 25.4% | **7 of 9** |

Per month, share of exposed quarter-hours with ≥2 distinct θ:

| month | exposed | low | main | high | stress |
|---|---|---|---|---|---|
| 2026-01 | 10 | 0% | 0% | 100% | 0% |
| 2026-02 | 23 | 0% | 100% | 100% | 0% |
| 2026-03 | 139 | 0% | 100% | 100% | 100% |
| 2026-04 | 492 | **100%** | 100% | 100% | 100% |
| 2026-05 | 315 | 0% | 0% | 100% | 0% |
| 2026-06 | 199 | 0% | 100% | 100% | 0% |
| 2026-07 | 306 | 0% | 100% | 100% | 0% |
| 2026-08 | 226 | 0% | 0% | 0% | 0% |
| 2026-09 | 143 | 0% | 0% | 0% | 0% |

**At AW `low`, all 492 separating quarter-hours are April 2026.** The entire cohort
structure at that setting rests on one month.

### A correction to `docs/09`

`docs/09` says the −5…0 band "carries most of the information". It carries most of the
**observations** — 1,261 of 1,853 exposed quarter-hours — but *less* separation than
average at every setting: 15.9% against 26.6% (low), 57.2% against 62.5% (main), 73.9%
against 80.1% (high), 25.4% against 34.1% (stress). The shallow band is where the
quarter-hours are, not where the cohort contrast is.

### Which channel carries the separation

Counterfactuals, each isolating one channel, on the separating exposed quarter-hours. A
≥2 share saturates at 100% wherever all three channels happen to be live, so the mean
number of distinct θ values is what discriminates.

| channel | low | main | high | stress |
|---|---|---|---|---|
| actual | 4.49 | 3.19 | 3.83 | 3.19 |
| run-length / trigger alone | 2.00 | 2.00 | 2.00 | 2.00 |
| **premium spread alone** | **7.00** | **4.36** | **6.65** | **5.34** |
| support status alone | 2.00 | 2.00 | 2.00 | 2.00 |

The premium spread is much the richest channel; the trigger and support-status channels are
**binary by construction** — each splits the fleet in two and can never do more. So
separation rests on the one channel that vanishes whenever MV ≥ AW. This is the mechanism
behind v1.8's observation that the clock never separates cohorts on its own.

*On comparability:* v1.8's decomposition counts quarter-hours where **exposure** differs;
this one counts distinct **θ**. θ differing does not imply exposure differing — the price
must fall between two thresholds — so the two are upstream and downstream of each other and
the numbers are not directly comparable. Nothing here contradicts v1.8.

### Plain answer: is tier 1 identified on real data?

**No, not robustly.**

* AW `high` — identified. 80.1% of exposed quarter-hours separate, 61.8% three ways, no
  flat month.
* AW `main` — weakly identified. 62.5% separate, but **4 of 9 months have no cohort
  structure at all**.
* AW `low` — **not identified.** 26.6%, 8 of 9 months flat, and every separating
  quarter-hour in a single month.
* Base-tariff `stress` — **not identified.** 34.1%, 7 of 9 months flat.

Rule 19 requires the result to be reported across all three AW settings, and v1.8 makes
"stability of r̂ across these three θ settings" the primary real-data identification check.
A design that is identified at one end of the award-value range and not at the other cannot
deliver that stability. **Tier 1 should not be assumed; which tier the thesis runs on is a
supervisor decision.** Flagged as such in spec v1.9 §3 I4.

---

## Step 3 — the float `tobytes()` trap

Every site that keys, groups or hashes a float buffer:

| site | what it keys | exposed? |
|---|---|---|
| `src/censoring/identification.py:177` `_row_key` | θ and `(s, depth)` rows | **No** — normalised with `+ 0.0`, with a regression test |
| `src/e1_cmp_mastr.py:25` | `s[i].tobytes()` | No — see below |
| `src/e1_cmp_mastr.py:54` | `mat[i].tobytes()` (that same `s`) | No |
| `tests/test_identification.py:47` | asserts the trap exists | No — that is its job |
| `e1_cmp_rank.py:22`, `e1_cmp_mastr.py:43`, `e1_cmp_synthetic.py:50` | `np.unique(s.T, axis=0)` | No — see below |

Four claims verified rather than assumed:

1. **`s` cannot hold −0.0.** It is built as `(price < theta).astype(float)` — a bool
   comparison — so its values are exactly `+0.0` and `1.0`. The two `e1_cmp_mastr.py` sites
   key on `s`, so they are safe.
2. **θ can.** `-np.maximum(0.0, aw - ref)` returns `-0.0` wherever the premium is zero
   (`signbit` set). θ is the vulnerable array, and `identification.py` is the only place
   that keys on it — already fixed.
3. **`depth` cannot.** `np.maximum(0.0, ·)` returns `+0.0`, and `+0.0 × 0.0 = +0.0`.
4. **`np.unique(axis=0)` does not suffer the trap**, because it compares with `==` and
   `-0.0 == 0.0`, so the rows collapse. The asymmetry is the point: `tobytes()` compares
   **bits**, `np.unique` compares **values**. Non-obvious, and worth knowing before anyone
   "optimises" a `np.unique` into a byte key.

**Nothing clearly broken, so nothing fixed.** The two `e1_cmp_mastr.py` sites are latently
exposed — they would break if repointed at θ — and routing them through `_row_key` would put
the invariant in one place, but that is a tidy-up, not a fix, and the task says fix only the
clearly-broken.

---

## Step 4 — the fallback re-spec

Written to `docs/06_pivot_mechanism_aware_censoring.md` as a **v1.9** changes block plus an
amended §3 I4, with the v1.2 and v1.3 wordings kept inline as superseded, in the style the
doc already uses for the gate criteria.

**Numbering:** the brief called it v1.4, tracking the I4 clause's own lineage. v1.4 is
already a whole-spec revision of 30 Oct and the doc is at v1.8, so this is **v1.9**. Noted
in the doc.

**It is not pre-registered, and cannot be by me.** v1.8's minute reads "No further gate
changes without the student's written decision", and both the tiered fallback and the new
drop trigger are gate changes. They are recorded now so they *can* be adopted before the
merged grid is scored — a fallback chosen with the gate result in hand is not a
pre-registration — and they take effect only on that decision.

Summary of the amended clause: tier 1 K cohorts → tier 2 macro-cohorts by **θ regime**
(always 0 / switching / never 0), pooling r but not s → tier 3 one shared monotone r, with
the explicit note that tier 3 makes the claim structural rather than cohort-heterogeneous
and that RQ2's "and r_k" clause cannot be answered from it. Drop trigger: full rank on
`[s | depth]`, a per-pair floor of 10 quarter-hours, `cond(s) ≤ 100`, with `cond(w·s)`
reported and never gated and `exposure_differs_by_day` demoted to a diagnostic.

---

## Reproducing

```
python -m src.censoring.theta_audit --step mv      # step 1
python -m src.censoring.theta_audit --step theta   # step 2
python -m src.censoring.theta_audit                # both
```

Read-only. DE, no shuffling, `data/raw/` untouched. In a worktree, symlink
`data/processed` and `data/raw`.
