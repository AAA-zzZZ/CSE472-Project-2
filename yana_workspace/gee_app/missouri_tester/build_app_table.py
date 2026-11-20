"""
Build the one table the Earth Engine app reads: Missouri county-month predictions and model inputs.

Fits the Missouri LightGBM hurdle exactly as reduced_benchmark.py does (2000-2016, tree counts
chosen on 2000-2012 -> 2013-2016), predicts the 2017-2023 test years, and checks the scores against
results/missouri_prism/scores.csv.

It also adds the adaptation columns for the app's "Adaptation" layers (not inputs of the forecast
model; they are the A variables of adjustment_models.py), read from data/clean/ with the same
one-year lag as merge_panel.py: nfip_policies_per_hu, crs_best_class, median_income,
built_pre1980_share.

Output: yana_workspace/gee_app/missouri_tester/mo_flood_app_table.csv (115 counties x 84 months)
Run from the repository root:
    pip install lightgbm scikit-learn
    python yana_workspace/gee_app/missouri_tester/build_app_table.py
    python yana_workspace/gee_app/missouri_tester/build_app_table.py --adaptation-only
        (adds or refreshes only the adaptation columns of the existing table: no model refit,
         no model_panel.csv or LightGBM needed)
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.getcwd())

STATE = "MO"
OUT = "yana_workspace/gee_app/missouri_tester/mo_flood_app_table.csv"
CLEAN = "data/clean"
TOP_N = 6      # top 5% of 115 counties, as in the scores
# the exact inputs of the model, kept in the units the model sees
INPUTS = ["p_month", "rx5_rl_ratio", "snowmelt_mm", "frost_days", "sm_root_pct", "swe_mm",
          "c_rx5_rl10_mm", "log_built_surface", "impervious_mean", "hand_lt5_share",
          "log_land_km2", "wetland_share"]
ADAPTATION = ["nfip_policies_per_hu", "crs_best_class", "median_income", "built_pre1980_share"]


def add_adaptation(t):
    """Join the adaptation columns by key and year, values from year - 1 (as merge_panel.py)."""
    def read(name, cols):
        df = pd.read_csv(os.path.join(CLEAN, name), dtype={"GEOID": str})
        df["key"] = "G" + df["GEOID"].str.zfill(5)
        return df[["key", "year"] + cols].assign(year=df["year"] + 1)
    yearly = (read("census_county_year.csv", ["housing_units", "median_income", "built_pre1980_share"])
              .merge(read("nfip_policies_county_year.csv", ["policies_in_force"]), on=["key", "year"], how="left")
              .merge(read("crs_county_year.csv", ["crs_best_class"]), on=["key", "year"], how="left"))
    yearly["nfip_policies_per_hu"] = yearly["policies_in_force"] / yearly["housing_units"]
    t = t.drop(columns=[c for c in ADAPTATION if c in t]).merge(
        yearly[["key", "year"] + ADAPTATION], on=["key", "year"], how="left")
    missing = t[ADAPTATION].isna().sum()
    if missing.any():
        raise SystemExit(f"adaptation values missing: {missing[missing > 0].to_dict()}")
    return t


def adaptation_only():
    t = pd.read_csv(OUT)
    n = len(t)
    t = add_adaptation(t)
    assert len(t) == n
    t = t.sort_values(["ym", "rank"])
    t.to_csv(OUT, index=False, float_format="%.6g")
    print(f"added {ADAPTATION} to {OUT}: {len(t):,} rows x {t.shape[1]} columns")
    print(t[ADAPTATION].quantile([0, 0.01, 0.5, 0.99, 1]).T.round(4).to_string())


def build():
    import reduced_benchmark as rb
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
    t = add_adaptation(t)
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


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--adaptation-only", action="store_true",
                    help="add the adaptation columns to the existing table without refitting the model")
    if ap.parse_args().adaptation_only:
        adaptation_only()
    else:
        build()
