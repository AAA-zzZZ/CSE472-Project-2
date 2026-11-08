# Files Used in Model Creation and Fitting

This list covers the **reduced PRISM refits**: the GLM and LightGBM hurdle models on 12 inputs
plus calendar month, and state in the Midwest run. It was traced on 2026-11-08 from the file
reads and writes in each script. It is a list only, and no files were moved or deleted for it.

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

`temp_merge_panel.py` takes the outcome from `model_data_monthly_panel.csv`. That file's
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

`yana_workspace/temp_merge_panel.py` turns these files into `log_built_surface`.

### 5. Final panel and models

| Script | Reads | Writes |
|---|---|---|
| `yana_workspace/temp_merge_panel.py` | `panel_county_month.csv`, `model_data_monthly_panel.csv`, `out/prism_midwest/w_county_thresholds.csv`, `data/gee_ghsl/` | **`model_panel.csv`**, the PRISM panel |
| **`reduced_benchmark.py`** | `model_panel.csv` | `results/midwest_prism/`, `results/missouri_prism/` (each with `scores.csv`, `glm_coefs.csv`, `log.txt`) |

`yana_workspace/reduced_variables.md` defines the variable set, but it still describes NOAA
sources, a 1951–1999 baseline and `log_housing_units`. The refits use PRISM, a 2000–2009
baseline and `log_built_surface`.

## Check only

| File | Role |
|---|---|
| `loss_output_year_county.csv` | `data_clean.py` compares yearly totals against it |
| `data/clean/census_county_year.csv` (from `census_features.py` and `nhgis0001_csv/nhgis0001_csv/`) | `temp_merge_panel.py` joins it, but none of its columns are inputs to the reduced refits. It will supply the housing units for `nfip_policies_per_hu` |

## NOAA cross-check

| File or folder | Note |
|---|---|
| `model_panel_noaa.csv`, `panel_county_month_noaa.csv` | Frozen NOAA panels |
| `data/nclimgrid_midwest/`, `prep_nclimgrid.py` | NOAA daily rain and frost |
| `out/w_county_month.csv`, `out/w_county_thresholds.csv` | NOAA rain indices and 1951–1999 baseline |
| `merge_panel.py` | Original merge, used for the NOAA panel |

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
| `data/openfema/` | OpenFEMA placeholder; see the README there |

## Not used

| File or folder | Note |
|---|---|
| `maps.py`, `maps/`, `data/counties_midwest.geojson` | Maps only |
| `yana_workspace/build_county_panel.py`, `neighbour_model.py`, `prism_county_export.py`, `ghsl_county_export.py`, `gee_exposure_app.js` | Earlier 5-county Ohio design |
| `yana_workspace/data/`, `yana_workspace/results/` | Outputs of that 5-county design |
| `data/gee_prism39167/`, `data/gee_ghsl39167/`, `out/prism_39167/` | Single-county and 5-county PRISM and GHSL files |
| `yana_workspace/flood_model_variable_tree.*` | Diagram of the variables |
| `docs/`, `HANDOFF.md`, `yana_workspace/HANDOFF2.md`, `yana_workspace/HANDOFF3.md`, `SHELDUS_Data_Documentation.pdf`, `Data_Collection_and_Panel_Dataset (1).docx` | Documentation |
