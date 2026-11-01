# Handoff: Flood Impact Forecasting (CSE 472, Project 2)

Read this first when picking up the project in a new session. It summarizes the
work through 2026-11-01 on branch `enci-dev` (pull request #1 into `main`).

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
