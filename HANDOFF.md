# Handoff: Flood Impact Forecasting (CSE 472, Project 2)

Read this first when picking up the project in a new session. It summarizes the
work through 2026-10-29 on branch `enci-dev`.

**Status (2026-10-29):** the instructor reviewed the Initial Model Findings
report, and the team agreed a new study design (below). Step 1 of the rebuild is
done: the monthly outcome (`data_clean.py`) and the county-month panel
(`build_monthly_panel.py`). W, C and A for the new design are not built yet, so
the results further down still come from the old county-year design and are
pipeline checks only.

## Study design (agreed 2026-10-29)

| Decision | Choice |
|---|---|
| Unit of analysis | County × month |
| Period | 2000–2023; train 2000–2016, test 2017–2023 |
| Events | All flooding in SHELDUS (hazard = Flooding), 12 Midwest states, property damage |
| Outcome | `direct_loss_aggregated_output_32423.csv` (SHELDUS by county and month) |
| Inputs | Never from SHELDUS. Time-varying inputs cover 2000–2023 at monthly or finer resolution; static inputs allowed |
| C (flood climate) | From a non-SHELDUS source, e.g. 1951–1999 extreme-rainfall frequency (NOAA nClimGrid or PRISM) |
| Spatial unit | County boundaries (gridded data summed per county, e.g. in Google Earth Engine), not NOAA climate divisions |

The panel will be 1,055 counties × 24 years × 12 months = 303,840 rows; 3.2% have
damage. A quick test (not in the pipeline) found same-month rainfall raised AUC
within each month from 0.704 to 0.765; month dummies alone added nothing to
ranking within a month.

## Instructor feedback (Saketh Vishnubhatla, on the findings report)

- SHELDUS supplies the outcome only; all inputs come from other sources.
- Choose variables from the literature, not by correlation search.
- Give every variable its definition, source (dataset ID or DOI), and spatial
  and temporal resolution.
- Use Google Earth Engine to aggregate to county boundaries instead of climate divisions.
- Drop the 1919 crop value.
- Don't read much into the current numbers; show county maps of the inputs
  rather than more tables.
