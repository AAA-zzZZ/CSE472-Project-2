import numpy as np
import pandas as pd


# cleans the SHELDUS county-month flood losses, the outcome of the model.
# SHELDUS is used ONLY for the outcome; every input comes from other sources.
# the county-year version of this script is legacy/data_clean.py
LOSS_FILE = 'direct_loss_aggregated_output_32423.csv'
YEARLY_FILE = 'loss_output_year_county.csv'  # only used to cross-check the totals

# read FIPS as a string so leading zeros are never lost, then pad in case a
# spreadsheet tool stripped them
data = pd.read_csv(LOSS_FILE, dtype={'County_FIPS': str})
data['County_FIPS'] = data['County_FIPS'].str.zfill(5)
print(f'loaded {len(data)} county-months, {data.shape[1]} columns')

dollar_cols = ['CropDmg', 'CropDmg(ADJ 2024)', 'CropDmgPerCapita',
               'PropertyDmg', 'PropertyDmg(ADJ 2024)', 'PropertyDmgPerCapita']
duration_cols = ['Crop_Damage_Duration', 'Property_Damage_Duration', 'Duration_Days']
KEY = ['County_FIPS', 'Year', 'Month']


# ---------------------------------------------------------------
# 1. missing values, duplicates, invalid entries
# ---------------------------------------------------------------
print('\n--- 1. data quality checks ---')

missing = data.isna().sum()
print('missing values per column:', missing[missing > 0].to_dict() or 'none')

print('fully duplicated rows:', data.duplicated().sum())
# one row should exist per county / year / month / hazard
print('duplicate county-month-hazard keys:', data.duplicated(KEY + ['Hazard']).sum())

bad_fips = ~data['County_FIPS'].str.fullmatch(r'\d{5}')
print('malformed FIPS codes (not 5 digits):', bad_fips.sum())

bad_date = ~data['Year'].between(1960, 2024) | ~data['Month'].between(1, 12)
print('years outside 1960-2024 or months outside 1-12:', bad_date.sum())

negatives = (data[dollar_cols + duration_cols + ['Records']] < 0).sum()
print('negative values:', negatives[negatives > 0].to_dict() or 'none')

# logical consistency between related columns. a duration can run past the
# month's end (it belongs to an event that started that month), so there is no
# 31-day cap here
checks = {
    'crop damage with zero crop duration':
        (data['CropDmg'] > 0) & (data['Crop_Damage_Duration'] == 0),
    'property damage with zero property duration':
        (data['PropertyDmg'] > 0) & (data['Property_Damage_Duration'] == 0),
    'crop/property duration longer than total duration':
        (data['Crop_Damage_Duration'] > data['Duration_Days'])
        | (data['Property_Damage_Duration'] > data['Duration_Days']),
    'duration over 366 days': data['Duration_Days'] > 366,
    'inflation-adjusted value below raw value':
        (data['PropertyDmg(ADJ 2024)'] < data['PropertyDmg'])
        | (data['CropDmg(ADJ 2024)'] < data['CropDmg']),
}
for name, mask in checks.items():
    print(f'{name}: {mask.sum()}')

# drop anything that failed a check
invalid = bad_fips | bad_date | (data[dollar_cols + duration_cols] < 0).any(axis=1)
for mask in checks.values():
    invalid |= mask
data = data[~invalid].drop_duplicates().reset_index(drop=True)
print(f'rows removed as invalid: {invalid.sum()}  ->  {len(data)} rows remain')

# two South Dakota codes changed. merge them into today's county and add up any
# county-months that then appear twice
#   46113 Shannon is 46102 Oglala Lakota (renamed 2015)
#   46131 Washabaugh was merged into Jackson (46071) in 1983
OLD_TO_NEW = {'46113': '46102', '46131': '46071'}
print('rows with an old South Dakota code:', data['County_FIPS'].isin(OLD_TO_NEW).sum())
data['County_FIPS'] = data['County_FIPS'].replace(OLD_TO_NEW)
names = data.drop_duplicates('County_FIPS', keep='last').set_index('County_FIPS')
sums = data.groupby(KEY + ['Hazard'], as_index=False)[dollar_cols + ['Records']].sum()
longest = data.groupby(KEY + ['Hazard'], as_index=False)[duration_cols].max()
data = sums.merge(longest, on=KEY + ['Hazard'])
data['StateName'] = data['County_FIPS'].map(names['StateName'])
data['CountyName'] = data['County_FIPS'].map(names['CountyName'])
print(f'after merging old codes: {len(data)} county-months, '
      f'{data["County_FIPS"].nunique()} counties')

