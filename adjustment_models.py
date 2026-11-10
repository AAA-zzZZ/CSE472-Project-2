"""
Climate and adaptation adjustment: five nested regressions of flood loss on storm size
(flood_adjustment_onepager.pdf, 10 Nov 2026; replaces the earlier "Equation 4" plan).

  log10(loss) = b1 storm + b2 exposure + c climate + a adaptation + d (storm x adaptation) + rest

  storm      rx5_rl_ratio            how extreme the rain was (W)
  exposure   log_built_surface       how much can be damaged (X)
  climate    c_rx5_rl10_mm / 10      how wet it normally is (C), so c is "per 10 mm"
  adaptation nfip_policies_per_hu, log_median_income, built_pre1980_share, wetland_share,
             crs_best_class if the panel has it (A), each scaled to mean 0, std 1
  rest       sm_root_pct, log snowmelt, log snow water, frost days, log monthly rain,
             hand_lt5_share, log land area, month and state fixed effects (in every model)

  M0  rest only                What does a storm appear to cost if we ignore climate and adaptation?
  M1  + climate                Does the storm effect change among counties with a similar climate?
  M2  + adaptation             Does it change among counties that are similarly prepared?
  M3  + climate + adaptation   Best estimate of the storm effect, the same for every county
  M4  M3 + storm x adaptation  Does the same storm do less damage in a better-prepared county?

Rules from the one-pager, as applied here:
  * Same rows in every model: damage months (loss > 0) in model years 2011-2023, with no
    missing value in any M4 variable. NFIP policies are joined with a one-year lag by
    merge_panel.py, so the 2010-2022 policy table covers exactly these model years.
  * The adaptation effect is read from d, not a: risky counties buy more insurance, so a
    positive a does not mean insurance causes losses.
  * No input is caused by the flood: no claims, disaster declarations or FEMA payouts.

Loss is SHELDUS property damage in 2024 dollars, log_PropertyDmgADJ = log10(loss + 1), so a
coefficient b means "one more unit multiplies loss by about 10^b". Ordinary least squares
with standard errors clustered by county. Damage months only, as in part 2 of the hurdle
model: the one-pager's outcome log10(loss) is not defined for zero-loss months.

This is a regression for interpretation, not a forecast, so there is no train/test split.

Input : model_panel.csv from merge_panel.py (PRISM climate, GHSL, census and NFIP tables)
Output, in --out-dir:
  coefs.csv         every coefficient of every model, with clustered SE and 95% interval
  summary.csv       b1, b2, c and d per model (the one-pager's Step 3 table)
  correlations.csv  pairs of continuous inputs with |r| above --corr-max
  sample.csv        rows, counties and years per state in the fitted sample
  log.txt           everything printed here, including the four report sentences
  plot_storm_coef.png, plot_climate_bars.png, plot_damage_curves.png   (needs matplotlib)

Usage:
    python adjustment_models.py --state MO --out-dir results/adjustment_missouri
    python adjustment_models.py --out-dir results/adjustment_midwest
    python adjustment_models.py --extras --drop poverty_rate --out-dir <folder>
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

TARGET = "log_PropertyDmgADJ"
STATES = {"17": "IL", "18": "IN", "19": "IA", "20": "KS", "26": "MI", "27": "MN",
          "29": "MO", "31": "NE", "38": "ND", "39": "OH", "46": "SD", "55": "WI"}
YEARS = (2011, 2023)

STORM = "rx5_rl_ratio"
EXPOSURE = "log_built_surface"
CLIMATE = "climate_10mm"                 # c_rx5_rl10_mm / 10
ADAPT = ["nfip_policies_per_hu", "log_median_income", "built_pre1980_share", "wetland_share"]
CRS = "crs_best_class"                   # added to ADAPT when the panel has it
REST = ["sm_root_pct", "log_snowmelt_mm", "log_swe_mm", "frost_days", "log_p_month",
        "hand_lt5_share", "log_land_km2"]
EXTRAS = ["log_median_value", "mobile_home_share", "impervious_mean"]   # --extras, added to REST

MODELS = {
    "M0": dict(climate=False, adapt=False, inter=False),
    "M1": dict(climate=True, adapt=False, inter=False),
    "M2": dict(climate=False, adapt=True, inter=False),
    "M3": dict(climate=True, adapt=True, inter=False),
    "M4": dict(climate=True, adapt=True, inter=True),
}
MAIN_A = "nfip_policies_per_hu"          # the adaptation variable used in the report sentences


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


# ---------------------------------------------------------------
# data
# ---------------------------------------------------------------
def load(path, state, extras, drop):
    data = pd.read_csv(path, dtype={"GEOID": str})
    data["GEOID"] = data["GEOID"].str.zfill(5)
    data["state"] = data["GEOID"].str[:2].map(STATES)
    if state:
        if state not in STATES.values():
            raise SystemExit(f"--state {state}: use one of {sorted(STATES.values())}")
        data = data[data["state"] == state]

    need = [TARGET, "has_damage", STORM, EXPOSURE, "c_rx5_rl10_mm", "nfip_policies_per_hu",
            "median_income", "built_pre1980_share", "wetland_share", "sm_root_pct", "snowmelt_mm",
            "swe_mm", "frost_days", "p_month", "hand_lt5_share", "land_km2"]
    if extras:
        need += ["median_value", "mobile_home_share", "impervious_mean"]
    absent = [c for c in need if c not in data]
    if absent:
        raise SystemExit(f"{absent} not in {path}. Rebuild it with merge_panel.py after "
                         "census_features.py, ghsl_features.py and openfema_features.py.")

    data = data[(data["has_damage"] == 1) & data["year"].between(*YEARS)].copy()
    data[CLIMATE] = data["c_rx5_rl10_mm"] / 10
    data["log_median_income"] = np.log(data["median_income"])
    for col in ["p_month", "swe_mm", "snowmelt_mm"]:
        data["log_" + col] = np.log1p(data[col].clip(lower=0))
    data["log_land_km2"] = np.log(data["land_km2"])
    if extras:
        data["log_median_value"] = np.log(data["median_value"])

    adapt = ADAPT + ([CRS] if CRS in data else [])
    rest = REST + (EXTRAS if extras else [])
    for name in drop:
        if name not in [STORM, EXPOSURE, CLIMATE] + adapt + rest:
            raise SystemExit(f"--drop {name}: not one of the model inputs")
        if name in [STORM, EXPOSURE, CLIMATE]:
            raise SystemExit(f"--drop {name}: storm, exposure and climate are the core of the design")
    adapt = [c for c in adapt if c not in drop]
    rest = [c for c in rest if c not in drop]
    if not adapt:
        raise SystemExit("no adaptation variable left after --drop")

    # same rows in every model: complete cases on the full M4 set
    cols = [TARGET, STORM, EXPOSURE, CLIMATE] + adapt + rest
    finite = np.isfinite(data[cols].to_numpy(dtype=float)).all(axis=1)
    print(f"damage months {YEARS[0]}-{YEARS[1]}: {len(data):,}; "
          f"dropped {(~finite).sum():,} with a missing or infinite input")
    if (~finite).any():
        bad = (~np.isfinite(data.loc[~finite, cols].to_numpy(dtype=float))).sum(axis=0)
        print("  missing by column:", {c: int(n) for c, n in zip(cols, bad) if n})
    data = data[finite].reset_index(drop=True)
    if data.empty:
        raise SystemExit("no rows left")

    # scale each adaptation variable to mean 0, std 1 on the fitted rows, so a and d are per
    # 1 std and b1 in M4 is the storm effect in a county of average adaptation
    for c in adapt:
        data[c] = (data[c] - data[c].mean()) / data[c].std()
    return data, adapt, rest


def check_correlations(data, cols, limit):
    """Pairs of continuous inputs that move together closely enough to split one effect."""
    r = data[cols].corr()
    pairs = [(a, b, r.loc[a, b]) for i, a in enumerate(cols) for b in cols[i + 1:]
             if abs(r.loc[a, b]) > limit]
    out = pd.DataFrame(pairs, columns=["var1", "var2", "r"])
    if out.empty:
        print(f"correlation check: no pair above |r| = {limit}")
    else:
        print(f"correlation check: {len(out)} pair(s) above |r| = {limit}; drop one of each "
              "with --drop and rerun")
        print(out.round(3).to_string(index=False))
    return out


# ---------------------------------------------------------------
# regression
# ---------------------------------------------------------------
def design(data, spec, adapt, rest, states):
    cols = [STORM, EXPOSURE]
    if spec["climate"]:
        cols.append(CLIMATE)
    if spec["adapt"]:
        cols += adapt
    X = data[cols + rest].astype(float).copy()
    if spec["inter"]:
        for a in adapt:
            X[f"{STORM}:{a}"] = data[STORM] * data[a]
    X = pd.concat([X, pd.get_dummies(data["month"], prefix="m", dtype=float)
                   .reindex(columns=[f"m_{m}" for m in range(2, 13)], fill_value=0.0)], axis=1)
    for s in states[1:]:
        X[f"st_{s}"] = (data["state"] == s).astype(float)
    X = X.loc[:, X.std() > 0]            # a month with no damage rows in a small state
    X.insert(0, "const", 1.0)
    return X


def ols_cluster(X, y, groups):
    """OLS with county-clustered (CR1) standard errors."""
    A, y = X.to_numpy(), y.to_numpy()
    n, k = A.shape
    if np.linalg.matrix_rank(A) < k:
        raise SystemExit(f"design matrix is rank deficient ({np.linalg.matrix_rank(A)} < {k})")
    AtA_inv = np.linalg.inv(A.T @ A)
    beta = AtA_inv @ A.T @ y
    resid = y - A @ beta
    score = pd.DataFrame(A * resid[:, None]).groupby(groups.to_numpy()).sum().to_numpy()
    g = score.shape[0]
    meat = score.T @ score
    V = AtA_inv @ meat @ AtA_inv * (g / (g - 1)) * ((n - 1) / (n - k))
    se = np.sqrt(np.diag(V))
    r2 = 1 - resid.var() / y.var()
    return pd.Series(beta, X.columns), pd.Series(se, X.columns), pd.DataFrame(V, X.columns, X.columns), r2


def fit_all(data, adapt, rest):
    states = sorted(data["state"].unique())
    rows, fits = [], {}
    for name, spec in MODELS.items():
        X = design(data, spec, adapt, rest, states)
        b, se, V, r2 = ols_cluster(X, data[TARGET], data["GEOID"])
        fits[name] = dict(X=X, b=b, V=V)
        print(f"{name}: {len(X):,} rows, {data['GEOID'].nunique()} counties, {X.shape[1]} terms, "
              f"R2 {r2:.3f}")
        for term in X.columns:
            rows.append(dict(model=name, term=term, coef=b[term], se=se[term],
                             ci_lo=b[term] - 1.96 * se[term], ci_hi=b[term] + 1.96 * se[term],
                             z=b[term] / se[term], n=len(X), n_counties=data["GEOID"].nunique(), r2=r2))
    return pd.DataFrame(rows), fits


def summary_table(coefs, adapt):
    """The one-pager's Step 3 table: b1, b2, c and each d, with SE, one column per model."""
    labels = {STORM: "b1 storm", EXPOSURE: "b2 exposure", CLIMATE: "c climate (per 10 mm)"}
    labels.update({f"{STORM}:{a}": f"d storm x {a}" for a in adapt})
    labels.update({a: f"a {a}" for a in adapt})
    keep = coefs[coefs["term"].isin(labels)]
    est = keep.pivot(index="term", columns="model", values="coef")
    se = keep.pivot(index="term", columns="model", values="se")
    est = est.reindex([t for t in labels if t in est.index])
    se = se.reindex(est.index)
    out = pd.concat({"coef": est, "se": se}, axis=1)
    out.index = [labels[t] for t in out.index]
    shown = est.copy()
    for m in shown.columns:
        shown[m] = [("" if pd.isna(e) else f"{e:.3f} ({s:.3f})") for e, s in zip(est[m], se[m])]
    shown.index = out.index
    print("\ncoefficients (clustered SE); adaptation per 1 std, loss in log10 dollars")
    print(shown.to_string())
    return out


