"""
Hurdle (two-part) impact model on the county x month table, zeros included.

  part 1  P(damage > 0 | w, x, c)             logistic regression, every county-month
  part 2  log10 damage | damage > 0, w, x, c  linear regression, damaged county-months
  expected loss = P(damage) x E[damage | damage]

Input : model_panel.csv from merge_panel.py (303,840 county-months, 2000-2023)
Output: printed tables, and results/hurdle_scores.csv

Design (see HANDOFF.md):
  * Train 2000-2016, test 2017-2023. Ridge strengths are chosen on 2000-2012 vs 2013-2016;
    the test years are scored once, at the end.
  * Models add one block at a time, so each row shows what that block adds:
      setting        exposure, susceptibility, rain climate (C), wetlands, state, calendar month
      + known in advance   previous-month rain index, soil moisture and snowpack on day 1,
                           previous month's snowmelt (all known before the month starts)
      + monthly rain       same-month total            } same-month hazard = a perfect
      + 5-day extreme      wettest 5 days / 10-yr level } weather forecast, the upper bound
      + snow and frost     same-month snowmelt and frost days, rain x wet soil
    The rain measures overlap (Spearman 0.87-0.96), so only one enters per step.
  * Reporting rates differ by state (Iowa 7.9% of months vs Illinois 2.6% in 2000-2016), so
    every model has a state effect; one row drops it to show its size, and results are
    also given by state.
  * Baseline to beat: each county's damage rate for that calendar month in 2000-2016.

Usage:
    python hurdle_model.py
"""

import os

import numpy as np
import pandas as pd

PANEL = "model_panel.csv"
TARGET = "log_PropertyDmgADJ"
STATES = {"17": "IL", "18": "IN", "19": "IA", "20": "KS", "26": "MI", "27": "MN",
          "29": "MO", "31": "NE", "38": "ND", "39": "OH", "46": "SD", "55": "WI"}
RIDGE_GRID = [0.1, 1, 10, 100, 1000]
TOP_SHARE = 0.05             # ranking: the top 5% of counties each month (53 of 1,055)
N_BOOT = 200

# one representative per group of overlapping columns
X_COLS = ["log_housing_units", "urban_share", "impervious_mean", "water_share",
          "hand_lt5_share", "log_land_km2"]
A_COLS = ["wetland_share"]
C_COLS = ["c_rx5_rl10_mm"]
W_PRIOR = ["spi1_prev", "sm_root_pct", "log_swe_mm", "log_snowmelt_prev_mm"]
W_RAIN = ["log_p_month"]
W_RX5 = ["rx5_rl_ratio"]
W_SNOW = ["log_snowmelt_mm", "frost_days", "rain_x_wetsoil"]

SETTING = X_COLS + A_COLS + C_COLS
MODELS = {
    "setting (x, c, state, month)": SETTING,
    "+ known in advance": SETTING + W_PRIOR,
    "+ monthly rain": SETTING + W_PRIOR + W_RAIN,
    "+ 5-day extreme": SETTING + W_PRIOR + W_RAIN + W_RX5,
    "+ snow and frost (full)": SETTING + W_PRIOR + W_RAIN + W_RX5 + W_SNOW,
}
FULL = MODELS["+ snow and frost (full)"]
CHECKS = {
    "full, no state effect": (FULL, False),
    "full, no rain climate (C)": ([c for c in FULL if c not in C_COLS], True),
}


# ---------------------------------------------------------------
# 1. data
# ---------------------------------------------------------------
data = pd.read_csv(PANEL, dtype={"GEOID": str})
data["state"] = data["GEOID"].str[:2].map(STATES)
# amounts in mm are skewed; ERA5 snowpack can be a hair below zero
for col in ["p_month", "swe_mm", "snowmelt_mm", "snowmelt_prev_mm"]:
    data["log_" + col] = np.log1p(data[col].clip(lower=0))
