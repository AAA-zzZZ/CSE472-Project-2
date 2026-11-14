"""
Build the table the Midwest Earth Engine app reads: county-month predictions and model inputs for
all 12 states (1,055 counties), structured like missouri_tester/mo_flood_app_table.csv.

Fits the 12-state LightGBM hurdle exactly as reduced_benchmark.py does without --state
(2000-2016, state is an input, tree counts chosen on 2000-2012 -> 2013-2016), predicts the
2017-2023 test years, and checks the scores against results/midwest_prism/scores.csv.

Same columns as the Missouri table, plus:
  state         two-letter state code
  rank_midwest  rank by expected loss among all 1,055 counties that month
'rank' and 'top5' are within the county's own state, as in the Missouri table: top5 marks the top
5% of that state's counties (round(0.05 x counties), e.g. 6 of Missouri's 115).

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
    data, _, tree = rb.load("model_panel.csv", False, None, rb.DEFAULT_EXPOSURE)
    train = data[data["split"] == "train"].reset_index(drop=True)
    test = data[data["split"] == "test"].reset_index(drop=True)
    fit = train[train["year"] <= 2012].reset_index(drop=True)
    valid = train[train["year"] >= 2013].reset_index(drop=True)

    _, _, _, rounds, _ = rb.lgb_hurdle(fit, valid, tree, valid_df=valid)
    final = (int(rounds[0] * 1.15), int(rounds[1] * 1.15))
    p, mu, expected, _, _ = rb.lgb_hurdle(train, test, tree, rounds=final)
    print(f"trees: {final}")

    # the app must show the model in the report, so stop if it does not reproduce
    base = rb.climatology(train, test)
    got = rb.scores(test, p, mu, expected, np.mean((base[0] - test["has_damage"]) ** 2))
    saved = pd.read_csv(SAVED_SCORES).query(
        "period == 'test 2017-2023' and model == 'LightGBM hurdle'").iloc[0]
    for col in ["ROC-AUC", "PR-AUC", "MAE, damaged"]:
        print(f"{col}: {got[col]:.4f} (saved {saved[col]:.4f})")
        if abs(got[col] - saved[col]) > 0.0015:
            raise SystemExit(f"{col} does not match {SAVED_SCORES}")

    t = test[["GEOID", "state", "year", "month", "has_damage", "PropertyDmgADJ"] + INPUTS].copy()
    # a text key: Earth Engine would otherwise read GEOID as a number
    t.insert(0, "key", "G" + t["GEOID"])
    t["ym"] = t["year"] * 100 + t["month"]
    t["ym_label"] = t["year"].astype(str) + "-" + t["month"].astype(str).str.zfill(2)
    t["p_damage"] = p
    t["expected_loss"] = expected
    t["loss_if_damage"] = expected / p
    t = t.rename(columns={"PropertyDmgADJ": "actual_loss"})
    t["log10_expected_loss"] = np.log10(t["expected_loss"] + 1)
    t["log10_actual_loss"] = np.log10(t["actual_loss"] + 1)
    # rank within the state (as in the Missouri table) and across the Midwest
    t["rank"] = t.groupby(["ym", "state"])["expected_loss"].rank(ascending=False, method="first").astype(int)
    top_n = (t.groupby("state")["key"].nunique() * TOP_SHARE).round().astype(int)
    t["top5"] = (t["rank"] <= t["state"].map(top_n)).astype(int)
    t["rank_midwest"] = t.groupby("ym")["expected_loss"].rank(ascending=False, method="first").astype(int)
    t = MO.add_adaptation(t)
    t = t.sort_values(["ym", "state", "rank"])
    t.drop(columns=["GEOID"]).to_csv(OUT, index=False, float_format="%.6g")

    print(f"wrote {len(t):,} rows x {t.shape[1] - 1} columns to {OUT} ({os.path.getsize(OUT) / 1e6:.1f} MB)")
    print("missing values:", int(t.isna().sum().sum()), "| counties:", t["key"].nunique(), "| months:", t["ym"].nunique())
    print("\ncounties and top-5% size per state (for the app's STATES table):")
    print(pd.DataFrame({"counties": t.groupby("state")["key"].nunique(), "top_n": top_n}).to_string())
    print("\nmap ranges (1st and 99th percentile):")
    cols = INPUTS + ["p_damage", "log10_expected_loss", "log10_actual_loss"] + MO.ADAPTATION
    print(t[cols].quantile([0, 0.01, 0.5, 0.99, 1]).T.round(4).to_string())
    caught = t[t["top5"] == 1].groupby("ym")["actual_loss"].sum().sum() / t["actual_loss"].sum()
    print(f"\nshare of test-year loss in each state's top 5% of counties each month: {caught:.3f}")
    print(t[t.ym == 201704].nsmallest(6, "rank_midwest")[
        ["key", "state", "rank", "rank_midwest", "p_damage", "expected_loss", "actual_loss"]].to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--adaptation-only", action="store_true",
                    help="add the adaptation columns to the existing table without refitting the model")
    if ap.parse_args().adaptation_only:
        adaptation_only()
    else:
        build()
