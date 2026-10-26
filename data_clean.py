import numpy as np
import pandas as pd


# read FIPS as a string so leading zeros (e.g. '01001') are never lost
# this is because many counties start with a leading zero, but pandas needs to read it 
data = pd.read_csv('loss_output_year_county.csv', dtype={'County_FIPS': str})
print(f'loaded {len(data)} rows, {data.shape[1]} columns')

# group everything int raw and inflation adjusted dollars 
dollar_cols = ['CropDmg', 'CropDmg(ADJ 2024)', 'CropDmgPerCapita',
               'PropertyDmg', 'PropertyDmg(ADJ 2024)', 'PropertyDmgPerCapita']
# just the duration columns 
duration_cols = ['Crop_Damage_Duration', 'Property_Damage_Duration', 'Duration_Days']


# ---------------------------------------------------------------
# 1. missing values, duplicates, invalid entries
# ---------------------------------------------------------------
print('\n--- 1. data quality checks ---')

# want to remove bad data from the file 
missing = data.isna().sum()
print('missing values per column:', missing[missing > 0].to_dict() or 'none')

print('fully duplicated rows:', data.duplicated().sum())
# one row should exist per county / year / hazard
print('duplicate county-year-hazard keys:',
      data.duplicated(['County_FIPS', 'Year', 'Hazard']).sum())

bad_fips = ~data['County_FIPS'].str.fullmatch(r'\d{5}')
print('malformed FIPS codes (not 5 digits):', bad_fips.sum())

bad_year = ~data['Year'].between(1960, 2024)
print('years outside 1960-2024:', bad_year.sum())

negatives = (data[dollar_cols + duration_cols + ['Records']] < 0).sum()
print('negative values:', negatives[negatives > 0].to_dict() or 'none')

# logical consistency between related columns
checks = {
    'crop damage with zero crop duration':  # if there was damage it lasted at least a day
        (data['CropDmg'] > 0) & (data['Crop_Damage_Duration'] == 0),
    'property damage with zero property duration':
        (data['PropertyDmg'] > 0) & (data['Property_Damage_Duration'] == 0),
    'crop/property duration longer than total duration':  # the damage duration cant be longer than the total duration
        (data['Crop_Damage_Duration'] > data['Duration_Days'])
        | (data['Property_Damage_Duration'] > data['Duration_Days']),
    'duration over 366 days': data['Duration_Days'] > 366,
    'inflation-adjusted value below raw value':  # inflation should make the dollar amount bigger 
        (data['PropertyDmg(ADJ 2024)'] < data['PropertyDmg'])
        | (data['CropDmg(ADJ 2024)'] < data['CropDmg']),
}
for name, mask in checks.items():
    print(f'{name}: {mask.sum()}')

# drop anything that failed a check (currently nothing does in original SHELDUS)
invalid = bad_fips | bad_year | (data[dollar_cols + duration_cols] < 0).any(axis=1)
for mask in checks.values():
    invalid |= mask
data = data[~invalid].drop_duplicates().reset_index(drop=True)
print(f'rows removed as invalid: {invalid.sum()}  ->  {len(data)} rows remain')


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

# the largest values are real, well-documented floods (Grand Forks 1997,
# Iowa 1993, Detroit 2014, Cedar Rapids 2008), so they are kept, not removed.
# they are flagged so they can be capped or excluded at modeling time if needed
cap = data['PropertyDmg(ADJ 2024)'].quantile(0.99)
data['is_extreme_property'] = (data['PropertyDmg(ADJ 2024)'] > cap).astype(int)
print(f'99th percentile of PropertyDmg(ADJ 2024): ${cap:,.0f}')
print('rows above it (flagged):', data['is_extreme_property'].sum())
print(data.nlargest(5, 'PropertyDmg(ADJ 2024)')
      [['StateName', 'CountyName', 'Year', 'PropertyDmg(ADJ 2024)']].to_string(index=False))


# ---------------------------------------------------------------
# 4. log transform the dollar columns
# ---------------------------------------------------------------
print('\n--- 4. log transform ---')
# lots of $0 or small thousands, so the larger events will dominate the regression
# now instead we do a log transformation to give the magnitude of the loss of 2024 adjusted 

# log10(x + 1): zero stays zero, $1M becomes 6. use 10 ** y - 1 to undo
for col in ['CropDmg(ADJ 2024)', 'CropDmgPerCapita',
            'PropertyDmg(ADJ 2024)', 'PropertyDmgPerCapita']:
    new_col = 'log_' + col.replace('(ADJ 2024)', 'ADJ')
    data[new_col] = np.log10(data[col] + 1)
    print(f'{new_col}: min {data[new_col].min():.2f}, '
          f'median {data[new_col].median():.2f}, max {data[new_col].max():.2f}')

# crop damage is 58% zeros, so store "was there any" as its own column
data['has_crop_damage'] = (data['CropDmg'] > 0).astype(int)
print('rows with crop damage:', data['has_crop_damage'].sum())


data.to_csv('loss_cleaned.csv', index=False)
print(f'\nsaved loss_cleaned.csv: {len(data)} rows, {data.shape[1]} columns')
