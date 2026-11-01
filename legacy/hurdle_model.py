import numpy as np
import pandas as pd


# hurdle (two-part) impact model on the full county-year panel, zeros included:
#   part 1  P(damage > 0 | w, x, c)           logistic regression, all county-years
#   part 2  log10 damage | damage > 0, w, x, c  linear regression, damaged rows only
#   expected loss = P(damage) x E[damage | damage]
# the loss forecast is used to rank every county, so the main scores are ranking
# scores over ALL counties, not just the ones that flooded.
# run build_panel.py first to create model_data_panel.csv
TARGET = 'log_PropertyDmgADJ'

# w: same-year rainfall stands in for a perfect hazard forecast; prior fall rain
# is the one rainfall feature known before the year starts
HAZARD_COLS = ['annual_precip_anom', 'max_month_precip_anom',
               'spring_precip_anom', 'prior_fall_precip_anom']
PRE_EVENT_HAZARD_COLS = ['prior_fall_precip_anom']

# x: log_population is not available for no-damage years (it comes from SHELDUS
# per-capita damage), so housing units stand in for it (0.99 correlated)
EXPOSURE_COLS = ['log_housing_units', 'urban_share', 'log_crop_value_1919']

# c: floods per year in 1960-1999, before the study period
CLIMATOLOGY_COLS = ['c_flood_freq', 'c_big_flood_freq']
# cross-check only: NRI's frequency counts 1996-2019 events, overlapping these years
NRI_COLS = ['nri_flood_freq', 'nri_floodplain_share']


# ---------------------------------------------------------------
# 1. split by time, as in the evaluation setup
# ---------------------------------------------------------------
data = pd.read_csv('model_data_panel.csv', dtype={'County_FIPS': str})
train = data[data['Year'].between(2000, 2016)].reset_index(drop=True)
test = data[data['Year'].between(2017, 2023)].reset_index(drop=True)
train_pos = train[train['has_damage'] == 1].reset_index(drop=True)
print(f'train 2000-2016: {len(train)} county-years ({train["has_damage"].mean():.1%} with damage), '
      f'test 2017-2023: {len(test)} ({test["has_damage"].mean():.1%} with damage)')


# ---------------------------------------------------------------
# 2. the two parts
# ---------------------------------------------------------------
def design(df, features):
    # standardize with the TRAINING data only; one dummy per state, first dropped
    X = (df[features] - train[features].mean()) / train[features].std()
    states = pd.get_dummies(df['State'], dtype=float)
    states = states.reindex(columns=sorted(train['State'].unique())[1:], fill_value=0.0)
    X = pd.concat([X, states], axis=1)
    X['const'] = 1.0
    return X


def fit_logit(X, y, ridge=1e-4):
    # logistic regression by Newton's method; the tiny ridge only keeps the
    # steps stable, it does not change the fit noticeably
    beta = np.zeros(X.shape[1])
    for _ in range(25):
        p = 1 / (1 + np.exp(-(X.values @ beta)))
        hessian = X.values.T @ (X.values * (p * (1 - p))[:, None]) + ridge * np.eye(len(beta))
        beta += np.linalg.solve(hessian, X.values.T @ (y.values - p) - ridge * beta)
    return pd.Series(beta, index=X.columns)


def fit_ols(X, y):
    beta, *_ = np.linalg.lstsq(X.values, y.values, rcond=None)
    return pd.Series(beta, index=X.columns)


def hurdle(features):
    # returns P(damage), the predicted log damage given damage, and the training
    # residuals of part 2 (used to turn the two parts into one prediction)
    logit = fit_logit(design(train, features), train['has_damage'])
    amount = fit_ols(design(train_pos, features), train_pos[TARGET])
    residual = train_pos[TARGET] - design(train_pos, features) @ amount
    p = 1 / (1 + np.exp(-(design(test, features) @ logit)))
    mu = design(test, features) @ amount
    return p, mu, residual.values


def combine(p, mu, residual):
    # expected dollars = P(damage) x E[dollars | damage]; E[10^log] is not
    # 10^E[log], so scale by the average of 10^residual (smearing)
    expected = p * 10 ** mu * np.mean(10 ** residual)
    # the point prediction with the lowest absolute error is the median of the
    # mixture: 0 when damage is less likely than not, otherwise the part-2
    # quantile that leaves half the total probability above it
    q = np.clip(1 - 0.5 / p.clip(lower=1e-9), 0, 1)
    median = np.where(p > 0.5, mu + np.quantile(residual, q), 0.0)
    return expected, pd.Series(median, index=p.index)


