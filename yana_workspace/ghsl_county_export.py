"""
GHSL built-up surface and population for Washington County, Ohio and its four Ohio neighbours.

This is the Earth Engine exposure input (X) that replaces log_housing_units (IPUMS NHGIS is
not in Earth Engine). It is the same data as the "Built-up surface" and "Population (GHSL)"
layers in gee_exposure_app.js, summed per county.

  JRC/GHSL/P2023A/GHS_BUILT_S  band built_surface     m2 of built-up surface per 100 m cell
  JRC/GHSL/P2023A/GHS_POP      band population_count  people per 100 m cell
GHSL epochs are every 5 years; 2005-2020 cover the model years 2010-2023 with a one-year lag
(build_county_panel.py interpolates between epochs).

ONE export task for all epochs and all 5 counties (a few hundred thousand 100 m cells, so the
compute is small).

Example:
    python yana_workspace/ghsl_county_export.py --project flood-513221

Output: ghsl_39167.csv in Drive folder gee_ghsl_39167, columns GEOID, epoch, built_km2, population.
Download it to data/gee_ghsl39167/.
"""

import argparse
import os
import sys

import ee

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import prism_export as pe  # noqa: E402

FOCUS = "39167"
GEOIDS = ["39167", "39009", "39111", "39115", "39121"]
BUILT_ID = "JRC/GHSL/P2023A/GHS_BUILT_S"
POP_ID = "JRC/GHSL/P2023A/GHS_POP"
EPOCHS = [2005, 2010, 2015, 2020]
SCALE = 100


def epoch_image(collection_id, band, epoch):
    return (ee.ImageCollection(collection_id)
            .filter(ee.Filter.calendarRange(epoch, epoch, "year")).first().select(band))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", required=True, help="Google Cloud project registered for Earth Engine")
    ap.add_argument("--folder", default=f"gee_ghsl_{FOCUS}", help="Google Drive folder")
    args = ap.parse_args()

    ee.Initialize(project=args.project)
    counties = (ee.FeatureCollection(pe.COUNTIES_ID)
                .filter(ee.Filter.inList("GEOID", GEOIDS)).select(["GEOID"]))

    tables = []
    for epoch in EPOCHS:
        img = (epoch_image(BUILT_ID, "built_surface", epoch).divide(1e6).rename("built_km2")
               .addBands(epoch_image(POP_ID, "population_count", epoch).rename("population")))
        red = img.reduceRegions(collection=counties, reducer=ee.Reducer.sum(), scale=SCALE, tileScale=4)
        tables.append(pe.strip(red, ["GEOID", "built_km2", "population"], {"epoch": epoch}))

    print(f"GHSL epochs {EPOCHS}, {len(GEOIDS)} counties, scale {SCALE} m")
    pe.start_export(ee.FeatureCollection(tables).flatten(), f"ghsl_{FOCUS}", args.folder,
                    ["GEOID", "epoch", "built_km2", "population"])


if __name__ == "__main__":
    main()
