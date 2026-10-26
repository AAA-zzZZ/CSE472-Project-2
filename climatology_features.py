import numpy as np
import pandas as pd


# climatology features (c): how often floods hit a county in the long run.
# built from SHELDUS records BEFORE the 2000-2023 study period, so they are fixed
# county traits that cannot leak test-year information or drift over time
# (unlike the running history features, which grow as records pile up).
# run exposure_features.py first to create model_data_combined.csv
LOSS_FILE = 'loss_output_year_county.csv'
TARGET = 'log_PropertyDmgADJ'

# FEMA National Risk Index (March 2023 release), county table, used as an
# independent cross-check. FEMA's own site now redirects, so this is the copy
# archived on Harvard Dataverse: https://doi.org/10.7910/DVN/JSQ8KZ
#   RFLD_AFREQ    riverine flood events per year, counted 1996-2019 (overlaps the
#                 study period, so it is only a cross-check, not a main feature)
#   RFLD_EXP_AREA area exposed to riverine flooding (sq mi), from flood maps
# the loss columns (RFLD_HLR*, RFLD_EAL*, RFLD_RISK*) are built from SHELDUS,
# the source of the target, so they are never used
NRI_FILE = 'external_data/fema_nri/NRI_Table_Counties.csv'

CLIM_START, CLIM_END = 1960, 1999
CLIM_YEARS = CLIM_END - CLIM_START + 1

# a "big" flood year: at least $1M of property damage in 2024 dollars
BIG_FLOOD_DOLLARS = 1_000_000

# old county codes whose history belongs to a current county
#   46113 Shannon was renamed Oglala Lakota (46102) in 2015
#   46131 Washabaugh was merged into Jackson (46071) in 1983
OLD_TO_CURRENT = {'46113': '46102', '46131': '46071'}


# ---------------------------------------------------------------
# 1. flood record before the study period
# ---------------------------------------------------------------
loss = pd.read_csv(LOSS_FILE, dtype={'County_FIPS': str})
past = loss[loss['Year'].between(CLIM_START, CLIM_END)].copy()
past['County_FIPS'] = past['County_FIPS'].replace(OLD_TO_CURRENT)

# merge the old and current codes into one row per county-year
past = past.groupby(['County_FIPS', 'Year'], as_index=False).agg(
    records=('Records', 'sum'), damage=('PropertyDmg(ADJ 2024)', 'sum'))

clim = past.groupby('County_FIPS').agg(
    flood_years=('Year', 'size'),
    records=('records', 'sum'),
    big_flood_years=('damage', lambda d: (d >= BIG_FLOOD_DOLLARS).sum()))

# events per year, the slides' "annualized frequency"
clim['c_flood_freq'] = clim['flood_years'] / CLIM_YEARS
clim['c_records_per_year'] = clim['records'] / CLIM_YEARS
clim['c_big_flood_freq'] = clim['big_flood_years'] / CLIM_YEARS
clim_cols = ['c_flood_freq', 'c_records_per_year', 'c_big_flood_freq']

# the old codes are still separate counties in the model data, so give them
# the same climatology as the county they became
for old, current in OLD_TO_CURRENT.items():
    clim.loc[old] = clim.loc[current]


# ---------------------------------------------------------------
# 2. National Risk Index cross-check
# ---------------------------------------------------------------
nri = pd.read_csv(NRI_FILE, encoding='utf-8-sig', dtype={'STCOFIPS': str},
                  usecols=['STCOFIPS', 'AREA', 'RFLD_AFREQ', 'RFLD_EXP_AREA'])
nri = nri.set_index('STCOFIPS')
nri['nri_flood_freq'] = nri['RFLD_AFREQ']
nri['nri_floodplain_share'] = (nri['RFLD_EXP_AREA'] / nri['AREA']).clip(upper=1.0)
nri_cols = ['nri_flood_freq', 'nri_floodplain_share']

# NRI only has the current codes, so the old codes borrow their successor's values
for old, current in OLD_TO_CURRENT.items():
    nri.loc[old] = nri.loc[current]


# ---------------------------------------------------------------
# 3. join to the model data
# ---------------------------------------------------------------
model = pd.read_csv('model_data_combined.csv', dtype={'County_FIPS': str})
model = model.merge(clim[clim_cols], left_on='County_FIPS', right_index=True, how='left')
model = model.merge(nri[nri_cols], left_on='County_FIPS', right_index=True, how='left')

# a county with no flood in 1960-1999 really had zero floods on record
no_history = model.loc[model[clim_cols[0]].isna(), 'County_FIPS'].unique()
print(f'counties with no flood in {CLIM_START}-{CLIM_END}: {len(no_history)} {list(no_history)}')
model[clim_cols] = model[clim_cols].fillna(0.0)
print('rows missing NRI values:', model[nri_cols].isna().any(axis=1).sum())

model.to_csv('model_data_climatology.csv', index=False)
print(f'saved model_data_climatology.csv ({len(model)} rows, {model.shape[1]} columns)')


# ---------------------------------------------------------------
# 4. what the features look like
# ---------------------------------------------------------------
clim_cols = clim_cols + nri_cols
study = model[model['Year'].between(2000, 2023)]
per_county = study.groupby('County_FIPS')[clim_cols + [TARGET, 'max_month_precip_anom']].mean()

print(f'\nclimatology features, study years 2000-2023 ({len(study)} rows):')
summary = pd.DataFrame({
    'median': study[clim_cols].median(),
    'max': study[clim_cols].max(),
    'spearman w/ target (per row)': study[clim_cols].corrwith(study[TARGET], method='spearman'),
    'spearman w/ target (per county)': per_county[clim_cols].corrwith(per_county[TARGET], method='spearman'),
    # the C -> W arrow in the causal graph: do frequently flooded counties also
    # get heavier hazards?
    'spearman w/ wettest-month anom': study[clim_cols].corrwith(study['max_month_precip_anom'],
                                                                method='spearman'),
})
print(summary.round(3).to_string())

print('\ncorrelation between climatology features (spearman):')
print(study[clim_cols].corr(method='spearman').round(2).to_string())
