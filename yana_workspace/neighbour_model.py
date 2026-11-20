"""
Does the neighbouring counties' hazard help predict Washington County's flood damage?

Hurdle model (as in hurdle_model.py), fitted with and without the neighbour (nb_*) hazard:
  part 1  P(damage > 0)                logistic regression, every month
  part 2  log10 damage | damage > 0    linear regression, damaged months
  expected loss = P(damage) x 10^(part 2) x smearing factor

Inputs : yana_workspace/data/focus_panel_39167.csv   Washington, 168 months (2010-2023)
         yana_workspace/data/county_set_panel.csv    5 counties x 168 months
Outputs: yana_workspace/results/neighbour_scores.csv     test scores of every model
         yana_workspace/results/neighbour_coefs.csv      standardized coefficients
         yana_workspace/results/predictions_5county.csv  pooled model predictions (for the GEE app)

Design
  * Train 2010-2018, test 2019-2023 (scored once). Ridge strength picked by leave-one-year-out
    cross-validation inside 2010-2018.
  * One county has no variation in setting (X, C, A), so the focus models use only the monthly
    hazard (W) plus a smooth season (sin/cos of the month): 11 month dummies are too many for
    26 training damage months.
  * Models: climatology baseline (training damage rate per calendar month), own hazard,
    own + neighbour hazard, neighbour hazard only.
  * Intervals: bootstrap over test years (only 5, so they are wide). A leave-one-year-out run over
    all 14 years is printed as a robustness check (it trains on later years, so it is not a forecast).
  * Pooled check: all 5 counties as rows, county indicators, each county's neighbour hazard =
    land-weighted mean of its bordering counties inside the 5-county set.

Usage:
    python yana_workspace/neighbour_model.py
"""

import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "results")
TARGET = "log_PropertyDmgADJ"
RIDGE_GRID = [0.3, 1, 3, 10, 30, 100, 300]
N_BOOT = 2000
RNG = np.random.default_rng(472)

HAZARD = ["log_p_month", "rx5_rl_ratio", "log_snowmelt_mm", "frost_days", "sm_root_pct", "log_swe_mm"]
NB = ["nb_" + c for c in HAZARD]
SEASON = ["season_sin", "season_cos"]
# bordering counties inside the 5-county set (shared boundary points in counties_midwest.geojson)
BORDERS = {"39167": ["39009", "39111", "39115", "39121"], "39009": ["39167", "39115"],
           "39111": ["39167", "39121"], "39115": ["39167", "39009", "39121"],
           "39121": ["39167", "39111", "39115"]}
RAW = ["p_month", "rx5_rl_ratio", "snowmelt_mm", "frost_days", "sm_root_pct", "swe_mm"]