# the monthly rows should add up to the county-year export
yearly = pd.read_csv(YEARLY_FILE, dtype={'County_FIPS': str})
yearly['County_FIPS'] = yearly['County_FIPS'].replace(OLD_TO_NEW)
yearly = yearly.groupby(['County_FIPS', 'Year'])['PropertyDmg(ADJ 2024)'].sum()
monthly = data.groupby(['County_FIPS', 'Year'])['PropertyDmg(ADJ 2024)'].sum()
both = pd.concat([monthly.rename('monthly'), yearly.rename('yearly')], axis=1)
off = (both['monthly'] - both['yearly']).abs() > 0.01 * both['yearly'].abs() + 1
print('county-years where monthly and yearly totals disagree:',
      int(off.sum() + both.isna().any(axis=1).sum()))


# ---------------------------------------------------------------
# 2. month-long durations and category-style damage values
# ---------------------------------------------------------------
print('\n--- 2. reporting artifacts ---')

# events logged as spanning a whole month show up as 28-31 days.
# keep them, but flag them so a model can tell them apart
data['is_month_long'] = data['Duration_Days'].between(28, 31).astype(int)
print('month-long records (28-31 days):', data['is_month_long'].sum())

# older Storm Data reported damage in ranges ($5K-$50K, ...) that became
# fixed round amounts like 500, 5000, 10000, 25000, 50000.
# a value is "round" if it is 1, 2, 2.5 or 5 times a power of ten
def is_round(values):
    positive = values > 0
    magnitude = 10 ** np.floor(np.log10(values.where(positive, 1)))
    leading = (values / magnitude).round(6)
    return (positive & leading.isin([1, 2, 2.5, 5])).astype(int)

data['is_round_property'] = is_round(data['PropertyDmg'])
data['is_round_crop'] = is_round(data['CropDmg'])
print('round property damage values:', data['is_round_property'].sum(),
      f"({data['is_round_property'].sum() / (data['PropertyDmg'] > 0).sum():.0%} of nonzero)")
print('round crop damage values:', data['is_round_crop'].sum(),
      f"({data['is_round_crop'].sum() / (data['CropDmg'] > 0).sum():.0%} of nonzero)")
print('share of nonzero property values that are round, by era:')
nonzero = data[data['PropertyDmg'] > 0]
era = pd.cut(nonzero['Year'], [1959, 1995, 2024], labels=['1960-1995', '1996-2024'])
print(nonzero.groupby(era, observed=True)['is_round_property'].mean().round(2).to_string())


# ---------------------------------------------------------------
# 3. extreme outliers
# ---------------------------------------------------------------
print('\n--- 3. outliers ---')

# the largest values are real, well-documented floods, so they are kept, not
# removed. they are flagged so they can be capped or excluded at modeling time
cap = data['PropertyDmg(ADJ 2024)'].quantile(0.99)
data['is_extreme_property'] = (data['PropertyDmg(ADJ 2024)'] > cap).astype(int)
print(f'99th percentile of PropertyDmg(ADJ 2024): ${cap:,.0f}')
print('rows above it (flagged):', data['is_extreme_property'].sum())
print(data.nlargest(5, 'PropertyDmg(ADJ 2024)')
      [['StateName', 'CountyName', 'Year', 'Month', 'PropertyDmg(ADJ 2024)']].to_string(index=False))


# ---------------------------------------------------------------
# 4. log transform the dollar columns
# ---------------------------------------------------------------
print('\n--- 4. log transform ---')

# log10(x + 1): zero stays zero, $1M becomes 6. use 10 ** y - 1 to undo
for col in ['CropDmg(ADJ 2024)', 'CropDmgPerCapita',
            'PropertyDmg(ADJ 2024)', 'PropertyDmgPerCapita']:
    new_col = 'log_' + col.replace('(ADJ 2024)', 'ADJ')
    data[new_col] = np.log10(data[col] + 1)
    print(f'{new_col}: min {data[new_col].min():.2f}, '
          f'median {data[new_col].median():.2f}, max {data[new_col].max():.2f}')

data['has_property_damage'] = (data['PropertyDmg'] > 0).astype(int)
data['has_crop_damage'] = (data['CropDmg'] > 0).astype(int)
print('rows with property damage:', data['has_property_damage'].sum(),
      ' with crop damage:', data['has_crop_damage'].sum())


# ---------------------------------------------------------------
# 5. when in the year does damage happen?
# ---------------------------------------------------------------
print('\n--- 5. seasonality (property damage, 2000-2023) ---')
study = data[data['Year'].between(2000, 2023) & (data['has_property_damage'] == 1)]
season = pd.DataFrame({'share_of_damage_months': study.groupby('Month').size() / len(study),
                       'median_log_dmg': study.groupby('Month')['log_PropertyDmgADJ'].median()})
print(season.round(3).to_string())


front = ['StateName', 'CountyName', 'County_FIPS', 'Year', 'Month', 'Hazard']
data = data[front + [c for c in data.columns if c not in front]]
data = data.sort_values(KEY).reset_index(drop=True)
data.to_csv('loss_cleaned_monthly.csv', index=False)
print(f'\nsaved loss_cleaned_monthly.csv: {len(data)} rows, {data.shape[1]} columns')
