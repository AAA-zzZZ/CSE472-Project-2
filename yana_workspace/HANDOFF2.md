# Handoff 2: Pivot to Earth Engine Only, Washington County, Ohio (CSE 472, Project 2)

Read this after `HANDOFF.md`. It covers the session of 2026-11-04 on branch
`yan-dev2`. Everything created in this session is in `yana_workspace/`.

**Status (2026-11-04):** the input list was narrowed to 12 inputs + 2 controls,
and the project pivoted to two mentor rules: (1) every input must come from
Google Earth Engine, and (2) the study focuses on one county and its neighbours.
The focus is **Washington County, Ohio (GEOID 39167)** and its four Ohio
neighbours. To stay under the Earth Engine cap, **the existing ERA5, NLCD and
terrain exports are reused**; the only new pull is PRISM daily rain and Tmin for
the 5 counties: **5 export tasks in total, not yet run**. The county panel
builder runs today on the existing data and adds the PRISM columns once the
pull is in. Nothing has been committed.

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
| SHELDUS (`loss_cleaned_monthly.csv`) | Outcome Y | No | Kept: outcome, not an input (confirm with mentor) |
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
- **Checked locally:** it compiles and rejects 1981–1999. **Not yet run against Earth Engine.**

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
5. Decide with the mentor whether SHELDUS counts as allowed (it is the outcome),
   and whether an Earth Engine exposure layer (JRC GHSL built-up, WorldPop)
   should replace `log_housing_units`.

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

Download the Drive folder `gee_prism_39167` to `data/gee_prism_39167/`.

### Pull log (current)

| Task | Years | File | Status |
|---|---|---|---|
| 1 | 2000–2009 | `prism_39167_2000_2009.csv` | Not run |
| 2 | 2010–2019 | `prism_39167_2010_2019.csv` | Not run |
| 3 | 2020–2023 | `prism_39167_2020_2023.csv` | Not run |

### Code still to update for the new years

Both pieces of code still assume the old design:

- **`w_indices.py`** needs the new years passed in:
  `python w_indices.py --input data/gee_prism_39167 --out-dir out/prism_39167/ --base-start 2000 --base-end 2009 --model-start 2010 --model-end 2023`
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