def add_features(df, prefix=""):
    for col in ["p_month", "snowmelt_mm", "swe_mm"]:
        if prefix + col in df:
            df[prefix + "log_" + col] = np.log1p(df[prefix + col].clip(lower=0))
    df["season_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["season_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    return df


# ---------------------------------------------------------------
# model pieces (numpy only)
# ---------------------------------------------------------------
def design(df, cols, ref, dummies=()):
    X = (df[cols] - ref[cols].mean()) / ref[cols].std().replace(0, 1)
    for d in dummies:
        X[d] = df[d].astype(float)
    X["const"] = 1.0
    return X


def penalty(X, ridge):
    return np.array([1e-6 if c in ("const",) or c.startswith(("season_", "cty_")) else ridge
                     for c in X.columns])


def fit_logit(X, y, ridge):
    A, y, lam = X.to_numpy(), np.asarray(y, float), penalty(X, ridge)
    beta = np.zeros(A.shape[1])
    beta[-1] = np.log(y.mean() / (1 - y.mean()))
    for _ in range(50):
        p = 1 / (1 + np.exp(-(A @ beta)))
        step = np.linalg.solve(A.T @ (A * (p * (1 - p))[:, None]) + np.diag(lam),
                               A.T @ (y - p) - lam * beta)
        beta += step
        if np.abs(step).max() < 1e-8:
            break
    return pd.Series(beta, index=X.columns)


def fit_ols(X, y, ridge):
    A, lam = X.to_numpy(), penalty(X, ridge)
    return pd.Series(np.linalg.solve(A.T @ A + np.diag(lam), A.T @ np.asarray(y, float)), index=X.columns)


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


def pick_ridge(train, cols, dummies):
    """Leave-one-year-out CV inside the training years: log-loss for part 1, MSE for part 2."""
    best = {}
    for part in (1, 2):
        losses = {}
        for r in RIDGE_GRID:
            err = []
            for yr in sorted(train["year"].unique()):
                fit, val = train[train.year != yr], train[train.year == yr]
                if part == 1:
                    b = fit_logit(design(fit, cols, fit, dummies), fit["has_damage"], r)
                    p = np.clip(sigmoid(design(val, cols, fit, dummies) @ b), 1e-6, 1 - 1e-6)
                    y = val["has_damage"]
                    err.extend(-(y * np.log(p) + (1 - y) * np.log(1 - p)))
                else:
                    fp, vp = fit[fit.has_damage == 1], val[val.has_damage == 1]
                    if len(vp) == 0:
                        continue
                    b = fit_ols(design(fp, cols, fit, dummies), fp[TARGET], r)
                    err.extend((vp[TARGET] - design(vp, cols, fit, dummies) @ b) ** 2)
            losses[r] = np.mean(err)
        best[part] = min(losses, key=losses.get)
    return best[1], best[2]


def hurdle(fit, score, cols, dummies=(), ridges=None):
    r1, r2 = ridges or pick_ridge(fit, cols, dummies)
    pos = fit[fit.has_damage == 1]
    b1 = fit_logit(design(fit, cols, fit, dummies), fit["has_damage"], r1)
    b2 = fit_ols(design(pos, cols, fit, dummies), pos[TARGET], r2)
    smear = np.mean(10 ** (pos[TARGET] - design(pos, cols, fit, dummies) @ b2))
    X = design(score, cols, fit, dummies)
    p, mu = sigmoid(X @ b1).to_numpy(), (X @ b2).to_numpy()
    return {"p": p, "mu": mu, "expected": p * 10 ** mu * smear, "b1": b1, "b2": b2, "ridge": (r1, r2)}


def climatology(fit, score, group=("month",), prior=2.0):
    """Damage rate per calendar month (and county) in fit, shrunk toward the overall rate."""
    overall = fit["has_damage"].mean()
    g = fit.groupby(list(group))["has_damage"].agg(["sum", "count"])
    rate = ((g["sum"] + prior * overall) / (g["count"] + prior)).rename("p")
    p = score.join(rate, on=list(group))["p"].fillna(overall).to_numpy()
    mu = np.full(len(score), fit.loc[fit.has_damage == 1, TARGET].mean())
    return {"p": p, "mu": mu}


def auc(y, s):
    y, s = np.asarray(y), np.asarray(s)
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return np.nan
    return (np.sum(pos[:, None] > neg[None, :]) + 0.5 * np.sum(pos[:, None] == neg[None, :])) / (len(pos) * len(neg))


def avg_precision(y, s):
    y = np.asarray(y)[np.argsort(-np.asarray(s), kind="stable")]
    hits = np.cumsum(y)
    return np.sum((hits / np.arange(1, len(y) + 1))[y == 1]) / max(y.sum(), 1)


def scores(df, pred, base_p):
    y = df["has_damage"].to_numpy()
    brier, base_brier = np.mean((pred["p"] - y) ** 2), np.mean((base_p - y) ** 2)
    d = y == 1
    resid = df[TARGET].to_numpy()[d] - pred["mu"][d]
    return {"ROC-AUC": auc(y, pred["p"]), "PR-AUC": avg_precision(y, pred["p"]),
            "Brier": brier, "Brier skill vs climatology": 1 - brier / base_brier,
            "part 2 RMSE (log10 $)": np.sqrt(np.mean(resid ** 2))}


def year_bootstrap(df, preds, a, b, base_p):
    """Differences b - a in AUC and Brier skill, resampling whole test years."""
    years = df["year"].to_numpy()
    uniq = np.unique(years)
    idx_by_year = {yr: np.where(years == yr)[0] for yr in uniq}
    y = df["has_damage"].to_numpy()
    d_auc, d_bs = [], []
    for _ in range(N_BOOT):
        idx = np.concatenate([idx_by_year[yr] for yr in RNG.choice(uniq, len(uniq))])
        yy = y[idx]
        if yy.sum() == 0 or yy.sum() == len(yy):
            continue
        bb = np.mean((base_p[idx] - yy) ** 2)
        d_auc.append(auc(yy, preds[b]["p"][idx]) - auc(yy, preds[a]["p"][idx]))
        d_bs.append((np.mean((preds[a]["p"][idx] - yy) ** 2) - np.mean((preds[b]["p"][idx] - yy) ** 2)) / bb)
    q = lambda v: np.percentile(v, [2.5, 97.5])
    return np.mean(np.array(d_auc) > 0), q(d_auc), q(d_bs)


def print_table(title, table):
    print(f"\n{title}")
    print(pd.DataFrame(table).T.round(3).to_string())


# ---------------------------------------------------------------
# 1. Washington County alone
# ---------------------------------------------------------------
focus = add_features(pd.read_csv(os.path.join(DATA, "focus_panel_39167.csv"), dtype={"GEOID": str}))
focus = add_features(focus, "nb_")
train, test = focus[focus.split == "train"].reset_index(drop=True), focus[focus.split == "test"].reset_index(drop=True)
print(f"Washington: train 2010-2018 {len(train)} months ({train.has_damage.sum()} damaged), "
      f"test 2019-2023 {len(test)} months ({test.has_damage.sum()} damaged)")

corr = {c: focus[c].corr(focus["nb_" + c]) for c in HAZARD}
print("correlation own vs neighbour hazard:", {k: round(v, 2) for k, v in corr.items()})

MODELS = {"own hazard": SEASON + HAZARD,
          "own + neighbour hazard": SEASON + HAZARD + NB,
          "neighbour hazard only": SEASON + NB}
base = climatology(train, test)
preds, table, coefs = {"climatology": base}, {}, []
table["climatology (month rate)"] = scores(test, base, base["p"])
for name, cols in MODELS.items():
    preds[name] = hurdle(train, test, cols)
    table[name] = scores(test, preds[name], base["p"]) | {"ridge (p1, p2)": str(preds[name]["ridge"])}
    for part in ("b1", "b2"):
        coefs.append(preds[name][part].rename(f"{name} | part {part[1]}"))
print_table("Washington test scores (2019-2023)", table)

share, ci_auc, ci_bs = year_bootstrap(test, preds, "own hazard", "own + neighbour hazard", base["p"])
print(f"\nadding neighbour hazard, bootstrap over test years ({N_BOOT} draws):")
print(f"  AUC change 95% interval [{ci_auc[0]:+.3f}, {ci_auc[1]:+.3f}], share of draws improved {share:.0%}")
print(f"  Brier skill change 95% interval [{ci_bs[0]:+.3f}, {ci_bs[1]:+.3f}]")

# robustness: leave one year out over all 14 years
loyo = {name: np.empty(len(focus)) for name in ["climatology"] + list(MODELS)}
for yr in sorted(focus.year.unique()):
    fit, held = focus[focus.year != yr], focus[focus.year == yr]
    i = held.index.to_numpy()
    loyo["climatology"][i] = climatology(fit, held)["p"]
    for name, cols in MODELS.items():
        loyo[name][i] = hurdle(fit, held, cols, ridges=preds[name]["ridge"])["p"]
print("\nleave-one-year-out over 2010-2023 (robustness, not a forecast):")
for name, p in loyo.items():
    y = focus["has_damage"]
    print(f"  {name:28s} AUC {auc(y, p):.3f}  PR-AUC {avg_precision(y, p):.3f}  "
          f"Brier skill {1 - np.mean((p - y) ** 2) / np.mean((loyo['climatology'] - y) ** 2):+.3f}")

# ---------------------------------------------------------------
# 2. pooled: all five counties as rows
# ---------------------------------------------------------------
panel = add_features(pd.read_csv(os.path.join(DATA, "county_set_panel.csv"), dtype={"GEOID": str}))
land = panel.groupby("GEOID")["land_km2"].first()
key = panel.set_index(["GEOID", "year", "month"])[RAW]
nb_rows = []
for g, nbs in BORDERS.items():
    w = land[nbs] / land[nbs].sum()
    parts = [key.xs(n, level="GEOID") * w[n] for n in nbs]
    m = sum(parts).add_prefix("nb_").reset_index()
    m["GEOID"] = g
    nb_rows.append(m)
panel = panel.merge(pd.concat(nb_rows), on=["GEOID", "year", "month"])
panel = add_features(panel, "nb_").sort_values(["GEOID", "year", "month"]).reset_index(drop=True)
CTY = [f"cty_{g}" for g in sorted(BORDERS)[1:]]
for g in sorted(BORDERS)[1:]:
    panel[f"cty_{g}"] = (panel.GEOID == g).astype(float)

ptrain, ptest = panel[panel.split == "train"].reset_index(drop=True), panel[panel.split == "test"].reset_index(drop=True)
print(f"\npooled 5 counties: train {len(ptrain)} rows ({ptrain.has_damage.sum()} damaged), "
      f"test {len(ptest)} rows ({ptest.has_damage.sum()} damaged)")
pbase = climatology(ptrain, ptest, group=("GEOID", "month"))
ppreds, ptable = {"climatology": pbase}, {"climatology (county x month rate)": scores(ptest, pbase, pbase["p"])}
POOLED = {"own hazard": (SEASON + HAZARD, CTY), "own + neighbour hazard": (SEASON + HAZARD + NB, CTY)}
# exposure (GHSL population, run build_county_panel.py with --ghsl) + floodplain share in place
# of the county indicators: does the setting explain why counties differ? Exposure barely
# changes within a county, and 5 counties support at most ~2 county-level inputs.
EXPOSURE = ["log_population", "hand_lt5_share"]
if all(c in panel for c in EXPOSURE):
    POOLED["own hazard + exposure (no county indicators)"] = (SEASON + HAZARD + EXPOSURE, ())
    POOLED["own hazard, no county indicators"] = (SEASON + HAZARD, ())
for name, (cols, dummies) in POOLED.items():
    ppreds[name] = hurdle(ptrain, ptest, cols, dummies)
    ptable[name] = scores(ptest, ppreds[name], pbase["p"]) | {"ridge (p1, p2)": str(ppreds[name]["ridge"])}
    for part in ("b1", "b2"):
        coefs.append(ppreds[name][part].rename(f"pooled {name} | part {part[1]}"))
print_table("pooled test scores (2019-2023)", ptable)
for g, name in panel.groupby("GEOID")["county"].first().items():
    i = (ptest.GEOID == g).to_numpy()
    y = ptest.has_damage[i]
    print(f"  {name:11s} test damage months {y.sum():2d}  AUC own {auc(y, ppreds['own hazard']['p'][i]):.3f}"
          f"  own+nb {auc(y, ppreds['own + neighbour hazard']['p'][i]):.3f}")
share, ci_auc, ci_bs = year_bootstrap(ptest, ppreds, "own hazard", "own + neighbour hazard", pbase["p"])
print(f"  adding neighbour hazard: AUC change [{ci_auc[0]:+.3f}, {ci_auc[1]:+.3f}] ({share:.0%} of draws improved), "
      f"Brier skill change [{ci_bs[0]:+.3f}, {ci_bs[1]:+.3f}]")

# ---------------------------------------------------------------
# 3. outputs
# ---------------------------------------------------------------
os.makedirs(OUT, exist_ok=True)
out = pd.concat([pd.DataFrame(table).T.assign(model_set="Washington"),
                 pd.DataFrame(ptable).T.assign(model_set="pooled 5 counties")])
out.index.name = "model"
out.to_csv(os.path.join(OUT, "neighbour_scores.csv"), float_format="%.4f")
pd.concat(coefs, axis=1).to_csv(os.path.join(OUT, "neighbour_coefs.csv"), float_format="%.4f")

# predictions for the app: model fitted on 2010-2018, applied to every month
best = "own + neighbour hazard"
allp = hurdle(ptrain, panel, SEASON + HAZARD + NB, CTY, ridges=ppreds[best]["ridge"])
pred = panel[["GEOID", "county", "year", "month", "split", "PropertyDmgADJ", "has_damage"]].copy()
pred["p_damage"] = allp["p"]
pred["expected_dmg"] = allp["expected"]
pred["model"] = best
pred.to_csv(os.path.join(OUT, "predictions_5county.csv"), index=False, float_format="%.5g")
print(f"\nwrote {OUT}: neighbour_scores.csv, neighbour_coefs.csv, predictions_5county.csv ({len(pred)} rows)")