- Next method: Bayesian spatial model (Moraga, *Spatial Statistics for Data
  Science*, ch. 9: https://www.paulamoraga.com/book-spatial/bayesian-spatial-models.html).

## Literature review

`docs/literature_review/literature_review.md` (research notes in
`docs/literature_review/notes/`). Network limits meant most sources were read
from abstracts only; numbers marked [snippet] or [unverified] must be checked.
Main points:

- W: add multi-day maxima (Rx1/3/5day), percentile exceedances, prior-month
  rainfall, soil moisture and snow (ERA5-Land). Davenport et al. 2021 (PNAS)
  find monthly and 5-day precipitation both drive US flood damage.
- C: pre-2000 rainfall climatology from nClimGrid or PRISM. Drop FEMA NRI
  frequency: it uses the outcome's source and years.
- X: Annual NLCD impervious and developed share, floodplain share, terrain
  (height above nearest drainage, slope), soils; census vulnerability
  components rather than SVI.
- A: NFIP policies in force, CRS class, buyouts, all lagged one year. NFIP
  claims and FEMA assistance are never inputs.
- Methods: hurdle models, gradient-boosted hurdle, Tweedie, BYM2 hurdle in
  R-INLA; check spatial confounding.

The shared workflow doc on claude.ai ("Flood Impact Forecasting: Project
Workflow") has the same study design, the literature tables and the pipeline
checklist.

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
scikit-learn is not installed, so models are written with numpy. pandas'
Spearman correlation needs scipy (`pip install scipy` if `impact_model.py`
fails with `No module named 'scipy'`).

**County-month pipeline (new design, being rebuilt step by step):**

| # | Script | Writes | Status |
|---|---|---|---|
| 1 | `data_clean.py` | `loss_cleaned_monthly.csv` (SHELDUS county-months, flags, logs) | Done (step 1) |
| 2 | `build_monthly_panel.py` | `model_data_monthly_panel.csv` (1,055 counties × 288 months = 303,840 rows, zeros included; git-ignored, 21 MB) | Done (step 1): outcome + census housing only |
| 3 | `hazard_features.py` | county × month W | To rebuild (step 2) |
| 4 | `climatology_features.py` | non-SHELDUS C | To rebuild (step 2) |
| 5 | `exposure_features.py`, new `adaptation_features.py` | X and A | To rebuild (step 3) |
| 6 | `hurdle_model.py` | results | To rebuild |

Step-1 checks: the monthly file adds up exactly to the county-year file (0
county-years differ); the panel holds $21.5B of 2000–2023 property loss, the same
as SHELDUS; 9,845 county-months (3.2%) have damage, 3.5% in training years and
2.5% in test years; 84 counties have no damage month in 2000–2016. At the
monthly level 30% of nonzero property values are round (14% before 1996, 54%
after), higher than the yearly 24% because summing months blurs round numbers.

**Earth Engine inputs:** `gee/export_county_data.py` exports county means of
PRISM monthly (1895–2023) and daily (1981–2023) precipitation, ERA5-Land soil
moisture and snow (1950–2023), NLCD land cover and terrain (height above
nearest drainage, slope) to Google Drive. It must run on a team member's own
Earth Engine account (this cloud container has no Earth Engine credentials and
cannot reach Drive); the CSVs then go in `external_data/gee/`. See
`gee/README.md`.

**Report:** the fixed "Initial Model Findings and Process" report is a Claude
Doc on the owner's claude.ai account (study design, SHELDUS cleaning, variable
specification table, one pipeline-check results table, references).

**County-year pipeline (old design):** see `legacy/README.md` for the run order.
`build_features_DU.py`, `impact_model.py`, the county-year `data_clean.py`, and
the two post-event side explorations moved to `legacy/`. `hazard_features.py`,
`exposure_features.py`, `climatology_features.py`, `build_panel.py` and
`hurdle_model.py` in the root are still the county-year versions until rebuilt;
they read `model_data_DU.csv`, `loss_cleaned.csv` and the other existing CSVs.

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

## Next steps (pipeline)

1. **Decisions and write-up:** apply the text fixes to the findings report;
   confirm with the instructor that rainfall-based C, NFIP/CRS as A, and R-INLA
   are acceptable; verify the flagged literature numbers.
2. **Variable specification table:** definition, formula, unit, source ID,
   resolution, aggregation and years for every input.
3. **Data collection:** Earth Engine script for PRISM county × month rainfall
   features and ERA5-Land soil moisture and snow; nClimGrid county files for C;
   Annual NLCD, 3DEP, gNATSGO, floodplain share; OpenFEMA NFIP policies, CRS
   lists, HMA buyouts; NHGIS/ACS vulnerability components. Open question: how
   complete OpenFEMA policies are before ~2009.
4. **Maps:** county map of each input and of 2000–2016 loss.
5. **Code rebuild:** `build_monthly_panel.py`; replace `hazard_features.py` and
   `climatology_features.py`; drop history features and 1919 crop value; adapt
   `hurdle_model.py` to county × month with one results table; decide what to
   commit (`external_data/fema_nri/` is 24 MB and now unused).
6. **Models:** baselines (county × calendar-month climatology, current hurdle,
   ranking by P(damage) × expected log damage); rainfall comparison (monthly
   only → + multi-day extremes → + antecedent wetness and snow); gradient-boosted
   hurdle vs Tweedie; BYM2 hurdle in R-INLA; county fixed effects with W × C;
   confounding simulation (C raises W and A, A lowers Y); forecast-like W with
   80% prediction ranges.
7. **Evaluation:** by test year 2017–2023: PR-AUC, ROC-AUC and Brier skill
   against climatology; rank correlation, top-10% hit, share of loss captured;
   MAE on damaged months; interval coverage.

## Working notes

- The team's write-ups are PDFs (distribution, cleaning, relationship, hazard,
  exposure, model testing, impact model, next steps). A shared workflow doc with
  the same content lives on claude.ai (owner's account).
- Commit only when asked; feature work happens on `enci-dev`, merged with
  teammates' `yana-dev`.
