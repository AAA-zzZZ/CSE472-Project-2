# OpenFEMA placeholder

No OpenFEMA data has been collected yet. Put the raw downloads in this folder. Using
OpenFEMA still needs the mentor's approval (step 1 of the work plan).

The models are already wired for these inputs, and the path was tested with fake tables.
Only the step that turns the raw downloads into the two tables below is still to write,
because the HMA dataset fields have not been confirmed.

## 1. Tables to produce

Save these in `data/clean/`, using exactly these names, because `merge_panel.py` looks for them:

| File | Columns | Used as |
|---|---|---|
| `nfip_policies_county_year.csv` | `GEOID, year, policies_in_force` | `nfip_policies_per_hu` (`policies_per_unit` in the handout) = policies ÷ housing units |
| `hma_county_year.csv` | `GEOID, year, buyouts_cum, elevations_cum` | `buyouts_cum`. `elevations_cum` is joined to the panel but is not a model input |

Rules for both tables:

- `GEOID` is the 5-digit county code.
- Save each value under **its own year**. `merge_panel.py` applies the one-year lag, so do
  not shift the years first.
- Include all 1,055 counties for **1999–2022**. Model year 2000 reads 1999, and 2023 reads 2022.
- A county with no buyouts needs a row with `0`, not a missing row.
- NFIP: use **policies only, never claims**. Claims come from the flood losses being
  predicted, so using them would leak the outcome.

## 2. Rebuild and refit

```powershell
python yana_workspace/temp_merge_panel.py --thresholds out/prism_midwest/w_county_thresholds.csv --out model_panel_openfema.csv
python reduced_benchmark.py --panel model_panel_openfema.csv --openfema --out-dir results/midwest_prism_openfema
python reduced_benchmark.py --panel model_panel_openfema.csv --openfema --state MO --out-dir results/missouri_prism_openfema
```

Writing to `model_panel_openfema.csv` leaves `model_panel.csv` and its results as they are.
Add `model_panel_openfema.csv` to `.gitignore` first, because it is about 100 MB.

## 3. Known issue: NFIP coverage before 2009

The handout flags NFIP coverage before 2009 as unchecked. If years are missing,
`reduced_benchmark.py` stops and prints the share of missing rows by year. The GLM cannot
take missing values, and the team needs to decide how to handle them. The options are
shorter training years or a separate model version. Do not fill them with zeros, because
an unknown year is not a year with no policies.
