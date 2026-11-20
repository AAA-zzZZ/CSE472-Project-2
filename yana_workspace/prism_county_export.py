"""
PRISM daily rain and Tmin for Washington County, Ohio and its four Ohio neighbours.

PRISM is the only new Earth Engine pull for the county study: ERA5-Land, NLCD and
terrain are reused from the Midwest exports already in data/gee_era5, data/gee_nlcd
and data/gee_terrain. To save Earth Engine quota, each pull is ONE export task (not one
per year) and covers at most 10 years.

County set (touching counties of 39167, found from data/counties_midwest.geojson):
  39167 Washington (focus), 39009 Athens, 39111 Monroe, 39115 Morgan, 39121 Noble
The West Virginia neighbours across the Ohio River are left out: SHELDUS has no
outcome for them and the existing ERA5/NLCD/terrain files do not cover them.

Example:
    python yana_workspace/prism_county_export.py --project flood-513221 --start 1981 --end 1990

Output: one CSV per pull, prism_39167_<start>_<end>.csv, columns GEOID, date, ppt, tmin
(the format w_indices.py reads), in Drive folder gee_prism_39167.
"""

import argparse
import os
import sys

import ee

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import prism_export as pe  # noqa: E402

FOCUS = "39167"
GEOIDS = ["39167", "39009", "39111", "39115", "39121"]
MAX_YEARS = 10


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True, help="Google Cloud project registered for Earth Engine")
    ap.add_argument("--start", type=int, required=True, help="first year")
    ap.add_argument("--end", type=int, required=True, help="last year, inclusive")
    ap.add_argument("--folder", default=f"gee_prism_{FOCUS}", help="Google Drive folder")
    args = ap.parse_args()
    if args.end - args.start + 1 > MAX_YEARS:
        ap.error(f"at most {MAX_YEARS} years per pull; split {args.start}-{args.end} into chunks")

    ee.Initialize(project=args.project)
    counties = (ee.FeatureCollection(pe.COUNTIES_ID)
                .filter(ee.Filter.inList("GEOID", GEOIDS)).select(["GEOID"]))
    scale = pe.native_scale(pe.PRISM_ID)
    days = (ee.ImageCollection(pe.PRISM_ID)
            .filterDate(ee.Date.fromYMD(args.start, 1, 1), ee.Date.fromYMD(args.end + 1, 1, 1))
            .select(pe.PRISM_BANDS))

    def per_day(img):
        red = img.reduceRegions(collection=counties, reducer=ee.Reducer.mean(), scale=scale, tileScale=4)
        return pe.strip(red, ["GEOID"] + pe.PRISM_BANDS, {"date": img.date().format("YYYY-MM-dd")})

    print(f"PRISM {args.start}-{args.end}, {len(GEOIDS)} counties, scale {scale:.0f} m")
    pe.start_export(days.map(per_day).flatten(), f"prism_{FOCUS}_{args.start}_{args.end}",
                    args.folder, ["GEOID", "date"] + pe.PRISM_BANDS)


if __name__ == "__main__":
    main()
