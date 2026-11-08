# 10 — E1 first run against the real panel

Run 8 Nov 2026 on branch `e1-first-run`. Implements the task "run E1 against the real
panel and report". Supersedes nothing. The generator's logic was **not** changed; the only
code change is a `--cols` / `--area` argument so the real column names can be reached
without renaming stored data or editing the generator's defaults.

**Headline: the generator is correct on real data — 17/17 assertions pass for DE, 50Hertz
and Amprion, and all 225 grid cells hit their rate target. One thing is genuinely broken
for the gate: the hourly-clock cohort's response is identified off 10 quarter-hours at the
main DE cell (7 for 50Hertz, 14 for Amprion, 2 on the narrower study window), and off
1–11 in every one of the 225 DE grid cells. It never grows with the censoring rate. That
is not a thin cell, it is the whole arm.**

---

## 0. Three discrepancies between the task description and the repo

Reported first because they affect how the rest of this document should be read.

1. **The files were not where the task said.** The task places them at
   `src/e1_generator.py` and `src/e1_validate.py`. They are not there and never have been
   in git history. They were found untracked at the repo root in
   `E1_generator/e1_generator.py` and `E1_generator/e1_validate.py` (28K / 12K, mtime
   8 Nov 2026). This branch copies them to `src/`, which is where the task and the design
   note say they belong.

2. **`docs/09_e1_generator_design.md` did not exist in the repo** when this report was
   written; the design note was supplied only as pasted text. Its decisions are quoted
   below where they were tested, and two of its statements turn out to be wrong on real
   data (§7). It has since been committed, in a revised form that marks its superseded
   claims, on branch `identification-fix`.

3. **There is already a committed E1 generator for the same spec section.**
   `src/censoring/synthetic.py` (committed, 24.9K, polars) is a semi-synthetic censoring
   generator for spec 06 §7 — the same experiment — with `SyntheticConfig`, per-cohort
   `true_response`, `_inject_prices`, and `load_base(area, safe_price_floor)`. It is
   supported by `src/censoring/{cohorts,metrics,baselines,gate_verdict,run_reduced_grid}.py`
   and E1 grid arms are already committed (`results/12_reduced_grid.csv`,
   `results/12_ladder.csv`, `results/12_hetero_r.csv`, `results/12_proxy_quality.csv`,
   commit `fec1390` "Add the three completed E1 grid arms from the 31 Oct run").

   So `e1_generator.py` is a **second, independent implementation** of E1, in pandas rather
   than polars, with its own cohort and response code. The pasted design note's closing
   line — "Next build: the metrics module ... and baselines B1–B4" — is already false of
   this repo: `src/censoring/metrics.py` and `src/censoring/baselines.py` exist and are
   committed. **Which of the two implementations the week-6 gate is scored with is a
   decision this report cannot make.** Everything below concerns the new one only.

---

## 1. Panel facts

The processed 15-minute panel is written by **`src/build_panel.py:229-230`**, not by
`src/ingest_smard.py` (which only fetches the raw SMARD JSON into `data/raw/`).

| | |
|---|---|
| full path | `/Users/gagan/msc-thesis-wind-curtailment/data/processed/panel_qh.parquet` |
| row count | 495,360 |
| file size | 16,755,193 bytes (16.8 MB), 5 row groups |
| areas | DE, 50Hertz, Amprion, TenneT, TransnetBW — 99,072 rows each, exactly |
| timestamp range | 2023-12-31 23:00:00 → 2026-10-28 22:45:00 UTC |
| Berlin dates | 2024-01-01 → 2026-10-28 = **1032 days** |
| spacing | 15 min exactly (single unique diff within area) |

### Columns and dtypes

| column | dtype | nulls |
|---|---|---|
| `ts_utc` | int64 (epoch ms) | 0 |
| `area` | str | 0 |
| `berlin_date` | str | 0 |
| `price_eur_mwh` | float64 | 0 |
| `da_onshore_mw` | float64 | 384 |
| `da_offshore_mw` | float64 | 0 |
| `id_onshore_mw` | float64 | 480 |
| `id_offshore_mw` | float64 | 96 |
| `act_onshore_mw` | float64 | 8 |
| `act_offshore_mw` | float64 | 2 |
| `da_wind_mw` | float64 | 384 |
| `id_wind_mw` | float64 | 480 |
| `act_wind_mw` | float64 | 8 |
| `e_mw` | float64 | 392 |
| `e_id_mw` | float64 | 488 |
| `ts_utc_dt` | datetime64[us] | 0 |

