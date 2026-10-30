"""
Export every Earth Engine input for the Midwest flood-loss model as county-level CSVs.

One command per dataset. Each export is an Earth Engine batch task that writes a CSV
to a folder in your Google Drive.

  inspect   print band names and date range of each dataset (run this first)
  prism     county x day precipitation and Tmin, one CSV per year     (W)
  era5      county x day soil moisture, snowpack, snowmelt, per year  (W, antecedent/snow)
  nlcd      county x year developed, wetland, water share, impervious (X, A)
  terrain   county static slope, elevation, HAND share                (C / susceptibility)

Setup (once):
    pip install earthengine-api
    earthengine authenticate

Examples:
    python gee_export.py inspect --project MY_PROJECT
    python gee_export.py prism   --project MY_PROJECT --start 2019 --end 2019   # test year
    python gee_export.py prism   --project MY_PROJECT                           # 1981-2023
    python gee_export.py era5    --project MY_PROJECT                           # 1950-2023
    python gee_export.py nlcd    --project MY_PROJECT                           # 1999-2023
    python gee_export.py terrain --project MY_PROJECT

Check progress:   earthengine task list
"""

import argparse
import ee

# ---------------------------------------------------------------- settings

# Census Bureau Midwest region (state FIPS). Override with --states.
MIDWEST_STATEFP = ["17", "18", "19", "20", "26", "27", "29", "31", "38", "39", "46", "55"]
COUNTIES_ID = "TIGER/2018/Counties"

PRISM_ID = "OREGONSTATE/PRISM/ANd"
PRISM_BANDS = ["ppt", "tmin"]                       # mm/day, deg C

ERA5_ID = "ECMWF/ERA5_LAND/DAILY_AGGR"
ERA5_BANDS = [
    "volumetric_soil_water_layer_1",                # 0-7 cm, m3/m3
    "volumetric_soil_water_layer_2",                # 7-28 cm
    "volumetric_soil_water_layer_3",                # 28-100 cm
    "snow_depth_water_equivalent",                  # m of water
    "snowmelt_sum",                                 # m of water per day
]
ERA5_SHORT = ["sm1", "sm2", "sm3", "swe", "snowmelt"]

NLCD_LC_ID = "projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/LANDCOVER"
NLCD_IMP_ID = "projects/sat-io/open-datasets/USGS/ANNUAL_NLCD/FRACTIONAL_IMPERVIOUS_SURFACE"

DEM_ID = "USGS/3DEP/10m_collection"
MERIT_ID = "MERIT/Hydro/v1_0_1"                     # 'hnd' = height above nearest drainage (m)


# ---------------------------------------------------------------- helpers

def get_counties(states):
    fc = ee.FeatureCollection(COUNTIES_ID).filter(ee.Filter.inList("STATEFP", states))
    return fc.select(["GEOID", "ALAND", "AWATER"])


def strip(reduced, props, extra=None):
    """Drop geometry and keep only the named properties (plus constant extras)."""
    extra = extra or {}

    def f(feat):
        d = {p: feat.get(p) for p in props}
        d.update(extra)
        return ee.Feature(None, d)

    return reduced.map(f)


def start_export(table, name, folder, selectors):
    task = ee.batch.Export.table.toDrive(
        collection=table,
        description=name,
        folder=folder,
        fileNamePrefix=name,
        fileFormat="CSV",
        selectors=selectors,
    )
    task.start()
    print(f"  started {name}  (task {task.id})")


def native_scale(collection_id):
    return ee.ImageCollection(collection_id).first().projection().nominalScale().getInfo()


def daily_export(collection_id, bands, short, year, counties, scale, prefix, folder):
    """County x day means of `bands` for one calendar year."""
    start = ee.Date.fromYMD(year, 1, 1)
    days = (ee.ImageCollection(collection_id)
            .filterDate(start, start.advance(1, "year"))
            .select(bands, short))

    def per_day(img):
        date = img.date().format("YYYY-MM-dd")
        red = img.reduceRegions(collection=counties, reducer=ee.Reducer.mean(),
                                scale=scale, tileScale=4)
        return strip(red, ["GEOID"] + short, {"date": date})

    table = days.map(per_day).flatten()
    start_export(table, f"{prefix}_{year}", folder, ["GEOID", "date"] + short)


# ---------------------------------------------------------------- commands

def cmd_inspect(args, counties):
    print(f"counties: {counties.size().getInfo()} in states {','.join(args.states)}")
    for cid in [PRISM_ID, ERA5_ID, NLCD_LC_ID, NLCD_IMP_ID, DEM_ID]:
        col = ee.ImageCollection(cid)
        try:
            first, last = col.first(), col.sort("system:time_start", False).first()
            print(f"\n{cid}")
            print("  bands :", first.bandNames().getInfo())
            print("  first :", ee.Date(first.get("system:time_start")).format("YYYY-MM-dd").getInfo())
            print("  last  :", ee.Date(last.get("system:time_start")).format("YYYY-MM-dd").getInfo())
            print("  images:", col.size().getInfo(), "  scale (m):", round(native_scale(cid)))
        except Exception as e:
            print(f"\n{cid}\n  ERROR: {e}")
    try:
        print(f"\n{MERIT_ID}\n  bands :", ee.Image(MERIT_ID).bandNames().getInfo())
    except Exception as e:
        print(f"\n{MERIT_ID}\n  ERROR: {e}")