data["log_land_km2"] = np.log(data["land_km2"])

train = data[data["split"] == "train"].reset_index(drop=True)
test = data[data["split"] == "test"].reset_index(drop=True)
fit_part = train[train["year"] <= 2012].reset_index(drop=True)
valid_part = train[train["year"] >= 2013].reset_index(drop=True)
print(f"train 2000-2016: {len(train):,} county-months ({train['has_damage'].mean():.2%} with damage); "
      f"test 2017-2023: {len(test):,} ({test['has_damage'].mean():.2%})")
print(f"validation: fit 2000-2012 ({len(fit_part):,}), score 2013-2016 ({len(valid_part):,})")


# ---------------------------------------------------------------
# 2. model pieces
# ---------------------------------------------------------------
def design(df, features, ref, state=True):
    """Standardize with the fitting data only; calendar-month and state indicators, first dropped."""
    X = (df[features] - ref[features].mean()) / ref[features].std()
    parts = [X, pd.get_dummies(df["month"], prefix="m", dtype=float)
             .reindex(columns=[f"m_{m}" for m in range(2, 13)], fill_value=0.0)]
    if state:
        parts.append(pd.get_dummies(df["state"], prefix="st", dtype=float)
                     .reindex(columns=[f"st_{s}" for s in sorted(STATES.values())[1:]], fill_value=0.0))
    X = pd.concat(parts, axis=1)
    X["const"] = 1.0
    return X


def penalty(X, ridge):
    # ridge on the standardized features only, never on the intercept or the indicators
    return np.array([ridge if not (c == "const" or c.startswith(("m_", "st_"))) else 1e-6
                     for c in X.columns])


def fit_logit(X, y, ridge):
    """Logistic regression by Newton's method with a ridge penalty."""
    A, y, lam = X.to_numpy(), y.to_numpy(), penalty(X, ridge)
    beta = np.zeros(A.shape[1])
    beta[-1] = np.log(y.mean() / (1 - y.mean()))
    for _ in range(30):
        p = 1 / (1 + np.exp(-(A @ beta)))
        step = np.linalg.solve(A.T @ (A * (p * (1 - p))[:, None]) + np.diag(lam), A.T @ (y - p) - lam * beta)
        beta += step
        if np.abs(step).max() < 1e-8:
            break
    return pd.Series(beta, index=X.columns)


def fit_ols(X, y, ridge):
    A, lam = X.to_numpy(), penalty(X, ridge)
    return pd.Series(np.linalg.solve(A.T @ A + np.diag(lam), A.T @ y.to_numpy()), index=X.columns)


def logistic(X, beta):
    return 1 / (1 + np.exp(-(X @ beta)))


def hurdle(features, fit_df, score_df, ridge1, ridge2, state=True):
    """P(damage), predicted log damage and smeared expected dollars for score_df."""
    pos = fit_df[fit_df["has_damage"] == 1]
    b1 = fit_logit(design(fit_df, features, fit_df, state), fit_df["has_damage"], ridge1)
    b2 = fit_ols(design(pos, features, fit_df, state), pos[TARGET], ridge2)
    residual = pos[TARGET] - design(pos, features, fit_df, state) @ b2
    X = design(score_df, features, fit_df, state)
    p, mu = logistic(X, b1), X @ b2
    # E[10^log] is not 10^E[log]: scale by the mean of 10^residual (smearing)
    expected = p * 10 ** mu * np.mean(10 ** residual)
    return p.to_numpy(), mu.to_numpy(), expected.to_numpy(), b1, b2