### Timezone: NOT tz-aware — flagged, but harmless here

`ts_utc_dt` is `datetime64[us]` with **`tz=None`**. It is *not* timezone-aware. The values
are genuine UTC: `pd.to_datetime(ts_utc, unit="ms") == ts_utc_dt` is `True` for all
495,360 rows, and `ts_utc` is unambiguous epoch milliseconds.

This does not corrupt the E1 run. `_prepare_base` calls
`pd.to_datetime(df[cols.timestamp], utc=True)` (`src/e1_generator.py:265`), which localises
a naive column to UTC rather than shifting it, so the Berlin-local day boundaries and the
hourly clock are correct. But the panel does not satisfy the repo convention "UTC
timestamps" in the stronger tz-aware sense, and any future consumer that assumes
`.dt.tz_convert` works directly will fail. Worth fixing in `build_panel.py`, not here.

### MW sanity check — PASSES

`MWH_PER_QH_TO_MW = 4.0` (`src/smard_config.py:62`) is applied at
`src/build_panel.py:124`. Empirically, for DE `act_wind_mw`:

| statistic | value |
|---|---|
| max | 53,586 MW (53.6 GW) |
| p99 | 45,709 MW |
| mean | 15,503 MW |
| `da_wind_mw` max | 52,901 MW |

Peak is 53.6 GW, not ~13 GW. The columns are **MW, not MWh per quarter-hour**. Nothing
downstream is off by a factor of four.

### E1 base: price > 5 EUR/MWh

The day-ahead price is identical across all five areas (one DE/LU bidding zone), so the
clean-row count is identical too; only the wind columns differ by area.

| area | rows total | price > 5 | and wind non-null | % clean | clean days | days with ≥ 88 clean QH |
|---|---|---|---|---|---|---|
| DE | 99,072 | 89,480 | 89,399 | 90.3% | 1031 | **698** |
| 50Hertz | 99,072 | 89,480 | 89,473 | 90.3% | 1031 | **698** |
| Amprion | 99,072 | 89,480 | 89,384 | 90.3% | 1031 | **698** |
| TenneT | 99,072 | 89,480 | 89,480 | 90.3% | 1031 | 698 |
| TransnetBW | 99,072 | 89,480 | 89,302 | 90.3% | 1031 | 698 |

Note the last column. The generator's `min_qh_per_day = 88` default discards **333 of the
1031 clean days (32%)** — days where negative-price or missing quarter-hours leave fewer
than 88 clean ones. The generator therefore works on 698 days / 66,761 DE rows, not 1031
days / 89,399 rows. This is correct behaviour (a run length is only meaningful on a day
that is nearly complete) but it is a larger cut than the design note implies.

### The study-period discrepancy — needs a decision

The task gives a reference figure of "99 event-days in 391 days (about 25%)". That figure
is **not** the panel on disk. It is the panel restricted to the configured study period:

| window | event-days | negative QH | within-event-day negative share |
|---|---|---|---|
| full panel on disk (2024-01-01 → 2026-10-28, 1032 days) | 283 / 1032 = **27.4%** | 6.04% | 22.0% |
| config window (`berlin_date >= 2025-10-01`, 393 days) | 99 / 393 = **25.2%** | 5.46% | 21.7% |

`src/smard_config.py:23-24` declares `PERIOD_START_BERLIN = 2025-10-01` and
`PERIOD_END_BERLIN = 2026-10-28 23:45`. The stored panel has been **extended 21 months
further back** than that constant, to 2024-01-01, and the constant was not updated. The
task's "99 in 391" is the config window to within rounding.

Because it was not clear which window the gate uses, **everything below was run twice**:
once on the full panel on disk (primary — it is what the file contains and what the task
literally asked for) and once on the config window (secondary). Conclusions are identical
in every respect except that the thin direction of §4.2 gets *worse* on the narrower window.

---

## 2. The `PanelSpec` used

Three of the five fields needed overriding; `area` and `price` already matched.

```python
PanelSpec(
    timestamp  = 'ts_utc_dt',       # default was 'timestamp_utc'
    area       = 'area',            # default, unchanged
    actual_mw  = 'act_wind_mw',     # default was 'wind_actual_mw'
    forecast_mw= 'da_wind_mw',      # default was 'wind_da_forecast_mw'
    price      = 'price_eur_mwh',   # default, unchanged
)
```

