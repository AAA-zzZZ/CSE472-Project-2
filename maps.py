"""
County maps of the outcome and the model inputs, to check that each variable looks sensible
before modelling (instructor feedback: maps rather than more tables).

Inputs:
  model_panel.csv                  from merge_panel.py
  data/counties_midwest.geojson    county boundaries; created on first run from the U.S. Census
                                   Bureau 2016 cartographic boundary file bundled with the
                                   plotly-geo package (pip install plotly-geo)
Output:
  maps/*.png, one per topic

Usage:
    pip install geopandas matplotlib plotly-geo
    python maps.py
"""

import os

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

STATES = ["17", "18", "19", "20", "26", "27", "29", "31", "38", "39", "46", "55"]
BOUNDARIES = "data/counties_midwest.geojson"
PANEL = "model_panel.csv"
OUT = "maps"
ALBERS = "EPSG:5070"            # equal-area projection for the contiguous US


def county_boundaries():
    """The 1,055 counties as a GeoDataFrame in an equal-area projection."""
    if not os.path.exists(BOUNDARIES):
        import _plotly_geo
        shp = os.path.join(os.path.dirname(_plotly_geo.__file__), "package_data",
                           "cb_2016_us_county_500k.shp")
        g = gpd.read_file(shp).set_crs("EPSG:4269")       # Census files are NAD83
        g = g[g["STATEFP"].isin(STATES)][["GEOID", "STATEFP", "NAME", "geometry"]]
        g["geometry"] = g.simplify(0.005)                   # ~500 m; plenty for state-wide maps
        os.makedirs(os.path.dirname(BOUNDARIES), exist_ok=True)
        g.to_file(BOUNDARIES, driver="GeoJSON")
        print(f"saved {BOUNDARIES} ({len(g)} counties)")
    g = gpd.read_file(BOUNDARIES)
    g["GEOID"] = g["GEOID"].astype(str).str.zfill(5)
    return g.to_crs(ALBERS)


def draw(ax, gdf, column, title, cmap="viridis", label="", vmin=None, vmax=None, zero_gray=False):
    data = gdf.copy()
    if zero_gray:
        # counties with no damage at all are shown in gray, not as the lowest colour
        gray = data[data[column] <= 0]
        gray.plot(ax=ax, color="#d9d9d9", linewidth=0)
        data = data[data[column] > 0]
    data.plot(column=column, ax=ax, cmap=cmap, vmin=vmin, vmax=vmax, linewidth=0,
              legend=True, legend_kwds={"label": label, "shrink": 0.6, "orientation": "horizontal",
                                        "pad": 0.02})
    STATE_LINES.plot(ax=ax, facecolor="none", edgecolor="white", linewidth=0.6)
    ax.set_title(title, fontsize=10)
    ax.set_axis_off()


