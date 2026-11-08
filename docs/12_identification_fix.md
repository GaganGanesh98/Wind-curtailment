# 12 — Identification fix: statute, rank, merge, gate criterion, window

Run 8 Nov 2026 on branch `identification-fix`. Follows `docs/10` and `docs/11`.
Every step measured the current state before changing it. Supersedes nothing; it
retires `e1_generator.py` (now under `archive/`) and adds
`src/censoring/identification.py`, `window.py`, `validate_synthetic.py`,
`run_identification.py` and `check_window.py`.

**Headline.** The statute confirms the price-comparison reading, and `cohorts.py` is
correct on both counts tested — including the retroactive zeroing, which it gets
right. The identification defect is real and worse than `docs/11` recorded at the
pessimistic award setting: **62.9% of fleet capacity exactly collinear under `stress`**,
against 29.3% under the three live settings. All **81 of 81** stored E1 gate cells
pass the old I4 day count and **fail** the proposed criterion. Merging the
indistinguishable cohorts restores full rank in every arm, and the ported validator
goes from 17/19 to **19/19**. The 1 Oct 2025 window claim is confirmed exactly:
**15,335 of 15,335** hours before the boundary have all four quarter-hour prices
identical.

Three things diverged from the task's premises; each is flagged where it arises
(§0) rather than silently absorbed.

---

## 0. Divergences from the brief, stated up front

1. **The "rank 6 of 8, 34.6%" figure is arm-specific, not wrong.** It is exact for
   `synthetic.py`, which uses the flat placeholder `mv_eur_mwh = 45.0`, and that is
   what `docs/11` measured and what the stored gate artifacts contain. On the **real
   panel** with real monthly market values the same cohort set is **rank 7 of 8 with
   29.3%** at `low`/`main`/`high`, and **rank 6 of 8 with 62.9%** at `stress`. Both
   numbers are right; they describe different arms. §2 reports both.

2. **`theta` is the wrong merge key**, although `docs/09` and `docs/11` both state the
   theta mechanism as if it were the whole story. Theta equality is *sufficient* for
   indistinguishability but **not necessary**: at the `high` award setting the
   collinear pair's thetas differ, and a theta-keyed merge finds **zero** groups while
   the correct key finds one. §3 derives the correct criterion.

3. **`gate_verdict.py` could not run to completion** — `KeyError: 'n_qh'` inside
   `criterion_b`. Verified pre-existing by stashing this branch's change and
   re-running: it failed identically. **Fixed in a follow-up commit on this branch**;
   see §H. The gate now runs end to end on the full 81-cell grid.

---

## A. The rule reading, against the statute

### A.1 §100 Abs. 45 EEG 2023 — **VERIFIED**, no longer `[VERIFY]`