def climatology(fit_df, score_df, prior=2.0):
    """Baseline: each county's damage rate for that calendar month in fit_df, shrunk toward its
    state's rate for that month (prior = pseudo-years); severity = county mean log damage."""
    rate = fit_df.groupby(["GEOID", "month"])["has_damage"].agg(["sum", "count"])
    state_rate = fit_df.groupby(["state", "month"])["has_damage"].mean().rename("state_rate")
    pos = fit_df[fit_df["has_damage"] == 1]
    sev = pos.groupby("GEOID")[TARGET].mean().rename("sev")
    df = (score_df[["GEOID", "state", "month"]]
          .join(rate, on=["GEOID", "month"]).join(state_rate, on=["state", "month"]).join(sev, on="GEOID"))
    p = (df["sum"] + prior * df["state_rate"]) / (df["count"] + prior)
    mu = df["sev"].fillna(pos[TARGET].mean())
    return p.to_numpy(), mu.to_numpy(), (p * 10 ** mu).to_numpy()


# ---------------------------------------------------------------
# 3. scores
# ---------------------------------------------------------------
def auc(y, s):
    """Chance that a random damaged county-month scores above a random undamaged one."""
    r = pd.Series(s).rank().to_numpy()
    n1 = y.sum()
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * (len(y) - n1))


def avg_precision(y, s):
    """PR-AUC: precision averaged over the damaged county-months, in score order."""
    order = np.argsort(-s, kind="mergesort")
    hits = y[order]
    return (np.cumsum(hits) / np.arange(1, len(y) + 1))[hits == 1].mean()


def scores(df, p, mu, expected, base_brier):
    y = df["has_damage"].to_numpy()
    pc = np.clip(p, 1e-9, 1 - 1e-9)
    brier = np.mean((pc - y) ** 2)
    out = {"ROC-AUC": auc(y, p), "PR-AUC": avg_precision(y, p), "Brier": brier,
           "Brier skill": 1 - brier / base_brier,
           "log loss": -np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc)),
           "mean P / rate": pc.mean() / y.mean()}
    d = df.assign(p=p, e=expected)
    # ranking counties within the same month removes the credit for knowing the season
    within = [auc(g["has_damage"].to_numpy(), g["p"].to_numpy())
              for _, g in d.groupby(["year", "month"]) if 0 < g["has_damage"].sum() < len(g)]
    out["AUC within month"] = np.mean(within)
    # share of each month's loss in the model's top 5% of counties. in dollars a few months
    # dominate (March 2019 holds 21% of all test-year loss), so it is also given without the
    # largest month and as the median month
    k = int(round(TOP_SHARE * d["GEOID"].nunique()))
    month = d.groupby(["year", "month"]).apply(
        lambda g: pd.Series({"caught": g.nlargest(k, "e")["PropertyDmgADJ"].sum(),
                             "total": g["PropertyDmgADJ"].sum()}), include_groups=False)
    month = month[month["total"] > 0]
    rest = month.drop(month["total"].idxmax())
    out["top 5%: share of loss"] = month["caught"].sum() / month["total"].sum()
    out["... without largest month"] = rest["caught"].sum() / rest["total"].sum()
    out["... median month"] = (month["caught"] / month["total"]).median()
    # county-year totals, ranked within each year
    yr = d.groupby(["year", "GEOID"])[["e", "PropertyDmgADJ"]].sum()
    out["rank corr, year"] = np.mean([g["e"].corr(g["PropertyDmgADJ"], method="spearman")
                                      for _, g in yr.groupby(level="year")])
    damaged = y == 1
    out["MAE, damaged"] = np.abs(df[TARGET].to_numpy()[damaged] - mu[damaged]).mean()
    return out


# ---------------------------------------------------------------
# 4. choose ridge strengths on 2000-2012 -> 2013-2016
# ---------------------------------------------------------------
print("\nchoosing ridge strength on the full model (validation 2013-2016):")
vy = valid_part["has_damage"].to_numpy()
vpos = valid_part["has_damage"] == 1
fit_pos = fit_part[fit_part["has_damage"] == 1]
rows = []
for lam in RIDGE_GRID:
    p, mu, _, _, _ = hurdle(FULL, fit_part, valid_part, lam, lam)
    pc = np.clip(p, 1e-9, 1 - 1e-9)
    rows.append({"ridge": lam, "log loss": -np.mean(vy * np.log(pc) + (1 - vy) * np.log(1 - pc)),
                 "ROC-AUC": auc(vy, p),
                 "MAE, damaged": np.abs(valid_part.loc[vpos, TARGET].to_numpy() - mu[vpos.to_numpy()]).mean()})
