"""
Which model family works best on the county x month table? Same split, scores and baseline as
hurdle_model.py, so the rows are directly comparable.

  baseline        each county's damage rate for that calendar month in the training years
  GLM hurdle      logistic + linear regression on log10 damage (hurdle_model.py's full model)
  RF hurdle       random forest classifier + random forest regressor
  LightGBM hurdle gradient-boosted classifier + gradient-boosted regressor on log10 damage
  LightGBM Tweedie one gradient-boosted model of expected dollars (compound Poisson-gamma)

The tree models get every input column (they are not hurt by overlapping inputs) plus state and
calendar month. Their number of trees is chosen by early stopping on 2000-2012 -> 2013-2016,
then they are refit on 2000-2016 and scored once on 2017-2023.

Input : model_panel.csv from merge_panel.py
Output: printed tables, results/model_comparison.csv

Usage:
    pip install lightgbm scikit-learn
    python model_comparison.py
"""

import os

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

PANEL = "model_panel.csv"
TARGET = "log_PropertyDmgADJ"
STATES = {"17": "IL", "18": "IN", "19": "IA", "20": "KS", "26": "MI", "27": "MN",
          "29": "MO", "31": "NE", "38": "ND", "39": "OH", "46": "SD", "55": "WI"}
TOP_SHARE = 0.05
N_BOOT = 200
SEED = 472

# every input in model_panel.csv; none comes from SHELDUS
INPUTS = ["p_month", "rx1", "rx3", "rx5", "n_gt_p95", "n_gt_p99", "rx5_gt_rl10", "rx5_rl_ratio",
          "frost_days", "snowmelt_mm", "rain_x_wetsoil",
          "spi1_prev", "spi2_prev", "frost_days_prev", "snowmelt_prev_mm",
          "sm_surface", "sm_root", "sm_root_pct", "sm_root_anom", "swe_mm",
          "c_wetday_p95_mm", "c_wetday_p99_mm", "c_rx5_rl2_mm", "c_rx5_rl10_mm", "c_rx5_rl25_mm",
          "log_housing_units", "urban_share", "developed_share", "impervious_mean", "water_share",
          "elev_mean", "slope_mean", "flat_share", "hand_mean", "hand_lt5_share", "land_km2", "water_km2",
          "wetland_share", "wetland_change_since_1999"]
# the GLM uses hurdle_model.py's full model: one representative per overlapping group
GLM_INPUTS = ["log_housing_units", "urban_share", "impervious_mean", "water_share", "hand_lt5_share",
              "log_land_km2", "wetland_share", "c_rx5_rl10_mm", "spi1_prev", "sm_root_pct",
              "log_swe_mm", "log_snowmelt_prev_mm", "log_p_month", "rx5_rl_ratio",
              "log_snowmelt_mm", "frost_days", "rain_x_wetsoil"]


# ---------------------------------------------------------------
# 1. data
# ---------------------------------------------------------------
data = pd.read_csv(PANEL, dtype={"GEOID": str})
# PRISM starts 2000-01-01, so January 2000 has no previous-month rain index
data = data.dropna(subset=["spi1_prev"]).reset_index(drop=True)
data["state"] = data["GEOID"].str[:2].map(STATES)
for col in ["p_month", "swe_mm", "snowmelt_mm", "snowmelt_prev_mm"]:
    data["log_" + col] = np.log1p(data[col].clip(lower=0))
data["log_land_km2"] = np.log(data["land_km2"])
data["state_code"] = data["state"].astype("category").cat.codes
TREE_INPUTS = INPUTS + ["month", "state_code"]

train = data[data["split"] == "train"].reset_index(drop=True)
test = data[data["split"] == "test"].reset_index(drop=True)
fit_part = train[train["year"] <= 2012].reset_index(drop=True)
valid_part = train[train["year"] >= 2013].reset_index(drop=True)
yt = test["has_damage"].to_numpy()
print(f"train {len(train):,} county-months ({train['has_damage'].mean():.2%} damage), "
      f"test {len(test):,} ({yt.mean():.2%})")


