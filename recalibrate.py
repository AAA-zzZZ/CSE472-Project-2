"""
Per-state recalibration of the hurdle models (fix D): fewer damage months were reported after 2016,
so models trained on 2000-2016 predict too many. Shift each state's log-odds so its predicted
number of damage months matches the recent observed number, and score the shift on later years.

Models: GLM and LightGBM hurdle from reduced_benchmark.py, fitted on 2000-2016 exactly as there
(ridge and tree counts chosen on 2000-2012 -> 2013-2016).

Corrections, all scored on 2019-2023 only:
  none      the 2000-2016 model as it is
  fixed     one log-odds shift per state, fitted on 2017-2018 (the plan in HANDOFF.md)
  rolling   each year's shift fitted on the two years before it (2019 uses 2017-2018, 2020 uses
            2018-2019, ...): only past years, the way it would run each year in practice
The shift moves a state's probabilities up or down together, so it cannot change the ranking within
a state; it fixes the number of damage months and the expected dollars (p x amount).

Usage:
    python recalibrate.py --out-dir results/recalibration_midwest
    python recalibrate.py --state MO --out-dir results/recalibration_missouri
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

import reduced_benchmark as rb

CAL_YEARS = (2017, 2018)     # fixed correction
SCORE_START = 2019           # years scored: 2019-2023


def logit(p):
    p = np.clip(p, 1e-9, 1 - 1e-9)
    return np.log(p / (1 - p))


def shift_for(lp, y):
    """Log-odds shift d so that sum(sigmoid(lp + d)) equals the observed damage months (Newton)."""
    target, d = y.sum(), 0.0
    if target == 0:
        return -5.0   # no damage at all: cap the shift instead of going to minus infinity
    for _ in range(100):
        p = 1 / (1 + np.exp(-(lp + d)))
        step = (p.sum() - target) / (p * (1 - p)).sum()
        d -= step
        if abs(step) < 1e-10:
            break
    return d


def corrected(test, p, method):
    """Recalibrated probabilities for the test years; returns p and the shift table."""
    lp, y = logit(p), test["has_damage"].to_numpy()
    out, rows = p.copy(), []
    for state, idx in test.groupby("state").indices.items():
        years = test["year"].to_numpy()[idx]
        if method == "fixed":
            cal = idx[(years >= CAL_YEARS[0]) & (years <= CAL_YEARS[1])]
            d = shift_for(lp[cal], y[cal])
            out[idx] = 1 / (1 + np.exp(-(lp[idx] + d)))
            rows.append({"state": state, "fitted on": f"{CAL_YEARS[0]}-{CAL_YEARS[1]}", "shift": d})
        else:
            for yr in range(SCORE_START, years.max() + 1):
                cal = idx[(years >= yr - 2) & (years <= yr - 1)]
                d = shift_for(lp[cal], y[cal])
                now = idx[years == yr]
                out[now] = 1 / (1 + np.exp(-(lp[now] + d)))
                rows.append({"state": state, "fitted on": f"{yr - 2}-{yr - 1}", "year": yr, "shift": d})
    return out, pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="model_panel.csv")
    ap.add_argument("--state", help="one state only, e.g. MO")
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

    # ------ the 2000-2016 models, settings as in reduced_benchmark.py ------
    vy = valid["has_damage"].to_numpy()
    loss1, loss2 = {}, {}
    for lam in rb.RIDGE_GRID:
        p, mu, _, _, _ = rb.glm_hurdle(fit, valid, glm_inputs, lam, lam)
        pc = np.clip(p, 1e-9, 1 - 1e-9)
        loss1[lam] = -np.mean(vy * np.log(pc) + (1 - vy) * np.log(1 - pc))
        loss2[lam] = np.abs(valid[rb.TARGET].to_numpy()[vy == 1] - mu[vy == 1]).mean()
    r1, r2 = min(loss1, key=loss1.get), min(loss2, key=loss2.get)
    _, _, _, rounds, _ = rb.lgb_hurdle(fit, valid, tree_inputs, valid_df=valid)
    rounds = (int(rounds[0] * 1.15), int(rounds[1] * 1.15))
    models = {"GLM hurdle": rb.glm_hurdle(train, test, glm_inputs, r1, r2)[:3],
              "LightGBM hurdle": rb.lgb_hurdle(train, test, tree_inputs, rounds=rounds)[:3]}
    print(f"{args.state or 'Midwest'}: models fitted on 2000-2016 (GLM ridge {r1}/{r2}, LightGBM trees {rounds})")

    # ------ corrections, scored on 2019-2023 ------
    later = (test["year"] >= SCORE_START).to_numpy()
    score_df = test[later].reset_index(drop=True)
    yl = score_df["has_damage"].to_numpy()
    base = rb.climatology(train, score_df)
    base_brier = np.mean((base[0] - yl) ** 2)
    print(f"scored on {SCORE_START}-2023: {len(score_df):,} county-months, {int(yl.sum()):,} damage months "
          f"({yl.mean():.2%})\n")

    table, by_state, by_year, shifts = {}, {}, {}, []
    for name, (p, mu, e) in models.items():
        for method in ["none", "fixed", "rolling"]:
            if method == "none":
                pa = p
            else:
                pa, sh = corrected(test, p, method)
                shifts.append(sh.assign(model=name, method=method))
            ea = e * pa / p                       # expected dollars = p x amount, amount unchanged
            pl = pa[later]
            table[(name, method)] = rb.scores(score_df, pl, mu[later], ea[later], base_brier)
            d = score_df.assign(p=pl)
            by_state[(name, method)] = d.groupby("state")["p"].sum() / d.groupby("state")["has_damage"].sum()
            by_year[(name, method)] = d.groupby("year")["p"].sum() / d.groupby("year")["has_damage"].sum()

    table = pd.DataFrame(table).T
    table.index.names = ["model", "correction"]
    cols = ["mean P / rate", "Brier skill", "log loss", "ROC-AUC", "AUC within month",
            "top 5%: without largest month", "rank corr, year"]
    print(f"SCORES {SCORE_START}-2023 (mean P / rate: 1 = right number of damage months)")
    print(table[cols].round(3).to_string())
    print("\npredicted / observed damage months, by year:")
    print(pd.DataFrame(by_year).T.round(2).to_string())
    if not args.state:
        print("\npredicted / observed damage months, by state:")
        print(pd.DataFrame(by_state).T.round(2).to_string())
    shifts = pd.concat(shifts)
    fixed = shifts[shifts["method"] == "fixed"].pivot(index="state", columns="model", values="shift")
    print("\nfixed log-odds shift per state (negative = predictions lowered; -0.69 halves the odds):")
    print(fixed.round(2).to_string())

    table.round(4).to_csv(os.path.join(args.out_dir, "scores.csv"))
    shifts.round(4).to_csv(os.path.join(args.out_dir, "shifts.csv"), index=False)
    print(f"\nwrote scores.csv, shifts.csv and log.txt to {args.out_dir}")


if __name__ == "__main__":
    main()
