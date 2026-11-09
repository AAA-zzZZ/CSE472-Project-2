"""
Final merge: join the input panel, the SHELDUS outcome and the static and yearly county
tables into the one table the models use.

One row per county per month, 2000-2023 (1,055 counties x 288 months = 303,840 rows).

Inputs:
  --inputs      panel_county_month.csv        from build_panel.py (W, X, terrain)
  --outcome     model_data_monthly_panel.csv  from build_monthly_panel.py (Y, census housing)
  --thresholds  out/prism_midwest/w_county_thresholds.csv
                                              from w_indices.py (C: PRISM 2000-2009 rain climate;
                                              out/w_county_thresholds.csv is the NOAA 1951-1999 one)
  --clean-dir   data/clean/                   optional tables from the data-collection guide;
                                              each is joined if its file exists:
      census_county_year.csv         GEOID, year, housing_units, population, median_value, ...
      ghsl_county_year.csv           GEOID, year, built_m2 (ghsl_features.py; adds log_built_surface)
      nfip_policies_county_year.csv  GEOID, year, policies_in_force
      hma_county_year.csv            GEOID, year, buyouts_cum, elevations_cum
      crs_county_year.csv            GEOID, year, crs_best_class, crs_class5_or_better
      soils_county.csv               GEOID, soil_cd_share (static)

Output:
  model_panel.csv  (git-ignored; rebuild with this script)

Usage:
    python merge_panel.py               # PRISM panel with every data/clean/ table, model_panel.csv
    python merge_panel.py --thresholds out/w_county_thresholds.csv --out model_panel_noaa.csv

Leakage rules:
  * SHELDUS supplies only the outcome columns; nothing derived from losses is an input.
  * Yearly tables are saved for their own year; this script joins year t - 1 to model year t,
    so do not shift years before saving them.
  * The C columns come from 2000-2009 daily rainfall only (PRISM): before the test years, but
    overlapping the training years.
"""

import argparse
import os

import numpy as np
import pandas as pd

KEYS = ["GEOID", "year", "month"]
N_COUNTIES = 1055

# outcome columns taken from the SHELDUS panel; split is the train/test key
OUTCOME_COLS = ["PropertyDmgADJ", "log_PropertyDmgADJ", "has_damage", "split"]
# census housing already in the outcome panel (IPUMS NHGIS, not SHELDUS); replaced
# by census_county_year.csv once that table exists
HOUSING_COLS = ["log_housing_units", "urban_share"]

# C: each county's 1951-1999 rain climate (mm)
C_NAMES = {"p95": "c_wetday_p95_mm", "p99": "c_wetday_p99_mm",
           "rl2": "c_rx5_rl2_mm", "rl10": "c_rx5_rl10_mm", "rl25": "c_rx5_rl25_mm"}

YEARLY_TABLES = ["census_county_year.csv", "ghsl_county_year.csv", "nfip_policies_county_year.csv",
                 "hma_county_year.csv", "crs_county_year.csv"]
STATIC_TABLES = ["soils_county.csv"]


def read(path):
    df = pd.read_csv(path, dtype={"GEOID": str})
    df["GEOID"] = df["GEOID"].str.zfill(5)
    return df


def check_counties(df, name, counties):
    found = set(df["GEOID"])
    extra, missing = sorted(found - counties), sorted(counties - found)
    if extra or missing:
        print(f"  WARNING {name}: {len(missing)} panel counties missing {missing[:5]}, "
              f"{len(extra)} codes not in the panel {extra[:5]}")


def join_yearly(panel, path, counties):
    """Join a county-year table with a one-year lag: values saved for year t feed model year t + 1."""
    table = read(path)
    name = os.path.basename(path)
    if table.duplicated(["GEOID", "year"]).any():
        raise SystemExit(f"{name}: duplicate GEOID-year rows")
    check_counties(table, name, counties)
    cols = [c for c in table.columns if c not in ("GEOID", "year")]
    table = table.assign(year=table["year"] + 1)
    panel = panel.merge(table, on=["GEOID", "year"], how="left")
    print(f"  {name}: {cols} (from year - 1), {panel[cols].isna().any(axis=1).mean():.1%} rows missing")
    return panel