def report(coefs, adapt):
    """The four comparisons from the one-pager, filled with this run's numbers."""
    c = coefs.set_index(["model", "term"])["coef"]
    b1 = {m: c[(m, STORM)] for m in MODELS}
    print("\nreport sentences (check signs and intervals before using them):")
    print(f"  Storm, M0 to M3: one more unit of rx5_rl_ratio multiplies loss by "
          f"10^{b1['M0']:.2f} = {10 ** b1['M0']:.1f}x ignoring climate and adaptation, and by "
          f"10^{b1['M3']:.2f} = {10 ** b1['M3']:.1f}x after adjusting for both.")
    print(f"  Storm, M2 vs M3: {b1['M2']:.2f} vs {b1['M3']:.2f}. A gap means the adaptation "
          "variables do not capture everything that climate stands in for.")
    c1, c3 = c[("M1", CLIMATE)], c[("M3", CLIMATE)]
    share = (c1 - c3) / c1 if c1 != 0 else np.nan
    print(f"  Climate, M1 to M3: c moves from {c1:.3f} to {c3:.3f} per 10 mm; measured "
          f"adaptation explains {share:.0%} of the climate coefficient.")
    a = MAIN_A if MAIN_A in adapt else adapt[0]
    d = c[("M4", f"{STORM}:{a}")]
    b14 = b1["M4"]
    print(f"  M4: one more unit of rx5_rl_ratio multiplies loss by {10 ** b14:.1f}x in a county of "
          f"average {a}, and by 10^({b14:.2f} {d:+.2f}) = {10 ** (b14 + d):.1f}x one std above "
          "average.")


