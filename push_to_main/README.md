# Files Used to Build and Feed the Models

This lists every script and data folder that creates the flood-loss models or supplies data to
them, in pipeline order. Each entry gives its path from the repository root, what it does, what
is inside, and for data, where it came from and how and why it was changed.

Traced on 2026-11-14 on branch `enci-dev`. It replaces `cleaned_items/used_files.md`
(2026-11-08), which does not include the loss-class model, the adjustment models or the apps.

**The models in one line:** a two-part (hurdle) model for each county and month in 12 Midwest
states (1,055 counties, 2000–2023). Part 1 gives the chance of any flood property damage; part 2
gives the loss class if damage occurs (minor under $10k, moderate $10k–$100k, major $100k–$1M,
severe $1M or more). Train 2000–2016, test 2017–2023.

**Git-ignored files** (too large to commit) are marked **(ignored)**. They are rebuilt by the
script named in their entry.

---

## Pipeline at a glance

```
SHELDUS losses ─► data_clean.py ─► build_monthly_panel.py ─┐  (outcome)
NHGIS housing  ─► housing_features.py ─────────────────────┘
PRISM daily    ─► prism_export.py prism ─► w_indices.py ───┐  (rain, frost, rain climate)
ERA5-Land, NLCD, terrain ─► prism_export.py ─► build_panel.py ─┤  (soil, snow, land cover, terrain)
GHSL           ─► ghsl_export.py ─► ghsl_features.py ──────┤  (built-up surface)
NHGIS census   ─► census_features.py ──────────────────────┤  (income, housing age)
OpenFEMA       ─► openfema_features.py ────────────────────┤  (insurance, CRS, buyouts)
                                                           ▼
                                   merge_panel.py ─► model_panel.csv
                                                           │
     reduced_benchmark.py, loss_class_model.py, adjustment_models.py, recalibrate.py
                                                           │
                       build_midwest_app_table.py ─► Earth Engine explorer app
```

---

## 1. Outcome: flood property loss (SHELDUS)

SHELDUS is used **only** for the outcome. Nothing derived from losses is a model input.

### `direct_loss_aggregated_output_32423.csv`
- **What:** the raw SHELDUS export. One row per county, month and hazard, with property and crop
  damage, in nominal dollars and adjusted to 2024 dollars, plus per-capita values, durations and
  record counts.
- **Source:** SHELDUS (Spatial Hazard Events and Losses Database for the United States, Arizona
  State University), hazard **Flooding**, 12 Midwest states, 1960–2024. See
  `SHELDUS_Data_Documentation.pdf`.
- **Changed:** no, raw input.

### `loss_output_year_county.csv`
- **What:** the same SHELDUS query by county-year.
- **Use:** check only. `data_clean.py` confirms the monthly rows add up to these yearly totals.

### `data_clean.py` → `loss_cleaned_monthly.csv`
- **What:** cleans the raw SHELDUS county-month losses.
- **How the data is changed, and why:**
  - FIPS codes are read as text and padded to 5 digits, so leading zeros are never lost.
  - Rows with missing values, duplicates, bad FIPS, bad dates or negative values are dropped.
  - Two old South Dakota codes are merged into today's counties: 46113 Shannon → 46102 Oglala
    Lakota, and 46131 Washabaugh → 46071 Jackson. Otherwise those losses would match no county.
  - Records that span a whole month (28–31 days) are **flagged** (`is_month_long`), not removed.
  - Round amounts (1, 2, 2.5 or 5 × a power of ten) are **flagged** (`is_round_property`).
    Older Storm Data reported damage in ranges that became fixed round values; about 30% of
    losses are round.
  - Extreme values are **kept and flagged** (`is_extreme_property`): they are real,
    documented floods.
  - `log10(x + 1)` columns are added: dollar losses are very skewed, and the models work on a
    log scale.

