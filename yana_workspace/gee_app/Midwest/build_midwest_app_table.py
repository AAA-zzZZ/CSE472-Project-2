"""
Build the table the Midwest Earth Engine app reads: county-month predictions and model inputs for
all 12 states (1,055 counties), structured like missouri_tester/mo_flood_app_table.csv.

Predicts loss classes, not dollars (loss_class_model.py): part 1 is the 12-state LightGBM damage
classifier exactly as reduced_benchmark.py fits it without --state; part 2 is the LightGBM
multiclass model of loss_class_model.py (minor under $10k, moderate $10k-$100k, major $100k-$1M,
severe $1M or more). Both are fitted on 2000-2016 (state is an input, tree counts chosen on
2000-2012 -> 2013-2016) and predict the 2017-2023 test years. The scores are checked against
results/midwest_prism/scores.csv (part 1) and results/loss_classes_midwest/scores.csv (part 2).

Prediction columns:
  p_damage                  chance of any damage that month
  p_<class>_if_damage       chance of each loss class if damage occurs (minor ... severe; sum to 1)
  likely_class              most likely class if damage occurs: 1 minor ... 4 severe
  p_major_or_worse          chance of a loss of $100k or more = p_damage x (major + severe)
  p_severe_loss             chance of a loss of $1M or more = p_damage x severe (the ranking score)
  actual_class              recorded class: 0 none, 1 minor ... 4 severe
Other columns as in the Missouri table, without its dollar predictions (expected_loss,
loss_if_damage, log10_expected_loss), plus:
  state         two-letter state code
  rank_midwest  rank by p_severe_loss among all 1,055 counties that month
'rank' and 'top5' are within the county's own state, by p_severe_loss: top5 marks the top 5% of
that state's counties (round(0.05 x counties), e.g. 6 of Missouri's 115).

The adaptation columns (nfip_policies_per_hu, crs_best_class, median_income, built_pre1980_share)
are joined with add_adaptation() from missouri_tester/build_app_table.py (values from year - 1).

Output: yana_workspace/gee_app/Midwest/midwest_flood_app_table.csv (1,055 counties x 84 months)
Run from the repository root:
    pip install lightgbm scikit-learn
    python yana_workspace/gee_app/Midwest/build_midwest_app_table.py
    python yana_workspace/gee_app/Midwest/build_midwest_app_table.py --adaptation-only
        (adds or refreshes only the adaptation columns of the existing table: no model refit)
"""

import argparse
import importlib.util
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())

OUT = "yana_workspace/gee_app/Midwest/midwest_flood_app_table.csv"
SAVED_SCORES = "results/midwest_prism/scores.csv"
SAVED_CLASS_SCORES = "results/loss_classes_midwest/scores.csv"
TOP_SHARE = 0.05
# the exact inputs of the model, kept in the units the model sees (as in the Missouri table)
INPUTS = ["p_month", "rx5_rl_ratio", "snowmelt_mm", "frost_days", "sm_root_pct", "swe_mm",
          "c_rx5_rl10_mm", "log_built_surface", "impervious_mean", "hand_lt5_share",
          "log_land_km2", "wetland_share"]


