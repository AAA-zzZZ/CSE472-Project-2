"""
County census table for the model: exposure (X) and vulnerability / capacity (A), one row per
county per year, 1999-2023.

Input : nhgis0001_csv/nhgis0001_csv/   IPUMS NHGIS extract "flood census 2000-2023"
          nhgis0001_ts_nominal_county.csv   time series AV0 population, A41 housing units,
                                            B79 median household income, BV3 poverty by age
          nhgis0001_ds*_county.csv          source tables, 2000 Census SF3a and each ACS
                                            5-year release 2005-2009 ... 2019-2023:
                                            units in structure, year built, median value
Output: data/clean/census_county_year.csv
          GEOID, year, housing_units, population, median_value, median_income, poverty_rate,
          mobile_home_share, built_pre1980_share
        merge_panel.py joins it with a one-year lag (model year t uses census year t - 1).

Method:
  * Each estimate is placed in a year: the 2000 Census in 2000, each ACS 5-year release in
    its last year (2006-2010 -> 2010). Years in between are interpolated linearly per county;
    1999 copies 2000 (no earlier data in the extract).
  * Dollars are converted to 2024 dollars with the CPI-U, the same base as the SHELDUS loss:
    2000 Census income is in 1999 dollars, 2000 Census home value in 2000 dollars, and each
    ACS release in the dollars of its last year.
  * Shares come from counts: poverty = people below the poverty line / people whose poverty
    status is determined; mobile homes / housing units; homes built before 1980 / housing units.
  * Variable codes differ between datasets (GAF in 2000, ASUG in 2019-2023), so source-table
    columns are found from each file's codebook by table code and label.

Caveat: an ACS release ending in year t is published in December of year t + 1, so with the
one-year lag in merge_panel.py the model uses it a few months before it was released.

Usage:
    python census_features.py
"""

import glob
import os
import re

import numpy as np
import pandas as pd

SRC = "nhgis0001_csv/nhgis0001_csv"
OUT = "data/clean/census_county_year.csv"
STATES = ["17", "18", "19", "20", "26", "27", "29", "31", "38", "39", "46", "55"]
OLD_TO_NEW = {"46113": "46102"}        # Shannon County SD became Oglala Lakota (2015)
YEARS = range(1999, 2024)
N_COUNTIES = 1055

# CPI-U, U.S. city average, all items, annual average (BLS series CUUR0000SA0)
CPI = {1999: 166.6, 2000: 172.2, 2001: 177.1, 2002: 179.9, 2003: 184.0, 2004: 188.9,
       2005: 195.3, 2006: 201.6, 2007: 207.342, 2008: 215.303, 2009: 214.537, 2010: 218.056,
       2011: 224.939, 2012: 229.594, 2013: 232.957, 2014: 236.736, 2015: 237.017,
       2016: 240.007, 2017: 245.120, 2018: 251.107, 2019: 255.657, 2020: 258.811,
       2021: 270.970, 2022: 292.655, 2023: 304.702, 2024: 313.689}


def to_2024(values, dollar_year):
    return values * CPI[2024] / CPI[dollar_year]


def geoid(df, state_col, county_col):
    g = df[state_col].astype(str).str.zfill(2) + df[county_col].astype(str).str.zfill(3)
    return g.replace(OLD_TO_NEW)


# ---------------------------------------------------------------
# 1. time series: population, housing units, median income, poverty
# ---------------------------------------------------------------
ts = pd.read_csv(f"{SRC}/nhgis0001_ts_nominal_county.csv", dtype=str, encoding="latin-1")
ts["GEOID"] = geoid(ts, "STATEFP", "COUNTYFP")
ts = ts[ts["STATEFP"].str.zfill(2).isin(STATES)].set_index("GEOID")

# period suffix -> year the estimate is placed in: '2000' census, '105' = ACS 2006-2010 -> 2010
PERIODS = {"2000": 2000, **{f"{y % 100 * 10 + 5:03d}" if y < 2010 else f"{y - 2000}5": y
                             for y in range(2010, 2024)}}


def series(prefix, period):
    col = prefix + period
    return pd.to_numeric(ts[col], errors="coerce") if col in ts else None


rows = []
for period, year in PERIODS.items():
    row = pd.DataFrame(index=ts.index)
    row["year"] = year
    row["population"] = series("AV0AA", period)
    row["housing_units"] = series("A41AA", period)
    income = series("B79AA", period)
    # census 2000 asked about 1999 income; an ACS release is in the dollars of its last year
    row["median_income"] = None if income is None else to_2024(income, 1999 if year == 2000 else year)
    below = [series(f"BV3A{s}", period) for s in "ABCDE"]           # below poverty, 5 age groups
    above = [series(f"BV3A{s}", period) for s in "FGHIJ"]           # at or above, same groups
    if all(v is not None for v in below + above):
        n_below, n_all = sum(below), sum(below) + sum(above)
        row["poverty_rate"] = n_below / n_all
    rows.append(row)
ts_long = pd.concat(rows).reset_index()
missing_periods = [p for p in PERIODS if f"AV0AA{p}" not in ts]
print(f"time series: {ts_long['GEOID'].nunique()} counties, years {sorted(ts_long['year'].unique())}"
      + (f"; periods not found: {missing_periods}" if missing_periods else ""))