Reached from the command line without touching the stored data or the defaults:

```
--cols 'timestamp=ts_utc_dt,actual_mw=act_wind_mw,forecast_mw=da_wind_mw'
```

`da_wind_mw` (day-ahead) is used for the forecast, not `id_wind_mw` (intraday), matching
the spec's day-ahead forecast F.

### Code changes made (no logic, no defaults)

* `src/e1_generator.py` — added `parse_panel_spec()` (a `field=column` parser) and `--cols`
  / `--area` CLI arguments; threaded `cols` into the `--grid` path and the single-cell path.
* `src/e1_validate.py` — added `--cols` / `--area`; `run_checks(panel, cols)` now threads
  the spec into all six internal `generate()` calls, which previously used defaults.
* `src/e1_run_grid.py` — new: the grid driver used for §5, so the run is reproducible.

No default value, threshold, cohort, response or block-geometry parameter was altered.
Verified by re-running the stand-in selftest: **17/17 pass, and the design note's
"7 rows" thin-direction figure reproduces exactly**, so the plumbing is inert.

---

## 3. Validator on real data — 17/17, all three areas

```
python src/e1_validate.py \
  --panel data/processed/panel_qh.parquet \
  --cols 'timestamp=ts_utc_dt,actual_mw=act_wind_mw,forecast_mw=da_wind_mw' \
  --area DE
```

### DE (verbatim)

```
panel rows = 99,072   cols = PanelSpec(timestamp='ts_utc_dt', area='area', actual_mw='act_wind_mw', forecast_mw='da_wind_mw', price='price_eur_mwh')

Diagnostics for the main cell (rate 0.20, gamma 0.5, logistic, seed 0):
  target_rate                      0.2
  realised_rate                    0.2008
  rate_definition                  qh_share
  rate_target_met                  True
  intensity                        1.4619
  n_days_available                 698
  n_rows                           66761
  n_censored_rows                  13406
  n_negative_price_rows            13397
  n_event_days                     419
  mean_c_on_censored               0.3017
  energy_censored_share            0.0742
  gamma                            0.5
  response_shape                   logistic
  seed                             0
  cohort_exposure_differs_days     404
  confounding_corr_F_vs_c          0.1226

==============================================================================
[PASS] G = A x (1 - c) holds within the noise band                     p99.9 relative deviation = 0.0328
[PASS] c_true in [0, 1]                                                min=0.0000 max=0.9000
[PASS] c_true equals the cohort sum                                    max abs diff = 0.00e+00
[PASS] I1 -- c = 0 wherever no cohort is exposed                       53,355 unexposed rows
[PASS] no censoring when both price clocks are non-negative            53,355 rows clean on both clocks
[PASS] hourly-clock censoring at a positive quarter-hour price exists  9 rows -- the identifying variation for I4
[PASS] G does not exceed A beyond the noise term                       max relative excess = 0.0408
[PASS] I3 -- r* non-decreasing in depth                                qh_clock: monotone; hourly_clock_2h: monotone
[PASS] hourly-clock exposure respects the minimum run length           hourly_clock_2h: 0 runs shorter than 2.0 h
[PASS] I4 -- cohort exposure differs on >= 10 event-days               404 days with differing exposure (2,218 QHs)
[PASS] ground-truth columns present                                    A_true_mw, c_true, r_star_qh_clock, r_star_hourly_clock_2h
[PASS] A and G actually differ on censored rows                        mean |A - G| on censored = 5428.6 MW
[PASS] same seed reproduces the dataset exactly                        
[PASS] different seed gives different data                             
[PASS] corr(F, c) increases with gamma                                 gamma 0/0.5/1 -> -0.018 / +0.123 / +0.241
[PASS] step > logistic > half in mean censoring depth                  step=0.818 logistic=0.323 half=0.179
[PASS] all five censoring rates reached within tolerance               0.05->0.051 0.10->0.100 0.20->0.199 0.30->0.301 0.40->0.399
==============================================================================
17/17 checks passed
```

### 50Hertz and Amprion

Both **17/17**. The checks are identical; only the quantitative details differ:

| check detail | DE | 50Hertz | Amprion |
|---|---|---|---|
| hourly-clock censoring at positive QH price | 9 rows | 12 rows | 11 rows |
| I4 differing days (QHs) | 404 (2,218) | 403 (2,098) | 398 (2,154) |
| mean \|A − G\| on censored | 5,428.6 MW | 1,722.4 MW | 1,053.6 MW |
| corr(F, c) at gamma 0 / 0.5 / 1 | −0.018 / +0.123 / +0.241 | −0.019 / +0.137 / +0.265 | −0.011 / +0.169 / +0.218 |
| unexposed rows | 53,355 | 53,514 | 53,352 |

