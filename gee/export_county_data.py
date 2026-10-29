import argparse

import ee


# exports the county-level inputs for the county-month model from Google Earth
# Engine to Google Drive as CSVs. every value is a mean over the county boundary,
# so neighbouring counties no longer share one climate-division value.
# run on your own machine (needs an Earth Engine account and a Cloud project):
#   pip install earthengine-api
#   earthengine authenticate
#   python gee/export_county_data.py --project YOUR-CLOUD-PROJECT
# then download the Drive folder and put the CSVs in external_data/gee/
# (see gee/README.md). nothing here uses SHELDUS.

STATES = ['17', '18', '19', '20', '26', '27', '29', '31', '38', '39', '46', '55']
DRIVE_FOLDER = 'flood_gee'

# collections, newest name first: PRISM renamed AN81m/AN81d to ANm/ANd, and the
# script uses whichever name the catalog still serves
PRISM_MONTHLY = ['OREGONSTATE/PRISM/ANm', 'OREGONSTATE/PRISM/AN81m']
PRISM_DAILY = ['OREGONSTATE/PRISM/ANd', 'OREGONSTATE/PRISM/AN81d']
ERA5_LAND_MONTHLY = ['ECMWF/ERA5_LAND/MONTHLY_AGGR']
ERA5_BANDS = ['volumetric_soil_water_layer_1', 'snow_depth_water_equivalent',
              'snowmelt_sum', 'temperature_2m_min', 'runoff_sum']
NLCD = ['USGS/NLCD_RELEASES/2019_REL/NLCD']
MERIT_HYDRO = 'MERIT/Hydro/v1_0_1'
ELEVATION = 'USGS/SRTMGL1_003'
COUNTIES = 'TIGER/2018/Counties'

PRISM_SCALE = 4638.3  # PRISM pixel size in metres
ERA5_SCALE = 11132    # 0.1 degree
NLCD_SCALE = 30
TERRAIN_SCALE = 90


def first_available(ids, kind=ee.ImageCollection):
    # the first collection id that exists in the catalog
    for collection_id in ids:
        try:
            kind(collection_id).limit(1).size().getInfo()
            return collection_id
        except ee.EEException:
            continue
    raise SystemExit(f'none of these Earth Engine collections are available: {ids}')


def counties():
    # the 1,055 counties of the 12 states, keeping only the join key
    fc = ee.FeatureCollection(COUNTIES).filter(ee.Filter.inList('STATEFP', STATES))
    return fc.select(['GEOID', 'NAME', 'STATEFP', 'ALAND'])


def county_means(image, regions, scale, names, date_format):
    # mean of each band over each county, as plain rows (no geometry)
    stats = image.reduceRegions(collection=regions, reducer=ee.Reducer.mean(),
                                scale=scale, tileScale=4)
    date = image.date().format(date_format)

    def row(f):
        values = {'GEOID': f.get('GEOID'), 'date': date}
        for band in names:
            # a single-band image reports its mean as 'mean'
            values[band] = f.get('mean' if len(names) == 1 else band)
        return ee.Feature(None, values)

    return stats.map(row)


def export(table, name, selectors, dry_run):
    if dry_run:
        print(f'  [dry run] {name}: first row {table.first().getInfo()["properties"]}')
        return
    task = ee.batch.Export.table.toDrive(collection=table, description=name,
                                         folder=DRIVE_FOLDER, fileNamePrefix=name,
                                         fileFormat='CSV', selectors=selectors)
    task.start()
    print(f'  started {name}')


def monthly_series(collection_id, bands, scale, start, end, chunk_years, prefix, dry_run):
    # one row per county per month, exported in chunks of years
    regions = counties()
    for first in range(start, end + 1, chunk_years):
        last = min(first + chunk_years - 1, end)
        images = (ee.ImageCollection(collection_id).select(bands)
                  .filterDate(f'{first}-01-01', f'{last + 1}-01-01'))
        rows = images.map(lambda img: county_means(img, regions, scale, bands, 'YYYY-MM')).flatten()
        export(rows, f'{prefix}_{first}_{last}', ['GEOID', 'date'] + bands, dry_run)
        if dry_run:
            return


def daily_precip(collection_id, start, end, dry_run):
    # one row per county per day, one file per year (daily PRISM starts in 1981)
    regions = counties()
    for year in range(start, end + 1):
        images = (ee.ImageCollection(collection_id).select('ppt')
                  .filterDate(f'{year}-01-01', f'{year + 1}-01-01'))
        rows = images.map(lambda img: county_means(img, regions, PRISM_SCALE, ['ppt'], 'YYYY-MM-dd')).flatten()
        export(rows, f'prism_daily_{year}', ['GEOID', 'date', 'ppt'], dry_run)
        if dry_run:
            return