# ---------------------------------------------------------------
# 2. models
# ---------------------------------------------------------------
def climatology(fit_df, score_df, prior=2.0):
    rate = fit_df.groupby(["GEOID", "month"])["has_damage"].agg(["sum", "count"])
    state_rate = fit_df.groupby(["state", "month"])["has_damage"].mean().rename("state_rate")
    pos = fit_df[fit_df["has_damage"] == 1]
    sev = pos.groupby("GEOID")[TARGET].mean().rename("sev")
    df = (score_df[["GEOID", "state", "month"]]
          .join(rate, on=["GEOID", "month"]).join(state_rate, on=["state", "month"]).join(sev, on="GEOID"))
    p = ((df["sum"] + prior * df["state_rate"]) / (df["count"] + prior)).to_numpy()
    mu = df["sev"].fillna(pos[TARGET].mean()).to_numpy()
    return p, mu, p * 10 ** mu


def glm_design(df, ref):
    X = (df[GLM_INPUTS] - ref[GLM_INPUTS].mean()) / ref[GLM_INPUTS].std()
    X = pd.concat([X, pd.get_dummies(df["month"], prefix="m", dtype=float)
                   .reindex(columns=[f"m_{m}" for m in range(2, 13)], fill_value=0.0),
                   pd.get_dummies(df["state"], prefix="st", dtype=float)
                   .reindex(columns=[f"st_{s}" for s in sorted(STATES.values())[1:]], fill_value=0.0)], axis=1)
    X["const"] = 1.0
    return X


def glm_hurdle(fit_df, score_df, ridge1=100, ridge2=0.1):
    """hurdle_model.py's full model: ridge logistic + ridge linear regression on log10 damage."""
    def lam(X, r):
        return np.diag([r if not (c == "const" or c.startswith(("m_", "st_"))) else 1e-6 for c in X.columns])
    X, y = glm_design(fit_df, fit_df), fit_df["has_damage"].to_numpy()
    A, L = X.to_numpy(), lam(X, ridge1)
    b = np.zeros(A.shape[1])
    b[-1] = np.log(y.mean() / (1 - y.mean()))
    for _ in range(30):
        p = 1 / (1 + np.exp(-(A @ b)))
        step = np.linalg.solve(A.T @ (A * (p * (1 - p))[:, None]) + L, A.T @ (y - p) - L @ b)
        b += step
        if np.abs(step).max() < 1e-8:
            break
    pos = fit_df[fit_df["has_damage"] == 1]
    Ap = glm_design(pos, fit_df).to_numpy()
    b2 = np.linalg.solve(Ap.T @ Ap + lam(X, ridge2), Ap.T @ pos[TARGET].to_numpy())
    smear = np.mean(10 ** (pos[TARGET].to_numpy() - Ap @ b2))
    S = glm_design(score_df, fit_df).to_numpy()
    p, mu = 1 / (1 + np.exp(-(S @ b))), S @ b2
    return p, mu, p * 10 ** mu * smear


LGB_BASE = dict(learning_rate=0.03, num_leaves=31, min_child_samples=100, subsample=0.8, subsample_freq=1,
                colsample_bytree=0.8, reg_lambda=1.0, n_estimators=3000, random_state=SEED, verbose=-1)


def lgb_rounds(model, X_fit, y_fit, X_val, y_val, metric):
    """Number of trees chosen by early stopping on the 2013-2016 validation years."""
    model.set_params(metric=metric)
    model.fit(X_fit, y_fit, eval_set=[(X_val, y_val)], callbacks=[lgb.early_stopping(100, verbose=False)])
    return model.best_iteration_


def lgb_hurdle(rounds=None):
    """Gradient-boosted classifier for any damage + regressor on log10 damage."""
    pos_fit, pos_val = fit_part[fit_part["has_damage"] == 1], valid_part[valid_part["has_damage"] == 1]
    if rounds is None:
        r1 = lgb_rounds(lgb.LGBMClassifier(**LGB_BASE), fit_part[TREE_INPUTS], fit_part["has_damage"],
                        valid_part[TREE_INPUTS], valid_part["has_damage"], "binary_logloss")
        r2 = lgb_rounds(lgb.LGBMRegressor(**LGB_BASE), pos_fit[TREE_INPUTS], pos_fit[TARGET],
                        pos_val[TREE_INPUTS], pos_val[TARGET], "l1")
        rounds = (r1, r2)
    # refit on all training years, a little longer because there is more data
    clf = lgb.LGBMClassifier(**{**LGB_BASE, "n_estimators": int(rounds[0] * 1.15)})
    clf.fit(train[TREE_INPUTS], train["has_damage"])
    pos = train[train["has_damage"] == 1]
    reg = lgb.LGBMRegressor(**{**LGB_BASE, "n_estimators": int(rounds[1] * 1.15)})
    reg.fit(pos[TREE_INPUTS], pos[TARGET])
    smear = np.mean(10 ** (pos[TARGET].to_numpy() - reg.predict(pos[TREE_INPUTS])))
    p, mu = clf.predict_proba(test[TREE_INPUTS])[:, 1], reg.predict(test[TREE_INPUTS])
    return p, mu, p * 10 ** mu * smear, rounds, clf


