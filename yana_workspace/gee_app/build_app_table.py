"""
Build the one table the Earth Engine app reads: Missouri county-month predictions and model inputs.

Fits the Missouri LightGBM hurdle exactly as reduced_benchmark.py does (2000-2016, tree counts
chosen on 2000-2012 -> 2013-2016), predicts the 2017-2023 test years, and checks the scores against
results/missouri_prism/scores.csv.

Output: yana_workspace/gee_app/mo_flood_app_table.csv (115 counties x 84 months)
Run from the repository root:
    pip install lightgbm scikit-learn
    python yana_workspace/gee_app/build_app_table.py
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())
import reduced_benchmark as rb  # noqa: E402

STATE = "MO"
OUT = "yana_workspace/gee_app/mo_flood_app_table.csv"
TOP_N = 6      # top 5% of 115 counties, as in the scores
# the exact inputs of the model, kept in the units the model sees
INPUTS = ["p_month", "rx5_rl_ratio", "snowmelt_mm", "frost_days", "sm_root_pct", "swe_mm",
          "c_rx5_rl10_mm", "log_built_surface", "impervious_mean", "hand_lt5_share",
          "log_land_km2", "wetland_share"]

data, _, tree = rb.load("model_panel.csv", False, STATE, rb.DEFAULT_EXPOSURE)
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
saved = pd.read_csv("results/missouri_prism/scores.csv").query(
    "period == 'test 2017-2023' and model == 'LightGBM hurdle'").iloc[0]
for col in ["ROC-AUC", "PR-AUC", "MAE, damaged"]:
    print(f"{col}: {got[col]:.4f} (saved {saved[col]:.4f})")
    if abs(got[col] - saved[col]) > 0.0015:
        raise SystemExit(f"{col} does not match results/missouri_prism/scores.csv")

t = test[["GEOID", "year", "month", "has_damage", "PropertyDmgADJ"] + INPUTS].copy()
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
t["rank"] = t.groupby("ym")["expected_loss"].rank(ascending=False, method="first").astype(int)
t["top5"] = (t["rank"] <= TOP_N).astype(int)
t = t.sort_values(["ym", "rank"])
t.drop(columns=["GEOID"]).to_csv(OUT, index=False, float_format="%.6g")
print(f"wrote {len(t):,} rows x {t.shape[1] - 1} columns to {OUT} ({os.path.getsize(OUT) / 1e6:.1f} MB)")
print("missing values:", int(t.isna().sum().sum()), "| counties:", t["key"].nunique(), "| months:", t["ym"].nunique())
print("\nmap ranges (1st and 99th percentile):")
cols = INPUTS + ["p_damage", "log10_expected_loss", "log10_actual_loss"]
print(t[cols].quantile([0, 0.01, 0.5, 0.99, 1]).T.round(3).to_string())
caught = t[t["top5"] == 1].groupby("ym")["actual_loss"].sum().sum() / t["actual_loss"].sum()
print(f"\nshare of test-year loss in the app's top {TOP_N} counties each month: {caught:.3f}")
print(t[t.ym == 201704].head(6)[["key", "rank", "p_damage", "expected_loss", "actual_loss"]].to_string(index=False))