**No FAILs anywhere, so there is nothing to adjudicate between generator and assertion.**
The one assertion the design note flagged as having been wrong on the stand-in panel —
check 5/6, that a positive quarter-hour price can legitimately be censored when its hourly
mean is negative — holds on real data too, and the generator's behaviour is the correct
one. The design note's finding is confirmed, not overturned.

---

## 4. The three numbers that decide viability

All at rate 0.20, gamma 0.5, logistic, **seed 42**, per the task.
Source: `scratchpad/e1/step4.py`, `step4b_geometry.py`, `step4d_thin.py`.

### 4.1 I4 separability — clears the threshold by ~40×

| area | days exposure differs | quarter-hours | pre-registered threshold | verdict |
|---|---|---|---|---|
| DE | **403** | 2,050 | 10 | PASS |
| 50Hertz | **410** | 2,147 | 10 | PASS |
| Amprion | **399** | 2,130 | 10 | PASS |

Config window: DE 161 days / 867 QH, 50Hertz 164 / 836, Amprion 157 / 845. Still PASS.

Across all 225 grid cells the minimum is **169 days** and the median **392**
(`data/e1/e1_grid_diagnostics.csv`); on the config window, minimum 65, median 157. **Zero
cells fall below 10.** This criterion is not a binding constraint on real data.

**But the count is deceptive, and §4.2 is why.**

### 4.2 Identifying variation in the thin direction — the real problem

Rows where the quarter-hour price is ≥ 0, the hourly mean is < 0, and the hourly-clock
cohort is exposed:

| area | thin rows | of n rows | share | distinct days |
|---|---|---|---|---|
| DE | **10** | 66,761 | 0.0150% | 9 |
| 50Hertz | **7** | 66,759 | 0.0105% | 7 |
| Amprion | **14** | 66,665 | 0.0210% | 12 |
| *stand-in panel reference* | *7* | *23,004* | *0.030%* | — |

**On the config window it is 2 rows for each of the three areas.**

So the real panel is *no better than the fabricated stand-in* in the direction that matters,
and on the pre-registered window it is three to seven times worse.

Decomposing the exposure difference at DE 0.20/0.5/logistic/seed 42 shows why the 403-day
separability figure above gives false comfort:

| exposure pattern | quarter-hours |
|---|---|
| both cohorts exposed | 11,293 |
| QH-clock only (hourly not) | 2,040 ← plentiful |
| **hourly-clock only (QH not)** | **10** ← the thin direction |
| neither | 53,418 |

The 2,050 differing quarter-hours are **99.5% one direction**: quarter-hours with a negative
price whose hourly run is too short to trigger the 2 h cohort. That direction identifies
the *qh-clock* cohort fine. The hourly-clock cohort has essentially no quarter-hour where
it alone is exposed, so its response curve is pinned almost entirely by the 11,293 rows
where both cohorts fire together — where its contribution is collinear with the qh cohort's
and separable only through the 10 rows.

**And this does not improve anywhere in the grid.** Sweeping all rates × gammas (DE,
logistic, seed 42):

| target rate | gamma 0 | gamma 0.5 | gamma 1 |
|---|---|---|---|
| 0.05 | 1 | 3 | 7 |
| 0.10 | 5 | 8 | 5 |
| 0.20 | 3 | 10 | 5 |
| 0.30 | 9 | 10 | 11 |
| 0.40 | 4 | 8 | 4 |

The thin count stays in **1–11 rows** while "both exposed" grows from 2,424 to 25,011.
Raising the censoring rate adds *collinear* exposure, not identifying exposure. There is no
cell of the pre-registered grid where the hourly cohort is well identified.

This is a structural consequence of the block geometry, not bad luck: negative prices are
injected as contiguous blocks with a ~3 h median length and a parabolic depth profile
(design note decision 5). A block long enough to trigger the 2 h hourly cohort is almost
always long enough that its interior quarter-hours are negative too, so the qh cohort fires
on the same rows. The thin direction only occurs at a block's ragged edge, where one or two
quarter-hours sit at the shallow tail of the parabola, above zero, inside an hour whose mean
is still negative. The parabolic profile makes those edges rare by construction.

