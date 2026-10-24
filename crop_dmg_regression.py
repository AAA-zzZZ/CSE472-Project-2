import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt



# linear regression of log10 crop damage (inflation adjusted) on event characteristics
# only county-years with nonzero crop damage are used (10473 of 17962 rows are zero)
# state/county are left out for now

data = pd.read_csv('loss_output_year_county.csv')

target = 'CropDmg(ADJ 2024)'
data = data[data[target] > 0]

# damage and counts are right-skewed, so model them on a log scale
X = pd.DataFrame({
    'log10(Records)': np.log10(data['Records']),
    'log10(Duration_Days)': np.log10(data['Duration_Days']),
    'Year': data['Year'],
})
y = np.log10(data[target]).to_numpy()

# 80/20 train/test split
rng = np.random.default_rng(42)
idx = rng.permutation(len(X))
n_train = int(0.8 * len(X))
train, test = idx[:n_train], idx[n_train:]

# ordinary least squares with an intercept column
A = np.column_stack([np.ones(len(X)), X.to_numpy()])
coef, *_ = np.linalg.lstsq(A[train], y[train], rcond=None)

# standard errors from the residual variance on the training set
resid = y[train] - A[train] @ coef
dof = len(train) - A.shape[1]
sigma2 = resid @ resid / dof
se = np.sqrt(np.diag(sigma2 * np.linalg.inv(A[train].T @ A[train])))

names = ['Intercept'] + list(X.columns)
summary = pd.DataFrame({'coef': coef, 'std_err': se, 't': coef / se}, index=names)


def r2(y_true, y_pred):
    return 1 - ((y_true - y_pred) ** 2).sum() / ((y_true - y_true.mean()) ** 2).sum()


def rmse(y_true, y_pred):
    return np.sqrt(((y_true - y_pred) ** 2).mean())


pred = A @ coef
print(f'Target: log10({target}), n={len(X)} (train={len(train)}, test={len(test)})\n')
print(summary.round(4))
print(f'\nTrain R^2 = {r2(y[train], pred[train]):.4f}   RMSE = {rmse(y[train], pred[train]):.4f}')
print(f'Test  R^2 = {r2(y[test], pred[test]):.4f}   RMSE = {rmse(y[test], pred[test]):.4f}')

# predicted vs actual and residuals on the test set
out_dir = os.path.join('regression', 'crop_dmg')
os.makedirs(out_dir, exist_ok=True)

fig, axes = plt.subplots(1, 2, figsize=(12, 5))
ax = axes[0]
ax.scatter(y[test], pred[test], s=5, alpha=0.2, color='seagreen')
lims = [y.min(), y.max()]
ax.plot(lims, lims, color='black', linestyle='--', linewidth=1)
ax.set_xlabel(f'Actual log10({target})')
ax.set_ylabel(f'Predicted log10({target})')
ax.set_title(f'Crop damage: predicted vs actual (test, R^2={r2(y[test], pred[test]):.3f})')

ax = axes[1]
ax.scatter(pred[test], y[test] - pred[test], s=5, alpha=0.2, color='seagreen')
ax.axhline(0, color='black', linestyle='--', linewidth=1)
ax.set_xlabel('Predicted')
ax.set_ylabel('Residual')
ax.set_title('Residuals vs predicted (test)')

fig.tight_layout()
fig.savefig(os.path.join(out_dir, 'fit.png'), dpi=120)
plt.close(fig)

summary.to_csv(os.path.join(out_dir, 'coefficients.csv'))
