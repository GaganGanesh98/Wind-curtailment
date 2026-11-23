# Post-hoc: audit of Hirth (2026) with the method, results

**Post-hoc.** Pre-registration `docs/22_posthoc_hirth_audit_preregistration.md` (commit `bb0b3e1`)
and its Amendment 1 (commit `e001380`), both committed before any range was computed. The run
started from commit `a158e41` (`python -m src.experiments.hirth_audit --run`, then
`--summarise`) and wrote `artifacts/hirth_audit/claim_cells.csv`, `claim_mapping.csv`,
`claim_ranges.csv` and `claim_verdicts.csv`. Every table below is generated from those files.
ĉ = 1 − G/H throughout; M0 and M1 only drop quarter-hours. The H1b reproduction check against
λ₂ passed on every grid and mask (`tests/test_hirth_audit_compute.py`).

The verdict rule, the classes and the comparison bias are those of docs/22 as amended: not
decidable (width of 0.25 or more), then supported (cross-period: consistent), then outside.
The comparison bias is read on the fine grid at the first allowance at or above H's bias
(`hirth_design` in docs/22). Figure 18 shows the headline ranges.

## Summary

<!-- generated:hirth_counts -->
- Main class, headline, unweighted, at B = 0: supported none; outside H23, H24; not decidable H12.
- Main class, headline, unweighted, at the comparison B: supported H24; outside H23; not decidable H12.
- Contradicted or inconsistent (outside at B = 0.15): none.
- Depends on weighting: none.
- Cross-period claims are left out of these counts (Amendment 1).
<!-- /generated -->

## Main class

Hirth's 2026 claims (January to September 2026 lie inside the Experiment 3 window).

<!-- generated:hirth_results_main -->
| claim | variant | weighting | Hirth | band quarter-hours / event days | range at B = 0 | verdict at B = 0 | range at the comparison B | verdict at the comparison B | B = 0 verdict holds to (V2) | holds to (fine) | depends on weighting |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H12 | headline | unweighted | 69.0 % | 68 / 6 | [0.525, 0.977] | not decidable | [0.508, 0.977] | not decidable | > 0.15 | > 0.06 | no |
| H12 | headline | weighted | 69.0 % | 68 / 6 | [0.527, 0.979] | not decidable | [0.510, 0.979] | not decidable | > 0.15 | > 0.06 | no |
| H12 | M0 | unweighted | 69.0 % | 22 / 2 | [0.488, 1.000] | not decidable | [0.470, 1.000] | not decidable | > 0.15 | > 0.06 | no |
| H12 | M0 | weighted | 69.0 % | 22 / 2 | [0.483, 1.000] | not decidable | [0.465, 1.000] | not decidable | > 0.15 | > 0.06 | no |
| H12 | M1 | unweighted | 69.0 % | 31 / 3 | [0.545, 0.995] | not decidable | [0.529, 0.995] | not decidable | > 0.15 | > 0.06 | no |
| H12 | M1 | weighted | 69.0 % | 31 / 3 | [0.552, 0.996] | not decidable | [0.536, 0.997] | not decidable | > 0.15 | > 0.06 | no |
| H23 | headline | unweighted | 25.0 % | 2052 / 97 | [0.309, 0.403] | outside | [0.284, 0.423] | outside | 0.08 | > 0.06 | no |
| H23 | headline | weighted | 25.0 % | 2052 / 97 | [0.294, 0.392] | outside | [0.269, 0.413] | outside | 0.06 | > 0.06 | no |
| H23 | M0 | unweighted | 25.0 % | 746 / 51 | [0.328, 0.433] | outside | [0.304, 0.452] | outside | 0.11 | > 0.06 | no |
| H23 | M0 | weighted | 25.0 % | 746 / 51 | [0.319, 0.431] | outside | [0.294, 0.451] | outside | 0.09 | > 0.06 | no |
| H23 | M1 | unweighted | 25.0 % | 947 / 57 | [0.336, 0.430] | outside | [0.312, 0.450] | outside | 0.12 | > 0.06 | no |
| H23 | M1 | weighted | 25.0 % | 947 / 57 | [0.322, 0.425] | outside | [0.298, 0.445] | outside | 0.1 | > 0.06 | no |
| H24 | headline | unweighted | 37.0 % | 2052 / 97 | [0.384, 0.501] | outside | [0.354, 0.526] | supported | 0.01 | 0.015 | no |
| H24 | headline | weighted | 37.0 % | 2052 / 97 | [0.381, 0.507] | outside | [0.348, 0.534] | supported | 0.01 | 0.01 | no |
| H24 | M0 | unweighted | 37.0 % | 746 / 51 | [0.384, 0.506] | outside | [0.356, 0.529] | supported | 0.01 | 0.0175 | no |
| H24 | M0 | weighted | 37.0 % | 746 / 51 | [0.392, 0.531] | outside | [0.362, 0.554] | supported | 0.02 | 0.025 | no |
| H24 | M1 | unweighted | 37.0 % | 947 / 57 | [0.400, 0.512] | outside | [0.371, 0.535] | outside | 0.03 | 0.035 | no |
| H24 | M1 | weighted | 37.0 % | 947 / 57 | [0.407, 0.538] | outside | [0.377, 0.563] | outside | 0.04 | 0.0425 | no |
<!-- /generated -->

