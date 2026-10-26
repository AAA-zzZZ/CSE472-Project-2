# Handoff: Flood Impact Forecasting (CSE 472, Project 2)

Read this first when picking up the project in a new session. It summarizes the
work through 2026-10-26 on branch `enci-dev`.

## The task

Build the **impact model** τ(w; x, c) from the course slides: given how hard a
flood hits a county (w), what is exposed (x) and the county's long-run flood
climate (c), predict its property loss, so counties can be **ranked** for
emergency resources. Evaluation from the slides: train on 2000–2016, test on
2017–2023, use only pre-event information, and check the method on simulated
losses with a known answer.

The slides frame it causally: a plain regression learns E[Y | W, X], but the goal
is E[Y | do(W), X, C]. The backdoor path is W ← C → A → Y (counties that flood
often get stronger floods *and* adapt more). A (adaptation) is not measured yet.

Background reading: Merz et al. (2020), *Impact Forecasting to Support Emergency
Management of Natural Hazards*, Reviews of Geophysics, doi:10.1029/2020RG000704.

## Pipeline (run in this order)

Each script reads the previous one's output. Only numpy and pandas are used;
scikit-learn is not installed, so models are written with numpy.

| # | Script | Writes |
|---|---|---|
| 1 | `data_preprocess.py` | `distributions/` (plots only) |
| 2 | `data_clean.py` | `loss_cleaned.csv` |
| 3 | `relationship_eda.py` | `relationships/` (plots only) |
| 4 | `build_features_DU.py` | `model_data_DU.csv` (running county history) |
| 5 | `hazard_features.py` | `model_data_hazard.csv`, `hazard_by_division.csv` |
| 6 | `exposure_features.py` | `model_data_combined.csv`, `exposure_by_county_year.csv` |
| 7 | `climatology_features.py` | `model_data_climatology.csv` |
| 8 | `build_panel.py` | `model_data_panel.csv` (every county-year, zeros included) |
| 9 | `impact_model.py` | printed results (flooded county-years only) |
| 10 | `hurdle_model.py` | printed results (full panel) |

`crop_dmg_regression.py` and `property_dmg_regression.py` are side explorations.
They use `Records` and duration, which are only known after the flood, so they are
not forecasts.

## Data sources

