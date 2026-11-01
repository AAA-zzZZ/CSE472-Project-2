"""
Shrink the NOAA nClimGrid-Daily county files to Midwest counties, one file per year.

Input : folder of monthly files YYYYMM-scaled.csv from
        s3://noaa-nclimgrid-daily-pds/EpiNOAA/v1-0-0/csv/cty/
        columns: region_type,fips,ncei_code,state_name,postal_code,region_name,date,tmax,tmin,tavg,prcp
Output: nclimgrid_county_daily_YYYY.csv.gz   columns: GEOID, date, ppt (mm), tmin (deg C)
        (the format w_indices.py reads)

Usage:
    pip install pandas
    python prep_nclimgrid.py --input data/nclimgrid_cty --out data/nclimgrid_midwest

After it finishes and the yearly files look right, the raw monthly files can be deleted.
"""

import argparse
import glob
import os
import re
from collections import defaultdict

import pandas as pd

MIDWEST_STATEFP = ["17", "18", "19", "20", "26", "27", "29", "31", "38", "39", "46", "55"]
MISSING = -999                     # values at or below this are treated as missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="folder with YYYYMM-scaled.csv files")
    ap.add_argument("--out", required=True, help="output folder for yearly Midwest files")
    ap.add_argument("--states", default=",".join(MIDWEST_STATEFP), help="comma-separated state FIPS")
    ap.add_argument("--start", type=int, default=1951)
    ap.add_argument("--end", type=int, default=2023)
    args = ap.parse_args()
    states = tuple(args.states.split(","))
    os.makedirs(args.out, exist_ok=True)

    by_year = defaultdict(list)
    for f in sorted(glob.glob(os.path.join(args.input, "*-scaled.csv"))):
        m = re.match(r"(\d{4})(\d{2})-scaled\.csv$", os.path.basename(f))
        if m and args.start <= int(m.group(1)) <= args.end:
            by_year[int(m.group(1))].append(f)
    if not by_year:
        raise SystemExit(f"no YYYYMM-scaled.csv files for {args.start}-{args.end} in {args.input}")

    missing_years = [y for y in range(args.start, args.end + 1) if len(by_year.get(y, [])) != 12]
    if missing_years:
        print(f"WARNING: years without all 12 monthly files: {missing_years}")

    for year in sorted(by_year):
        parts = []
        stray = {}
        for f in by_year[year]:
            df = pd.read_csv(f, dtype={"fips": str, "date": str}, usecols=["fips", "date", "tmin", "prcp"],
                             skipinitialspace=True)
            df["fips"] = df["fips"].str.strip().str.zfill(5)
            df = df[df["fips"].str[:2].isin(states)]
            # Keep only dates inside this file's own month; record anything else.
            d = pd.to_datetime(df["date"].str.strip(), errors="coerce")
            ym = os.path.basename(f)[:6]
            inside = d.dt.strftime("%Y%m") == ym
            if (~inside).any():
                for v, n in df.loc[~inside, "date"].value_counts().items():
                    stray[f"{v!r} in {os.path.basename(f)}"] = n
            df = df[inside].copy()
            df["date"] = d[inside].dt.strftime("%Y-%m-%d")
            parts.append(df)
        if stray:
            print(f"  {year}: dropped rows with dates outside their file's month: {stray}")
        out = pd.concat(parts, ignore_index=True).rename(columns={"fips": "GEOID", "prcp": "ppt"})
        for c in ["ppt", "tmin"]:
            out[c] = pd.to_numeric(out[c], errors="coerce")
            out.loc[out[c] <= MISSING, c] = float("nan")
        # Some county-days appear more than once in the source files (e.g. one row with values,
        # one with -999.99). Keep the row with the most non-missing values.
        n_raw = len(out)
        out["_nvalid"] = out[["ppt", "tmin"]].notna().sum(axis=1)
        out = (out.sort_values(["GEOID", "date", "_nvalid"], ascending=[True, True, False])
                  .drop_duplicates(["GEOID", "date"], keep="first"))
        out = out[["GEOID", "date", "ppt", "tmin"]]
        path = os.path.join(args.out, f"nclimgrid_county_daily_{year}.csv.gz")
        out.to_csv(path, index=False, float_format="%.2f")
        days = pd.Period(f"{year}-12-31").dayofyear
        print(f"{year}: {len(by_year[year])} months, {out['GEOID'].nunique()} counties, "
              f"{len(out):,} rows (expected {out['GEOID'].nunique() * days:,}), "
              f"{n_raw - len(out):,} duplicates removed, "
              f"{out[['ppt', 'tmin']].isna().mean().max():.2%} missing")


if __name__ == "__main__":
    main()