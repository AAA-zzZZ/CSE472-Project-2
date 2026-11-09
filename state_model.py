"""
Single-state hurdle models on the final Route 2 variables (yana_workspace/HANDOFF3.md).

  baseline         each county's damage rate for that calendar month in the training years
  GLM hurdle       ridge logistic + ridge linear regression on log10 damage
  LightGBM hurdle  gradient-boosted classifier + regressor, trained on the state only
  LightGBM, pooled the same model trained on all 12 Midwest states (with a state input),
                   scored on the state; shows whether one state has enough damage months

Final variables (calendar month is the only control; state is constant within one state):
  W same month   p_month, rx5_rl_ratio, frost_days (PRISM); snowmelt_mm (ERA5-Land)
  W in advance   sm_root_pct, swe_mm (ERA5-Land)
  C              c_rx5_rl10_mm (PRISM, 2000-2009)
  X              log_built_surface (GHSL), impervious_mean, hand_lt5_share, log_land_km2
  A              wetland_share

Train 2000-2016, test 2017-2023. Ridge strengths and numbers of trees are chosen on
2000-2012 -> 2013-2016; the test years are scored once.

Input : model_panel.csv from merge_panel.py (built with the PRISM thresholds)
Output: printed tables, results/state_<ST>_scores.csv, results/predictions_<ST>.csv

Usage:
    pip install lightgbm scikit-learn
    python state_model.py --state 29
"""

import argparse
import os

import lightgbm as lgb
import numpy as np
import pandas as pd

PANEL = "model_panel.csv"
TARGET = "log_PropertyDmgADJ"
STATES = {"17": "IL", "18": "IN", "19": "IA", "20": "KS", "26": "MI", "27": "MN",
          "29": "MO", "31": "NE", "38": "ND", "39": "OH", "46": "SD", "55": "WI"}
TOP_SHARE = 0.05
N_BOOT = 200
SEED = 472
RIDGE_GRID = [0.1, 1, 10, 100, 1000]

W_SAME = ["p_month", "rx5_rl_ratio", "frost_days", "snowmelt_mm"]
W_PRIOR = ["sm_root_pct", "swe_mm"]
C_COLS = ["c_rx5_rl10_mm"]
X_COLS = ["log_built_surface", "impervious_mean", "hand_lt5_share", "log_land_km2"]
A_COLS = ["wetland_share"]
INPUTS = W_SAME + W_PRIOR + C_COLS + X_COLS + A_COLS
# the GLM takes logs of the skewed rain and snow amounts
GLM_INPUTS = ["log_p_month", "rx5_rl_ratio", "frost_days", "log_snowmelt_mm", "sm_root_pct",
              "log_swe_mm"] + C_COLS + X_COLS + A_COLS


# ---------------------------------------------------------------
# 1. data
# ---------------------------------------------------------------
ap = argparse.ArgumentParser()
ap.add_argument("--state", default="29", help="two-digit state FIPS code, e.g. 29 for Missouri")
args = ap.parse_args()
ST = STATES[args.state]

data = pd.read_csv(PANEL, dtype={"GEOID": str})
for col in ["p_month", "swe_mm", "snowmelt_mm"]:
    data["log_" + col] = np.log1p(data[col].clip(lower=0))
data["log_land_km2"] = np.log(data["land_km2"])
data["state_code"] = data["GEOID"].str[:2].astype(int)
missing = data[INPUTS].isna().sum()
if missing.any():
    raise SystemExit(f"missing inputs: {missing[missing > 0].to_dict()}")

state = data[data["GEOID"].str[:2] == args.state]
train = state[state["split"] == "train"].reset_index(drop=True)
test = state[state["split"] == "test"].reset_index(drop=True)
fit_part, valid_part = train[train["year"] <= 2012], train[train["year"] >= 2013]
yt = test["has_damage"].to_numpy()
print(f"{ST}: {state['GEOID'].nunique()} counties; train {len(train):,} county-months "
      f"({int(train['has_damage'].sum())} with damage, {train['has_damage'].mean():.2%}), "
      f"test {len(test):,} ({int(yt.sum())}, {yt.mean():.2%})")


# ---------------------------------------------------------------
# 2. models
# ---------------------------------------------------------------
def climatology(fit_df, score_df, prior=2.0):
    """County x calendar-month damage rate, shrunk toward the state's rate for that month."""
    rate = fit_df.groupby(["GEOID", "month"])["has_damage"].agg(["sum", "count"])
    month_rate = fit_df.groupby("month")["has_damage"].mean().rename("month_rate")
    pos = fit_df[fit_df["has_damage"] == 1]
    sev = pos.groupby("GEOID")[TARGET].mean().rename("sev")
    df = score_df[["GEOID", "month"]].join(rate, on=["GEOID", "month"]).join(month_rate, on="month").join(sev, on="GEOID")
    p = ((df["sum"].fillna(0) + prior * df["month_rate"]) / (df["count"].fillna(0) + prior)).to_numpy()
    mu = df["sev"].fillna(pos[TARGET].mean()).to_numpy()
    return p, mu, p * 10 ** mu