def lgb_tweedie(power=1.5):
    """One gradient-boosted model of expected dollars; no separate probability or amount."""
    model = lgb.LGBMRegressor(**{**LGB_BASE, "objective": "tweedie", "tweedie_variance_power": power})
    r = lgb_rounds(model, fit_part[TREE_INPUTS], fit_part["PropertyDmgADJ"],
                   valid_part[TREE_INPUTS], valid_part["PropertyDmgADJ"], "tweedie")
    model = lgb.LGBMRegressor(**{**LGB_BASE, "objective": "tweedie", "tweedie_variance_power": power,
                                 "n_estimators": int(r * 1.15)})
    model.fit(train[TREE_INPUTS], train["PropertyDmgADJ"])
    e = model.predict(test[TREE_INPUTS])
    return e, r


def rf_hurdle():
    clf = RandomForestClassifier(n_estimators=300, min_samples_leaf=50, max_features="sqrt",
                                 n_jobs=-1, random_state=SEED)
    clf.fit(train[TREE_INPUTS], train["has_damage"])
    pos = train[train["has_damage"] == 1]
    reg = RandomForestRegressor(n_estimators=300, min_samples_leaf=10, max_features="sqrt",
                                oob_score=True, n_jobs=-1, random_state=SEED)
    reg.fit(pos[TREE_INPUTS], pos[TARGET])
    # smearing from out-of-bag residuals (in-sample forest residuals are too small)
    smear = np.mean(10 ** (pos[TARGET].to_numpy() - reg.oob_prediction_))
    p, mu = clf.predict_proba(test[TREE_INPUTS])[:, 1], reg.predict(test[TREE_INPUTS])
    return p, mu, p * 10 ** mu * smear


# ---------------------------------------------------------------
# 3. scores (same definitions as hurdle_model.py)
# ---------------------------------------------------------------
def auc(y, s):
    r = pd.Series(s).rank().to_numpy()
    n1 = y.sum()
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * (len(y) - n1))


def avg_precision(y, s):
    order = np.argsort(-s, kind="mergesort")
    hits = y[order]
    return (np.cumsum(hits) / np.arange(1, len(y) + 1))[hits == 1].mean()


def scores(p, mu, expected, base_brier):
    """p = score used for 'any damage' (a probability, or expected dollars for Tweedie)."""
    out = {"ROC-AUC": auc(yt, p), "PR-AUC": avg_precision(yt, p)}
    if p.max() <= 1:
        out["Brier skill"] = 1 - np.mean((p - yt) ** 2) / base_brier
        out["mean P / rate"] = p.mean() / yt.mean()
    d = test.assign(p=p, e=expected)
    out["AUC within month"] = np.mean([auc(g["has_damage"].to_numpy(), g["p"].to_numpy())
                                       for _, g in d.groupby(["year", "month"])
                                       if 0 < g["has_damage"].sum() < len(g)])
    k = int(round(TOP_SHARE * d["GEOID"].nunique()))
    month = d.groupby(["year", "month"]).apply(
        lambda g: pd.Series({"caught": g.nlargest(k, "e")["PropertyDmgADJ"].sum(),
                             "total": g["PropertyDmgADJ"].sum()}), include_groups=False)
    month = month[month["total"] > 0]
    rest = month.drop(month["total"].idxmax())
    out["top 5%: share of loss"] = month["caught"].sum() / month["total"].sum()
    out["... without largest month"] = rest["caught"].sum() / rest["total"].sum()
    out["... median month"] = (month["caught"] / month["total"]).median()
    yr = d.groupby(["year", "GEOID"])[["e", "PropertyDmgADJ"]].sum()
    out["rank corr, year"] = np.mean([g["e"].corr(g["PropertyDmgADJ"], method="spearman")
                                      for _, g in yr.groupby(level="year")])
    if mu is not None:
        dmg = yt == 1
        out["MAE, damaged"] = np.abs(test[TARGET].to_numpy()[dmg] - mu[dmg]).mean()
    return out


