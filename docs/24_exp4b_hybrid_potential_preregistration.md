# Experiment 4b, a hybrid available-power model: pre-registration

Written on 23 Nov 2026 and committed before any model was fitted on real data. Every constant in
the design block is read from `src/method/learned_potential_v2/config.py`; every count below is
read from `artifacts/exp4b_hybrid_potential/phase0_facts.csv`
(`python -m src.method.learned_potential_v2.facts`), which counts inputs and scores nothing.

## Status and purpose

**A new experiment.** Experiment 4 (`docs/12_learned_potential_preregistration.md`, results in
`docs/12b_learned_potential_results.md`) was pre-registered, run and failed S2. It stays exactly
as reported; no code, doc or artifact of it is changed. Experiment 4b is a separately
pre-registered attempt at the same goal with a different design. It is not a re-run of
Experiment 4, and Experiment 4's verdict does not change whatever 4b finds.

**Goal, unchanged.** Estimate available onshore wind power Â that never sees the price, use it to
estimate H's bias at negative prices, and from that a budget B̂ for the breakdown points of
Experiment 3.

**What changes.** Experiment 4 learned small corrections to the day-ahead forecast F, which is
itself trained on recorded output that contains switch-off. 4b is a hindcast: it estimates, after
the fact, what the weather allowed the fleet to produce. Observed weather (ERA5 reanalysis and DWD
station measurements) is therefore allowed; F is not. The model is built as grid operators build
theirs: physics first (Layer 1), a statistical correction trained on clean hours second (Layer 2).

**Assumption A1, restated.** Conditional on the allowed inputs, available power does not depend on
the price; price changes output only through switch-off. Weather is not affected by price or
switch-off, but A1 cannot be proven from data. The look-alike hours are clean hours that resemble
negative-price hours in the allowed inputs; S2 checks Â there, where the truth is known, and cannot
check it in the negative-price hours themselves.

## Data decisions (student, 23 Nov 2026)

- **Period.** 2024-01-01 to 2026-09-30, the data already local. No back-fill of earlier SMARD or
  redispatch data. ERA5 months before 2024 are downloaded but unused.
- **Resolution.** Hours (UTC). An hour's G, H and F are the means of its four quarter-hours; an
  hour enters only if all four are present.
- **No fit before the inputs are complete.** No model is fitted on real data until every ERA5 month
  from 2024-01 to 2026-09 is on disk and checked.

## Clean, target and look-alike sets

**Onshore-wind redispatch proxy.** The redispatch export has no technology field. A renewable
reduction (direction `reduzieren`, carrier `Erneuerbar`, not a test run or countertrade) instructed
by the area's TSO counts as onshore wind unless the plant name marks it as solar, PV or offshore
(the plant-name rule of `redispatch_checks`). This is conservative: solar inside distribution-cluster
aggregates is counted as wind and removes the hour.

**Unit check.** A renewable reduction whose mean MW × duration and stated MWh are more than the
tolerance apart cannot be resolved; any hour it touches is not clean, whatever its plant name. Scope
as measured, the whole export, three areas:

<!-- generated:exp4b_redispatch -->
- Renewable reductions instructed by the three TSOs, 2024-01-04 to 2026-10-28: 7,328. Named solar or PV: 711. Named offshore: 1,949. Counted as onshore wind (the proxy): 4,668. Failing the unit check: 2,250 of 7,328.
<!-- /generated -->

**Sets.** Clean and target hours as in the design block. Look-alike hours: clean hours in the
evaluation window in the top decile of the domain score p, per area; at the three-area aggregate,
hours clean in all three areas whose mean p across the areas is in the top decile among such hours,
as in Experiment 4.

**Effect of the new clean rule.** Hourly counts, Experiment 4's rule applied to hours against 4b's
rule. The change is negligible. The training history is the same as Experiment 4's (from its
`HISTORY_START`), and the period is the same 33 months. Any gain must therefore come from the
weather inputs and the physics, not from the rule or from more data.