### 4.3 Event-day realism — defaults kept, deliberately

The identity below is exact and is the whole story:

```
negative-QH share  =  event-day share  x  within-event-day negative share
```

Real DE, full panel: `0.274 x 0.220 = 0.0604`, against an observed 0.0604 — exact.

Generator as it stands (`block_len_qh_median=12`, `p_second_block=0.25`), DE, gamma 0.5,
logistic, seed 42:

| target rate | realised | intensity | event-days / available | event-day share | real |
|---|---|---|---|---|---|
| 0.05 | 0.0485 | 0.469 | 196 / 698 | **28.1%** | 27.4% |
| 0.10 | 0.1004 | 0.938 | 393 / 698 | 56.3% | 27.4% |
| 0.20 | 0.1999 | 1.500 | 419 / 698 | 60.0% | 27.4% |
| 0.30 | 0.3005 | 2.062 | 419 / 698 | 60.0% | 27.4% |
| 0.40 | 0.4019 | 2.906 | 419 / 698 | 60.0% | 27.4% |

**At the 5% rate the generator already reproduces reality almost exactly: 28.1% against
27.4%, an error of 0.7pp.** The task's trigger for retuning — "if a 5% censoring rate
produces an implausible number of event-days" — is therefore **not met**, and I changed
nothing. `max_day_fraction` was not touched.

From rate 0.10 upward the event-day share runs away and then pins at exactly 60.0%, which
is `max_day_fraction = 0.6`: `intensity` exceeds 1 at rate ≥ 0.20, so every selectable day
is already an event-day and further rate is bought by lengthening blocks.

**No `(block_len_qh_median, p_second_block)` pair can fix the higher rates, because the
identity forbids it.** To hold the event-day share at the real 27.4% while reaching a 20%
quarter-hour rate, each event-day would need `0.20 / 0.274 = 73%` of its quarter-hours
negative, against a real figure of 22%. To hold the *within-day* share at the real 22%
instead, you would need `0.20 / 0.22 = 91%` of days to be event-days — above the 0.6 cap.
The sweep confirms both arms of the trade-off (DE, gamma 0.5, seed 42):

| rate | blk_med | p_2nd | realised | event-day share | within-day share |
|---|---|---|---|---|---|
| 0.05 | 12 | 0.25 | 0.0485 | 28.1% | 17.3% |
| 0.05 | 24 | 0.25 | 0.0507 | 14.0% | 36.1% |
| 0.05 | 60 | 0.80 | 0.0515 | 7.4% | 69.1% |
| 0.20 | 12 | 0.25 | 0.1999 | 60.0% | 33.3% |
| 0.20 | 24 | 0.60 | 0.2004 | 46.4% | 43.2% |
| 0.20 | 60 | 0.80 | 0.2023 | 28.8% | 70.3% |
| 0.40 | 12 | 0.25 | 0.4019 | 60.0% | 66.9% |
| 0.40 | 60 | 0.80 | 0.3980 | 57.3% | 69.4% |

Matching the real event-day share at rate 0.20 (`blk=60, p2=0.80` → 28.8%) costs a 70.3%
within-day negative share, i.e. event-days that are three times more negative than any real
one. The geometry can be realistic on one margin or the other, never both, at any rate
above ~5%.

A finer sweep at rate 0.05 — the only rate with a real analogue — averaged over seeds
42/43/44, against the joint target (27.4% event-day, 22.0% within-day):

| blk_med | p_2nd | event-day | within-day | joint distance |
|---|---|---|---|---|
| 12 | 0.25 **(current)** | 27.2% | 18.2% | 0.171 |
| 12 | 0.40 | 24.8% | 20.2% | 0.124 |
| 14 | 0.10 | 25.3% | 19.9% | **0.123** |
| 16 | 0.10 | 22.0% | 22.8% | 0.199 |

The best alternative improves a composite distance from 0.171 to 0.123 **by making the
event-day match worse** (0.2pp error → 2.1pp) to gain on a within-day margin the task did
not ask about. That is tuning to a metric I invented. **Defaults kept at
`block_len_qh_median = 12`, `p_second_block = 0.25`.** The frontier is recorded here so the
choice can be revisited deliberately rather than silently.

---

## 5. Grid — 225 cells, DE only

```
python src/e1_run_grid.py --panel data/processed/panel_qh.parquet \
  --cols 'timestamp=ts_utc_dt,actual_mw=act_wind_mw,forecast_mw=da_wind_mw' \
  --area DE --out-dir data/e1
```

