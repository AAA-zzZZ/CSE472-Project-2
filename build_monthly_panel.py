import numpy as np
import pandas as pd


# full county-month panel for 2000-2023: every county in the 12 states, every
# month, including the months with NO recorded flood loss (loss = 0). SHELDUS only
# lists county-months that had a loss, so a missing county-month means no
# recorded loss. this is the table the hurdle model is trained and tested on.
# run data_clean.py first to create loss_cleaned_monthly.csv
# inputs attached so far: x (census housing). w (county rainfall), c (non-SHELDUS
# flood climate) and a (adaptation) are added as their scripts are rebuilt
LOSS_FILE = 'loss_cleaned_monthly.csv'
EXPOSURE_FILE = 'exposure_by_county_year.csv'  # written by exposure_features.py
START, END = 2000, 2023

# the 12 states, by state FIPS code
STATES = {'17': 'Illinois', '18': 'Indiana', '19': 'Iowa', '20': 'Kansas',
          '26': 'Michigan', '27': 'Minnesota', '29': 'Missouri', '31': 'Nebraska',
          '38': 'North Dakota', '39': 'Ohio', '46': 'South Dakota', '55': 'Wisconsin'}

# old codes that no longer exist in the study period
#   46113 Shannon is 46102 Oglala Lakota (renamed 2015)
#   46131 Washabaugh was merged into Jackson (46071) in 1983
OLD_CODES = ['46113', '46131']


# ---------------------------------------------------------------
# 1. every county x every month
# ---------------------------------------------------------------
# the county list comes from the census table, not from SHELDUS, so a county
# that never reported a flood is still in the panel
exposure = pd.read_csv(EXPOSURE_FILE, dtype={'County_FIPS': str})
counties = sorted(set(exposure['County_FIPS']) - set(OLD_CODES))
panel = pd.MultiIndex.from_product([counties, range(START, END + 1), range(1, 13)],
                                   names=['County_FIPS', 'Year', 'Month']).to_frame(index=False)
panel['State'] = panel['County_FIPS'].str[:2].map(STATES)
print(f'{len(counties)} counties x {END - START + 1} years x 12 months = {len(panel)} county-months')
print('counties per state:', panel.drop_duplicates('County_FIPS')['State'].value_counts().sort_index().to_dict())


# ---------------------------------------------------------------
# 2. the outcome: property loss, 0 when SHELDUS has no record
# ---------------------------------------------------------------
loss = pd.read_csv(LOSS_FILE, dtype={'County_FIPS': str})
loss = loss[loss['Year'].between(START, END)]
outside = set(loss['County_FIPS']) - set(counties)
print('loss rows for counties outside the panel:', int(loss['County_FIPS'].isin(outside).sum()))

dollars = loss.groupby(['County_FIPS', 'Year', 'Month'])['PropertyDmg(ADJ 2024)'].sum()
panel['PropertyDmgADJ'] = panel.set_index(['County_FIPS', 'Year', 'Month']).index.map(dollars)
panel['PropertyDmgADJ'] = panel['PropertyDmgADJ'].fillna(0.0)
panel['log_PropertyDmgADJ'] = np.log10(panel['PropertyDmgADJ'] + 1)
panel['has_damage'] = (panel['PropertyDmgADJ'] > 0).astype(int)
print(f'county-months with property damage: {panel["has_damage"].sum()} '
      f'({panel["has_damage"].mean():.1%})')
print(f'total property loss in the panel: ${panel["PropertyDmgADJ"].sum() / 1e9:.1f}B (2024 dollars); '
      f'in SHELDUS for these years: ${loss["PropertyDmg(ADJ 2024)"].sum() / 1e9:.1f}B')

# split key, as in the evaluation setup: learn from 2000-2016, test on 2017-2023
panel['split'] = np.where(panel['Year'] <= 2016, 'train', 'test')


# ---------------------------------------------------------------
# 3. attach x: census housing (most recent census at or before the year)
# ---------------------------------------------------------------
# the 1919 crop value, 1934 crop failure, rural units and housing growth are
# dropped (instructor feedback, and weak or drifting in earlier tests)
X_COLS = ['log_housing_units', 'urban_share']
panel = panel.merge(exposure[['County_FIPS', 'Year'] + X_COLS], on=['County_FIPS', 'Year'], how='left')
missing = panel[X_COLS].isna().sum()
print('rows missing an x feature:', missing[missing > 0].to_dict() or 'none')

panel.to_csv('model_data_monthly_panel.csv', index=False)
print(f'saved model_data_monthly_panel.csv ({len(panel)} rows, {panel.shape[1]} columns)')


# ---------------------------------------------------------------
# 4. how often does damage happen?
# ---------------------------------------------------------------
print('\nshare of county-months with property damage:')
by_split = panel.groupby('split')['has_damage'].agg(['mean', 'sum'])
print(by_split.round(4).to_string())

print('\nby calendar month (2000-2023):')
print(panel.groupby('Month')['has_damage'].mean().round(4).to_string())

print('\nby year:')
print(panel.groupby('Year')['has_damage'].mean().round(4).to_string())

# counties with no damage month at all in the training years: the model has to
# rank these from inputs alone (a spatial model would borrow from neighbours)
train_counts = panel[panel['split'] == 'train'].groupby('County_FIPS')['has_damage'].sum()
print(f'\ncounties with no damage month in 2000-2016: {(train_counts == 0).sum()} of {len(train_counts)}')
print('damage months per county in 2000-2016 (quantiles):',
      train_counts.quantile([0.25, 0.5, 0.75, 0.9]).to_dict())
