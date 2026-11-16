# 11 — E1 identification audit: `src/censoring/synthetic.py` vs `src/e1_generator.py`

Run 8 Nov 2026 on branch `e1-first-run`, following report 10 §6 item 1. Answers one
question: does the already-committed E1 generator have the thin-direction problem that
report 10 found in the new one? Supersedes nothing. No code outside this branch was changed.

**Answer: no — it has zero thin-direction rows, because it models exposure differently.
But it has a worse problem of its own: 34.6% of fleet capacity sits in exactly-collinear
cohort pairs, so the exposure matrix is rank 6 of 8 and those cohorts' responses are not
identified at all. The pre-registered rule-18 check does not detect this, and reports
"K-cohort stands" at all four AW settings while it holds.**

---

## 1. The thin direction is zero, for a structural reason

Measured on the real panel (`data/processed/panel_qh.parquet`), DE, rate 0.20, gamma 0.5,
logistic, seed 42, 89,376 quarter-hours, `placeholder_cohort_set()`:

| quantity | `src/e1_generator.py` | `src/censoring/synthetic.py` |
|---|---|---|
| QH price ≥ 0 inside a negative hour | 2,218 (opportunity) | 216 (opportunity) |
| **any cohort exposed at a QH with price ≥ 0** | **10** | **0** |
| hourly-clock cohort exposed alone | 10 | 0 |

Zero is not a sampling outcome. In `cohorts.py:371` `theta_and_exposure` sets

```
theta[k,t] = 0                  if the trigger is active, or the cohort is out of support
           = -max(0, AW_k - MV) otherwise
s[k,t]     = 1[ price_qh[t] < theta[k,t] ]
```

`theta ≤ 0` always, and exposure is evaluated on the **quarter-hour** price on *both*
clocks. So `price_qh ≥ 0` implies `s[k,t] = 0` for every cohort, on every clock, for any
price series. Confirmed empirically: `max(theta) = 0.000` across all cohorts and
quarter-hours. The hourly clock only decides whether `theta` is `0` or `−MP`; it never
decides which price the plant looks at.

### The two generators disagree on a legal question, not a tuning parameter

This is the substantive finding, and it is more fundamental than either generator's sample
sizes:

* **`e1_generator.py`**: once a run of negative hours reaches the cohort's minimum length,
  the whole hour is censored *including its non-negative quarter-hours* (`retro_run=True`,
  `src/e1_generator.py:92`). Its validator check 6 **asserts that such rows must exist**
  ("hourly-clock censoring at a positive quarter-hour price exists"), and the design note
  calls this "part of the identifying variation behind I4" and "not an edge case to be
  tidied away".