Plain numbers, no verdict:

<!-- generated:hirth_results_plain -->
| claim | class | variant | weighting | Hirth | method's band mean of e | method − Hirth | event days |
|---|---|---|---|---|---|---|---|
| H2 | cross-period | headline | unweighted | 64.0 % | 0.805 | +0.165 | 97 |
| H2 | cross-period | headline | weighted | 64.0 % | 0.774 | +0.134 | 97 |
| H2 | cross-period | M0 | unweighted | 64.0 % | 0.855 | +0.215 | 51 |
| H2 | cross-period | M0 | weighted | 64.0 % | 0.813 | +0.173 | 51 |
| H2 | cross-period | M1 | unweighted | 64.0 % | 0.840 | +0.200 | 57 |
| H2 | cross-period | M1 | weighted | 64.0 % | 0.791 | +0.151 | 57 |
| H22 | main | headline | unweighted | 68.0 % | 0.805 | +0.125 | 97 |
| H22 | main | headline | weighted | 68.0 % | 0.774 | +0.094 | 97 |
| H22 | main | M0 | unweighted | 68.0 % | 0.855 | +0.175 | 51 |
| H22 | main | M0 | weighted | 68.0 % | 0.813 | +0.133 | 51 |
| H22 | main | M1 | unweighted | 68.0 % | 0.840 | +0.160 | 57 |
| H22 | main | M1 | weighted | 68.0 % | 0.791 | +0.111 | 57 |
<!-- /generated -->

## Cross-period class

Hirth's 2025 claims and the pooled claims whose hours lie mostly before the window
(Amendment 1). Reported as ranges; not counted in the summary.

