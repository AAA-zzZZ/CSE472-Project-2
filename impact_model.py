import numpy as np
import pandas as pd


# impact model tau(w; x, c): predicts a county's flood loss from the hazard (w),
# what is exposed (x) and the county's context (c), using linear regression.
# run exposure_features.py first to create model_data_combined.csv
TARGET = 'log_PropertyDmgADJ'

# w: how bad the hazard was. same-year rainfall is observed, not forecast, so
# it stands in for a perfect hazard forecast. prior fall rain is known beforehand
HAZARD_COLS = ['annual_precip_anom', 'max_month_precip_anom',
               'spring_precip_anom', 'prior_fall_precip_anom']
PRE_EVENT_HAZARD_COLS = ['prior_fall_precip_anom']

# x: what is there to be damaged
EXPOSURE_COLS = ['log_population', 'log_housing_units', 'log_rural_units',
                 'urban_share', 'housing_growth', 'log_crop_value_1919']

# c: how the county has fared before, plus state (added as dummies below)
# State is added separately as dummies in design 
CONTEXT_COLS = ['crop_failure_rate_1934', 'prior_flood_years', 'years_since_last_flood',
                'prior_median_log_dmg', 'prior_max_log_dmg', 'prior_crop_share']


# ---------------------------------------------------------------
# 1. split by time, as in the evaluation setup
# ---------------------------------------------------------------
# learn from 2000-2016, test on 2017-2023
data = pd.read_csv('model_data_combined.csv', dtype={'County_FIPS': str})
train = data[data['Year'].between(2000, 2016)].reset_index(drop=True)
test = data[data['Year'].between(2017, 2023)].reset_index(drop=True)
print(f'train 2000-2016: {len(train)} county-years, test 2017-2023: {len(test)} county-years')


# ---------------------------------------------------------------
# 2. linear regression
# ---------------------------------------------------------------
def design(df, features):
    # fill gaps and standardize with the TRAINING data only, so coefficients are
    # comparable (change in log10 dollars per 1 std of the feature)
    X = df[features].fillna(train[features].median())
    X = (X - train[features].mean()) / train[features].std()
    # one dummy per state, dropping the first so it doesn't duplicate the constant
    states = pd.get_dummies(df['State'], dtype=float)
    states = states.reindex(columns=sorted(train['State'].unique())[1:], fill_value=0.0)
    X = pd.concat([X, states], axis=1)
    X['const'] = 1.0
    return X


def fit(X, y):
    beta, *_ = np.linalg.lstsq(X.values, y.values, rcond=None)
    return pd.Series(beta, index=X.columns)


def scores(df, pred):
    actual = df[TARGET]
    error = actual - pred
    result = {'MAE': error.abs().mean(),
              'RMSE': np.sqrt((error ** 2).mean()),
              'R2': 1 - (error ** 2).sum() / ((actual - actual.mean()) ** 2).sum()}
    # the loss forecast is used to rank counties, so also check the ranking
    # within each test year: rank correlation, and how many of the true top 10%
    # of counties land in the predicted top 10%
    rank_corr, top_hits = [], []
    for _, rows in df.assign(pred=pred).groupby('Year'):
        # a constant prediction (like the overall median) has no ranking
        if rows['pred'].nunique() > 1:
            rank_corr.append(rows['pred'].corr(rows[TARGET], method='spearman'))
        k = max(1, len(rows) // 10)
        true_top = set(rows.nlargest(k, TARGET).index)
        pred_top = set(rows.nlargest(k, 'pred').index)
        top_hits.append(len(true_top & pred_top) / k)
    result['rank corr'] = np.mean(rank_corr) if rank_corr else np.nan
    result['top 10% hit'] = np.mean(top_hits)
    return result


models = {
    'exposure (x)': EXPOSURE_COLS,
    'exposure + context (x, c)': EXPOSURE_COLS + CONTEXT_COLS,
    'pre-event only (w0, x, c)': PRE_EVENT_HAZARD_COLS + EXPOSURE_COLS + CONTEXT_COLS,
    'full tau (w, x, c)': HAZARD_COLS + EXPOSURE_COLS + CONTEXT_COLS,
}

results = {'train median': scores(test, pd.Series(train[TARGET].median(), index=test.index)),
           'county prior median': scores(test, test['prior_median_log_dmg']
                                         .fillna(train[TARGET].median()))}
for name, features in models.items():
    beta = fit(design(train, features), train[TARGET])
    results[name] = scores(test, design(test, features) @ beta)

print('\ntest 2017-2023, log10 dollars (rank scores are averaged over test years):')
print(pd.DataFrame(results).T.round(3).to_string())


# ---------------------------------------------------------------
# 3. coefficients of the full model
# ---------------------------------------------------------------
features = HAZARD_COLS + EXPOSURE_COLS + CONTEXT_COLS
X_train = design(train, features)
beta = fit(X_train, train[TARGET])
residual = train[TARGET] - X_train @ beta
# standard errors from the usual OLS formula
sigma2 = (residual ** 2).sum() / (len(X_train) - X_train.shape[1])
se = np.sqrt(np.diag(sigma2 * np.linalg.pinv(X_train.T.values @ X_train.values)))
coef = pd.DataFrame({'coef': beta, 'std err': se, 't': beta / se})

print('\nfull model coefficients (per 1 std of each feature):')
for label, cols in [('w: hazard', HAZARD_COLS), ('x: exposure', EXPOSURE_COLS),
                    ('c: context', CONTEXT_COLS)]:
    print(f'\n{label}')
    print(coef.loc[cols].round(3).to_string())


# ---------------------------------------------------------------
# 4. check the model on simulated losses with a known answer
# ---------------------------------------------------------------
# make up losses from known coefficients using the REAL feature rows, then see
# if the fit gets the coefficients back and how close the test error gets to
# the noise floor. some true coefficients are set to zero on purpose
rng = np.random.default_rng(472)
true_beta = pd.Series(0.0, index=X_train.columns)
true_beta['const'] = 4.8
true_beta['max_month_precip_anom'] = 0.3
true_beta['spring_precip_anom'] = 0.15
true_beta['log_housing_units'] = 0.5
true_beta['prior_median_log_dmg'] = 0.4
noise = residual.std()

X_test = design(test, features)
sim_train = X_train @ true_beta + rng.normal(0, noise, len(X_train))
sim_test = X_test @ true_beta + rng.normal(0, noise, len(X_test))
sim_beta = fit(X_train, sim_train)

recovered = pd.DataFrame({'true': true_beta, 'fitted': sim_beta, 'std err': se})
recovered['within 2 se'] = (recovered['true'] - recovered['fitted']).abs() <= 2 * recovered['std err']
print(f'\nsimulated check (noise std {noise:.3f}):')
print(recovered.loc[features + ['const']].round(3).to_string())
print(f'coefficients within 2 std err: {recovered["within 2 se"].sum()} / {len(recovered)}')
print(f'test MAE {np.abs(sim_test - X_test @ sim_beta).mean():.3f}  '
      f'vs best possible {np.abs(sim_test - X_test @ true_beta).mean():.3f}')
