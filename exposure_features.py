import numpy as np
import pandas as pd


# exposure features (what is there to be damaged) from IPUMS NHGIS census tables.
# run hazard_features.py first to create model_data_hazard.csv
#   https://www.nhgis.org  (extract nhgis0001, codebooks are next to each csv)
HOUSING_FILE = 'nhgis0001_csv/nhgis0001_ts_nominal_county.csv'  # housing units, urban/rural, 1970-2020
CROPS_1919_FILE = 'nhgis0001_csv/nhgis0001_ds210_1920_county.csv'  # total value of all crops, 1919
LAND_1934_FILE = 'nhgis0001_csv/nhgis0001_ds213_1935_county.csv'  # farms reporting land use, 1934
TARGET = 'log_PropertyDmgADJ'

CENSUS_YEARS = [1970, 1980, 1990, 2000, 2010, 2020]

# counties in the model that did not exist (or had another code) in an older table,
# mapped to the county they came from
#   46102 Oglala Lakota was Shannon (46113) until 2015
#   27077 Lake of the Woods was split from Beltrami (27007) in 1922
#   55078 Menominee was split mostly from Shawano (55115) in 1961
SUCCESSOR_TO_PARENT = {'46102': '46113', '27077': '27007', '55078': '55115'}


# ---------------------------------------------------------------
# 1. housing units by census year
# ---------------------------------------------------------------
# A62AA{year} = urban housing units, A62AB{year} = rural housing units
housing = pd.read_csv(HOUSING_FILE, dtype=str)
housing['County_FIPS'] = housing['STATEFP'] + housing['COUNTYFP']
housing = housing.set_index('County_FIPS')
unit_cols = [c for c in housing.columns if c.startswith('A62')]
housing = housing[unit_cols].apply(pd.to_numeric)

# Oglala Lakota only has the 2020 census under its new code
housing.loc['46102'] = housing.loc['46102'].fillna(housing.loc['46113'])

census = []
for year in CENSUS_YEARS:
    c = pd.DataFrame({'urban': housing[f'A62AA{year}'], 'rural': housing[f'A62AB{year}']})
    c['census_year'] = year
    census.append(c.reset_index())
census = pd.concat(census).dropna(subset=['urban', 'rural'])
census = census.sort_values(['County_FIPS', 'census_year']).reset_index(drop=True)

total = census['urban'] + census['rural']
census['log_housing_units'] = np.log1p(total)
census['log_rural_units'] = np.log1p(census['rural'])
census['urban_share'] = census['urban'] / total.replace(0, np.nan)
# growth over the previous ten years: new building in places that flood
census['housing_growth'] = total.groupby(census['County_FIPS']).pct_change()
print(f'loaded {len(census)} county-census years, {census["County_FIPS"].nunique()} counties')


# ---------------------------------------------------------------
# 2. one-time farm features (1919 crops, 1934 land use)
# ---------------------------------------------------------------
def read_old_county_table(path):
    # older tables use NHGIS codes: FIPS with a trailing digit (Alabama = 010,
    # Autauga = 0010). a trailing 5 marks a county that no longer exists
    df = pd.read_csv(path, dtype=str)
    df = df[df['COUNTYA'].str.endswith('0')]
    df['County_FIPS'] = df['STATEA'].str[:2] + df['COUNTYA'].str[:3]
    return df.set_index('County_FIPS')


crops = read_old_county_table(CROPS_1919_FILE)
land = read_old_county_table(LAND_1934_FILE)
farm = pd.DataFrame(index=crops.index.union(land.index))
farm['log_crop_value_1919'] = np.log1p(pd.to_numeric(crops['AB4R001']))
# 1934 was a Dust Bowl drought year: the share of farms that lost a crop
# says how fragile a county's farming is
farm['crop_failure_rate_1934'] = (pd.to_numeric(land['ACIG002'])
                                  / pd.to_numeric(land['ACIG001']))
for child, parent in SUCCESSOR_TO_PARENT.items():
    farm.loc[child] = farm.reindex([child]).iloc[0].fillna(farm.loc[parent])