5 rates × 3 gammas × 3 shapes × 5 seeds (0–4). No per-cell Parquet was written.

| | full panel | config window |
|---|---|---|
| cells completed | **225 / 225** | 225 / 225 |
| rate target met | **225 / 225** | 225 / 225 |
| wall clock | **321.6 s (5.36 min)** | 130.7 s (2.18 min) |
| DE rows per cell | 66,761 | 26,593 |

Outputs (both gitignored under `/data/*`, per repo convention):

* `data/e1/e1_grid_diagnostics.csv` — 225 rows, one per cell
* `data/e1/e1_grid_diagnostics_configwindow.csv` — 225 rows, secondary window
* `data/e1/e1_de_r20_g0.0_logistic_s42.parquet` — 66,761 rows, 2.8 MB
* `data/e1/e1_de_r20_g0.5_logistic_s42.parquet` — 66,761 rows, 2.8 MB
* `data/e1/e1_de_r20_g1.0_logistic_s42.parquet` — 66,761 rows, 2.8 MB

8.4 MB of Parquet in total, against 278 MB had all 225 been stored.

### Mean realised rate, by target rate × gamma

| target \ gamma | 0.0 | 0.5 | 1.0 |
|---|---|---|---|
| 0.05 | 0.0508 | 0.0498 | 0.0499 |
| 0.10 | 0.0990 | 0.0993 | 0.1013 |
| 0.20 | 0.1993 | 0.2011 | 0.2002 |
| 0.30 | 0.3000 | 0.2991 | 0.2988 |
| 0.40 | 0.3998 | 0.4008 | 0.4000 |

Every cell within the 0.002 tolerance of its target. Gamma does not bias the rate control.

### Mean `confounding_corr_F_vs_c`, by target rate × gamma

| target \ gamma | 0.0 | 0.5 | 1.0 | monotone? |
|---|---|---|---|---|
| 0.05 | −0.0029 | +0.1335 | +0.2235 | YES |
| 0.10 | −0.0092 | +0.1560 | +0.2322 | YES |
| 0.20 | −0.0178 | +0.1841 | +0.2718 | YES |
| 0.30 | −0.0274 | +0.1753 | +0.2892 | YES |
| 0.40 | −0.0293 | +0.1827 | +0.3106 | YES |

**The correlation rises with gamma at every one of the five rates**, as required, and so it
does on the config window. Two details worth noting: at gamma 0 the correlation is slightly
*negative*, drifting from −0.003 to −0.029 as the rate rises (not zero — censoring removes
output preferentially from high-wind quarter-hours even under uniform placement, which
mechanically depresses the correlation); and the gamma-1 correlation on real data reaches
+0.31 at rate 0.40, above the design note's reported 0.22 for the stand-in panel.

### `cohort_exposure_differs_days` across cells

| | min | p25 | median | max | cells < 10 |
|---|---|---|---|---|---|
| full panel | **169** | 346 | **392** | 411 | **0** |
| config window | 65 | — | 157 | 166 | 0 |

By target rate (full panel): 0.05 → min 169 / median 176; 0.10 → 340 / 358;
0.20 → 395 / 403; 0.30 → 395 / 404; 0.40 → 384 / 392.

### The conversion: quarter-hour share → energy share

This is the number the design note warns gets confused in writing, and it is **strongly
shape-dependent**, which the note understates.

| target rate | step | logistic | half | pooled mean |
|---|---|---|---|---|
| 0.05 | 0.0553 | 0.0205 | 0.0114 | 0.0290 |
| 0.10 | 0.1005 | 0.0375 | 0.0208 | 0.0529 |
| 0.20 | 0.2040 | 0.0782 | 0.0434 | 0.1086 |
| 0.30 | 0.3022 | 0.1129 | 0.0627 | 0.1593 |
| 0.40 | 0.4012 | 0.1536 | 0.0853 | 0.2134 |

**Ratio of energy share to realised quarter-hour share — stable in rate, so usable as a
conversion factor:**

| shape | ratio (rate 0.05 → 0.40) | use |
|---|---|---|
| step | 1.103, 1.006, 1.019, 1.010, 1.002 | **energy ≈ 1.00 × QH rate** |
| logistic | 0.408, 0.375, 0.391, 0.377, 0.384 | **energy ≈ 0.39 × QH rate** |
| half | 0.226, 0.208, 0.217, 0.210, 0.213 | **energy ≈ 0.21 × QH rate** |

