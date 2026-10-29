import numpy as np
import pandas as pd


# full county-year panel for 2000-2023: every county in the 12 states, every year,
# including the years with NO recorded flood loss (loss = 0). SHELDUS only lists
# county-years that had a loss, so a missing county-year means no recorded loss.
# the earlier files hold only flooded county-years, so a model trained on them can
# say how much damage a flood does but never whether there is any; ranking every
# county needs both, which is what the hurdle model (hurdle_model.py) is for.
# run hazard_features.py, exposure_features.py and climatology_features.py first
LOSS_FILE = 'loss_output_year_county.csv'
START, END = 2000, 2023

# old codes that no longer exist in the study period
#   46113 Shannon is 46102 Oglala Lakota (renamed 2015, no 46113 rows after 1998)
#   46131 Washabaugh was merged into Jackson (46071) in 1983
OLD_CODES = ['46113', '46131']


# ---------------------------------------------------------------
# 1. every county x every year
# ---------------------------------------------------------------
loss = pd.read_csv(LOSS_FILE, dtype={'County_FIPS': str})
counties = sorted(set(loss['County_FIPS']) - set(OLD_CODES))
panel = pd.MultiIndex.from_product([counties, range(START, END + 1)],
                                   names=['County_FIPS', 'Year']).to_frame(index=False)

state = loss.drop_duplicates('County_FIPS').set_index('County_FIPS')['StateName'].str.title()
panel['State'] = panel['County_FIPS'].map(state)

# the recorded loss, 0 when the county-year is missing from SHELDUS
dollars = loss.set_index(['County_FIPS', 'Year'])['PropertyDmg(ADJ 2024)']
panel['PropertyDmgADJ'] = panel.set_index(['County_FIPS', 'Year']).index.map(dollars)
panel['PropertyDmgADJ'] = panel['PropertyDmgADJ'].fillna(0.0)
panel['log_PropertyDmgADJ'] = np.log10(panel['PropertyDmgADJ'] + 1)
panel['has_damage'] = (panel['PropertyDmgADJ'] > 0).astype(int)
print(f'{len(counties)} counties x {END - START + 1} years = {len(panel)} county-years, '
      f'{panel["has_damage"].sum()} with property damage ({panel["has_damage"].mean():.1%})')


# ---------------------------------------------------------------
# 2. attach w, x and c
# ---------------------------------------------------------------
# w: rainfall by climate division, every division-year
division = (pd.read_csv('model_data_hazard.csv', dtype={'County_FIPS': str, 'division': str})
            .drop_duplicates('County_FIPS').set_index('County_FIPS')['division'])
panel['division'] = panel['County_FIPS'].map(division)
rain = pd.read_csv('hazard_by_division.csv', dtype={'division': str})
panel = panel.merge(rain, on=['division', 'Year'], how='left')

# x: census exposure, every county-year. log_population is NOT available here: it
# is backed out of SHELDUS per-capita damage, so it only exists for flooded rows
exposure = pd.read_csv('exposure_by_county_year.csv', dtype={'County_FIPS': str})
panel = panel.merge(exposure, on=['County_FIPS', 'Year'], how='left')

# c: climatology, one fixed value per county
clim_cols = ['c_flood_freq', 'c_records_per_year', 'c_big_flood_freq',
             'nri_flood_freq', 'nri_floodplain_share']
clim = (pd.read_csv('model_data_climatology.csv', dtype={'County_FIPS': str})
        .drop_duplicates('County_FIPS').set_index('County_FIPS')[clim_cols])
panel = panel.merge(clim, left_on='County_FIPS', right_index=True, how='left')

feature_cols = [c for c in panel.columns if c.endswith('_anom')] + \
               ['log_housing_units', 'urban_share', 'log_crop_value_1919'] + clim_cols
missing = panel[feature_cols].isna().sum()
print('rows missing a feature:', missing[missing > 0].to_dict() or 'none')

panel.to_csv('model_data_panel.csv', index=False)
print(f'saved model_data_panel.csv ({len(panel)} rows, {panel.shape[1]} columns)')


# ---------------------------------------------------------------
# 3. how often does damage happen?
# ---------------------------------------------------------------
print('\nshare of county-years with property damage, by year:')
print(panel.groupby('Year')['has_damage'].mean().round(3).to_string())

# c is "how often floods hit": it should separate damage years from no-damage years
print('\nspearman correlation with has_damage:')
print(panel[feature_cols].corrwith(panel['has_damage'], method='spearman')
      .sort_values(key=abs, ascending=False).round(3).to_string())