def figure(panels, name, suptitle):
    """panels: list of (column, title, kwargs) drawn from COUNTY."""
    n = len(panels)
    fig, axes = plt.subplots(1, n, figsize=(6.2 * n, 5.6))
    axes = np.atleast_1d(axes)
    for ax, (column, title, kw) in zip(axes, panels):
        draw(ax, COUNTY, column, title, **kw)
    fig.suptitle(suptitle, fontsize=12)
    fig.tight_layout()
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  {path}")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    gdf = county_boundaries()
    STATE_LINES = gdf.dissolve(by="STATEFP")

    panel = pd.read_csv(PANEL, dtype={"GEOID": str})
    print(f"panel: {len(panel):,} rows; boundaries: {len(gdf)} counties")
    train = panel[panel["split"] == "train"]
    test = panel[panel["split"] == "test"]

    # one row per county with everything the maps need
    county = pd.DataFrame({
        # outcome, training and test years separately
        "loss_train": np.log10(train.groupby("GEOID")["PropertyDmgADJ"].sum() + 1),
        "loss_test": np.log10(test.groupby("GEOID")["PropertyDmgADJ"].sum() + 1),
        "damage_rate_train": train.groupby("GEOID")["has_damage"].mean() * 100,
        "damage_rate_test": test.groupby("GEOID")["has_damage"].mean() * 100,
    })
    static = panel.drop_duplicates("GEOID").set_index("GEOID")
    for col in ["c_rx5_rl10_mm", "c_wetday_p95_mm", "hand_lt5_share", "slope_mean", "flat_share"]:
        county[col] = static[col]
    for col in ["impervious_mean", "developed_share", "wetland_share", "log_housing_units"]:
        county[col] = panel[panel["year"] == 2016].groupby("GEOID")[col].first()
    county["housing_units"] = np.exp(county["log_housing_units"]) - 1
    county["log10_housing_units"] = np.log10(county["housing_units"] + 1)
    # two big flood months: June 2008 (Iowa) and March 2019 (Missouri basin)
    for y, m, tag in [(2008, 6, "2008_06"), (2019, 3, "2019_03")]:
        month = panel[(panel["year"] == y) & (panel["month"] == m)].set_index("GEOID")
        county[f"rx5_ratio_{tag}"] = month["rx5_rl_ratio"]
        county[f"sm_pct_{tag}"] = month["sm_root_pct"] * 100
        county[f"loss_{tag}"] = np.log10(month["PropertyDmgADJ"] + 1)
        county[f"swe_prevmonth_{tag}"] = month["swe_mm"]
    COUNTY = gdf.merge(county, left_on="GEOID", right_index=True, how="left")

    loss_scale = dict(cmap="magma_r", label=r"log10 of total loss, 2024 \$ (6 = \$1M)", vmin=4, vmax=9,
                      zero_gray=True)
    rate_scale = dict(cmap="Blues", label="% of months with property damage", vmin=0, vmax=12)

    print("writing maps:")
    figure([("loss_train", "Total property loss, 2000-2016 (train)", loss_scale),
            ("loss_test", "Total property loss, 2017-2023 (test)", loss_scale)],
           "1_outcome_loss.png", "Outcome: SHELDUS flood property loss (gray = none recorded)")
    figure([("damage_rate_train", "Months with damage, 2000-2016", rate_scale),
            ("damage_rate_test", "Months with damage, 2017-2023", rate_scale)],
           "2_outcome_damage_rate.png", "Outcome: how often a county has a damage month")
    figure([("c_rx5_rl10_mm", "10-year 5-day rainfall, 1951-1999",
             dict(cmap="YlGnBu", label="mm")),
            ("c_wetday_p95_mm", "95th percentile wet-day rain, 1951-1999",
             dict(cmap="YlGnBu", label="mm"))],
           "3_climate_C.png", "Flood climate (C): rainfall climate before the study period (NOAA nClimGrid)")
    figure([("rx5_ratio_2008_06", "June 2008: wettest 5 days / 10-year level",
             dict(cmap="YlGnBu", label="ratio (1 = 10-year event)", vmin=0, vmax=1.6)),
            ("sm_pct_2008_06", "June 2008: soil moisture on day 1",
             dict(cmap="BrBG", label="percentile vs 1950-1999", vmin=0, vmax=100)),
            ("loss_2008_06", "June 2008: property loss",
             dict(cmap="magma_r", label=r"log10 loss, 2024 \$", vmin=4, vmax=9, zero_gray=True))],
           "4_hazard_W_june2008.png", "Hazard (W) and loss in one flood month: June 2008")
    figure([("rx5_ratio_2019_03", "March 2019: wettest 5 days / 10-year level",
             dict(cmap="YlGnBu", label="ratio (1 = 10-year event)", vmin=0, vmax=1.6)),
            ("swe_prevmonth_2019_03", "March 2019: snowpack on day 1",
             dict(cmap="PuBu", label="snow water equivalent, mm", vmin=0, vmax=150)),
            ("loss_2019_03", "March 2019: property loss",
             dict(cmap="magma_r", label=r"log10 loss, 2024 \$", vmin=4, vmax=9, zero_gray=True))],
           "5_hazard_W_march2019.png", "Hazard (W) and loss in one flood month: March 2019")
    figure([("log10_housing_units", "Housing units (census)",
             dict(cmap="OrRd", label="log10 housing units")),
            ("impervious_mean", "Impervious surface, 2016 (NLCD)",
             dict(cmap="OrRd", label="% of county area", vmin=0, vmax=10)),
            ("wetland_share", "Wetland share, 2016 (NLCD)",
             dict(cmap="Greens", label="share of county area", vmin=0, vmax=0.3))],
           "6_exposure_X_adaptation_A.png", "Exposure (X) and wetlands (A)")
    figure([("hand_lt5_share", "Land within 5 m of drainage height",
             dict(cmap="PuBu", label="share of county area", vmin=0, vmax=1)),
            ("flat_share", "Flat land (slope under 2 degrees)",
             dict(cmap="YlOrBr", label="share of county area", vmin=0, vmax=1)),
            ("slope_mean", "Mean slope",
             dict(cmap="YlOrBr", label="degrees"))],
           "7_terrain_susceptibility.png", "Susceptibility: terrain (MERIT Hydro HAND, USGS 3DEP)")