### `nhgis0001_csv/nhgis0001_ts_nominal_county.csv` (+ `_codebook.txt`)
- **What:** IPUMS NHGIS time series A62: urban and rural housing units by county, censuses
  1970–2020.
- **Source:** IPUMS NHGIS (https://www.nhgis.org), extract `nhgis0001`.

### `housing_features.py` → `housing_county_year.csv`
- **What:** housing units and urban share for every county and year, 1999–2023.
- **How changed, and why:** each year takes the most recent census at or before it, so no
  later census leaks into an earlier year. The old South Dakota codes are merged as above.

### `build_monthly_panel.py` → `model_data_monthly_panel.csv` (ignored)
- **What:** the full county × month grid, 2000–2023: every county in the 12 states and every
  month, 303,840 rows.
- **How changed, and why:**
  - SHELDUS lists only months that had a loss. Missing county-months are filled with **loss
    = 0**, because the model must learn from months without damage too.
  - The county list comes from the census, not SHELDUS, so counties that never reported a flood
    are included.
  - It adds `has_damage` (loss > 0) and `split` (train 2000–2016, test 2017–2023).
  - It attaches census housing. That is not a model input any more, but the step is needed to
    build the file.

---

## 2. Rain, frost and rain climate (PRISM)

### `prism_export.py` (`prism` command) → `data/gee_prism_midwest/`
- **What:** 24 files, one per year 2000–2023. Each holds daily rain (`ppt`, mm) and minimum
  temperature (`tmin`, °C) averaged over each county.
- **Source:** PRISM daily (`OREGONSTATE/PRISM/ANd`, about 4 km), through Google Earth Engine.
  County shapes come from Census TIGER 2018 (`TIGER/2018/Counties`).
- **How changed, and why:** grid cells are averaged over each county, because the models work
  per county. The script also holds the `era5`, `nlcd` and `terrain` exports (section 3).

### `w_indices.py` → `out/prism_midwest/`
- **What:** turns daily county rain and temperature into monthly hazard measures.
  - `w_county_month.csv` (ignored): one row per county-month. Holds `p_month` (monthly rain),
    `rx1`/`rx3`/`rx5` (wettest 1/3/5 days), `rx5_rl_ratio`, `frost_days` (days with Tmin < 0 °C),
    SPI drought indices and others.
  - `w_county_thresholds.csv`: each county's normal rain climate, from 2000–2009. Holds wet-day
    95th/99th percentiles and 2-, 10- and 25-year 5-day rain levels.
- **How changed, and why:**
  - **`rx5_rl_ratio`** = wettest 5 days of the month ÷ the county's own 10-year 5-day rain level
    (from a GEV fit to 2000–2009 yearly maxima). 100 mm can be extreme in a dry county and
    ordinary in a wet one; dividing by the county's own level makes storms comparable. This is
    the model's main storm input.
  - The thresholds use only 2000–2009, so a county's "normal" is not learned from the years it
    is tested on. 2000–2009 is the earliest PRISM decade in the export.
  - Multi-day windows count in the month they end, as in the ETCCDI convention.

### NOAA cross-check (not used by the current models)
- `prep_nclimgrid.py` → `data/nclimgrid_midwest/`: NOAA nClimGrid-Daily county rain and Tmin,
  1951–2023 (from `s3://noaa-nclimgrid-daily-pds/`), cut down to the Midwest.
- `out/w_county_month.csv` (ignored), `out/w_county_thresholds.csv`: the same indices on NOAA,
  with a 1951–1999 baseline.
- `model_panel_noaa.csv`, `panel_county_month_noaa.csv` (ignored): frozen NOAA panels.
- **Why kept:** the project first used NOAA, then switched to PRISM. NOAA is kept only to
  check the PRISM results.

---

## 3. Soil, snow, land cover and terrain (Earth Engine)

All are exported by `prism_export.py` (commands `era5`, `nlcd`, `terrain`) and averaged over each
county.

### `data/gee_era5/`
- **What:** 74 files, 1950–2023, one per year. Holds soil moisture in 3 layers and snowpack
  (snow water equivalent) on day 1 of each month, and the monthly snowmelt total.
- **Source:** ERA5-Land (`ECMWF/ERA5_LAND/DAILY_AGGR` and `MONTHLY_AGGR`, about 11 km).
- **Why from 1950:** the soil-wetness percentile is ranked against 1950–1999.

### `data/gee_nlcd/`
- **What:** 25 files, 1999–2023. Holds the shares of developed land, wetland and water, and
  mean paved (impervious) percent, per county.
- **Source:** USGS Annual NLCD land cover and fractional impervious surface (Earth Engine
  community catalog, `projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/...`), at 90 m.

### `data/gee_terrain/terrain_county.csv`
- **What:** one row per county with land and water area, mean elevation, slope, the flat share
  (slope < 2°), mean height above the nearest drainage (HAND), and the share of land less than
  5 m above drainage.
- **Source:** USGS 3DEP 10 m elevation (`USGS/3DEP/10m_collection`), MERIT Hydro HAND, and Census
  TIGER land area.

### `build_panel.py` → `panel_county_month.csv` (ignored)
- **What:** joins ERA5, NLCD, terrain and the PRISM indices into one county × month table.
- **How changed, and why:**
  - Soil moisture and snowpack are taken on **day 1** of the month. They are then known before
    that month's floods, so they are fair predictors.
  - Root-zone soil water is a depth-weighted average of 0–100 cm, turned into `sm_root_pct`, a
    percentile against 1950–1999 for that county and calendar month. "Wet for this place and
    season" matters more than the raw value.
  - Land cover is from the **previous year** (year − 1), so it was known before the month.
  - `wetland_change_since_1999` is wetland share in year − 1 minus 1999.

---

## 4. Built-up surface (GHSL)

### `yana_workspace/ghsl_export.py` → `data/gee_ghsl/`
- **What:** 7 files (1995, 2000, …, 2025). Holds total built-up area per county (`built_m2`).
- **Source:** JRC Global Human Settlement Layer, `JRC/GHSL/P2023A/GHS_BUILT_S`, 100 m, through
  Earth Engine.

### `ghsl_features.py` → `data/clean/ghsl_county_year.csv`
- **What:** built-up area for every county and year.
- **How changed, and why:** GHSL comes in 5-year steps, so values for the years in between are
  filled by linear interpolation. `merge_panel.py` takes the natural log (`log_built_surface`),
  because built area is very skewed. This is the models' exposure input: more buildings, more to
  damage. It replaced census housing units.

---

## 5. Census and OpenFEMA (adaptation and exposure)

### `nhgis0001_csv/nhgis0001_csv/` → `census_features.py` → `data/clean/census_county_year.csv`
- **What:** per county and year 1999–2023: housing units, population, median home value, median
  household income, poverty rate, mobile-home share and share of homes built before 1980.
- **Source:** IPUMS NHGIS extract of the 2000 Census (SF3a) and each ACS 5-year release
  (2005–2009 … 2019–2023).
- **How changed, and why:**
  - Each estimate is placed in a year: the 2000 Census in 2000, and each ACS release in its last
    year. Years in between are interpolated so every year has a value.
  - Dollars are converted to **2024 dollars** with the CPI-U, the same base as the SHELDUS loss.
  - Shares are computed from counts.
  - Variable codes differ between releases, so columns are found by table code from each
    codebook.
- **Use:** housing units (the denominator of insurance per home), income and pre-1980 share
  feed the adjustment models and the app. They are not inputs to the forecast models.

### `openfema_features.py` → `data/clean/nfip_policies_county_year.csv`, `crs_county_year.csv`, `hma_county_year.csv`
- **What:** per county and year 1999–2022:
  - flood insurance policies in force on 1 July;
  - Community Rating System class (the best in the county; 10 = not taking part);
  - cumulative FEMA buyouts and elevations.
- **Source:** OpenFEMA NFIP Redacted Policies v3, HMA Subapplications Project Site Inventories v1
  and HMA Subapplications v2. Downloads go in `data/openfema/raw/` (ignored, about 4 GB). See
  `data/openfema/README.md` for links, curl commands and checks.
- **How changed, and why:**
  - Policies are counted if in force on 1 July of each year.
  - Years before 2010 are left **empty, not zero**: the records start in 2009, and an unknown
    year is not a year with no policies.
  - **Policies only, never claims:** claims come from the losses being predicted.
- **Use:** adjustment models and the app. Buyouts were tested as a forecast input
  (`results/*_buyouts/`) and added nothing.

---

## 6. Final panel

### `merge_panel.py` → `model_panel.csv` (ignored, 108 MB)
- **What:** **the one table every model reads.** One row per county-month, 2000–2023, 303,840
  rows.
- **How changed, and why:**
  - Joins the input panel (section 3), the outcome (section 1), the PRISM rain-climate
    thresholds (section 2) and the yearly `data/clean/` tables.
  - Yearly tables are joined with a **one-year lag** (model year t uses year t − 1), so every
    input was known before the month it predicts.
  - Adds `log_built_surface = ln(built_m2)` and `nfip_policies_per_hu = policies / housing units`.
  - Renames the climate columns to `c_rx5_rl10_mm` and the others.
- **Rebuild:** run sections 1–5 in order, then `python merge_panel.py`.

### The 12 inputs of the forecast models

| Input | Meaning | Source | Changed how |
|---|---|---|---|
| `p_month` | rain that month (mm) | PRISM | daily county average, summed |
| `rx5_rl_ratio` | wettest 5 days ÷ county's 10-year level | PRISM | ratio to 2000–2009 GEV level |
| `snowmelt_mm` | snowmelt that month (mm) | ERA5-Land | monthly total |
| `frost_days` | days with Tmin < 0 °C | PRISM | count per month |
| `sm_root_pct` | soil wetness, day 1 | ERA5-Land | percentile vs 1950–1999 |
| `swe_mm` | snowpack, day 1 (mm of water) | ERA5-Land | day 1 value |
| `c_rx5_rl10_mm` | county's 10-year 5-day rain (mm) | PRISM 2000–2009 | GEV fit; fixed per county |
| `log_built_surface` | built-up area, year − 1 | GHSL | interpolated, ln |
| `impervious_mean` | paved %, year − 1 | Annual NLCD | county mean |
| `hand_lt5_share` | land < 5 m above drainage | MERIT Hydro | share; fixed per county |
| `log_land_km2` | county land area | Census TIGER | ln |
| `wetland_share` | wetland share, year − 1 | Annual NLCD | classes 90 + 95 |

LightGBM also gets calendar month and state; the GLM gets month and state effects and logs the
skewed amounts.

---

## 7. Models

### `reduced_benchmark.py` → `results/midwest_prism/`, `results/missouri_prism/`, `results/missouri_pooled/`, `results/*_prism_buyouts/`
- **What:** the main forecast models on the 12 inputs: a GLM hurdle (ridge logistic + ridge
  linear) and a LightGBM hurdle, against a county-rate baseline. Part 2 here predicts log10
  dollars.
- **Design:** settings are chosen on 2000–2012 → 2013–2016; final fit on 2000–2016; scored once
  on 2017–2023. It includes a county bootstrap of ROC-AUC differences.
- **Output (per folder):** `scores.csv`, `glm_coefs.csv`, `log.txt`.
- **Use:** part 1 (chance of damage) is the part used by the class model and the app.

### `loss_class_model.py` → `results/loss_classes_midwest/`, `results/loss_classes_missouri/`
- **What:** part 2 as **loss classes** instead of dollars (current design). It uses an ordinal
  logistic GLM and a LightGBM multiclass model, and also scores binned dollars and a baseline.
  Counties are ranked by the chance of a $1M+ loss.
- **Why classes:** see `Project 2/Summary Guides/loss_classes_summary.pdf`. Each class is one
  power of ten, which matches the model's precision (the dollar model was typically off about
  7×).