def glm_design(df, ref):
    X = (df[GLM_INPUTS] - ref[GLM_INPUTS].mean()) / ref[GLM_INPUTS].std()
    X = pd.concat([X, pd.get_dummies(df["month"], prefix="m", dtype=float)
                   .reindex(columns=[f"m_{m}" for m in range(2, 13)], fill_value=0.0)], axis=1)
    X["const"] = 1.0
    return X


def glm_hurdle(fit_df, score_df, ridge1, ridge2):
    """Ridge logistic for any damage + ridge linear regression on log10 damage; no penalty on month."""
    def lam(X, r):
        return np.diag([1e-6 if c == "const" or c.startswith("m_") else r for c in X.columns])
    X, y = glm_design(fit_df, fit_df), fit_df["has_damage"].to_numpy()
    A, L = X.to_numpy(), lam(X, ridge1)
    b = np.zeros(A.shape[1])
    b[-1] = np.log(y.mean() / (1 - y.mean()))
    for _ in range(50):
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
    return p, mu, p * 10 ** mu * smear, pd.Series(b, index=X.columns)


def pick_ridge():
    """Ridge strengths chosen on 2000-2012 -> 2013-2016: log loss for part 1, MAE for part 2."""
    yv = valid_part["has_damage"].to_numpy()
    pos_v = (yv == 1)
    loss1, loss2 = {}, {}
    for r in RIDGE_GRID:
        p, mu, _, _ = glm_hurdle(fit_part, valid_part, r, r)
        p = p.clip(1e-9, 1 - 1e-9)
        loss1[r] = -np.mean(yv * np.log(p) + (1 - yv) * np.log(1 - p))
        loss2[r] = np.abs(valid_part[TARGET].to_numpy()[pos_v] - mu[pos_v]).mean()
    return min(loss1, key=loss1.get), min(loss2, key=loss2.get)


LGB_BASE = dict(learning_rate=0.03, num_leaves=15, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                reg_lambda=1.0, n_estimators=3000, random_state=SEED, verbose=-1)


def lgb_hurdle(fit_df, valid_df, train_df, score_df, inputs, min_leaf_1, min_leaf_2):
    """Gradient-boosted classifier for any damage + regressor on log10 damage. Number of trees by
    early stopping on the validation years, then refit on all training years. More rain can
    only raise the prediction (monotone constraints)."""
    mono =[1 if c in ("p_month", "rx5_rl_ratio") else 0 for c in inputs]
    p1 = {**LGB_BASE, "min_child_samples": min_leaf_1, "monotone_constraints": mono}
    p2 = {**LGB_BASE, "min_child_samples": min_leaf_2, "monotone_constraints": mono}
    stop = [lgb.early_stopping(100, verbose=False)]
    clf = lgb.LGBMClassifier(**p1, metric="binary_logloss")
    clf.fit(fit_df[inputs], fit_df["has_damage"], eval_set=[(valid_df[inputs], valid_df["has_damage"])], callbacks=stop)
    r1 = clf.best_iteration_
    pf, pv = fit_df[fit_df["has_damage"] == 1], valid_df[valid_df["has_damage"] == 1]
    reg = lgb.LGBMRegressor(**p2, metric="l1")
    reg.fit(pf[inputs], pf[TARGET], eval_set=[(pv[inputs], pv[TARGET])], callbacks=stop)
    r2 = reg.best_iteration_
    clf = lgb.LGBMClassifier(**{**p1, "n_estimators": max(int(r1 * 1.15), 10)}).fit(train_df[inputs], train_df["has_damage"])
    pos = train_df[train_df["has_damage"] == 1]
    reg = lgb.LGBMRegressor(**{**p2, "n_estimators": max(int(r2 * 1.15), 10)}).fit(pos[inputs], pos[TARGET])
    smear = np.mean(10 ** (pos[TARGET].to_numpy() - reg.predict(pos[inputs])))
    p, mu = clf.predict_proba(score_df[inputs])[:, 1], reg.predict(score_df[inputs])
    return p, mu, p * 10 ** mu * smear, (r1, r2), clf