def missouri_builder():
    """The Missouri script, for its add_adaptation() and ADAPTATION list (one copy of that join)."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "missouri_tester", "build_app_table.py")
    spec = importlib.util.spec_from_file_location("mo_build_app_table", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MO = missouri_builder()


def adaptation_only():
    t = pd.read_csv(OUT)
    n = len(t)
    t = MO.add_adaptation(t)
    assert len(t) == n
    t = t.sort_values(["ym", "state", "rank"])
    t.to_csv(OUT, index=False, float_format="%.6g")
    print(f"added {MO.ADAPTATION} to {OUT}: {len(t):,} rows x {t.shape[1]} columns")
    print(t[MO.ADAPTATION].quantile([0, 0.01, 0.5, 0.99, 1]).T.round(4).to_string())


def build():
    import reduced_benchmark as rb
    import loss_class_model as lc
    data, _, tree = rb.load("model_panel.csv", False, None, rb.DEFAULT_EXPOSURE)
    train = data[data["split"] == "train"].reset_index(drop=True)
    test = data[data["split"] == "test"].reset_index(drop=True)
    fit = train[train["year"] <= 2012].reset_index(drop=True)
    valid = train[train["year"] >= 2013].reset_index(drop=True)

    # part 1 (and reduced_benchmark's dollar regressor, kept only to check the saved scores)
    _, _, _, rounds, _ = rb.lgb_hurdle(fit, valid, tree, valid_df=valid)
    final = (int(rounds[0] * 1.15), int(rounds[1] * 1.15))
    p, mu, expected, _, _ = rb.lgb_hurdle(train, test, tree, rounds=final)
    # part 2: loss classes
    _, cls_rounds = lc.lgb_classes(fit, valid, tree, valid_df=valid)
    cls_final = int(cls_rounds * 1.15)
    q, _ = lc.lgb_classes(train, test, tree, rounds=cls_final)
    print(f"trees: part 1 {final[0]}, classes {cls_final}")

    # the app must show the model in the report, so stop if it does not reproduce
    base = rb.climatology(train, test)
    got = rb.scores(test, p, mu, expected, np.mean((base[0] - test["has_damage"]) ** 2))
    got.update(lc.class_scores(test, q=q))
    checks = [(SAVED_SCORES, "LightGBM hurdle", ["ROC-AUC", "PR-AUC"]),
              (SAVED_CLASS_SCORES, "LightGBM: multiclass", ["class log loss", "accuracy", "weighted kappa"])]
    for path, model, cols in checks:
        saved = pd.read_csv(path).query("period == 'test 2017-2023' and model == @model").iloc[0]
        for col in cols:
            print(f"{col}: {got[col]:.4f} (saved {saved[col]:.4f})")
            if abs(got[col] - saved[col]) > 0.0015:
                raise SystemExit(f"{col} does not match {path}")

    t = test[["GEOID", "state", "year", "month", "has_damage", "PropertyDmgADJ"] + INPUTS].copy()
    # a text key: Earth Engine would otherwise read GEOID as a number
    t.insert(0, "key", "G" + t["GEOID"])
    t["ym"] = t["year"] * 100 + t["month"]
    t["ym_label"] = t["year"].astype(str) + "-" + t["month"].astype(str).str.zfill(2)
    t["p_damage"] = p
    for i, name in enumerate(lc.NAMES[1:]):
        t[f"p_{name}_if_damage"] = q[:, i]
    t["likely_class"] = q.argmax(axis=1) + 1
    t["p_major_or_worse"] = p * q[:, lc.MAJOR - 1:].sum(axis=1)
    t["p_severe_loss"] = p * q[:, 3]
    t["actual_class"] = lc.loss_class(test)
    t = t.rename(columns={"PropertyDmgADJ": "actual_loss"})
    t["log10_actual_loss"] = np.log10(t["actual_loss"] + 1)
    # rank by the chance of a severe loss, within the state (as in the Missouri table) and across the Midwest
    t["rank"] = t.groupby(["ym", "state"])["p_severe_loss"].rank(ascending=False, method="first").astype(int)
    top_n = (t.groupby("state")["key"].nunique() * TOP_SHARE).round().astype(int)
    t["top5"] = (t["rank"] <= t["state"].map(top_n)).astype(int)
    t["rank_midwest"] = t.groupby("ym")["p_severe_loss"].rank(ascending=False, method="first").astype(int)
    t = MO.add_adaptation(t)
    t = t.sort_values(["ym", "state", "rank"])
    t.drop(columns=["GEOID"]).to_csv(OUT, index=False, float_format="%.6g")

    print(f"wrote {len(t):,} rows x {t.shape[1] - 1} columns to {OUT} ({os.path.getsize(OUT) / 1e6:.1f} MB)")
    print("missing values:", int(t.isna().sum().sum()), "| counties:", t["key"].nunique(), "| months:", t["ym"].nunique())
    print("\ncounties and top-5% size per state (for the app's STATES table):")
    print(pd.DataFrame({"counties": t.groupby("state")["key"].nunique(), "top_n": top_n}).to_string())
    print("\nmap ranges (1st and 99th percentile):")
    cols = INPUTS + ["p_damage", "p_major_or_worse", "p_severe_loss", "log10_actual_loss"] + MO.ADAPTATION
    print(t[cols].quantile([0, 0.01, 0.5, 0.95, 0.99, 1]).T.round(4).to_string())
    print("\nmost likely class if damage occurs (share of rows):\n"
          + t["likely_class"].value_counts(normalize=True).sort_index().round(3).to_string())
    caught = t[t["top5"] == 1].groupby("ym")["actual_loss"].sum().sum() / t["actual_loss"].sum()
    print(f"\nshare of test-year loss in each state's top 5% of counties each month: {caught:.3f}")
    print(t[t.ym == 201704].nsmallest(6, "rank_midwest")[
        ["key", "state", "rank", "rank_midwest", "p_damage", "likely_class", "p_severe_loss",
         "actual_class"]].to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--adaptation-only", action="store_true",
                    help="add the adaptation columns to the existing table without refitting the model")
    if ap.parse_args().adaptation_only:
        adaptation_only()
    else:
        build()
