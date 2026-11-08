# 09 — E1 generator (`e1_generator.py`): SUPERSEDED, with corrections

**Status as of 8 Nov 2026: do not use `e1_generator.py` for thesis results.**
It is wrong on §51, and `src/censoring/synthetic.py` — already committed — is right.
Kept because several of this doc's own claims were wrong in ways worth recording.

Revision history: written 8 Nov 2026 before the repo state was checked; rewritten the same
day after the first run; corrected after `docs/12_identification_fix.md`; corrected again
after the gate fix and the fallback re-spec (commits `dbb5c47`, `e3585e0`), which postdate
the previous revision and moved three of its claims. **The repo wins on any difference.**

## Why it is superseded

### 1. It misreads §51 (fatal)

`e1_generator.py` evaluates the hourly-clock cohort's exposure against the **hourly mean
price**, so a quarter-hour whose own price is positive, inside a qualifying negative hour,
is treated as switched off. Spec 06 already said otherwise — the θ branches at `docs/06:266`
and `s_k,t = 1[p_t < θ_k,t]` at `docs/06:302`. The clock decides **θ**, not which price the
plant compares against:

    theta_k,t = 0            if support is zeroed (§51 triggered, or out of support)
              = -MP_k,t      otherwise
    s_k,t     = 1[ p_qh,t < theta_k,t ]        -- always the QUARTER-HOUR price

The argument, in order of how much weight it carries:

1. §51's own text zeroes the *anzulegender Wert* and is **silent on switching off**. It
   governs the support payment, not the operating decision.
2. Since the 15-minute market time unit went live for delivery day 1 Oct 2025, day-ahead
   revenue is settled per quarter-hour. A plant whose support is zeroed still earns the
   quarter-hour price; if that price is positive it has no reason to stop.
3. **[VERIFY]** Commentary reportedly states §51 "schreibt keine automatische Abschaltung
   vor". Taken from a commercial blog, not read in a legal source. The conclusion does not
   rest on it — (1) and (2) carry alone — but it must not be cited until found in
   commentary proper.

`retro_run = True` is right about the law — the pre-2025 wording zeroes the value "für den
gesamten Zeitraum, in dem der Spotmarktpreis ohne Unterbrechung negativ ist" — and
`cohorts.py` implements it correctly: θ = 0 at the **first** hour of a qualifying 6-hour run,
while still comparing the quarter-hour price. Right on both, which is the pairing that
matters. The bug was conflating support-zeroing with switch-off.

Worse: validation check 6 **asserted such rows must exist**. A test requiring the bug.

### 2. It duplicated existing work

`src/censoring/synthetic.py` was already committed (`fec1390`) implementing spec 06 §7, with
`metrics.py`, `baselines.py` and `gate_verdict.py` behind it. PROJECT_CONTEXT.md says the
repo wins; the repo was not checked before building.

## §100 Abs. 45 EEG — verified

Read at gesetze-im-internet.de. A calendar hour counts as negative when "das arithmetische
Mittel aus den Spotmarktpreisen der Viertelstunden dieser Kalenderstunde negativ ist",
conditional on the version of §51(1) that counts hours. The `[VERIFY]` is discharged.

One point the earlier framing missed: the provision keys to an **event, not a date** — "ab
dem Tag, an dem die Strombörsen erstmals … Stromviertelstundenkontrakte … zugrunde legen" —
and never names that day. So 1 Oct 2025 is a **market fact needing its own source**, not
something readable off the statute. Cite the SDAC go-live, not §100(45), for the date.

## Corrections to earlier versions of this doc

- **Energy-share band was wrong.** Claimed 6–10% energy share for a 20% quarter-hour rate.
  Measured: **4.3% (half), 7.8% (logistic), 20.4% (step)** — a stable per-shape ratio of the
  quarter-hour rate (×1.00 step, ×0.39 logistic, ×0.21 half).
- **The "thin direction" was the bug, not a data problem.** 1–11 rows across all cells. Those
  rows should not exist at all.
- **"Cohorts defined by distinct θ" is the wrong merge key.** θ equality is *sufficient* but
  not *necessary*: θ need only agree **on the exposed set**, and may differ freely where
  neither cohort is exposed. At the `high` AW setting a θ-keyed merge finds **zero** groups
  while the realised `(s, depth)` block finds one. **Merge on the realised block.**
  (A θ-keyed merge also hit a `-0.0` vs `+0.0` `tobytes()` trap — equal under `==`, different
  bit patterns. Grep the repo for other float `tobytes()` groupings.)
- **"Nothing in `src/censoring/` computes rank or conditioning"** no longer holds:
  `identification.py`.
