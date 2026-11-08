"""
Reduced refit: GLM hurdle and LightGBM hurdle on the 12 reduced inputs plus calendar month,
and state when more than one state is fitted, against a simple county-rate baseline.

  part 1  P(damage > 0)                 ridge logistic / LightGBM classifier, every county-month
  part 2  log10 damage | damage > 0     ridge linear / LightGBM regressor, damage months only
  expected loss = P(damage) x E[damage | damage], with a smearing correction

Design (data_route_plan_summary.pdf, recommended Route 2):
  * Train 2000-2016, test 2017-2023. Ridge strengths and tree counts are chosen on
    2000-2012 -> 2013-2016 only.
  * Validation (2013-2016) scores are printed first. Those years also chose the settings, so
    they run slightly high. Compare designs on them, not on the test years.
  * --state fits that state's counties only, with the same model settings. State is then
    constant, so it drops out of both models.

Input : model_panel.csv, the PRISM panel from yana_workspace/temp_merge_panel.py
Output, in --out-dir:
        scores.csv     validation and test scores
        glm_coefs.csv  GLM coefficients per 1 std of each input
        log.txt        everything printed here

OpenFEMA placeholder: --openfema adds nfip_policies_per_hu and buyouts_cum. Off by default.
See data/openfema/README.md for how to supply them.

Usage:
    pip install lightgbm scikit-learn
    python reduced_benchmark.py --out-dir results/midwest_prism
    python reduced_benchmark.py --state MO --out-dir results/missouri_prism
    python reduced_benchmark.py --panel model_panel_noaa.csv --exposure log_housing_units --out-dir <folder>
"""

import argparse
import os
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd

TARGET = "log_PropertyDmgADJ"
STATES = {"17": "IL", "18": "IN", "19": "IA", "20": "KS", "26": "MI", "27": "MN",
          "29": "MO", "31": "NE", "38": "ND", "39": "OH", "46": "SD", "55": "WI"}
RIDGE_GRID = [0.1, 1, 10, 100, 1000]
TOP_SHARE = 0.05             # ranking: the top 5% of counties each month (53 of 1,055)
N_BOOT = 200
SEED = 472

# the same 12 inputs in both models; the GLM logs the skewed amounts, trees do not need it
DEFAULT_EXPOSURE = "log_built_surface"
GLM_INPUTS = ["log_p_month", "rx5_rl_ratio", "log_snowmelt_mm", "frost_days",
              "sm_root_pct", "log_swe_mm", "c_rx5_rl10_mm", DEFAULT_EXPOSURE,
              "impervious_mean", "hand_lt5_share", "log_land_km2", "wetland_share"]
TREE_INPUTS = ["p_month", "rx5_rl_ratio", "snowmelt_mm", "frost_days",
               "sm_root_pct", "swe_mm", "c_rx5_rl10_mm", DEFAULT_EXPOSURE,
               "impervious_mean", "hand_lt5_share", "log_land_km2", "wetland_share",
               "month", "state_code"]
# from merge_panel.py once data/clean/ holds the OpenFEMA tables (both already year - 1)
OPENFEMA_INPUTS = ["nfip_policies_per_hu", "buyouts_cum"]

LGB_BASE = dict(learning_rate=0.03, num_leaves=31, min_child_samples=100, subsample=0.8,
                subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, n_estimators=3000,
                random_state=SEED, verbose=-1)


