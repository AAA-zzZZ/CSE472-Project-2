# Midwest Flood Impact: forecasting and explaining county flood losses

CSE 472, Project 2. We predict, for every county and month in 12 Midwest states (1,055 counties,
2000–2023), the chance of any flood property damage and, if damage occurs, its loss class. We
also test how much rain climate and community preparedness change the effect of a storm. An
Earth Engine app maps the predictions and the inputs.

- **Write-up:** [`report/Writeup.tex`](report/Writeup.tex)
- **Every file, its source and how the data is changed:** [`docs/README.md`](docs/README.md)
- **Papers cited:** [`Literature/`](Literature/)
- Earlier designs, working notes and exploratory scripts are on the `enci-dev` branch.

## The model in brief

A two-part (hurdle) model per county-month:

1. **Chance of any damage**: LightGBM and a ridge logistic GLM.
2. **Loss class if damage occurs**: minor (< $10k), moderate ($10k–$100k), major ($100k–$1M) or
   severe (≥ $1M), in 2024 dollars. Ordinal logistic GLM and LightGBM multiclass.

Train 2000–2016, test 2017–2023. The outcome is SHELDUS flood property loss. The 12 inputs come
from PRISM (rain, frost, rain climate), ERA5-Land (soil wetness, snow), GHSL (built-up surface),
Annual NLCD (paved and wetland share), MERIT Hydro (land near streams) and Census TIGER (land area).
Every yearly input is taken from the previous year, so it is known before the month it predicts.

## Repository layout

| Path | What it is |
|---|---|
| `data_clean.py`, `housing_features.py`, `build_monthly_panel.py` | Outcome: SHELDUS losses on a full county × month grid |
| `prism_export.py`, `ghsl_export.py` | Earth Engine exports (county averages to Google Drive) |
| `w_indices.py`, `build_panel.py` | Monthly rain indices and the input panel |
| `census_features.py`, `ghsl_features.py`, `openfema_features.py` | Yearly county tables in `data/clean/` |
| `merge_panel.py` | Joins everything into `model_panel.csv`, the one table every model reads |
| `reduced_benchmark.py`, `loss_class_model.py`, `recalibrate.py` | Forecast models |
| `causal_model.py` | Explanatory models (storm effect, climate and preparedness) |
| `data/` | Earth Engine exports (`gee_*`), yearly tables joined by `merge_panel.py` (`clean/`), OpenFEMA notes |
| `report/` | The write-up (`Writeup.tex`) |
| `docs/` | File-by-file description of the pipeline (`README.md`) |
| `results/` | Scores, coefficients and logs of each model run |
| `gee_app/` | Earth Engine apps and the prediction tables they read |
| `data/raw/` | Raw inputs: SHELDUS losses (`direct_loss_aggregated_output_32423.csv`, `loss_output_year_county.csv`) and the NHGIS census extract (`nhgis0001_csv/`) |
| `data/interim/` | Cleaned losses and housing units (`loss_cleaned_monthly.csv`, `housing_county_year.csv`), read by `build_monthly_panel.py` |

## Rebuild

Python 3; install the packages with `pip install -r requirements.txt` (`earthengine-api` is only
needed for the exports). Run from the repository root. The Earth Engine exports are already in `data/`, so the rebuild starts from them:

```bash
python data_clean.py; python housing_features.py; python build_monthly_panel.py
python w_indices.py --input data/gee_prism_midwest --out-dir out/prism_midwest/ --base-start 2000 --base-end 2009 --model-start 2000 --model-end 2023
python build_panel.py --era5 data/gee_era5 --nlcd data/gee_nlcd --terrain data/gee_terrain --w out/prism_midwest/w_county_month.csv --out panel_county_month.csv
python census_features.py
python ghsl_features.py
python openfema_features.py   # optional: needs the downloads in data/openfema/raw/; its tables are already in data/clean/
python merge_panel.py         # writes model_panel.csv
```

Then the models:

```bash
python reduced_benchmark.py --out-dir results/midwest_prism
python reduced_benchmark.py --state MO --out-dir results/missouri_prism
python reduced_benchmark.py --score-state MO --out-dir results/missouri_pooled
python loss_class_model.py --out-dir results/loss_classes_midwest
python loss_class_model.py --state MO --out-dir results/loss_classes_missouri
python causal_model.py --design nested --out-dir results/causal_nested_midwest
python recalibrate.py --out-dir results/recalibration_midwest
python recalibrate.py --state MO --out-dir results/recalibration_missouri
python gee_app/Midwest/build_midwest_app_table.py   # app table for the Earth Engine app
```

`model_panel.csv`, `panel_county_month.csv`, `model_data_monthly_panel.csv` and
`out/prism_midwest/w_county_month.csv` are git-ignored (too large) and made by the commands above.

To redo the Earth Engine exports (needs an Earth Engine account and a Cloud project):

```bash
python prism_export.py prism   --project MY_PROJECT --start 2000 --end 2023
python prism_export.py era5    --project MY_PROJECT
python prism_export.py nlcd    --project MY_PROJECT --scale 90
python prism_export.py terrain --project MY_PROJECT
python ghsl_export.py --project MY_PROJECT --start 1995 --end 2025
```

The files land in Google Drive. Copy them into the matching `data/gee_*` folders.

## Earth Engine app

The current app is **[`gee_app/Midwest/flood_explorer_app3.js`](gee_app/Midwest/flood_explorer_app3.js)**.
It covers all 12 states, 2017–2023, with the chance of damage, the recorded SHELDUS loss class
and every model input as county layers.

**Published copy:** the Code Editor repository `users/ezheng3/midwest_flood_impact` (script
`flood_explorer`) runs this file against the asset
`projects/cse472-project-2/assets/midwest_flood_app_table`. To get it, open
<https://code.earthengine.google.com/?accept_repo=users/ezheng3/midwest_flood_impact> (needs
access from the owner). To set up your own copy instead:

1. In the [Earth Engine Code Editor](https://code.earthengine.google.com), upload
   [`gee_app/Midwest/midwest_flood_app_table.csv`](gee_app/Midwest/midwest_flood_app_table.csv)
   as a table asset (**Assets → NEW → CSV file**). Leave the coordinate fields empty: rows are
   matched to counties by the `key` column.
2. Set `ASSET_ID` (line 21) to your asset's ID, for example
   `projects/<your-project>/assets/midwest_flood_app_table`.
3. Paste the script into a new file and press **Run**. Pick a layer, year and month, then click a
   county for its details.

Others need **Reader** access to the asset (Assets tab → Share) to run the app.

Other apps in `gee_app/`:

| File | What it is |
|---|---|
| `missouri_tester/flood_explorer_app.js` | Missouri only, older dollar-loss predictions; reads `missouri_tester/mo_flood_app_table.csv`. Guide: `flood_explorer_app_guide.pdf` |

Earlier app versions (the Midwest version 2 and an input-only exposure app) are on the `enci-dev`
branch.