- **The rate control did not need porting.** `synthetic.py` hits all five targets exactly;
  the `intensity` / `max_day_fraction` machinery was not carried over.
- **"The 17 assertions are the reusable artefact" was overstated — two were wrong.**
  The minimum-run check assumed hourly exposure can only arise via the §51 trigger; it
  cannot — θ = −MP exposure carries no run condition, and all 1,211 apparent violations were
  trigger-inactive. And "step > logistic > half" encoded the archived generator's
  parameterisation; `synthetic.py`'s `half` is a flat r* = 0.5, so `half > logistic` is
  correct there. The suite transfers, but not unexamined. 17/19 unmerged, **19/19 merged**,
  both cohort sets.
- **`rank(s) == K` is itself too strict**, so the pre-registration list below no longer asks
  for it. A pair with identical `s` but *differing* `depth` is weakly identified, not
  unidentified — separable through the depth contrast — and a rank test on `s` alone would
  fail a design that is in fact identified. The condition is full rank on the feature block
  `[s | depth]`, with both ranks reported. Found by writing the regression tests, not by
  reasoning (`f03f9c4`).

## Identification: the finding that outlives the generator

`s_k` depends on the cohort only through θ_k **on the exposed set**, so cohorts agreeing
there have bit-identical exposure. This is arithmetic, not bad luck.

Rank is **arm-specific** — no single figure covers it:

| Set / arm | rank | capacity exactly collinear |
|---|---|---|
| `synthetic.py` flat MV, 81 stored artifacts | 6 of 8 | 34.6% |
| Real panel, AW low / main / high | 7 of 8 | 29.3% |
| Real panel, AW **stress** | **6 of 8** | **62.9%** |

The `stress` arm is the serious one and no document had recorded it: forcing
`pre2016_in_support_no_s51` (the largest cohort, 33.6%) onto θ = 0 creates a three-cohort
group carrying nearly two-thirds of the fleet. That is not a sensitivity result, it is a
degenerate model.

The θ = 0 pair is structural. The AW = 66 pair was a placeholder artefact and has already
dissolved under real award values.

Identification therefore comes from **θ separation on the exposed set**: the gap between
θ = 0 and θ = −MP, the run-length thresholds that flip a cohort between them, and the spread
of market premiums. The shallow band carries it — 1,461 of 2,059 negative quarter-hours sit
in −5 to 0 €/MWh, 71.3%, the most populated band in every window. (Band open at −5: exactly
8 quarter-hours sit at −5.00, and the half-open reading gives 1,469. State the convention.)

**But the premium channel is weaker than that list implies.** On the real panel
`MP = max(0, AW − MV) = 0` in any month where the market value exceeds the award value, and
the monthly market value runs **57.18 – 115.45 €/MWh** against award values of 74 – 89. So
MP is zero for much of the window — throughout for `out_of_support`, in 89% of it for
`pilot_exempt` — and θ = 0 there with no §51 trigger involved at all. Of the three sources,
the premium spread is the one least available on real data. `synthetic.py`'s flat
`mv_eur_mwh = 45.0` hides this completely, which is why a structural choice validated only
on the benchmark can be degenerate on the data the thesis is about (see the fallback, below).

**Pre-registration to add before the week-6 gate:**
- full rank on the feature block `[s | depth]` over the evaluation window, per arm, with
  `rank(s)` reported alongside — **not** `rank(s) == K`, which fails weakly-identified
  designs that are nonetheless identified
- a **per-pair floor of 10 quarter-hours** on which any two cohorts differ — this is the
  binding test, inheriting the pre-registered 10
- `cond(s) <= 100` as a derived backstop. **Not `cond(w·s)`**: it is nearly blind to
  near-collinearity (543.6 with one differing quarter-hour against 602.2 untouched, and it
  *falls* as duplication worsens). Report it, never gate on it.
- cohorts merged on the realised `(s, depth)` block, legal labels kept as metadata
- a fallback partition that survives the merge — see below

Status: all **81 of 81** stored gate cells pass the old day-count criterion and **fail** the
proposed one. On the real panel all four AW settings fail before merging and pass after.
Criterion (d) is wired into `gate_verdict.py` marked PROPOSED and excluded from the verdict.

## The two-cohort fallback does not survive merging

Spec §7's fail branch says to refit with the two-cohort / single-response structure — spec
§3 I4's macro-cohorts by **price clock**, response tied inside each macro. A macro-tied fit
inverts the capacity-weighted aggregate `A_m = Σ_{k∈m} w_k s_k`, not the per-cohort `s`, and
on a merged design that matrix has **one row**: `post_feb2025_qh`, the only quarter-hour-clock
cohort, is absorbed into a merged cohort whose θ is 0 at every quarter-hour, so no clock is
ever consulted and every survivor inherits the hour macro. The fail branch cannot be executed
as written.

