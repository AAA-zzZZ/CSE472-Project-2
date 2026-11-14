"""
Loss classes instead of dollar amounts: the second part of the hurdle predicts which order of
magnitude the loss falls in, not how many dollars.

  class 0  no damage            (part 1, unchanged from reduced_benchmark.py)
  class 1  minor     under $10k
  class 2  moderate  $10k to $100k
  class 3  major     $100k to $1M
  class 4  severe    $1M or more

  part 1  P(damage > 0)              ridge logistic / LightGBM classifier (as reduced_benchmark.py)
  part 2  P(class k | damage > 0)    ridge ordinal logistic / LightGBM multiclass, damage months only
  P(class 0) = 1 - P(damage);  P(class k) = P(damage) x P(class k | damage)

Why powers of ten: the models work on log10 dollars, so each class is one unit on that scale; the
dollar model's test error (MAE 0.83 in log10, about a factor of 7) means narrower classes would
claim more precision than the model has; and the labels need no explanation. Above $10M there are
only about 250 damage months in 2000-2023, too few for a class of their own.
Amounts are SHELDUS PropertyDmgADJ (inflation-adjusted, 2024 dollars).

Same design as reduced_benchmark.py: train 2000-2016, test 2017-2023, settings (ridge strengths,
tree counts) chosen on 2000-2012 -> 2013-2016 only. Also scored, for comparison:
  * baseline: the county damage rate x the county's class shares, shrunk toward the state's
  * "binned dollars": the existing log10-dollar regressions of reduced_benchmark.py, cut at the
    same class edges (a hard class only, no probabilities)

Ranking: counties are ranked each month by the chance of a severe loss,
P(class 4) = P(damage) x P(loss >= $1M | damage). Chosen on 2013-2016 among three dollar-free
scores (RANK_SCORES: P(severe), P(major or worse), expected class); the dollar ranking of
reduced_benchmark.py is shown next to it.

Output, in --out-dir:
    scores.csv           part 1, part 2 (damage months), all-row and ranking scores
    confusion_test.csv   test-year confusion matrices of part 2 (damage months)
    glm_ordinal_coefs.csv  ordinal GLM coefficients, per 1 std of each input
    class_counts.csv     damage months per class and period
    log.txt              everything printed here

Usage:
    pip install lightgbm scikit-learn scipy
    python loss_class_model.py --out-dir results/loss_classes_midwest
    python loss_class_model.py --state MO --out-dir results/loss_classes_missouri
"""

import argparse
import os
import sys

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit
from sklearn.metrics import cohen_kappa_score

import reduced_benchmark as rb

EDGES = [1e4, 1e5, 1e6]      # class edges in dollars; class k covers [EDGES[k-2], EDGES[k-1])
CLASSES = [0, 1, 2, 3, 4]
NAMES = ["none", "minor", "moderate", "major", "severe"]
LABELS = ["No damage", "Under $10k", "$10k to $100k", "$100k to $1M", "$1M or more"]
MAJOR = 3                    # "major or worse" = class 3 or 4, loss of $100k or more


def loss_class(df):
    """0 for no damage, else 1-4 by order of magnitude of the recorded loss."""
    c = np.digitize(df["PropertyDmgADJ"].to_numpy(), EDGES) + 1
    return np.where(df["has_damage"].to_numpy() == 1, c, 0)


