# Handoff 4: PRISM Refit, Remaining Limits and Data Needs (CSE 472, Project 2)

Read this after `HANDOFF.md`, `HANDOFF2.md` and `HANDOFF3.md`. It covers the session of
2026-11-08 on branch `enci-dev`. The refit is committed in `ff53ea1`.

**Status:** the GLM and LightGBM hurdle models are refit on PRISM rain and GHSL exposure, for
the full Midwest and for Missouri. **NFIP flood insurance and buyout data are still being
collected**, so these results do not include them.

Longer write-up, with score definitions: `Project 2/Summary Guides/prism_refit_summary.pdf`
(outside this repository). File list: [../cleaned_items/used_files.md](../cleaned_items/used_files.md).

## What changed from `HANDOFF3.md`

| Item | `HANDOFF3.md` | Now |
|---|---|---|
| Model scope | One state, not named | **Full Midwest and Missouri**, fitted separately |
| Exposure | `log_built_surface` proposed | **`log_built_surface` in the models**, replacing `log_housing_units` |
| Panel build | `merge_panel.py` | `temp_merge_panel.py`, because `merge_panel.py` defaults to the NOAA baseline and does not add GHSL |
| Data folders | `data/gee_prism_midwest/`, `data/gee_ghsl/` planned | Files are now in those folders |
| `model_panel.csv` | NOAA | **PRISM.** NOAA is saved as `model_panel_noaa.csv` |

Design: 12 reduced inputs plus calendar month, and state in the Midwest run. Train on 2000–2016,
test on 2017–2023, rain baseline 2000–2009. Settings are chosen by fitting 2000–2012 and scoring
2013–2016.

## Results

"Top 5%" is the share of loss in the model's top 5% of counties each month, leaving out the
largest month. That is 53 counties in the Midwest and 6 in Missouri. "Pred ÷ actual" is
predicted damage months over actual; 1 is calibrated. MAE is in log10 dollars.

### Full Midwest: 7,611 training and 2,234 test damage months

| Period | Model | ROC-AUC | PR-AUC | Brier skill | Pred ÷ actual | Top 5% | MAE |
|---|---|---|---|---|---|---|---|
| Test 2017–2023 | Baseline | 0.728 | 0.066 | 0.000 | 1.40 | 0.266 | 0.905 |
| | GLM | 0.865 | 0.206 | 0.098 | 1.58 | 0.747 | 0.858 |
| | **LightGBM** | **0.891** | **0.265** | **0.134** | **1.51** | **0.803** | **0.831** |
| Validation 2013–2016 | Baseline | 0.744 | 0.091 | 0.000 | 1.11 | 0.075 | 0.888 |
| | GLM | 0.884 | 0.284 | 0.121 | 1.45 | 0.717 | 0.854 |
| | LightGBM | 0.900 | 0.316 | 0.134 | 1.42 | 0.671 | 0.801 |

### Missouri: 590 training and 174 test damage months

| Period | Model | ROC-AUC | PR-AUC | Brier skill | Pred ÷ actual | Top 5% | MAE |
|---|---|---|---|---|---|---|---|
| Test 2017–2023 | Baseline | 0.748 | 0.066 | 0.000 | 1.40 | 0.124 | 0.966 |
| | GLM | 0.895 | 0.238 | −0.089 | 2.03 | 0.478 | 0.781 |
| | **LightGBM** | **0.902** | **0.281** | **0.068** | **1.56** | **0.449** | **0.761** |
| Validation 2013–2016 | Baseline | 0.633 | 0.050 | 0.000 | 0.69 | 0.119 | 1.001 |
| | GLM | 0.915 | 0.433 | 0.259 | 1.01 | 0.474 | 0.776 |
| | LightGBM | 0.916 | 0.299 | 0.181 | 0.89 | 0.469 | 0.758 |

- **Midwest:** LightGBM beats the GLM by 0.026 test ROC-AUC (95% interval 0.021 to 0.030).
- **Missouri:** the two models are tied on test ROC-AUC (0.007; interval −0.009 to 0.019). The
  GLM's test probabilities are less accurate than the baseline's, and it predicts twice the
  actual damage months.
- **PRISM against NOAA, Midwest LightGBM:** ROC-AUC rose from 0.883 to 0.891 and PR-AUC from
  0.240 to 0.265, but over-prediction worsened from 1.36× to 1.51×. A PRISM run with housing
  units scored about the same as the GHSL run (0.891 and 0.262), so the gain comes from rain.