# ---------------------------------------------------------------
# 3. scores (same definitions as model_comparison.py)
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
    out = {"ROC-AUC": auc(yt, p), "PR-AUC": avg_precision(yt, p),
           "Brier skill": 1 - np.mean((p - yt) ** 2) / base_brier, "mean P / rate": p.mean() / yt.mean()}
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
    yr = d.groupby(["year", "GEOID"])[["e", "PropertyDmgADJ"]].sum()
    out["rank corr, year"] = np.mean([g["e"].corr(g["PropertyDmgADJ"], method="spearman")
                                      for _, g in yr.groupby(level="year")])
    dmg = yt == 1
    out["MAE, damaged"] = np.abs(test[TARGET].to_numpy()[dmg] - mu[dmg]).mean()
    return out


# ---------------------------------------------------------------
# 4. fit, score once on 2017-2023
# ---------------------------------------------------------------
results, preds = {}, {}
base = climatology(train, test)
base_brier = np.mean((base[0] - yt) ** 2)
results["baseline: county x month rate"], preds["baseline"] = scores(*base, base_brier), base

r1, r2 = pick_ridge()
glm = glm_hurdle(train, test, r1, r2)
results["GLM hurdle"], preds["GLM"] = scores(*glm[:3], base_brier), glm[:3]
print(f"GLM hurdle done (ridge chosen on 2013-2016: part 1 {r1}, part 2 {r2})")

lgb_in = INPUTS + ["month"]
p, mu, e, rounds, clf = lgb_hurdle(fit_part, valid_part, train, test, lgb_in, 50, 20)
results["LightGBM hurdle"], preds["LGB"] = scores(p, mu, e, base_brier), (p, mu, e)
print(f"LightGBM hurdle done (trees: part 1 {rounds[0]}, part 2 {rounds[1]})")

# pooled: train on every Midwest state, score this state's test rows
all_train = data[data["split"] == "train"]
pool_in = lgb_in + ["state_code"]
pp, pmu, pe, prounds, _ = lgb_hurdle(all_train[all_train["year"] <= 2012], all_train[all_train["year"] >= 2013],
                                     all_train, test, pool_in, 100, 50)
results["LightGBM hurdle, trained on 12 states"], preds["LGB_pooled"] = scores(pp, pmu, pe, base_brier), (pp, pmu, pe)
print(f"pooled LightGBM done (trees: part 1 {prounds[0]}, part 2 {prounds[1]})")

table = pd.DataFrame(results).T
pd.set_option("display.width", 220)
print(f"\nTEST 2017-2023, {ST} ({len(test):,} county-months, {int(yt.sum())} with damage, "
      f"top 5% = {int(round(TOP_SHARE * test['GEOID'].nunique()))} counties a month)")
print(table.round(3).to_string())
os.makedirs("results", exist_ok=True)
table.round(4).to_csv(f"results/state_{ST}_scores.csv")


# ---------------------------------------------------------------
# 5. how sure? county bootstrap of ROC-AUC differences
# ---------------------------------------------------------------
rng = np.random.default_rng(SEED)
rows = test.groupby("GEOID").indices
ids = np.array(list(rows))
pairs = [("LGB", "baseline"), ("GLM", "baseline"), ("LGB", "GLM"), ("LGB_pooled", "LGB")]
draws = {pair: [] for pair in pairs}
for _ in range(N_BOOT):
    idx = np.concatenate([rows[g] for g in rng.choice(ids, len(ids))])
    for a, b in pairs:
        draws[(a, b)].append(auc(yt[idx], preds[a][0][idx]) - auc(yt[idx], preds[b][0][idx]))
print(f"\nROC-AUC differences, 95% interval from {N_BOOT} county bootstrap samples:")
for (a, b), d in draws.items():
    lo, hi = np.percentile(d, [2.5, 97.5])
    print(f"  {a:10s} vs {b:9s} {auc(yt, preds[a][0]) - auc(yt, preds[b][0]):+.4f}  ({lo:+.4f} to {hi:+.4f})")

print("\nGLM part 1 coefficients (per standard deviation):")
print(glm[3].drop([c for c in glm[3].index if c.startswith("m_")]).round(3).to_string())
imp = pd.Series(clf.booster_.feature_importance("gain"), index=lgb_in)
print("\nLightGBM part 1, share of total gain by input:")
print((imp / imp.sum()).sort_values(ascending=False).round(3).to_string())


# ---------------------------------------------------------------
# 6. predictions for the Earth Engine app (upload as a table asset); also carries the inputs
#    that need county baselines (C, rx5 / 10-year level, soil moisture percentile)
# ---------------------------------------------------------------
p, mu, e = preds["LGB"]
out = test[["GEOID", "year", "month", "has_damage", "PropertyDmgADJ",
            "c_rx5_rl10_mm", "rx5_rl_ratio", "sm_root_pct"]].assign(
    p_damage=p.round(5), expected_dmg=e.round(0))
out.to_csv(f"results/predictions_{ST}.csv", index=False)
print(f"\nwrote results/state_{ST}_scores.csv and results/predictions_{ST}.csv ({len(out):,} rows)")