The obvious re-spec — **θ ever 0 vs never 0** — is endorsed by the benchmark (M = 2, cond
**4.0** against the clock partition's 12.0, a balanced 61/39 split, the strongest
weakest-link of any candidate) and is **degenerate on the real panel**, for the MP = 0 reason
above: every cohort reaches θ = 0 there, so "ever 0" partitions nothing.

What survives is the **θ regime** — always 0 / switching / never 0 — the only candidate
identified on both panels, before and after merging: M = 3 at cond 6.2 on the benchmark,
M = 2 at cond 6.7 on the real panel, where the "never 0" group is simply empty. On real data
it also beats the pre-registered clock partition (6.7 against 21.1), and it is identified in
all four AW settings.

**Identified, not strongly identified.** Its weakest pair of macro profiles differs by a mean
of only 0.0137 on the benchmark and 0.0191 on the real panel, against 0.0407 for the clock
partition before merging. The fallback will run; what it recovers will be imprecise, and that
belongs in the write-up. PROPOSED, not pre-registered. `docs/12` §I;
`DEFAULT_FALLBACK_MODE` in `identification.py`, with `"clock"` kept available so the
degeneracy can be reproduced rather than taken on trust.

## Window

E1 and E2 run from **1 Oct 2025** (393 days, 99 event-days). Confirmed empirically:
**15,335 of 15,335** hours before that date have all four quarter-hour prices identical
(mean spread 0.000), against 0.30% after, sharp at the month boundary; and **0 of 982**
negative-price hours before have mixed sign within the hour, against 218 of 626 after.

Before the MTU change there is no quarter-hour day-ahead price, so θ = 0 and θ = −MP cohorts
cannot separate on sub-hourly variation and the two clocks collapse into one. Now
`MTU15_FIRST_DELIVERY_DAY` in `src/censoring/window.py`. E3 is explicitly excluded — only
the hourly regime exists there anyway.

Not yet applied: `synthetic.py:235 load_base` still takes the whole panel, so no E1/E2
result has been produced on the restricted window.

## Open

- **Regenerate the 81 artifacts with merged cohorts.** Merging happens upstream of
  generation, so nothing can be salvaged by re-scoring. In progress at the time of writing
  (`run_reduced_grid --only grid --merge-cohorts`, ~7 min per cell, writing to
  `data/processed/e1_gate_artifacts_merged/` and `results/12_reduced_grid_merged.csv` so the
  unmerged run survives). The before/after gate comparison goes in `docs/12`.
- **Pre-register criterion (d) and the fallback partition, or decide against them.** Both are
  implemented, derived and reported, and both are excluded from the verdict until
  pre-registered.
- **Decide what `stress` means for the verdict.** At 62.9% collinear capacity, merged it
  drops K to 6 and two legal cohorts the thesis wants to discuss separately cease to exist.
- **Restrict E1/E2 to the window and re-run** — `window.py` exists but nothing calls it.
- **Find the "keine automatische Abschaltung" statement in legal commentary, or drop it.**
- The merged cohort that absorbed the quarter-hour clock still carries `clock="hour"` and
  `macro=MACRO_HOUR` as inherited metadata, which is misleading: its θ is 0 throughout, so
  neither field is ever consulted. A third value meaning "no clock applies" would touch
  `Cohort.__post_init__` and `MACRO_QH`/`MACRO_HOUR` across the package. Left alone; it
  changes no number and `theta_regime` reads neither field.

## Closed since the previous revision

- **`gate_verdict.py`'s `KeyError: 'n_qh'` is fixed** (`dbb5c47`). The previous revision
  listed it as open and blocking, and guessed the cause might be a missing artifact field
  that regeneration would supply. It was not: `metrics.paired_abs_bias` returned neither
  `n_qh` nor `n_days` on either return path, while its two siblings in the same module do,
  and `criterion_b` writes both into the results CSV. Regeneration would never have fixed it.
  The grid was complete all along — "81 of 81" — so `--allow-partial` was never needed, and
  the gate has now scored for the first time: **(a) FAIL** (half fails), **(b) FAIL** (both
  gammas), **(c) PASS**, **GATE: FAIL**, in `results/13_gate_verdict.csv`. Read it with the
  regeneration item above attached: those are failures on a rank-6-of-8 design, which is
  exactly the case the fail branch addresses.