- **More inputs add little:** the 39-input LightGBM in `model_comparison.py` reaches 0.896.
- **Rain must be known:** with only pre-month inputs, that LightGBM falls to 0.764. All other
  scores assume the month's rain is already known.

## Why the model is limited

| Problem | Evidence (Midwest LightGBM, test years) | Likely cause |
|---|---|---|
| Too many predicted damage months | 1.51× overall and 2.63× in 2021; Iowa 2.54×, Nebraska 2.17× | Less damage recorded after 2016. Iowa fell from 7.9% to 2.5% of months |
| Dollar amounts are poor | R² 0.14. Over $10M is about 77× too low; under $10k is about 16× too high | The largest 1% of damage months hold 65% of the loss and are rare |
| Loss records are imprecise | 42% of damage rows match another county's exact dollars in that state and month | SHELDUS splits multi-county losses equally, and flood amounts can be a "guesstimate" |
| Heavy rain without damage | 22% of months at or above the 10-year rain level had damage | Rain location within the county, and protection, are not measured |
| Missed damage months | The top-ranked group holds 32% of damage months; 14% of below-median-rain damage months are caught | Upstream water is not measured; small losses are close to random |

**The main limit is the loss data, not a missing input.** On the 2013–2016 validation years,
adding county history, recent state reporting or statewide rain did not improve ROC-AUC, which
stayed at 0.895–0.900. Census values helped dollars slightly (MAE 0.80 to 0.785). Knowing which
other counties were damaged that month, which is impossible in practice, raises ROC-AUC only to
0.92.

## Data to collect

| Priority | Data | Target problem | Status |
|---|---|---|---|
| 1 | **NFIP policies** (OpenFEMA) | Protection and exposure; heavy rain without damage | **In progress.** Check coverage before 2009 |
| 2 | **HMA buyouts and elevations** (OpenFEMA) | Adaptation; `wetland_share` is the only adaptation input now | **In progress.** Dataset fields still to confirm |
| 3 | NFIP claims, NOAA Storm Events | Checking the outcome and finding split multi-county losses | Not started. **Never use claims as a model input** |
| 4 | National Structure Inventory, FEMA flood-zone maps | Value of property at risk, for dollar amounts | Not started |
| 5 | USGS streamflow | Upstream river flooding | Not started |
| 6 | National Levee Database | Flood protection | Not started |
| 7 | Rain forecasts | Replacing the known-rain assumption | Not started |

- The census columns are **already in `model_panel.csv`**, so testing them needs no collection.
- Over-prediction needs **state-level recalibration**, not new inputs.
- NFIP and buyouts are wired in, but only tested with fake tables. The table format and commands
  are in [../data/openfema/README.md](../data/openfema/README.md). The step that converts raw
  downloads into county-year tables is not written.

## Would a spatial model help?

**Partly.** It would improve the GLM, but it probably will not beat LightGBM in the Midwest or
fix the main problems. R and R-INLA are not installed, so this is a Python approximation of a
BYM2 model: penalized county effects with neighbour smoothing and no uncertainty intervals.

Errors do cluster. Moran's I on county-average LightGBM errors is 0.35 in both regions
(permutation p < 0.01).

Validation years 2013–2016 only. The county-effect and BYM2-style rows use the best penalty setting
on those same years, so they are optimistic.

| Region | Model | ROC-AUC | PR-AUC | Pred ÷ actual | Top 5% | MAE |
|---|---|---|---|---|---|---|
| Midwest | GLM | 0.884 | 0.284 | 1.45 | 0.717 | 0.854 |
| | GLM + county effects | 0.897 | 0.319 | 1.47 | 0.669 | 0.812 |
| | GLM + BYM2-style | 0.900 | 0.325 | 1.48 | 0.633 | 0.803 |
| | LightGBM | 0.900 | 0.316 | 1.42 | 0.671 | 0.801 |
| | LightGBM + neighbour inputs | 0.900 | 0.313 | 1.41 | 0.592 | 0.798 |
| Missouri | GLM | 0.915 | 0.433 | 1.01 | 0.474 | 0.776 |
| | GLM + county effects | 0.933 | 0.504 | 1.11 | 0.487 | 0.776 |
| | GLM + BYM2-style | 0.934 | 0.506 | 1.13 | 0.492 | 0.775 |
| | LightGBM | 0.916 | 0.299 | 0.89 | 0.469 | 0.758 |
| | LightGBM + neighbour inputs | 0.911 | 0.257 | 0.88 | 0.478 | 0.723 |