<!-- generated:hirth_results_cross -->
| claim | variant | weighting | Hirth | band quarter-hours / event days | range at B = 0 | verdict at B = 0 | range at the comparison B | verdict at the comparison B | B = 0 verdict holds to (V2) | holds to (fine) | depends on weighting |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H1a | headline | unweighted | 50.0 % | 149 / 12 | [0.525, 0.860] | not decidable | [0.508, 0.864] | not decidable | > 0.15 | > 0.06 | no |
| H1a | headline | weighted | 50.0 % | 149 / 12 | [0.518, 0.862] | not decidable | [0.501, 0.866] | not decidable | > 0.15 | > 0.06 | no |
| H1a | M0 | unweighted | 50.0 % | 41 / 5 | [0.492, 0.909] | not decidable | [0.474, 0.912] | not decidable | > 0.15 | > 0.06 | no |
| H1a | M0 | weighted | 50.0 % | 41 / 5 | [0.494, 0.908] | not decidable | [0.476, 0.911] | not decidable | > 0.15 | > 0.06 | no |
| H1a | M1 | unweighted | 50.0 % | 60 / 6 | [0.549, 0.907] | not decidable | [0.533, 0.910] | not decidable | > 0.15 | > 0.06 | no |
| H1a | M1 | weighted | 50.0 % | 60 / 6 | [0.553, 0.913] | not decidable | [0.537, 0.915] | not decidable | > 0.15 | > 0.06 | no |
| H1b | headline | unweighted | 50.0 % | 149 / 12 | [0.525, 0.860] | not decidable | [0.508, 0.864] | not decidable | > 0.15 | > 0.06 | no |
| H1b | headline | weighted | 50.0 % | 149 / 12 | [0.518, 0.862] | not decidable | [0.501, 0.866] | not decidable | > 0.15 | > 0.06 | no |
| H1b | M0 | unweighted | 50.0 % | 41 / 5 | [0.492, 0.909] | not decidable | [0.474, 0.912] | not decidable | > 0.15 | > 0.06 | no |
| H1b | M0 | weighted | 50.0 % | 41 / 5 | [0.494, 0.908] | not decidable | [0.476, 0.911] | not decidable | > 0.15 | > 0.06 | no |
| H1b | M1 | unweighted | 50.0 % | 60 / 6 | [0.549, 0.907] | not decidable | [0.533, 0.910] | not decidable | > 0.15 | > 0.06 | no |
| H1b | M1 | weighted | 50.0 % | 60 / 6 | [0.553, 0.913] | not decidable | [0.537, 0.915] | not decidable | > 0.15 | > 0.06 | no |
| H3 | headline | unweighted | 27.0 % | 2052 / 97 | [0.384, 0.501] | outside | [0.354, 0.526] | outside | 0.08 | > 0.06 | no |
| H3 | headline | weighted | 27.0 % | 2052 / 97 | [0.381, 0.507] | outside | [0.348, 0.534] | outside | 0.07 | > 0.06 | no |
| H3 | M0 | unweighted | 27.0 % | 746 / 51 | [0.384, 0.506] | outside | [0.356, 0.529] | outside | 0.08 | > 0.06 | no |
| H3 | M0 | weighted | 27.0 % | 746 / 51 | [0.392, 0.531] | outside | [0.362, 0.554] | outside | 0.07 | > 0.06 | no |
| H3 | M1 | unweighted | 27.0 % | 947 / 57 | [0.400, 0.512] | outside | [0.371, 0.535] | outside | 0.09 | > 0.06 | no |
| H3 | M1 | weighted | 27.0 % | 947 / 57 | [0.407, 0.538] | outside | [0.377, 0.563] | outside | 0.07 | > 0.06 | no |
| H4 | headline | unweighted | 17.0 % | 2052 / 97 | [0.309, 0.403] | outside | [0.284, 0.423] | outside | 0.12 | > 0.06 | no |
| H4 | headline | weighted | 17.0 % | 2052 / 97 | [0.294, 0.392] | outside | [0.269, 0.413] | outside | 0.11 | > 0.06 | no |
| H4 | M0 | unweighted | 17.0 % | 746 / 51 | [0.328, 0.433] | outside | [0.304, 0.452] | outside | 0.11 | > 0.06 | no |
| H4 | M0 | weighted | 17.0 % | 746 / 51 | [0.319, 0.431] | outside | [0.294, 0.451] | outside | 0.11 | > 0.06 | no |
| H4 | M1 | unweighted | 17.0 % | 947 / 57 | [0.336, 0.430] | outside | [0.312, 0.450] | outside | 0.12 | > 0.06 | no |
| H4 | M1 | weighted | 17.0 % | 947 / 57 | [0.322, 0.425] | outside | [0.298, 0.445] | outside | 0.11 | > 0.06 | no |
| H5 | headline | unweighted | 57.0 % | 68 / 6 | [0.525, 0.977] | not decidable | [0.508, 0.977] | not decidable | > 0.15 | > 0.06 | no |
| H5 | headline | weighted | 57.0 % | 68 / 6 | [0.527, 0.979] | not decidable | [0.510, 0.979] | not decidable | > 0.15 | > 0.06 | no |
| H5 | M0 | unweighted | 57.0 % | 22 / 2 | [0.488, 1.000] | not decidable | [0.470, 1.000] | not decidable | > 0.15 | > 0.06 | no |
| H5 | M0 | weighted | 57.0 % | 22 / 2 | [0.483, 1.000] | not decidable | [0.465, 1.000] | not decidable | > 0.15 | > 0.06 | no |
| H5 | M1 | unweighted | 57.0 % | 31 / 3 | [0.545, 0.995] | not decidable | [0.529, 0.995] | not decidable | > 0.15 | > 0.06 | no |
| H5 | M1 | weighted | 57.0 % | 31 / 3 | [0.552, 0.996] | not decidable | [0.536, 0.997] | not decidable | > 0.15 | > 0.06 | no |
| H6 | headline | unweighted | 51.0 % | 81 / 12 | [0.464, 0.846] | not decidable | [0.445, 0.849] | not decidable | > 0.15 | > 0.06 | no |
| H6 | headline | weighted | 51.0 % | 81 / 12 | [0.466, 0.855] | not decidable | [0.447, 0.858] | not decidable | > 0.15 | > 0.06 | no |
| H6 | M0 | unweighted | 51.0 % | 19 / 5 | [0.448, 0.909] | not decidable | [0.429, 0.911] | not decidable | > 0.15 | > 0.06 | no |
| H6 | M0 | weighted | 51.0 % | 19 / 5 | [0.452, 0.918] | not decidable | [0.432, 0.920] | not decidable | > 0.15 | > 0.06 | no |
| H6 | M1 | unweighted | 51.0 % | 29 / 6 | [0.498, 0.905] | not decidable | [0.479, 0.908] | not decidable | > 0.15 | > 0.06 | no |
| H6 | M1 | weighted | 51.0 % | 29 / 6 | [0.501, 0.917] | not decidable | [0.484, 0.919] | not decidable | > 0.15 | > 0.06 | no |
| H7 | headline | unweighted | 35.0 % | 148 / 20 | [0.374, 0.663] | not decidable | [0.351, 0.675] | not decidable | > 0.15 | > 0.06 | no |
| H7 | headline | weighted | 35.0 % | 148 / 20 | [0.381, 0.688] | not decidable | [0.358, 0.699] | not decidable | > 0.15 | > 0.06 | no |
| H7 | M0 | unweighted | 35.0 % | 58 / 9 | [0.401, 0.733] | not decidable | [0.380, 0.741] | not decidable | > 0.15 | > 0.06 | no |
| H7 | M0 | weighted | 35.0 % | 58 / 9 | [0.399, 0.740] | not decidable | [0.377, 0.748] | not decidable | > 0.15 | > 0.06 | no |
| H7 | M1 | unweighted | 35.0 % | 68 / 11 | [0.426, 0.731] | not decidable | [0.406, 0.741] | not decidable | > 0.15 | > 0.06 | no |
| H7 | M1 | weighted | 35.0 % | 68 / 11 | [0.435, 0.759] | not decidable | [0.415, 0.767] | not decidable | > 0.15 | > 0.06 | no |
| H8 | headline | unweighted | 22.0 % | 139 / 28 | [0.308, 0.567] | not decidable | [0.283, 0.581] | not decidable | > 0.15 | > 0.06 | no |
| H8 | headline | weighted | 22.0 % | 139 / 28 | [0.314, 0.590] | not decidable | [0.289, 0.604] | not decidable | > 0.15 | > 0.06 | no |
| H8 | M0 | unweighted | 22.0 % | 50 / 13 | [0.323, 0.610] | not decidable | [0.299, 0.623] | not decidable | > 0.15 | > 0.06 | no |
| H8 | M0 | weighted | 22.0 % | 50 / 13 | [0.319, 0.628] | not decidable | [0.295, 0.641] | not decidable | > 0.15 | > 0.06 | no |
| H8 | M1 | unweighted | 22.0 % | 78 / 16 | [0.356, 0.617] | not decidable | [0.333, 0.630] | not decidable | > 0.15 | > 0.06 | no |
| H8 | M1 | weighted | 22.0 % | 78 / 16 | [0.355, 0.660] | not decidable | [0.332, 0.672] | not decidable | > 0.15 | > 0.06 | no |
| H9 | headline | unweighted | 15.0 % | 1616 / 97 | [0.253, 0.357] | outside | [0.226, 0.379] | outside | 0.1 | > 0.06 | no |
| H9 | headline | weighted | 15.0 % | 1616 / 97 | [0.242, 0.350] | outside | [0.215, 0.373] | outside | 0.1 | > 0.06 | no |
| H9 | M0 | unweighted | 15.0 % | 597 / 51 | [0.278, 0.393] | outside | [0.252, 0.414] | outside | 0.1 | > 0.06 | no |
| H9 | M0 | weighted | 15.0 % | 597 / 51 | [0.262, 0.385] | outside | [0.236, 0.406] | outside | 0.09 | > 0.06 | no |
| H9 | M1 | unweighted | 15.0 % | 741 / 57 | [0.275, 0.380] | outside | [0.249, 0.402] | outside | 0.1 | > 0.06 | no |
| H9 | M1 | weighted | 15.0 % | 741 / 57 | [0.254, 0.369] | outside | [0.227, 0.390] | outside | 0.09 | > 0.06 | no |
<!-- /generated -->

