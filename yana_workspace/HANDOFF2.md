# Handoff 2: Pivot to Earth Engine Only, Washington County, Ohio (CSE 472, Project 2)

Read this after `HANDOFF.md`. It covers the sessions of 2026-11-04 (on branch
`yan-dev2`, merged into `enci-dev`) and 2026-11-05 (on `enci-dev`). Everything
created in these sessions is in `yana_workspace/`. **For the latest status, start
at [Session 2026-11-05](#session-2026-11-05-panel-rebuilt-neighbour-model-gee-app)
at the end of this file.**

**Status (2026-11-04):** the input list was narrowed to 12 inputs + 2 controls,
and the project pivoted to two mentor rules: (1) every input must come from
Google Earth Engine, and (2) the study focuses on one county and its neighbours.
The focus is **Washington County, Ohio (GEOID 39167)** and its four Ohio
neighbours. To stay under the Earth Engine cap, **the existing ERA5, NLCD and
terrain exports are reused**; the only new pull is PRISM daily rain and Tmin for
the 5 counties. After mentor feedback the pull was cut to **2000–2023 in 3
export tasks; all 3 have been run and downloaded to `data/gee_prism39167/`**
(see [Update: later start year](#update-later-start-year-mentor-feedback-2026-11-04)).
On 2026-11-05 the panel was rebuilt for 2010–2023 with the PRISM columns and
the neighbour model was fitted (see the last section).

## What changed (the pivot)

| | Before (`HANDOFF.md`) | Now |
|---|---|---|
| Allowed input sources | Any non-SHELDUS source | **Google Earth Engine only** (SHELDUS stays as the outcome) |
| Spatial scope | 12 Midwest states, 1,055 counties | **Washington, OH (39167) + Athens (39009), Monroe (39111), Morgan (39115), Noble (39121)** |
| Daily rain and Tmin | NOAA nClimGrid-Daily (not in GEE) | **PRISM daily, `OREGONSTATE/PRISM/ANd`** (GEE; starts 1981) |
| Rain climate C baseline | 1951–1999 | **1981–1999**, the earliest PRISM allows |
| Soil moisture baseline | 1950–1999 | Unchanged (ERA5-Land, already in GEE exports) |
| Model years | 2000–2023, train 2000–2016, test 2017–2023 | Unchanged |
| Inputs | 39 columns (trees), 17 (GLM) | **12 inputs + 2 controls** ([reduced_variables.md](reduced_variables.md)); see the GEE-only status below |
| Earth Engine use | Whole Midwest, one task per year | **PRISM only, 5 counties, one task per pull, at most 10 years per pull** |
| New research question | | Does the neighbouring counties' hazard affect Washington County's property damage? |

### Why Washington County, Ohio

From `loss_cleaned_monthly.csv`, 2000–2023 flood property damage:

- Most damage months in the region: **57** (22 in 2000–2016, 35 in 2017–2023),
  $34.0M (2024 $). It is the most balanced train/test split of the top counties
  (Polk, IA has 51 but only 9 in the test years after Iowa's reporting drop).
- Its neighbour Athens is also near the top (50 damage months), and the Ohio
  River runs along its border.

| County | GEOID | Damage months 2000–2023 | In 2000–2016 |
|---|---|---|---|
| Washington (focus) | 39167 | 57 | 22 |
| Athens | 39009 | 50 | 26 |
| Morgan | 39115 | 22 | 12 |
| Monroe | 39111 | 13 | 10 |
| Noble | 39121 | 12 | 9 |

**Neighbours** were found from shared boundary points in
`data/counties_midwest.geojson`, so no Earth Engine call was needed. The West
Virginia counties across the Ohio River are left out on purpose:

- SHELDUS has no outcome for them.
- The existing exports don't cover them, so including them would need new ERA5, NLCD and terrain pulls.

**Round values:** 54% of Washington County's nonzero property values are round
figures, against 30% across the region (`is_round_property`).

## Data sources audit

| Source | Used for | In GEE? | Decision |
|---|---|---|---|
| SHELDUS (`loss_cleaned_monthly.csv`) | Outcome Y | No | **Kept as the outcome** (decided 2026-11-05): the observed damage the model's predictions are trained and scored against, never an input |
| NOAA nClimGrid-Daily (`prep_nclimgrid.py`, `data/nclimgrid_midwest/`) | `p_month`, `rx5_rl_ratio`, `frost_days`, C | No | **Replaced by PRISM** (the one new pull) |
| ERA5-Land (`ECMWF/ERA5_LAND/...`) | `sm_root_pct`, `swe_mm`, `snowmelt_mm` | Yes | **Reused** from `data/gee_era5/` (1950–2023) |
| Annual NLCD (`projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/...`) | `impervious_mean`, `wetland_share` | Yes (community catalog) | **Reused** from `data/gee_nlcd/` (1999–2023) |
| MERIT Hydro, USGS 3DEP, TIGER 2018 | `hand_lt5_share`, `land_km2` | Yes | **Reused** from `data/gee_terrain/` |
| IPUMS NHGIS census / ACS | `log_housing_units`, all census columns | No | **On hold** |
| NFIP policies, HMA buyouts, gNATSGO soils, USGS streamflow | Planned A, X, W | No | **On hold** (never built) |

### Reduced variables under the GEE-only rule

| Block | Variable | Source | Status |
|---|---|---|---|
| W, same month | `p_month`, `rx5_rl_ratio`, `frost_days` | PRISM | Waiting on the pull |
| W, same month | `snowmelt_mm` | ERA5-Land | In the county panel now |
| W, known in advance | `sm_root_pct`, `swe_mm` | ERA5-Land | In the county panel now |
| C | `c_rx5_rl10_mm` (1981–1999) | PRISM | Waiting on the pull |
| X | `impervious_mean`, `hand_lt5_share`, `land_km2` | NLCD, MERIT, TIGER | In the county panel now |
| X | `log_housing_units` | NHGIS | **On hold** (not GEE) |
| A | `wetland_share` | NLCD | In the county panel now |
| Controls | calendar month | | State is constant (all Ohio), so the state control drops out |
| Neighbours (new) | `nb_*`: land-area-weighted mean of the 4 neighbours' monthly hazard | Same as above | ERA5 parts now, PRISM parts after the pull |

**Caveats:**
- **Shorter baseline:** the 10-year return level is fitted on 19 annual maxima (1981–1999) instead of 49, so `c_rx5_rl10_mm` is less precise.
- **C barely varies:** with 5 neighbouring counties it is nearly constant, so in a single-county model it acts as a constant, not a confounder control.

## Work done this session

| File | What it is |
|---|---|
| [reduced_variables.md](reduced_variables.md) | Impact-model equation (τ, causal target, hurdle model), the 12 reduced inputs, the 27 dropped inputs with reasons, the tree embedded as HTML. Written before the GEE-only pivot: `log_housing_units` is now on hold |
| [flood_model_variable_tree.md](flood_model_variable_tree.md) | Text version of the reduced variable tree |
| [flood_model_variable_tree.html](flood_model_variable_tree.html) | The tree as a web page |
| [flood_model_variable_tree.pdf](flood_model_variable_tree.pdf) | The tree printed from the HTML page (2 landscape pages) |
| [prism_county_export.py](prism_county_export.py) | The one Earth Engine pull: PRISM daily ppt + tmin for the 5 counties, one task per pull, at most 10 years |
| [build_county_panel.py](build_county_panel.py) | County-month panel from the existing ERA5/NLCD/terrain files, the SHELDUS outcome and (once pulled) PRISM; adds neighbour hazard columns |
| `HANDOFF2.md` | This file |

### `prism_county_export.py`

- **County set:** the 5 GEOIDs are hard-coded and filtered from `TIGER/2018/Counties`.
- **One task per pull:** all days in the year range go into a single table, so the 1981–2023 pull is 5 tasks, not 43. The old `prism_export.py prism` command made one task per year.
- **Output:** `prism_39167_<start>_<end>.csv` with columns `GEOID, date, ppt, tmin`, which is what `w_indices.py` reads. The files land in Drive folder `gee_prism_39167`.
- **10-year limit:** it refuses any pull longer than 10 years.
- **Checked locally:** it compiles and rejects 1981–1999. Run on 2026-11-04 for 2000–2009, 2010–2019 and 2020–2023 (see the current pull log).

### `build_county_panel.py`

- **Inputs:** it reuses `build_panel.py`'s ERA5, NLCD and terrain loaders, keeping only the 5 counties before the percentile step. Soil percentiles still use the 1950–1999 ERA5 baseline, and land cover is from year − 1.
- **Outcome:** built from `loss_cleaned_monthly.csv` the same way `build_monthly_panel.py` does it. Months with no record are 0, `log_PropertyDmgADJ` = log10(x + 1), and `split` puts years up to 2016 in train. It doesn't need the NHGIS housing table, and it doesn't need `merge_panel.py`.
- **Outputs:**
  - `county_set_panel.csv`: 5 counties × 288 months.
  - `focus_panel_39167.csv`: Washington's 288 months plus `nb_*` columns.
- **Run on 2026-11-04 without PRISM:** 1,440 rows and no missing values. Washington has 57 damage months, which matches SHELDUS.

## Pull plan (Earth Engine project `flood-513221`)

Only PRISM is pulled: 5 tasks for 5 counties. Run from the repository root.

```powershell
# one-time setup
pip install earthengine-api
earthengine authenticate

# optional: confirm PRISM's date range and bands (reads metadata only, no export)
python prism_export.py inspect --project flood-513221

# baseline for C (1981-1999)
python yana_workspace/prism_county_export.py --project flood-513221 --start 1981 --end 1990
python yana_workspace/prism_county_export.py --project flood-513221 --start 1991 --end 1999

# model years (2000-2023)
python yana_workspace/prism_county_export.py --project flood-513221 --start 2000 --end 2009
python yana_workspace/prism_county_export.py --project flood-513221 --start 2010 --end 2019
python yana_workspace/prism_county_export.py --project flood-513221 --start 2020 --end 2023

# progress
earthengine task list
```

Download the Drive folder `gee_prism_39167` to `data/gee_prism_39167/`.

### Pull log

Superseded: this 5-task plan was replaced by the 3-task plan in
[Update: later start year](#update-later-start-year-mentor-feedback-2026-11-04).
Tasks 1–2 (1981–1999) were not run; tasks 3–5 match the 3 tasks that were run.

| Task | Years | File | Status |
|---|---|---|---|
| 1 | 1981–1990 | `prism_39167_1981_1990.csv` | Not run |
| 2 | 1991–1999 | `prism_39167_1991_1999.csv` | Not run |
| 3 | 2000–2009 | `prism_39167_2000_2009.csv` | Not run |
| 4 | 2010–2019 | `prism_39167_2010_2019.csv` | Not run |
| 5 | 2020–2023 | `prism_39167_2020_2023.csv` | Not run |

## Building the panel after the pull

```powershell
# W and C from PRISM, rain baseline 1981-1999
python w_indices.py --input data/gee_prism_39167 --out-dir out/prism_39167/ --base-start 1981 --base-end 1999

# county panel: existing ERA5/NLCD/terrain + SHELDUS outcome + PRISM
python yana_workspace/build_county_panel.py --w-dir out/prism_39167 --out-dir yana_workspace/data
```

Without `--w-dir` the builder runs today on the existing data. It just leaves
out `p_month`, `rx5_rl_ratio`, `frost_days`, `c_rx5_rl10_mm` and their `nb_*`
versions.

## Next steps

1. Run the 5 PRISM tasks and fill in the pull log.
2. Check PRISM against the old nClimGrid values for these counties in 2000–2023
   (`data/nclimgrid_midwest/` has the same columns): `p_month` and `rx5` should
   correlate highly.
3. Neighbour-influence model on `focus_panel_39167.csv`: GLM hurdle on the
   reduced inputs, with and without the `nb_*` columns, scored on 2017–2023.
   288 months with 57 damage months is small: keep the model small (few inputs,
   ridge penalty) and use a bootstrap over years for intervals.
4. Larger alternative: use all 5 counties as rows (`county_set_panel.csv`,
   1,440 rows, 154 damage months) with each county's neighbour hazard as a
   spatial-lag term.
5. ~~Decide whether SHELDUS counts as allowed, and which Earth Engine exposure
   layer should replace `log_housing_units`.~~ Resolved 2026-11-05, see
   [Decisions](#decisions-2026-11-05).

## Decisions (2026-11-05)

- **SHELDUS is the outcome.** It provides the observed property damage that the
  model's predictions are trained and evaluated against (`has_damage`,
  `log_PropertyDmgADJ`). It is not a model input, so the GEE-only rule for
  inputs does not apply to it.
- **Exposure layers go in an Earth Engine app.** The team is building an Earth
  Engine app where the user selects one of several exposure layers and the app
  shows it as a heatmap on the map. So no single layer has to be picked to
  replace `log_housing_units`.

## Working notes

- Project ID: `flood-513221`. Focus county GEOID: `39167`.
- PRISM `ANd` starts 1981-01-01; confirm with `inspect`.
- `build_panel.py` and the other repository scripts are unchanged; the new
  scripts import from them.
- All new documents go in `yana_workspace/` for this session's work.
- Commit only when asked.

## Update: later start year (mentor feedback, 2026-11-04)

**This section replaces the [Pull plan](#pull-plan-earth-engine-project-flood-513221),
the pull log and the baseline years above.**

### Context

An earlier email to Saketh said the PRISM pull through Earth Engine was too
expensive: one test year used 6.8 of the 150 free monthly compute hours, so
1981–2023 would need about 290 hours. The team had switched to NOAA nClimGrid
for that reason. Saketh replied:

> Why not just start from a later year if you have problems from 1981-2024 for
> your period of analysis, instead of not using GEE?

The 1981–2023 commands above use GEE but still pull the full 43 years, so they
only answer half of the question. The plan below pulls fewer years.

- **Lower cost.** The 6.8 hours per year were for all 1,055 Midwest counties,
  one task per year. The new pull covers 5 counties in one task per pull, so
  compute should be far lower. This is not measured: Earth Engine also charges
  a fixed amount for every daily image, whatever the area.
- **No test year.** To save quota, the team decided to run the pulls directly.
  If a pull fails or the years need changing, it can be pulled again.

### New design

| | Before (this file, above) | Now |
|---|---|---|
| Rain-climate baseline (C) | 1981–1999 | **2000–2009** |
| Analysis period | 2000–2023 | **2010–2023** |
| Train / test | 2000–2016 / 2017–2023 | **2010–2018 / 2019–2023** |
| PRISM years pulled | 43 (5 tasks) | **24 (3 tasks)** |

Washington County damage months by period (`loss_cleaned_monthly.csv`):

| Analysis period | Damage months | Split |
|---|---|---|
| 2000–2023 (old) | 57 | train to 2016: 22 · test from 2017: 35 |
| **2010–2023 (new)** | **48** | **train 2010–2018: 26 · test 2019–2023: 22** |

- **Only 9 damage months are lost.** Most of the county's damage falls after
  2010.
- **The split moves to 2019.** Keeping 2017 as the first test year would leave
  only 13 damage months to train on.
- **The baseline is shorter.** The 10-year return level now rests on 10 annual
  maxima, not 19. With five neighbouring counties, C barely varies anyway.
  1981–1999 can still be pulled later (2 more tasks) for a longer baseline.

### Commands to run

```powershell
pip install earthengine-api
earthengine authenticate

python yana_workspace/prism_county_export.py --project flood-513221 --start 2000 --end 2009   # baseline for C
python yana_workspace/prism_county_export.py --project flood-513221 --start 2010 --end 2019   # analysis
python yana_workspace/prism_county_export.py --project flood-513221 --start 2020 --end 2023   # analysis
earthengine task list
```

The files were downloaded from the Drive folder `gee_prism_39167` to
**`data/gee_prism39167/`** (no underscore before `39167`; the commands below
use this path).

### Pull log (current)

| Task | Years | File | Rows | Status |
|---|---|---|---|---|
| 1 | 2000–2009 | `prism_39167_2000_2009.csv` | 18,265 | Run; in `data/gee_prism39167/` |
| 2 | 2010–2019 | `prism_39167_2010_2019.csv` | 18,260 | Run; in `data/gee_prism39167/` |
| 3 | 2020–2023 | `prism_39167_2020_2023.csv` | 7,305 | Run; in `data/gee_prism39167/` |

**Status:** all three commands have been run and the files are downloaded.
Checked: each file has the columns `GEOID, date, ppt, tmin`, all 5 GEOIDs
(39009, 39111, 39115, 39121, 39167), every day of its years (rows = days × 5,
leap days included) and no missing `ppt` or `tmin` values.

### Rebuilding the panel

1. Update `build_county_panel.py` for the new years (see
   [Code still to update](#code-still-to-update-for-the-new-years)).
2. Build the rain indices and the rain climate (C), then the panel:

```powershell
python w_indices.py --input data/gee_prism39167 --out-dir out/prism_39167/ --base-start 2000 --base-end 2009 --model-start 2010 --model-end 2023
python yana_workspace/build_county_panel.py --w-dir out/prism_39167 --out-dir yana_workspace/data
```

3. Record the row counts that `build_county_panel.py` prints.

### Code still to update for the new years

Both pieces of code still assume the old design:

- **`w_indices.py`** needs the new years passed in:
  `python w_indices.py --input data/gee_prism39167 --out-dir out/prism_39167/ --base-start 2000 --base-end 2009 --model-start 2010 --model-end 2023`
- **`build_county_panel.py`** has `MODEL_START = 2000` hard-coded and the split
  at `year <= 2016`. Change them to 2010 and `year <= 2018`. Its ERA5
  soil-moisture baseline (1950–1999) can stay: ERA5 comes from GEE and is
  already downloaded.

### Reply sent to the mentor (draft)

> Thanks Saketh, that works. We've narrowed the study to Washington County, OH
> and its four neighbouring counties, which cuts the Earth Engine compute by a
> large factor. Following your suggestion we'll pull PRISM daily from GEE for
> 2000–2023 only: 2000–2009 as the rainfall baseline and 2010–2023 as the
> analysis period (48 of the county's 57 flood-damage months fall in it). All
> inputs will then come from GEE.

## Session 2026-11-05: panel rebuilt, neighbour model, GEE app

### Decisions
See [Decisions (2026-11-05)](#decisions-2026-11-05): SHELDUS is the outcome the
model is trained and scored against, and exposure layers are shown in an Earth
Engine app rather than picking one to replace `log_housing_units`.

### Panel rebuilt for 2010–2023
The [code changes for the new years](#code-still-to-update-for-the-new-years)
are done: `build_county_panel.py` has `MODEL_START = 2010` and trains on
`year <= 2018`.

```
python w_indices.py --input data/gee_prism39167 --out-dir out/prism_39167/ --base-start 2000 --base-end 2009 --model-start 2010 --model-end 2023
python yana_workspace/build_county_panel.py --w-dir out/prism_39167 --out-dir yana_workspace/data
```

- `w_indices.py` (needs `scipy`): 840 county-months. `p_month`, `rx5_rl_ratio`
  and `frost_days` have no gaps. The 10-year 5-day level (C) is 96–108 mm.
  It needs at least 10 baseline years, and 2000–2009 is exactly 10.
- Panel: 840 rows (5 counties × 168 months), no missing values. Focus panel:
  168 rows with the 6 `nb_*` columns.

| County | Damage months 2010–2023 | Train 2010–2018 | Test 2019–2023 |
|---|---|---|---|
| Washington | 48 | 26 | 22 |
| Athens | 35 | 19 | 16 |
| Morgan | 15 | 7 | 8 |
| Noble | 7 | 5 | 2 |
| Monroe | 5 | 3 | 2 |

### Neighbour model (`neighbour_model.py`)
GLM hurdle as in `hurdle_model.py`, numpy only. Inputs: the 6 monthly hazard
columns plus a sin/cos season (11 month dummies are too many for 26 training
damage months). Ridge picked by leave-one-year-out CV inside 2010–2018. Outputs
are in `yana_workspace/results/`.

Washington alone, test 2019–2023:

| Model | ROC-AUC | PR-AUC | Brier skill vs climatology |
|---|---|---|---|
| Climatology (month rate) | 0.63 | 0.56 | 0 |
| Own hazard | 0.81 | 0.74 | +0.16 |
| Own + neighbour hazard | 0.79 | 0.73 | +0.13 |
| Neighbour hazard only | 0.88 | 0.83 | +0.29 |

Pooled, 5 counties with county indicators (test: 300 rows, 50 damaged): own
0.91 AUC, own + neighbour 0.90.

**Finding: the neighbours' hazard adds nothing measurable.**
- Own and neighbour hazard correlate 0.92–1.00. ERA5 snow and soil are almost
  the same across 5 adjacent counties, and so is monthly rain (0.97).
- Adding `nb_*` lowers AUC slightly in both setups. The year bootstrap puts the
  change at [−0.03, 0.00] for Washington and [−0.017, −0.006] pooled.
- "Neighbour only" scoring best on the test years is noise. Over all 14 years
  (leave one year out), own 0.84, own + neighbour 0.84 and neighbour only 0.83
  are equal.
- Using only the difference (neighbour minus own rain) also hurts part 1
  (AUC 0.71). It improves part 2 RMSE (0.81 to 0.62 log10 $) on 22 damaged test
  months, which is too few to rely on.
- The hazard model clearly beats climatology (AUC 0.81–0.91 vs 0.63–0.73).

**Ideas if the neighbour question stays:** Ohio River flooding at Marietta is
driven by the upstream basin (Pittsburgh, West Virginia), far beyond the 4
bordering counties. An upstream-basin rain index, or USGS river stage (not in
GEE), is a better "neighbour" signal than adjacent-county rain.

### Exposure from Earth Engine (`ghsl_county_export.py`), run 2026-11-05
One task: GHSL built-up km² and population summed per county for epochs
2005/2010/2015/2020. It ran on Earth Engine project **`cse472-project-2`**, now
the script's default. `flood-513221` refuses this account (no IAM role). The
file is in `data/gee_ghsl39167/ghsl_39167.csv` (20 rows).

```
python yana_workspace/ghsl_county_export.py
python yana_workspace/build_county_panel.py --w-dir out/prism_39167 --out-dir yana_workspace/data --ghsl data/gee_ghsl39167
```

- **Panel:** `--ghsl` adds `built_share` and `log_population`, interpolated
  between epochs, held flat after 2020 and lagged one year like NLCD. The
  panels in `yana_workspace/data/` are now built with it (no missing values).
  Without `--ghsl` the output matches the earlier panel.
- **Check:** GHSL population matches the census. Washington ≈ 62k, Athens ≈ 65k,
  Monroe, Morgan and Noble ≈ 15k each.
- **Variation:** exposure barely changes within a county over 2010–2023, so it
  only differs between the 5 counties. The county-level inputs also correlate
  0.83–0.98 with each other (`built_share`, `log_population`, `impervious_mean`,
  `land_km2`). With 5 counties, at most about 2 of them can enter.

Pooled model, test 2019–2023, with exposure in place of the county indicators:

| Model | ROC-AUC | PR-AUC | Brier skill |
|---|---|---|---|
| Own hazard, no county indicators | 0.84 | 0.53 | +0.09 |
| Own hazard + `log_population` + `hand_lt5_share` | 0.89 | 0.69 | +0.23 |
| Own hazard + county indicators | 0.91 | 0.71 | +0.25 |

- **Exposure explains most of why counties differ.** The two exposure inputs
  recover most of what the 4 county indicators add.
- **Part 1 coefficients** (standardized): population +0.64 and floodplain
  share +0.50 on the chance of damage. In part 2 (the amount) both are ≈ 0.
- **Caveat:** this rests on 5 counties. Population also stands in for
  reporting: bigger counties have more property and more people to report
  damage. The data can't separate those.

### Earth Engine app (`gee_exposure_app.js`)
- Code Editor script with 6 exposure heatmaps (GHSL built-up and population,
  WorldPop, NLCD impervious, MERIT HAND < 5 m, JRC surface water), a year slider
  and a legend. Click a county to get its mean.
- Mirrored to the Earth Engine script repo
  `users/ezheng3/flood_impact_forecasting` (file `gee_exposure_app`). Local clone:
  `flood_impact_forecasting/`, hidden from this repo through `.git/info/exclude`.
- Optional model layers: upload `results/predictions_5county.csv` as a table
  asset and set `PRED_ASSET`. That adds mean P(damage), expected damage per year
  and SHELDUS observed damage months per county.
- Syntax checked only. Dataset IDs and colour ranges still need checking in the
  Code Editor.

### Next
1. Run the app in the Code Editor, fix any dataset or band errors, then publish
   it (Apps → New App).
2. ~~Run `ghsl_county_export.py`, rebuild with `--ghsl`, and refit the pooled
   model.~~ Done 2026-11-05 (see above).
3. Upload `predictions_5county.csv` to project `cse472-project-2` and set
   `PRED_ASSET`.
4. Decide with the team whether to keep the neighbour question (null result
   above) or switch to an upstream-basin index.