- **Output:** `scores.csv`, `confusion_test.csv`, `glm_ordinal_coefs.csv`, `class_counts.csv`,
  `ranking_options.csv`, `log.txt`.

### `adjustment_models.py` → `results/adjustment_midwest/`, `results/adjustment_missouri/`
- **What:** five nested regressions (M0–M4) of log10 loss on storm size. They test whether
  adjusting for rain climate and adaptation (insurance, CRS, income, pre-1980 housing, wetlands)
  changes the storm effect. This is for explanation, not forecasting.
- **Output:** coefficients, summary, correlations, sample, log and three plots.

### `recalibrate.py` → `results/recalibration_midwest/`, `results/recalibration_missouri/`
- **What:** per-state shifts so the predicted number of damage months matches recent years,
  because fewer damage months were reported after 2016. It fixes the levels, not the ranking.

### Earlier models (kept for comparison; not the current design)
- `hurdle_model.py` → `results/hurdle_scores.csv`: 17-input GLM hurdle, built one block at a
  time.
- `model_comparison.py` → `results/model_comparison.csv`: GLM, random forest, LightGBM and
  Tweedie on 39 inputs. This is where LightGBM was chosen.

---

## 8. Using the models: Earth Engine explorer apps

### `yana_workspace/gee_app/Midwest/`
- `build_midwest_app_table.py` → `midwest_flood_app_table.csv`: refits part 1
  (`reduced_benchmark.py`) and the class model (`loss_class_model.py`) on 12 states and predicts
  2017–2023. It stops unless the scores match the saved results. Output: 88,620 rows ×
  37 columns of predictions, ranks, inputs and adaptation values.
