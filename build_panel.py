"""
Build the county x month modelling panel from the Earth Engine exports.

One row per county per month, model years only (default 2000-2023).

Inputs (folders of CSVs downloaded from Google Drive):
  --era5     gee_era5/     era5_county_monthly_<YEAR>.csv   (GEOID, date, sm1, sm2, sm3, swe, snowmelt_month)
  --nlcd     gee_nlcd/     nlcd_county_<YEAR>.csv           (GEOID, year, developed_share, wetland_share, ...)
  --terrain  gee_terrain/  terrain_county.csv               (GEOID, ALAND, AWATER, elev_mean, slope_mean, ...)
  --w        optional      w_county_month.csv from w_indices.py (rainfall indices), add when ready

Output:
  panel_county_month.csv

Usage:
    pip install pandas numpy
    python build_panel.py --era5 data/gee_era5 --nlcd data/gee_nlcd --terrain data/gee_terrain --out panel_county_month.csv
    # later, once the rainfall indices exist:
    python build_panel.py ... --w out/w_county_month.csv

Leakage rules:
  * Soil moisture and snowpack are measured on the first day of the target month, so they are
    known before that month's floods. Their percentiles are ranked against 1950-1999 only.
  * Land cover is taken from the previous year (year - 1).
  * snowmelt_month is the same-month hazard (like same-month rainfall); snowmelt_prev is the prior month.

Columns added:
  ERA5:    sm_surface (0-7 cm), sm_root (0-100 cm, depth-weighted), sm_root_pct (0-1 percentile vs
           1950-1999 for that county and calendar month), sm_root_anom (minus baseline mean),
           swe_mm (snowpack on day 1), snowmelt_mm (month total), snowmelt_prev_mm
  NLCD:    developed_share, wetland_share, water_share, impervious_mean (all from year - 1),
           wetland_change_since_1999 (wetland share in year - 1 minus 1999)
  Terrain: elev_mean, slope_mean, flat_share, hand_mean, hand_lt5_share, land_km2, water_km2
  If --w:  rainfall indices plus rain_x_wetsoil = rx5_rl_ratio * sm_root_pct
"""

import argparse
import glob
import os
import warnings

import numpy as np
import pandas as pd

# ERA5-Land layer thicknesses (cm) for the 0-100 cm root-zone average.
LAYER_CM = {"sm1": 7, "sm2": 21, "sm3": 72}


def read_folder(folder, pattern="*.csv"):
    """Read every CSV in a folder into one table and return (table, number of files).

    No math: the files are stacked row-wise. GEOID is read as text and left-padded with zeros
    to 5 digits (2-digit state FIPS + 3-digit county FIPS), so e.g. "1001" becomes "01001" and
    keys match across datasets.
    """
    files = sorted(glob.glob(os.path.join(folder, pattern)))
    if not files:
        raise SystemExit(f"no CSV files found in {folder}")
    df = pd.concat((pd.read_csv(f, dtype={"GEOID": str}) for f in files), ignore_index=True)
    df["GEOID"] = df["GEOID"].str.zfill(5)
    return df, len(files)


def baseline_percentile(df, col, base_start, base_end):
    """Percentile (0-1) of each value against the same county and calendar month in the baseline years.

    For each county g and calendar month m (so a March is only compared with past Marches):
      1. ref = the sorted baseline values of col for (g, m), one per baseline year.
         If there are fewer than 10, the percentile is left NaN (too few years to rank against).
      2. For every value x of (g, m), in any year, the percentile is the empirical CDF:
             pct(x) = (# baseline values <= x) / (# baseline values)
         np.searchsorted(ref, x, side="right") returns exactly that count, because it finds the
         position just after the last ref value that is <= x.
    So 0.9 means the value is wetter than 90% of baseline years for that county and month,
    0 means below every baseline year and 1 means at or above the baseline maximum.
    """
    out = pd.Series(np.nan, index=df.index)
    base = df["year"].between(base_start, base_end)
    for _, idx in df.groupby(["GEOID", "month"]).groups.items():
        vals = df.loc[idx, col]
        ref = np.sort(vals[base.loc[idx]].dropna().to_numpy())
        if len(ref) < 10:
            continue
        ok = vals.notna()
        out.loc[vals.index[ok]] = np.searchsorted(ref, vals[ok].to_numpy(), side="right") / len(ref)
    return out


