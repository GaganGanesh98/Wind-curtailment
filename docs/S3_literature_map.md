# Literature folder map (Phase S3, 15 Nov 2026)

`Literature Review/` and `02_literature/` were merged into `literature/` on 15 Nov 2026.
`literature/` holds copyrighted PDFs. It is excluded from git through `.git/info/exclude` and is
never committed. It reaches the supervisor only through `tools/export_share.sh`.

Filenames follow `Author_Year_Short-Title[_version].pdf`. Author, year and title come from each
PDF's first page. There are three exceptions:
- The Wang & Wang SSRN PDFs carry no author names (anonymised); the authors are taken from `docs/02_evidence_base.md`.
- The VGB Windstudie PDF is encrypted, so its text could not be read; it keeps its original title words.
- `hirth_fig12_p17_extract.png` keeps its name.

## Old path → new path

| Old path | New path |
|---|---|
| `Literature Review/2609.10053v2.pdf` | `literature/01_closest_work/Hirth_2026_Curtail-at-negative-prices_arXiv-v2.pdf` |
| `02_literature/closest_work/2609.10053v1.pdf` | `literature/01_closest_work/Hirth_2026_Curtail-at-negative-prices_arXiv-v1.pdf` |
| `02_literature/closest_work/hirth_fig12_p17_extract.png` | `literature/01_closest_work/hirth_fig12_p17_extract.png` |
| `Literature Review/wp_25_1124.pdf` | `literature/01_closest_work/VanSteenberghe-Ovaere_2025_Market-inefficiencies-offshore-wind-CfDs_Ghent-WP.pdf` |
| `02_literature/closest_work/ssrn-7025858.pdf` | `literature/01_closest_work/Wang-Wang_2026_Censored-available-power-data-bias-dispatch_SSRN-WP.pdf` |
| `02_literature/closest_work/ssrn-7195331.pdf` | `literature/01_closest_work/Wang-Wang_2026_Learning-deliverable-capability-from-censored-SCADA_SSRN-WP.pdf` |
| `Literature Review/wes-2026-188.pdf` | `literature/01_closest_work/Grafe-et-al_2026_Wind-farm-value-revenue-triggered-curtailment_WES-preprint.pdf` |
| `Literature Review/Modeling_Censored_Mobility_Demand_Through_Censored_Quantile_Regression_Neural_Networks.pdf` | `literature/02_censored_learning_methods/Huttel-et-al_2022_Censored-mobility-demand-CQRNN.pdf` |
| `Literature Review/1-s2.0-S0968090X2300178X-main.pdf` | `literature/02_censored_learning_methods/Huttel-Rodrigues-Pereira_2023_Mind-the-gap-censored-EV-charging-demand.pdf` |
| `Literature Review/NeurIPS-2022-censored-quantile-regression-neural-networks-for-distribution-free-survival-analysis-Paper-Conference.pdf` | `literature/02_censored_learning_methods/Pearce-et-al_2022_Censored-quantile-regression-NN-survival.pdf` |
| `Literature Review/3600270.3600811_supp.pdf` | `literature/02_censored_learning_methods/Pearce-et-al_2022_Censored-quantile-regression-NN-survival_supplement.pdf` |
| `Literature Review/2007.07056v2.pdf` | `literature/02_censored_learning_methods/Jia-Jeong_2021_DeepQuantreg-quantile-regression-right-censoring_arXiv-v2.pdf` |
| `Literature Review/runje23a.pdf` | `literature/02_censored_learning_methods/Runje-Shankaranarayana_2023_Constrained-monotonic-neural-networks.pdf` |
| `Literature Review/Gneiting2007jasa.pdf` | `literature/02_censored_learning_methods/Gneiting-Raftery_2007_Strictly-proper-scoring-rules.pdf` |
| `Literature Review/1-s2.0-S0957417425014940-main (1).pdf` | `literature/03_wind_forecasting/Jorgensen-et-al_2025_Sequential-error-correction-probabilistic-wind-forecasts.pdf` |
| `Literature Review/2203.08252v2.pdf` | `literature/03_wind_forecasting/Wen-et-al_2022_Wind-forecasting-with-missing-values-FCS_arXiv-v2.pdf` |
| `02_literature/closest_work/2602.13010v2.pdf` | `literature/03_wind_forecasting/Bruninx-et-al_2026_Probabilistic-wind-forecasting-tree-ML-weather-ensembles_arXiv-v2.pdf` |
| `Literature Review/1-s2.0-S0360544216311811-main.pdf` | `literature/03_wind_forecasting/Staffell-Pfenninger_2016_Bias-corrected-reanalysis-wind-power.pdf` |
| `Literature Review/ssrn-3643762.pdf` | `literature/04_energy_markets_and_curtailment/Frondel-Kaeding-Sommer_2020_Market-premia-renewables-Germany_SSRN-WP.pdf` |
| `Literature Review/3679240.3734627.pdf` | `literature/04_energy_markets_and_curtailment/Maji-et-al_2025_Node-level-curtailment-of-renewables.pdf` |
| `Literature Review/2610.08337v1.pdf` | `literature/04_energy_markets_and_curtailment/Shamim-Shamim_2026_ML-German-redispatch-forecasting_arXiv-v1.pdf` |
| `Literature Review/1-s2.0-S0306261921004529-main.pdf` | `literature/04_energy_markets_and_curtailment/Lago-et-al_2021_Forecasting-day-ahead-electricity-prices-review.pdf` |
| `02_literature/background/2503.14860v1.pdf` | `literature/05_background/Robinson-et-al_2025_Global-Renewables-Watch_arXiv-v1.pdf` |
| `02_literature/background/VGB-Windstudie-2017-Teil-1-EN.pdf` | `literature/05_background/VGB_2017_Windstudie-Teil-1-EN.pdf` |
| `nodal-curtailment-analysis-main/` | `literature/06_datasets_and_code/nodal-curtailment-analysis-main/` (internal names kept) |

Duplicates, off-topic files and citation exports went to `~/msc-thesis-guidance/` (see its README).

## References left as written

- `docs/Q0c_preregistration.md` line 14 cites `Literature Review/2609.10053v2.pdf`. It is a
  pre-registration, so its text is not changed. That file is now
  `literature/01_closest_work/Hirth_2026_Curtail-at-negative-prices_arXiv-v2.pdf`.
  Its sha256 still begins `9bfd90e7ad8c8739`, as recorded there (checked 15 Nov 2026).
- `docs/literature/` and `docs/legal/` hold git-tracked PDFs that `src/` cites by path; they
  are not touched. `docs/literature/hirth_2026_2609.10053v1.pdf` is byte-identical to the
  Hirth v1 file above.
- No `literature_table.csv` existed, so none was moved. The literature table is `docs/07_literature_table.md`.