<!-- generated:exp4b_clean -->
| span | area | hours | clean, Experiment 4's rule | clean, 4b before the unit check | clean, 4b |
|---|---|---|---|---|---|
| history | 50Hertz | 15,335 | 10,963 | 11,220 | 10,978 |
| history | Amprion | 15,335 | 13,575 | 13,575 | 13,575 |
| history | TransnetBW | 15,335 | 13,730 | 13,762 | 13,762 |
| evaluation window | 50Hertz | 8,760 | 6,139 | 6,230 | 6,129 |
| evaluation window | Amprion | 8,760 | 7,758 | 7,758 | 7,758 |
| evaluation window | TransnetBW | 8,760 | 7,556 | 7,556 | 7,556 |
<!-- /generated -->

**Overlap.** The 50Hertz midday overlap problem of Experiment 4 (Amendment 1 of docs/12) is
expected to persist, because the clean rule still removes hours with cluster redispatch. Amendment
1's changes C2 to C5 therefore apply from the start: the primary estimand uses target hours with
overlap (p ≤ the threshold), the untrimmed estimate is a labelled sensitivity arm, a reading whose
verdict differs between the two is reported as depending on extrapolation (Amendment 1, C4), and b̂_H is reported per
area and pooled with the trimmed share beside it. There is no overlap stop rule; the shares without
overlap are reported. Amendment 1's exploratory arm E1 is not carried over.

## The fleet (MaStR)

Built from the raw MaStR XML of 31 Oct 2026 (`EinheitenWind.xml`), onshore units only, not units
only planned. Units decommissioned in the period are included up to their decommissioning date.

<!-- generated:exp4b_fleet -->
| area | units live in the period | GW | decommissioned in the period | no coordinates | no hub height | no rotor diameter | area by Bundesland proxy, split state |
|---|---|---|---|---|---|---|---|
| 50Hertz | 11,159 | 23.97 | 560 (0.68 GW) | 0.00% | 0.97% | 0.59% | 3.08% |
| Amprion | 6,595 | 15.68 | 370 (0.43 GW) | 0.26% | 1.57% | 0.87% | 3.13% |
| TransnetBW | 1,010 | 2.37 | 26 (0.03 GW) | 0.02% | 1.11% | 0.84% | 5.64% |
| all | 18,764 | 42.03 | 956 (1.13 GW) | 0.10% | 1.20% | 0.71% | 3.24% |
<!-- /generated -->

- **Live on a day:** commissioned on or before it, and not finally decommissioned on or before it.
  A unit temporarily shut down is not live from the start date of its shutdown.
- **Control area:** the register's grid-connection control area where the processed table has it
  (as in Experiment 3), otherwise the Bundesland. The proxy is approximate only in states split
  between TSOs; their capacity share is in the last column above.
- **Imputation.** Hub height and rotor diameter: the median of onshore units commissioned in the
  same year (nearest year with data if none). Coordinates: the mean of units with coordinates in
  the same municipality key, else the same postcode, else the same Bundesland. Shares imputed are
  reported per area. Rated power and commissioning date are never missing.
- **Installed capacity C** of an area and hour: the sum of rated power of the live units.

## Weather

