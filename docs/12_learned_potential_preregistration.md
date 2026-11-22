# Experiment 4, learning available power: pre-registration

Written on 22 Nov 2026 and committed before any model was fitted on real data. Every number in
the design block below is read from `src/method/learned_potential/config.py`.

## Purpose

Experiment 3 reports how much bias in H each reading survives, but H's bias during negative
prices cannot be observed directly. Experiment 4 learns a second estimate of available power, Â,
that never sees the price, and uses it to estimate that bias. The estimate gives a data-driven
budget B̂, and the existing breakdown points are compared against it. Â is also run as an
alternative potential for Experiment 3.

**Assumption A1.** Conditional on the allowed inputs, available power does not depend on the
price. Price changes output only through switch-off. This cannot be proven from data; the
look-alike validation and the domain classifier's overlap report are the evidence offered for it.

## Sets and target

- **Clean set:** quarter-hours where nothing should be switched off, so output G equals available
  power. These are the only labelled training rows.
- **Target set:** negative-price quarter-hours, where Â is needed.
- **Target variable:** y = log(G / F) per control area and quarter-hour, F the onshore day-ahead
  forecast. Â = F · exp(ŷ), with ŷ the predicted median. The multiplicative form follows the
  kill test, where the forecast error behaved like a proportional haircut.

## Inputs (closed allow-list)

The onshore, offshore and solar day-ahead forecasts of the area (all published before the
auction; the offshore forecast is zero in Amprion and TransnetBW, which have no offshore wind),
the quarter-hour of the day and the day of the week in Berlin time, a nationwide public-holiday
flag computed from the calendar (state-only holidays are not included), and the area. N1 also
sees the three forecasts over a window around the quarter-hour. Nothing else, in particular never
the price, θ, exposure, depth, run length, H, G of the scored day, the intraday forecast,
redispatch or anything derived from them. The allow-list is enforced in code and tested.

## Design

<!-- generated:exp4_design -->
- **Data.** Control areas 50Hertz, Amprion, TransnetBW; quarter-hours from 2024-01-01; every score and the budget use the evaluation window 2025-10-01 to 2026-09-30.
- **Clean set:** price above 5 €/MWh and no renewable redispatch in the area. **Target set:** price below 0.
- **Folds.** Rolling origin by calendar month over the evaluation window: the model for month m is trained on clean quarter-hours from 2024-01-01 to 7 days before m starts, and predicts all of month m. Never shuffled.
- **Domain classifier.** Gradient-boosted (31 leaves, learning rate 0.05, 300 trees, at least 100 rows per leaf), cross-fitted leaving one calendar month out. Weights w = p/(1 − p) × n_clean/n_target, clipped at their 99th percentile. No overlap: p above 0.99; stop if more than 10% of target quarter-hours lack overlap. Look-alike: clean quarter-hours in the evaluation window in the top 10% of p.
- **L1, L2.** LightGBM quantile models at 0.05, 0.25, 0.5, 0.75, 0.95; learning rate 0.03, at least 100 rows per leaf, row subsample 0.8; grid: 15 leaves, 300 trees; 31 leaves, 300 trees; 15 leaves, 800 trees; 31 leaves, 800 trees.
- **N1.** Temporal CNN over the allowed forecasts from −6 h to +6 h, kernel 5, quantile heads at 0.05, 0.25, 0.5, 0.75, 0.95, pinball loss, Adam at 0.001, batch 512, at most 40 epochs, early stopping after 6 epochs without improvement on the last 28 days of the training span; grid: 2 layers, 16 channels; 2 layers, 32 channels; 3 layers, 16 channels; 3 layers, 32 channels; seed 42, CPU, deterministic.
- **Hyperparameters** chosen once: train to 2025-08-24, validate on clean quarter-hours of 2025-09 (median pinball loss, importance-weighted for L2 and N1), then fixed for every fold.
- **Intervals.** Day-block bootstrap, 5,000 draws, seed 42.
- **S2 tolerance:** ±0.02. **Ties** in |bias| at 4 decimals, broken by σ. **Agreement** of the Experiment 3 arm: same verdict at B = 0 and breakdown within 0.01.
<!-- /generated -->

## Models

- **B-F:** Â = F. **B-H:** H itself, scored on the same quarter-hours.
- **L1:** LightGBM quantile models, unweighted. **L2:** the same, importance-weighted.
- **N1:** the temporal CNN, importance-weighted.
- Quantile predictions are sorted per row, so they never cross.

## Scores on look-alike quarter-hours

Primary, at the three-area aggregate (the level Experiment 3 uses): the look-alike timestamps
are those clean in all three areas whose mean p across the areas is in the top decile among such
timestamps in the evaluation window. On them, σ and mean of log(ΣG / ΣÂ), with day-block
intervals. Secondary, per area and pooled over area rows: σ and mean of log(G / Â), pinball loss
of the quantiles on the log scale, and coverage of the outer quantile band. F and H are scored on
the same quarter-hours.

## Bias budget

- b̂_H is the mean over Experiment 3's negative-price quarter-hours of log(ΣH / ΣÂ), and β̂_Â is the
  aggregate look-alike mean of log(ΣG / ΣÂ), both with their own day-block bootstrap.
- Corrected: b̂_H − β̂_Â, an estimate of the mean of log(H / A) at negative prices. Its interval
  comes from subtracting the two sets of draws, so both uncertainties enter.
- B̂ is the larger absolute end of that interval.
- The selected model is the one among L1, L2 and N1 with the lowest look-alike |bias|, ties broken
  by σ. B-F's budget is reported beside it.

## Success criteria

- **S1.** The best learned model has a lower look-alike σ than F.
- **S2.** The selected model's look-alike bias interval lies within the tolerance in the design
  block. If not, B̂ is reported as not estimable with public inputs, and the readings are not
  compared against it.
- **S3.** The importance-weighted models are not worse than L1 on look-alike σ. Reported either
  way; the weighting is not dropped.

## Downstream, fixed now

- Each reading's breakdown point, on the pre-registered 0.01 grid and the post-hoc finer grid
  (`docs/10_posthoc_breakdown_grid.md`), is compared with B̂: a reading holds at B̂ if it still
  holds at the first grid allowance at or above B̂.
- Experiment 3's full-window identified sets are re-run with the selected model's Â as the
  potential (B = 0 and the pre-registered 0.01 B grid) as a robustness arm, through `run_v2` with
  its default unchanged. A reading agrees with the headline when its verdict at B = 0 is the same
  and its breakdown moves by less than the tolerance in the design block.

## What this cannot show

A1 is an assumption. The look-alike quarter-hours resemble negative-price quarter-hours in the
allowed inputs, not in everything; if Â is biased there in a way the inputs do not reveal, B̂ is
biased too.