# ---------------------------------------------------------------
# 3. scores
# ---------------------------------------------------------------
def auc(y, score):
    # chance that a random damaged county-year scores above a random undamaged one
    ranks = pd.Series(score).rank().values
    n_pos = y.sum()
    return (ranks[y.values == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * (len(y) - n_pos))


def part1_scores(p):
    y = test['has_damage']
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return {'AUC': auc(y, p) if np.ptp(p) > 0 else 0.5,
            'log loss': -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean(),
            'Brier': ((p - y) ** 2).mean()}


def ranking_scores(expected, point):
    # rank ALL counties within each test year by expected loss
    df = test.assign(expected=np.asarray(expected), point=np.asarray(point))
    rank_corr, top_hits = [], []
    for _, rows in df.groupby('Year'):
        if rows['expected'].nunique() > 1:
            rank_corr.append(rows['expected'].corr(rows['PropertyDmgADJ'], method='spearman'))
        # the worst 10% of counties that year (only those with damage can be in it)
        k = len(rows) // 10
        true_top = set(rows[rows['has_damage'] == 1].nlargest(k, 'PropertyDmgADJ').index)
        pred_top = set(rows.nlargest(k, 'expected').index)
        top_hits.append(len(true_top & pred_top) / len(true_top))
    return {'MAE (all)': (df[TARGET] - df['point']).abs().mean(),
            'rank corr': np.mean(rank_corr) if rank_corr else np.nan,
            'top 10% hit': np.mean(top_hits)}


models = {
    'exposure (x)': EXPOSURE_COLS,
    'climatology (c)': CLIMATOLOGY_COLS,
    'x + c': EXPOSURE_COLS + CLIMATOLOGY_COLS,
    'pre-event (w0, x, c)': PRE_EVENT_HAZARD_COLS + EXPOSURE_COLS + CLIMATOLOGY_COLS,
    'w + x, no c': HAZARD_COLS + EXPOSURE_COLS,
    'full tau (w, x, c)': HAZARD_COLS + EXPOSURE_COLS + CLIMATOLOGY_COLS,
    'cross-check: w, x, c_nri': HAZARD_COLS + EXPOSURE_COLS + NRI_COLS,
}

rate = train['has_damage'].mean()
constant = pd.Series(rate, index=test.index)
part1 = {'train damage rate': part1_scores(constant)}
part2 = {}
combined = {'always predict 0': ranking_scores(constant, pd.Series(0.0, index=test.index))}

# one-part baseline: a single linear regression on log10(damage + 1), zeros
# included, which is what the earlier models would do if handed the zeros
full = HAZARD_COLS + EXPOSURE_COLS + CLIMATOLOGY_COLS
one_part = design(test, full) @ fit_ols(design(train, full), train[TARGET])
combined['one-part OLS (w, x, c)'] = ranking_scores(one_part, one_part)

test_pos = test['has_damage'] == 1
for name, features in models.items():
    p, mu, residual = hurdle(features)
    part1[name] = part1_scores(p)
    part2[name] = {'MAE (damaged)': (test.loc[test_pos, TARGET] - mu[test_pos]).abs().mean()}
    combined[name] = ranking_scores(*combine(p, mu, residual))

print('\npart 1, P(damage > 0), test 2017-2023 (AUC higher, log loss and Brier lower is better):')
print(pd.DataFrame(part1).T.round(3).to_string())
print(f'\npart 2, log10 damage given damage, test county-years with damage ({test_pos.sum()}):')
print(pd.DataFrame(part2).T.round(3).to_string())
print('\nhurdle combined, ALL test county-years (rank scores averaged over test years):')
print(pd.DataFrame(combined).T.round(3).to_string())


# ---------------------------------------------------------------
# 4. coefficients of the full model, and the confounding check
# ---------------------------------------------------------------
logit = fit_logit(design(train, full), train['has_damage'])
amount = fit_ols(design(train_pos, full), train_pos[TARGET])
print('\nfull model coefficients (per 1 std of each feature):')
print(pd.DataFrame({'part 1 (log-odds of damage)': logit[full],
                    'part 2 (log10 dollars)': amount[full]}).round(3).to_string())

# w <- c -> a -> y: if c confounds the hazard, its coefficients move when c is added
logit_no_c = fit_logit(design(train, HAZARD_COLS + EXPOSURE_COLS), train['has_damage'])
print('\npart 1 hazard coefficients without vs with climatology:')
print(pd.DataFrame({'without c': logit_no_c[HAZARD_COLS], 'with c': logit[HAZARD_COLS]})
      .round(3).to_string())


# ---------------------------------------------------------------
# 5. check the logistic fit on simulated outcomes with a known answer
# ---------------------------------------------------------------
# draw damage / no damage from known log-odds on the REAL feature rows, refit, and
# see whether the coefficients come back. some are set to zero on purpose
rng = np.random.default_rng(472)
X_train = design(train, full)
true_beta = pd.Series(0.0, index=X_train.columns)
true_beta['const'] = -1.2
true_beta['annual_precip_anom'] = 0.5
true_beta['log_housing_units'] = 0.3
true_beta['c_flood_freq'] = 0.4
sim_y = pd.Series(rng.random(len(X_train)) < 1 / (1 + np.exp(-(X_train @ true_beta))), dtype=int)
sim_beta = fit_logit(X_train, sim_y)
p_sim = 1 / (1 + np.exp(-(X_train @ sim_beta)))
se = np.sqrt(np.diag(np.linalg.inv(X_train.values.T @ (X_train.values * (p_sim * (1 - p_sim)).values[:, None]))))
recovered = pd.DataFrame({'true': true_beta, 'fitted': sim_beta, 'std err': se})
recovered['within 2 se'] = (recovered['true'] - recovered['fitted']).abs() <= 2 * recovered['std err']
print('\nsimulated check, part 1:')
print(recovered.loc[full + ['const']].round(3).to_string())
print(f'coefficients within 2 std err: {recovered["within 2 se"].sum()} / {len(recovered)}')