grid = pd.DataFrame(rows).set_index("ridge")
print(grid.round(4).to_string())
RIDGE1 = grid["log loss"].idxmin()
RIDGE2 = grid["MAE, damaged"].idxmin()
print(f"chosen: part 1 ridge {RIDGE1}, part 2 ridge {RIDGE2}")

valid_base = climatology(fit_part, valid_part)
valid_brier = np.mean((valid_base[0] - vy) ** 2)
print("\nvalidation scores, 2013-2016 (models chosen here, before looking at the test years):")
vt = {"baseline: county x month rate": scores(valid_part, *valid_base, valid_brier)}
for name, feats in MODELS.items():
    p, mu, e, _, _ = hurdle(feats, fit_part, valid_part, RIDGE1, RIDGE2)
    vt[name] = scores(valid_part, p, mu, e, valid_brier)
print(pd.DataFrame(vt).T[["ROC-AUC", "PR-AUC", "Brier skill", "AUC within month"]].round(3).to_string())


# ---------------------------------------------------------------
# 5. final fits on 2000-2016, scored once on 2017-2023
# ---------------------------------------------------------------
yt = test["has_damage"].to_numpy()
base = climatology(train, test)
base_brier = np.mean((base[0] - yt) ** 2)
results, preds = {}, {}
results["baseline: county x month rate"] = scores(test, *base, base_brier)
preds["baseline: county x month rate"] = base[0]
fits = {}
for name, feats in MODELS.items():
    p, mu, e, b1, b2 = hurdle(feats, train, test, RIDGE1, RIDGE2)
    results[name], preds[name], fits[name] = scores(test, p, mu, e, base_brier), p, (b1, b2)
for name, (feats, state) in CHECKS.items():
    p, mu, e, b1, b2 = hurdle(feats, train, test, RIDGE1, RIDGE2, state)
    results[name], preds[name], fits[name] = scores(test, p, mu, e, base_brier), p, (b1, b2)

table = pd.DataFrame(results).T
pd.set_option("display.width", 200)
print(f"\nTEST 2017-2023: {len(test):,} county-months, {int(yt.sum()):,} with damage")
print("part 1 (any damage): higher ROC-AUC, PR-AUC, Brier skill is better; mean P / rate 1 = calibrated")
print(table[["ROC-AUC", "PR-AUC", "Brier skill", "log loss", "mean P / rate", "AUC within month"]].round(3).to_string())
print("\nranking and amount: share of each month's loss in the model's top 5% of counties (all months, "
      "without the largest month, median month); rank correlation of county-year totals; part-2 error "
      "on damaged months (log10 $)")
print(table[["top 5%: share of loss", "... without largest month", "... median month",
             "rank corr, year", "MAE, damaged"]].round(3).to_string())
os.makedirs("results", exist_ok=True)
table.round(4).to_csv("results/hurdle_scores.csv")


# ---------------------------------------------------------------
# 6. how sure are the differences? bootstrap over counties
# ---------------------------------------------------------------
# resample whole counties (a county's months are not independent), keep the predictions fixed
comparisons = [("+ known in advance", "setting (x, c, state, month)"),
               ("+ monthly rain", "+ known in advance"),
               ("+ 5-day extreme", "+ monthly rain"),
               ("+ snow and frost (full)", "+ 5-day extreme"),
               ("+ snow and frost (full)", "full, no state effect"),
               ("+ snow and frost (full)", "full, no rain climate (C)"),
               ("+ known in advance", "baseline: county x month rate")]