# ---------------------------------------------------------------
# 4. fit, score once on 2017-2023
# ---------------------------------------------------------------
results, preds = {}, {}
base = climatology(train, test)
base_brier = np.mean((base[0] - yt) ** 2)
results["baseline: county x month rate"], preds["baseline"] = scores(*base, base_brier), base[0]

glm = glm_hurdle(train, test)
results["GLM hurdle (hurdle_model.py)"], preds["GLM"] = scores(*glm, base_brier), glm[0]
print("GLM hurdle done")

rf = rf_hurdle()
results["random forest hurdle"], preds["RF"] = scores(*rf, base_brier), rf[0]
print("random forest done")

p, mu, e, rounds, clf = lgb_hurdle()
results["LightGBM hurdle"], preds["LGB"] = scores(p, mu, e, base_brier), p
print(f"LightGBM hurdle done (trees chosen on 2013-2016: part 1 {rounds[0]}, part 2 {rounds[1]})")

e_tw, r_tw = lgb_tweedie()
results["LightGBM Tweedie (one part)"], preds["Tweedie"] = scores(e_tw, None, e_tw, base_brier), e_tw
print(f"LightGBM Tweedie done ({r_tw} trees)")

# same LightGBM hurdle using only what is known before the month (no same-month weather)
SAME_MONTH = ["p_month", "rx1", "rx3", "rx5", "n_gt_p95", "n_gt_p99", "rx5_gt_rl10", "rx5_rl_ratio",
              "frost_days", "snowmelt_mm", "rain_x_wetsoil"]
full_inputs = TREE_INPUTS
TREE_INPUTS = [c for c in full_inputs if c not in SAME_MONTH]
p0, mu0, e0, _, _ = lgb_hurdle()
results["LightGBM hurdle, known in advance only"], preds["LGB_prior"] = scores(p0, mu0, e0, base_brier), p0
TREE_INPUTS = full_inputs

table = pd.DataFrame(results).T
pd.set_option("display.width", 220)
print(f"\nTEST 2017-2023 ({len(test):,} county-months, {int(yt.sum()):,} with damage)")
print(table.round(3).to_string())
os.makedirs("results", exist_ok=True)
table.round(4).to_csv("results/model_comparison.csv")


# ---------------------------------------------------------------
# 5. how sure? county bootstrap of ROC-AUC differences
# ---------------------------------------------------------------
rng = np.random.default_rng(SEED)
rows = test.groupby("GEOID").indices
ids = np.array(list(rows))
pairs = [("LGB", "GLM"), ("RF", "GLM"), ("Tweedie", "GLM"), ("LGB", "Tweedie"), ("LGB_prior", "baseline")]
draws = {pair: [] for pair in pairs}
for _ in range(N_BOOT):
    idx = np.concatenate([rows[g] for g in rng.choice(ids, len(ids))])
    for a, b in pairs:
        draws[(a, b)].append(auc(yt[idx], preds[a][idx]) - auc(yt[idx], preds[b][idx]))
print(f"\nROC-AUC differences, 95% interval from {N_BOOT} county bootstrap samples:")
for (a, b), d in draws.items():
    lo, hi = np.percentile(d, [2.5, 97.5])
    print(f"  {a:10s} vs {b:9s} {auc(yt, preds[a]) - auc(yt, preds[b]):+.4f}  ({lo:+.4f} to {hi:+.4f})")


# ---------------------------------------------------------------
# 6. what does the LightGBM classifier rely on? (gain importance, top 15)
# ---------------------------------------------------------------
imp = pd.Series(clf.booster_.feature_importance("gain"), index=full_inputs)
print("\nLightGBM part 1, share of total gain by input (top 15):")
print((imp / imp.sum()).sort_values(ascending=False).head(15).round(3).to_string())
