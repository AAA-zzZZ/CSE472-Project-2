"""
OpenFEMA adaptation tables (A) for the 12 Midwest states: NFIP policies in force and HMA buyouts
and elevations by county and year, in the format merge_panel.py joins (data/openfema/README.md).

Sources (checked 2026-11-09; the older FimaNfipPolicies v2, HazardMitigationAssistanceMitigatedProperties
v4 and HazardMitigationAssistanceProjects v4 were removed on 2026-10-15):
  NFIP Redacted Policies v3        https://www.fema.gov/openfema-data-page/nfip-redacted-policies-v3
      bulk file NfipPoliciesV3.parquet, 3.7 GB, 74.7M policy records; no record starts before 2009
  HMA Subapplications Project Site Inventories v1
      https://www.fema.gov/openfema-data-page/hma-subapplications-project-site-inventories-v1
      one row per mitigated site: county, primaryActivity (Acquisition, Elevation, ...)
  HMA Subapplications v2           https://www.fema.gov/openfema-data-page/hma-subapplications-v2
      fiscalYear and status of each subapplication, joined on the subapplication ID

Outputs (data/clean/, saved under their own year; merge_panel.py applies the one-year lag):
  nfip_policies_county_year.csv  GEOID, year, policies_in_force   1999-2022, all 1,055 counties
      policies in force on July 1 (effective <= July 1 < termination or cancellation).
      Years before 2010 are left empty: the data starts in 2009, so July 1, 2009 misses the
      policies that began in 2008. Unknown is not zero, so they are not filled.
  hma_county_year.csv            GEOID, year, buyouts_cum, elevations_cum   1999-2022, 0 if none
      cumulative count of acquisition / elevation sites since 1989 by program fiscal year, for
      subapplications that were approved or later (not denied, withdrawn, pending, ...).
      For disaster grants the fiscal year is the year of the disaster, so work finishes later.

Never use NFIP claims as an input: they come from the losses being predicted.

Usage (from the repository root; the raw files are git-ignored). Download the three files in
FILES into data/openfema/raw/ first (about 4 GB; FEMA refuses Python's downloader, so use curl or
a browser), for example:
    curl.exe -L -o data/openfema/raw/NfipPoliciesV3.parquet <url>
then:
    python openfema_features.py
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

STATES = {"17": "IL", "18": "IN", "19": "IA", "20": "KS", "26": "MI", "27": "MN",
          "29": "MO", "31": "NE", "38": "ND", "39": "OH", "46": "SD", "55": "WI"}
START, END = 1999, 2022           # model years 2000-2023 read year - 1
NFIP_FIRST_YEAR = 2010            # first July 1 with complete policy terms
# old South Dakota code (see HANDOFF.md)
OLD_CODES = {"46113": "46102"}

FILES = {
    "nfip": ("NfipPoliciesV3.parquet",
             "https://www.fema.gov/about/reports-and-data/openfema/v3/NfipPoliciesV3.parquet"),
    "sites": ("HmaSubapplicationsProjectSiteInventories.csv",
              "https://www.fema.gov/api/open/v1/HmaSubapplicationsProjectSiteInventories.csv"),
    "subs": ("HmaSubapplications.csv", "https://www.fema.gov/api/open/v2/HmaSubapplications.csv"),
}
NFIP_COLS = ["propertyState", "censusGeoid", "policyEffectiveDate", "policyTerminationDate",
             "cancellationDateOfFloodPolicy", "policyCount"]
# subapplication statuses that mean the project was funded
FUNDED = {"Approved", "Awarded", "Subaward Accepted", "Closed", "Closeout Initiated", "Completed",
          "Subgrant Financial Reconciliation"}


def check_files(raw, skip_nfip):
    missing = [(name, url) for key, (name, url) in FILES.items()
               if not (skip_nfip and key == "nfip") and not os.path.exists(os.path.join(raw, name))]
    if missing:
        print(f"missing in {raw}/; download them with curl or a browser:")
        for name, url in missing:
            print(f'  curl.exe -L -o "{os.path.join(raw, name)}" "{url}"')
        sys.exit(1)


def county_table(geojson="data/counties_midwest.geojson"):
    with open(geojson) as f:
        props = [feat["properties"] for feat in json.load(f)["features"]]
    counties = pd.DataFrame(props)[["GEOID", "STATEFP", "NAME"]]
    # St. Louis city (29510) and St. Louis County (29189) share the name
    counties.loc[counties["GEOID"] == "29510", "NAME"] = "St. Louis city"
    return counties


def all_rows(counties):
    return pd.MultiIndex.from_product([sorted(counties["GEOID"]), range(START, END + 1)],
                                      names=["GEOID", "year"]).to_frame(index=False)


# ---------------------------------------------------------------
# 1. NFIP policies in force
# ---------------------------------------------------------------
def nfip(raw, counties):
    pf = pq.ParquetFile(os.path.join(raw, FILES["nfip"][0]))
    states = pa.array(list(STATES.values()))
    years = range(2009, END + 1)
    totals, n_rows, n_nogeo = [], 0, 0
    for batch in pf.iter_batches(columns=NFIP_COLS, batch_size=2_000_000):
        batch = batch.filter(pc.is_in(batch["propertyState"], value_set=states))
        if batch.num_rows == 0:
            continue
        df = batch.to_pandas()
        n_rows += len(df)
        geo = df["censusGeoid"].astype("string")
        n_nogeo += int(geo.isna().sum())
        df["GEOID"] = geo.str[:5].replace(OLD_CODES)
        eff = pd.to_datetime(df["policyEffectiveDate"])
        end = pd.to_datetime(df["policyTerminationDate"])
        cancel = pd.to_datetime(df["cancellationDateOfFloodPolicy"])
        end = end.where(cancel.isna() | (cancel > end), cancel)
        for y in years:
            day = pd.Timestamp(y, 7, 1)
            live = (eff <= day) & (end > day) & df["GEOID"].notna()
            if live.any():
                totals.append(df.loc[live].groupby("GEOID")["policyCount"].sum().rename(y))
        print(f"  {n_rows:,} Midwest policy records read")
    print(f"NFIP: {n_rows:,} records in the 12 states, {n_nogeo:,} without a census code (dropped)")

    by_year = pd.concat(totals, axis=1).T.groupby(level=0).sum().T          # GEOID x year
    extra = sorted(set(by_year.index) - set(counties["GEOID"]))
    if extra:
        print(f"  dropped {len(extra)} codes not in the county list: {extra[:5]}")
    out = all_rows(counties).join(by_year.stack().rename("policies_in_force"), on=["GEOID", "year"])
    known = out["year"] >= NFIP_FIRST_YEAR
    out.loc[known, "policies_in_force"] = out.loc[known, "policies_in_force"].fillna(0)
    out.loc[~known, "policies_in_force"] = np.nan
    state_tot = (out[known].assign(state=out["GEOID"].str[:2].map(STATES))
                 .pivot_table(index="year", columns="state", values="policies_in_force", aggfunc="sum"))
    print("policies in force on July 1, by state (check against FEMA's published totals):")
    print(state_tot.astype(int).to_string())
    return out


# ---------------------------------------------------------------
# 2. HMA buyouts and elevations
# ---------------------------------------------------------------
def name_key(s):
    s = s.str.lower().str.replace(r"\b(county|parish|city of)\b", "", regex=True)
    s = s.str.replace(r"\bsaint\b", "st", regex=True).str.replace(r"[^a-z]", "", regex=True)
    return s


def hma(raw, counties):
    sites = pd.read_csv(os.path.join(raw, FILES["sites"][0]), dtype=str)
    subs = pd.read_csv(os.path.join(raw, FILES["subs"][0]), dtype=str,
                       usecols=["subapplicationIdentifier", "fiscalYear", "status", "program"])
    sites = sites[sites["stateCode"].isin(STATES)]
    df = sites.merge(subs, left_on="subapplicationId", right_on="subapplicationIdentifier", how="left")
    print(f"HMA: {len(df):,} project sites in the 12 states, {df['fiscalYear'].isna().mean():.1%} "
          f"without a matching subapplication")
    act = df["primaryActivity"].fillna("")
    df = df[act.isin(["Acquisition", "Elevation"])]
    print(f"  acquisition or elevation: {len(df):,}; status {df['status'].value_counts().to_dict()}")
    df = df[df["status"].isin(FUNDED)].copy()
    df["year"] = pd.to_numeric(df["fiscalYear"])

    # county: state code + county code where given, otherwise match the county name in that state
    code = df["stateCode"] + df["countyCode"].str.zfill(3)
    keys = counties.assign(key=name_key(counties["NAME"])).set_index(["STATEFP", "key"])["GEOID"]
    by_name = pd.Series(list(zip(df["stateCode"], name_key(df["county"].fillna(""))))).map(keys)
    df["GEOID"] = code.where(df["countyCode"].notna(), by_name.to_numpy()).replace(OLD_CODES)
    bad = ~df["GEOID"].isin(counties["GEOID"])
    print(f"  funded: {len(df):,} sites, {bad.sum()} without a county "
          f"(e.g. {df.loc[bad, 'county'].dropna().unique()[:6].tolist()}), dropped")
    df = df[~bad]
    print("  funded sites by fiscal year (gaps are gaps in the FEMA data, not in mitigation):")
    print("  " + str(df.groupby((df["year"] // 5) * 5).size().to_dict()))

    df["kind"] = np.where(df["primaryActivity"] == "Acquisition", "buyouts_cum", "elevations_cum")
    counts = df.groupby(["GEOID", "kind", "year"]).size().unstack("kind", fill_value=0)
    out = all_rows(counties)
    first = int(min(df["year"].min(), START))
    grid = pd.MultiIndex.from_product([sorted(counties["GEOID"]), range(first, END + 1)], names=["GEOID", "year"])
    cum = counts.reindex(grid, fill_value=0).groupby(level="GEOID").cumsum()
    out = out.join(cum, on=["GEOID", "year"])
    for col in ["buyouts_cum", "elevations_cum"]:
        if col not in out:
            out[col] = 0
    out[["buyouts_cum", "elevations_cum"]] = out[["buyouts_cum", "elevations_cum"]].fillna(0).astype(int)
    last = out[out["year"] == END]
    print(f"  by {END}: {int(last['buyouts_cum'].sum()):,} buyouts in {(last['buyouts_cum'] > 0).sum()} counties, "
          f"{int(last['elevations_cum'].sum()):,} elevations in {(last['elevations_cum'] > 0).sum()} counties")
    return out[["GEOID", "year", "buyouts_cum", "elevations_cum"]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default="data/openfema/raw", help="folder for the downloaded files")
    ap.add_argument("--out-dir", default="data/clean")
    ap.add_argument("--skip-nfip", action="store_true", help="build only the HMA table")
    args = ap.parse_args()

    check_files(args.raw, args.skip_nfip)
    counties = county_table()
    os.makedirs(args.out_dir, exist_ok=True)

    table = hma(args.raw, counties)
    table.to_csv(os.path.join(args.out_dir, "hma_county_year.csv"), index=False)
    print(f"saved hma_county_year.csv: {len(table):,} rows\n")

    if not args.skip_nfip:
        table = nfip(args.raw, counties)
        table.to_csv(os.path.join(args.out_dir, "nfip_policies_county_year.csv"), index=False, float_format="%.0f")
        print(f"saved nfip_policies_county_year.csv: {len(table):,} rows, "
              f"years before {NFIP_FIRST_YEAR} left empty")


if __name__ == "__main__":
    main()
