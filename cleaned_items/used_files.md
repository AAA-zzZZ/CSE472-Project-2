# Files Used in Model Creation and Fitting

This list covers the **reduced PRISM refits**: the GLM and LightGBM hurdle models on 12 inputs
plus calendar month, and state in the Midwest run. It was traced on 2026-11-08 from the file
reads and writes in each script, and reflects commit `ff53ea1`. It is a list only, and no files
were moved or deleted for it.

> **Update 2026-11-09:** `yana_workspace/temp_merge_panel.py` is deleted. `merge_panel.py` now
> defaults to the PRISM 2000–2009 climate and joins GHSL through `data/clean/ghsl_county_year.csv`
> from `ghsl_features.py`; the panel's 55 columns are identical. `openfema_features.py` adds the
> OpenFEMA tables (optional inputs). `state_model.py` was added and deleted the same session. The
> tables below are updated to match; see the "Latest session" section of `../HANDOFF.md`.

## What changed for the PRISM refit

| File or folder | Change |
|---|---|
| `model_panel.csv`, `panel_county_month.csv` | **Rebuilt on PRISM.** The NOAA versions are `*_noaa.csv` |
| `data/gee_prism_midwest/`, `data/gee_ghsl/` | **Renamed** from `data/gee_midwest/` and `data/gee_ghls/` |
| `reduced_benchmark.py` | **New.** Fits and scores the reduced models. Reads `model_panel.csv` by default |
| `yana_workspace/temp_merge_panel.py` | **New and temporary** (deleted 2026-11-09: `merge_panel.py` + `ghsl_features.py` replace it) |
| `out/prism_midwest/` | **New.** PRISM rain indices and 2000–2009 thresholds |
| `results/midwest_prism/`, `results/missouri_prism/` | **New.** Refit results |
| `results/hurdle_scores.csv`, `results/model_comparison.csv` | **Rewritten** on the PRISM panel |
| `hurdle_model.py`, `model_comparison.py` | **Edited.** Both skip January 2000 |
| `results/reduced_noaa_*` | **Deleted.** Replaced by the PRISM results |

## Quick view

| Status | Meaning |
|---|---|
| **Used** | The refits depend on this file |
| **Check only** | Read during the build, but no value reaches the model inputs |
| **NOAA cross-check** | Kept to compare against PRISM, not used by the PRISM refits |
| **Reruns** | Older scripts rerun on the PRISM panel, outside the reduced refits |
| **Waiting** | Placeholder for data not collected yet |
| **Not used** | Plays no part in these refits |

## Used

Listed in pipeline order. The first column is the step's script. To reproduce the panel,
run them from top to bottom.

### 1. Outcome (flood loss)

| Script | Reads | Writes |
|---|---|---|
| `data_clean.py` | `direct_loss_aggregated_output_32423.csv` | `loss_cleaned_monthly.csv` |
| `housing_features.py` | `nhgis0001_csv/nhgis0001_ts_nominal_county.csv` | `housing_county_year.csv` |
| `build_monthly_panel.py` | `loss_cleaned_monthly.csv`, `housing_county_year.csv` | `model_data_monthly_panel.csv` |

`merge_panel.py` takes the outcome from `model_data_monthly_panel.csv`. That file's
housing columns are not inputs to the reduced refits, but the two housing steps above are
still needed to build it.

### 2. Rain and frost (PRISM)

| Script | Reads | Writes |
|---|---|---|
| `prism_export.py` (`prism` command) | Earth Engine | `data/gee_prism_midwest/` (24 files, 2000–2023) |
| `w_indices.py` (baseline 2000–2009) | `data/gee_prism_midwest/` | `out/prism_midwest/w_county_month.csv`, `out/prism_midwest/w_county_thresholds.csv` |

### 3. Soil, snow, land cover and terrain (Earth Engine)

| Script | Reads | Writes |
|---|---|---|
| `prism_export.py` (`era5`, `nlcd` and `terrain` commands) | Earth Engine | `data/gee_era5/` (74 files, 1950–2023), `data/gee_nlcd/` (25 files, 1999–2023), `data/gee_terrain/terrain_county.csv` |
| `build_panel.py` | The three folders above, `out/prism_midwest/w_county_month.csv` | `panel_county_month.csv` |

### 4. Exposure (GHSL)

