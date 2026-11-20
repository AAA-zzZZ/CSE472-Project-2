"""
County-month panel for Washington County, Ohio (39167) and its four Ohio neighbours,
built from data already in the repository plus the PRISM pull.

Reuses (no new Earth Engine pulls):
  data/gee_era5/      ERA5-Land, 1950-2023   -> sm_root_pct (1950-1999 baseline), swe_mm, snowmelt_mm
  data/gee_nlcd/      Annual NLCD, 1999-2023 -> impervious_mean, wetland_share (year - 1)
  data/gee_terrain/   MERIT Hydro, TIGER     -> hand_lt5_share, land_km2
  loss_cleaned_monthly.csv  SHELDUS outcome (0 where no record)
New:
  --w-dir  output folder of w_indices.py run on the PRISM pull
           -> p_month, rx5_rl_ratio, frost_days (W) and c_rx5_rl10_mm (C, 2000-2009 baseline)
           Optional, so the panel can be checked before PRISM arrives.

Outputs (in --out-dir):
  county_set_panel.csv  5 counties x 168 months (2010-2023): outcome + reduced inputs
  focus_panel_39167.csv Washington's 168 months + nb_* columns: the land-area-weighted
                        mean of the four neighbours' hazard in the same month

Usage:
    python yana_workspace/build_county_panel.py --w-dir out/prism_39167 --out-dir yana_workspace/data
"""

import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import build_panel as bp  # noqa: E402

FOCUS = "39167"
GEOIDS = ["39167", "39009", "39111", "39115", "39121"]
NAMES = {"39167": "Washington", "39009": "Athens", "39111": "Monroe", "39115": "Morgan", "39121": "Noble"}
MODEL_START, MODEL_END = 2010, 2023  # analysis period; 2000-2009 is the PRISM rain baseline

ERA5_COLS = ["sm_root_pct", "swe_mm", "snowmelt_mm"]
NLCD_COLS = ["impervious_mean", "wetland_share"]
TERRAIN_COLS = ["hand_lt5_share", "land_km2"]
W_COLS = ["p_month", "rx5_rl_ratio", "frost_days"]
OUTCOME_COLS = ["PropertyDmgADJ", "log_PropertyDmgADJ", "has_damage", "split"]
# neighbour hazard: the inputs that change month to month
NB_COLS = ["p_month", "rx5_rl_ratio", "frost_days", "sm_root_pct", "swe_mm", "snowmelt_mm"]

# build_panel's loaders read whole Midwest folders; keep only the five counties
# before the per-county percentile step, which is slow on 1,055 counties
_read_folder = bp.read_folder


def read_five(folder, pattern="*.csv"):
    df, n = _read_folder(folder, pattern)
    return df[df["GEOID"].isin(GEOIDS)].reset_index(drop=True), n


bp.read_folder = read_five


def outcome(loss_file):
    loss = pd.read_csv(loss_file, dtype={"County_FIPS": str})
    loss = loss[loss["County_FIPS"].isin(GEOIDS) & loss["Year"].between(MODEL_START, MODEL_END)]
    dollars = loss.groupby(["County_FIPS", "Year", "Month"])["PropertyDmg(ADJ 2024)"].sum()
    dollars.index.names = ["GEOID", "year", "month"]
    grid = pd.MultiIndex.from_product([GEOIDS, range(MODEL_START, MODEL_END + 1), range(1, 13)],
                                      names=["GEOID", "year", "month"])
    out = dollars.reindex(grid, fill_value=0.0).rename("PropertyDmgADJ").reset_index()
    out["log_PropertyDmgADJ"] = np.log10(out["PropertyDmgADJ"] + 1)
    out["has_damage"] = (out["PropertyDmgADJ"] > 0).astype(int)
    out["split"] = np.where(out["year"] <= 2018, "train", "test")
    return out


