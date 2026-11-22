# Experiment 4, learning available power: results

Pre-registration and Amendment 1: `docs/12_learned_potential_preregistration.md`. Code
`src/method/learned_potential/`; artifacts `artifacts/exp4_learned_potential/`. Every table and
figure below is generated from those artifacts. Steps 3 to 5 (N1, the bias budget and the
downstream comparisons) are not done yet; this note grows with them.

## Step 2: L1 and L2 (LightGBM)

**Hyperparameter selection** (pre-window fold, `gbm_selection.csv`):

<!-- generated:exp4_selection -->
| model | leaves | trees | median pinball loss, validation month | chosen |
|---|---|---|---|---|
| L1 | 15 | 300 | 0.1357 | yes |
| L1 | 31 | 300 | 0.1361 |  |
| L1 | 15 | 800 | 0.1362 |  |
| L1 | 31 | 800 | 0.1378 |  |
| L2 | 15 | 300 | 0.1612 | yes |
| L2 | 31 | 300 | 0.1707 |  |
| L2 | 15 | 800 | 0.1658 |  |
| L2 | 31 | 800 | 0.1765 |  |
<!-- /generated -->

**Folds** (rolling origin by month; `gbm_fold_training.csv`). L1 and L2 train on the same rows;
look-alike quarter-hours of earlier months are ordinary clean rows in later folds' training, as
the rolling origin implies, and none of the scored month is ever trained on.

<!-- generated:exp4_folds -->
| scored month | last training day | training rows (L1 = L2) | sum of weights, L2 | target rows in training | look-alike rows of the scored month in training |
|---|---|---|---|---|---|
| 2025-10 | 2025-09-23 | 151,990 | 59,755 | 0 | 0 |
| 2025-11 | 2025-10-24 | 159,357 | 63,512 | 0 | 0 |
| 2025-12 | 2025-11-23 | 166,666 | 64,640 | 0 | 0 |
| 2026-01 | 2025-12-24 | 174,290 | 65,124 | 0 | 0 |
| 2026-02 | 2026-01-24 | 182,210 | 67,510 | 0 | 0 |
| 2026-03 | 2026-02-21 | 190,061 | 69,801 | 0 | 0 |
| 2026-04 | 2026-03-24 | 197,814 | 77,024 | 0 | 0 |
| 2026-05 | 2026-04-23 | 204,063 | 80,688 | 0 | 0 |
| 2026-06 | 2026-05-24 | 211,075 | 86,259 | 0 | 0 |
| 2026-07 | 2026-06-23 | 217,786 | 94,506 | 0 | 0 |
| 2026-08 | 2026-07-24 | 224,783 | 105,173 | 0 | 0 |
| 2026-09 | 2026-08-24 | 232,276 | 117,187 | 0 | 0 |
<!-- /generated -->