* **`synthetic.py` + `cohorts.py`**: §51 zeroes the *support payment* for the hour, but the
  plant still decides quarter-hour by quarter-hour whether that quarter-hour's price is
  below its threshold (`cohorts.py:371` docstring, verbatim: "A plant whose support has
  been zeroed for the hour still decides quarter-hour by quarter-hour whether this
  quarter-hour's price is below its threshold").

**Both cannot be right, and the difference is not cosmetic**: it is the whole of
`e1_generator.py`'s I4 identifying variation. One implementation asserts those rows must
exist; the other makes them impossible. This is a question about what §51 EEG 2023 actually
requires, settled by `docs/05_eeg_rule_table.md` and the legal texts, not by either
generator. **I have not adjudicated it and it should not be decided by whichever file is
picked for the gate.** Note that the economic reading in `cohorts.py` is the more defensible
one on its face — a plant with no support left to lose has no reason to pay to generate into
a positive price — but that is an argument, not a reading of the statute.

---

## 2. `synthetic.py`'s own identification failure: exact collinearity

### Phase 2 placeholder set — rank 4 of 5

| # | cohort | clock | §51 | in support | AW | θ min | exposed QH | share |
|---|---|---|---|---|---|---|---|---|
| 0 | `pre2016_out_of_support` | hour | False | False | — | 0.0 | 17,901 | 0.10 |
| 1 | `wind2016_2020_6h` | hour | True | True | 62 | −17.0 | 12,194 | 0.30 |
| 2 | `wind2021_2022_4h` | hour | True | True | 59 | −14.0 | 15,680 | 0.18 |
| 3 | `wind2023_feb2025_staircase` | hour | True | True | 71 | −26.0 | 17,400 | 0.27 |
| 4 | `post_feb2025_qh` | **quarter-hour** | True | True | 74 | −29.0 | 17,901 | 0.15 |

`s[0]` and `s[4]` are **bit-identical**, and this holds in **12 of 12** cells tested
(rates 0.05/0.20/0.40 × gamma 0/1 × seeds 42/43). It is structural, not sampling:

* cohort 0 is out of support → `theta = 0` always → exposed iff `price_qh < 0`;
* cohort 4 is the quarter-hour-clock §51 cohort → its trigger is active **exactly** where
  `price_qh < 0`, so `theta = 0` exactly there and `−29` elsewhere → exposed iff
  `price_qh < 0`.

Two different cohorts, identical exposure vectors, for any price series whatsoever.
**25% of fleet capacity.**

```
singular values = [276.44  57.99  31.65  17.16   0.00]
rank = 4 of 5       cond = 4.2e14
```

### Phase 3 MaStR set — rank 6 of 8, 34.6% of capacity

`mastr_cohort_set("DE")`, same cell:

| # | cohort | AW | θ min | exposed QH | share |
|---|---|---|---|---|---|
| 0 | `out_of_support` | — | 0.0 | 17,901 | 0.167 |
| 1 | `pilot_exempt` | 66 | −21.0 | 2,742 | 0.004 |
| 2 | `post_feb2025_qh` | 74 | −29.0 | 17,901 | 0.126 |
| 3 | `pre2016_in_support_no_s51` | 62 | −17.0 | 3,208 | 0.336 |
| 4 | `size_exempt` | 66 | −21.0 | 2,742 | 0.049 |
| 5 | `wind2016_2020_6h` | 62 | −17.0 | 12,194 | 0.155 |
| 6 | `wind2021_2022_4h` | 59 | −14.0 | 15,680 | 0.060 |
| 7 | `wind2023_feb2025_staircase` | 71 | −26.0 | 17,400 | 0.103 |

Two exactly-duplicated pairs:

| pair | cause | combined capacity |
|---|---|---|
| `out_of_support` ≡ `post_feb2025_qh` | both reduce to "exposed iff `price_qh < 0`" | **29.3%** |
| `pilot_exempt` ≡ `size_exempt` | both §51-exempt, in support, **same AW = 66** → θ = −21 | **5.4%** |

**34.6% of fleet capacity in exactly-collinear pairs.**

```
singular values = [279.65  83.56  54.68  31.57  17.37  17.04   0.00   0.00]
rank = 6 of 8
distinct exposure patterns = 10 of 256 possible
```

The second pair is an artefact of two placeholder cohorts sharing AW = 66 and may dissolve
under real tender values. **The first is structural and will not.**

### What is *not* wrong

No cohort is ever exposed alone, in either set. That sounds alarming but is **not** itself
an identification failure: the thresholds are nested (θ = 0 > −14 > −17 > −26 > −29), so
the weakest-threshold cohort fires whenever anyone does. A nested design can still be full
rank. Dropping one row of each duplicated pair confirms the nesting is fine:

```
MaStR, 6 unique rows:  rank = 6 of 6     cond = 16.6
singular values = [245.62  69.62  50.76  30.26  15.35  14.81]
```

**Exactly the duplicates cause the deficiency.** Merge them and the design is full rank and
well conditioned. The fix is a cohort-definition change, not a generator change.

### When it bites

With `r_cohort_offsets=None` (the default) one `r*` is shared across cohorts, so only one
curve needs identifying and rank is irrelevant. The rank deficiency bites precisely in the
arm that sets `r_cohort_offsets` — **the arm whose purpose is to test whether cohort
structure is worth having** (`synthetic.py:115` docstring: "With offsets the cohorts
genuinely differ and cohort structure becomes testable"). Verified with
`r_cohort_offsets=(0.0, −0.1, 0.05, 0.1, −0.05)`: rank stays 4 of 5, `r*_0` and `r*_4`
differ by 0.05 mean absolute on exposed quarter-hours, but since `s[0] ≡ s[4]` only the
capacity-weighted sum `w_0·r_0 + w_4·r_4` enters `c_true`. The split is unrecoverable from
any amount of data.

---

## 3. The pre-registered check misses this in both implementations

This is the part that should change before the gate.

`cohorts.py:447 exposure_differs_by_day` implements the rule-18 / I4 criterion: count
event-days on which at least one quarter-hour has two cohorts with different exposure; under
10 days, collapse to two cohorts. On the cell above it returns **544 days**. The committed
real-data run agrees (`results/38_rule18_settings.csv`):

| setting | qh_differing | event_days | threshold | verdict |
|---|---|---|---|---|
| low | 292 | 19 | 10 | K-cohort stands |
| main | 803 | 55 | 10 | K-cohort stands |
| high | 1220 | 71 | 10 | K-cohort stands |
| stress | 362 | 29 | 10 | K-cohort stands |

**All four settings say "K-cohort stands" while 34.6% of capacity is exactly unidentified.**
The criterion asks whether cohorts differ *somewhere*; it cannot see rank, because a single
pair differing anywhere satisfies it regardless of how many other pairs are identical.

`grep -rn "rank\|collinear" src/censoring/` returns only the verb "rank methods" in
`metrics.py:69` and `run_synthetic.py:132`. **Nothing in the repo computes the rank or
conditioning of the exposure matrix.**

This is the same blind spot report 10 §4.1 found in `e1_generator.py`, where
`cohort_exposure_differs_days = 403` passes at 40× margin while the hourly cohort is
identified off 10 rows. **Two independent generators, the same pre-registered criterion,
the same false pass.** That makes it a defect in the criterion, not in either generator.

### Recommended replacement, for pre-registration

Supplement — do not replace — the day-count threshold with two conditions on the exposure
matrix `s` (K × T), both cheap and both computable before any model is fitted:

1. **`rank(s) == K`**, reported with the singular values. On failure, name the collinear
   groups and merge them, reducing K and re-deriving capacity shares, before any fit.
2. **A per-cohort floor on exposure that is not a copy of another cohort's** — for each
   cohort, the number of quarter-hours where its exposure differs from every other
   cohort's. This is the quantity report 10 measured as 10 for `e1_generator.py`'s hourly
   cohort and 0 for every `synthetic.py` cohort. A day-count threshold cannot substitute
   for it.

Both are spec changes and need pre-registration before the week-6 gate on 31 Dec 2026.

---

## 4. What this means for the choice in report 10 §6 item 1

Neither generator is ready, and they fail differently:

| | `src/e1_generator.py` | `src/censoring/synthetic.py` |
|---|---|---|
| maturity | new, untracked until this branch | committed, with metrics, baselines, `gate_verdict`, 3 grid arms |
| cohorts | 2 (fallback structure) | 5 placeholder / 8 MaStR, from the real rule table |
| exposure model | hourly mean + `retro_run`; positive QH **can** be censored | always the QH price; positive QH **cannot** be censored |
| validator | 17 assertions, 17/17 on real data | no equivalent standalone suite found |
| exposure matrix | rank 2 of 2 | **rank 4 of 5 / 6 of 8** |
| scarce direction | hourly-only: **10 QH** (2 on the config window) | hourly-only: **0 QH**, by construction |
| identification gap | hourly cohort, 55% of capacity | collinear pairs, **34.6%** of capacity |

On balance I would **keep `synthetic.py` as the gate's generator** — it is committed, it
carries the real rule table, the metrics and baselines are already written against it, and
its collinearity has a clean fix (merge the duplicated pairs: rank 6 of 6, cond 16.6) that
costs two cohorts rather than a redesign. `e1_generator.py`'s gap has no comparable fix:
its identifying variation would have to be manufactured by changing the block geometry,
which changes the benchmark rather than repairing it.

**But that recommendation is conditional on the §1 legal question**, because if the
`retro_run` reading of §51 is correct then `synthetic.py`'s exposure model is wrong on a
point of law and its zero thin-direction count is a modelling error rather than a design
choice. Settle §1 first; it determines which file is even a candidate.

### Order of work

1. Settle whether §51 censors a positive quarter-hour inside a qualifying negative hour
   (§1). Everything else depends on it.
2. Merge the collinear cohort pairs in `placeholder_cohort_set` and `mastr_cohort_set`, or
   document why 34.6% of capacity may share a response (§2).
3. Pre-register the rank and per-cohort-uniqueness conditions (§3).
4. Only then decide which generator scores the gate.

---

## Reproducing

```
python src/e1_cmp_synthetic.py   # §1 thin direction, §2 placeholder set
python src/e1_cmp_rank.py        # §2 rank across the grid, r_cohort_offsets arm
python src/e1_cmp_mastr.py       # §2 MaStR set, duplicate pairs, merged rank
```

Requires `data/processed/panel_qh.parquet` reachable at the repo-relative path
(`synthetic.py:70 PANEL_PATH`); in a worktree, symlink `data/processed`. Seed 42, DE,
no shuffling, `data/raw/` untouched.