- **ERA5** (`reanalysis-era5-single-levels`, 0.25°, hourly): 100 m and 10 m wind components, 2 m
  temperature, surface pressure, instantaneous 10 m gust. Bilinear interpolation to each turbine;
  a turbine outside the grid takes the nearest edge point. The hour [h, h+1) takes the mean of the
  instantaneous fields at h and h+1 (at h only for the period's last hour).
- **DWD** hourly station wind speed (open data, `hourly/wind`). Each turbine is assigned to its
  nearest qualifying station; the area value is the capacity-weighted mean over stations with a
  valid value in the hour. DWD speeds are at the anemometer height and are not extrapolated.
- **DWD time stamp.** DWD's hourly mean may be stamped at the start or the end of its interval. The
  lag (0 or 1 h) is fixed before any fit by the higher correlation between DWD speed and ERA5 10 m
  speed at the station's location over 2024. This uses neither G nor the price; the result is
  reported.

<!-- generated:exp4b_dwd -->
- DWD stations with data in the period: 296; with at least 90% of hours valid: 284.
<!-- /generated -->

## Design

<!-- generated:exp4b_design -->
- **Data.** Control areas 50Hertz, Amprion, TransnetBW; hours from 2024-01-01 to 2026-09-30 (Berlin dates); every score and the budget use the evaluation window 2025-10-01 to 2026-09-30. ERA5 months from 2024-01 on are used.
- **Clean hour:** every quarter-hour priced above 5 €/MWh with G > 0, no onshore-wind redispatch measure (proxy below) and no renewable reduction failing the unit check (more than 2% apart) touching the hour in the area. **Target hour:** at least one quarter-hour priced below 0.
- **Folds.** Rolling origin by calendar month over the evaluation window: the model for month m is trained on clean hours from 2024-01-01 to 7 days before m starts, and predicts all of month m. Never shuffled.
- **Physics (Layer 1).** Hub-height speed by the power law from ERA5's 100 m speed, exponent from ERA5's 10 m and 100 m speeds in the same cell and hour, clipped to [0, 0.45], and 0.1429 when either speed is below 0.5 m/s. Density-equivalent speed v·(ρ/1.225)^(1/3), ρ = sp / (287.05 · t2m). Power curve per turbine from its specific power: zero below 3 m/s and at or above 25 m/s; rated speed (2 · specific power / (1.225 · 0.45))^(1/3); (v³ − 3³)/(v_rated³ − 3³) of rated power in between.
- **Correction (Layer 2).** Target y = log((G + 0.01·C) / (P_phys + 0.01·C)), C the installed capacity of the area and hour. LightGBM quantile models at 0.05, 0.25, 0.5, 0.75, 0.95; learning rate 0.03, at least 100 rows per leaf, row subsample 0.8; grid: 15 leaves, 300 trees; 31 leaves, 300 trees; 15 leaves, 800 trees; 31 leaves, 800 trees. Â = max((P_phys + 0.01·C) · exp(ŷ₀.₅) − 0.01·C, 0).
- **New capacity input:** the share of C commissioned in the last 183 days.
- **DWD stations:** those with a valid hourly wind speed in at least 90% of the period's hours.
- **Domain classifier.** Gradient-boosted (31 leaves, learning rate 0.05, 300 trees, at least 100 rows per leaf), on the allowed inputs, cross-fitted leaving one calendar month out. Weights w = p/(1 − p) × n_clean/n_target, clipped at their 99th percentile. No overlap: p above 0.99. Look-alike: clean hours in the evaluation window in the top 10% of p.
- **Hyperparameters** chosen once: train to 2025-08-24, validate on clean hours of 2025-09 (median pinball loss, importance-weighted for H2), then fixed for every fold.
- **Intervals.** Day-block bootstrap, 5,000 draws, seed 42.
- **S2 tolerance:** ±0.02. **Ties** in |bias| at 4 decimals, broken by σ. **Agreement** of the Experiment 3 arm: same verdict at B = 0 and breakdown within 0.01.
<!-- /generated -->

## Inputs (closed allow-list)

<!-- generated:exp4b_inputs -->
- `p_phys_cf`: Layer 1's physical potential P_phys divided by installed capacity C.
- `era5_ws100`: ERA5 100 m wind speed.
- `era5_ws_hub`: hub-height wind speed (before the density correction).
- `era5_dir_sin`: sine of the direction of the capacity-weighted 100 m wind vector.
- `era5_dir_cos`: cosine of the same direction.
- `era5_rho`: air density sp / (R · t2m).
- `era5_gust`: ERA5 instantaneous 10 m gust.
- `era5_gust_ratio`: gust divided by the 10 m speed (turbulence proxy).
- `era5_shear`: power-law shear exponent used for the hub-height speed.
- `era5_t2m`: 2 m temperature (icing).
- `dwd_ws`: DWD station hourly wind speed, each turbine's nearest qualifying station.
- `new_cap_share`: share of C commissioned in the last 183 days.
- `hour_utc`: hour of the day, UTC.
- `month_of_year`: calendar month.
- `area`: control area.
<!-- /generated -->

Never an input, in any model or the domain classifier, in any form: the price, θ, exposure, depth,
run length, H, F (any day-ahead or intraday forecast), G of the hour, redispatch, the clean and
target flags, or anything derived from them. The allow-list is enforced in code and tested, and a
test permutes the price and requires every prediction to be unchanged.

## Models

- **P0:** physics only, Â = P_phys.
- **H1:** hybrid, Layer 2 unweighted. **H2:** hybrid, Layer 2 importance-weighted.
- **Baselines:** F and H on the same hours.
- Quantile predictions are sorted per row, so they never cross. P0 has no quantiles; it enters the
  σ and bias scores only.

## Scores, criteria and selection

Scores on look-alike hours as in Experiment 4: primary at the three-area aggregate, σ and mean of
log(ΣG / ΣÂ) with day-block intervals; secondary per area and pooled, with pinball loss and outer
band coverage for H1 and H2. F and H on the same hours.

- **Selection:** among P0, H1 and H2, the lowest aggregate look-alike |bias|, ties broken by σ.
- **S1.** The best of P0, H1 and H2 has a lower look-alike σ than F.
- **S2.** The selected model's look-alike bias interval lies within the tolerance in the design
  block. If not, B̂ is reported as not estimable with public inputs, and the readings are not
  compared against it.
- **S3.** H2 is not worse than H1 on look-alike σ. Reported either way; the weighting is not
  dropped.
- **S4 (descriptive, no pass rule).** On all clean hours of the evaluation window, the selected
  model's σ of log(ΣG / ΣÂ) next to H's σ of log(ΣG / ΣH): how close a public-data model gets to
  the operators' own estimate.

S1 to S3 are Experiment 4's criteria, unchanged in wording and tolerance.

## Downstream, fixed now (as docs/12 and its Amendment 1)

Only if S2 passes:

- b̂_H, the mean over Experiment 3's negative-price quarter-hours of log(ΣH / ΣÂ), each
  quarter-hour taking Â and p from its hour; corrected by the look-alike bias, both with their own
  day-block bootstrap; trimmed (primary) and untrimmed (sensitivity); per area and pooled. Computed
  as `learned_potential/bias_budget.py` computes it, with 4b's Â.
- B̂ is the larger absolute end of the corrected interval. Each reading's breakdown point, on the
  pre-registered 0.01 grid and the post-hoc finer grid (`docs/10_posthoc_breakdown_grid.md`), is
  compared with B̂.
- Experiment 3's full-window identified sets are re-run with the selected model's Â as the potential
  (B = 0 and the 0.01 B grid) through `run_v2` with its default unchanged. A reading agrees with
  the headline when its verdict at B = 0 is the same and its breakdown moves by less than the
  tolerance in the design block.

If S2 fails: stop. The conclusion is that public data cannot calibrate H's bias, even with a
grid-operator-style hybrid model on observed weather.

## Build commitments (Phase 2, before any real fit)

Modules in `src/method/learned_potential_v2/`: `weather.py`, `fleet.py`, `physics.py`,
`hybrid.py`, `evaluate.py` (Experiment 4's scoring functions by import). Tests: the allow-list; the
price permutation; no fold scores a day it trained on; the power curve is zero below cut-in and at
or above cut-out and monotone between; P_phys / C within [0, 1]; capacity per area against the
processed MaStR totals within 1%; a fit reproducible from the seed.

## What this cannot show

A1 is an assumption. If Â is biased in negative-price hours in a way the allowed inputs do not
reveal, b̂_H and B̂ are biased too. A persisting gap between H and Â would itself be a finding: two
independent public-data methods (this model and Hirth's weather-based fleet model) against H.
