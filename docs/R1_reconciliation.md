# R1 — reconciling the two working copies

**Run 15 November 2026, before Q0.** Phase Q orders R1 first because "results that
cannot be traced to committed code are worth nothing at a defence". Every figure
below was measured from the repository, not quoted from the brief.

Two working copies exist:

| | path | branch | HEAD at start |
|---|---|---|---|
| main checkout | `/Users/gagan/msc-thesis-wind-curtailment` | `mechanism-aware-censoring-gate-and-test2` | `f2b601f`, 10 Nov 18:05 |
| Phase P worktree | `.claude/worktrees/phase-p-postauction-forecasting-68cc63` | `claude/phase-p-postauction-forecasting-68cc63` | `0df6fef` |

---

## 0. Headline

| item | finding | action |
|---|---|---|
| `real_panel.py` untracked | results already cite it | **committed** (`1f08fce`) |
| `docs/P0_preregistration.md` "missing" | not drift — a different branch | explained, §3 |
| `results/00–02_*` modified | produced on the **2024-01-01 panel**, crossing the 15-minute boundary | **restored**, superseded copies preserved |
| `results/21_tb_primary_report_*` modified | the working version is the **correct** one | **committed** (`5aa5313`) |
| `m2.py`, `tb_methods.py` modified | changes a **frozen** pre-registered grid | **left as found** → `docs/Q_STOP_R1.md` |

---

## 1. The drifted result files: which window produced them

**Answer: the full rebuilt panel, 2024-01-01 to 2026-10-28, which crosses
`MTU15_FIRST_DELIVERY_DAY` (2025-10-01).** The arithmetic is exact, not inferred.

Panel (`data/processed/panel_qh.parquet`, 495,360 rows):

| | |
|---|---|
| timestamp range, UTC | **2023-12-31 23:00** to **2026-10-28 22:45** |
| Berlin dates | **2024-01-01** to **2026-10-28** |
| DE quarter-hours | 99,072 |

Recomputed directly from that panel:

| DE | whole panel | from 2025-10-01 |
|---|---|---|
| negative-price quarter-hours | **5,987** | **2,059** |
| negative-price event-days | **283** | **99** |

The modified files report **5,987 on 283**; the committed files report **2,059 on
99**. The two numbers are the same statistic over two different windows, and the
modified files' "total QHs in period (usable, DE)" of **98,976** is 99,072 DE rows
minus the 96 with a missing forecast or output — the same 96 that
`artifacts/P0/p0_planning_recompute.csv` counts.