rng = np.random.default_rng(472)
county_rows = test.groupby("GEOID").indices
ids = np.array(list(county_rows))
draws = {pair: [] for pair in comparisons}
for _ in range(N_BOOT):
    idx = np.concatenate([county_rows[g] for g in rng.choice(ids, len(ids))])
    y = yt[idx]
    for a, b in comparisons:
        draws[(a, b)].append(auc(y, preds[a][idx]) - auc(y, preds[b][idx]))
print(f"\nROC-AUC differences, 95% interval from {N_BOOT} county bootstrap samples:")
for (a, b), d in draws.items():
    lo, hi = np.percentile(d, [2.5, 97.5])
    print(f"  {a:26s} vs {b:30s} {results[a]['ROC-AUC'] - results[b]['ROC-AUC']:+.4f}  ({lo:+.4f} to {hi:+.4f})")


# ---------------------------------------------------------------
# 7. by test year and by state
# ---------------------------------------------------------------
show = ["baseline: county x month rate", "+ known in advance", "+ snow and frost (full)"]


def breakdown(key):
    out = {}
    for k, g in test.groupby(key):
        i = g.index.to_numpy()
        y = yt[i]
        row = {"damage rate": y.mean()}
        for name in show:
            short = name.split(":")[0].replace("+ ", "").replace(" (full)", "")
            row[f"AUC {short}"] = auc(y, preds[name][i]) if 0 < y.sum() < len(y) else np.nan
            row[f"P/rate {short}"] = preds[name][i].mean() / y.mean() if y.sum() else np.nan
        out[k] = row
    return pd.DataFrame(out).T


print("\nby test year (P/rate above 1 = the model expects more damage months than happened):")
print(breakdown("year").round(3).to_string())
print("\nby state, test years:")
print(breakdown("state").round(3).to_string())


# ---------------------------------------------------------------
# 8. coefficients, and the confounding check
# ---------------------------------------------------------------
b1, b2 = fits["+ snow and frost (full)"]
print("\nfull model coefficients (per 1 std of each input):")
print(pd.DataFrame({"part 1 (log-odds of damage)": b1[FULL], "part 2 (log10 dollars)": b2[FULL]})
      .round(3).to_string())
# w <- c -> a -> y: if C confounds the hazard, the hazard coefficients move when C is dropped
b1_no_c = fits["full, no rain climate (C)"][0]
hazard = W_PRIOR + W_RAIN + W_RX5 + W_SNOW
print("\npart 1 hazard coefficients with vs without rain climate (C):")
print(pd.DataFrame({"with C": b1[hazard], "without C": b1_no_c[hazard]}).round(3).to_string())


# ---------------------------------------------------------------
# 9. simulation check: does the fitting code recover known coefficients?
# ---------------------------------------------------------------
# outcomes drawn from known coefficients on the REAL training rows; some are zero on purpose
X = design(train, FULL, train)
true = pd.Series(0.0, index=X.columns)
true["const"], true["log_p_month"], true["rx5_rl_ratio"] = -4.0, 0.4, 0.5
true["sm_root_pct"], true["log_housing_units"], true["c_rx5_rl10_mm"] = 0.3, 0.3, -0.2
sim_y = pd.Series((rng.random(len(X)) < logistic(X, true)).astype(int))
sim = fit_logit(X, sim_y, 1e-6)
ps = logistic(X, sim).to_numpy()
se = np.sqrt(np.diag(np.linalg.inv(X.to_numpy().T @ (X.to_numpy() * (ps * (1 - ps))[:, None]))))
check = pd.DataFrame({"true": true, "fitted": sim, "std err": se})
check["within 2 se"] = (check["true"] - check["fitted"]).abs() <= 2 * check["std err"]
print(f"\nsimulated check, part 1 ({sim_y.mean():.1%} simulated damage months):")
print(check.loc[FULL + ["const"]].round(3).to_string())
print(f"coefficients within 2 std err: {check['within 2 se'].sum()} / {len(check)}")
