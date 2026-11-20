import numpy as np
import pandas as pd


# census housing (x): housing units and urban share for every county and year,
# from the IPUMS NHGIS time-series table A62 (urban and rural housing units,
# 1970-2020, https://www.nhgis.org, extract nhgis0001; codebook next to the csv).
# each year uses the most recent census at or before it, so no later census leaks in.
# this is the housing part of the earlier exposure_features.py; it will be replaced
# by the census/ACS table from the data-collection guide (data/clean/)
HOUSING_FILE = 'nhgis0001_csv/nhgis0001_ts_nominal_county.csv'
STATES = ['17', '18', '19', '20', '26', '27', '29', '31', '38', '39', '46', '55']
CENSUS_YEARS = [1970, 1980, 1990, 2000, 2010, 2020]
START, END = 1999, 2023

# old codes that no longer exist in the study period
#   46113 Shannon is 46102 Oglala Lakota (renamed 2015)
#   46131 Washabaugh was merged into Jackson (46071) in 1983
OLD_CODES = ['46113', '46131']


# ---------------------------------------------------------------
# 1. housing units by census year
# ---------------------------------------------------------------
# A62AA{year} = urban housing units, A62AB{year} = rural housing units
housing = pd.read_csv(HOUSING_FILE, dtype=str)
housing = housing[housing['STATEFP'].isin(STATES)]
housing['County_FIPS'] = housing['STATEFP'] + housing['COUNTYFP']
housing = housing.set_index('County_FIPS')
unit_cols = [c for c in housing.columns if c.startswith('A62')]
housing = housing[unit_cols].apply(pd.to_numeric)

# Oglala Lakota only has the 2020 census under its new code
housing.loc['46102'] = housing.loc['46102'].fillna(housing.loc['46113'])
housing = housing.drop(index=[c for c in OLD_CODES if c in housing.index])

census = []
for year in CENSUS_YEARS:
    c = pd.DataFrame({'urban': housing[f'A62AA{year}'], 'rural': housing[f'A62AB{year}']})
    c['census_year'] = year
    census.append(c.reset_index())
census = pd.concat(census).dropna(subset=['urban', 'rural'])
census = census.sort_values(['County_FIPS', 'census_year']).reset_index(drop=True)

total = census['urban'] + census['rural']
census['log_housing_units'] = np.log1p(total)
census['urban_share'] = census['urban'] / total.replace(0, np.nan)
print(f'loaded {len(census)} county-census years, {census["County_FIPS"].nunique()} counties')


# ---------------------------------------------------------------
# 2. one row per county and year
# ---------------------------------------------------------------
base = pd.MultiIndex.from_product([sorted(housing.index), range(START, END + 1)],
                                  names=['County_FIPS', 'Year']).to_frame(index=False)
out = pd.merge_asof(base.sort_values('Year'), census.sort_values('census_year'),
                    left_on='Year', right_on='census_year', by='County_FIPS', direction='backward')
out = out[['County_FIPS', 'Year', 'log_housing_units', 'urban_share']].sort_values(['County_FIPS', 'Year'])
missing = out[['log_housing_units', 'urban_share']].isna().sum()
print('rows missing a value:', missing[missing > 0].to_dict() or 'none')

out.to_csv('housing_county_year.csv', index=False)
print(f'saved housing_county_year.csv: {out["County_FIPS"].nunique()} counties x '
      f'{END - START + 1} years = {len(out)} rows')