# ---------------------------------------------------------------
# part 2 models: P(class | damage), classes 1-4 (columns 0-3 of q)
# ---------------------------------------------------------------
def ordinal_fit(X, y, pen):
    """Proportional-odds logistic with a ridge penalty. y in 0..K-1. P(Y <= k) = sigmoid(t_k - X b).
    Thresholds are kept in order by fitting the first one and log gaps to the next."""
    n, m = X.shape
    K = int(y.max()) + 1
    rows = np.arange(n)

    def unpack(w):
        return w[:m], np.cumsum(np.r_[w[m], np.exp(w[m + 1:])])

    def objective(w):
        b, t = unpack(w)
        eta = X @ b
        up = np.r_[t, np.inf][y] - eta            # upper edge of each row's class
        lo = np.r_[-np.inf, t][y] - eta           # lower edge
        Fu, Fl = expit(up), expit(lo)
        fu, fl = Fu * (1 - Fu), Fl * (1 - Fl)
        prob = np.clip(Fu - Fl, 1e-12, None)
        nll = -np.log(prob).sum() + 0.5 * (pen * b * b).sum()
        g_eta = (fu - fl) / prob                  # d nll / d eta
        g_b = X.T @ g_eta + pen * b
        g_t = np.zeros(K - 1)                     # d nll / d threshold
        np.add.at(g_t, y[y < K - 1], -(fu / prob)[y < K - 1])
        np.add.at(g_t, y[y > 0] - 1, (fl / prob)[y > 0])
        # thresholds -> free parameters: t_j = w0 + sum_{i<=j} exp(w_i)
        g_w = np.r_[g_t.sum(), [np.exp(w[m + i]) * g_t[i:].sum() for i in range(1, K - 1)]]
        return nll, np.r_[g_b, g_w]

    share = np.cumsum(np.bincount(y, minlength=K))[:-1] / n
    t0 = np.log(share / (1 - share))
    w0 = np.r_[np.zeros(m), t0[0], np.log(np.diff(t0))]
    res = minimize(objective, w0, jac=True, method="L-BFGS-B", options={"maxiter": 2000})
    return unpack(res.x)


def ordinal_predict(X, b, t):
    cum = expit(t[None, :] - (X @ b)[:, None])
    cum = np.hstack([np.zeros((len(X), 1)), cum, np.ones((len(X), 1))])
    return np.diff(cum, axis=1)


def glm_classes(fit_df, score_df, inputs, ridge):
    """Ordinal GLM on damage months. Same standardised design as reduced_benchmark.design(),
    without the constant (the thresholds take its place); month and state are barely penalised."""
    pos = fit_df[fit_df["has_damage"] == 1]
    X = rb.design(pos, fit_df, inputs).drop(columns="const")
    pen = np.array([1e-6 if c.startswith(("m_", "st_")) else ridge for c in X.columns])
    b, t = ordinal_fit(X.to_numpy(), loss_class(pos) - 1, pen)
    S = rb.design(score_df, fit_df, inputs).drop(columns="const").to_numpy()
    return ordinal_predict(S, b, t), pd.Series(b, index=X.columns), t


def lgb_classes(fit_df, score_df, inputs, rounds=None, valid_df=None):
    """LightGBM multiclass on damage months. With valid_df: early-stop on its damage months and
    return the tree count. With rounds: a fixed tree count."""
    pos = fit_df[fit_df["has_damage"] == 1]
    params = {**rb.LGB_BASE, "objective": "multiclass", "num_class": 4}
    if rounds is None:
        vpos = valid_df[valid_df["has_damage"] == 1]
        clf = lgb.LGBMClassifier(**params, metric="multi_logloss")
        clf.fit(pos[inputs], loss_class(pos) - 1, eval_set=[(vpos[inputs], loss_class(vpos) - 1)],
                callbacks=[lgb.early_stopping(100, verbose=False)])
        rounds = clf.best_iteration_
    else:
        clf = lgb.LGBMClassifier(**{**params, "n_estimators": rounds})
        clf.fit(pos[inputs], loss_class(pos) - 1)
    return clf.predict_proba(score_df[inputs]), rounds


def baseline_classes(fit_df, score_df, prior=2.0):
    """The county's share of damage months in each class, shrunk toward its state's shares."""
    pos = fit_df[fit_df["has_damage"] == 1].assign(c=lambda d: loss_class(d))
    county = pd.crosstab(pos["GEOID"], pos["c"]).reindex(columns=[1, 2, 3, 4], fill_value=0)
    state = pd.crosstab(pos["state"], pos["c"]).reindex(columns=[1, 2, 3, 4], fill_value=0)
    state = state.div(state.sum(axis=1), axis=0)
    s = state.reindex(score_df["state"]).to_numpy()
    c = county.reindex(score_df["GEOID"]).fillna(0).to_numpy()
    return (c + prior * s) / (c.sum(axis=1, keepdims=True) + prior)


def binned(mu):
    """A log10(dollars + 1) prediction cut at the class edges: classes 1-4."""
    return np.digitize(10 ** mu - 1, EDGES) + 1


