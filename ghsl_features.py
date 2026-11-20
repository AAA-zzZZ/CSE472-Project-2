import glob

import numpy as np
import pandas as pd


# built-up surface (x): total built-up area in each county from GHSL
# (JRC/GHSL/P2023A/GHS_BUILT_S, 100 m, images every 5 years 1995-2025), exported by
# yana_workspace/ghsl_export.py. the 5-year images are interpolated linearly to every
# year; merge_panel.py joins year t - 1 to model year t.
# output: data/clean/ghsl_county_year.csv with GEOID, year, built_m2
GHSL_DIR = 'data/gee_ghsl'
OUT_FILE = 'data/clean/ghsl_county_year.csv'
START, END = 1999, 2023


ghsl = pd.concat([pd.read_csv(f, dtype={'GEOID': str}) for f in sorted(glob.glob(f'{GHSL_DIR}/ghsl_county_*.csv'))])
ghsl['GEOID'] = ghsl['GEOID'].str.zfill(5)
images = sorted(ghsl['year'].unique())
print(f'loaded {len(images)} GHSL images {images}, {ghsl["GEOID"].nunique()} counties')
if ghsl.duplicated(['GEOID', 'year']).any():
    raise SystemExit('duplicate GEOID-year rows in the GHSL files')

wide = ghsl.pivot(index='GEOID', columns='year', values='built_m2')
if wide.isna().any().any():
    raise SystemExit(f'{wide.isna().any(axis=1).sum()} counties are missing a GHSL image')

years = np.arange(START, END + 1)
out = pd.DataFrame([np.interp(years, images, row) for row in wide.to_numpy()],
                   index=wide.index, columns=years)
out = out.stack().rename('built_m2').reset_index().rename(columns={'level_1': 'year'})
print(f'zero built-up area: {(out["built_m2"] <= 0).sum()} county-years')

out.to_csv(OUT_FILE, index=False, float_format='%.6g')
print(f'saved {OUT_FILE}: {out["GEOID"].nunique()} counties x {len(years)} years = {len(out)} rows')
