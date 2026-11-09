# 15 — T-B: why it stopped, and whether it can be resumed

Diagnosis run 9 Nov 2026. **Read-only: nothing was restarted, no grid was run, no
pre-registered quantity was touched.** The backup at
`results/21_tb_primary.PARTIAL_82cells_2026-11-02.csv.bak` was not opened.

State: `results/21_tb_primary.csv` holds **574 of 945 rows = 82 of 135 cells**. Rate 0.10
complete (45 cells), rate 0.20 at 37 of 45, rate 0.40 never started.

---

## 1. Why it stopped — cannot be determined, and the reason is recoverable only in part

### What the run was

Launched **1 Nov 2026 13:35:36** from Claude Code session `ec908bf9`, as:

```
rm -f results/21_tb_primary_probe2.csv results/21_tb_primary.csv \
  && nohup .venv/bin/python -m src.censoring.run_tb --pass primary \
       > $SP/tb_primary.log 2>&1 &
```

Note the `rm -f` — the workflow deleted the CSV before each relaunch, which is the
correct habit given §3's finding that the writer truncates.

### The one artifact that would have answered this is gone

`$SP` was that session's scratchpad,
`/private/tmp/claude-501/-Users-gagan-msc-thesis-wind-curtailment/ec908bf9-…/scratchpad/`.
**That directory is now empty** (recreated 8 Nov 18:07, 0 bytes). `/private/tmp` has been
cleared, so `tb_primary.log` — the stdout and stderr of the run, including whatever it
printed as it died — no longer exists. Nothing else captured it.

### What the surviving evidence says

| check | result |
|---|---|
| `~/.zsh_history` | readable, **no `run_tb` anywhere** — consistent with a Claude-launched run, not a typed one |
| `~/Library/Logs/DiagnosticReports` | **no Python crash reports at all**, any date. No segfault, no abort, no jetsam report |
| Claude transcripts, 2 Nov | **zero events in this project on 2 November** — no session stopped it |
| Claude transcripts, any date | no `Traceback`, `MemoryError` or `KeyboardInterrupt` tied to the 1 Nov launch. One `Killed` marker exists at **1 Nov 13:43:54**, which is an *earlier* probe, 8 minutes after launch, not this run |
| `pmset -g log`, 2 Nov 12:00–16:00 | routine maintenance wakes only; nothing conclusive in the window |
| compute vs wall clock | `seconds` sums to **3.06 h** of compute, but the span from launch (1 Nov 13:35) to last write (2 Nov ~13:31) is **~24 h** — so the machine was asleep for the great majority of it |

### Verdict

**The cause cannot be established.** The evidence is consistent with the process being
terminated by its environment — not surviving a sleep/wake cycle, a shutdown, or memory
pressure — and is inconsistent with a code fault: there is no traceback in any transcript,
no crash report of any kind, and the run stopped cleanly between cells (§2). But that is an
argument from absence, and the log that would have settled it was in cleared `/private/tmp`.

Stating it plainly: **restarting is not demonstrably safe from a "no bug" finding, because
no evidence of a bug would have survived either.** What makes a restart reasonable is §2 and
§3 — the stop was on a cell boundary and the cells are independent — not a positive
diagnosis.

### What I would want, and why most of it is already unobtainable

* `$SP/tb_primary.log` — gone with `/private/tmp`.
* The macOS unified log for 2 Nov (`log show --predicate 'process == "python3.13"'`) — its
  retention is days, not a week, so this is also gone.
* A jetsam / low-memory report for 2 Nov — none present.
* **Actionable instead:** relaunch under `caffeinate -i` and tee the log to a path *inside
  the repo or a persistent directory*, never a session scratchpad. That one change makes the
  next failure diagnosable.

### A correction to the brief's reasoning

The brief argues "574 ÷ 7 = 82 exactly, so no partially written cell … unless the writer
flushes per row". **It does flush per row.** `Writer.write` ends with `self.fh.flush()` on
every row (`run_reduced_grid.py:104`). So a mid-cell death would have left a non-multiple of
7, and landing on an exact multiple by chance has probability ~1/7 — the divisibility
argument is weak.

The conclusion survives anyway, by a sounder route: the cells in the file are in **exactly**
the canonical order for all 82, the last is cell 82, and cell 83 is absent entirely (§2). The
stop was on a cell boundary.

---

## 2. Which cell was next

Canonical order from `run_tb.py:65-68, 357-358`:

```
RATES  = (0.10, 0.20, 0.40)        GAMMAS = (0.0, 0.5, 1.0)
SHAPES = ("step", "logistic", "half")   SEEDS = (45, 46, 47, 48, 49)
cells  = [(r,g,sh,sd) for r in RATES for g in GAMMAS for sh in SHAPES for sd in SEEDS]
```

3 × 3 × 3 × 5 = **135 cells**, as expected.

| | |
|---|---|
| cell 82 (1-indexed) | `(0.20, 1.0, "logistic", 46)` |
| **cell 83 — never ran** | **`(0.20, 1.0, "logistic", 47)`** |

Verified against the file: the 82 distinct cells present are **identical, in order**, to
`cells[:82]`, and the last row written is cell 82. So the run stopped between 82 and 83.

### It was not reproduced, deliberately

The brief's own header says read-only, no CPU. Three further reasons:

1. The E1 merged grid is running on this machine and holding ~3 cores; adding T-B would slow
   both and distort any timing taken from it.