- Most of the GLM's gain comes from county effects. Neighbour smoothing adds only 0.001–0.003.
- In the Midwest the spatial GLM only catches up with LightGBM, and its top-5% share falls.
- Missouri is the most promising case: the spatial GLM's ROC-AUC and PR-AUC beat LightGBM's.
- Calibration does not improve, because fixed county effects cannot follow a change over time.
- The main reason to run it is **uncertainty intervals and maps**, which LightGBM does not give.

The neighbour map joins counties within 1 km of each other, averaging 5.9 neighbours per county.

## Files added or changed

| File | What it is |
|---|---|
| [../reduced_benchmark.py](../reduced_benchmark.py) | New: fits and scores the baseline, GLM and LightGBM hurdle. `--state`, `--exposure`, `--openfema` |
| [temp_merge_panel.py](temp_merge_panel.py) | New and temporary: PRISM baseline and the GHSL input. Replace with a permanent merge step |
| [../results/midwest_prism/](../results/midwest_prism/), [../results/missouri_prism/](../results/missouri_prism/) | `scores.csv`, `glm_coefs.csv`, `log.txt` |
| `../results/hurdle_scores.csv`, `../results/model_comparison.csv` | Rewritten on the PRISM panel. They keep `log_housing_units` and larger input sets |
| `../out/prism_midwest/` | PRISM rain indices and 2000–2009 thresholds |
| `../hurdle_model.py`, `../model_comparison.py` | Now skip January 2000, because PRISM has no earlier month |
| `../model_panel_noaa.csv`, `../panel_county_month_noaa.csv` | Git-ignored NOAA panels, kept as a cross-check |

## Rebuild commands

Run from the repository root. The main Python environment needs
`pip install lightgbm scikit-learn`.

```powershell
python w_indices.py --input data/gee_prism_midwest --out-dir out/prism_midwest/ --base-start 2000 --base-end 2009 --model-start 2000 --model-end 2023
python build_panel.py --era5 data/gee_era5 --nlcd data/gee_nlcd --terrain data/gee_terrain --w out/prism_midwest/w_county_month.csv --out panel_county_month.csv
python yana_workspace/temp_merge_panel.py --thresholds out/prism_midwest/w_county_thresholds.csv --ghsl data/gee_ghsl --out model_panel.csv
python reduced_benchmark.py --out-dir results/midwest_prism
python reduced_benchmark.py --state MO --out-dir results/missouri_prism
python hurdle_model.py
python model_comparison.py
```

## Caveats

- **The test years have been scored several times.** Make design choices on 2013–2016.
- **Some numbers cannot be rerun from the repository.** The error breakdowns, added-input tests,
  PRISM-with-housing run and spatial test were one-off runs and were not saved.
- **Limited uncertainty.** Intervals resample counties, not years, and each main LightGBM model
  used one seed. Across three seeds, Midwest validation top-5% ranged from 0.67 to 0.70.
- **Missouri is small.** 174 test damage months, and the LightGBM settings were not tuned for it.
- **Baseline overlap.** 2000–2009 overlaps training. The causal step must start in 2010.
- **GHSL timing.** Values are interpolated, so a year can draw on the next 5-year image. Confirm
  whether the 2025 image is observed or projected, because it feeds the 2022–2023 test years.
- **`spi2_prev` is blank every February**, because the January 2-month total has 9 baseline
  years. Only the tree models in `model_comparison.py` use it.
- **`reduced_variables.md` is out of date.** It still describes NOAA, a 1951–1999 baseline and
  housing units.

## Next steps

1. Finish NFIP and buyouts, write the conversion step, and refit both regions.
2. Add state-level recalibration, then check over-prediction on the validation years.
3. Test the census columns in `reduced_benchmark.py`.
4. Confirm with the mentor: Midwest plus Missouri, training on 2000–2016, and the overlapping
   baseline.
5. Install R and R-INLA, then run BYM2, starting with Missouri.
6. Run Equation 4 on 2010–2023.
7. Replace `temp_merge_panel.py` with a permanent merge step.

## Working notes

- Project ID: `flood-513221`.
- `merge_panel.py` still defaults to NOAA thresholds. Use `temp_merge_panel.py` for PRISM.
- `data/clean/` tables are joined only if the file exists, with a one-year lag.
- Commit only when asked.