def load_era5(folder, base_start, base_end):
    """Load ERA5-Land county-month exports and compute the soil moisture and snow features.

    Inputs per county-month: sm1, sm2, sm3 = volumetric soil water (m3 water / m3 soil) in the
    0-7, 7-28 and 28-100 cm layers on day 1 of the month; swe = snow water equivalent on day 1 (m);
    snowmelt_month = total snowmelt during the month (m of water).

    Calculations:
      sm_surface       = sm1 (top 0-7 cm layer)
      sm_root          = depth-weighted average over 0-100 cm:
                           (7*sm1 + 21*sm2 + 72*sm3) / 100
                         each layer counts in proportion to its thickness
      swe_mm           = swe * 1000          (metres -> millimetres)
      snowmelt_mm      = snowmelt_month * 1000
      snowmelt_prev_mm = snowmelt_mm of the previous month for the same county (shift by 1 row
                         after sorting by county, year, month)
      sm_root_pct      = percentile of sm_root vs baseline years, same county and calendar month
                         (see baseline_percentile)
      sm_root_anom     = sm_root - sm_clim, where sm_clim is the baseline mean of sm_root for
                         that county and calendar month (positive = wetter than normal)
    Duplicate (GEOID, date) rows are dropped first, so a year exported twice is not double counted.
    """
    df, n = read_folder(folder)
    df["date"] = pd.to_datetime(df["date"])
    before = len(df)
    df = df.drop_duplicates(["GEOID", "date"])          # e.g. 2019 exported twice
    df["year"], df["month"] = df["date"].dt.year, df["date"].dt.month
    print(f"ERA5: {n} files, {df['year'].min()}-{df['year'].max()}, "
          f"{df['GEOID'].nunique()} counties, {before - len(df)} duplicate rows dropped")

    total = sum(LAYER_CM.values())
    df["sm_root"] = sum(df[c] * w for c, w in LAYER_CM.items()) / total
    df["sm_surface"] = df["sm1"]
    df["swe_mm"] = df["swe"] * 1000
    df["snowmelt_mm"] = df["snowmelt_month"] * 1000

    df = df.sort_values(["GEOID", "year", "month"]).reset_index(drop=True)
    df["snowmelt_prev_mm"] = df.groupby("GEOID")["snowmelt_mm"].shift(1)
    df["sm_root_pct"] = baseline_percentile(df, "sm_root", base_start, base_end)
    clim = (df[df["year"].between(base_start, base_end)]
            .groupby(["GEOID", "month"])["sm_root"].mean().rename("sm_clim"))
    df = df.join(clim, on=["GEOID", "month"])
    df["sm_root_anom"] = df["sm_root"] - df["sm_clim"]

    cols = ["GEOID", "year", "month", "sm_surface", "sm_root", "sm_root_pct", "sm_root_anom",
            "swe_mm", "snowmelt_mm", "snowmelt_prev_mm"]
    return df[cols]


def load_nlcd(folder):
    """Load the NLCD county-year land cover table and lag it by one year.

    Calculations:
      wetland_change_since_1999 = wetland_share(year) - wetland_share(1999) for the same county
                                  (negative = wetlands lost since the end of the baseline)
      year -> year + 1          the land cover measured in year t is attached to model year t + 1,
                                so every month only sees land cover that existed before it
    The share columns (developed, wetland, water, impervious) are passed through unchanged.
    """
    df, n = read_folder(folder)
    df = df.drop_duplicates(["GEOID", "year"]).sort_values(["GEOID", "year"])
    print(f"NLCD: {n} files, {df['year'].min()}-{df['year'].max()}, {df['GEOID'].nunique()} counties")
    w1999 = df[df["year"] == 1999].set_index("GEOID")["wetland_share"]
    df["wetland_change_since_1999"] = df["wetland_share"] - df["GEOID"].map(w1999)
    df["year"] = df["year"] + 1          # land cover from year t is used for model year t + 1
    return df