Config-window values agree to within 0.002 on every entry.

So "a 20% censoring rate" means a 20.4% energy loss under `step`, 7.8% under `logistic`,
and 4.3% under `half`. **Always state the shape alongside a reported censoring rate, not
just the definition.**

---

## 6. What this means for the week-6 gate (31 Dec 2026)

**E1 is viable on real data as a benchmark for the qh-clock cohort, and is not viable as it
stands for the hourly-clock cohort.** Specifically:

**What works, and needs nothing.**
The observation model is exact, the ground truth is well formed and distinct from the
observable, the rate control hits all five targets in 225/225 cells on both windows, the
confounding knob is monotone at every rate, the three response shapes order correctly, and
generation is deterministic. The real panel is roughly 3× the stand-in's size and runs in
5.4 minutes. 17/17 on three areas. Nothing in the mechanics blocks the gate.

**What blocks part of the gate.**
The hourly-clock cohort's response `r*_hourly` is identified off **1–11 quarter-hours in
every cell of the pre-registered grid** (2 on the config window). Any metric the gate scores
against `r*_hourly` — integrated absolute error of `r̂` against `r*`, and the 80/90%
coverage and PIT of its posterior — will be measuring sampling noise on a handful of rows,
not recovery. Two cohorts are the pre-registered I4 fallback structure, so this is not a
corner of the design; it is 55% of fleet capacity (the hourly cohort's `capacity_share`)
whose response the benchmark cannot score.

The 403-day `cohort_exposure_differs_days` figure does **not** protect against this, and the
pre-registered threshold of 10 does not test for it. The threshold asks whether the cohorts
differ *at all*; it passes at 40× margin while the identifying variation for one of the two
cohorts sits at 10 rows. **I would treat the current threshold as not fit for purpose and
add a direction-specific one** — e.g. at least N quarter-hours where each cohort is exposed
*alone* — before the gate is scored. That is a spec change and needs pre-registration, so
it should be decided now, not in December.

**What needs fixing first, in order.**

1. **Decide which E1 implementation the gate uses** — this new `src/e1_generator.py`, or
   the committed `src/censoring/synthetic.py` that already has metrics, baselines and three
   grid arms behind it (§0.3). Running the gate against two generators is worse than either.
   Note that `synthetic.py` draws episode lengths from the *real* negative-run distribution
   "on both clocks, plus deliberate sub-hour episodes that leave the hourly mean positive"
   (its docstring, `src/censoring/synthetic.py:20-24`) — that is precisely the thin
   direction, injected on purpose. It may already not have this problem. **Check that before
   changing anything here.**

   > **Checked — see `docs/11_e1_identification_audit.md`.** `synthetic.py` has *zero*
   > thin-direction rows, but structurally: its exposure is always evaluated on the
   > quarter-hour price, so a positive quarter-hour can never be censored on either clock.
   > The two generators therefore disagree on what §51 does, which must be settled first.
   > Separately, `synthetic.py` has an exposure matrix of rank 4 of 5 (placeholder cohorts)
   > and 6 of 8 (MaStR), with 34.6% of fleet capacity in exactly-collinear pairs — and the
   > rule-18 check reports "K-cohort stands" at all four AW settings while that holds. The
   > blind spot in the pre-registered criterion is common to both generators.
2. **Fix the thin direction, if this generator is kept.** The cause is the parabolic depth
   profile (`depth_profile_exponent = 0.7`) making above-zero quarter-hours inside a negative
   hour rare at block edges. A deliberate sub-hour-episode mechanism — the same device
   `synthetic.py` uses — would create it by construction. This is a generator change, so it
   must precede any scored run, and the validator's check 6 should be strengthened from
   "> 0 rows" to a real floor.
3. **Settle the study window** (§1). The panel on disk is 1032 days; `smard_config.py:23`
   says the period starts 2025-10-01 (393 days). The gate must state which it scores, and
   the thin direction is materially worse on the narrower one.
4. **Make the panel timezone-aware** in `build_panel.py`, or document that `ts_utc_dt` is
   naive-UTC. Harmless for E1, a trap for the next consumer.
5. **Fix the two wrong statements in the design note** (§7) before they reach the write-up.

**What does not need fixing.** Event-day realism. The geometry already matches reality at
the only rate that has a real analogue, and the higher rates are stress tests whose
event-day share cannot be made realistic without making event-days themselves absurd (§4.3).
Leave `max_day_fraction`, `block_len_qh_median` and `p_second_block` alone and report the
rates as stress tests rather than as calibrated scenarios.

---

## 7. What surprised me

1. **The thin direction does not grow with the censoring rate.** I expected a 40% censoring
   rate to buy identifying variation. It buys collinear variation instead: "both exposed"
   goes 2,424 → 25,011 while "hourly only" stays at 1–11. Turning the rate up makes the
   dataset bigger and the hourly cohort no better identified. This is the single most
   important finding in this run and it was not visible from the stand-in panel, where the
   7 rows looked like a small-sample artefact rather than a structural ceiling.

2. **The 403-day separability figure is nearly meaningless as written.** 99.5% of the
   differing quarter-hours are one direction. A pre-registered check that passes at 40×
   margin while the thing it is meant to protect sits at 10 rows is a check that measures
   the wrong quantity. I did not expect the pre-registered threshold itself to be the
   problem.

3. **The design note's energy-share claim is wrong.** It states "at a 20% quarter-hour rate
   the energy share is roughly 6–10% depending on response shape". On real DE the range is
   **4.3% to 20.4%** — `step` gives 20.4%, double the top of the stated band, and `half`
   gives 4.3%, below the bottom. The 6–10% band happens to bracket `logistic` (7.8%) only.
   Since the note's stated purpose is to stop the two rates being confused in the write-up,
   a wrong conversion band there is worse than none.

4. **The design note's "Next build" list is already built.** It names the metrics module
   and baselines B1–B4 as the next thing to write; `src/censoring/metrics.py` and
   `src/censoring/baselines.py` are committed, as is `gate_verdict.py`. Combined with the
   existence of `synthetic.py`, the note appears to describe a parallel effort rather than
   the state of this repo, and I would not trust its other forward-looking statements
   without checking them.

5. **The panel on disk is 2.6× the configured study period**, and the task's own reference
   figure ("99 event-days in 391 days") turned out to be the config window rather than the
   file. Two credible definitions of "the real panel" differ by 21 months of data, and
   nothing in the repo flags the mismatch. I found it only because the 283/1032 I measured
   would not reconcile with the 99/391 I was given.

6. **`min_qh_per_day = 88` discards 32% of clean days** (333 of 1031). I expected a handful.
   It is defensible — a run length needs a near-complete day — but it means E1 runs on 698
   days, and the figure appears nowhere in the design note.

7. **`corr(F, c)` at gamma 0 is not zero but mildly negative**, and systematically more so
   at higher rates (−0.003 at 5%, −0.029 at 40%). Censoring removes output preferentially
   where there is output to remove, so even uniform placement induces a small negative
   correlation. Harmless, but "gamma 0 means unconfounded" is not exactly true and the
   gate's placebo arm should expect a small negative value rather than zero.

8. **The price column is identical across all five control areas.** Obvious in hindsight —
   one DE/LU bidding zone — but it means the 50Hertz and Amprion runs differ from DE only
   through the wind columns, so they are much less independent as robustness checks than
   three separate areas sound.

---

## Reproducing every number in this document

```
# §1 panel facts
python src/e1_check_panel.py

# §3 validator, per area
python src/e1_validate.py --panel data/processed/panel_qh.parquet \
  --cols 'timestamp=ts_utc_dt,actual_mw=act_wind_mw,forecast_mw=da_wind_mw' --area DE

# §4 the three numbers
python src/e1_check_numbers.py    # 4.1 separability, 4.2 thin direction, 4.3 event-days
python src/e1_check_geometry.py   # geometry sweep, fine sweep, exposure decomposition
python src/e1_check_thin.py       # thin direction across all rates x gammas

# §5 grid
python src/e1_run_grid.py --panel data/processed/panel_qh.parquet \
  --cols 'timestamp=ts_utc_dt,actual_mw=act_wind_mw,forecast_mw=da_wind_mw' \
  --area DE --out-dir data/e1

# config window variant
python src/e1_run_grid.py --panel data/processed/panel_qh.parquet \
  --cols 'timestamp=ts_utc_dt,actual_mw=act_wind_mw,forecast_mw=da_wind_mw' \
  --area DE --from-date 2025-10-01 --out-dir data/e1 --tag _configwindow
```

Seed 42 for the representative frames and the §4 numbers; seeds 0–4 for the grid; no
shuffling; `data/raw/` untouched throughout.