**Look-alike scores, all look-alike quarter-hours** (`lookalike_scores.csv`; day-block 95%
intervals; F and H on the same quarter-hours; N1's rows were added in step 3):

<!-- generated:exp4_lookalike_all -->
| unit | model | quarter-hours / days | σ of log(G / Â) | mean of log(G / Â) | pinball loss | 0.05–0.95 coverage |
|---|---|---|---|---|---|---|
| 50Hertz | F | 1,480 / 161 | 0.3254 [0.2552, 0.3949] | −0.0908 [−0.1508, −0.0381] | — | — |
| 50Hertz | H | 1,480 / 161 | 0.0917 [0.0694, 0.1152] | −0.0674 [−0.0804, −0.0564] | — | — |
| 50Hertz | L1 | 1,480 / 161 | 0.3279 [0.2574, 0.3994] | −0.0992 [−0.1608, −0.0461] | 0.0723 [0.0563, 0.0929] | 0.842 [0.777, 0.899] |
| 50Hertz | L2 | 1,480 / 161 | 0.3305 [0.2612, 0.4006] | −0.1011 [−0.1622, −0.0469] | 0.0760 [0.0588, 0.0978] | 0.747 [0.673, 0.817] |
| 50Hertz | N1 | 1,480 / 161 | 0.3245 [0.2536, 0.3947] | −0.1102 [−0.1725, −0.0571] | 0.0717 [0.0551, 0.0925] | 0.834 [0.770, 0.893] |
| Amprion | F | 3,454 / 225 | 0.3567 [0.2994, 0.4118] | +0.0834 [+0.0394, +0.1291] | — | — |
| Amprion | H | 3,454 / 225 | 0.0881 [0.0769, 0.0993] | −0.0330 [−0.0416, −0.0248] | — | — |
| Amprion | L1 | 3,454 / 225 | 0.3365 [0.2818, 0.3902] | +0.0362 [−0.0063, +0.0795] | 0.0717 [0.0611, 0.0839] | 0.856 [0.816, 0.893] |
| Amprion | L2 | 3,454 / 225 | 0.3447 [0.2915, 0.3973] | +0.0451 [+0.0016, +0.0893] | 0.0749 [0.0636, 0.0876] | 0.817 [0.774, 0.856] |
| Amprion | N1 | 3,454 / 225 | 0.3320 [0.2836, 0.3818] | +0.0573 [+0.0167, +0.0993] | 0.0742 [0.0638, 0.0857] | 0.844 [0.806, 0.879] |
| TransnetBW | F | 3,815 / 257 | 0.5142 [0.4416, 0.5847] | +0.0837 [+0.0183, +0.1494] | — | — |
| TransnetBW | H | 3,815 / 257 | 0.1964 [0.1500, 0.2398] | −0.1444 [−0.1689, −0.1228] | — | — |
| TransnetBW | L1 | 3,815 / 257 | 0.4549 [0.3978, 0.5114] | +0.0301 [−0.0281, +0.0862] | 0.1033 [0.0921, 0.1158] | 0.910 [0.885, 0.932] |
| TransnetBW | L2 | 3,815 / 257 | 0.4601 [0.4052, 0.5140] | +0.0311 [−0.0264, +0.0856] | 0.1061 [0.0940, 0.1196] | 0.875 [0.843, 0.905] |
| TransnetBW | N1 | 3,815 / 257 | 0.4941 [0.4316, 0.5552] | +0.0362 [−0.0252, +0.0961] | 0.1123 [0.0988, 0.1273] | 0.847 [0.812, 0.880] |
| pooled area rows | F | 8,749 / 285 | 0.4333 [0.3855, 0.4821] | +0.0541 [+0.0128, +0.0960] | — | — |
| pooled area rows | H | 8,749 / 285 | 0.1548 [0.1253, 0.1838] | −0.0874 [−0.1003, −0.0758] | — | — |
| pooled area rows | L1 | 8,749 / 285 | 0.3945 [0.3553, 0.4348] | +0.0106 [−0.0259, +0.0463] | 0.0856 [0.0771, 0.0951] | 0.877 [0.855, 0.898] |
| pooled area rows | L2 | 8,749 / 285 | 0.4005 [0.3625, 0.4384] | +0.0143 [−0.0219, +0.0498] | 0.0887 [0.0798, 0.0985] | 0.831 [0.805, 0.855] |
| pooled area rows | N1 | 8,749 / 285 | 0.4139 [0.3721, 0.4554] | +0.0198 [−0.0177, +0.0567] | 0.0904 [0.0813, 0.1004] | 0.844 [0.818, 0.868] |
| three-area aggregate | F | 2,430 / 206 | 0.2370 [0.1953, 0.2790] | −0.0137 [−0.0501, +0.0191] | — | — |
| three-area aggregate | H | 2,430 / 206 | 0.0710 [0.0550, 0.0872] | −0.0436 [−0.0521, −0.0362] | — | — |
| three-area aggregate | L1 | 2,430 / 206 | 0.2354 [0.1944, 0.2773] | −0.0201 [−0.0552, +0.0124] | — | — |
| three-area aggregate | L2 | 2,430 / 206 | 0.2421 [0.2004, 0.2854] | −0.0147 [−0.0505, +0.0191] | — | — |
| three-area aggregate | N1 | 2,430 / 206 | 0.2358 [0.1962, 0.2762] | −0.0225 [−0.0577, +0.0103] | — | — |
<!-- /generated -->

**Look-alike scores, sunny look-alike days** (descriptive only, not a criterion):

<!-- generated:exp4_lookalike_sunny -->
| unit | model | quarter-hours / days | σ of log(G / Â) | mean of log(G / Â) | pinball loss | 0.05–0.95 coverage |
|---|---|---|---|---|---|---|
| 50Hertz | F | 134 / 8 | 0.3133 [0.1755, 0.4020] | −0.1100 [−0.3172, +0.0568] | — | — |
| 50Hertz | H | 134 / 8 | 0.0510 [0.0225, 0.0640] | −0.0439 [−0.0720, −0.0186] | — | — |
| 50Hertz | L1 | 134 / 8 | 0.3052 [0.1647, 0.3815] | −0.1300 [−0.3342, +0.0270] | 0.0767 [0.0390, 0.1334] | 0.806 [0.537, 0.971] |
| 50Hertz | L2 | 134 / 8 | 0.2843 [0.1669, 0.3571] | −0.1648 [−0.3401, −0.0119] | 0.0804 [0.0409, 0.1377] | 0.739 [0.457, 0.938] |
| 50Hertz | N1 | 134 / 8 | 0.2966 [0.1620, 0.3821] | −0.1427 [−0.3281, +0.0211] | 0.0746 [0.0422, 0.1180] | 0.896 [0.738, 1.000] |
| Amprion | F | 189 / 7 | 0.5281 [0.3373, 0.6557] | +0.1529 [−0.0786, +0.3819] | — | — |
| Amprion | H | 189 / 7 | 0.0731 [0.0359, 0.1104] | −0.0516 [−0.0676, −0.0315] | — | — |
| Amprion | L1 | 189 / 7 | 0.4982 [0.3084, 0.6241] | −0.0234 [−0.2828, +0.2359] | 0.1230 [0.0819, 0.1688] | 0.831 [0.674, 0.958] |
| Amprion | L2 | 189 / 7 | 0.5069 [0.3006, 0.6492] | −0.0213 [−0.2875, +0.2492] | 0.1273 [0.0833, 0.1797] | 0.804 [0.635, 0.944] |
| Amprion | N1 | 189 / 7 | 0.4536 [0.2971, 0.5552] | +0.0276 [−0.1794, +0.2458] | 0.1140 [0.0784, 0.1530] | 0.820 [0.657, 0.954] |
| pooled area rows | F | 323 / 15 | 0.4697 [0.3205, 0.5816] | +0.0439 [−0.1217, +0.2036] | — | — |
| pooled area rows | H | 323 / 15 | 0.0650 [0.0388, 0.0920] | −0.0484 [−0.0640, −0.0315] | — | — |
| pooled area rows | L1 | 323 / 15 | 0.4320 [0.3000, 0.5407] | −0.0676 [−0.2351, +0.0963] | 0.1038 [0.0713, 0.1411] | 0.820 [0.691, 0.926] |
| pooled area rows | L2 | 323 / 15 | 0.4346 [0.2893, 0.5597] | −0.0808 [−0.2504, +0.0896] | 0.1079 [0.0737, 0.1485] | 0.777 [0.632, 0.892] |
| pooled area rows | N1 | 323 / 15 | 0.4049 [0.2838, 0.4949] | −0.0431 [−0.1875, +0.1023] | 0.0976 [0.0700, 0.1280] | 0.851 [0.738, 0.948] |
| three-area aggregate | F | 163 / 7 | 0.1751 [0.0860, 0.2244] | −0.0073 [−0.1111, +0.0774] | — | — |
| three-area aggregate | H | 163 / 7 | 0.0606 [0.0316, 0.0739] | −0.0422 [−0.0718, −0.0144] | — | — |
| three-area aggregate | L1 | 163 / 7 | 0.1479 [0.0593, 0.2045] | −0.0057 [−0.0698, +0.0481] | — | — |
| three-area aggregate | L2 | 163 / 7 | 0.1551 [0.0872, 0.1998] | −0.0261 [−0.0924, +0.0406] | — | — |
| three-area aggregate | N1 | 163 / 7 | 0.1767 [0.0896, 0.2331] | −0.0046 [−0.0839, +0.0721] | — | — |
<!-- /generated -->

## Criteria after step 2

<!-- generated:exp4_criteria_step2 -->
- **S1 (PASS).** Best learned model by aggregate look-alike σ: L1, 0.2354 [0.1944, 0.2773], against F's 0.2370 [0.1953, 0.2790]. The two intervals overlap almost entirely.
- **S3 (FAIL).** L2 σ 0.2421 [0.2004, 0.2854], against L1's 0.2354 [0.1944, 0.2773]. Reported as pre-registered; the weighting is not dropped.
- **S2 (preliminary, FAIL).** Selected so far by the rule (lowest aggregate look-alike |bias|, ties by σ): L2, bias -0.0147 [-0.0505, 0.0191]; the interval must lie within ±0.02. N1 is not fitted yet, so this can still change.
<!-- /generated -->

## Notes

<!-- generated:exp4_notes_step2 -->
- **Grid edge.** Both selections sit at the edge of the pre-registered grid (L1: 15 leaves is the lower edge and 300 trees is the lower edge; L2: 15 leaves is the lower edge and 300 trees is the lower edge). In a two-by-two grid every point is an edge; the grid is not changed, and a model outside it might have scored better.
- **Sunny look-alike days** (descriptive only, not a criterion): look-alike days whose clean quarter-hours have a median solar forecast above the clean set's 75th percentile. Days: 50Hertz 8, Amprion 7, pooled area rows 15, three-area aggregate 7; none in TransnetBW. So the look-alike check reaches sunny conditions only on a handful of days.
<!-- /generated -->
- L2's folds took several times longer to train than L1's with the same hyperparameters and rows.
  A likely cause is LightGBM's quantile objective recomputing leaf values as weighted quantiles
  when sample weights are given; this was not measured further.

## Expectation before N1 (22 November 2026)

Written before any N1 fit, from the L1, L2 and F scores of step 2.

<!-- generated:exp4_expectation -->
- **σ an unbiased model would need** for its aggregate look-alike bias interval to lie within ±0.02: F: σ 0.2370, half-width 0.0346, σ needed 0.137; L1: σ 0.2354, half-width 0.0338, σ needed 0.139; L2: σ 0.2421, half-width 0.0348, σ needed 0.139. Assumption: on the same look-alike days the interval's half-width scales in proportion to σ, so the needed σ is σ × 0.02 / half-width. It ignores any change in how errors cluster within days.
- **Kish effective sample size of L2's weights**, (Σw)² / Σw², per fold: from 5,658 of 151,990 training rows (3.7%) in the 2025-10 fold to 9,731 of 232,276 (4.2%) in the 2026-09 fold (`artifacts/exp4_learned_potential/expectation_before_n1.csv`).
- Descriptive only; no criterion changes.
<!-- /generated -->

## Step 3: N1 (temporal CNN)

**Hyperparameter selection** (pre-window fold, `cnn_selection.csv`):

<!-- generated:exp4_cnn_selection -->
| layers | channels | weighted median pinball loss, validation month | best epoch | chosen |
|---|---|---|---|---|
| 2 | 16 | 0.1587 | 3 | yes |
| 2 | 32 | 0.1656 | 3 |  |
| 3 | 16 | 0.1625 | 3 |  |
| 3 | 32 | 0.1735 | 3 |  |
<!-- /generated -->

<!-- generated:exp4_cnn_grid_edge -->
- **Grid edge.** The selection chose 2 layers and 16 channels: the lower edge of the layers axis and the lower edge of the channels axis, the smallest configuration in the pre-registered grid. The grid is not changed and nothing was retuned; a smaller network outside it might have scored better.
<!-- /generated -->

**Loss curves** (`cnn_loss_trace.csv`, from a logged re-run that reproduced every stored fit bit for
bit; summary `cnn_trace_summary.csv`; figure `figures/14_exp4_n1_loss_curves.png`). The validation
loss is computed on the last 28 days of each training span only, importance-weighted as
pre-registered.

<!-- generated:exp4_cnn_trace -->
| fit | config | epochs | best epoch | train loss: epoch 1 / best / last | validation loss: epoch 1 / best / last | max above best | pattern |
|---|---|---|---|---|---|---|---|
| selection | 2 × 16 | 9 | 3 | 0.0911 / 0.0769 / 0.0696 | 0.1013 / 0.0906 / 0.1038 | 21.6% | unstable |
| selection | 2 × 32 | 9 | 3 | 0.0888 / 0.0760 / 0.0670 | 0.1010 / 0.0921 / 0.1054 | 20.9% | unstable |
| selection | 3 × 16 | 9 | 3 | 0.0919 / 0.0766 / 0.0674 | 0.1057 / 0.0933 / 0.1006 | 22.9% | unstable |
| selection | 3 × 32 | 9 | 3 | 0.0916 / 0.0753 / 0.0649 | 0.1069 / 0.0928 / 0.1008 | 19.0% | unstable |
| 2025-10 | 2 × 16 | 9 | 3 | 0.0906 / 0.0784 / 0.0707 | 0.0732 / 0.0673 / 0.0718 | 25.8% | unstable |
| 2025-11 | 2 × 16 | 7 | 1 | 0.0898 / 0.0898 / 0.0720 | 0.0727 / 0.0727 / 0.0912 | 25.4% | unstable |
| 2025-12 | 2 × 16 | 8 | 2 | 0.0889 / 0.0805 / 0.0714 | 0.0439 / 0.0437 / 0.0474 | 9.3% | unstable |
| 2026-01 | 2 × 16 | 14 | 8 | 0.0882 / 0.0713 / 0.0675 | 0.0389 / 0.0330 / 0.0375 | 17.6% | unstable |
| 2026-02 | 2 × 16 | 10 | 4 | 0.0870 / 0.0741 / 0.0690 | 0.0401 / 0.0395 / 0.0424 | 14.4% | unstable |
| 2026-03 | 2 × 16 | 8 | 2 | 0.0851 / 0.0772 / 0.0692 | 0.0428 / 0.0394 / 0.0438 | 23.3% | unstable |
| 2026-04 | 2 × 16 | 14 | 8 | 0.0822 / 0.0672 / 0.0627 | 0.1016 / 0.0931 / 0.1075 | 22.6% | unstable |
| 2026-05 | 2 × 16 | 15 | 9 | 0.0838 / 0.0674 / 0.0638 | 0.0797 / 0.0771 / 0.0820 | 10.0% | unstable |
| 2026-06 | 2 × 16 | 11 | 5 | 0.0838 / 0.0712 / 0.0665 | 0.0729 / 0.0693 / 0.0731 | 6.1% | unstable |
| 2026-07 | 2 × 16 | 10 | 4 | 0.0831 / 0.0719 / 0.0661 | 0.1196 / 0.1133 / 0.1260 | 13.5% | unstable |
| 2026-08 | 2 × 16 | 11 | 5 | 0.0867 / 0.0743 / 0.0704 | 0.0918 / 0.0860 / 0.0879 | 6.7% | unstable |
| 2026-09 | 2 × 16 | 10 | 4 | 0.0871 / 0.0763 / 0.0712 | 0.1180 / 0.1147 / 0.1208 | 12.5% | unstable |
<!-- /generated -->

<!-- generated:exp4_cnn_trace_note -->
- **Rule.** With rel = (validation loss − best) / best: flat if every epoch is within 2% of the best; rising after the best epoch if, from the best epoch on, no epoch-to-epoch fall exceeds 0.5% of the best and the last epoch is at least 2% above it; unstable otherwise. Descriptive only.
- **Counts over the 16 fits:** unstable 16. Training loss falls in every fit (epoch 1 to last: 0.0822–0.0919 to 0.0627–0.0720); the folds' best epochs run from 1 to 9.
- The validation windows are the last 28 days of each training span, so their level moves with the season of that window; compare curves within a fit, not across fits.
<!-- /generated -->

N1's look-alike scores are in the tables of step 2.

## Criteria after step 3 (final for S1 to S3)

<!-- generated:exp4_criteria_step3 -->
- **S1 (PASS).** Best learned model by aggregate look-alike σ: L1, 0.2354 [0.1944, 0.2773], against F's 0.2370 [0.1953, 0.2790]. The two intervals overlap almost entirely.
- **S3 (FAIL).** L2 σ 0.2421 [0.2004, 0.2854]; N1 σ 0.2358 [0.1962, 0.2762], against L1's 0.2354 [0.1944, 0.2773]. Reported as pre-registered; the weighting is not dropped.
- **S2 (FAIL).** All three learned models are fitted. The rule (lowest aggregate look-alike |bias|, ties by σ) selects L2, bias -0.0147 [-0.0505, 0.0191]; the interval must lie within ±0.02. As pre-registered, B̂ is reported as not estimable with public inputs, and the readings are not compared against it.
<!-- /generated -->

## Interpretation fixed before step 4 (23 November 2026)

Written after S2 failed and before any step 4 computation.

- **The Experiment 3 arm** re-runs the full-window identified sets with L2's Â as the potential.
  L2 failed S2, so Â is not a validated potential. If a reading agrees with the headline under
  Â, that shows only that the reading is robust to this choice of potential, and is weak support.
  If it disagrees, the question is not resolved by public data; disagreement is not evidence that
  H is wrong.
- **b̂_H** is computed as pre-registered and amended (trimmed primary, untrimmed sensitivity, per
  area and pooled, corrected by L2's look-alike bias, day-block bootstrap with 5,000 draws). It is
  descriptive only. No reading is classified against it, and no B̂ is defined.

## Step 4 (reduced): descriptive bias estimate and Experiment 3 arm

**b̂_H** (`bias_budget.csv`; L2's Â; day-block bootstrap; trimmed = target quarter-hours with
overlap, as Amendment 1 C2):

<!-- generated:exp4_bias_table -->
| unit | arm | target quarter-hours (share kept) | b̂_H, mean log(H / Â) | L2 look-alike bias, mean log(G / Â) | corrected, mean log(H / A) | status |
|---|---|---|---|---|---|---|
| 50Hertz | trimmed (primary) | 1,525 (74.3%) | +0.2518 [+0.1847, +0.3182] | −0.1011 [−0.1610, −0.0473] | +0.3529 [+0.2641, +0.4408] | descriptive, S2 failed |
| 50Hertz | untrimmed (sensitivity, extrapolation) | 2,052 (100.0%) | +0.2769 [+0.2169, +0.3353] | −0.1011 [−0.1610, −0.0473] | +0.3779 [+0.2991, +0.4625] | descriptive, S2 failed |
| Amprion | trimmed (primary) | 1,916 (93.4%) | +0.2061 [+0.1558, +0.2617] | +0.0451 [+0.0008, +0.0880] | +0.1610 [+0.0953, +0.2308] | descriptive, S2 failed |
| Amprion | untrimmed (sensitivity, extrapolation) | 2,052 (100.0%) | +0.2180 [+0.1672, +0.2728] | +0.0451 [+0.0008, +0.0880] | +0.1728 [+0.1068, +0.2417] | descriptive, S2 failed |
| TransnetBW | trimmed (primary) | 2,008 (97.9%) | +0.3991 [+0.3001, +0.5209] | +0.0311 [−0.0235, +0.0849] | +0.3680 [+0.2555, +0.5000] | descriptive, S2 failed |
| TransnetBW | untrimmed (sensitivity, extrapolation) | 2,052 (100.0%) | +0.3996 [+0.3012, +0.5182] | +0.0311 [−0.0235, +0.0849] | +0.3686 [+0.2563, +0.4990] | descriptive, S2 failed |
| pooled area rows | trimmed (primary) | 5,449 (88.5%) | +0.2900 [+0.2335, +0.3504] | +0.0143 [−0.0228, +0.0492] | +0.2758 [+0.2096, +0.3467] | descriptive, S2 failed |
| pooled area rows | untrimmed (sensitivity, extrapolation) | 6,156 (100.0%) | +0.2981 [+0.2463, +0.3519] | +0.0143 [−0.0228, +0.0492] | +0.2839 [+0.2219, +0.3481] | descriptive, S2 failed |
| three-area aggregate | trimmed (primary) | 1,997 (97.3%) | +0.2518 [+0.2073, +0.2960] | −0.0147 [−0.0516, +0.0190] | +0.2665 [+0.2100, +0.3236] | descriptive, S2 failed |
| three-area aggregate | untrimmed (sensitivity, extrapolation) | 2,052 (100.0%) | +0.2580 [+0.2124, +0.3026] | −0.0147 [−0.0516, +0.0190] | +0.2728 [+0.2152, +0.3298] | descriptive, S2 failed |
<!-- /generated -->

**Experiment 3 with L2's Â as the potential** (`exp3_with_learned_potential.csv`, full window,
pre-registered 0.01 B grid; `exp3_arm_readings.csv`):

<!-- generated:exp4_arm_table -->
| reading | under H: interval at B = 0, holds, breakdown | under Â (L2): interval at B = 0, holds, breakdown | agrees |
|---|---|---|---|
| λ₁ informative | [0.300, 0.508], yes, 0.04 | [0.000, 0.479], no, 0.00 | no |
| λ₂ lower bound at least 0.5 | [0.525, 0.860], yes, 0.06 | [0.172, 0.990], no, 0.00 | no |
| λ₃ upper bound at most 0.75 | [0.000, 0.579], yes, > 0.15 | [0.000, 0.814], no, 0.00 | no |
| λ₆ upper bound at most 0.5 | [−0.967, 0.398], yes, 0.04 | [−0.795, 0.814], no, 0.00 | no |
<!-- /generated -->

<!-- generated:exp4_arm_note -->
- **Agreement:** 0 of 4 readings agree with the headline. Under Â the data-fit tolerance ε at B = 0 is 0.241, against 0.113 under H, on the same 34,937 quarter-hours: Â follows output much less closely than H, so every identified set widens. As fixed before step 4, this disagreement is not resolved by public data and is not evidence that H is wrong.
- **b̂_H** at the aggregate, trimmed (primary): corrected mean log(H / A) +0.2665 [+0.2100, +0.3236]. Descriptive only: L2 failed S2, no B̂ is defined and no reading is classified against it. It cannot tell H adding back more than was curtailed apart from Â, which never saw negative-price hours, falling short there.
<!-- /generated -->

## Summary of Experiment 4

<!-- generated:exp4_summary -->
- **S2 failed.** The selected model, L2, has an aggregate look-alike bias of -0.0147 [-0.0505, 0.0191], not within ±0.02. B̂ is therefore not estimable with public inputs, and no reading is classified against a budget.
- **The σ gap.** For an unbiased model's interval to fit within ±0.02, its aggregate look-alike σ would need to be about 0.139 (expectation section above); the best learned model, L1, reached 0.235. Neither the shift correction nor the temporal model closed that gap.
<!-- /generated -->

**Figures.** `figures/15_exp4_lookalike_error.png` (look-alike error per model),
`figures/16_exp4_bias_descriptive.png` (b̂_H per area, trimmed and untrimmed, descriptive),
`figures/17_exp4_overlap.png` (domain score distributions), and `figures/14_exp4_n1_loss_curves.png`.
