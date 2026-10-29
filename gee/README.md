# Earth Engine exports

`export_county_data.py` computes county-level inputs in Google Earth Engine and
saves them to Google Drive as CSVs. Every value is a mean over the county
boundary (Census TIGER 2018), for the 1,055 counties of the 12 states. Nothing
here uses SHELDUS.

## Run it

You need an Earth Engine account and a Google Cloud project registered for
Earth Engine (https://code.earthengine.google.com/register).

```
pip install earthengine-api
earthengine authenticate
python gee/export_county_data.py --project YOUR-CLOUD-PROJECT --dry-run   # one sample row per group, no exports
python gee/export_county_data.py --project YOUR-CLOUD-PROJECT             # start all exports
```

Use `--only prism_monthly era5_land` (any of `counties prism_monthly
prism_daily era5_land nlcd terrain`) to start just some groups. The exports run
on Google's servers; follow them at https://code.earthengine.google.com/tasks.
When they finish, download the `flood_gee` folder from Google Drive and put the
CSVs in `external_data/gee/`.

## What it exports

| Group | Files | Rows | Source | Used for |
|---|---|---|---|---|
| counties | `counties.csv` | 1,055 | TIGER/2018/Counties | Join check |
| prism_monthly | `prism_monthly_<years>.csv`, 7 files (1895–2023) | ~1.6M | PRISM monthly precipitation (`ppt`, mm) | W: monthly anomaly vs the 1895–1959 normal, prior-month anomaly; C: share of very wet months 1951–1999 |
| prism_daily | `prism_daily_<year>.csv`, 43 files (1981–2023) | ~385k each | PRISM daily precipitation (`ppt`, mm) | W: Rx1/3/5day, days above the county's 1981–1999 95th percentile; C: mean annual Rx5day |
| era5_land | `era5_land_monthly_<years>.csv`, 3 files (1950–2023) | ~0.9M | ERA5-Land monthly: top-layer soil water (m³/m³), snow water equivalent (m), snowmelt (m), minimum temperature (K), runoff (m) | W: antecedent wetness, snowmelt, frozen ground |
| nlcd | `nlcd_<year>.csv`, one per NLCD release (2001–2019) | 1,055 each | NLCD 2019 release: impervious %, developed share (classes 21–24), wetland share (90, 95) | X: exposure; A: wetlands |
| terrain | `terrain_static.csv` | 1,055 | MERIT Hydro height above nearest drainage; SRTM slope | X: susceptibility |

Each monthly or daily row is `GEOID, date, <values>`; `GEOID` is the 5-digit
county FIPS code, matching `County_FIPS` in the panel.

## Notes

- The PRISM collections were renamed (`AN81m` → `ANm`, `AN81d` → `ANd`); the
  script uses whichever name the catalog still serves.
- Daily extremes are computed from the county-mean daily series, so they
  describe rain over the whole county, not the wettest pixel.
- The script stops with a clear message if an ERA5-Land band name has changed.
- Not exported here: flood insurance policies and Community Rating System
  classes (OpenFEMA / FEMA lists) and census vulnerability variables (NHGIS);
  those are downloads, not Earth Engine data.
