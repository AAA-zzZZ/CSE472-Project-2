# Handoff 3: Route 2 with Earth Engine, Single-State Model (CSE 472, Project 2)

Read this after `HANDOFF.md` and `HANDOFF2.md`. It covers the session of
2026-11-06 on branch `enci-dev`.

> **Update 2026-11-09:** the chosen state is **Missouri** (FIPS 29). The rebuild command below
> needs `merge_panel.py --thresholds out/prism_midwest/w_county_thresholds.csv` (without it, C is
> the NOAA 1951–1999 climate). The data folders are `data/gee_prism_midwest/` and `data/gee_ghsl/`.
> NFIP and HMA were later collected after all. Current status: the "Latest session" section of
> `../HANDOFF.md`.

**Status (2026-11-06):** the team is continuing with **Route 2: PRISM and other
inputs from Google Earth Engine (GEE)**. The **2000–2023 Midwest PRISM pull and
the GHSL export are done**, as reported by the team. The model scope has since
changed: **it will run on one specific state: [STATE TO BE FILLED IN]**, not the
full Midwest or the 5 Ohio counties in `HANDOFF2.md`. The Midwest files were not
yet in `data/gee_prism_midwest/` or `data/gee_ghsl/` when this was written, so
download them there first. See
[Update: single-state scope](#update-single-state-scope). `HANDOFF3.md` is not
committed yet.

Presentation handout, with the pros and cons, variables and equations:
`Project 2/Summary Guides/data_route_plan_summary.pdf` (outside this repository).

## What changed

| | `HANDOFF2.md` | Now |
|---|---|---|
| Spatial scope | Washington County, OH + 4 neighbours | **Data pulled for 12 Midwest states (1,055 counties); model runs on one state: [STATE TO BE FILLED IN]** |
| Daily rain and Tmin | PRISM, 5 counties (already pulled) | **PRISM, all Midwest counties, 2000–2023 (pulled)** |
| Rain baseline (C) | 2000–2009 | 2000–2009 |
| Train / test | 2010–2018 / 2019–2023 | **2000–2016 / 2017–2023 (recommended; confirm with the mentor)** |
| Exposure | GHSL exported for 5 counties; layers shown in a GEE app | **`log_built_surface` from GHSL, proposed model input; GHSL export done** |
| Neighbour `nb_*` columns | Built for Washington County | Dropped from the plan; they do not carry over to the new scope |

The first version of the new scope was baseline 2000–2009, train 2010–2016, test
2017–2023. Testing below led to the recommendation to train on 2000–2016 instead.

## How Route 2 was chosen

Two routes were compared:

- **Route 1, NOAA:** keep nClimGrid daily rain and Tmin (not in GEE), baseline
  1951–1999.
- **Route 2, GEE:** pull PRISM for 2000–2023, baseline 2000–2009, and take the
  other new inputs from GEE where they exist.

Route 2 fits the mentor's push to stay in GEE. In the test below, the recommended
Route 2 design scored the same as Route 1, so staying in GEE should not cost
predictive skill. PRISM itself is still untested.

### Test

Same 12 reduced inputs plus state and calendar month, tested on 2017–2023,
LightGBM hurdle. **nClimGrid stood in for PRISM**, because the Midwest pull has
not been run, so these rows measure the effect of the years, not of PRISM.

| Design | Training | Rain baseline | ROC-AUC | PR-AUC | Loss in top 5% | MAE |
|---|---|---|---|---|---|---|
| Route 1 | 2000–2016 | 1951–1999 | 0.883 | 0.240 | 0.747 | 0.827 |
| Shorter training only | 2010–2016 | 1951–1999 | 0.876 | 0.216 | 0.663 | 0.803 |
| Route 2 as first proposed | 2010–2016 | 2000–2009 | 0.875 | 0.219 | 0.695 | 0.802 |
| **Route 2, recommended** | **2000–2016** | **2000–2009** | **0.883** | **0.240** | **0.753** | **0.828** |
| Recommended, no housing | 2000–2016 | 2000–2009 | 0.882 | 0.239 | 0.765 | 0.828 |
| Simple guess (county rate) | 2000–2016 | | 0.728 | 0.066 | 0.266 | 0.905 |

"Loss in top 5%" leaves out the largest month, as in `HANDOFF.md`.

- **Training years are what matter.** 2010–2016 has 3,144 damage months against
  7,611 for 2000–2016 (59% fewer). Route 1 beats the first Route 2 design by 0.008
  ROC-AUC (95% interval 0.004 to 0.012).
- **The shorter baseline barely matters for prediction.** Route 1 minus the
  recommended design is −0.001 (−0.002 to 0.000).
- **Housing adds little to these scores:** 0.001 ROC-AUC (0.000 to 0.003).
- **Shorter training has one gain:** predicted damage months are closer to the
  true count (about 1.16–1.18× against 1.35×).

The experiment scripts were in a temporary folder and are not in this repository.
To reproduce the runs, change the baseline and training years in a refit on
`model_panel.csv`, using the scoring code from `hurdle_model.py`.

### Trade-offs of the recommended design

- **Baseline overlap.** 2000–2009 overlaps the training years. It uses rain only
  and ends before the test years, so it leaks no test information. The causal
  equation still needs the rain climate to come first, so it must use 2010–2023.
- **Weak baseline.** 10 annual maxima is the minimum `w_indices.py` accepts. In the
  nClimGrid check, 712 of 1,055 counties (67%) fell back from GEV to Gumbel, so
  fitting Gumbel everywhere would be cleaner. Compared with 1951–1999, the
  county-level `rl10` rank correlation is 0.84 overall and 0.54 within states
  (median).
- **Cost.** About 163 compute hours (24 years × 6.8), over the 150-hour monthly
  Community Tier limit. The 6.8 figure comes from `HANDOFF2.md`, not a new
  measurement.

## Data decisions

| Item | Decision |
|---|---|
| PRISM (`OREGONSTATE/PRISM/ANd`) | **Pulled** for the Midwest, 2000–2023 |
| GHSL built-up (`JRC/GHSL/P2023A/GHS_BUILT_S`) | **Exported**; 5-year images, interpolate between them |
| NFIP flood insurance | **Omitted.** Not in GEE, not required by the equations |
| HMA buyouts and elevations | **Omitted.** Not in GEE, not required by the equations |
| USGS streamflow | **Omitted.** Report as a limitation |
| ERA5-Land, NLCD, MERIT/terrain, SHELDUS | Reuse; no new pull |
| HiHydroSoil (`soil_cd_share`) | Optional and not started; no export script yet |

**Limitations to report:** `wetland_share` is the only adaptation input, which
weakens the causal argument more than prediction. Upstream river flooding is not
measured (9% of damage months had below-median local rain).

## Final variables

| Block | Variables |
|---|---|
| W, same month | `p_month`, `rx5_rl_ratio`, `frost_days` (PRISM); `snowmelt_mm` (ERA5-Land) |
| W, known in advance | `sm_root_pct` (1950–1999 baseline), `swe_mm` (ERA5-Land) |
| C | `c_rx5_rl10_mm` (PRISM, 2000–2009) |
| X | `log_built_surface` (GHSL, proposed), `impervious_mean`, `hand_lt5_share`, `log_land_km2` |
| A | `wetland_share` |
| Controls | calendar month |

The state control drops out, because it is constant within one state. The handout
still shows it, along with the Midwest-wide results. The equations are in the
handout:

- **Equations 1–3:** the hurdle model, for prediction.
- **Equation 4:** a fixed-effects causal model in the style of Gallagher (2014),
  on 2010–2023 with county and state × year-month effects. It uses raw `rx5`
  plus `rx5 × C`, and cannot forecast.

## Pull commands

**The team reports these pulls are done.** The commands are kept as a record of
what was planned; the exact accounts and commands used were not recorded. If a
pull has to be repeated, run it from the repository root. `SECOND_PROJECT` is the
second account's Earth Engine project ID. Check first that Google's terms allow
splitting one job across accounts; this was not confirmed. Quota is tracked by
Cloud project, as far as could be checked, so the second account needs its own
registered project.

```powershell
# Account 1: largest pull, 17 tasks, about 116 hours
earthengine authenticate --force
python prism_export.py prism --project flood-513221 --start 2000 --end 2016 --folder gee_prism_midwest

# Account 2: PRISM 7 tasks, about 48 hours; GHSL 7 tasks, smallest
earthengine authenticate --force
python prism_export.py prism --project SECOND_PROJECT --start 2017 --end 2023 --folder gee_prism_midwest
python yana_workspace/ghsl_export.py --project SECOND_PROJECT --start 1995 --end 2025

earthengine task list
```

Download the PRISM CSVs to `data/gee_prism_midwest/` and the GHSL CSVs to
`data/gee_ghsl/`. **Do not put PRISM Midwest files in `data/gee_prism39167/`:**
`w_indices.py` reads every CSV in its folder and keeps only the first copy of each
date, so mixing the two would silently drop counties.

## Rebuilding the panel after the pulls

Copy `model_panel.csv` to `model_panel_noaa.csv` first to keep the NOAA version.

```powershell
python w_indices.py --input data/gee_prism_midwest --out-dir out/prism_midwest/ --base-start 2000 --base-end 2009 --model-start 2000 --model-end 2023
python build_panel.py --era5 data/gee_era5 --nlcd data/gee_nlcd --terrain data/gee_terrain --w out/prism_midwest/w_county_month.csv --out panel_county_month.csv
python merge_panel.py
```

These have not been run on the Midwest PRISM files. Check for missing values in the
first months of 2000, because PRISM starts on 2000-01-01. They build all 1,055
counties; filter to the chosen state afterwards, using the first two digits of
`GEOID`.

## Work done this session

| File | What it is |
|---|---|
| [ghsl_export.py](ghsl_export.py) | New: GHSL built-up area by county, one task per 5-year image. Output `ghsl_county_<year>.csv` with `GEOID, year, built_m2`. Image IDs and bands checked for 1995, 2020 and 2025. Committed in `ffe9c6f`. Its Midwest output files were not in `data/` when this was written |
| `Summary Guides/data_route_plan_summary.tex` and `.pdf` | 7-page handout (outside the repository) |
| `model_panel.csv` and other git-ignored outputs | Rebuilt from NOAA data on 2026-11-06: 303,840 rows × 53 columns, no missing values |

`lightgbm` and `scikit-learn` are not installed in the main Python environment.
They were installed only in a temporary folder for the test.

## Next steps

1. Fill in the chosen state everywhere this file says [STATE TO BE FILLED IN].
2. Confirm with the mentor: the single-state scope, the GEE-only rule, omitting
   NFIP and HMA, and training on 2000–2016 with an overlapping baseline.
3. Download the PRISM and GHSL files to `data/gee_prism_midwest/` and
   `data/gee_ghsl/`, then check that every year and county is present.
4. Compare PRISM with nClimGrid on county-month rain.
5. Add `log_built_surface` to the panel. `build_panel.py` does not do this yet:
   interpolate the GHSL images to yearly values, take year − 1, then log.
   `build_county_panel.py` already interpolates GHSL for the 5-county design, so
   check whether that code can be reused.
6. Rebuild the panel, filter to the state, and check the damage months in each
   split.
7. Refit LightGBM and the GLM on the final variables and compare them with the
   simple baseline for that state.
8. Decide whether to fit Gumbel for every county in `w_indices.py`.
9. Run the BYM2 spatial model, then Equation 4.

## Update: single-state scope

After the Route 2 decision, the 2000–2023 Midwest PRISM data was pulled, the GHSL
export was done, and the scope changed so that the model runs on **one specific
state: [STATE TO BE FILLED IN]**.

- **Data:** no new pull should be needed. The state's counties are a subset of the
  Midwest files, as long as both exports cover them.
- **Results above:** the route comparison and the 2,234 test damage months are for
  all 1,055 counties. **They do not carry over automatically to one state.** Redo
  them on the state's counties.
- **Model size:** one state has far fewer damage months, so check the counts in each
  split before choosing the model and its settings.
- **State differences:** one state avoids mixing states' reporting practices, but
  a reporting change inside that state, like Iowa's drop after 2016, stays in
  the data. `state × year-month` effects in Equation 4 become plain `year-month`
  effects.
- **Handout:** `data_route_plan_summary.pdf` still describes the full Midwest and
  has not been updated for this scope.

## Caveats

- **The test years were used to compare designs.** The project's rule is to score
  2017–2023 once. Treat the table above as a design check, and repeat the choice
  on 2013–2016 before reporting final scores.
- **Limited uncertainty.** Intervals resample counties, not years, and each
  LightGBM model used one seed.
- **Dollar ranking is unstable.** The GLM's top-5% score moved between 0.51 and
  0.69 across designs, and the reduced GLM scored 0.53 against 0.74 for the
  17-input GLM. Use LightGBM for this score, and be ready for this question if
  presenting the GLM equations. The reason for the GLM drop was not investigated.
- **Same-month rain is a perfect-forecast assumption.** All designs use observed
  rain for the month being predicted.
- **The hurdle model is not spatial yet.** It does not know which counties are
  neighbours.
- **`reduced_variables.md` is out of date.** It still lists nClimGrid and a
  1951–1999 baseline.

## Working notes

- Project ID: `flood-513221`.
- SHELDUS has months: the outcome comes from
  `direct_loss_aggregated_output_32423.csv`, which has a `Month` column.
  `loss_output_year_county.csv` is only used as a check.
- Commit only when asked.
