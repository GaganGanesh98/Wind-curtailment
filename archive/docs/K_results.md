# K — results: the statute-anchored bias bridge

Pre-registration `docs/K0_preregistration.md`, commit **`299e3f9`**, recorded in every K
artifact (`k0_commit`). Code `src/potential/k_bridge.py` (written after K0), data through
`src/potential/k_bridge_data.py`. Every figure below is re-derived by
`tests/test_reported_numbers.py`.

## K1 — pseudo-event cross-validation: **FAIL** (the gate)

> **On the three-area aggregate the nominal 90% band covers 0.740 of the masked quarter-hours
> (95% interval [0.675, 0.806]) with a median half-width of 0.189 log units.** The pass rule
> needed coverage in [0.85, 0.95] and a median half-width below 0.03. Both fail: coverage below
> 0.85 means the error model is wrong, and a half-width at or above 0.047 means no gain over the
> measured global bias. **Per hard rule 3 the phase stops here: K2, K3, K4 and K5 are not run,
> and nothing in the bridge was adjusted after K1's metric was seen.**

Setting, as K0 fixed it: 321 pseudo-event windows (3 per held-out non-event day, 107 days,
2026-03-30 to 2026-09-30), start and length drawn from the 134 real negative runs; covariance
fitted on the 160 earlier non-event days; δ = 0. Artifacts: `artifacts/K1/k1_summary.csv`,
`k1_verdict.csv`, `k1_covariance.csv`, `k1_windows.csv`, `k1_masked_qh.csv`. Intervals: held-out-day
block bootstrap, 5,000 draws, seed 42.

### Projection H (decides the gate on the aggregate)

| unit | windows | bin | masked QH | coverage | 95% interval | median half-width | 95% interval | 90th pct half-width |
|---|---|---|---|---|---|---|---|---|
| H 50Hertz+Amprion+TransnetBW | 321 | all | 5099 | 0.740 | [0.675, 0.806] | 0.189 | [0.077, 0.207] | 0.248 |
| H 50Hertz+Amprion+TransnetBW | 100 | short | 132 | 0.886 | [0.822, 0.946] | 0.137 | [0.047, 0.137] | 0.146 |
| H 50Hertz+Amprion+TransnetBW | 76 | medium | 842 | 0.768 | [0.672, 0.856] | 0.169 | [0.066, 0.186] | 0.215 |
| H 50Hertz+Amprion+TransnetBW | 145 | long | 4125 | 0.730 | [0.655, 0.803] | 0.203 | [0.077, 0.222] | 0.250 |
| H 50Hertz | 321 | all | 5099 | 0.662 | [0.592, 0.727] | 0.294 | [0.051, 0.321] | 0.385 |
| H 50Hertz | 100 | short | 132 | 0.758 | [0.662, 0.848] | 0.213 | [0.033, 0.213] | 0.227 |
| H 50Hertz | 76 | medium | 842 | 0.664 | [0.560, 0.764] | 0.151 | [0.044, 0.286] | 0.336 |
| H 50Hertz | 145 | long | 4125 | 0.658 | [0.579, 0.731] | 0.315 | [0.051, 0.345] | 0.388 |
| H Amprion | 321 | all | 5099 | 0.740 | [0.683, 0.793] | 0.062 | [0.058, 0.072] | 0.088 |
| H Amprion | 100 | short | 132 | 0.811 | [0.717, 0.897] | 0.050 | [0.037, 0.050] | 0.053 |
| H Amprion | 76 | medium | 842 | 0.739 | [0.638, 0.829] | 0.061 | [0.052, 0.067] | 0.077 |
| H Amprion | 145 | long | 4125 | 0.737 | [0.675, 0.797] | 0.062 | [0.058, 0.077] | 0.089 |
| H TransnetBW | 321 | all | 5099 | 0.861 | [0.815, 0.902] | 0.113 | [0.106, 0.245] | 0.363 |
| H TransnetBW | 100 | short | 132 | 0.879 | [0.804, 0.946] | 0.066 | [0.066, 0.074] | 0.194 |
| H TransnetBW | 76 | medium | 842 | 0.808 | [0.713, 0.890] | 0.098 | [0.091, 0.240] | 0.305 |
| H TransnetBW | 145 | long | 4125 | 0.872 | [0.823, 0.913] | 0.114 | [0.108, 0.289] | 0.366 |

### Day-ahead forecast F (reported, decides nothing)