2. **There is no way to run one cell from the CLI.** `run_tb.py` has only `--pass`,
   `--limit` and `--report-only` — no `--out`, `--resume` or `--cells`. `--limit 83` runs
   cells 1–83, about 2.8 h of compute, not one cell.
3. **A bare `python -m src.censoring.run_tb --pass primary` would truncate the 574-row
   file** at its first write (§3). The backup makes that recoverable, but it should not
   happen by accident.

The safe way to run exactly cell 83, when someone wants to — `run()` already takes a `cells=`
argument and an output name, so no change to any pre-registered quantity is involved:

```python
from src.censoring.run_tb import run, N_PRIMARY
run((N_PRIMARY,), "21_tb_cell83_probe.csv",
    cells=[(0.20, 1.0, "logistic", 47)])
```

Note `--limit N` already redirects to `21_tb_primary_probeN.csv`, so the existing probe path
is non-destructive; it is only the unflagged run that truncates.

---

## 3. Resume or restart

### The writer truncates, and "append-as-you-go" is a misnomer

`run_reduced_grid.Writer` opens lazily on the first row with
`open(self.path, "w", newline="", encoding="utf-8")` and flushes after every row. So the
docstring's "Append-as-you-go CSV" means **flush**-as-you-go: a rerun starts a new file and
the 574 rows are lost. Hence the `rm -f` in the 1 Nov launch, and hence the backup.

### Are the cells independent?

Checked, and the answer appears to be yes, but note the limits of the check — this was a
targeted review, not a full read of `run_tb.py`:

* **No module-level mutable state.** No module-level dict/list accumulators, no
  `functools.lru_cache`, no `global`, no `_CACHE` in `run_tb.py`.
* **No global RNG seeding.** No `np.random.seed(...)`. The only generator is
  `np.random.default_rng(seed)` inside `nested_day_subsets` (`run_tb.py:155`), a fresh local
  generator, so it does not depend on how many cells ran before it.
* **The day subsample is pinned independently of the cell.** `SUBSAMPLE_SEED = 42`
  (`run_tb.py:72`) "fixes WHICH days, independently of the cell seed", so each cell draws the
  same day sets regardless of position in the run.
* **Each cell is fully parameterised** by `(rate, gamma, shape, seed)` into
  `SyntheticConfig(..., seed=seed)` at `run_tb.py:367`.

So a cell's result should be bit-identical whether it is computed 1st or 83rd, and **a resume
that skips the 82 completed cells is equivalent to an uninterrupted run.**

### Proposed resume patch — plumbing only

Not a pre-registered quantity: it changes no λ grid, no bins grid, no seed, no threshold, no
criterion, and no cell definition. Two parts:

1. **`Writer(..., append=False)`** — when `append=True` and the file exists, open `"a"` and
   skip `writeheader()`, after asserting the existing header matches the fieldnames exactly
   (mismatch must raise, not silently realign — the same failure mode the `extrasaction`
   change of 1 Nov was introduced to stop).
2. **`--resume`** in `run_tb.main()` — read the existing `results/21_tb_primary.csv`, build
   the set of `(rate, gamma, shape, seed)` already present, filter them out of `cells`
   preserving canonical order, and pass `append=True`. Print how many cells were skipped and
   the first cell to be computed, so the resume is auditable.

Guard worth adding at the same time: refuse to resume if any cell in the file has fewer than
its full 7 method rows, since that would mean a genuinely partial cell. On the current file
that check passes — all 82 cells have 7 rows.

**Before any of this runs, verify the backup matches:** the file was last written
2 Nov and the brief records 13:31 where the filesystem mtime reads **14:31**. One hour, no
DST change in that window (CET since 25 Oct), so it is unexplained. Immaterial to the
diagnosis, but it means one of the two records is imprecise, and a `diff` against the `.bak`
before resuming costs nothing.

---

## 4. Time budget for the remaining 53 cells

Per-cell wall seconds = sum of that cell's 7 method rows.

| rate | cells done | median | mean | max | total |
|---|---|---|---|---|---|
| 0.10 | 45 | 99.9 s | 122.9 s | 376.8 s | 1.54 h |
| 0.20 | 37 | 149.2 s | 148.1 s | 286.3 s | 1.52 h |
| 0.40 | 0 | — | — | — | — |

Mean per-cell cost rises **1.21×** from rate 0.10 to 0.20. Remaining: **8 cells at rate 0.20
plus all 45 at rate 0.40 = 53**.

| assumption for rate 0.40 per-cell | compute |
|---|---|
| flat, same as 0.20 (148 s) | **2.2 h** |
| one more 1.21× step (179 s) | **2.6 h** |
| ratio applied twice (215 s) | **3.0 h** |

**Estimate: 2.2–3.0 h of compute**, most likely near the upper end, since rate 0.40 has the
most censored quarter-hours and the per-row distribution is heavily right-skewed (median
0.7 s against a mean of 19.2 s, so a few rows dominate).

**Wall clock is the number that actually matters, and it is not this.** The original run took
**~24 h of wall clock for 3.06 h of compute** because the machine slept. Unless the next run
is held awake, expect the same ratio. Two practical consequences:

* run it under `caffeinate -i` (or with the display asleep but the system held awake);
* do not start it while the E1 merged grid is still running — they will contend for cores on
  a MacBook Air, and the E1 grid has ~3 h left as of this diagnosis.

---

## Nothing was changed

No file in the repository was modified by this diagnosis. No grid was run. No
pre-registered quantity — λ grid, bins grid, seed, threshold, criterion — was touched. The
resume patch in §3 is a proposal, not an edit.