def load_terrain(folder):
    """Load the static terrain table (one row per county, no time dimension).

    Calculations:
      land_km2  = ALAND / 1e6     Census land area, square metres -> square kilometres
      water_km2 = AWATER / 1e6    Census water area, same conversion
    The terrain columns (elev_mean, slope_mean, flat_share, hand_mean, hand_lt5_share) are
    passed through unchanged; they are the same for every month of a county.
    """
    df, _ = read_folder(folder)
    df = df.drop_duplicates("GEOID")
    df["land_km2"] = df.pop("ALAND") / 1e6
    df["water_km2"] = df.pop("AWATER") / 1e6
    print(f"Terrain: {len(df)} counties, columns {[c for c in df.columns if c != 'GEOID']}")
    return df


def main():
    """Join all sources into one county x month panel, check it, and write it out.

    Steps:
      1. Start from the ERA5 rows in the model years (default 2000-2023); this sets the panel rows.
      2. Left-join NLCD on (GEOID, year), already lagged so year t carries land cover from t - 1.
      3. Left-join terrain on GEOID (same values for every month of a county).
      4. If --w is given, left-join the rainfall indices on (GEOID, year, month) and add
             rain_x_wetsoil = rx5_rl_ratio * sm_root_pct
         an interaction term: a big 5-day rain (relative to the 10-year return level) scaled by
         how wet the soil already was, since rain on saturated ground runs off instead of soaking in.
    Checks:
      expected rows = (# counties) * (# model years) * 12; a warning is printed if it differs.
      missing share per column = (# NaN rows) / (# rows), printed for any column above 0.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--era5", required=True)
    ap.add_argument("--nlcd", required=True)
    ap.add_argument("--terrain", required=True)
    ap.add_argument("--w", help="optional w_county_month.csv from w_indices.py")
    ap.add_argument("--out", default="panel_county_month.csv")
    ap.add_argument("--base-start", type=int, default=1950)
    ap.add_argument("--base-end", type=int, default=1999)
    ap.add_argument("--model-start", type=int, default=2000)
    ap.add_argument("--model-end", type=int, default=2023)
    args = ap.parse_args()

    era5 = load_era5(args.era5, args.base_start, args.base_end)
    nlcd = load_nlcd(args.nlcd)
    terrain = load_terrain(args.terrain)

    panel = era5[era5["year"].between(args.model_start, args.model_end)].copy()
    panel = panel.merge(nlcd, on=["GEOID", "year"], how="left")
    panel = panel.merge(terrain, on="GEOID", how="left")

    if args.w:
        w = pd.read_csv(args.w, dtype={"GEOID": str})
        w["GEOID"] = w["GEOID"].str.zfill(5)
        panel = panel.merge(w.drop(columns=["n_days"], errors="ignore"),
                            on=["GEOID", "year", "month"], how="left")
        panel["rain_x_wetsoil"] = panel["rx5_rl_ratio"] * panel["sm_root_pct"]
        print(f"Rainfall: merged {len(w):,} rows")

    # Checks
    expected = panel["GEOID"].nunique() * (args.model_end - args.model_start + 1) * 12
    if len(panel) != expected:
        warnings.warn(f"{len(panel):,} rows, expected {expected:,}: some county-months are missing")
    miss = panel.isna().mean()
    miss = miss[miss > 0].sort_values(ascending=False)
    if len(miss):
        print("columns with missing values (share of rows):")
        print(miss.round(4).to_string())

    panel = panel.sort_values(["GEOID", "year", "month"])
    panel.to_csv(args.out, index=False, float_format="%.5g")
    print(f"wrote {len(panel):,} rows x {panel.shape[1]} columns "
          f"({panel['GEOID'].nunique()} counties, {args.model_start}-{args.model_end}) to {args.out}")


if __name__ == "__main__":
    main()