# ---------------------------------------------------------------
# plots
# ---------------------------------------------------------------
def plots(coefs, fits, data, adapt, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed: plots skipped")
        return
    models = list(MODELS)

    # 1. b1 (and b2) per model with 95% intervals
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    for term, label, shift, color in [(STORM, "b1 storm (rx5_rl_ratio)", -0.1, "#1f5fa8"),
                                      (EXPOSURE, "b2 exposure (log_built_surface)", 0.1, "#b5651d")]:
        sub = coefs[coefs["term"] == term].set_index("model").reindex(models)
        x = np.arange(len(models)) + shift
        ax.errorbar(x, sub["coef"], yerr=[sub["coef"] - sub["ci_lo"], sub["ci_hi"] - sub["coef"]],
                    fmt="o", capsize=4, color=color, label=label)
    ax.axhline(0, color="grey", lw=0.8)
    ax.set_xticks(range(len(models)), models)
    ax.set_ylabel("coefficient (log10 loss per unit)")
    ax.set_title("Storm and exposure effect by model, 95% intervals")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "plot_storm_coef.png"), dpi=200)
    plt.close(fig)

    # 2. climate coefficient before (M1) and after (M3) adding adaptation
    sub = coefs[coefs["term"] == CLIMATE].set_index("model").reindex(["M1", "M3"])
    fig, ax = plt.subplots(figsize=(4, 3.5))
    ax.bar(["M1\nclimate only", "M3\n+ adaptation"], sub["coef"], color=["#7a9cc6", "#1f5fa8"],
           yerr=[sub["coef"] - sub["ci_lo"], sub["ci_hi"] - sub["coef"]], capsize=5)
    ax.axhline(0, color="grey", lw=0.8)
    ax.set_ylabel("c (log10 loss per 10 mm of rx5 10-year level)")
    ax.set_title("Climate coefficient before and after adaptation")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "plot_climate_bars.png"), dpi=200)
    plt.close(fig)

    # 3. M4 damage curves: predicted loss vs storm size at adaptation -1, 0, +1 std, one
    #    panel per adaptation variable, every other input at its sample mean
    fit = fits["M4"]
    X, b = fit["X"], fit["b"]
    storm = np.linspace(data[STORM].quantile(0.02), data[STORM].quantile(0.98), 60)
    base = X.mean()
    fig, axes = plt.subplots(1, len(adapt), figsize=(3.2 * len(adapt), 3.4), sharey=True, squeeze=False)
    for ax, a in zip(axes[0], adapt):
        for level, color in [(-1, "#c0504d"), (0, "#555555"), (1, "#1f5fa8")]:
            rows = pd.DataFrame([base] * len(storm))
            rows[STORM] = storm
            for other in adapt:
                rows[other] = 0.0
                rows[f"{STORM}:{other}"] = 0.0
            rows[a] = level
            rows[f"{STORM}:{a}"] = storm * level
            pred = rows[X.columns].to_numpy() @ b.to_numpy()
            ax.plot(storm, 10 ** pred, color=color, label=f"{level:+d} std" if level else "average")
        ax.set_yscale("log")
        ax.set_title(a, fontsize=9)
        ax.set_xlabel("storm size (rx5_rl_ratio)")
    axes[0][0].set_ylabel("predicted loss, 2024 $ (log scale)")
    axes[0][0].legend(frameon=False, fontsize=8, title="adaptation", title_fontsize=8)
    fig.suptitle("M4 damage curves: same storm, different adaptation", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "plot_damage_curves.png"), dpi=200)
    plt.close(fig)
    print(f"plots written to {out_dir}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="model_panel.csv")
    ap.add_argument("--state", help="fit one state's counties only, e.g. MO")
    ap.add_argument("--extras", action="store_true",
                    help="add the optional inputs: log median home value, mobile home share, imperviousness")
    ap.add_argument("--drop", nargs="*", default=[], help="inputs to leave out (after the correlation check)")
    ap.add_argument("--corr-max", type=float, default=0.8)
    ap.add_argument("--out-dir", default="results/adjustment")
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    log = open(os.path.join(args.out_dir, "log.txt"), "w")
    sys.stdout = Tee(sys.__stdout__, log)
    print(f"adjustment_models.py {' '.join(sys.argv[1:])}")

    data, adapt, rest = load(args.panel, args.state, args.extras, args.drop)
    sample = data.groupby("state").agg(rows=(TARGET, "size"), counties=("GEOID", "nunique"),
                                       first_year=("year", "min"), last_year=("year", "max"))
    print(sample.to_string())
    sample.to_csv(os.path.join(args.out_dir, "sample.csv"))

    corr = check_correlations(data, [STORM, EXPOSURE, CLIMATE] + adapt + rest, args.corr_max)
    corr.to_csv(os.path.join(args.out_dir, "correlations.csv"), index=False)

    coefs, fits = fit_all(data, adapt, rest)
    coefs.to_csv(os.path.join(args.out_dir, "coefs.csv"), index=False)
    summary_table(coefs, adapt).to_csv(os.path.join(args.out_dir, "summary.csv"))
    report(coefs, adapt)
    plots(coefs, fits, data, adapt, args.out_dir)
    print(f"\nresults in {args.out_dir}")


if __name__ == "__main__":
    main()
