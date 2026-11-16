# 21 — `--report-only` reported FAIL on a PASS result

Found 10 November 2026, 02:24, immediately after `f900031`.

## 1. Order of events

1. The live T-B re-run on the corrected response curve finished at 00:51 and
   printed `T-B VERDICT at n = 50: PASS`.
2. `results/21_tb_primary.csv` (945 rows) was committed in `50e9947`.
3. A capture of `run_tb.py --pass primary --report-only` was committed empty in
   `ef51aec` (wrong interpreter, no torch), then re-run and committed in
   `f900031`.
4. That capture, reading the **same** CSV, printed every M2-vs-rival cell as
   `nan` with `n_eff = 0` and concluded `T-B VERDICT at n = 50: FAIL`.
5. The committed capture is therefore a false record and is superseded by this
   note and by the corrected capture that follows it.

## 2. The defect

`score_verdict.metric()` reads three fields without type coercion, which is safe
for the in-memory rows a live run passes and wrong for the strings
`csv.DictReader` returns:

- `r["n_event_days_requested"] != n_level` compares `"50"` with `50`, so every
  row is skipped. This alone empties the comparison.
- `float("inf") if r["failed"]` treats the string `"False"` as truthy, so every
  fit would score as a failure.
- `r["int_abs_r"]` is never converted to `float`.

`paired_diffs.metric()`, 30 lines below, coerces all three correctly. That is why
the component attribution block printed correct figures in the same run.

## 3. Which verdict stands

**PASS.** Verified by a clean-room reimplementation of `sign_test`,
`sign_test_threshold`, `exact_two_sided_p` and the section 0.3 rule, written
against the CSV with no repo imports. It reproduces the live run on all 18
shape/rival rows: means to five decimals, win counts, effective n, thresholds,
two-sided p-values, and both tie counts.

The 9 November FAIL is unaffected by this defect — it came from a live run and
its cause was the response-curve atom, recorded in `docs/20`.

## 4. Why 187 tests missed it

`tests/test_tb.py` calls `score_verdict` with hand-built dicts holding
`"n_event_days_requested": 50` as an `int` and `"failed": False` as a `bool`.
Every test exercises the live path. No test has ever run the reporting route that
section 3 of `docs/10` mandates.

This is the second defect in this programme found between the result and the
verdict rather than in the model or the statistics, after `docs/20`. Both were
invisible to a passing suite for the same reason: the suite tested the
computation and never the route by which the computation reaches a decision.

## 5. Binding sequence

This note was committed before the fix, so the false record exists in the history
with its correction attached rather than being rewritten out of it.