def join_static(panel, path, counties):
    table = read(path)
    name = os.path.basename(path)
    if table.duplicated("GEOID").any():
        raise SystemExit(f"{name}: duplicate GEOID rows")
    check_counties(table, name, counties)
    cols = [c for c in table.columns if c != "GEOID"]
    panel = panel.merge(table, on="GEOID", how="left")
    print(f"  {name}: {cols} (static), {panel[cols].isna().any(axis=1).mean():.1%} rows missing")
    return panel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", default="panel_county_month.csv")
    ap.add_argument("--outcome", default="model_data_monthly_panel.csv")
    ap.add_argument("--thresholds", default="out/prism_midwest/w_county_thresholds.csv")
    ap.add_argument("--clean-dir", default="data/clean")
    ap.add_argument("--out", default="model_panel.csv")
    args = ap.parse_args()

    # inputs: W, X and terrain, one row per county-month
    panel = read(args.inputs)
    counties = set(panel["GEOID"])
    print(f"inputs: {len(panel):,} rows, {len(counties)} counties, {panel.shape[1] - 3} variables")
    if len(counties) != N_COUNTIES:
        print(f"  WARNING expected {N_COUNTIES} counties")

    # outcome: SHELDUS property loss, 0 where there is no record
    outcome = pd.read_csv(args.outcome, dtype={"County_FIPS": str})
    outcome = outcome.rename(columns={"County_FIPS": "GEOID", "Year": "year", "Month": "month"})
    outcome = outcome[KEYS + OUTCOME_COLS + HOUSING_COLS]
    joined = panel.merge(outcome, on=KEYS, how="outer", indicator=True)
    unmatched = joined["_merge"].value_counts()
    if unmatched.get("left_only", 0) or unmatched.get("right_only", 0):
        raise SystemExit(f"inputs and outcome do not match one-to-one: {unmatched.to_dict()}")
    panel = joined.drop(columns="_merge")
    print(f"outcome: {panel['has_damage'].sum():,} damage months ({panel['has_damage'].mean():.1%}), "
          f"${panel['PropertyDmgADJ'].sum() / 1e9:.1f}B of property loss")

    # C: rain climate from the baseline years (PRISM 2000-2009 by default)
    clim = read(args.thresholds).rename(columns=C_NAMES)
    check_counties(clim, os.path.basename(args.thresholds), counties)
    panel = panel.merge(clim, on="GEOID", how="left")
    print(f"climate (C) from {args.thresholds}: {list(C_NAMES.values())}")

    # optional tables from the data-collection guide
    print(f"tables in {args.clean_dir}:")
    found = False
    for name in YEARLY_TABLES + STATIC_TABLES:
        path = os.path.join(args.clean_dir, name)
        if not os.path.exists(path):
            continue
        found = True
        panel = (join_yearly if name in YEARLY_TABLES else join_static)(panel, path, counties)
    if not found:
        print("  none yet")
    if "policies_in_force" in panel and "housing_units" in panel:
        panel["nfip_policies_per_hu"] = panel["policies_in_force"] / panel["housing_units"]
    if "built_m2" in panel:
        panel["log_built_surface"] = np.log(panel["built_m2"])

    # checks
    if panel.duplicated(KEYS).any():
        raise SystemExit("duplicate county-months after merging")
    miss = panel.isna().mean()
    miss = miss[miss > 0].sort_values(ascending=False)
    print("columns with missing values (share of rows):", miss.round(4).to_dict() or "none")
    print("mean of selected inputs in months with and without damage:")
    show = [c for c in ["p_month", "rx5", "rx5_rl_ratio", "sm_root_pct", "snowmelt_mm",
                        "c_rx5_rl10_mm"] if c in panel]
    print(panel.groupby("has_damage")[show].mean().round(2).to_string())

    front = KEYS + ["split"] + OUTCOME_COLS[:3]
    panel = panel[front + [c for c in panel.columns if c not in front]]
    panel = panel.sort_values(KEYS)
    panel.to_csv(args.out, index=False, float_format="%.5g")
    print(f"wrote {len(panel):,} rows x {panel.shape[1]} columns to {args.out}")


if __name__ == "__main__":
    main()