# ---------------------------------------------------------------
# scores
# ---------------------------------------------------------------
def full_probs(p, q):
    """5-class probabilities (0-4) from P(damage) and P(class | damage)."""
    return np.hstack([(1 - p)[:, None], p[:, None] * q])


RANK_SCORES = {
    "P(major or worse)": lambda P: P[:, MAJOR:].sum(axis=1),
    "P(severe)": lambda P: P[:, 4],
    "expected class": lambda P: P @ np.arange(5),
}
# chosen on 2013-2016 by the top-5% share of loss: LightGBM 0.718 (P(severe)) vs 0.584 and 0.585,
# GLM 0.742 vs 0.633 and 0.573 (ranking_options.csv)
RANK_SCORE = "P(severe)"


def class_scores(df, q=None, hard=None):
    """Part 2 on damage months: q = P(class | damage) (n x 4), or hard = predicted class 1-4."""
    d = (df["has_damage"] == 1).to_numpy()
    y = loss_class(df)[d]
    out = {"damage months": int(d.sum())}
    if q is not None:
        qd = np.clip(q[d], 1e-12, 1)
        out["class log loss"] = -np.mean(np.log(qd[np.arange(len(y)), y - 1]))
        cum, obs = np.cumsum(qd, axis=1)[:, :-1], (y[:, None] <= np.arange(1, 4)).astype(float)
        out["RPS, damaged"] = np.mean(((cum - obs) ** 2).sum(axis=1)) / 3
        hard = q.argmax(axis=1) + 1
    h = hard[d]
    out["accuracy"] = np.mean(h == y)
    out["within one class"] = np.mean(np.abs(h - y) <= 1)
    out["MAE, classes"] = np.mean(np.abs(h - y))
    out["weighted kappa"] = cohen_kappa_score(y, h, weights="quadratic")
    return out


def all_row_scores(df, P, base_rps=None):
    """Ranked probability score of the 5-class forecast on every county-month, and the ranking."""
    y = loss_class(df)
    cum = np.cumsum(P, axis=1)[:, :-1]
    obs = (y[:, None] <= np.arange(4)).astype(float)
    rps = np.mean(((cum - obs) ** 2).sum(axis=1)) / 4
    out = {"RPS, all rows": rps}
    if base_rps is not None:
        out["RPS skill"] = 1 - rps / base_rps
    out.update(ranking(df, RANK_SCORES[RANK_SCORE](P)))
    return out