# ---------------------------------------------------------------
# 3. attach the features to each county-year
# ---------------------------------------------------------------
# each year uses the most recent census at or before it, so no later census
# leaks in. 1960-69 has no earlier census, so it falls back to the first one
model = pd.read_csv('model_data_DU.csv', dtype={'County_FIPS': str})
# every county-year, flooded or not, so the full panel (build_panel.py) can reuse it
base = pd.MultiIndex.from_product([model['County_FIPS'].unique(), range(1960, 2025)],
                                  names=['County_FIPS', 'Year']).to_frame(index=False)
base = base.sort_values('Year')
right = census.sort_values('census_year')
past = pd.merge_asof(base, right, left_on='Year', right_on='census_year',
                     by='County_FIPS', direction='backward')
future = pd.merge_asof(base, right, left_on='Year', right_on='census_year',
                       by='County_FIPS', direction='forward')
exposure = past.set_index(['County_FIPS', 'Year']).combine_first(
    future.set_index(['County_FIPS', 'Year']))

housing_cols = ['log_housing_units', 'log_rural_units', 'urban_share', 'housing_growth']
farm_cols = list(farm.columns)
exposure = exposure[housing_cols].reset_index()
exposure = exposure.merge(farm, left_on='County_FIPS', right_index=True, how='left')
exposure_cols = housing_cols + farm_cols
exposure.to_csv('exposure_by_county_year.csv', index=False)

model = model.merge(exposure, on=['County_FIPS', 'Year'], how='left')
print('rows without housing data:', model['log_housing_units'].isna().sum())
print('rows without farm data:', model[farm_cols].isna().any(axis=1).sum())
model.to_csv('model_data_exposure.csv', index=False)
print(f'saved model_data_exposure.csv: {len(model)} rows')

combined = pd.read_csv('model_data_hazard.csv', dtype={'County_FIPS': str, 'division': str})
combined = combined.merge(exposure, on=['County_FIPS', 'Year'], how='left')
combined.to_csv('model_data_combined.csv', index=False)
print(f'saved model_data_combined.csv: {len(combined)} rows')


# ---------------------------------------------------------------
# 4. how strongly does each exposure feature relate to the target?
# ---------------------------------------------------------------
print(f'\nspearman correlation with {TARGET}:')
corr = model[exposure_cols].corrwith(model[TARGET], method='spearman')
print(corr.sort_values(key=abs, ascending=False).round(3).to_string())


# ---------------------------------------------------------------
# 5. does exposure improve the prediction?
# ---------------------------------------------------------------
# same test as hazard_features.py: train on 1960-2014, test on 2015-2024
train = combined[combined['Year'] <= 2014]
test = combined[combined['Year'] > 2014]
y = test[TARGET]


def mae(pred):
    return np.abs(y - pred).mean()


def fit_predict(features):
    # least absolute deviations, since the score is MAE: start from a
    # least-squares fit, then reweight rows to shrink the influence of outliers
    def design(df):
        X = df[features].fillna(train[features].median())
        X = pd.concat([X, pd.get_dummies(df['State'], dtype=float)], axis=1)
        X['const'] = 1.0
        return X

    X_train = design(train)
    X_test = design(test)[X_train.columns]
    weights = np.ones(len(X_train))
    for _ in range(50):
        w = np.sqrt(weights)[:, None]
        beta, *_ = np.linalg.lstsq(X_train.values * w, train[TARGET].values * w[:, 0], rcond=None)
        residual = np.abs(train[TARGET].values - X_train.values @ beta)
        weights = 1 / np.maximum(residual, 1e-3)
    return X_test.values @ beta


history_cols = ['Year', 'log_population', 'prior_flood_years', 'prior_median_log_dmg',
                'prior_max_log_dmg', 'last_log_dmg', 'years_since_last_flood',
                'prior_crop_share', 'prior_mean_records', 'has_history']
anomaly_cols = [c for c in combined.columns if c.endswith('_anom')]

print(f'\ntest years 2015-2024 ({len(test)} rows), MAE on the log scale:')
print(f'  overall median                  {mae(train[TARGET].median()):.3f}')
print(f'  history + state                 {mae(fit_predict(history_cols)):.3f}')
print(f'  exposure + state                {mae(fit_predict(exposure_cols)):.3f}')
print(f'  history + exposure + state      {mae(fit_predict(history_cols + exposure_cols)):.3f}')
print(f'  history + rainfall + state      {mae(fit_predict(history_cols + anomaly_cols)):.3f}')
print(f'  history + rainfall + exposure   {mae(fit_predict(history_cols + anomaly_cols + exposure_cols)):.3f}')
