# Handoff: Flood Impact Forecasting (CSE 472, Project 2)

Read this first when picking up the project in a new session. It summarizes the
work through 2026-11-01 on branch `enci-dev` (pull request #1 into `main`).

**Newest work:** [Midwest explorer app (2026-11-13)](#midwest-explorer-app-2026-11-13).
**Before that:** [Climate and adaptation adjustment (2026-11-10 to 2026-11-11)](#climate-and-adaptation-adjustment-2026-11-10-to-2026-11-11),
then [Latest session (2026-11-08 to 2026-11-09)](#latest-session-2026-11-08-to-2026-11-09)
below, then `yana_workspace/HANDOFF2.md` to `HANDOFF4.md` (the teammate's sessions: 5-county
design, Route 2 with PRISM, the PRISM refit). The sections after the latest session describe the
original NOAA design and are kept as history.

## Midwest explorer app (2026-11-13)

The Missouri explorer is extended to all 12 states. Everything new is in
`yana_workspace/gee_app/Midwest/`; the Missouri app in `missouri_tester/` is unchanged. Decisions
(agreed with the team): predictions for the **2017-2023 test years only** (as Missouri; earlier
years would be in-sample), from **one LightGBM trained on all 12 states**, **rank and top 5% within
each state** plus a Midwest-wide rank, and a **state selector** with an "All 12 Midwest states"
option.

### Files in `yana_workspace/gee_app/`

| File | What it is |
|---|---|
| `missouri_tester/build_app_table.py`, `flood_explorer_app.js`, `mo_flood_app_table.csv`, `flood_explorer_app_guide.tex/.pdf` | Missouri app (unchanged). `midwest_flood_impact/flood_explorer.js` is the same app with another `ASSET_ID` |
| `Midwest/build_midwest_app_table.py` | New: builds the Midwest table |
| `Midwest/midwest_flood_app_table.csv` | New: 88,620 rows (1,055 counties x 84 months, 2017-01 to 2023-12), 32 columns, 17.5 MB, no missing values |
| `Midwest/flood_explorer_app2.js` | New: the Midwest explorer, adapted from `flood_explorer_app.js` |

### `build_midwest_app_table.py`

```powershell
pip install lightgbm scikit-learn
python yana_workspace/gee_app/Midwest/build_midwest_app_table.py                    # refit and write the table
python yana_workspace/gee_app/Midwest/build_midwest_app_table.py --adaptation-only  # refresh adaptation columns only
```

- Loads `model_panel.csv` with `reduced_benchmark.load()` for all 12 states (state is an input),
  chooses tree counts on 2000-2012 -> 2013-2016, refits on 2000-2016 with 15% more trees
  (546 and 436) and predicts 2017-2023: the same steps as `reduced_benchmark.py` without `--state`.
- Stops unless the test scores match `results/midwest_prism/scores.csv`. They match exactly:
  ROC-AUC 0.8910, PR-AUC 0.2651, MAE 0.8315.
- Joins the adaptation columns with `add_adaptation()` imported from
  `missouri_tester/build_app_table.py` (one copy of that join; values from year - 1).
- Prints the counties and top-5% size per state and the 1st/99th percentiles used for the app's
  colour ranges.

### How the columns match `mo_flood_app_table.csv`

Every column of the Missouri table, with the same name, units and meaning, plus two:

| Columns | Same as Missouri? |
|---|---|
| `key` (`G` + 5-digit GEOID), `year`, `month`, `ym`, `ym_label`, `has_damage`, `actual_loss`, `log10_actual_loss` | Same |
| The 12 model inputs: `p_month`, `rx5_rl_ratio`, `snowmelt_mm`, `frost_days`, `sm_root_pct`, `swe_mm`, `c_rx5_rl10_mm`, `log_built_surface`, `impervious_mean`, `hand_lt5_share`, `log_land_km2`, `wetland_share` | Same (units the model sees) |
| `p_damage`, `expected_loss`, `loss_if_damage`, `log10_expected_loss` | Same meaning, but from the 12-state model, so Missouri's values differ from `mo_flood_app_table.csv` |
| `rank`, `top5` | Same meaning: rank **within the county's state** each month; `top5` = top 5% of that state's counties, `round(0.05 x counties)`: MO 6; IA, IL, IN, KS, NE 5; MI, MN, OH, WI 4; ND, SD 3 |
| `nfip_policies_per_hu`, `crs_best_class`, `median_income`, `built_pre1980_share` | Same (year - 1) |
| **`state`** (new, second column) | Two-letter state code; the app filters on it |
| **`rank_midwest`** (new, after `top5`) | Rank by expected loss among all 1,055 counties that month |

Rows are sorted by `ym`, `state`, `rank`. Each state's top 5% catches 51% of test-year loss.

### How `flood_explorer_app2.js` is set up

Same layout, layer groups, county details and chart as `flood_explorer_app.js`. Changes:

- **`ASSET_ID`** = `projects/flood-513221/assets/midwest_flood_app_table` (upload the CSV there,
  or change it).
- **`STATES` table** at the top: FIPS, name, county count and top-5% size for each state;
  `N_MIDWEST = 1055`.
- **State selector** (Missouri by default, any state, or "All 12 Midwest states"). `setState()`
  sets `counties` (TIGER counties of that state, or all 12) and `stateRows` (the table filtered on
  `state`, so the monthly join only touches that state's rows). Changing state zooms the map,
  clears the selected county and redraws; the title follows the state. The All view adds state
  borders.
- **Prediction layers:** "Rank within the state" colours 1 to the selected state's county count
  (115 in the All view); new **"Rank across the Midwest"** layer uses `rank_midwest` (1 to 1,055).
- **Top-5% outline:** the selected state's top counties; in the All view, each state's top 5%.
  The checkbox label updates with the count.
- **County details:** heading names county and state; shows "Rank in <state>: r of n (top 5%)"
  and "Rank in the Midwest: r of 1,055".
- **Colour ranges** reset from the Midwest table's 1st-99th percentiles, since Missouri's cut off
  much of the region: snowmelt 0-65 mm, snowpack 0-80 mm, 10-year 5-day rain 65-210 mm, built
  surface 13.4-18.7, land area 6.2-8.8, wetland share 0-30%, insurance 0-5 per 100 homes, income
  $40k-$110k, pre-1980 28-87%; raster snowpack 0-100 mm, snowmelt 0-70 mm, elevation 100-1,000 m.
- **Raster layers** clip with `clipToCollection(counties)` (cheaper than a 1,055-county
  geometry); the 3DEP mosaic is filtered to the selected counties.
- "About the predictions" text describes the 12-state model; the CRS note says about 200 of
  1,055 counties take part.

Syntax-checked with `node --check`; **not yet run in the Code Editor.**

### Next steps

1. Upload `Midwest/midwest_flood_app_table.csv` as a table asset at `ASSET_ID`, run
   `flood_explorer_app2.js`, and check the All view (1,055 counties, slower) and the Elevation
   and land-cover rasters over the whole region.
2. Re-upload `missouri_tester/mo_flood_app_table.csv` too (adaptation columns; see below).
3. Optional: SHAP values or partial dependence plots for LightGBM, to show its storm and exposure
   effects point the same way as b1 and b2 of the adjustment regressions.

Write-ups for this and the adjustment are outside the repository, in
`Project 2/Summary Guides/`: `adjustment_models_summary.pdf` (models M0-M4 and the log) and
`meaningful_coefficients_summary.pdf` (which coefficients are meaningful, why LightGBM has none).

## Climate and adaptation adjustment (2026-11-10 to 2026-11-11)

The instructor's one-pager (*Flood impact: adjusting for climatology and adaptation*, 10 Nov
2026) replaces the "Equation 4" plan. It asks for five nested regressions on the same rows, to
see whether controlling for rain climate (C) and adaptation (A) changes the storm effect. This is
a separate analysis for interpretation; it does not change the forecast model or the app.

### Design (`adjustment_models.py`)

`log10(loss) = b1 storm + b2 exposure + c climate + a adaptation + d (storm x adaptation) + rest`,
ordinary least squares with standard errors clustered by county.

| Part | Variables |
|---|---|
| Sample | Damage months only (log10 loss is undefined at zero), model years 2011-2023. NFIP and CRS are joined with a one-year lag, so the 2010-2022 tables cover exactly these years. Same rows in every model (complete cases on the M4 set) |
| Storm (b1) | `rx5_rl_ratio` = wettest 5 days of the month / county's 10-year 5-day level |
| Exposure (b2) | `log_built_surface` |
| Climate (c) | `c_rx5_rl10_mm` / 10, so c is per 10 mm |
| Adaptation (a, d) | `nfip_policies_per_hu`, `log_median_income`, `built_pre1980_share`, `wetland_share`, `crs_credit` = 10 - `crs_best_class` (so higher = better prepared; CRS class 1 is best, 10 = not in CRS). Each scaled to mean 0, std 1 on the fitted rows. Higher `built_pre1980_share` means *less* prepared |
| Rest (every model) | `sm_root_pct`, `log_swe_mm`, `frost_days`, `log_p_month`, `hand_lt5_share`, `log_land_km2`, month and state effects. `log_snowmelt_mm` dropped (`--drop`): it correlates 0.85 with `log_swe_mm` and 0.86 with `frost_days`; dropping it moved b1 by 0.01 and each d by under 0.01 |
| Models | M0 rest only; M1 + climate; M2 + adaptation; M3 + both; M4 = M3 + storm x each adaptation variable |

CRS comes from `crsClassCode` on the NFIP policies (`openfema_features.py`, `data/clean/crs_county_year.csv`).
Only 200 of 1,055 counties (12 of Missouri's 115) ever have a class better than 10.

```powershell
python merge_panel.py      # after openfema_features.py, so the panel has crs_best_class
python adjustment_models.py --drop log_snowmelt_mm --out-dir results/adjustment_midwest
python adjustment_models.py --state MO --drop log_snowmelt_mm --out-dir results/adjustment_missouri
```

Outputs per folder: `coefs.csv`, `summary.csv` (the one-pager's Step 3 table), `correlations.csv`,
`sample.csv`, `log.txt` (with report sentences) and three plots: `plot_storm_coef.png`,
`plot_climate_bars.png`, `plot_damage_curves.png`. The committed logs were written before the
report sentences were reworded (storm per 0.1, interval-aware wording); rerun to refresh them.

### Results

| | 12 states (4,698 damage months, 883 counties) | Missouri (415, 80 counties) |
|---|---|---|
| b1 storm, M0 -> M3 (SE) | 1.20 -> 1.16 (0.07) | 1.24 -> 1.32 (0.22) |
| Loss per 0.1 more storm, M0 -> M3 | 1.32x -> 1.30x | 1.33x -> 1.36x |
| c climate per 10 mm, M1 / M3 | -0.014 (0.012) / -0.012 (0.012) | +0.038 (0.019) / +0.045 (0.018) |
| d storm x insurance | **-0.095 (0.045)** | -0.168 (0.151) |
| d storm x pre-1980 housing | -0.154 (0.042) | 0.038 (0.172) |
| d storm x income / wetlands / CRS | none clearly nonzero | none clearly nonzero |

- **The storm effect hardly changes after adjusting** (both regions; changes under one SE). The
  one-pager's illustration (0.60 -> 0.75) does not appear in this data. Report it as a finding.
- **Climate:** no clear effect given the storm across the 12 states. In Missouri, wetter-climate
  counties lose somewhat more, and only clearly so once adaptation is in (M3), so adaptation does
  not explain the climate coefficient. Do not report a "% explained".
- **Insurance is the one adaptation result:** the same storm does less damage where more homes are
  insured (12 states, about 2 SE; Missouri same sign, not significant). Read it from d, not a:
  in Missouri a for insurance is +0.29 in M4, because risky counties buy more insurance.
- **Pre-1980 housing** has a clear d in the 12 states but in the unexpected direction (older stock,
  less extra damage per storm), probably rural, less exposed counties. Flag, do not interpret as
  adaptation. Missouri shows nothing.
- Missouri alone has wide intervals (SE about 3x the 12-state run). Lead with the 12-state run.

### Earth Engine apps

The forecast layers are unchanged: the apps show the LightGBM forecast model, which still uses
`snowmelt_mm` (the drop applies to the adjustment regressions only).

**Added 2026-11-11:** an "Adaptation (county values)" layer group in the explorer (both copies:
`midwest_flood_impact/flood_explorer.js` and `yana_workspace/gee_app/missouri_tester/flood_explorer_app.js`,
which differ only in `ASSET_ID`), for the one-pager's side-by-side maps of climate
("10-year 5-day rain"), adaptation and loss:

| Layer | Column | Colour range |
|---|---|---|
| Flood insurance | `nfip_policies_per_hu` (shown per 100 homes) | 0 to 4 |
| Community Rating System class | `crs_best_class` (darker = better; 10 = not in CRS) | 5 to 10 |
| Median household income | `median_income` (2024 dollars) | $35k to $100k |
| Homes built before 1980 | `built_pre1980_share` | 20% to 87% |
| Wetland share | `wetland_share` (also a model input) | 0 to 8.5% |

Clicking a county also lists these values. All are from year - 1, as in `merge_panel.py`.
`build_app_table.py` adds the four new columns from `data/clean/`;
`--adaptation-only` adds them to the existing table without refitting the model. The committed
`mo_flood_app_table.csv` now has them (other columns unchanged). **Re-upload the CSV** to the
Earth Engine table asset, or the new layers come up blank.

### Next steps

1. ~~Rerun both adjustment commands to refresh `log.txt` with the reworded sentences.~~ Done
   (`30c4532`).
2. Tell the instructor the expected pattern (storm effect larger after adjusting, negative climate
   coefficient) does not appear, and that insurance is the only clear adaptation effect.
3. Re-upload `mo_flood_app_table.csv` to the Earth Engine asset and check the Adaptation layers.
4. Optional: a check with insurance as the only A variable.

## Latest session (2026-11-08 to 2026-11-09)

Scope is now **Missouri** (state FIPS 29, 115 counties), with the data and the Midwest-wide runs
kept for all 12 states. Inputs follow `yana_workspace/HANDOFF3.md` (PRISM rain with a 2000–2009
baseline, GHSL exposure). Train 2000–2016, test 2017–2023. The mentor now allows data from
outside Earth Engine if each source and variable is justified.

### Where things stand (summary)

| Topic | Decision or result | Status |
|---|---|---|
| Main model for Missouri | LightGBM hurdle trained on all 12 states, scored on Missouri (`reduced_benchmark.py --score-state MO`); GLM on Missouri only | Chosen on 2013–2016 validation |
| Over-prediction | Rolling per-state recalibration (`recalibrate.py`): Missouri LightGBM 1.61× → 0.99× actual damage months | Done; not yet in the app table |
| Chance of damage | Works: test ROC-AUC 0.90–0.91 vs 0.75 for county history | Report as the main result |
| Dollars and rank | Weak (within 2× of recorded loss in 24% of damage months); mostly a SHELDUS problem (split multi-county losses) | Report as indicative |
| OpenFEMA | Pulled and built; buyouts add nothing; NFIP only usable 2010+ (Equation 4) | Done |
| Variable documentation | `docs/flood_variable_reference.xlsx` updated to PRISM, GHSL and OpenFEMA | Done; `reduced_variables.md` still old |
| Equation 4 | Replaced by the climate and adaptation adjustment (above) | Done 2026-11-11 |
| BYM2, loss-data checks | Not started | Next |

### Files added or changed

| File | What it is | Committed |
|---|---|---|
| `ghsl_features.py` | New: interpolates the 5-year GHSL images to yearly `built_m2` in `data/clean/ghsl_county_year.csv` | `9cdc75f`; path fix in `3f8c6b1` |
| `merge_panel.py` | Joins `ghsl_county_year.csv` (one-year lag) and adds `log_built_surface`; default rain climate is now PRISM 2000–2009. Replaces `yana_workspace/temp_merge_panel.py` (identical 55 columns) | `9cdc75f`; PRISM default in `3f8c6b1` |
| `yana_workspace/temp_merge_panel.py` | **Deleted** (replaced by `merge_panel.py` + `ghsl_features.py`) | Deleted in `3f8c6b1` |
| `state_model.py`, `results/state_MO_scores.csv`, `results/predictions_MO.csv` | **Deleted.** Was a one-state hurdle script plus a 12-state LightGBM; replaced by `reduced_benchmark.py` (`--state`, `--score-state`). Its results are kept in the table below | Deleted in `3f8c6b1` |
| `yana_workspace/gee_exposure_app.js` | Rewritten Earth Engine app: any of the 12 states (Missouri default), year and month; one layer per final input; model layers from the teammate's `mo_flood_app_table.csv` uploaded as a table asset. Syntax-checked, not yet run in the Code Editor | `9cdc75f`; table switch in `3f8c6b1` |
| `openfema_features.py` | New: builds `data/clean/nfip_policies_county_year.csv` and `hma_county_year.csv` from OpenFEMA downloads | `3f8c6b1` |
| `reduced_benchmark.py` | `--openfema buyouts` adds buyouts only; plain `--openfema` still adds NFIP and buyouts. `--score-state MO` fits all 12 states and scores Missouri only (`results/missouri_pooled/`) | `3f8c6b1` |
| `docs/flood_variable_reference.xlsx` | Replaces `docs/variable_reference.xlsx` (deleted). Updated to Route 2: PRISM source and 2000–2009 baseline for W and C; new row for `built_m2, log_built_surface` (GHSL); OpenFEMA rows filled in (NFIP v3, current HMA datasets, coverage gaps); new column K for the final model's inputs; Datasets, Blocks and Notes sheets updated | `3f8c6b1` |
| `recalibrate.py` | New: per-state recalibration (fix for over-prediction), scored on 2019–2023 | `3f8c6b1` |
| `results/*_prism_buyouts/`, `results/recalibration_*/`, `results/missouri_pooled/` | Scores and logs from the runs below | `3f8c6b1` |
| `data/clean/nfip_policies_county_year.csv`, `data/clean/hma_county_year.csv` | OpenFEMA tables from `openfema_features.py` | `3f8c6b1` |
| `.gitignore` | Ignores `data/openfema/raw/` (4 GB) and `model_panel_openfema.csv` (no longer needed) | `3f8c6b1` |
| `data/openfema/README.md` | Rewritten: download, build, coverage limits, results | `3f8c6b1` |

### Missouri model: my run and the teammate's

Both builds give the same panel. Only the LightGBM settings differ (teammate: 31 leaves, at least
100 rows per leaf; `state_model.py`, since deleted: 15 leaves, 50/20 rows, monotone in rain). Test 2017–2023,
174 damage months; "top 5%" = the share of loss in the top 6 counties each month, without the
largest month:

| Model | ROC-AUC | PR-AUC | Top 5% | MAE |
|---|---|---|---|---|
| Baseline | 0.748 | 0.066 | 0.124 | 0.966 |
| GLM (both) | 0.895 | 0.238 | 0.478 | 0.781 |
| LightGBM, teammate (`reduced_benchmark.py`) | 0.902 | 0.281 | 0.449 | 0.761 |
| LightGBM, `state_model.py` | 0.906 | 0.270 | 0.236 | 0.731 |
| LightGBM trained on 12 states, scored on Missouri (`state_model.py` settings) | 0.910 | 0.284 | 0.441 | 0.727 |

- **Whether damage occurs works** (+0.15 ROC-AUC over the baseline, interval about +0.12 to
  +0.20). The ROC-AUC differences between the LightGBM versions are within noise.
- **Dollars are weak.** Expected loss is within 2× of the recorded loss in 24% of damage months.
  Two months hold 82% of test loss: July 2022 (all of it caught in the top 6) and April 2017
  (18% caught; a river flood that local rain misses).
- **One state alone is too thin for the dollar part.** Use the teammate's settings or train on all
  12 states. On 2013–2016 the GLM ranks dollars much better than LightGBM, so the dollar ranking
  should come from the GLM or an average of the two (decide on 2013–2016, not on the test years).

**12-state training, checked on 2013–2016** (`reduced_benchmark.py --score-state MO` against
`--state MO`; Missouri's 182 validation damage months):

| Model | Trained on | ROC-AUC | PR-AUC | Brier skill | Pred ÷ actual | AUC within month | Top 5% (all months) | Top 5% (without largest) | MAE |
|---|---|---|---|---|---|---|---|---|---|
| GLM | Missouri | 0.915 | 0.433 | 0.259 | 1.01 | 0.853 | 0.799 | 0.474 | 0.776 |
| GLM | 12 states | 0.917 | 0.385 | 0.228 | 1.02 | 0.839 | 0.799 | 0.424 | 0.819 |
| LightGBM | Missouri | 0.916 | 0.299 | 0.182 | 0.89 | 0.872 | 0.103 | 0.469 | 0.758 |
| LightGBM | 12 states | 0.921 | 0.439 | 0.258 | 1.20 | 0.858 | 0.791 | 0.416 | 0.718 |

Adopt 12-state training **for LightGBM** (better PR-AUC, Brier skill, dollar error, and it catches
the largest validation month that the Missouri-only model missed); its slightly higher
over-prediction is what recalibration fixes. **Keep the GLM on Missouri only**: pooling makes it
worse on PR-AUC and dollars. The earlier test-year claim that 12-state training doubles the dollar
ranking (0.44 vs 0.24) compared against the weaker `state_model.py` settings; against the
teammate's Missouri-only LightGBM the test-year values are equal (0.452 vs 0.449).

### OpenFEMA data (adaptation, A)

The datasets first planned (NFIP Policies v2, HMA Mitigated Properties and Projects v4) were
**removed by FEMA on 2026-10-15**. `openfema_features.py` uses the replacements (full details in
`data/openfema/README.md`):

| Table | Source | Coverage |
|---|---|---|
| `nfip_policies_county_year.csv`: policies in force on July 1 | NFIP Redacted Policies v3, bulk file `NfipPoliciesV3.parquet` (3.7 GB). The API is too slow for 3.7M Midwest rows | **No policy starts before 2009.** 2010–2022 complete; 1999–2009 left empty, not zero |
| `hma_county_year.csv`: cumulative acquisitions and elevations | HMA Subapplications Project Site Inventories v1 (county, activity) joined to HMA Subapplications v2 (fiscal year, status) | **No funded sites 2005–2019** in the current FEMA data: 14,638 buyouts by 2022, almost all from the 1990s |

Pull (FEMA refuses Python's downloader; curl or a browser works):

```powershell
New-Item -ItemType Directory -Force data/openfema/raw
curl.exe -L -o data/openfema/raw/NfipPoliciesV3.parquet "https://www.fema.gov/about/reports-and-data/openfema/v3/NfipPoliciesV3.parquet"
curl.exe -L -o data/openfema/raw/HmaSubapplicationsProjectSiteInventories.csv "https://www.fema.gov/api/open/v1/HmaSubapplicationsProjectSiteInventories.csv"
curl.exe -L -o data/openfema/raw/HmaSubapplications.csv "https://www.fema.gov/api/open/v2/HmaSubapplications.csv"
python openfema_features.py
```

Checks: Missouri has 24,537 policies in force in 2010 and 17,111 in 2022, Illinois about 48,000;
compare with FEMA's published totals. 91% of HMA sites have no county code and are matched by
county name; 19 of 14,906 funded sites could not be matched.

**Buyouts add nothing** (`--openfema buyouts`, both regions). Validation 2013–2016 scores move by
0.02 or less except one Midwest LightGBM top-5% value (0.671 to 0.721) that no other score
supports; LightGBM ranks buyouts last (under 1% of gain). The GLM coefficient is slightly
positive (+0.07 in Missouri): buyouts mark counties flooded in the 1990s, not protected ones
(C → A confounding). **NFIP cannot enter the 2000–2016 model** (missing for model years
2000–2010); use it in Equation 4 (2010–2023).

### Recalibration (over-prediction)

`recalibrate.py` shifts each state's log-odds so predicted damage months match observed ones:
"fixed" is fitted on 2017–2018, "rolling" refits each year on the two years before it. Scored on
2019–2023. Predicted ÷ actual damage months:

| | Missouri GLM | Missouri LightGBM | Midwest GLM | Midwest LightGBM |
|---|---|---|---|---|
| No correction | 1.98 | 1.61 | 1.54 | 1.48 |
| Fixed | 0.70 | 0.96 | 0.91 | 0.91 |
| Rolling | 0.92 | 0.99 | 0.95 | 0.95 |

- Midwest LightGBM Brier skill rises from 0.137 to 0.173; ROC-AUC and within-month AUC move by
  under 0.01, because the shift does not reorder counties within a state.
- **Rolling is the better default:** the fixed shift learns from two years and over-corrects small
  states (South Dakota 0.16, Nebraska and Michigan about 0.5); rolling keeps every state within
  0.39–1.31 and uses only past years.
- Single years still swing (2021 is 1.6–2× too high, 2019 0.65×).
- The Missouri LightGBM top-5% score jumps from 0.08 to 0.59 with the fixed shift. That is one
  county in August 2023 entering the top 6; July 2022 holds 80% of 2019–2023 Missouri loss.
  **Not a real gain.**

### Loss data

The teammate's conclusion (HANDOFF4) stands: the main limit is SHELDUS, especially multi-county
losses split equally (42% of damage rows share another county's exact dollars). Options, none
started:

1. Train on all 12 states and score Missouri: **done** (`reduced_benchmark.py --score-state MO`);
   adopted for LightGBM, not for the GLM (table above).
2. Predict loss classes (none, < $100k, $100k–$1M, > $1M) instead of exact dollars, and flag split
   losses (same dollars as other counties in the state and month) to down-weight them or score
   them as one event.
3. Check SHELDUS against **NFIP Claims v3** (`https://www.fema.gov/api/open/v3/NfipClaims`, 51,304
   Missouri claims with date of loss and damage) or NOAA Storm Events. Claims are an outcome
   check only, **never an input**, and only cover insured property.
4. More years: 1985–1999 has 10,592 SHELDUS damage months (2000–2016 has 7,611). This needs no
   new rain pull if the whole design switches to nClimGrid (on disk for 1951–2023; scored the same
   as PRISM in HANDOFF3) with a 1951–1984 baseline; NLCD and GHSL would need small exports for
   1985–1998. Do not mix PRISM and nClimGrid across years. Older SHELDUS dollars are rougher.

### Rebuild commands (this session)

The full rebuild from the Earth Engine and NOAA downloads, run from the repository root
(`pip install lightgbm scikit-learn pyarrow` first):

```powershell
python data_clean.py; python housing_features.py; python build_monthly_panel.py
python w_indices.py --input data/gee_prism_midwest --out-dir out/prism_midwest/ --base-start 2000 --base-end 2009 --model-start 2000 --model-end 2023
python build_panel.py --era5 data/gee_era5 --nlcd data/gee_nlcd --terrain data/gee_terrain --w out/prism_midwest/w_county_month.csv --out panel_county_month.csv
python census_features.py
python ghsl_features.py
python openfema_features.py        # optional; needs the downloads in data/openfema/raw/
python merge_panel.py              # model_panel.csv: PRISM climate by default, every data/clean/ table
python reduced_benchmark.py --out-dir results/midwest_prism
python reduced_benchmark.py --state MO --out-dir results/missouri_prism
python reduced_benchmark.py --score-state MO --out-dir results/missouri_pooled
python reduced_benchmark.py --openfema buyouts --state MO --out-dir results/missouri_prism_buyouts
python reduced_benchmark.py --openfema buyouts --out-dir results/midwest_prism_buyouts
python recalibrate.py --state MO --out-dir results/recalibration_missouri
python recalibrate.py --out-dir results/recalibration_midwest
python yana_workspace/gee_app/missouri_tester/build_app_table.py
```

`merge_panel.py` now defaults to the PRISM 2000–2009 climate (`out/prism_midwest/`), so it
replaces `yana_workspace/temp_merge_panel.py` (deleted; same 55 columns, checked identical).
It joins every table in `data/clean/`, so `model_panel.csv` also carries the four OpenFEMA
columns; the models use them only with `--openfema`. The separate `model_panel_openfema.csv` used
for the buyout runs is no longer needed. For the NOAA panel, pass
`--thresholds out/w_county_thresholds.csv`.

### Caveats

- **The test years have been scored many times** (route tests, two Missouri runs, buyouts,
  recalibration on 2019–2023). Make every remaining choice on 2013–2016.
- Two Earth Engine apps exist: `yana_workspace/gee_exposure_app.js` (input layers, any of the 12
  states) and `yana_workspace/gee_app/missouri_tester/flood_explorer_app.js` (model outputs for
  Missouri). Both read the same `mo_flood_app_table.csv`. Keep one or merge them.
- GHSL interpolation lets a year draw on the next 5-year image (mild look-ahead).

### Next steps

1. Committed and pushed in `3f8c6b1`. Tell the teammate: it deletes their
   `temp_merge_panel.py` and edits their `reduced_benchmark.py`, `cleaned_items/used_files.md`
   and `HANDOFF2.md` to `HANDOFF4.md`; OpenFEMA is done.
2. One pipeline: **done** (2026-11-09). `temp_merge_panel.py` and `state_model.py` are deleted;
   `merge_panel.py` defaults to PRISM, and `reduced_benchmark.py --score-state` replaces the
   12-state part of `state_model.py` (its monotone constraints were not carried over). Still to
   decide with the teammate: one Earth Engine app.
3. Add rolling recalibration to `reduced_benchmark.py --score-state` output and rebuild the app
   table from the 12-state LightGBM (`yana_workspace/gee_app/missouri_tester/build_app_table.py`;
   agree with the teammate first).
4. Choose on 2013–2016 where the dollar ranking comes from: GLM, LightGBM or their average.
   (Missouri-only vs 12-state training is decided: 12 states for LightGBM.)
5. Ask the mentor (see below), then: loss classes and the split-loss flag; NFIP claims check.
6. Equation 4: **done** as `adjustment_models.py` (see the newest section). Still open: the confounding simulation;
   BYM2 for Missouri in R-INLA (teammate, HANDOFF4).
7. Update `reduced_variables.md` (describes the old setup). `data/openfema/README.md` is current
   (rewritten 2026-11-09).
8. Score the final models on 2017–2023 once, after all choices, and say in the report that the
   test years were used for earlier design checks.

**Open questions for the mentor:** Missouri as the scope, with LightGBM trained on all 12 states;
training on 2000–2016 with the overlapping 2000–2009 baseline; OpenFEMA given its coverage gaps
(buyouts as a reported null result, NFIP only in Equation 4); loss classes instead of exact
dollars; NFIP claims as a check or a second outcome; whether chance of damage and rank, with
indicative dollars, is an acceptable headline.

## Original design (through 2026-11-01, history)

**Status (2026-11-01):** the county-month data pipeline is built, merged and
reproducible: rebuilding every output from the raw data gives byte-identical
files. The modelling table `model_panel.csv` has the outcome, hazard, exposure,
terrain, rain climate and census/ACS variables for all 1,055 counties × 288
months. The first hurdle model and a model comparison are done (results below;
LightGBM hurdle is the chosen main model). Still missing: the flood-insurance,
buyout and soil tables, models that use the census columns, and the remaining
models.

## The task

Build the **impact model** τ(w; x, c) from the course slides: given how hard a
flood hits a county (W), what is exposed (X) and the county's long-run flood
climate (C), predict its property loss, so counties can be **ranked** for
emergency resources. Evaluation from the slides: train on 2000–2016, test on
2017–2023, use only pre-event information, and check the method on simulated
losses with a known answer.

The slides frame it causally: a plain regression learns E[Y | W, X], but the goal
is E[Y | do(W), X, C]. The backdoor path is W ← C → A → Y: counties that flood
often get stronger floods *and* adapt more (A).

Background reading: Merz et al. (2020), *Impact Forecasting to Support Emergency
Management of Natural Hazards*, Reviews of Geophysics, doi:10.1029/2020RG000704.

## Study design (agreed 2026-10-29)

| Decision | Choice |
|---|---|
| Unit of analysis | County × month |
| Region | 12 Midwest states (FIPS 17, 18, 19, 20, 26, 27, 29, 31, 38, 39, 46, 55), 1,055 counties (2018 county list) |
| Period | 2000–2023; train 2000–2016, test 2017–2023 |
| Events | All flooding in SHELDUS (hazard = Flooding), property damage in 2024 dollars |
| Outcome | `direct_loss_aggregated_output_32423.csv` (SHELDUS by county and month) |
| Inputs | Never from SHELDUS. Time-varying inputs at monthly or finer resolution, known before the month (yearly tables use year − 1); static inputs allowed |
| C (flood climate) | 1951–1999 rain climate from NOAA nClimGrid, before the study years and independent of losses |
| Spatial unit | County boundaries, not NOAA climate divisions |

Labels: in this project C means **rain climate** (the confounder on W ← C → A → Y).
Terrain and soils are **susceptibility** and are grouped with X. The
teammate's data guide calls terrain and soils "C"; use the definition here in
the write-up.

## Instructor feedback (Saketh Vishnubhatla, on the findings report)

- SHELDUS supplies the outcome only; all inputs come from other sources.
- Choose variables from the literature, not by correlation search.
- Give every variable its definition, source (dataset ID or DOI), and spatial
  and temporal resolution.
- Aggregate gridded data to county boundaries (Earth Engine) instead of climate divisions.
- Drop the 1919 crop value.
- Don't read much into the current numbers; show county maps of the inputs.
- Next method: Bayesian spatial model (Moraga, *Spatial Statistics for Data
  Science*, ch. 9: https://www.paulamoraga.com/book-spatial/bayesian-spatial-models.html).

## Pipeline (county × month)

Run from the repository root. Needs `pandas numpy scipy`; maps also need
`geopandas matplotlib plotly-geo`; the Earth Engine export needs
`earthengine-api` and an Earth Engine account.

| # | Script | Reads | Writes | Status |
|---|---|---|---|---|
| 1 | `data_clean.py` | `direct_loss_aggregated_output_32423.csv` | `loss_cleaned_monthly.csv` (SHELDUS county-months, flags, logs) | Done |
| 2 | `housing_features.py` | `nhgis0001_csv/nhgis0001_ts_nominal_county.csv` | `housing_county_year.csv`: housing units and urban share, 1999–2023 | Done |
| 2b | `build_monthly_panel.py` | steps 1 and 2 | `model_data_monthly_panel.csv`: Y + census housing, 303,840 rows | Done |
| 3 | `prism_export.py` | Earth Engine | Drive CSVs, now in `data/gee_era5/` (1950–2023), `data/gee_nlcd/` (1999–2023), `data/gee_terrain/` | Done |
| 4 | `prep_nclimgrid.py` | NOAA nClimGrid-Daily county files (8 GB, not in repo) | `data/nclimgrid_midwest/` (daily rain and Tmin, 1951–2023) | Done |
| 5 | `w_indices.py` | step 4 | `out/w_county_month.csv` (W), `out/w_county_thresholds.csv` (C) | Done |
| 6 | `build_panel.py` | steps 3 and 5 | `panel_county_month.csv`: inputs, 303,840 rows × 35 columns | Done |
| 6b | `census_features.py` | NHGIS extract `nhgis0001_csv/nhgis0001_csv/` | `data/clean/census_county_year.csv` | Done |
| 7 | `merge_panel.py` | steps 2, 5, 6, `data/clean/*` | `model_panel.csv`: 303,840 rows × 53 columns, no missing values | Done |
| 8 | `maps.py` | step 7, `data/counties_midwest.geojson` | `maps/*.png` (7 maps) | Done |
| 9 | `hurdle_model.py` | step 7 | printed tables, `results/hurdle_scores.csv` | Done (first version) |
| 10 | `model_comparison.py` | step 7 | printed tables, `results/model_comparison.csv` | Done; needs `lightgbm scikit-learn` |

`housing_county_year.csv` (step 2) still supplies `log_housing_units` and
`urban_share` (census years only, most recent census at or before the year).
`census_county_year.csv` (step 6b) adds yearly census/ACS values, including
`housing_units`; the models still use the step-2 columns until they are refit.

Rebuild the git-ignored outputs (about 3 minutes; checked from a clean checkout
of `enci-dev` on 2026-11-01: every committed output, including both results
files, reproduces byte for byte):

```
python data_clean.py && python housing_features.py && python build_monthly_panel.py
python w_indices.py --input data/nclimgrid_midwest --out-dir out/
python build_panel.py --era5 data/gee_era5 --nlcd data/gee_nlcd --terrain data/gee_terrain --w out/w_county_month.csv --out panel_county_month.csv
python census_features.py
python merge_panel.py
python maps.py
python hurdle_model.py          # about 1 minute
python model_comparison.py      # about 2 minutes; needs lightgbm scikit-learn
```

Git-ignored: `model_data_monthly_panel.csv` (21 MB), `out/w_county_month.csv`
(28 MB), `panel_county_month.csv` (70 MB), `model_panel.csv` (104 MB).

## Variables in `model_panel.csv`

Full reference (every column plus planned variables: definition, block, unit, source,
aggregation, timing, script and model use; plus datasets, blocks and notes):
`docs/flood_variable_reference.xlsx` (updated for the PRISM design on 2026-11-09; the table below
is the original NOAA design).

| Block | Columns | Source |
|---|---|---|
| Keys | `GEOID`, `year`, `month`, `split` (train/test) | |
| Y | `PropertyDmgADJ` (2024 $, 0 if no record), `log_PropertyDmgADJ` (log10(x + 1)), `has_damage` | SHELDUS |
| W, same month (perfect forecast) | `p_month`, `rx1`, `rx3`, `rx5`, `n_gt_p95`, `n_gt_p99`, `rx5_gt_rl10`, `rx5_rl_ratio`, `frost_days`, `snowmelt_mm`, `rain_x_wetsoil` | nClimGrid-Daily; ERA5-Land |
| W, known in advance | `spi1_prev`, `spi2_prev`, `frost_days_prev`, `snowmelt_prev_mm`, `sm_surface`, `sm_root`, `sm_root_pct`, `sm_root_anom`, `swe_mm` (day 1 of the month) | nClimGrid-Daily; ERA5-Land |
| C | `c_wetday_p95_mm`, `c_wetday_p99_mm`, `c_rx5_rl2_mm`, `c_rx5_rl10_mm`, `c_rx5_rl25_mm` (1951–1999) | nClimGrid-Daily |
| X | `log_housing_units` (natural log), `urban_share` | IPUMS NHGIS |
| X, land cover (year − 1) | `developed_share`, `impervious_mean`, `water_share` | Annual NLCD |
| X, susceptibility (static) | `elev_mean`, `slope_mean`, `flat_share`, `hand_mean`, `hand_lt5_share`, `land_km2`, `water_km2` | USGS 3DEP; MERIT Hydro |
| A (year − 1) | `wetland_share`, `wetland_change_since_1999` | Annual NLCD |
| X, census (year − 1) | `housing_units`, `population`, `median_value` (2024 $) | NHGIS time series AV0, A41; NH085A / B25077 |
| A, census (year − 1) | `median_income` (2024 $), `poverty_rate`, `mobile_home_share`, `built_pre1980_share` | NHGIS time series B79, BV3; NH030A / B25024; NH034A / B25034 |

Rainfall and soil thresholds are fitted on 1951–1999 (soil 1950–1999) only.
Never inputs: SHELDUS `Records`, `Duration_Days`, `Fatalities`, any other damage
column; NFIP claims; FEMA IA/PA payouts; disaster declarations; repetitive-loss
counts; later HMA grants; FEMA National Risk Index; NCEI Storm Events.

## Checks and findings

- The monthly SHELDUS file adds up exactly to the county-year file; the panel
  holds $21.5B of 2000–2023 property loss, the same as SHELDUS.
- 9,845 county-months (3.2%) have damage: 3.5% in 2000–2016, 2.5% in 2017–2023.
  84 counties have no damage month in 2000–2016.
- Inputs and outcome join one-to-one. Damage months average 152 mm of monthly
  rain vs 69 mm otherwise, and 82 mm vs 38 mm in the wettest 5 days.
- Same-month rain measures are near-duplicates (`rx3`, `rx5`, `rx5_rl_ratio`
  Spearman 0.92–0.96; `p_month` 0.87–0.90 with them): use one per model step.
- **Reporting differs by state.** Damage-month rates in 2000–2016: Iowa 7.9%,
  Ohio 6.7%, Indiana 5.2%, Illinois 2.6%, Minnesota 2.2%, Kansas 2.1%, with
  similar rain. Iowa falls to 2.5% in 2017–2023. Models need state (or NWS
  office) effects and results by state.
- **River flooding from upstream is not measured.** 9% of damage months (7% of
  loss) had below-median local rain; in March 2019 losses follow the Missouri
  River where local rain was ordinary. USGS streamflow would cover this.
- At the monthly level 30% of nonzero property values are round figures (14%
  before 1996, 54% after); flagged in `loss_cleaned_monthly.csv`.

## Hurdle model results (first county-month version, 2026-11-01)

`hurdle_model.py`: part 1 logistic for any damage, part 2 linear regression on
log10 damage, both with calendar-month and state indicators and a ridge penalty
(chosen on 2000–2012 → 2013–2016: part 1 = 100, part 2 = 0.1; it barely
matters). Trained on 2000–2016 (215,220 county-months, 3.54% damage), scored
once on 2017–2023 (88,620, 2.52% damage). One representative per overlapping
group: X = housing units, urban share, impervious %, water share, land within
5 m of drainage, log land area; A = wetland share; C = 10-year 5-day rain level.

| Model (test 2017–2023) | ROC-AUC | PR-AUC | AUC within month | Loss in top 5%, without largest month | Rank corr, county-year |
|---|---|---|---|---|---|
| Baseline: county × calendar-month rate | 0.728 | 0.066 | 0.709 | 0.266 | 0.113 |
| Setting: X, C, wetlands, state, month | 0.690 | 0.053 | 0.651 | 0.296 | 0.126 |
| + known in advance (prior rain, soil, snow) | 0.724 | 0.064 | 0.666 | 0.316 | 0.158 |
| + monthly rain | 0.851 | 0.168 | 0.825 | 0.562 | 0.248 |
| + 5-day extreme | 0.860 | 0.194 | 0.823 | 0.715 | 0.258 |
| + snow and frost (full) | 0.859 | 0.193 | 0.824 | 0.742 | 0.259 |
| Full, no state effect | 0.856 | 0.174 | 0.821 | 0.458 | 0.262 |
| Full, no rain climate (C) | 0.858 | 0.191 | 0.822 | 0.715 | 0.259 |

- **Same-month rain is what works:** +0.127 AUC (95% CI 0.117–0.135 from a
  county bootstrap). The 5-day extreme adds +0.009 (0.007–0.011). Snow and
  frost add nothing to AUC but catch March 2019: 71% of that month's loss is in
  the full model's top 5% of counties vs 11% without them. March 2019 holds 21%
  of all test-year loss, so dollar-weighted scores swing on it; the table shows
  the version without the largest month.
- **Known in advance ≈ the baseline.** Information available before the month
  (+0.035 AUC over the setting) only matches each county's own past damage rate
  (difference −0.004, CI −0.013 to +0.006). Real forecasting skill depends on
  forecasting the month's rain.
- **State effects matter** (+0.004 AUC, CI 0.000–0.007; much more for dollars:
  0.742 vs 0.458 of loss caught without the largest month).
- **Rain climate (C) adds a little** (+0.002 AUC, CI 0.000–0.003) and the
  monthly-rain coefficient rises from 1.35 to 1.49 when C is dropped: a sign of
  the W ← C confounding the causal framing predicts.
- **Calibration is off for the test years:** mean predicted probability is
  1.37× the observed rate, 2.3× in 2021 and 2.5× in Iowa, because damage was
  reported less often after 2016 (3.5% → 2.5%) and Iowa's rate fell most.
- Part 2 (amount) barely improves: MAE 0.862 log10 vs 0.905 for the baseline.
- Simulation check: 40 of 40 coefficients recovered within 2 standard errors.

## Model choice (2026-11-01)

`model_comparison.py` (needs `lightgbm scikit-learn`) compares model families on the
same split and scores as `hurdle_model.py`; `results/model_comparison.csv`. Full
write-up with sources: `docs/model_selection/model_selection.md` (notes in
`docs/model_selection/notes/`; most literature read from abstracts only).

| Model (test 2017–2023) | ROC-AUC | PR-AUC | Top 5%, without largest month | MAE, damaged |
|---|---|---|---|---|
| Baseline: county × calendar-month rate | 0.728 | 0.066 | 0.266 | 0.905 |
| GLM hurdle (`hurdle_model.py`) | 0.859 | 0.193 | 0.742 | 0.862 |
| Random forest hurdle | 0.879 | 0.216 | 0.756 | 0.829 |
| LightGBM hurdle | 0.886 | 0.252 | 0.723 | 0.816 |
| LightGBM Tweedie | 0.864 | 0.180 | 0.549 | – |
| LightGBM hurdle, known in advance only | 0.769 | 0.093 | 0.397 | 0.883 |

Recommended stack: LightGBM hurdle as the main model (monotone constraints on
hazard inputs); allocation by the rank average of LightGBM, random forest and
GLM; per-state intercept recalibration fitted on 2017–2018; R-INLA BYM2 hurdle
as the second method, then a hybrid with LightGBM predictions as covariates;
county + year-month fixed effects with W × C, then DML / causal forest for τ;
hurdle-structured conformal intervals. Open benchmark issue: the GLM uses 17
inputs and the trees 39 + state + month, so refit the GLM on matched inputs.

## Census and ACS data (`census_features.py`, 2026-11-01)

Input: the NHGIS extract "flood census 2000-2023" in `nhgis0001_csv/nhgis0001_csv/`
(time series AV0 population, A41 housing units, B79 median household income,
BV3 poverty by age; source tables for units in structure, year built and median
value from the 2000 Census SF3a and every ACS 5-year release 2005–2009 to
2019–2023). Output: `data/clean/census_county_year.csv`, 1,055 counties ×
1999–2023, no missing values.

- Each ACS release is placed in its last year (2006–2010 → 2010); values are
  interpolated linearly between survey years; 1999 copies 2000.
- Dollars in 2024 terms with the CPI-U (BLS CUUR0000SA0, hard-coded annual
  averages): 2000 Census income is in 1999 dollars, 2000 home value in 2000
  dollars, each ACS release in its last year's dollars.
- Source-table columns are found from each codebook (variable codes change
  between datasets, e.g. GAF in 2000 vs ASUG in 2019–2023).
- Checks: housing counts match the step-2 NHGIS table exactly in 2000 (within a
  few percent in 2010 and 2020). Median county income in 2024 $: $66,900 (2000),
  $63,300 (2010), $68,200 (2023); poverty peaks around 2014 (13.4%); homes
  built before 1980 fall from 77% to 64%.
- Caveat: an ACS release ending in year t is published in December of t + 1,
  so the one-year lag in `merge_panel.py` uses it a few months early; a two-year
  lag would avoid this.

## Still missing

**Data** (teammate's guide, saved to `data/clean/` and joined by `merge_panel.py`
with a one-year lag):

| Table | Block | Status |
|---|---|---|
| `census_county_year.csv`: housing units, population, median value, income, poverty, mobile-home share, built before 1980 (Census 2000 + ACS 5-year) | X, A | **Done 2026-11-01** (`census_features.py`, NHGIS extract in `nhgis0001_csv/nhgis0001_csv/`): 1,055 counties × 1999–2023, no missing values, dollars in 2024 CPI-U terms; joined by `merge_panel.py` (`model_panel.csv` now 53 columns). Not yet used by the models |
| `nfip_policies_county_year.csv`: policies in force (OpenFEMA) | A | To do; check coverage before 2009 |
| `hma_county_year.csv`: cumulative buyouts and elevations (OpenFEMA HMA) | A | To do |
| `soils_county.csv`: share of slow-draining soils (gNATSGO) | X (susceptibility) | To do |
| `crs_county_year.csv`: Community Rating System class | A | Optional |
| USGS streamflow | W | Not planned yet |

This cloud container cannot reach NHGIS, FEMA, USDA or USGS; downloads are done
locally.

**Models:**

Done: `hurdle_model.py` for county × month and `model_comparison.py` (results
above). To do, in the order from Model choice:

1. Tune the LightGBM hurdle with the census columns and monotone constraints;
   refit the GLM hurdle on the same inputs; rank-average LightGBM, random
   forest and GLM for allocation.
2. Calibration for the test years (every model expects 1.3–1.4× too many damage
   months, up to 2–3× in 2021–2023 and in Iowa): per-state intercept fitted on
   2017–2018, checked on 2019–2023.
3. Bayesian spatial model: BYM2 hurdle in R-INLA (Moraga ch. 9), then a hybrid
   with LightGBM predictions as covariates.
4. Causal: confounding simulation (C raises W and A, A lowers Y); county +
   year-month fixed effects with W × C; then DML / causal forest.
5. Forecast-like W and conformal prediction ranges with coverage.

**Decisions open:** instructor approval of rain-climate C, NFIP/CRS as A and
R-INLA. (Decided: `scikit-learn` and `lightgbm` are used, by `model_comparison.py`.)

## Literature review

`docs/literature_review/literature_review.md` (notes in
`docs/literature_review/notes/`). Most sources were read from abstracts only;
numbers marked [snippet] or [unverified] must be checked. Key points: monthly and
5-day rain both drive US flood damage (Davenport et al. 2021); wet soil,
snowmelt and frozen ground matter as much in the Midwest (Berghuijs et al. 2016);
use census components rather than SVI; lag adaptation one year.

## Old county-year design (removed 2026-11-01)

The first design (one row per county per year, climate-division rainfall, a
SHELDUS-based C) and its results (hurdle AUC 0.740 for any damage on 25,320
county-years) were pipeline checks only. Its scripts, generated CSVs and
unused data (FEMA National Risk Index, NOAA climate divisions, NHGIS 1919/1934
farm tables and the ACS home-value extract nhgis0003, the EDA plots) were
removed from the branch; they remain in git history at commit `fed41c4`
(`git checkout fed41c4 -- legacy/` restores the old scripts).

## Working notes

- Branches: `enci-dev` holds everything. `yan-dev2` is fully merged. `yana-dev`
  has 3 commits not merged: comments added to county-year scripts that have
  since been rewritten (`data_clean.py`) or removed, so there is nothing left
  to merge.
- Two Claude Docs on the owner's claude.ai account: "Project Process and
  Report" (the report; formerly "Initial Model Findings and Process") and
  "Flood Impact Forecasting: Project Workflow".
- NHGIS citation: Schroeder et al., *IPUMS NHGIS: Version 21.0* [dataset],
  Minneapolis, MN: IPUMS, 2026, doi:10.18128/D050.V21.0.
- Two old South Dakota codes: 46113 Shannon = 46102 Oglala Lakota; 46131
  Washabaugh merged into 46071 Jackson. Scripts map them.
- Commit only when asked.
