# OpenFEMA data (adaptation, A)

Collected on 2026-11-09 for all 12 Midwest states. `openfema_features.py` (repository root)
turns the raw downloads in `raw/` into the three county-year tables below. The raw files are
about 4 GB and git-ignored; the tables are committed in `data/clean/`.

The datasets this folder was first planned around (FIMA NFIP Redacted Policies v2,
HMA Mitigated Properties v4, HMA Projects v4) were **removed by FEMA on 2026-10-15**. The script
uses their replacements.

## 1. Download

FEMA refuses Python's downloader (HTTP 403), so download with curl or a browser, from the
repository root. Keep these file names:

```powershell
New-Item -ItemType Directory -Force data/openfema/raw
curl.exe -L -o data/openfema/raw/NfipPoliciesV3.parquet "https://www.fema.gov/about/reports-and-data/openfema/v3/NfipPoliciesV3.parquet"
curl.exe -L -o data/openfema/raw/HmaSubapplicationsProjectSiteInventories.csv "https://www.fema.gov/api/open/v1/HmaSubapplicationsProjectSiteInventories.csv"
curl.exe -L -o data/openfema/raw/HmaSubapplications.csv "https://www.fema.gov/api/open/v2/HmaSubapplications.csv"
```

| File | Dataset | Size | Used for |
|---|---|---|---|
| `NfipPoliciesV3.parquet` | [NFIP Redacted Policies v3](https://www.fema.gov/openfema-data-page/nfip-redacted-policies-v3) | 3.7 GB, 74.7M records | Policies in force. The API is too slow (3.7M Midwest records) |
| `HmaSubapplicationsProjectSiteInventories.csv` | [HMA Subapplications Project Site Inventories v1](https://www.fema.gov/openfema-data-page/hma-subapplications-project-site-inventories-v1) | ~30 MB | One row per mitigated site: county, activity (Acquisition, Elevation, ...) |
| `HmaSubapplications.csv` | [HMA Subapplications v2](https://www.fema.gov/openfema-data-page/hma-subapplications-v2) | ~28 MB | Fiscal year and status of each subapplication, joined on the subapplication ID |

## 2. Build the tables

```powershell
python openfema_features.py
```

It writes to `data/clean/`, under the names `merge_panel.py` looks for:

| File | Columns | How it is built |
|---|---|---|
| `nfip_policies_county_year.csv` | `GEOID, year, policies_in_force` | Sum of `policyCount` for policies in force on 1 July (effective ≤ 1 July < termination, or cancellation if earlier). County = first 5 digits of `censusGeoid` |
| `crs_county_year.csv` | `GEOID, year, crs_best_class, crs_class5_or_better` | Community Rating System class from `crsClassCode` on the same 1 July policies: best (lowest) class in the county, 10 if no policy carries a class; indicator for class ≤ 5. Same years as NFIP (before 2010 empty) |
| `hma_county_year.csv` | `GEOID, year, buyouts_cum, elevations_cum` | Funded sites (status Approved or later) with primary activity Acquisition or Elevation, counted by county and program fiscal year, cumulative since 1989 |

Both cover all 1,055 counties for 1999–2022, saved under their own year (`merge_panel.py`
applies the one-year lag). A county with no buyouts has `0`. NFIP uses **policies only, never
claims**: claims come from the losses being predicted.

## 3. Coverage limits

- **NFIP: no policy record starts before 2009.** 1 July 2009 would miss the policies that
  began in 2008, so 1999–2009 are left **empty, not zero** (an unknown year is not a year with
  no policies). With the lag, NFIP is missing for model years 2000–2010.
- **HMA: no funded Midwest acquisitions or elevations in fiscal years 2005–2019** in the
  current FEMA data (1990s: about 14,600; 2000–2004: 238; 2020–2022: 52). The removed Mitigated
  Properties dataset covered those years. `buyouts_cum` is therefore almost a fixed count of
  1990s buyouts, mostly after the 1993 flood.
- 91% of HMA sites have no county code and are matched by county name; 19 of 14,906 funded
  sites could not be matched and are dropped.
- Fiscal year is the year of the disaster for disaster grants, so the work finishes later.

Checks: Missouri has 24,537 policies in force in 2010 and 17,111 in 2022; Illinois about
48,000. Compare with FEMA's published totals.

## 4. Rebuild the panel and refit

```powershell
python merge_panel.py
python reduced_benchmark.py --openfema buyouts --state MO --out-dir results/missouri_prism_buyouts
python reduced_benchmark.py --openfema buyouts --out-dir results/midwest_prism_buyouts
```

`merge_panel.py` joins every table in `data/clean/`, so `model_panel.csv` carries the four
OpenFEMA columns (`policies_in_force`, `nfip_policies_per_hu`, `buyouts_cum`, `elevations_cum`).
The models ignore them unless `--openfema` is given; the other columns are unchanged.
Use `--openfema buyouts`: plain `--openfema` also adds `nfip_policies_per_hu`, which is missing
for model years 2000–2010, so `reduced_benchmark.py` stops. (The 2026-11-09 runs used a separate
`model_panel_openfema.csv`, identical to today's `model_panel.csv`.)

## 5. Results

**Buyouts add nothing.** On the 2013–2016 validation years every score moves by 0.02 or less
in Missouri and the Midwest (one Midwest LightGBM top-5% value, 0.671 to 0.721, is not
supported by any other score). LightGBM ranks `buyouts_cum` last (under 1% of gain). The GLM
coefficient is slightly positive (+0.07 in Missouri): buyouts mark counties that flooded badly
in the 1990s, not protected ones (C → A confounding).

**NFIP fits Equation 4, not the prediction model.** It cannot enter the 2000–2016 training
years, but it covers the causal period (2010–2023) as a yearly adaptation variable.

## 6. Not collected

- **NFIP Redacted Claims v3** (`https://www.fema.gov/api/open/v3/NfipClaims`; 51,304 Missouri
  claims with date of loss and damage). Only to check the SHELDUS outcome (for example, losses
  split equally across counties), **never as an input**, and only with the instructor's approval.
  Claims cover insured property only.
- CRS classes before 2010. `crs_county_year.csv` takes them from the policies, so 1999–2009
  would need FEMA's past CRS community lists, assembled by hand.