def ranking(df, score):
    """Top 5% of counties each month by a risk score: share of recorded loss and of major+ months caught."""
    d = df.assign(s=score, major=(loss_class(df) >= MAJOR).astype(int))
    k = int(round(rb.TOP_SHARE * d["GEOID"].nunique()))
    month = d.groupby(["year", "month"]).apply(
        lambda g: pd.Series({"caught": g.nlargest(k, "s")["PropertyDmgADJ"].sum(),
                             "total": g["PropertyDmgADJ"].sum(),
                             "major caught": g.nlargest(k, "s")["major"].sum(),
                             "major": g["major"].sum()}), include_groups=False)
    month = month[month["total"] > 0]
    rest = month.drop(month["total"].idxmax())
    return {"top 5%: share of loss": month["caught"].sum() / month["total"].sum(),
            "top 5%: without largest month": rest["caught"].sum() / rest["total"].sum(),
            "top 5%: major+ months caught": month["major caught"].sum() / month["major"].sum()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="model_panel.csv")
    ap.add_argument("--state", help="fit one state's counties only, e.g. MO")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    log_file = open(os.path.join(args.out_dir, "log.txt"), "w", encoding="utf-8")
    sys.stdout = rb.Tee(sys.__stdout__, log_file)
    pd.set_option("display.width", 220)

    data, glm_inputs, tree_inputs = rb.load(args.panel, [], args.state, rb.DEFAULT_EXPOSURE)
    train = data[data["split"] == "train"].reset_index(drop=True)
    test = data[data["split"] == "test"].reset_index(drop=True)
    fit = train[train["year"] <= 2012].reset_index(drop=True)
    valid = train[train["year"] >= 2013].reset_index(drop=True)
    print(f"panel: {args.panel}, state: {args.state or 'all'}, {data['GEOID'].nunique()} counties")
    print("class edges: " + ", ".join(f"{n} = {l}" for n, l in zip(NAMES, LABELS)))

    period = np.where(data["year"] <= 2012, "fit 2000-2012",
                      np.where(data["year"] <= 2016, "validation 2013-2016", "test 2017-2023"))
    counts = pd.crosstab(period, loss_class(data)).rename(columns=dict(enumerate(NAMES)))
    counts = counts.loc[["fit 2000-2012", "validation 2013-2016", "test 2017-2023"]]
    print("\ncounty-months per class:\n" + counts.to_string())
    print("\nshare of damage months per class:\n"
          + counts.iloc[:, 1:].div(counts.iloc[:, 1:].sum(axis=1), axis=0).round(3).to_string())
    counts.to_csv(os.path.join(args.out_dir, "class_counts.csv"))

    # ------ settings, from 2000-2012 -> 2013-2016 only ------
    vd = (valid["has_damage"] == 1).to_numpy()
    rows = []
    for lam in rb.RIDGE_GRID:
        q, _, _ = glm_classes(fit, valid, glm_inputs, lam)
        rows.append({"ridge": lam, "class log loss": class_scores(valid, q)["class log loss"]})
    grid = pd.DataFrame(rows).set_index("ridge")
    ridge_ord = grid["class log loss"].idxmin()
    print(f"\nordinal GLM ridge search on 2013-2016:\n{grid.round(4).to_string()}\nchosen: {ridge_ord}")
    # part 1 and the dollar regressions: the same ridge search as reduced_benchmark.py
    rows = []
    for lam in rb.RIDGE_GRID:
        p, mu, _, _, _ = rb.glm_hurdle(fit, valid, glm_inputs, lam, lam)
        pc, vy = np.clip(p, 1e-9, 1 - 1e-9), valid["has_damage"].to_numpy()
        rows.append({"ridge": lam, "log loss": -np.mean(vy * np.log(pc) + (1 - vy) * np.log(1 - pc)),
                     "MAE": np.abs(valid[rb.TARGET].to_numpy()[vd] - mu[vd]).mean()})
    g = pd.DataFrame(rows).set_index("ridge")
    ridge1, ridge2 = g["log loss"].idxmin(), g["MAE"].idxmin()
    print(f"part 1 and dollar GLM ridges (as reduced_benchmark.py): {ridge1}, {ridge2}")

    table, rank_table, confusion = {}, {}, []

    def score_all(period_name, fit_df, score_df, lgb_rounds=None, cls_rounds=None):
        """Fit every model on fit_df and score score_df. Returns the LightGBM tree counts."""
        y_any = score_df["has_damage"].to_numpy()
        # baseline
        pb, _, _ = rb.climatology(fit_df, score_df)
        qb = baseline_classes(fit_df, score_df)
        Pb = full_probs(pb, qb)
        base_brier = np.mean((pb - y_any) ** 2)
        base_rps = all_row_scores(score_df, Pb)["RPS, all rows"]
        # GLM: part 1 logistic + ordinal part 2; and the dollar regression, binned
        pg, mug, eg, _, _ = rb.glm_hurdle(fit_df, score_df, glm_inputs, ridge1, ridge2)
        qg, coef, thr = glm_classes(fit_df, score_df, glm_inputs, ridge_ord)
        # LightGBM: part 1 classifier (and dollar regressor) + multiclass part 2
        if lgb_rounds is None:
            pl, mul, el, lgb_rounds, _ = rb.lgb_hurdle(fit_df, score_df, tree_inputs, valid_df=score_df)
            ql, cls_rounds = lgb_classes(fit_df, score_df, tree_inputs, valid_df=score_df)
        else:
            pl, mul, el, _, _ = rb.lgb_hurdle(fit_df, score_df, tree_inputs, rounds=lgb_rounds)
            ql, _ = lgb_classes(fit_df, score_df, tree_inputs, rounds=cls_rounds)

        for name, p, q, hard, e in [("baseline: county rate", pb, qb, None, None),
                                    ("GLM: ordinal classes", pg, qg, None, None),
                                    ("GLM: binned dollars", pg, None, binned(mug), eg),
                                    ("LightGBM: multiclass", pl, ql, None, None),
                                    ("LightGBM: binned dollars", pl, None, binned(mul), el)]:
            row = {"ROC-AUC": rb.auc(y_any, p), "PR-AUC": rb.avg_precision(y_any, p),
                   "Brier skill": 1 - np.mean((p - y_any) ** 2) / base_brier}
            row.update(class_scores(score_df, q=q, hard=hard))
            if q is not None:
                row.update(all_row_scores(score_df, full_probs(p, q), base_rps))
            else:   # the dollar model ranks by expected dollars, as in reduced_benchmark.py
                row.update(ranking(score_df, e))
            table[(period_name, name)] = row
        for name, p, q in [("GLM: ordinal classes", pg, qg), ("LightGBM: multiclass", pl, ql)]:
            P = full_probs(p, q)
            for s, f in RANK_SCORES.items():
                rank_table[(period_name, name, s)] = ranking(score_df, f(P))
        if period_name.startswith("test"):
            d = (score_df["has_damage"] == 1).to_numpy()
            y = loss_class(score_df)[d]
            for name, hard in [("GLM: ordinal classes", qg.argmax(1) + 1), ("LightGBM: multiclass", ql.argmax(1) + 1),
                               ("LightGBM: binned dollars", binned(mul))]:
                cm = pd.crosstab(pd.Series(y, name="recorded"), pd.Series(hard[d], name="predicted"))
                cm = cm.reindex(index=[1, 2, 3, 4], columns=[1, 2, 3, 4], fill_value=0)
                cm.index, cm.columns = NAMES[1:], NAMES[1:]
                confusion.append(cm.assign(model=name).set_index("model", append=True))
                print(f"\ntest confusion, {name} (rows recorded, columns predicted; damage months):\n{cm.to_string()}")
            coefs = pd.DataFrame({"coef (log-odds of a higher class)": coef[glm_inputs]})
            print("\nordinal GLM, per 1 std of each input (positive = larger loss class):\n"
                  + coefs.round(3).to_string())
            print("thresholds (log-odds):", np.round(thr, 3))
            coefs.round(4).to_csv(os.path.join(args.out_dir, "glm_ordinal_coefs.csv"))
            print(f"\nmean P(class | damage), LightGBM test: "
                  + ", ".join(f"{n} {v:.3f}" for n, v in zip(NAMES[1:], ql.mean(axis=0))))
        return lgb_rounds, cls_rounds

    # validation: fit 2000-2012, early-stop and score on 2013-2016 (compare designs here)
    rounds, cls_rounds = score_all("validation 2013-2016", fit, valid)
    print(f"\nLightGBM trees chosen on 2013-2016: part 1 {rounds[0]}, dollars {rounds[1]}, classes {cls_rounds}")
    # test: refit on 2000-2016 with 15% more trees (as reduced_benchmark.py)
    final = (int(rounds[0] * 1.15), int(rounds[1] * 1.15))
    score_all("test 2017-2023", train, test, lgb_rounds=final, cls_rounds=int(cls_rounds * 1.15))
    print(f"refit trees: part 1 {final[0]}, dollars {final[1]}, classes {int(cls_rounds * 1.15)}")

    table = pd.DataFrame(table).T
    table.index.names = ["period", "model"]
    print("\npart 1 (any damage), every county-month:\n"
          + table[["ROC-AUC", "PR-AUC", "Brier skill"]].round(3).to_string())
    print("\npart 2 (loss class), damage months only:\n"
          + table[["class log loss", "RPS, damaged", "accuracy", "within one class", "MAE, classes",
                   "weighted kappa"]].round(3).to_string())
    print(f"\nall rows and ranking (classes: ranked by {RANK_SCORE}; binned dollars: by expected dollars):\n"
          + table[["RPS, all rows", "RPS skill", "top 5%: share of loss", "top 5%: without largest month",
                   "top 5%: major+ months caught"]].round(3).to_string())
    rank_table = pd.DataFrame(rank_table).T
    rank_table.index.names = ["period", "model", "rank by"]
    print("\nranking score options (choose on validation):\n" + rank_table.round(3).to_string())

    table.round(4).to_csv(os.path.join(args.out_dir, "scores.csv"))
    rank_table.round(4).to_csv(os.path.join(args.out_dir, "ranking_options.csv"))
    pd.concat(confusion).to_csv(os.path.join(args.out_dir, "confusion_test.csv"))


if __name__ == "__main__":
    main()
