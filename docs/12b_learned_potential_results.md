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
intervals; F and H on the same quarter-hours):

<!-- generated:exp4_lookalike_all -->
| unit | model | quarter-hours / days | σ of log(G / Â) | mean of log(G / Â) | pinball loss | 0.05–0.95 coverage |
|---|---|---|---|---|---|---|
| 50Hertz | F | 1,480 / 161 | 0.3254 [0.2552, 0.3949] | −0.0908 [−0.1508, −0.0381] | — | — |
| 50Hertz | H | 1,480 / 161 | 0.0917 [0.0694, 0.1152] | −0.0674 [−0.0804, −0.0564] | — | — |
| 50Hertz | L1 | 1,480 / 161 | 0.3279 [0.2574, 0.3994] | −0.0992 [−0.1608, −0.0461] | 0.0723 [0.0563, 0.0929] | 0.842 [0.777, 0.899] |
| 50Hertz | L2 | 1,480 / 161 | 0.3305 [0.2612, 0.4006] | −0.1011 [−0.1622, −0.0469] | 0.0760 [0.0588, 0.0978] | 0.747 [0.673, 0.817] |
| Amprion | F | 3,454 / 225 | 0.3567 [0.2994, 0.4118] | +0.0834 [+0.0394, +0.1291] | — | — |
| Amprion | H | 3,454 / 225 | 0.0881 [0.0769, 0.0993] | −0.0330 [−0.0416, −0.0248] | — | — |
| Amprion | L1 | 3,454 / 225 | 0.3365 [0.2818, 0.3902] | +0.0362 [−0.0063, +0.0795] | 0.0717 [0.0611, 0.0839] | 0.856 [0.816, 0.893] |
| Amprion | L2 | 3,454 / 225 | 0.3447 [0.2915, 0.3973] | +0.0451 [+0.0016, +0.0893] | 0.0749 [0.0636, 0.0876] | 0.817 [0.774, 0.856] |
| TransnetBW | F | 3,815 / 257 | 0.5142 [0.4416, 0.5847] | +0.0837 [+0.0183, +0.1494] | — | — |
| TransnetBW | H | 3,815 / 257 | 0.1964 [0.1500, 0.2398] | −0.1444 [−0.1689, −0.1228] | — | — |
| TransnetBW | L1 | 3,815 / 257 | 0.4549 [0.3978, 0.5114] | +0.0301 [−0.0281, +0.0862] | 0.1033 [0.0921, 0.1158] | 0.910 [0.885, 0.932] |
| TransnetBW | L2 | 3,815 / 257 | 0.4601 [0.4052, 0.5140] | +0.0311 [−0.0264, +0.0856] | 0.1061 [0.0940, 0.1196] | 0.875 [0.843, 0.905] |
| pooled area rows | F | 8,749 / 285 | 0.4333 [0.3855, 0.4821] | +0.0541 [+0.0128, +0.0960] | — | — |
| pooled area rows | H | 8,749 / 285 | 0.1548 [0.1253, 0.1838] | −0.0874 [−0.1003, −0.0758] | — | — |
| pooled area rows | L1 | 8,749 / 285 | 0.3945 [0.3553, 0.4348] | +0.0106 [−0.0259, +0.0463] | 0.0856 [0.0771, 0.0951] | 0.877 [0.855, 0.898] |
| pooled area rows | L2 | 8,749 / 285 | 0.4005 [0.3625, 0.4384] | +0.0143 [−0.0219, +0.0498] | 0.0887 [0.0798, 0.0985] | 0.831 [0.805, 0.855] |
| three-area aggregate | F | 2,430 / 206 | 0.2370 [0.1953, 0.2790] | −0.0137 [−0.0501, +0.0191] | — | — |
| three-area aggregate | H | 2,430 / 206 | 0.0710 [0.0550, 0.0872] | −0.0436 [−0.0521, −0.0362] | — | — |
| three-area aggregate | L1 | 2,430 / 206 | 0.2354 [0.1944, 0.2773] | −0.0201 [−0.0552, +0.0124] | — | — |
| three-area aggregate | L2 | 2,430 / 206 | 0.2421 [0.2004, 0.2854] | −0.0147 [−0.0505, +0.0191] | — | — |
<!-- /generated -->

**Look-alike scores, sunny look-alike days** (descriptive only, not a criterion):

<!-- generated:exp4_lookalike_sunny -->
| unit | model | quarter-hours / days | σ of log(G / Â) | mean of log(G / Â) | pinball loss | 0.05–0.95 coverage |
|---|---|---|---|---|---|---|
| 50Hertz | F | 134 / 8 | 0.3133 [0.1755, 0.4020] | −0.1100 [−0.3172, +0.0568] | — | — |
| 50Hertz | H | 134 / 8 | 0.0510 [0.0225, 0.0640] | −0.0439 [−0.0720, −0.0186] | — | — |
| 50Hertz | L1 | 134 / 8 | 0.3052 [0.1647, 0.3815] | −0.1300 [−0.3342, +0.0270] | 0.0767 [0.0390, 0.1334] | 0.806 [0.537, 0.971] |
| 50Hertz | L2 | 134 / 8 | 0.2843 [0.1669, 0.3571] | −0.1648 [−0.3401, −0.0119] | 0.0804 [0.0409, 0.1377] | 0.739 [0.457, 0.938] |
| Amprion | F | 189 / 7 | 0.5281 [0.3373, 0.6557] | +0.1529 [−0.0786, +0.3819] | — | — |
| Amprion | H | 189 / 7 | 0.0731 [0.0359, 0.1104] | −0.0516 [−0.0676, −0.0315] | — | — |
| Amprion | L1 | 189 / 7 | 0.4982 [0.3084, 0.6241] | −0.0234 [−0.2828, +0.2359] | 0.1230 [0.0819, 0.1688] | 0.831 [0.674, 0.958] |
| Amprion | L2 | 189 / 7 | 0.5069 [0.3006, 0.6492] | −0.0213 [−0.2875, +0.2492] | 0.1273 [0.0833, 0.1797] | 0.804 [0.635, 0.944] |
| pooled area rows | F | 323 / 15 | 0.4697 [0.3205, 0.5816] | +0.0439 [−0.1217, +0.2036] | — | — |
| pooled area rows | H | 323 / 15 | 0.0650 [0.0388, 0.0920] | −0.0484 [−0.0640, −0.0315] | — | — |
| pooled area rows | L1 | 323 / 15 | 0.4320 [0.3000, 0.5407] | −0.0676 [−0.2351, +0.0963] | 0.1038 [0.0713, 0.1411] | 0.820 [0.691, 0.926] |
| pooled area rows | L2 | 323 / 15 | 0.4346 [0.2893, 0.5597] | −0.0808 [−0.2504, +0.0896] | 0.1079 [0.0737, 0.1485] | 0.777 [0.632, 0.892] |
| three-area aggregate | F | 163 / 7 | 0.1751 [0.0860, 0.2244] | −0.0073 [−0.1111, +0.0774] | — | — |
| three-area aggregate | H | 163 / 7 | 0.0606 [0.0316, 0.0739] | −0.0422 [−0.0718, −0.0144] | — | — |
| three-area aggregate | L1 | 163 / 7 | 0.1479 [0.0593, 0.2045] | −0.0057 [−0.0698, +0.0481] | — | — |
| three-area aggregate | L2 | 163 / 7 | 0.1551 [0.0872, 0.1998] | −0.0261 [−0.0924, +0.0406] | — | — |
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