## Notes

<!-- generated:hirth_exposure_line -->
- **Why H1a and H1b share a range.** Mean exposed share e for price ≤ −50, at b = 0: headline 1.0000 (weighted 1.0000, minimum 1.0000, 149 quarter-hours); M0 1.0000 (weighted 1.0000, minimum 1.0000, 41 quarter-hours); M1 1.0000 (weighted 1.0000, minimum 1.0000, 60 quarter-hours) (`exposure_check.csv`). e is 1 in every such quarter-hour, so the response functional equals the curtailment functional and H1a and H1b share their ranges by construction.
<!-- /generated -->

<!-- generated:hirth_masked_days -->
- **Event days under the masks.** The counts-only rule (fewer than 20 event days) was applied at arm level, as pre-registered in docs/11: M0 keeps 51 event days and M1 57, so neither arm is counts only and every masked range above is reported as a range. Band by band, several masked ranges rest on fewer than 20 event days (2 to 16, M0 and M1 together): H5 2 to 3, H12 2 to 3, H1a 5 to 6, H1b 5 to 6, H6 5 to 6; and H7 9 to 11, H8 13 to 16. The per-band counts are in the tables above. No verdict or rule is changed.
<!-- /generated -->

## Post-hoc, not pre-registered: H23 against H24

Added after the verdicts were known, as a factual comparison only; it changes no verdict and no
rule. Hirth's curtailment rate is his exposure rate times his response rate. The rows below
multiply the method's band mean of e for price below 0 (the H22 row) by Hirth's response rate
for 2026 (H24) and place the product against the method's H23 range.

