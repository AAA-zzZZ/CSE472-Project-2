"""
GHSL built-up surface by county for the 12 Midwest states, one export task per 5-year image.

Output: ghsl_county_<year>.csv, columns GEOID, year, built_m2 (total built-up area in the
county, m2), in Drive folder gee_ghsl. GHSL comes in 5-year steps, so values for the years
between images are interpolated when the panel is built.

Example:
    python yana_workspace/ghsl_export.py --project flood-513221 --start 1995 --end 2025
"""

import argparse
import os
import sys

import ee

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import prism_export as pe  # noqa: E402

GHSL_ID = "JRC/GHSL/P2023A/GHS_BUILT_S"
BAND = "built_surface"          # m2 of built-up surface in each 100 m cell
SCALE = 100


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True, help="Google Cloud project registered for Earth Engine")
    ap.add_argument("--start", type=int, default=1995, help="first image year (a multiple of 5)")
    ap.add_argument("--end", type=int, default=2025, help="last image year, inclusive")
    ap.add_argument("--folder", default="gee_ghsl", help="Google Drive folder")
    args = ap.parse_args()
    if args.start % 5 or args.end % 5:
        ap.error("GHSL images are 5 years apart: use years such as 1995, 2000 or 2025")

    ee.Initialize(project=args.project)
    counties = pe.get_counties(pe.MIDWEST_STATEFP)
    for year in range(args.start, args.end + 1, 5):
        img = ee.Image(f"{GHSL_ID}/{year}").select(BAND)
        red = img.reduceRegions(collection=counties, reducer=ee.Reducer.sum().setOutputs(["built_m2"]),
                                scale=SCALE, tileScale=16)
        pe.start_export(pe.strip(red, ["GEOID", "built_m2"], {"year": year}), f"ghsl_county_{year}",
                        args.folder, ["GEOID", "year", "built_m2"])


if __name__ == "__main__":
    main()