| Script | Reads | Writes |
|---|---|---|
| `yana_workspace/ghsl_export.py` | Earth Engine | `data/gee_ghsl/` (7 files, 1995–2025) |
| `ghsl_features.py` | `data/gee_ghsl/` | `data/clean/ghsl_county_year.csv` (5-year images interpolated to every year) |

`merge_panel.py` turns `built_m2` into `log_built_surface`.

### 5. Final panel and models

| Script | Reads | Writes |
|---|---|---|
| `openfema_features.py` (optional) | `data/openfema/raw/` (curl downloads) | `data/clean/nfip_policies_county_year.csv`, `data/clean/hma_county_year.csv` |
| `merge_panel.py` | `panel_county_month.csv`, `model_data_monthly_panel.csv`, `out/prism_midwest/w_county_thresholds.csv` (default), `data/clean/*` | **`model_panel.csv`**, the PRISM panel |
| **`reduced_benchmark.py`** | `model_panel.csv` | `results/midwest_prism/`, `results/missouri_prism/`, `results/missouri_pooled/` (`--score-state MO`), `results/*_prism_buyouts/` (each with `scores.csv`, `glm_coefs.csv`, `log.txt`) |
| `recalibrate.py` | `model_panel.csv` | `results/recalibration_midwest/`, `results/recalibration_missouri/` |

`yana_workspace/reduced_variables.md` defines the variable set, but it still describes NOAA
sources, a 1951–1999 baseline and `log_housing_units`. The refits use PRISM, a 2000–2009
baseline and `log_built_surface`.

## Check only

| File | Role |
|---|---|
| `loss_output_year_county.csv` | `data_clean.py` compares yearly totals against it |
| `data/clean/census_county_year.csv` (from `census_features.py` and `nhgis0001_csv/nhgis0001_csv/`) | `merge_panel.py` joins it, but none of its columns are inputs to the reduced refits. It will supply the housing units for `nfip_policies_per_hu` |

## NOAA cross-check

| File or folder | Note |
|---|---|
| `model_panel_noaa.csv`, `panel_county_month_noaa.csv` | Frozen NOAA panels |
| `data/nclimgrid_midwest/`, `prep_nclimgrid.py` | NOAA daily rain and frost |
| `out/w_county_month.csv`, `out/w_county_thresholds.csv` | NOAA rain indices and 1951–1999 baseline |
| `merge_panel.py --thresholds out/w_county_thresholds.csv` | Builds the NOAA panel (the default is now PRISM) |

## Reruns

These two older scripts were rerun on the PRISM panel. They use their own larger input sets
and `log_housing_units`, so they do not match the reduced refits. Both now skip January
2000, because PRISM has no earlier month.

| Script | Writes |
|---|---|
| `hurdle_model.py` (17-input GLM) | `results/hurdle_scores.csv` |
| `model_comparison.py` (39 inputs; GLM, random forest, LightGBM, Tweedie) | `results/model_comparison.csv` |

## Waiting

| File or folder | Note |
|---|---|
| `data/openfema/` | Collected 2026-11-09 (optional inputs; buyouts added nothing, NFIP starts in 2009); see the README there |

## Not used

| File or folder | Note |
|---|---|
| `maps.py`, `maps/` | Maps only |
| `data/counties_midwest.geojson` | Maps, plus the one-off spatial test in `HANDOFF4.md`. Not read by the refits |
| `yana_workspace/build_county_panel.py`, `neighbour_model.py`, `prism_county_export.py`, `ghsl_county_export.py` | Earlier 5-county Ohio design |
| `yana_workspace/gee_exposure_app.js`, `yana_workspace/gee_app/` | Earth Engine apps (display only). `gee_exposure_app.js` was rewritten for the 12 states and reads `mo_flood_app_table.csv` |
| `yana_workspace/data/`, `yana_workspace/results/` | Outputs of that 5-county design |
| `data/gee_prism39167/`, `data/gee_ghsl39167/`, `out/prism_39167/` | Single-county and 5-county PRISM and GHSL files |
| `yana_workspace/flood_model_variable_tree.*` | Diagram of the variables |
| `docs/`, `HANDOFF.md`, `yana_workspace/HANDOFF2.md`, `yana_workspace/HANDOFF3.md`, `yana_workspace/HANDOFF4.md`, `SHELDUS_Data_Documentation.pdf`, `Data_Collection_and_Panel_Dataset (1).docx` | Documentation |