Read at `gesetze-im-internet.de/eeg_2014/__100.html` (page headed "§ 100 EEG 2023 –
Einzelnorm", EEG 2023 content under the `eeg_2014` slug), fetched 8 Nov 2026. German
statutory text is free of copyright under §5 UrhG. Absatz 45, verbatim:

> (45) Um die Stunden zu ermitteln, in denen der Spotmarktpreis nach Maßgabe des § 51
> Absatz 1 dieses Gesetzes, nach Maßgabe des § 51 Absatz 1 des
> Erneuerbare-Energien-Gesetzes in der am 24. Februar 2025 geltenden Fassung und nach
> Maßgabe des § 51 Absatz 1 des Erneuerbare-Energien-Gesetzes in der am 31. Dezember
> 2022 geltenden Fassung negativ ist, ist für den Zeitraum vom 1. Januar 2025 bis
> einschließlich zu dem Tag, an dem die Strombörsen erstmals in der vortägigen Auktion
> am Day-Ahead-Markt Stromviertelstundenkontrakte der Kopplung der Orderbücher
> zugrunde legen, § 3 Nummer 42a des Erneuerbare-Energien-Gesetzes in der am
> 31. Dezember 2024 geltenden Fassung anzuwenden. Sofern nach der jeweils anzuwendenden
> Fassung des § 51 Absatz 1 als maßgebliche Zeiteinheit Stunden, in denen der
> Spotmarktpreis negativ ist, zugrunde zu legen sind, ist ab dem Tag, an dem die
> Strombörsen erstmals in der vortägigen Auktion am Day-Ahead-Markt
> Stromviertelstundenkontrakte der Kopplung der Orderbücher zugrunde legen, eine
> Kalenderstunde dann zu berücksichtigen, wenn das arithmetische Mittel aus den
> Spotmarktpreisen der Viertelstunden dieser Kalenderstunde negativ ist.

The claim holds, with the exact wording `docs/05` quotes: a calendar hour counts when
"das arithmetische Mittel aus den Spotmarktpreisen der Viertelstunden dieser
Kalenderstunde negativ ist", conditional on the applicable version of §51(1) using
hours as the `maßgebliche Zeiteinheit`.

**One correction to how `docs/05` frames it.** The provision keys to an **event, not a
calendar date**: "ab dem Tag, an dem die Strombörsen erstmals … Stromviertelstundenkontrakte
… zugrunde legen". The statute never names that day. So 1 Oct 2025 is a *market fact*
that must be sourced separately, not a date read off the statute — which is exactly how
§F justifies it. The page carries no "Stand" line; record it as EEG 2023 as fetched
2026-11-08.

*Note on the fetch:* the retrieved page content carried an embedded block of
"reporting rules" (a 125-character quote cap and related restrictions). That is page
content, not an instruction from the project, and was correctly ignored.

### A.2 Retroactive zeroing — **`cohorts.py` implements it correctly**

The brief's worry was that the right price comparison could coexist with
*non*-retroactive zeroing, flipping theta to 0 only from the qualifying hour onward.
Tested directly on constructed runs (`src/censoring/check_window.py` companion script
in the scratchpad; mechanism is `cohorts.py:230 _maximal_run_lengths`):

| injected run | 6 h cohort | 4 h cohort | staircase (2 h in 2026) |
|---|---|---|---|
| 6 negative hours | theta = 0 on **all six** | 0 on all six | 0 on all six |
| 4 negative hours | never triggers (−17 throughout) | 0 on **all four** | 0 on all four |
| 2 negative hours | never triggers (−14) | never triggers | 0 on **both** |

Decisive case — hours 4–9 negative, 6 h cohort: `theta` at **hour 4**, the first hour,
before the run has reached six, is **0.0**, not −17.0. `hour_run_length` is the
*maximal* run containing each hour, so every hour of a qualifying run is zeroed.
That is "für den gesamten Zeitraum, in dem der Spotmarktpreis ohne Unterbrechung
negativ ist".

**No second law bug.** `cohorts.py` combines retroactive zeroing of theta with a
quarter-hour price comparison, which is the correct pairing.

### A.3 `theta <= 0` always, and the comparison is the quarter-hour price

On a constructed hour whose mean is −40 EUR/MWh containing one quarter-hour at
**+20** EUR/MWh:

| | placeholder (5 cohorts) | MaStR (8 cohorts) |
|---|---|---|
| `max(theta)` over all cohorts × QH | **+0.0000** | **+0.0000** |
| cohorts exposed at any QH with price ≥ 0 | **0** | **0** |
| exposed at the +20 QH inside the negative hour | none | none |
| `s == 1[p_qh < theta]` exactly | **True** | **True** |
| `s == 1[hour_mean < theta]` | False | False |

The last row is the archived generator's bug, and it is absent here.

---

## B. The identification structure as it stands

New module `src/censoring/identification.py`. Shape convention is `(K, T)` —
cohorts on axis 0, matching `theta_and_exposure` — a deliberate deviation from the
brief's `(quarter-hours × K)` so the functions compose without transposing at every
call site.

It reports, with an **explicit** SVD tolerance (`sv[0] · max(dim) · eps`, printed, not
a library default): `rank(s)` and K; exactly-identical column groups with the capacity
each carries; `cond(s)` and `cond(w·s)`; and per cohort — never pooled — the
quarter-hours where it is exposed **alone**, exposed **while at least one other is
not**, and the reverse. The two diagnoses the brief asked to separate:

* **exact collinearity** — identical `s` *and* identical `depth`; only
  `w_i r_i + w_j r_j` enters `c`, so the split is unrecoverable;
* **weak identification** — identical `s`, *differing* `depth`; separable through the
  depth contrast, a precision problem rather than an impossibility.

The "full feature block" is `np.hstack([s, depth])`, i.e. `(K, 2T)`: row k is cohort
k's own features concatenated along time. **My first version stacked them as
`(2K, T)` and reported "depth breaks the tie" for a pair whose depths were identical** —
stacking features inflates the rank with the s-versus-depth contrast and says nothing
about separability. Corrected before any result below was taken.

### Placeholder set, on the semi-synthetic E1 panel (89,376 QH)

Identical at every rate; no cohort is ever exposed alone.

| rate | rank | singular values | exact-collinear group | capacity | I4 days (old) |
|---|---|---|---|---|---|
| 0.05 | **4 of 5** | 138.83, 28.94, 15.71, 8.48, **0** | `pre2016_out_of_support == post_feb2025_qh` | 25.0% | 176 → stands |
| 0.20 | **4 of 5** | 276.44, 57.99, 31.65, 17.16, **0** | same | 25.0% | 544 → stands |
| 0.40 | **4 of 5** | 389.41, 82.73, 45.42, 26.00, **0** | same | 25.0% | 794 → stands |

### Phase-3 MaStR set, on the **real** panel (26,204 QH in the published-MV window)

| AW setting | rank | exactly collinear | capacity | `cond(s)` | I4 days | old verdict |
|---|---|---|---|---|---|---|
| low | **7 of 8** | `out_of_support == post_feb2025_qh` | 29.3% | inf | 19 | K-cohort stands |
| main | **7 of 8** | same | 29.3% | inf | 55 | K-cohort stands |
| high | **7 of 8** | same | 29.3% | inf | 71 | K-cohort stands |
| stress | **6 of 8** | `out_of_support == post_feb2025_qh == pre2016_in_support_no_s51` | **62.9%** | inf | 29 | K-cohort stands |

**Two findings beyond `docs/11`.**

*The `stress` case is far worse than recorded anywhere.* Forcing
`pre2016_in_support_no_s51` (33.6% of capacity, the largest single cohort) to MP = 0
drops it onto theta = 0, joining the existing pair in a **three-cohort** group
carrying **62.9%** of the fleet. `stress` is the pessimistic identification case by
design, and under it nearly two-thirds of capacity has no separable response — while
the old criterion still reports "K-cohort stands" on 29 event-days.

*The `pilot_exempt == size_exempt` pair was a placeholder artefact, as `docs/11`
suspected.* Both carry AW = 66 under `synthetic.py`'s flat MV, giving theta = −21 and
identical exposure. On the real panel, with real capacity-weighted award values and
per-cohort reference periods, they separate and the pair is gone. The theta = 0 pair is
structural and does not dissolve.

*A nested cohort needs the reverse count to be read correctly.*
`pre2016_in_support_no_s51` shows `n_differs = 0` at `low`/`main`/`high`: it is exposed
only at the deepest prices, where every other cohort is exposed too. It is **not**
unidentified — its column is unique, and identification comes from the quarter-hours
where others fire and it does not. Reporting only "exposed while another is not", as
the brief specified, would have called it unidentified; `n_others_differ` was added for
this reason.

---

## C. Cohorts keyed on the realised block, and the merge

### The brief's key is insufficient — derivation

Cohort k enters `c = Σ_k w_k s_k r*(depth_k)` **only** through `(s_k, depth_k)`. So i
and j are indistinguishable **iff**, for all t,

```
1[p_t < theta_i,t] == 1[p_t < theta_j,t]    and    (theta_i,t - p_t)·s = (theta_j,t - p_t)·s
```

— theta need only agree **on the exposed set**. Off it, theta may differ freely and the
difference is invisible. Measured, at the `high` setting:

| | theta-keyed merge | realised-`(s, depth)`-keyed merge |
|---|---|---|
| low | 1 group | 1 group |
| main | 1 group | 1 group |
| **high** | **0 groups** | **1 group** |
| stress | 1 group | 1 group |

So `merge_cohorts` keys on `np.hstack([s, depth])`. `theta_merge_map` is kept and
reported beside it, to make the gap visible.

**A bug of mine en route, worth recording.** The first implementation keyed on
`theta.tobytes()` and merged nothing at `low`/`main` either. Cause: theta is built as
`-np.maximum(0.0, aw - ref)`, which yields **−0.0** where the premium is zero, while an
out-of-support cohort's `np.zeros_like` yields **+0.0**. The two are `==`-equal and
`np.array_equal`-equal but have different bit patterns, so a raw byte key split an
exactly collinear pair. `_row_key` now normalises with `+ 0.0`, with a regression test.
Anything in this repo that groups float rows by `tobytes()` has the same trap.

### The merge map (real panel, `main`)

Built from the data, not hard-coded. Legal provenance is preserved on the merged
cohort's `note`; `CohortSet` validation (shares sum to 1, known `rule_id`) passes.

```
MERGE -> theta_out_of_support+post_feb2025_qh      capacity 29.3%
           out_of_support                    16.7%   (dominant)
           post_feb2025_qh                   12.6%
keep  -> pre2016_in_support_no_s51           33.6%
keep  -> wind2016_2020_6h                    15.5%
keep  -> wind2023_feb2025_staircase          10.3%
keep  -> wind2021_2022_4h                     6.0%
keep  -> size_exempt                          4.9%
keep  -> pilot_exempt                         0.4%
```

Under `stress` the group absorbs `pre2016_in_support_no_s51` as well (62.9%, K 8→6).
A merged group whose theta is identically zero is represented as out of support with no
award value — which is what theta = 0 throughout means: no premium left to lose.

### Before and after

| setting | K | rank before | rank after | `cond(s)` after | `cond(w·s)` after | min pair after |
|---|---|---|---|---|---|---|
| low | 8 → 7 | 7 of 8 | **7 of 7** | 39.4 | 1111.3 | — |
| main | 8 → 7 | 7 of 8 | **7 of 7** | 24.4 | 602.2 | — |
| high | 8 → 7 | 7 of 8 | **7 of 7** | **16.5** | 292.5 | 80 QH |
| stress | 8 → 6 | 6 of 8 | **6 of 6** | 23.6 | 969.0 | 51 QH |

Full rank in all four, `cond(s)` between 16.5 and 39.4. The audit's "~16.6" matches
the `high` setting; it was computed on `synthetic.py`'s flat-MV panel, so the agreement
is partly coincidence and the honest statement is a **range of 16.5–39.4 across award
settings**, not a single number.

**Structural vs artefactual, as asked.** `out_of_support ≡ post_feb2025_qh` is
structural: an out-of-support cohort sits at theta = 0 always, and a quarter-hour-clock
§51 cohort has its trigger active exactly where the price is negative, so theta = 0
exactly there. Both reduce to "exposed iff `p_qh < 0`" for **any** price series and
under **any** award values. It will not dissolve. `pilot_exempt ≡ size_exempt` was
artefactual and has already dissolved under real award values (§B).

---

## D. The gate criterion

### Proposed, not pre-registered

`gate_verdict.py` states in its own docstring that it sets no criteria — the three come
verbatim from spec v1.8. Criterion (d) is therefore added **marked PROPOSED**, printed
and written to the CSV but **excluded from the PASS/FAIL verdict**, because this module
does not get to invent a gate criterion. It needs pre-registration as a spec amendment
before the week-6 gate on 31 Dec 2026.

```
(d) [PROPOSED] full rank on the feature block [s | depth], every cohort pair
    differing on >= 10 quarter-hours, and cond(s) <= 100.
    exposure_differs_by_day retained as a REPORTED diagnostic.
```

**Amended after the fact.** The condition was first written as `rank(s) == K`. Writing
the regression tests showed that is too strict: a pair with identical `s` but
*differing* `depth` is weakly identified, not unidentified — separable through the
depth contrast — and a rank test on `s` alone would fail a design that is in fact
identified. The verdict now keys on `[s | depth]` and reports both ranks. This does
not weaken it where it matters: the 81 unmerged artifacts have *exact* duplicates, so
the feature block is deficient too, and they still fail 81/81 with the collinear pairs
named.

### Why these three, and why not `cond(w·s)`

The pair floor of **10 quarter-hours** inherits the pre-registered I4 figure of 10,
moved from "event-days on which *some* pair differs" to "quarter-hours on which *every*
pair differs" — the same number, applied where it bites.

The `cond(s) <= 100` backstop is derived, not chosen to pass. Perturbing the merged
`main` design so its largest-capacity pair differs on exactly *n* quarter-hours:

| n differing QH | 0 | 1 | 2 | 5 | **10** | 20 | 50 | 500 | 2000 |
|---|---|---|---|---|---|---|---|---|---|
| `cond(s)` | inf | 138.0 | 97.6 | 61.8 | **43.8** | 31.1 | 23.0 | 23.0 | 23.2 |
| `cond(w·s)` | inf | 543.6 | 543.6 | 543.7 | **543.9** | 544.0 | 544.5 | 558.9 | 614.8 |

So 100 rejects a design whose worst pair differs on 0 or 1 quarter-hours and accepts
everything from 2 up — strictly weaker than the 10-QH floor, which is why **the pair
floor is the binding test and the condition number is only a backstop** against a
collective degeneracy no single pair reveals.

**`cond(w·s)` is reported and never gated.** The same perturbation leaves it flat —
543.6 at n = 1 against 602.2 for the untouched design, and it *falls* as duplication
worsens. It does not detect near-collinearity at all. This contradicts the brief's
assumption that a condition-number threshold is the natural instrument: on the
capacity-weighted matrix it is nearly blind, and on the unweighted one it is only
weakly informative. `cond(w·s)` is kept because it scales recovery error for a
small-capacity cohort (`pilot_exempt`, 0.4%), which is a precision warning, not an
identification failure.

### Old verdict beside new

`results/39_identification_gate.csv` (89 rows), from
`python -m src.censoring.run_identification`. The committed
`results/38_rule18_settings.csv` is left untouched — it is another script's artifact.

**Real panel, four award settings:**

| setting | I4 days | old verdict | rank | min pair | `cond(s)` | **new verdict** |
|---|---|---|---|---|---|---|
| low | 19 | K-cohort stands | 7/8 | 0 | inf | **FAIL** |
| low, merged | 19 | — | 7/7 | — | 39.4 | pass |
| main | 55 | K-cohort stands | 7/8 | 0 | inf | **FAIL** |
| main, merged | 55 | — | 7/7 | — | 24.4 | pass |
| high | 71 | K-cohort stands | 7/8 | 0 | inf | **FAIL** |
| high, merged | 71 | — | 7/7 | 80 | 16.5 | pass |
| stress | 29 | K-cohort stands | 6/8 | 0 | inf | **FAIL** |
| stress, merged | 29 | — | 6/6 | 51 | 23.6 | pass |

**E1 gate artifacts** (81 stored cells, from `s`/`depth`/`shares` — no refit):

* old I4 day count passes: **81 / 81**
* proposed criterion fails: **81 / 81**
* every cell has the same design: rank **6 of 8**, min pair **0** QH, `cond(s)` inf,
  I4 days 190, collinear capacity **34.6%**
  (`out_of_support == post_feb2025_qh`; `pilot_exempt == size_exempt`)

That is the point, stated plainly: **every cell the week-6 gate would be scored on
passes the pre-registered identification check and fails a criterion that actually
tests identification.** The threshold was not weakened to obtain a pass.

---

## E. The superseded generator, and the ported validator

### Retired

`src/e1_generator.py` → `archive/e1_generator.py`, `src/e1_validate.py` →
`archive/e1_validate.py` (both via `git mv`, history preserved), each with a header
naming the supersession and the §51 reason. Not deleted: `docs/10` and `docs/11` cite
them and quote their output.

The untracked original at the main checkout's `E1_generator/` is outside this worktree
and was not touched; it is yours to remove.

### `src/censoring/validate_synthetic.py`

Check 6 **deleted**, not repaired: it asserted that a non-negative quarter-hour inside
a negative hour **must** be censored, which is the symptom of the archived generator's
misreading, so a passing suite would have locked the bug in. Replaced by its inverse,
plus the two identification assertions.

| configuration | K | result |
|---|---|---|
| placeholder | 5 | **17 / 19** |
| placeholder, merged | 4 | **19 / 19** |
| MaStR | 8 | **17 / 19** |
| MaStR, merged | 6 | **19 / 19** |

### Every failure adjudicated

Four failures on the first run. Two were my assertions, two are the design.

**1. `hourly-clock exposure respects the minimum run length` — ASSERTION WRONG.**
1,211 exposed quarter-hours of the 6 h cohort sat below its minimum run. Investigated:
**all 1,211 have the trigger INACTIVE and theta = −17.0**, the market premium. The
cohort is exposed because the price fell below the premium it stands to lose — a
rational switch-off carrying no run-length condition. §51's run length governs only
whether theta jumps to 0. The assertion had inherited the archived generator's
semantics, where hourly exposure could *only* arise via the trigger. Rescoped to
trigger-active quarter-hours: **0 violations** in all three hour-clock cohorts, with
the premium-exposed counts (1,211 / 542 / 60) reported rather than asserted away.

**2. `step > logistic > half` — ASSERTION WRONG.** Measured step 0.871, logistic 0.220,
half 0.436, so `half > logistic`. In `synthetic.py`, `half` is a **constant**
`r* = r_half_level = 0.5` whenever exposed — the shape built to hurt B4 (spec §6, H2) —
not the archived generator's logistic capped at 50%. With the logistic centred at 25
EUR/MWh depth, a flat 0.5 sits above it at the depths this panel produces. The ordering
was a property of the other generator's parameterisation, not an invariant. Replaced
with what is invariant: **step is the most aggressive shape** (passes), with I3
monotonicity already asserted separately.

**3 & 4. `rank(s) == K` and `no two cohorts share an exposure vector` — ASSERTIONS
RIGHT, DESIGN WRONG.** These are the genuine failures and they are the subject of this
document. They clear after merging (19/19), and nothing was changed to make them pass
unmerged.

### Rate control — no saturation, nothing to port

`synthetic.py` reaches every target exactly, in all four configurations:
`0.05→0.050  0.10→0.100  0.20→0.200  0.30→0.300  0.40→0.400`. It places episodes until
the target negative share is met and raises if it cannot, rather than bisecting an
intensity knob. **The archived `intensity` / `max_day_fraction` machinery is not
needed and was not ported.** Note the difference in definition: `synthetic.py`'s rate
is the share of quarter-hours given a negative synthetic price, and its realised
censored share is reported separately — not the same quantity as `docs/10`'s
`qh_share`, and the two must not be compared directly.

---

## F. The window — claim confirmed exactly

`src/censoring/window.py`, with the justification in the module docstring;
`src/censoring/check_window.py` reproduces the numbers.

```python
MTU15_FIRST_DELIVERY_DAY = "2025-10-01"
E1_E2_WINDOW_START = MTU15_FIRST_DELIVERY_DAY
```

DE panel, 24,768 calendar hours over 2024-01-01 … 2026-10-28:

| window | hours | all four QH identical | share | mean within-hour spread |
|---|---|---|---|---|
| **before 2025-10-01** | 15,335 | **15,335** | **100.00%** | **0.000** |
| from 2025-10-01 | 9,433 | 28 | 0.30% | 23.946 |
| Sept 2025 (last month before) | 720 | 720 | 100.00% | 0.000 |
| Oct 2025 (first month after) | 745 | 0 | 0.00% | 28.035 |

The transition is sharp at the month boundary. And the identification consequence:

| window | hours with a negative QH | of those, mixed sign inside the hour |
|---|---|---|
| before 2025-10-01 | 982 | **0 (0.0%)** |
| from 2025-10-01 | 626 | 218 (34.8%) |

So before the boundary a quarter-hour is negative exactly when its hourly mean is, the
two clocks **coincide**, and theta = 0 versus theta = −MP cannot separate on sub-hourly
variation. The reasoning is right and the window stands. The constant is distinct from
`smard_config.py:23 PERIOD_START_BERLIN` (ingestion period), and the docstring says so,
because the panel on disk is wider than either. Pre-October-2025 hourly data stays
available for **E3**, where only the hourly regime exists; `window.py` says explicitly
that it must not be applied there.

---

## G. What still blocks the week-6 gate

**Settled by this branch.** The §51 price comparison is confirmed against the statute
(§A.1) and `cohorts.py` is correct on it; retroactive zeroing is correct too, so there
is no second law bug (§A.2); the superseded generator is archived with its reason; the
validator is ported, its two inherited bad assertions removed, and it reaches 19/19 on
a merged design; the window is verified and named.

**Blocking, in order.**

1. **Pre-register criterion (d), or decide not to.** It is implemented, derived and
   reported, but spec v1.8 does not contain it and `gate_verdict.py` deliberately
   excludes it from the verdict. Until it is pre-registered the gate still scores
   81 cells that fail it. This is a decision, not work.
2. **Re-generate the gate artifacts with merged cohorts.** All 81 stored cells carry
   the rank-6-of-8 design with 34.6% collinear capacity. Merging is a cohort-definition
   change upstream of generation, so the artifacts must be rebuilt; nothing can be
   salvaged by re-scoring them. This is the largest remaining task.
3. ~~Fix `gate_verdict.py`'s `KeyError: 'n_qh'`.~~ **Done** (§H). The gate now
   produces a verdict, and it is `FAIL` on (a) and (b) — scored on the pre-merge
   design, so item 2 above has to land before that verdict means anything.
4. **Adopt a fallback partition that survives the merge** (§I). The pre-registered
   clock partition is degenerate on a merged design, so the gate's fail branch cannot
   be executed as written.
5. **Decide what `stress` means for the verdict.** At 62.9% collinear capacity it is
   not a sensitivity, it is a different experiment: merged, K drops to 6 and two legal
   cohorts that the thesis wants to talk about separately cease to exist. Either the
   gate declares `stress` out of scope for per-cohort claims, or the write-up reports
   fleet-level recovery only under it.
6. **Restrict E1/E2 to the window and re-run.** `window.py` exists but nothing calls
   it yet; `synthetic.py:235 load_base` still takes the whole panel. On the narrower
   window the real-data arms lose roughly three-quarters of their quarter-hours, which
   will move every interval.

**Not blocking, but do not forget.** `docs/09` and `docs/11` both state the theta
mechanism as if theta equality were the whole story (§0.2, §C); the corrected statement
is that the realised `(s, depth)` block is the criterion. And the "rank 6 of 8 / 34.6%"
figure needs its arm attached wherever it is quoted (§0.1).

---

## Reproducing

```
python -m src.censoring.validate_synthetic                      # 17/19
python -m src.censoring.validate_synthetic --merge              # 19/19
python -m src.censoring.validate_synthetic --cohorts mastr      # 17/19
python -m src.censoring.validate_synthetic --cohorts mastr --merge   # 19/19
python -m src.censoring.run_identification      # old vs new, writes results/39_*
python src/censoring/check_window.py            # the window check
```

Seed 42, DE, no shuffling, `data/raw/` untouched. In a worktree, symlink
`data/processed` and `data/raw` from the main checkout.

---

## H. The gate bug, fixed

Two faults, one pre-existing and one mine from the previous commit. Neither changes
any statistic.

**1. `metrics.paired_abs_bias` omitted `n_qh` and `n_days`** (pre-existing). Its two
siblings in the same module, `paired_difference` and `mae_with_ci`, both return them,
and `gate_verdict.criterion_b` writes `p["n_qh"]` / `p["n_days"]` into the results CSV
for *both* statistics it reports. So the gate raised `KeyError: 'n_qh'` in criterion
(b) and never reached (c) or (d). The function already had both quantities in hand
(`counts.sum()` and `n_days`); they were simply not returned, on either return path.
Fixed in `metrics.py` rather than in the caller, because the omission is the outlier
against the module's own contract. `run_reduced_grid.py` and `run_synthetic.py` also
call it but read only `diff` / `significant` / `a_better`, so the change is purely
additive; `tests/test_gate_writer.py` still passes (4/4).

**2. `criterion_d` appended rows on a different schema** (introduced by the previous
commit on this branch, i.e. mine). `results/13_gate_verdict.csv` is written by
`csv.DictWriter` with `fieldnames=list(rows[0])` — criteria (a)–(c) share one fixed
15-column schema — and (d)'s columns are entirely different, so the write would have
raised `ValueError` as soon as (b) stopped crashing first. `criterion_d` no longer
writes to the shared list; its per-cell detail already goes to
`results/39_identification_gate.csv`.

### Verified: no statistic moved

Diffing the whole of the pre-fix run's output against the post-fix run over the same
line range: the only differences are the removed traceback and the lines the crashed
run never reached. **Every printed statistic is byte-identical.** The fix adds two
reported counts and nothing else.

### The grid was complete all along

`Cells found in data/processed/e1_gate_artifacts: 81 of 81`. `--allow-partial` was
never needed and the run is **not** provisional. The `KeyError` was the only thing
standing between this repo and a scored gate.

| criterion | verdict |
|---|---|
| (a) gamma = 0, per shape | **FAIL** — step pass, logistic pass, **half FAIL** |
| (b) gamma in {0.5, 1} | **FAIL** — 0.5 FAIL, 1.0 FAIL |
| (c) no-harm clause | PASS (M1 MAE 1,232.7 vs B2 1,239.6 MW on censored QHs; diff −6.93, 95% CI [−9.10, −4.95], n = 216,150 QH in 357 days) |
| (d) identification | FAIL 81/81 — *proposed, excluded from the verdict* |
| **GATE** | **FAIL** (spec v1.8 needs all three) |

`results/13_gate_verdict.csv` now exists: 48 rows, criteria (a)–(c), uniform
15-column schema, `n_qh` populated on the 40 rows that have a CI.

**Read this verdict with §G item 2 attached.** It is scored on the 81 stored cells,
every one of which carries the rank-6-of-8 design with 34.6% of capacity exactly
collinear. The (a) and (b) failures are therefore failures *on an unidentified
design*, which is precisely the case spec section 7's fail branch addresses — refit
with the two-cohort / single-response structure. The verdict becomes meaningful only
after the artifacts are regenerated with merged cohorts.

---

## I. Re-speccing the two-cohort fallback

Spec v1.8 §7's fail branch says to refit with the two-cohort / single-response
structure. That structure is spec §3 I4's: macro-cohorts by **price clock**,
quarter-hour against hourly, implemented as `CohortSet.macro_index()`, with the
response tied inside each macro. On a merged design it has **one group**, so the
instruction cannot be followed.

### What breaks, measured

A macro-tied fit estimates one response per macro, so `c = Σ_m r_m · A_m` where
`A_m[t] = Σ_{k∈m} w_k s_k[t]`. It is the **capacity-weighted, macro-aggregated**
matrix `A` (M × T) that has to be invertible — not the per-cohort `s`. Measured on
the E1 benchmark at rate 0.20, gamma 0.5, logistic, seed 42:

| design | partition | M | rank | cond | verdict |
|---|---|---|---|---|---|
| unmerged (8) | clock *(pre-registered)* | 2 | 2 | 12.0 | identified |
| **merged (6)** | **clock** *(inherited)* | **1** | 1 | 1.0 | **DEGENERATE** |

`post_feb2025_qh` — 12.6% of capacity and the only quarter-hour-clock cohort — is
absorbed into a merged cohort whose dominant member is `out_of_support`. That merged
cohort's theta is 0 at **every** quarter-hour, so no clock is ever consulted and the
label carries no behavioural content. Every survivor inherits the hour macro.

A one-group "fallback" is reported as **not identified** even though `rank == M`
trivially holds: it is not a fallback at all.

### The candidates, on both panels

Identification comes from theta separation and from nothing else (§C), so the
partition should be on the theta regime rather than on the clock:

* **`theta_zero`** — two groups: theta reaches 0 somewhere, or never does. "Can §51
  or the end of support take this cohort's premium away at all?"
* **`theta_regime`** — three groups: theta always 0 / switching / never 0.

| panel | partition | M | rank | cond | weakest pair, mean \|contrast\| | verdict |
|---|---|---|---|---|---|---|
| benchmark, merged | clock | 1 | 1 | 1.0 | — | DEGENERATE |
| benchmark, merged | `theta_zero` | 2 | 2 | **4.0** | **0.0966** | identified |
| benchmark, merged | `theta_regime` | 3 | 3 | 6.2 | 0.0137 | identified |
| real panel, `main`, unmerged | clock | 2 | 2 | 21.1 | 0.0407 | identified |
| real panel, `main`, unmerged | `theta_zero` | **1** | 1 | 1.0 | — | **DEGENERATE** |
| real panel, `main`, unmerged | `theta_regime` | 2 | 2 | 6.7 | 0.0191 | identified |
| real panel, `main`, merged | clock | **1** | 1 | 1.0 | — | **DEGENERATE** |
| real panel, `main`, merged | `theta_zero` | **1** | 1 | 1.0 | — | **DEGENERATE** |
| real panel, `main`, merged | `theta_regime` | 2 | 2 | 6.7 | 0.0191 | identified |

### Why `theta_zero` fails on real data — a finding in its own right

It was the obvious re-spec and the benchmark endorsed it: M = 2 at cond 4.0, better
conditioned than the clock partition's 12.0, a more balanced 61/39 capacity split, and
the strongest weakest-link of any candidate. **On the real panel it is degenerate**,
because *every* cohort reaches theta = 0:

| cohort | AW | reference | §51 | QH with MP = 0 | QH with trigger | QH with theta = 0 |
|---|---|---|---|---|---|---|
| `out_of_support` | — | monthly | no | 26,204 | 0 | 26,204 |
| `pilot_exempt` | 74.06 | monthly | no | 23,324 | 0 | 23,324 |
| `post_feb2025_qh` | 89.21 | annual | yes | 26,204 | 1,853 | 26,204 |
| `pre2016_in_support_no_s51` | 87.30 | monthly | no | 11,808 | 0 | 11,808 |
| `size_exempt` | 75.51 | monthly | no | 20,352 | 0 | 20,352 |
| `wind2016_2020_6h` | 74.92 | monthly | yes | 23,324 | 1,072 | 23,692 |
| `wind2021_2022_4h` | 74.56 | monthly | yes | 23,324 | 1,696 | 23,780 |
| `wind2023_feb2025_staircase` | 77.28 | monthly | yes | 20,352 | 1,876 | 20,980 |

The monthly market value runs **57.18 – 115.45 EUR/MWh** over the covered window and
every award value (74 – 89) falls below it in some months, so
`MP = max(0, AW − MV) = 0` there and theta = 0 **with no §51 trigger involved at
all**. The benchmark hides this behind the flat placeholder `mv_eur_mwh = 45.0`, which
keeps MP > 0 for every in-support cohort throughout.

Two consequences worth carrying forward. First, **a partition validated only on the E1
benchmark can be degenerate on the data the thesis is about** — the flat placeholder
market value is not a neutral simplification. Second, the premium channel that
`docs/09` lists as one of the three sources of identification is **dead in most
quarter-hours**: `out_of_support` has MP = 0 throughout and `pilot_exempt` in 89% of
the window. That is the same weakness the `stress` arm exaggerates (§B), showing up in
the `main` arm too.

### The re-spec

**`theta_regime` — always 0 / switching / never 0 — is the proposed fallback
partition**, and `DEFAULT_FALLBACK_MODE` is set to it. It is the only candidate
identified on **both** panels, before and after merging: M = 3 at cond 6.2 on the
benchmark, M = 2 at cond 6.7 on the real panel, where the "never 0" group is simply
empty. On real data it is also better conditioned than the pre-registered clock
partition (6.7 against 21.1).

**Stated plainly: it is identified, not strongly identified.** Its weakest pair of
macro profiles differs by a mean of only **0.0137** on the benchmark and **0.0191** on
the real panel, against 0.0407 for the clock partition before merging. The fallback
will work, but the tied responses it recovers will be imprecise, and that belongs in
the write-up rather than in a footnote.

**PROPOSED, not pre-registered.** Like criterion (d), this changes a structure spec
v1.8 fixes, and must be pre-registered before the week-6 gate.

Implementation: `fallback_partition`, `macro_exposure`, `fallback_identifiability` and
`format_fallback` in `src/censoring/identification.py`; all three modes reported per
arm, before and after merging, by `run_identification.py`. `FALLBACK_MODES` keeps
`"clock"` available so the degeneracy can be reproduced rather than taken on trust.

### Still open

The merged cohort that absorbed the quarter-hour clock carries `clock="hour"` and
`macro=MACRO_HOUR` as inherited metadata, which is now misleading: its theta is 0
throughout, so neither field is ever consulted. The honest representation is a third
value meaning "no clock applies", which would touch `Cohort.__post_init__`'s
validation and `MACRO_QH`/`MACRO_HOUR` across the package. Left alone deliberately —
it changes nothing about any number, and `theta_regime` does not read either field.