def land_cover(dry_run):
    # impervious, developed and wetland share for each NLCD release year
    collection_id = first_available(NLCD)
    regions = counties()
    nlcd = ee.ImageCollection(collection_id)
    years = nlcd.aggregate_array('system:index').getInfo()
    print('  NLCD images:', years)
    for index in years:
        image = nlcd.filter(ee.Filter.eq('system:index', index)).first()
        cover = image.select('landcover')
        layers = ee.Image.cat([
            image.select('impervious').rename('impervious_pct'),
            cover.gte(21).And(cover.lte(24)).rename('developed_share'),
            cover.eq(90).Or(cover.eq(95)).rename('wetland_share'),
        ]).set('system:time_start', image.get('system:time_start'))
        bands = ['impervious_pct', 'developed_share', 'wetland_share']
        rows = county_means(layers, regions, NLCD_SCALE, bands, 'YYYY')
        export(rows, f'nlcd_{index}', ['GEOID', 'date'] + bands, dry_run)
        if dry_run:
            return


def terrain(dry_run):
    # static susceptibility: height above nearest drainage (HAND) and slope
    hand = ee.Image(MERIT_HYDRO).select('hnd')
    slope = ee.Terrain.slope(ee.Image(ELEVATION).select('elevation'))
    layers = ee.Image.cat([
        hand.rename('hand_mean_m'),
        hand.lt(5).rename('hand_below_5m_share'),
        hand.lt(10).rename('hand_below_10m_share'),
        slope.rename('slope_mean_deg'),
    ])
    stats = layers.reduceRegions(collection=counties(), reducer=ee.Reducer.mean(),
                                 scale=TERRAIN_SCALE, tileScale=8)
    bands = ['hand_mean_m', 'hand_below_5m_share', 'hand_below_10m_share', 'slope_mean_deg']
    rows = stats.map(lambda f: ee.Feature(None, f.toDictionary(['GEOID', 'NAME', 'STATEFP', 'ALAND'] + bands)))
    export(rows, 'terrain_static', ['GEOID', 'NAME', 'STATEFP', 'ALAND'] + bands, dry_run)


GROUPS = ['counties', 'prism_monthly', 'prism_daily', 'era5_land', 'nlcd', 'terrain']

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, help='Google Cloud project registered for Earth Engine')
    parser.add_argument('--only', nargs='+', choices=GROUPS, default=GROUPS,
                        help='export only these groups (default: all)')
    parser.add_argument('--dry-run', action='store_true',
                        help='compute one sample row per group instead of starting exports')
    args = parser.parse_args()

    ee.Initialize(project=args.project)
    regions = counties()
    n = regions.size().getInfo()
    print(f'{n} counties in the 12 states (expected 1055)')

    if 'counties' in args.only:
        print('county list')
        export(regions.map(lambda f: ee.Feature(None, f.toDictionary())), 'counties',
               ['GEOID', 'NAME', 'STATEFP', 'ALAND'], args.dry_run)

    if 'prism_monthly' in args.only:
        # 1895-2023: 1895-1959 for the rainfall normal, 1951-1999 for C, 2000-2023 for W
        collection_id = first_available(PRISM_MONTHLY)
        print(f'PRISM monthly ({collection_id}), 1895-2023')
        monthly_series(collection_id, ['ppt'], PRISM_SCALE, 1895, 2023, 20, 'prism_monthly', args.dry_run)

    if 'prism_daily' in args.only:
        # 1981-1999 sets each county's wet-day thresholds; 2000-2023 is the study period
        collection_id = first_available(PRISM_DAILY)
        print(f'PRISM daily ({collection_id}), 1981-2023, one file per year')
        daily_precip(collection_id, 1981, 2023, args.dry_run)

    if 'era5_land' in args.only:
        # soil moisture, snow and frozen ground; 1950-1999 is the baseline
        collection_id = first_available(ERA5_LAND_MONTHLY)
        available = ee.ImageCollection(collection_id).first().bandNames().getInfo()
        missing = [b for b in ERA5_BANDS if b not in available]
        if missing:
            raise SystemExit(f'ERA5-Land bands not found: {missing}; available: {available}')
        print(f'ERA5-Land monthly ({collection_id}), 1950-2023')
        monthly_series(collection_id, ERA5_BANDS, ERA5_SCALE, 1950, 2023, 25, 'era5_land_monthly', args.dry_run)

    if 'nlcd' in args.only:
        print('NLCD land cover (2001-2019 releases)')
        land_cover(args.dry_run)

    if 'terrain' in args.only:
        print('terrain (MERIT Hydro HAND, SRTM slope)')
        terrain(args.dry_run)

    if not args.dry_run:
        print(f'\nexports run on Google\'s servers; watch them at https://code.earthengine.google.com/tasks '
              f'and download the "{DRIVE_FOLDER}" folder from Google Drive when they finish')