def cmd_prism(args, counties):
    scale = native_scale(PRISM_ID)
    print(f"PRISM {args.start}-{args.end}, scale {scale:.0f} m")
    for y in range(args.start, args.end + 1):
        daily_export(PRISM_ID, PRISM_BANDS, PRISM_BANDS, y, counties, scale,
                     "prism_county_daily", args.folder)


def cmd_era5(args, counties):
    scale = native_scale(ERA5_ID)
    print(f"ERA5-Land {args.start}-{args.end}, scale {scale:.0f} m")
    for y in range(args.start, args.end + 1):
        daily_export(ERA5_ID, ERA5_BANDS, ERA5_SHORT, y, counties, scale,
                     "era5_county_daily", args.folder)


def year_image(collection_id, year):
    """First band of the image for one year (filters on system:time_start)."""
    col = ee.ImageCollection(collection_id).filter(ee.Filter.calendarRange(year, year, "year"))
    return ee.Image(col.first()).select([0])


def cmd_nlcd(args, counties):
    print(f"Annual NLCD {args.start}-{args.end}, scale {args.scale} m")
    for y in range(args.start, args.end + 1):
        lc = year_image(NLCD_LC_ID, y)
        imp = year_image(NLCD_IMP_ID, y)
        # 0/1 indicator images; their county mean is the area share.
        img = ee.Image.cat([
            lc.gte(21).And(lc.lte(24)).rename("developed_share"),
            lc.eq(90).Or(lc.eq(95)).rename("wetland_share"),
            lc.eq(11).rename("water_share"),
            imp.rename("impervious_mean"),          # percent, 0-100
        ]).updateMask(lc.mask())
        bands = ["developed_share", "wetland_share", "water_share", "impervious_mean"]
        red = img.reduceRegions(collection=counties, reducer=ee.Reducer.mean(),
                                scale=args.scale, tileScale=16)
        start_export(strip(red, ["GEOID"] + bands, {"year": y}),
                     f"nlcd_county_{y}", args.folder, ["GEOID", "year"] + bands)


def cmd_terrain(args, counties):
    print(f"Terrain (static), scale {args.scale} m")
    dem_col = ee.ImageCollection(DEM_ID)
    dem = dem_col.mosaic().setDefaultProjection(dem_col.first().projection()).rename("elev")
    slope = ee.Terrain.slope(dem).rename("slope_deg")
    layers = [
        dem.rename("elev_mean"),
        slope.rename("slope_mean"),
        slope.lt(2).rename("flat_share"),           # share of land with slope < 2 degrees
    ]
    bands = ["elev_mean", "slope_mean", "flat_share"]
    if not args.no_hand:
        hnd = ee.Image(MERIT_ID).select("hnd")
        layers += [hnd.rename("hand_mean"), hnd.lt(5).rename("hand_lt5_share")]
        bands += ["hand_mean", "hand_lt5_share"]
    red = ee.Image.cat(layers).reduceRegions(collection=counties, reducer=ee.Reducer.mean(),
                                             scale=args.scale, tileScale=16)
    start_export(strip(red, ["GEOID", "ALAND", "AWATER"] + bands),
                 "terrain_county", args.folder, ["GEOID", "ALAND", "AWATER"] + bands)


# ---------------------------------------------------------------- CLI

DEFAULT_YEARS = {"prism": (1981, 2023), "era5": (1950, 2023), "nlcd": (1999, 2023)}
DEFAULT_SCALE = {"nlcd": 30, "terrain": 90}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["inspect", "prism", "era5", "nlcd", "terrain"])
    ap.add_argument("--project", required=True, help="Google Cloud project registered for Earth Engine")
    ap.add_argument("--start", type=int, help="first year (default depends on dataset)")
    ap.add_argument("--end", type=int, help="last year, inclusive")
    ap.add_argument("--folder", help="Google Drive folder (default: gee_<command>)")
    ap.add_argument("--states", default=",".join(MIDWEST_STATEFP), help="comma-separated state FIPS")
    ap.add_argument("--scale", type=float, help="reduction scale in m for nlcd/terrain")
    ap.add_argument("--no-hand", action="store_true", help="terrain: skip the MERIT HAND layer")
    args = ap.parse_args()

    args.states = args.states.split(",")
    y0, y1 = DEFAULT_YEARS.get(args.command, (None, None))
    args.start = args.start or y0
    args.end = args.end or y1
    args.scale = args.scale or DEFAULT_SCALE.get(args.command)
    args.folder = args.folder or f"gee_{args.command}"

    ee.Initialize(project=args.project)
    counties = get_counties(args.states)
    {"inspect": cmd_inspect, "prism": cmd_prism, "era5": cmd_era5,
     "nlcd": cmd_nlcd, "terrain": cmd_terrain}[args.command](args, counties)


if __name__ == "__main__":
    main()