| unit | windows | bin | masked QH | coverage | 95% interval | median half-width | 95% interval | 90th pct half-width |
|---|---|---|---|---|---|---|---|---|
| F 50Hertz+Amprion+TransnetBW | 321 | all | 5099 | 0.761 | [0.704, 0.817] | 0.264 | [0.190, 0.292] | 0.386 |
| F 50Hertz+Amprion+TransnetBW | 100 | short | 132 | 0.955 | [0.907, 0.991] | 0.182 | [0.093, 0.182] | 0.195 |
| F 50Hertz+Amprion+TransnetBW | 76 | medium | 842 | 0.850 | [0.778, 0.914] | 0.231 | [0.140, 0.256] | 0.304 |
| F 50Hertz+Amprion+TransnetBW | 145 | long | 4125 | 0.736 | [0.671, 0.800] | 0.289 | [0.203, 0.322] | 0.390 |
| F 50Hertz | 321 | all | 5099 | 0.757 | [0.699, 0.814] | 0.380 | [0.271, 0.424] | 0.563 |
| F 50Hertz | 100 | short | 132 | 0.924 | [0.867, 0.972] | 0.261 | [0.127, 0.261] | 0.278 |
| F 50Hertz | 76 | medium | 842 | 0.873 | [0.806, 0.932] | 0.268 | [0.186, 0.359] | 0.443 |
| F 50Hertz | 145 | long | 4125 | 0.728 | [0.661, 0.796] | 0.417 | [0.300, 0.467] | 0.569 |
| F Amprion | 321 | all | 5099 | 0.839 | [0.792, 0.886] | 0.358 | [0.336, 0.386] | 0.502 |
| F Amprion | 100 | short | 132 | 0.985 | [0.960, 1.000] | 0.263 | [0.196, 0.263] | 0.281 |
| F Amprion | 76 | medium | 842 | 0.922 | [0.865, 0.966] | 0.331 | [0.300, 0.362] | 0.422 |
| F Amprion | 145 | long | 4125 | 0.817 | [0.764, 0.872] | 0.371 | [0.341, 0.423] | 0.507 |
| F TransnetBW | 321 | all | 5099 | 0.828 | [0.785, 0.869] | 0.572 | [0.543, 0.593] | 0.702 |
| F TransnetBW | 100 | short | 132 | 0.939 | [0.883, 0.984] | 0.350 | [0.340, 0.350] | 0.390 |
| F TransnetBW | 76 | medium | 842 | 0.835 | [0.770, 0.895] | 0.493 | [0.473, 0.500] | 0.572 |
| F TransnetBW | 145 | long | 4125 | 0.823 | [0.774, 0.870] | 0.606 | [0.579, 0.621] | 0.713 |

## Why the error model fails (fit days only)

From `artifacts/K1/k1_diagnostics.csv`, computed on the 160 fit days and nothing else:

- **The bias is persistent for minutes, not hours.** The aggregate's empirical autocorrelation of
  y_t is 0.987 at one quarter-hour (P0's 0.989 for F agrees) but 0.263 at four hours (lag 16) and
  0.028 at eight hours (lag 32). 59 of the 134 real negative runs last longer than four hours, so
  most of a run lies beyond the reach of its shoulder anchors.
- **The pre-registered covariance cannot take that shape.** The single AR(1) term fits 0.915 at
  lag 1 against the empirical 0.987, and the fit fails K0's check (within 0.05 at lags 1–32) for
  every unit, pooled and in every wind tercile, so the pre-registered tercile fallback was used and
  also failed its check.
- **Low-wind days dominate the width.** The aggregate's lowest wind tercile has an empirical
  variance of y of 0.0207 against 0.0020 and 0.0008 in the other two: log(H/(G+RD)) is unstable
  when output is small.

These are observations about why K1 failed, not proposals; K0 forbids re-fitting after K1.

**Disclosed:** a `--smoke` run (20 of the 107 held-out days, output under `demo/output/`, not
committed) printed a verdict line before the full run. Nothing was changed between it and the
full run.

## Status of K2–K5

| step | status |
|---|---|
| K2 synthetic validation | not run (K1 failed) |
| K3 onset-jump placebo | not run; by K0 §1 it would be NOT TESTABLE anyway (no negative quarter-hour has e_t ≤ 0.05; minimum 0.3135) |
| K4 real-data bridged bounds | not run (K1 failed); Phase V's B-based breakdown points stand as the bias statement |
| K5 integration (C1 section, F11–F13, demo step) | not done (K1 failed) |

## Future work (out of scope, one line each)

- A joint identified set using exposure gradients from the 2024 – Sep 2025 hourly regime.
- Triple collocation of H, F and a weather-based potential to separate their errors.
- Validation on AEMO or ERCOT data, where unit-level availability is published.
- Calibrated-projection inference for the identified sets.
- Any solar analysis.
