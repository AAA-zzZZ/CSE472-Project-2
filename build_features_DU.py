import numpy as np
import pandas as pd


# target: property loss for a county-year, using only information that is
# known BEFORE the flood. run data_clean.py first to create loss_cleaned.csv
data = pd.read_csv('loss_cleaned.csv', dtype={'County_FIPS': str})
data = data.sort_values(['County_FIPS', 'Year']).reset_index(drop=True)

TARGET = 'log_PropertyDmgADJ'

# writes model_data, but was renamed as model_data_DU, so rerunning this will have an issue if rerunning exposureand harzard

# ---------------------------------------------------------------
# 1. population (known before the flood from the census)
# ---------------------------------------------------------------
# the per-capita columns are ADJ 2024 dollars / population, so dividing
# recovers population. per-capita is stored to 5 decimals, so tiny values
# are imprecise: only trust rows where per-capita >= 0.01, then fill the
# rest by interpolating within the county
prop_pc = data['PropertyDmgPerCapita']
crop_pc = data['CropDmgPerCapita']
use_crop = crop_pc > prop_pc

# sheldus has no population column so it is interpreted instead by using damage per capita
# a higher population means that there may be more damage possible due to more property 
# should check this possible incorrect data for checking 
implied_pop = np.where(use_crop,
                       data['CropDmg(ADJ 2024)'] / crop_pc.replace(0, np.nan),
                       data['PropertyDmg(ADJ 2024)'] / prop_pc.replace(0, np.nan))
reliable = np.maximum(prop_pc, crop_pc) >= 0.01
data['population'] = pd.Series(implied_pop).where(reliable)
data['population'] = (data.groupby('County_FIPS')['population']
                      .transform(lambda s: s.interpolate(limit_direction='both')))
data['log_population'] = np.log10(data['population'])
print('rows still missing population:', data['population'].isna().sum())


# ---------------------------------------------------------------
# 2. county flood history (only years BEFORE the current one)
# ---------------------------------------------------------------
county = data.groupby('County_FIPS')

data['prior_flood_years'] = county.cumcount()  # count the amount of years that the county had 
data['has_history'] = (data['prior_flood_years'] > 0).astype(int)  # flag
data['years_since_last_flood'] = data['Year'] - county['Year'].shift(1)  # want to see if there is a gap in flood years, may play a role in how often it happens

# shift(1) moves each value down one row, so the current year never sees itself
past_damage = county[TARGET].shift(1)
data['last_log_dmg'] = past_damage
data['prior_median_log_dmg'] = (past_damage.groupby(data['County_FIPS'])  # typical damage
                                .transform(lambda s: s.expanding().median()))
data['prior_max_log_dmg'] = (past_damage.groupby(data['County_FIPS'])  # worse damage 
                             .transform(lambda s: s.expanding().max()))  

past_records = county['Records'].shift(1)
data['prior_mean_records'] = (past_records.groupby(data['County_FIPS'])  # how many floods actually get logged
                              .transform(lambda s: s.expanding().mean()))

# share of past flood years that also damaged crops (rural vs urban signal)
past_crop = county['has_crop_damage'].shift(1)
data['prior_crop_share'] = (past_crop.groupby(data['County_FIPS'])  # how often the crops actually get hit 
                            .transform(lambda s: s.expanding().mean()))


# ---------------------------------------------------------------
# 3. state history (strictly earlier years, so a flood that hit many
#    counties in the same year can't leak into its own prediction)
# ---------------------------------------------------------------
state_prior = {}
for state, rows in data.groupby('StateName'):
    for year in rows['Year'].unique():
        earlier = rows.loc[rows['Year'] < year, TARGET]  # make sure that each row doesnt have overlap 
        state_prior[(state, year)] = earlier.median() if len(earlier) else np.nan
data['state_prior_median_log_dmg'] = [state_prior[(s, y)] 
                                      for s, y in zip(data['StateName'], data['Year'])]

# a county's first recorded flood has no history: fall back to the state's
data['prior_median_log_dmg'] = data['prior_median_log_dmg'].fillna(data['state_prior_median_log_dmg'])


# ---------------------------------------------------------------
# 4. keep only the target and pre-flood features
# ---------------------------------------------------------------
id_cols = ['County_FIPS', 'CountyName', 'StateName']
feature_cols = ['Year', 'log_population',
                'prior_flood_years', 'has_history', 'years_since_last_flood',
                'last_log_dmg', 'prior_median_log_dmg', 'prior_max_log_dmg',
                'prior_mean_records', 'prior_crop_share',
                'state_prior_median_log_dmg']

model_data = data[id_cols + feature_cols + [TARGET]].copy()
model_data = model_data.rename(columns={'StateName': 'State'})
model_data.to_csv('model_data.csv', index=False)
print(f'saved model_data.csv: {len(model_data)} rows, {len(feature_cols)} numeric features + State')


# ---------------------------------------------------------------
# 5. how strongly does each feature relate to the target?
# ---------------------------------------------------------------
print(f'\nspearman correlation with {TARGET} (rows where the feature exists):')
corr = {}
for col in feature_cols:
    present = model_data[col].notna()
    corr[col] = (model_data.loc[present, col].corr(model_data.loc[present, TARGET], method='spearman'),
                 present.sum())
corr = pd.DataFrame(corr, index=['spearman', 'rows']).T.sort_values('spearman', key=abs, ascending=False)
corr['rows'] = corr['rows'].astype(int)
print(corr.round(2).to_string())

# state is categorical, so check how much the median target differs by state
by_state = model_data.groupby('State')[TARGET].median().sort_values()
print('\nmedian target by state (log10 dollars):')
print(by_state.round(2).to_string())

# redundancy between the features themselves
pairs = model_data[feature_cols].corr(method='spearman')
pairs = pairs.where(np.triu(np.ones(pairs.shape, dtype=bool), k=1)).stack()
print('\nfeature pairs with |spearman| > 0.7:')
print(pairs[pairs.abs() > 0.7].sort_values(key=abs, ascending=False).round(2).to_string())
