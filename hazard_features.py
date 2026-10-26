import numpy as np
import pandas as pd


# hazard features from NOAA nClimDiv climate-division monthly precipitation.
# run build_features.py first to create model_data.csv
#   precipitation: https://www.ncei.noaa.gov/monitoring-content/data/us/climdiv/monthly/current/
#   county lookup: https://www.ncei.noaa.gov/pub/data/cirs/climdiv/county-to-climdivs.txt
PRECIP_FILE = 'external_data/noaa/climdiv-pcpndv-v1.0.0-20261006.txt'
LOOKUP_FILE = 'external_data/noaa/county-to-climdivs.txt'
TARGET = 'log_PropertyDmgADJ'

MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
          'jul', 'aug', 'sep', 'oct', 'nov', 'dec']


# ---------------------------------------------------------------
# 1. read the precipitation file
# ---------------------------------------------------------------
# each line: SSDDEEYYYY then 12 monthly totals in inches
#   SS = NOAA state code (NOT the FIPS state code), DD = division,
#   EE = element (01 = precipitation), YYYY = year. -9.99 = missing
precip = pd.read_csv(PRECIP_FILE, sep=r'\s+', header=None, names=['id'] + MONTHS,
                     dtype={'id': str})
precip['division'] = precip['id'].str[:4]
precip['Year'] = precip['id'].str[6:].astype(int)
precip[MONTHS] = precip[MONTHS].replace(-9.99, np.nan)
precip = precip.drop(columns='id').sort_values(['division', 'Year']).reset_index(drop=True)
print(f'loaded {len(precip)} division-years, {precip["division"].nunique()} divisions')


# ---------------------------------------------------------------
# 2. yearly rainfall features for each division
# ---------------------------------------------------------------
rain = precip[['division', 'Year']].copy()
rain['annual_precip'] = precip[MONTHS].sum(axis=1, min_count=12)
rain['max_month_precip'] = precip[MONTHS].max(axis=1)
rain['spring_precip'] = precip[['mar', 'apr', 'may', 'jun']].sum(axis=1)
rain['summer_precip'] = precip[['jul', 'aug', 'sep']].sum(axis=1)

# rain in the previous fall soaks the ground, so the next spring's rain
# runs off instead of soaking in. this is known before the flood year starts
fall = precip[['sep', 'oct', 'nov', 'dec']].sum(axis=1)
rain['prior_fall_precip'] = fall.groupby(precip['division']).shift(1)

# compare each year with the division's normal. the normal is taken from
# 1895-1959, before the flood data starts, so no future years leak in
baseline = rain[rain['Year'] < 1960].groupby('division')
for col in ['annual_precip', 'max_month_precip', 'spring_precip', 'prior_fall_precip']:
    mean = rain['division'].map(baseline[col].mean())
    std = rain['division'].map(baseline[col].std())
    rain[col + '_anom'] = (rain[col] - mean) / std


# ---------------------------------------------------------------
# 3. attach each county to its climate division
# ---------------------------------------------------------------
lookup = pd.read_csv(LOOKUP_FILE, sep=r'\s+', skiprows=3, dtype=str)
county_to_div = dict(zip(lookup['POSTAL_FIPS_ID'], lookup['CLIMDIV_ID']))

# two South Dakota counties changed after the lookup's codes were assigned
county_to_div['46113'] = county_to_div['46102']  # Shannon -> renamed Oglala Lakota (2015)
county_to_div['46131'] = county_to_div['46071']  # Washabaugh -> merged into Jackson (1983)

model = pd.read_csv('model_data_DU.csv', dtype={'County_FIPS': str})
model['division'] = model['County_FIPS'].map(county_to_div)
print('counties without a division:', model.loc[model['division'].isna(), 'County_FIPS'].nunique())

model = model.merge(rain, on=['division', 'Year'], how='left')
print('rows without rainfall data:', model['annual_precip'].isna().sum())
model.to_csv('model_data_hazard.csv', index=False)
print(f'saved model_data_hazard.csv: {len(model)} rows')


# ---------------------------------------------------------------
# 4. how strongly does each rainfall feature relate to the target?
# ---------------------------------------------------------------
hazard_cols = [c for c in rain.columns if c not in ('division', 'Year')]
print(f'\nspearman correlation with {TARGET}:')
corr = model[hazard_cols].corrwith(model[TARGET], method='spearman')
print(corr.sort_values(key=abs, ascending=False).round(3).to_string())


# ---------------------------------------------------------------
# 5. does rainfall improve the prediction?
# ---------------------------------------------------------------
# same test as before: train on 1960-2014, test on 2015-2024
train = model[model['Year'] <= 2014]
test = model[model['Year'] > 2014]
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
anomaly_cols = [c for c in hazard_cols if c.endswith('_anom')]

print(f'\ntest years 2015-2024 ({len(test)} rows), MAE on the log scale:')
print(f'  overall median                  {mae(train[TARGET].median()):.3f}')
print(f'  county prior median             {mae(test["prior_median_log_dmg"].fillna(train[TARGET].median())):.3f}')
print(f'  history + state                 {mae(fit_predict(history_cols)):.3f}')
print(f'  rainfall anomalies + state      {mae(fit_predict(anomaly_cols)):.3f}')
print(f'  history + rainfall + state      {mae(fit_predict(history_cols + anomaly_cols)):.3f}')