def load_ghsl(folder):
    """GHSL exposure (ghsl_county_export.py): interpolate the 5-year epochs to every year, then
    lag by one year like NLCD, so each month only sees exposure measured before it.
      log_population = ln(people), built_share = built-up km2 / land km2 (built_share is set later)."""
    g = pd.concat([pd.read_csv(f, dtype={"GEOID": str}) for f in
                   sorted(glob.glob(os.path.join(folder, "*.csv")))])
    g["GEOID"] = g["GEOID"].str.zfill(5)
    years = range(g["epoch"].min(), MODEL_END + 1)
    rows = []
    for gid, d in g.groupby("GEOID"):
        d = d.sort_values("epoch")
        for col in ["built_km2", "population"]:
            # linear between epochs, held flat after the last one
            vals = np.interp(list(years), d["epoch"], d[col])
            rows.append(pd.DataFrame({"GEOID": gid, "year": [y + 1 for y in years], "col": col, "v": vals}))
    out = pd.concat(rows).pivot_table(index=["GEOID", "year"], columns="col", values="v").reset_index()
    out["log_population"] = np.log(out["population"])
    return out[["GEOID", "year", "built_km2", "log_population"]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--era5", default="data/gee_era5")
    ap.add_argument("--nlcd", default="data/gee_nlcd")
    ap.add_argument("--terrain", default="data/gee_terrain")
    ap.add_argument("--loss", default="loss_cleaned_monthly.csv")
    ap.add_argument("--w-dir", help="w_indices.py output folder for the PRISM pull")
    ap.add_argument("--out-dir", default="yana_workspace/data")
    ap.add_argument("--ghsl", help="folder with ghsl_39167.csv from ghsl_county_export.py (optional)")
    args = ap.parse_args()

    panel = outcome(args.loss)
    era5 = bp.load_era5(args.era5, 1950, 1999)
    nlcd = bp.load_nlcd(args.nlcd)
    terrain = bp.load_terrain(args.terrain)
    panel = (panel.merge(era5[["GEOID", "year", "month"] + ERA5_COLS], on=["GEOID", "year", "month"], how="left")
                  .merge(nlcd[["GEOID", "year"] + NLCD_COLS], on=["GEOID", "year"], how="left")
                  .merge(terrain[["GEOID"] + TERRAIN_COLS], on="GEOID", how="left"))

    if args.ghsl:
        panel = panel.merge(load_ghsl(args.ghsl), on=["GEOID", "year"], how="left")
        panel["built_share"] = panel.pop("built_km2") / panel["land_km2"]

    nb_cols = [c for c in NB_COLS if c not in W_COLS]
    if args.w_dir:
        w = pd.read_csv(os.path.join(args.w_dir, "w_county_month.csv"), dtype={"GEOID": str})
        w["GEOID"] = w["GEOID"].str.zfill(5)
        c = pd.read_csv(os.path.join(args.w_dir, "w_county_thresholds.csv"), dtype={"GEOID": str})
        c["GEOID"] = c["GEOID"].str.zfill(5)
        panel = (panel.merge(w[["GEOID", "year", "month"] + W_COLS], on=["GEOID", "year", "month"], how="left")
                      .merge(c[["GEOID", "rl10"]].rename(columns={"rl10": "c_rx5_rl10_mm"}), on="GEOID", how="left"))
        nb_cols = NB_COLS
    else:
        print("no --w-dir: PRISM rain, frost and C columns left out")

    panel.insert(1, "county", panel["GEOID"].map(NAMES))
    panel = panel.sort_values(["GEOID", "year", "month"]).reset_index(drop=True)

    # neighbour hazard for the focus county, weighted by land area
    nb = panel[panel["GEOID"] != FOCUS]
    wsum = lambda g, col: np.average(g[col], weights=g["land_km2"]) if g[col].notna().all() else np.nan
    nb_mean = (nb.groupby(["year", "month"])[nb_cols + ["land_km2"]]
                 .apply(lambda g: pd.Series({f"nb_{c}": wsum(g, c) for c in nb_cols}))
                 .reset_index())
    focus = panel[panel["GEOID"] == FOCUS].merge(nb_mean, on=["year", "month"], how="left")

    os.makedirs(args.out_dir, exist_ok=True)
    panel.to_csv(os.path.join(args.out_dir, "county_set_panel.csv"), index=False, float_format="%.5g")
    focus.to_csv(os.path.join(args.out_dir, f"focus_panel_{FOCUS}.csv"), index=False, float_format="%.5g")

    print(f"county set: {len(panel):,} rows, {panel['GEOID'].nunique()} counties")
    print(panel.groupby("county")[["has_damage"]].sum()
               .join(panel[panel.split == "train"].groupby("county")["has_damage"].sum().rename("train"))
               .to_string())
    miss = panel.isna().mean()
    print("missing share:", miss[miss > 0].round(4).to_dict() or "none")
    print(f"focus panel: {len(focus)} rows, neighbour columns {[f'nb_{c}' for c in nb_cols]}")


if __name__ == "__main__":
    main()