**Cause.** `src/kill_test.py` applies **no date filter**: it reads the whole panel
(`src/kill_test.py:62-63`). The window is therefore whatever `PERIOD_START_BERLIN`
was when the panel was built, and commit `451aac1` ("Stage 1: panel rebuilt to
2024-01-01") moved it from 2025-10-01 to 2024-01-01. Re-running the kill test after
that rebuild necessarily produces the longer-window figures. File timestamps agree:
`results/00_*` 10 Nov 08:48, `results/01_`/`02_*` 10 Nov 09:20.

**How much of the extended run predates the boundary:**

| | share before 2025-10-01 |
|---|---|
| DE quarter-hours | 61,340 of 99,072 = **61.9%** |
| DE negative-price quarter-hours | 3,928 of 5,987 = **65.6%** |

This is the same base `docs/19` section 1.1b measures at 61.6% for the merged gate,
and the same cause.

### 1.1 What the superseded figures said

Preserved byte-for-byte at
`artifacts/R1/superseded_main_worktree_20261110/`, with the full diff at
`diff_vs_committed.patch` in that folder.

| area | committed (2,059 QH, 99 days) | extended (5,987 QH, 283 days) |
|---|---|---|
| DE | −1,684.4 MW, CI [−2,693.6, −806.5], −9.1% | −1,805.5 MW, CI [−2,231.7, −1,417.7], −10.0% |
| 50Hertz | −832.7, [−1,207.6, −500.3], −14.1% | −818.7, [−989.7, −659.2], −14.4% |
| Amprion | −431.3, [−624.4, −257.2], −13.1% | −339.3, [−438.2, −250.1], −10.9% |
| **TenneT DE** | −325.9, [−838.3, **+137.6**], **not significant** | −575.6, [−799.2, −361.8], **significant** |
| TransnetBW | −94.4, [−132.4, −57.6], −24.9% | −70.2, [−90.1, −51.2], −19.4% |

The point estimates move modestly. **The consequential change is TenneT**, which goes
from the one control area where the kill test found no significant negative-price
bias to a significant one. That statement is repeated as a standing caveat in
`docs/06`, `docs/08` and `docs/09`.

### 1.2 Why they were restored rather than committed

Two independent reasons, and the first is decisive on its own.

1. **`CLAUDE_CODE_PROMPT.md` hard rule 3 forbids it**: *"Do not change the kill-test
   code or results (`src/kill_test.py`, `check_da_vs_id.py`, `redispatch_control.py`,
   `results/00_*`–`04_*`) except to import shared helpers from them."* These files are
   `results/00_*`, `01_*` and `02_*`. The rule has no exception for a better window.
2. **The run mixes two market regimes.** 65.6% of its negative quarter-hours predate
   the 15-minute market time unit, where `src/censoring/window.py` establishes that
   all four quarter-hour prices are identical in 15,335 of 15,335 calendar hours.

**A qualification, so the second reason is not over-claimed.** The kill test uses no
cohorts and no exposure, so the collapse of the two §51 price clocks does not make it
*wrong* before the boundary — that argument is what rules E1 and E2 out of the
pre-MTU15 era, not the kill test. What the extended run is, precisely, is a
**different and broader measurement** than the committed one: a pooled estimate over
two price-formation regimes. That is a legitimate thing to want, and an illegitimate
thing to obtain by overwriting the artifact every other document cites.

**If the student wants a 2024-onwards kill test**, the way to have it is a new,
separately named artifact (`results/05_*`, say) that reports the two regimes split as
well as pooled, leaving `results/00_*`–`04_*` untouched. That needs a written decision
and is not taken here.

### 1.3 Blast radius, had they been committed

Documents quoting the committed kill-test figures, which would all have gone stale:

**Main checkout (8):** `CLAUDE_CODE_PROMPT.md`, `README.md`,
`docs/01_thesis_brief.md`, `docs/01_thesis_brief_v1_forecast-correction.md`,
`docs/04_rq1_killtest_note.md`, `docs/04_rq1_killtest_note_v3.md`,
`docs/06_pivot_mechanism_aware_censoring.md`, `docs/08_test2_preregistration.md`.

**Phase P branch, additionally (4):** `docs/16_e1_generator_design.md`,
`docs/17_e1_first_run_report.md`, `docs/P0_preregistration.md`,
`docs/P_STOP_P0.md`.

Two of those are **pre-registrations** — `docs/08` (Test 2) and
`docs/P0_preregistration.md` — whose sample-size tables are binding and may not be
rewritten after the fact.

---

## 2. `real_panel.py`: committed, tests handed over

`src/censoring/real_panel.py` had been untracked since **2 Nov 13:09** while
`docs/10` section 4 already quotes a result produced through it
(`results/26_td_iii_identification.csv`, T-D(iii), identification in 15 of 33
months). Committed as **`1f08fce`** on `mechanism-aware-censoring-gate-and-test2` —
the branch that produced it, not copied between worktrees.

**It had no tests of any kind.** 23 were written and **run against the main
checkout's copy: all pass.** They pin the German decimal parsing, the ct/kWh →
EUR/MWh conversion, the truth fields raising and naming themselves, exposure and
depth being exactly `1[p < θ]` and `max(0, θ − p)`, window contiguity, onshore as the
default, and the guard that a month with no published market value raises instead of
defaulting θ to 0 and manufacturing exposure.

**The test file could not be placed.** A `PreToolUse` hook blocks this session from
writing into the primary checkout, and this branch does not contain `real_panel.py`,
so the import cannot be collected here either. The file is handed over ready to apply
at **`artifacts/R1/test_real_panel.py.handover.txt`**; it belongs at
`tests/test_real_panel.py` in the main checkout. **This is the one piece of R1 left
open**, and it needs a session running in that checkout.

**Still untracked there, and deliberately not committed** because R1 named only
`real_panel.py`: `src/censoring/run_td.py` (the T-D runner that imports it),
`src/censoring/tb_lambda_widening.py`, `tests/test_report_only_matches_live.py`,
`results/26_td_iii_identification.csv`, `results/27_td_probe.csv`,
`results/40_m2_lambda_boundary.csv`, `results/41_tb_lambda_widening.csv`.
`run_td.py` and `results/26` are the live case: `docs/10` cites a number from a
runner that is still untracked. Recommended for a follow-up commit, not taken here.

---

## 3. `docs/P0_preregistration.md` is not missing — it is on another branch

R1 reads the two copies as having drifted. They have not, in that respect.

`docs/P0_preregistration.md` was committed on **15 November** as `1cd4b30` on
`claude/phase-p-postauction-forecasting-68cc63`. The main checkout is on
`mechanism-aware-censoring-gate-and-test2`, which has never contained it. **Before
today `f2b601f` was an ancestor of the Phase P branch**, so the Phase P branch held
everything the main checkout had committed, plus `identification-fix`, plus Phase P.

**The two R1 commits made today change that.** `1f08fce` and `5aa5313` are on
`mechanism-aware-censoring-gate-and-test2` and **not** on the Phase P branch, so the
branches have now genuinely diverged — by exactly those two commits. Either merge
them into Phase P, or let them arrive when Phase P merges back. Noted so it is not
rediscovered as a mystery.

---

## 4. `results/21_tb_primary_report_20261110.txt`: the working copy was the right one

The one drifted file where the **uncommitted** version was correct.

`docs/21` records that the committed capture of
`run_tb.py --pass primary --report-only` was a false record: a type-coercion defect
printed every cell as `nan` and concluded **FAIL** on a run that had **PASSED**.
`f2b601f` fixed the defect and its message quotes the corrected output, but the
capture file itself was never re-committed, so the repository still carried the false
FAIL.

**Verified, not assumed.** Re-running
`python -m src.censoring.run_tb --pass primary --report-only` today, against the
committed 945-row `results/21_tb_primary.csv`, reproduces the working-tree file
**byte-for-byte** and differs from the committed one. Committed as **`5aa5313`**. The
repository now ends that capture with `T-B VERDICT at n = 50: PASS`.

---

## 5. `m2.py` and `tb_methods.py`: stopped, not reconciled

Left exactly as found. The working tree widens `LAMBDA_GRID` from
`(0.0,) + logspace(-4, 2, 13)` to `(0.0,) + logspace(-6, 4, 21)`, which is a quantity
`docs/09` section 6 **freezes** and which the committed T-B PASS was produced on. The
change cites a `docs/22` that exists nowhere, and the re-run meant to justify it
(`results/41_tb_lambda_widening.csv`) holds **74 of 135 rows**.

Reconciling it either way would make a decision that belongs to the student or the
supervisor. Phase Q hard rule 10 therefore applies and the full case — including the
motivation, which is real: the committed grid was clipped in **104 of 135** fits —
is in **`docs/Q_STOP_R1.md`**. The diff is preserved at
`artifacts/R1/lambda_grid_widening_uncommitted.patch`.

---

## 6. State at the end of R1

**Main checkout**, `mechanism-aware-censoring-gate-and-test2`, now two commits ahead:

```
5aa5313  Commit the corrected T-B report capture ...
1f08fce  Commit real_panel.py, untracked since 2 November ...
f2b601f  Fix --report-only ...
```

Working tree there: `src/censoring/m2.py` and `src/censoring/tb_methods.py` modified
(§5), everything else clean of tracked modifications; the untracked files listed in
§2 remain untracked.

**Phase P worktree**: this note, `docs/Q_STOP_R1.md` and `artifacts/R1/`.

**Open, in priority order:**

1. Apply `artifacts/R1/test_real_panel.py.handover.txt` as `tests/test_real_panel.py`
   in the main checkout (§2).
2. Resolve the λ-grid question per `docs/Q_STOP_R1.md` (§5).
   **Decided** by the student (`docs/Q_STOP_R1.md`) and **run** as a sensitivity, reported
   15 November 2026 in `docs/TB_lambda_sensitivity.md`: on the widened grid T-B FAILS on
   the half-shape gate. The committed PASS is unchanged. 77 of 135 widened selections are
   at the new upper edge, so the sensitivity is itself provisional.
3. Decide whether `run_td.py` and `results/26` are committed, since `docs/10` cites
   that result (§2).
4. Decide whether a 2024-onwards kill test is wanted as a new artifact (§1.2).
5. Merge `1f08fce` and `5aa5313` into the Phase P branch, or let them meet on merge
   back (§3).
6. **The TenneT correlation in `docs/06` traces to the wrong series** (added 15 November
   2026, student's instruction). `docs/06` line 769 gives TenneT's projection-to-output
   correlation as "0.99+". Q0 Amendment 1 traced that figure to
   `results/34_hochrechnung_check.csv`, TenneT 0.9923, which is the *Hochrechnung
   Windenergie* export `docs/06` itself labels the wrong series, 1.57% of the fleet. The
   checker module that produced `results/34` no longer imports.
   **Re-measured with working code** on the series Anchor H is, at positive prices
   (`artifacts/Q0b/q0b_h_agreement.csv`, `corr_H_G`, TenneT, `price >= 0`):

   | series | quarter-hours | correlation |
   |---|---|---|
   | operational | 5,422 | 0.9913 |
   | quality-assured | 35,673 | 0.9914 |

   The re-measured value is also above 0.99, so the number in `docs/06` stands while its
   source does not. **Remaining action: re-cite `docs/06` line 769 to the Q0b artifact.**
   `docs/06` is the spec, so the edit is the student's call and is not made here.