# ---------------------------------------------------------------
# 2. source tables: units in structure, year built, median value
# ---------------------------------------------------------------
def read_codebook(path):
    """{source table code: {variable code: label}} for the estimate columns of one dataset."""
    tables, current = {}, None
    for line in open(path, encoding="latin-1"):
        m = re.match(r"\s+Source code:\s+(\S+)", line)
        if m:
            current = m.group(1)
            tables.setdefault(current, {})
            continue
        m = re.match(r"\s+([A-Z0-9]{3,5}\d{3}):\s+(.+)", line)   # data variables end in 3 digits
        # ACS codes are 7-8 characters ending E### (estimate) or M### (margin of error, skipped);
        # 2000 Census codes are 6 characters. context fields like GISJOIN have no digits
        if m and current and not (len(m.group(1)) >= 7 and re.search(r"M\d{3}$", m.group(1))):
            tables[current][m.group(1)] = m.group(2).strip()
    return tables


def built_before_1980(label):
    years = [int(y) for y in re.findall(r"(\d{4})", label)]
    return bool(years) and ("earlier" in label or max(years) <= 1979)


src_rows = []
for path in sorted(glob.glob(f"{SRC}/nhgis0001_ds*_county.csv")):
    tag = re.search(r"_ds\d+_(\d+)_county", path).group(1)
    year = int(tag[:4])                         # '2000' census, '20095' = ACS 2005-2009 -> 2009
    book = read_codebook(path.replace(".csv", "_codebook.txt"))
    df = pd.read_csv(path, dtype=str, encoding="latin-1")
    df["GEOID"] = geoid(df, "STATEA", "COUNTYA")
    df = df[df["STATEA"].str.zfill(2).isin(STATES)].set_index("GEOID")

    def table(code_start):
        code = next(c for c in book if c.startswith(code_start))
        cols = book[code]
        return {k: v for k, v in cols.items()}, df[list(cols)].apply(pd.to_numeric, errors="coerce")

    units_lab, units = table("NH030" if year == 2000 else "B25024")
    built_lab, built = table("NH034" if year == 2000 else "B25034")
    value_lab, value = table("NH085" if year == 2000 else "B25077")

    def total(labels, data):
        tot = [k for k, v in labels.items() if v == "Total"]
        return data[tot[0]] if tot else data.sum(axis=1)   # 2000 tables have no total column

    mobile = [k for k, v in units_lab.items() if v.lower().startswith("mobile home")]
    old = [k for k, v in built_lab.items() if v != "Total" and built_before_1980(v)]
    out = pd.DataFrame(index=df.index)
    out["year"] = year
    out["mobile_home_share"] = units[mobile[0]] / total(units_lab, units)
    out["built_pre1980_share"] = built[old].sum(axis=1) / total(built_lab, built)
    out["median_value"] = to_2024(value.iloc[:, 0], year)
    src_rows.append(out)
    print(f"  {os.path.basename(path)}: year {year}, {len(df)} counties, "
          f"pre-1980 brackets: {[built_lab[k] for k in old]}")
src_long = pd.concat(src_rows).reset_index()


# ---------------------------------------------------------------
# 3. one row per county per year, interpolated between survey years
# ---------------------------------------------------------------
anchors = ts_long.merge(src_long, on=["GEOID", "year"], how="outer")
VARS = ["housing_units", "population", "median_value", "median_income", "poverty_rate",
        "mobile_home_share", "built_pre1980_share"]
counties = sorted(anchors["GEOID"].unique())
grid = pd.MultiIndex.from_product([counties, YEARS], names=["GEOID", "year"])
anchors = anchors.groupby(["GEOID", "year"])[VARS].mean()        # one value per county-year
census = anchors.reindex(grid)
# linear in time between the survey years, per county; 1999 takes the 2000 value
census = census.groupby(level="GEOID", group_keys=False).apply(
    lambda g: g.reset_index(level="GEOID", drop=True).interpolate(method="index", limit_direction="both")
    .assign(GEOID=g.index.get_level_values("GEOID")[0]).set_index("GEOID", append=True)
    .reorder_levels(["GEOID", "year"]))
census = census.reset_index()


# ---------------------------------------------------------------
# 4. checks and save
# ---------------------------------------------------------------
panel_counties = set(pd.read_csv("out/w_county_thresholds.csv", dtype={"GEOID": str})["GEOID"])
extra, missing = sorted(set(counties) - panel_counties), sorted(panel_counties - set(counties))
print(f"\n{len(counties)} counties (panel has {N_COUNTIES}); not in panel: {extra[:5]}; missing: {missing[:5]}")
census = census[census["GEOID"].isin(panel_counties)]
print(f"rows: {len(census):,} ({census['GEOID'].nunique()} counties x {len(YEARS)} years)")
miss = census[VARS].isna().sum()
print("missing values:", miss[miss > 0].to_dict() or "none")
print("\nsummary (2024 dollars for value and income):")
print(census[VARS].describe().T[["mean", "min", "50%", "max"]].round(3).to_string())
print("\nmedians by year (check for jumps between sources):")
print(census.groupby("year")[["median_income", "median_value", "poverty_rate", "built_pre1980_share"]]
      .median().iloc[[0, 1, 5, 10, 11, 15, 20, 24]].round(3).to_string())

os.makedirs(os.path.dirname(OUT), exist_ok=True)
census[["GEOID", "year"] + VARS].to_csv(OUT, index=False, float_format="%.6g")
print(f"\nsaved {OUT}: {len(census):,} rows")