<!-- generated:hirth_product -->
| variant | weighting | method's e (H22 row) | e × Hirth's response 0.37 | H23 range at B = 0 | product vs range | H23 range at the comparison B | product vs range |
|---|---|---|---|---|---|---|---|
| headline | unweighted | 0.805 | 0.298 | [0.309, 0.403] | below | [0.284, 0.423] | inside |
| headline | weighted | 0.774 | 0.286 | [0.294, 0.392] | below | [0.269, 0.413] | inside |
| M0 | unweighted | 0.855 | 0.316 | [0.328, 0.433] | below | [0.304, 0.452] | inside |
| M0 | weighted | 0.813 | 0.301 | [0.319, 0.431] | below | [0.294, 0.451] | inside |
| M1 | unweighted | 0.840 | 0.311 | [0.336, 0.430] | below | [0.312, 0.450] | below |
| M1 | weighted | 0.791 | 0.293 | [0.322, 0.425] | below | [0.298, 0.445] | below |
<!-- /generated -->

<!-- generated:hirth_product_note -->
- For reference, Hirth's own exposure rate times his response rate for 2026, 0.68 × 0.37 = 0.252, against his curtailment rate 0.25 (H22, H24, H23; his Table 4 identity).
<!-- /generated -->

## Comparability gaps

Unchanged from docs/22 and not corrected here: technology and area, period, grid curtailment
(counted in ĉ; M0 and M1 are the check), hourly against quarter-hour prices, weighting,
available power and exposure. The masked variants carry the open redispatch unit check
(docs/22, `hirth_design`).