| Dataset | Files | Role |
|---|---|---|
| SHELDUS (ASU CEMHS), flooding, 12 Midwest states, county-year, 1960–2024, 2024 dollars | `loss_output_year_county.csv` | Y (target); C from 1960–1999; history features |
| NOAA nClimDiv climate-division monthly precipitation + county lookup | `external_data/noaa/` | W (rainfall anomalies vs each division's 1895–1959 normal) |
| IPUMS NHGIS extract nhgis0001 (housing 1970–2020, crops 1919, farms 1934) | `nhgis0001_csv/` | X |
| IPUMS NHGIS extract nhgis0003 (ACS median home value) | `nhgis0003_csv/` | X candidate; tested, no gain, not in pipeline |
| FEMA National Risk Index, March 2023 (archived copy: doi:10.7910/DVN/JSQ8KZ) | `external_data/fema_nri/` | C cross-check only |

NHGIS requires a citation in reports: Schroeder et al., *IPUMS NHGIS: Version
21.0* [dataset], Minneapolis, MN: IPUMS, 2026, doi:10.18128/D050.V21.0.

## Key variables

- **Target:** `log_PropertyDmgADJ` = log10(property damage in 2024 dollars + 1).
  An error of 1.0 means off by about 10×. Panel also has `PropertyDmgADJ` (0 when
  SHELDUS has no record) and `has_damage` (0/1).
- **W:** `annual_precip_anom`, `max_month_precip_anom` (strongest single feature),
  `spring_precip_anom`, `prior_fall_precip_anom` (the only pre-event one). Same-year
  rainfall stands in for a perfect hazard forecast; say so in the write-up.
- **X:** `log_housing_units`, `urban_share`, `log_crop_value_1919`.
  `log_population` exists only for flooded rows (it is backed out of SHELDUS
  per-capita damage), so the panel uses housing units instead (0.99 correlated).
- **C:** `c_flood_freq` (flood years 1960–1999 ÷ 40, main) and `c_big_flood_freq`.
  `c_records_per_year` is left out (0.83 correlated with `c_flood_freq`).
- **History features** (`prior_flood_years` etc.) grow over time and drift between
  train and test; kept only as comparison rows.
- **Never inputs:** `Records`, `Duration_Days`, `Fatalities`, and any other version
  of damage (raw, per capita, crop). They are known only after the flood or repeat
  the target.

Log bases differ: population uses log10; housing and crop value use the natural log.

## Results so far (test 2017–2023)

**Flooded county-years only (`impact_model.py`, OLS):** full model MAE about 0.996.
Adding C changes nothing (within bootstrap noise), and the rainfall coefficients
do not move. Reason: every row already flooded, and each rainfall anomaly is
measured against its own division's normal, so C barely correlates with W.

**Full panel with zeros (`hurdle_model.py`):** 1,055 counties × 24 years = 25,320
county-years, 25.7% with damage.

| Model | AUC (any damage) | Rank corr | Top 10% caught |
|---|---|---|---|
| Exposure only | 0.614 | 0.122 | 0.162 |
| w + x, no C | 0.732 | 0.223 | 0.235 |
| Hurdle, full (w, x, C) | 0.740 | 0.240 | 0.250 |
| One-part OLS on log(damage + 1) | n/a | 0.255 | 0.246 |
| Cross-check with NRI C (leaky) | 0.763 | 0.267 | 0.267 |

- C now matters: `c_flood_freq` has the largest part-1 coefficient (+0.67
  log-odds per standard deviation). Bootstrap: AUC +0.007 (95% CI 0.003–0.012),
  rank corr +0.017 (0.009–0.024).
- The one-part regression ranks slightly better than the hurdle (rank corr
  +0.015, CI 0.005–0.027). The hurdle still gives calibrated probabilities and
  sensible dollar figures.
- MAE over all panel rows is misleading: always predicting 0 scores best because
  79% of test rows are 0. Use AUC, part-2 MAE (0.860 on damaged rows) and ranking.
- Simulation checks pass in both scripts (coefficients recovered within 2 SE).

## Decisions and caveats

- **NRI frequency leaks:** it counts 1996–2019 events, overlapping the study
  years. Keep it as a cross-check. NRI loss columns (HLR, EAL, risk) are built
  from SHELDUS and must never be used. NRI floodplain share is map-based and fine
  as an independent check.
- **County-year, not event-level:** the slides describe county × event rows; the
  SHELDUS export is aggregated by year. This blurs the match between W and Y.
  Treated as a stated simplification unless the instructor requires events.
- **Two old South Dakota codes:** 46113 Shannon = 46102 Oglala Lakota; 46131
  Washabaugh merged into 46071 Jackson. Scripts map them.
- `hazard_features.py` previously read a nonexistent `model_data.csv`; it now
  reads `model_data_DU.csv`. Rerunning the feature scripts reproduces the existing
  CSVs byte for byte.

## Next steps

1. Ask the instructor: county-year or event-level? Is "share of the county
   flooded" expected for W? (The Global Flood Database may only run to ~2018.)
2. Rank the hurdle model by P(damage) × expected log damage instead of expected
   dollars, and see if it catches up with the one-part regression.
3. Add A: NFIP flood insurance policies in force per county (OpenFEMA, ~2009+),
   in both hurdle parts.
4. Estimate τ causally: double machine learning for the average effect of W, a
   causal forest for effects by county type (needs scikit-learn / econml).
5. Rebuild the simulation with confounding built in (C raises W and A; A lowers
   Y) and show the naive model is biased while the adjusted one recovers the truth.
6. Plug in a forecast-like W, rank counties per test year, and report 80%
   prediction ranges with their coverage.
7. Decide what to commit: `external_data/fema_nri/` is 24 MB, and the generated
   CSVs (`model_data_panel.csv`, `hazard_by_division.csv`,
   `exposure_by_county_year.csv`) can be rebuilt from the scripts.

## Working notes

- The team's write-ups are PDFs (distribution, cleaning, relationship, hazard,
  exposure, model testing, impact model, next steps). A shared workflow doc with
  the same content lives on claude.ai (owner's account).
- Commit only when asked; feature work happens on `enci-dev`, merged with
  teammates' `yana-dev`.