- `flood_explorer_app2.js`: the Earth Engine app for the 12 states. It reads the table above,
  uploaded as an Earth Engine asset.

### `yana_workspace/gee_app/missouri_tester/`
- `build_app_table.py` → `mo_flood_app_table.csv`, `flood_explorer_app.js`: the Missouri app
  (dollar predictions; unchanged). Its `add_adaptation()` is reused by the Midwest builder.
- `midwest_flood_impact/flood_explorer.js` is the same app with another asset ID.

---

## 9. Reference documents

| Path | What |
|---|---|
| `HANDOFF.md`, `yana_workspace/HANDOFF2.md`–`HANDOFF4.md` | Session-by-session history and decisions |
| `docs/flood_variable_reference.xlsx` | Variable reference |
| `docs/literature_review/`, `docs/model_selection/` | Literature and model-choice notes |
| `SHELDUS_Data_Documentation.pdf` | SHELDUS definitions |
| `Data_Collection_and_Panel_Dataset (1).docx` | Data-collection guide |
| `maps.py` → `maps/` | County maps to check inputs (display only); uses `data/counties_midwest.geojson` |

## Not used by the current models

| Path | Why |
|---|---|
| `yana_workspace/build_county_panel.py`, `neighbour_model.py`, `prism_county_export.py`, `ghsl_county_export.py`, `yana_workspace/data/`, `yana_workspace/results/` | Earlier 5-county Ohio design and the dropped spatial model |
| `data/gee_prism39167/`, `data/gee_ghsl39167/`, `out/prism_39167/` | Single-county test exports |
| `yana_workspace/reduced_variables.md` | Out of date (describes NOAA and housing units) |
| `yana_workspace/gee_exposure_app.js`, `yana_workspace/flood_model_variable_tree.*` | Display and diagram only |
| `cleaned_items/used_files.md` | Older version of this list |