class Tee:
    """Print to the screen and to the run log."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, text):
        for s in self.streams:
            s.write(text)

    def flush(self):
        for s in self.streams:
            s.flush()


def load(path, use_openfema, state, exposure):
    data = pd.read_csv(path, dtype={"GEOID": str})
    data["state"] = data["GEOID"].str[:2].map(STATES)
    if state:
        if state not in STATES.values():
            raise SystemExit(f"--state {state}: use one of {sorted(STATES.values())}")
        data = data[data["state"] == state].reset_index(drop=True)
    for col in ["p_month", "swe_mm", "snowmelt_mm"]:
        data["log_" + col] = np.log1p(data[col].clip(lower=0))
    data["log_land_km2"] = np.log(data["land_km2"])
    data["state_code"] = data["state"].astype("category").cat.codes
    glm = [exposure if c == DEFAULT_EXPOSURE else c for c in GLM_INPUTS]
    tree = [exposure if c == DEFAULT_EXPOSURE else c for c in TREE_INPUTS]
    if state:
        tree.remove("state_code")
    if use_openfema:
        absent = [c for c in OPENFEMA_INPUTS if c not in data]
        if absent:
            raise SystemExit(f"--openfema: {absent} not in {path}. Rebuild the panel with "
                             "merge_panel.py after adding the data/clean/ tables.")
        glm += OPENFEMA_INPUTS
        tree += OPENFEMA_INPUTS
    # the GLM cannot take missing values, and filling them is a choice for the team to make
    # (a county with no buyouts is a zero; a year before NFIP records begin is unknown)
    missing = data[sorted(set(glm + tree))].isna()
    if missing.any().any():
        by_year = missing.groupby(data["year"]).mean()
        by_year = by_year.loc[:, by_year.max() > 0].round(3)
        raise SystemExit(f"missing input values, share of rows by year:\n{by_year.to_string()}")
    return data, glm, tree


# ---------------------------------------------------------------
# models (same formulas as hurdle_model.py and model_comparison.py)
# ---------------------------------------------------------------
def design(df, ref, inputs):
    X = (df[inputs] - ref[inputs].mean()) / ref[inputs].std()
    X = pd.concat([X, pd.get_dummies(df["month"], prefix="m", dtype=float)
                   .reindex(columns=[f"m_{m}" for m in range(2, 13)], fill_value=0.0),
                   pd.get_dummies(df["state"], prefix="st", dtype=float)
                   .reindex(columns=[f"st_{s}" for s in sorted(ref["state"].unique())[1:]], fill_value=0.0)],
                  axis=1)
    X["const"] = 1.0
    return X


def penalty(X, ridge):
    return np.diag([1e-6 if c == "const" or c.startswith(("m_", "st_")) else ridge for c in X.columns])


def glm_hurdle(fit_df, score_df, inputs, ridge1, ridge2):
    X, y = design(fit_df, fit_df, inputs), fit_df["has_damage"].to_numpy()
    A, L = X.to_numpy(), penalty(X, ridge1)
    b1 = np.zeros(A.shape[1])
    b1[-1] = np.log(y.mean() / (1 - y.mean()))
    for _ in range(30):
        p = 1 / (1 + np.exp(-(A @ b1)))
        step = np.linalg.solve(A.T @ (A * (p * (1 - p))[:, None]) + L, A.T @ (y - p) - L @ b1)
        b1 += step
        if np.abs(step).max() < 1e-8:
            break
    pos = fit_df[fit_df["has_damage"] == 1]
    Ap = design(pos, fit_df, inputs).to_numpy()
    b2 = np.linalg.solve(Ap.T @ Ap + penalty(X, ridge2), Ap.T @ pos[TARGET].to_numpy())
    smear = np.mean(10 ** (pos[TARGET].to_numpy() - Ap @ b2))
    S = design(score_df, fit_df, inputs).to_numpy()
    p, mu = 1 / (1 + np.exp(-(S @ b1))), S @ b2
    return p, mu, p * 10 ** mu * smear, pd.Series(b1, index=X.columns), pd.Series(b2, index=X.columns)


def climatology(fit_df, score_df, prior=2.0):
    """Each county's damage rate for that calendar month, shrunk toward its state's rate."""
    rate = fit_df.groupby(["GEOID", "month"])["has_damage"].agg(["sum", "count"])
    state_rate = fit_df.groupby(["state", "month"])["has_damage"].mean().rename("state_rate")
    pos = fit_df[fit_df["has_damage"] == 1]
    sev = pos.groupby("GEOID")[TARGET].mean().rename("sev")
    df = (score_df[["GEOID", "state", "month"]]
          .join(rate, on=["GEOID", "month"]).join(state_rate, on=["state", "month"]).join(sev, on="GEOID"))
    p = ((df["sum"] + prior * df["state_rate"]) / (df["count"] + prior)).to_numpy()
    mu = df["sev"].fillna(pos[TARGET].mean()).to_numpy()
    return p, mu, p * 10 ** mu


def lgb_hurdle(fit_df, score_df, inputs, rounds=None, valid_df=None):
    """With valid_df: early-stop on it and return its tree counts. With rounds: fixed tree counts."""
    pos = fit_df[fit_df["has_damage"] == 1]
    if rounds is None:
        vpos = valid_df[valid_df["has_damage"] == 1]
        clf = lgb.LGBMClassifier(**LGB_BASE, metric="binary_logloss")
        clf.fit(fit_df[inputs], fit_df["has_damage"], eval_set=[(valid_df[inputs], valid_df["has_damage"])],
                callbacks=[lgb.early_stopping(100, verbose=False)])
        reg = lgb.LGBMRegressor(**LGB_BASE, metric="l1")
        reg.fit(pos[inputs], pos[TARGET], eval_set=[(vpos[inputs], vpos[TARGET])],
                callbacks=[lgb.early_stopping(100, verbose=False)])
        rounds = (clf.best_iteration_, reg.best_iteration_)
    else:
        clf = lgb.LGBMClassifier(**{**LGB_BASE, "n_estimators": rounds[0]})
        clf.fit(fit_df[inputs], fit_df["has_damage"])
        reg = lgb.LGBMRegressor(**{**LGB_BASE, "n_estimators": rounds[1]})
        reg.fit(pos[inputs], pos[TARGET])
    smear = np.mean(10 ** (pos[TARGET].to_numpy() - reg.predict(pos[inputs])))
    p, mu = clf.predict_proba(score_df[inputs])[:, 1], reg.predict(score_df[inputs])
    return p, mu, p * 10 ** mu * smear, rounds, clf


# ---------------------------------------------------------------
# scores (same definitions as hurdle_model.py)
# ---------------------------------------------------------------
def auc(y, s):
    r = pd.Series(s).rank().to_numpy()
    n1 = y.sum()
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * (len(y) - n1))


def avg_precision(y, s):
    order = np.argsort(-s, kind="mergesort")
    hits = y[order]
    return (np.cumsum(hits) / np.arange(1, len(y) + 1))[hits == 1].mean()


def scores(df, p, mu, expected, base_brier):
    y = df["has_damage"].to_numpy()
    pc = np.clip(p, 1e-9, 1 - 1e-9)
    brier = np.mean((pc - y) ** 2)
    out = {"ROC-AUC": auc(y, p), "PR-AUC": avg_precision(y, p), "Brier skill": 1 - brier / base_brier,
           "log loss": -np.mean(y * np.log(pc) + (1 - y) * np.log(1 - pc)),
           "mean P / rate": pc.mean() / y.mean()}
    d = df.assign(p=p, e=expected)
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
    out["top 5%: without largest month"] = rest["caught"].sum() / rest["total"].sum()
    out["top 5%: median month"] = (month["caught"] / month["total"]).median()
    yr = d.groupby(["year", "GEOID"])[["e", "PropertyDmgADJ"]].sum()
    out["rank corr, year"] = np.mean([g["e"].corr(g["PropertyDmgADJ"], method="spearman")
                                      for _, g in yr.groupby(level="year")])
    damaged = y == 1
    out["MAE, damaged"] = np.abs(df[TARGET].to_numpy()[damaged] - mu[damaged]).mean()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="model_panel.csv")
    ap.add_argument("--state", help="fit one state's counties only, e.g. MO")
    ap.add_argument("--exposure", default=DEFAULT_EXPOSURE, choices=[DEFAULT_EXPOSURE, "log_housing_units"])
    ap.add_argument("--openfema", action="store_true", help="add the OpenFEMA inputs")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    log_file = open(os.path.join(args.out_dir, "log.txt"), "w", encoding="utf-8")
    sys.stdout = Tee(sys.__stdout__, log_file)
    pd.set_option("display.width", 220)

    data, glm_inputs, tree_inputs = load(args.panel, args.openfema, args.state, args.exposure)
    train = data[data["split"] == "train"].reset_index(drop=True)
    test = data[data["split"] == "test"].reset_index(drop=True)
    fit_part = train[train["year"] <= 2012].reset_index(drop=True)
    valid_part = train[train["year"] >= 2013].reset_index(drop=True)
    print(f"panel: {args.panel}, state: {args.state or 'all'}, {data['GEOID'].nunique()} counties, "
          f"exposure: {args.exposure}, OpenFEMA inputs: {args.openfema}")
    for name, d in [("train", train), ("  fit", fit_part), ("  validation", valid_part), ("test", test)]:
        print(f"{name}: {d['year'].min()}-{d['year'].max()}, {len(d):,} county-months, "
              f"{int(d['has_damage'].sum()):,} damage months ({d['has_damage'].mean():.2%})")

    # ------ settings, from 2000-2012 -> 2013-2016 only ------
    vy, vpos = valid_part["has_damage"].to_numpy(), (valid_part["has_damage"] == 1).to_numpy()
    rows = []
    for lam in RIDGE_GRID:
        p, mu, _, _, _ = glm_hurdle(fit_part, valid_part, glm_inputs, lam, lam)
        pc = np.clip(p, 1e-9, 1 - 1e-9)
        rows.append({"ridge": lam, "log loss": -np.mean(vy * np.log(pc) + (1 - vy) * np.log(1 - pc)),
                     "MAE, damaged": np.abs(valid_part[TARGET].to_numpy()[vpos] - mu[vpos]).mean()})
    grid = pd.DataFrame(rows).set_index("ridge")
    ridge1, ridge2 = grid["log loss"].idxmin(), grid["MAE, damaged"].idxmin()
    print(f"\nGLM ridge search on 2013-2016:\n{grid.round(4).to_string()}")
    print(f"chosen: part 1 ridge {ridge1}, part 2 ridge {ridge2}")

    table = {}

    # ------ validation: compare designs here ------
    base = climatology(fit_part, valid_part)
    brier = np.mean((base[0] - vy) ** 2)
    table[("validation 2013-2016", "baseline: county rate")] = scores(valid_part, *base, brier)
    p, mu, e, _, _ = glm_hurdle(fit_part, valid_part, glm_inputs, ridge1, ridge2)
    table[("validation 2013-2016", "GLM hurdle")] = scores(valid_part, p, mu, e, brier)
    p, mu, e, rounds, _ = lgb_hurdle(fit_part, valid_part, tree_inputs, valid_df=valid_part)
    table[("validation 2013-2016", "LightGBM hurdle")] = scores(valid_part, p, mu, e, brier)
    print(f"LightGBM trees chosen on 2013-2016: part 1 {rounds[0]}, part 2 {rounds[1]}")

    # ------ final fits on 2000-2016, scored on 2017-2023 ------
    yt = test["has_damage"].to_numpy()
    base = climatology(train, test)
    brier = np.mean((base[0] - yt) ** 2)
    table[("test 2017-2023", "baseline: county rate")] = scores(test, *base, brier)
    p_g, mu, e, b1, b2 = glm_hurdle(train, test, glm_inputs, ridge1, ridge2)
    table[("test 2017-2023", "GLM hurdle")] = scores(test, p_g, mu, e, brier)
    print("GLM refit done")
    # 15% more trees because the refit has more data, as in model_comparison.py
    final_rounds = (int(rounds[0] * 1.15), int(rounds[1] * 1.15))
    p_l, mu, e, _, clf = lgb_hurdle(train, test, tree_inputs, rounds=final_rounds)
    table[("test 2017-2023", "LightGBM hurdle")] = scores(test, p_l, mu, e, brier)
    print(f"LightGBM refit done ({final_rounds[0]} and {final_rounds[1]} trees)")

    table = pd.DataFrame(table).T
    table.index.names = ["period", "model"]
    print("\n" + table[["ROC-AUC", "PR-AUC", "Brier skill", "mean P / rate", "AUC within month"]].round(3).to_string())
    print("\n" + table[["top 5%: share of loss", "top 5%: without largest month", "top 5%: median month",
                        "rank corr, year", "MAE, damaged"]].round(3).to_string())
    table.round(4).to_csv(os.path.join(args.out_dir, "scores.csv"))

    # ------ county bootstrap of test ROC-AUC differences; predictions held fixed ------
    preds = {"LightGBM": p_l, "GLM": p_g, "baseline": base[0]}
    rng = np.random.default_rng(SEED)
    rows = test.groupby("GEOID").indices
    ids = np.array(list(rows))
    pairs = [("LightGBM", "GLM"), ("LightGBM", "baseline"), ("GLM", "baseline")]
    draws = {pair: [] for pair in pairs}
    for _ in range(N_BOOT):
        idx = np.concatenate([rows[g] for g in rng.choice(ids, len(ids))])
        for a, b in pairs:
            draws[(a, b)].append(auc(yt[idx], preds[a][idx]) - auc(yt[idx], preds[b][idx]))
    print(f"\ntest ROC-AUC differences, 95% interval from {N_BOOT} county bootstrap samples:")
    for (a, b), d in draws.items():
        lo, hi = np.percentile(d, [2.5, 97.5])
        print(f"  {a:9s} vs {b:9s} {auc(yt, preds[a]) - auc(yt, preds[b]):+.4f}  ({lo:+.4f} to {hi:+.4f})")

    # ------ what the models rely on ------
    coefs = pd.DataFrame({"part 1 (log-odds of damage)": b1[glm_inputs], "part 2 (log10 dollars)": b2[glm_inputs]})
    print("\nGLM coefficients, per 1 std of each input:\n" + coefs.round(3).to_string())
    coefs.round(4).to_csv(os.path.join(args.out_dir, "glm_coefs.csv"))
    imp = pd.Series(clf.booster_.feature_importance("gain"), index=tree_inputs)
    print("\nLightGBM part 1, share of total gain:\n" + (imp / imp.sum()).sort_values(ascending=False).round(3).to_string())


if __name__ == "__main__":
    main()
