"""
Causal model (report Section 3.5): the effect of each factor in the causal diagram on the chance
of flood damage, in interpretable units. Replaces the earlier ordered-logit adjustment models
(on the enci-dev branch) after the instructor's feedback: variables must be interpretable (no
derived ratios, no log-loss outcome), and each effect needs its own controls.

Rows     : every county-month in 2011-2023 (the years with flood-insurance data), all 12 states,
           including months with no damage.
Outcomes : any   = any recorded flood damage (SHELDUS)
           major = a loss of $100,000 or more (2024 dollars)
Variables (all in units a reader can picture):
  rain      W  rain in the month's wettest 5 days, per 25 mm               (rx5 / 25)
  climate   C  rain the county expects in its 10-year 5-day storm, per 25 mm (c_rx5_rl10_mm / 25)
  built     X  built-up area, per doubling                                  (log2 km2)
  insurance A  flood-insurance policies per 100 homes, centred at its mean
  history      damaged months per year over the previous 10 years (confounder of insurance)
  background   soil wetness percentile and snowpack (log) on day 1, days below freezing,
               share of low-lying land, calendar month, state

Questions (each with the controls the causal diagram calls for):
  Q1 rain     : rain + climate + built + background      (also rain with no controls)
  Q2 climate  : the same model as Q1, read for climate
  Q3 insurance: rain x insurance + climate + history + built + background
  Q4 built-up : built + climate + background

Each effect is reported as an average change in probability (percentage points): every row's
predicted chance with the step (25 mm more rain, ...) minus without, averaged; standard errors by
the delta method from county-clustered coefficient covariances. Q3 gives the rain effect at low
(10th percentile) and high (90th percentile) insurance and their difference.

Checks: Q3 with each other preparedness measure in place of insurance; a linear probability model
(OLS on the 0/1 outcome, coefficients are probability changes); storm size relative to the
county's 10-year level (the course design); and expected dollars by Poisson regression (PPML).

--design nested (added 2026-11-17; the design of report Section 3.5): the course design's five
nested models on the same rows, with the interpretable variables above and all five preparedness
measures (insurance the main one), each centred at its average:
  M0 rain + built + background
  M1 M0 + climate
  M2 M0 + insurance, income, pre-1980 homes, wetland, any CRS community
  M3 M0 + climate + the five preparedness measures
  M4 M3 + rain x each preparedness measure
Reported for both outcomes: the rain effect (+25 mm) in every model; the climate effect (+25 mm,
same rain) in M1, M3, M4; built-up area doubled and each preparedness measure in M3 (reference
only); and from M4, the rain effect at low vs high values of each preparedness measure (10th vs
90th percentile; CRS no vs yes) with the difference. Checks: a linear probability model, storm
size relative to the 10-year level, and flood history added to M2-M4.

Usage:
    pip install statsmodels matplotlib
    python causal_model.py --design nested --out-dir results/causal_nested_midwest
    python causal_model.py --out-dir results/causal_midwest            (four questions)
    python causal_model.py --state MO --out-dir results/causal_missouri
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd
import patsy
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy.special import expit

STATES = {"17": "IL", "18": "IN", "19": "IA", "20": "KS", "26": "MI", "27": "MN",
          "29": "MO", "31": "NE", "38": "ND", "39": "OH", "46": "SD", "55": "WI"}
YEARS = (2011, 2023)
MAJOR = 1e5
OUTCOMES = {"any": "any damage", "major": "loss of $100k+"}


class Tee:
    def __init__(self, *s):
        self.s = s

    def write(self, t):
        for x in self.s:
            x.write(t)

    def flush(self):
        for x in self.s:
            x.flush()


def load(path, state):
    cols = ["GEOID", "year", "month", "has_damage", "PropertyDmgADJ", "rx5", "rx5_rl_ratio",
            "c_rx5_rl10_mm", "built_m2", "nfip_policies_per_hu", "sm_root_pct", "swe_mm",
            "frost_days", "hand_lt5_share", "median_income", "built_pre1980_share",
            "wetland_share", "crs_best_class"]
    d = pd.read_csv(path, dtype={"GEOID": str}, usecols=cols)
    d["GEOID"] = d["GEOID"].str.zfill(5)
    d["state"] = d["GEOID"].str[:2].map(STATES)
    if state:
        d = d[d["state"] == state]
    d = d.sort_values(["GEOID", "year", "month"]).reset_index(drop=True)
    # flood history: damaged months per year over the 120 months before this one (panel starts
    # in 2000, so every month from 2010 on has a full window)
    d["history"] = (d.groupby("GEOID")["has_damage"]
                    .transform(lambda s: s.shift(1).rolling(120, min_periods=120).sum()) / 10)
    d = d[d["year"].between(*YEARS)].copy()
    d["any"] = d["has_damage"].astype(int)
    d["major"] = (d["PropertyDmgADJ"] >= MAJOR).astype(int)
    d["rain"] = d["rx5"] / 25
    d["climate"] = d["c_rx5_rl10_mm"] / 25
    d["built"] = np.log2(d["built_m2"] / 1e6)
    d["ins_raw"] = 100 * d["nfip_policies_per_hu"]
    d["log_swe"] = np.log1p(d["swe_mm"].clip(lower=0))
    d["ratio"] = d["rx5_rl_ratio"] * 10                       # per 0.1 of the 10-year level
    # alternative preparedness measures for the Q3 check, in plain units
    d["inc_raw"] = d["median_income"] / 1e4                   # per $10k
    d["pre_raw"] = d["built_pre1980_share"] * 10              # per 10 percentage points
    d["wet_raw"] = d["wetland_share"] * 20                    # per 5 percentage points
    d["crs_raw"] = (d["crs_best_class"] < 10).astype(float)   # any community in the CRS
    need = ["rain", "climate", "built", "ins_raw", "history", "sm_root_pct", "log_swe",
            "frost_days", "hand_lt5_share", "inc_raw", "pre_raw", "wet_raw", "crs_raw", "ratio"]
    ok = np.isfinite(d[need].to_numpy(float)).all(axis=1)
    print(f"county-months {YEARS[0]}-{YEARS[1]}: {len(d):,}; dropped {(~ok).sum():,} with a missing input")
    d = d[ok].reset_index(drop=True)
    for c in ["ins", "inc", "pre", "wet", "crs"]:               # centre the moderators
        d[c] = d[c + "_raw"] - d[c + "_raw"].mean()
    return d


BG = "sm_root_pct + log_swe + frost_days + hand_lt5_share + C(month)"


def bg(d):
    return BG + (" + C(state)" if d["state"].nunique() > 1 else "")


def fit(formula, d, kind="logit"):
    groups = pd.factorize(d["GEOID"])[0]
    if kind == "logit":
        m = smf.logit(formula, d)
        res = m.fit(disp=0, method="newton", maxiter=100, cov_type="cluster",
                    cov_kwds={"groups": groups})
    elif kind == "ols":
        res = smf.ols(formula, d).fit(cov_type="cluster", cov_kwds={"groups": groups})
    else:                                                     # PPML on dollars
        res = smf.glm(formula, d, family=sm.families.Poisson()).fit(
            cov_type="cluster", cov_kwds={"groups": groups})
    return res


def ame(res, d, change):
    """Average change in predicted probability (logit) when `change(d)` is applied, with a
    delta-method SE. `change` returns a modified copy of the data."""
    di = res.model.data.model_spec
    X0 = np.asarray(patsy.build_design_matrices([di], d)[0])
    X1 = np.asarray(patsy.build_design_matrices([di], change(d.copy()))[0])
    b, V = res.params.to_numpy(), res.cov_params().to_numpy()
    p0, p1 = expit(X0 @ b), expit(X1 @ b)
    effect = (p1 - p0).mean()
    grad = ((p1 * (1 - p1))[:, None] * X1 - (p0 * (1 - p0))[:, None] * X0).mean(axis=0)
    return effect, float(np.sqrt(grad @ V @ grad)), p0.mean(), grad


def ame_diff(res, d, change_a, change_b):
    """Difference between two AMEs (b minus a), with its delta-method SE."""
    ea, _, _, ga = ame(res, d, change_a)
    eb, _, _, gb = ame(res, d, change_b)
    g = gb - ga
    return eb - ea, float(np.sqrt(g @ res.cov_params().to_numpy() @ g))


def setcol(col, value):
    def f(x):
        x[col] = value if not callable(value) else value(x)
        return x
    return f


def plus(col, step=1.0):
    return setcol(col, lambda x: x[col] + step)


def both(f, g):
    return lambda x: g(f(x))


def row(question, outcome, label, est, se, base=None, note=""):
    return dict(question=question, outcome=outcome, effect=label, pts=100 * est, se_pts=100 * se,
                lo=100 * (est - 1.96 * se), hi=100 * (est + 1.96 * se),
                clear=abs(est) > 1.96 * se, base_pct=None if base is None else 100 * base, note=note)


PREP = [("ins", "flood insurance (per 100 homes)"), ("inc", "median income ($10k)"),
        ("pre", "homes built before 1980 (10 pts)"), ("wet", "wetland share (5 pts)"),
        ("crs", "any CRS community (no/yes)")]
NESTED = {"M0": "rain + built", "M1": "rain + built + climate",
          "M2": "rain + built + {P}", "M3": "rain + built + climate + {P}",
          "M4": "rain + built + climate + {P} + {I}"}


def levels(d, c):
    """Low and high values of a centred preparedness measure: 10th/90th percentile, CRS no/yes."""
    raw = d[c + "_raw"]
    if c == "crs":
        return 0.0 - raw.mean(), 1.0 - raw.mean(), "no", "yes"
    a, b = raw.quantile([0.1, 0.9]).to_numpy()
    return a - raw.mean(), b - raw.mean(), f"{a:.2f}", f"{b:.2f}"


def rain_at(res, d, c, lo, hi):
    """Rain effect (+25 mm) with measure c set low, set high, and high minus low (delta SEs)."""
    V = res.cov_params().to_numpy()
    gs = [ame(res, d, f)[3] for f in [setcol(c, lo), both(setcol(c, lo), plus("rain")),
                                     setcol(c, hi), both(setcol(c, hi), plus("rain"))]]
    el, sl = ame_diff(res, d, setcol(c, lo), both(setcol(c, lo), plus("rain")))
    eh, sh = ame_diff(res, d, setcol(c, hi), both(setcol(c, hi), plus("rain")))
    g = (gs[3] - gs[2]) - (gs[1] - gs[0])
    return (el, sl), (eh, sh), (eh - el, float(np.sqrt(g @ V @ g)))


def nested(d, B, out_dir):
    P = " + ".join(c for c, _ in PREP)
    I = " + ".join(f"rain:{c}" for c, _ in PREP)
    forms = {m: f.format(P=P, I=I) for m, f in NESTED.items()}
    eff, coefs, checks, curves = [], [], [], {}
    for y, yname in OUTCOMES.items():
        print(f"\n===== outcome: {yname} (base rate {d[y].mean():.2%})")
        fits = {m: fit(f"{y} ~ {f} + {B}", d) for m, f in forms.items()}
        for m, r in fits.items():
            e, s, base, _ = ame(r, d, plus("rain"))
            eff.append(row(m, y, "rain +25 mm", e, s, base))
            if "climate" in forms[m]:
                e, s, base, _ = ame(r, d, plus("climate"))
                eff.append(row(m, y, "climate +25 mm (same rain)", e, s, base))
            for t in r.params.index:
                if not t.startswith(("C(", "Intercept")):
                    coefs.append(dict(outcome=y, model=m, term=t, coef=r.params[t], se=r.bse[t]))
        e, s, base, _ = ame(fits["M3"], d, plus("built"))
        eff.append(row("M3", y, "built-up area doubled", e, s, base))
        for c, label in PREP:                                   # main effects: reference only
            lo, hi, tl, th = levels(d, c)
            if c == "crs":                                      # switching every county no -> yes
                e, s = ame_diff(fits["M3"], d, setcol(c, lo), setcol(c, hi))
            else:
                e, s, _, _ = ame(fits["M3"], d, plus(c))
            eff.append(row("M3", y, f"{label} +1 step (reference only)", e, s, d[y].mean()))
        for c, label in PREP:                                   # M4: does rain do less harm?
            lo, hi, tl, th = levels(d, c)
            (el, sl), (eh, sh), (df, sd) = rain_at(fits["M4"], d, c, lo, hi)
            eff.append(row("M4", y, f"rain +25 mm, {label} low ({tl})", el, sl, d[y].mean()))
            eff.append(row("M4", y, f"rain +25 mm, {label} high ({th})", eh, sh, d[y].mean()))
            eff.append(row("M4", y, f"difference, {label} high minus low", df, sd, d[y].mean()))
        curves[y] = fits["M4"]

        # ---- checks ----
        o3 = fit(f"{y} ~ {forms['M3']} + {B}", d, "ols")
        o4 = fit(f"{y} ~ {forms['M4']} + {B}", d, "ols")
        o0 = fit(f"{y} ~ {forms['M0']} + {B}", d, "ols")
        for lab, r, t in [("M0 rain +25 mm", o0, "rain"), ("M3 rain +25 mm", o3, "rain"),
                          ("M3 climate +25 mm", o3, "climate"),
                          ("M4 rain x insurance (per 1/100 homes)", o4, "rain:ins")]:
            checks.append(dict(check="linear probability model", outcome=y, measure=lab,
                               pts=100 * r.params[t], se_pts=100 * r.bse[t],
                               clear=abs(r.params[t]) > 1.96 * r.bse[t]))
        for m in ["M0", "M3"]:
            rr = fit(f"{y} ~ {forms[m].replace('rain', 'ratio')} + {B}", d)
            e, s, _, _ = ame(rr, d, plus("ratio"))
            checks.append(dict(check="relative storm (per 0.1 of 10-year level)", outcome=y,
                               measure=f"{m} storm effect", pts=100 * e, se_pts=100 * s, clear=abs(e) > 1.96 * s))
        for m in ["M2", "M3", "M4"]:
            rh = fit(f"{y} ~ {forms[m]} + history + {B}", d)
            e, s, _, _ = ame(rh, d, plus("rain"))
            checks.append(dict(check="flood history added", outcome=y, measure=f"{m} rain +25 mm",
                               pts=100 * e, se_pts=100 * s, clear=abs(e) > 1.96 * s))
            if m == "M4":
                lo, hi, _, _ = levels(d, "ins")
                _, _, (df, sd) = rain_at(rh, d, "ins", lo, hi)
                checks.append(dict(check="flood history added", outcome=y,
                                   measure="M4 rain effect, insurance high minus low",
                                   pts=100 * df, se_pts=100 * sd, clear=abs(df) > 1.96 * sd))

    eff, checks = pd.DataFrame(eff), pd.DataFrame(checks)
    eff.to_csv(os.path.join(out_dir, "effects.csv"), index=False)
    checks.to_csv(os.path.join(out_dir, "checks.csv"), index=False)
    pd.DataFrame(coefs).to_csv(os.path.join(out_dir, "coefs.csv"), index=False)
    show = eff.copy()
    show["effect (pts)"] = [f"{p:+.3f} [{l:+.3f}, {h:+.3f}]{' *' if c else ''}"
                            for p, l, h, c in zip(show.pts, show.lo, show.hi, show.clear)]
    print("\neffects: average change in probability, percentage points [95% interval]; * clear")
    print(show[["question", "outcome", "effect", "effect (pts)", "base_pct"]].round(3).to_string(index=False))
    print("\nchecks:")
    print(checks.round(3).to_string(index=False))
    plot_nested(d, eff, curves, out_dir)


def plot_nested(d, eff, curves, out_dir):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    # 1. rain effect in M0-M4, both outcomes
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
    for ax, (y, yname) in zip(axes, OUTCOMES.items()):
        sub = eff[(eff.outcome == y) & (eff.effect == "rain +25 mm")]
        x = np.arange(len(sub))
        ax.errorbar(x, sub.pts, yerr=[sub.pts - sub.lo, sub.hi - sub.pts], fmt="o", capsize=4, color="#1f5fa8")
        ax.set_xticks(x, sub.question)
        ax.set_ylabel("change in chance (percentage points)")
        ax.set_title(f"Chance of {yname}: effect of 25 mm more rain", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "plot_rain_effect_models.png"), dpi=200)
    plt.close(fig)
    # 2. M4: chance of damage against rain at low and high insurance, others at observed values
    lo, hi, tl, th = levels(d, "ins")
    grid = np.arange(0, 201, 10) / 25
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    for ax, (y, yname) in zip(axes, OUTCOMES.items()):
        r = curves[y]
        di, b = r.model.data.model_spec, r.params.to_numpy()
        for ins, color, lab in [(lo, "#c0504d", f"low insurance ({tl}/100 homes)"),
                                (hi, "#1f5fa8", f"high insurance ({th}/100 homes)")]:
            p = []
            for g in grid:
                x = d.copy()
                x["rain"], x["ins"] = g, ins
                X = np.asarray(patsy.build_design_matrices([di], x)[0])
                p.append(100 * expit(X @ b).mean())
            ax.plot(grid * 25, p, color=color, label=lab)
        ax.set_xlabel("rain in the month's wettest 5 days (mm)")
        ax.set_ylabel(f"chance of {yname} (%)")
        ax.set_title(f"{yname.capitalize()} (M4)", fontsize=10)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "plot_rain_insurance.png"), dpi=200)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default="model_panel.csv")
    ap.add_argument("--state")
    ap.add_argument("--design", choices=["questions", "nested"], default="questions",
                    help="questions: the four-question design; nested: the course design M0-M4")
    ap.add_argument("--out-dir", default="results/causal_midwest")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    sys.stdout = Tee(sys.__stdout__, open(os.path.join(args.out_dir, "log.txt"), "w"))
    pd.set_option("display.width", 200)
    print(f"causal_model.py {' '.join(sys.argv[1:])}")

    d = load(args.panel, args.state)
    B = bg(d)
    if args.design == "nested":
        print(f"rows {len(d):,}, counties {d['GEOID'].nunique()}; any damage {d['any'].mean():.2%}, "
              f"loss $100k+ {d['major'].mean():.2%}")
        print("preparedness (raw) means and 10th/90th pct:")
        for c, label in PREP:
            r = d[c + "_raw"]
            print(f"  {label}: mean {r.mean():.3f}, p10 {r.quantile(.1):.3f}, p90 {r.quantile(.9):.3f}")
        print("correlations among preparedness measures:")
        print(d[[c + "_raw" for c, _ in PREP]].corr().round(2).to_string())
        nested(d, B, args.out_dir)
        print(f"\nresults in {args.out_dir}")
        return
    q10, q90 = d["ins_raw"].quantile([0.1, 0.9]).to_numpy()
    lo, hi = q10 - d["ins_raw"].mean(), q90 - d["ins_raw"].mean()
    print(f"rows {len(d):,}, counties {d['GEOID'].nunique()}; any damage {d['any'].mean():.2%}, "
          f"loss $100k+ {d['major'].mean():.2%}")
    print(f"insurance per 100 homes: mean {d['ins_raw'].mean():.2f}, 10th pct {q10:.2f}, 90th pct {q90:.2f}")
    print("means:", d[["rx5", "c_rx5_rl10_mm", "built", "history"]].mean().round(2).to_dict())

    eff, coefs, checks = [], [], []
    for y, yname in OUTCOMES.items():
        print(f"\n===== outcome: {yname}")
        # Q1 / Q2: one model, read for rain and for climate
        r0 = fit(f"{y} ~ rain", d)
        r1 = fit(f"{y} ~ rain + climate + built + {B}", d)
        e, s, base, _ = ame(r0, d, plus("rain"))
        eff.append(row("Q1", y, "rain +25 mm, no controls", e, s, base))
        e, s, base, _ = ame(r1, d, plus("rain"))
        eff.append(row("Q1", y, "rain +25 mm, controlled", e, s, base))
        e, s, base, _ = ame(r1, d, plus("climate"))
        eff.append(row("Q2", y, "climate +25 mm (same rain)", e, s, base))
        # Q3: rain x insurance with flood history
        r3 = fit(f"{y} ~ rain * ins + climate + history + built + {B}", d)
        base = d[y].mean()
        # rain effect at a fixed insurance level = AME of (set ins, +rain) minus AME of (set ins)
        el, sl = ame_diff(r3, d, setcol("ins", lo), both(setcol("ins", lo), plus("rain")))
        eh, sh = ame_diff(r3, d, setcol("ins", hi), both(setcol("ins", hi), plus("rain")))
        eff.append(row("Q3", y, f"rain +25 mm, low insurance ({q10:.2f}/100 homes)", el, sl, base))
        eff.append(row("Q3", y, f"rain +25 mm, high insurance ({q90:.2f}/100 homes)", eh, sh, base))
        # difference: (hi,+rain - hi) - (lo,+rain - lo)
        V = r3.cov_params().to_numpy()
        gs = [ame(r3, d, f)[3] for f in [setcol("ins", lo), both(setcol("ins", lo), plus("rain")),
                                        setcol("ins", hi), both(setcol("ins", hi), plus("rain"))]]
        g = (gs[3] - gs[2]) - (gs[1] - gs[0])
        eff.append(row("Q3", y, "difference, high minus low insurance", eh - el,
                       float(np.sqrt(g @ V @ g)), base))
        e, s, base, _ = ame(r3, d, plus("ins"))
        eff.append(row("Q3", y, "insurance +1 per 100 homes (reference only)", e, s, base))
        e, s, base, _ = ame(r3, d, plus("history", 1.0))
        eff.append(row("Q3", y, "flood history +1 damaged month a year", e, s, base))
        # Q4: built-up area
        r4 = fit(f"{y} ~ built + climate + {B}", d)
        e, s, base, _ = ame(r4, d, plus("built"))
        eff.append(row("Q4", y, "built-up area doubled", e, s, base))
        for name, r in [("Q1/Q2", r1), ("Q3", r3), ("Q4", r4)]:
            for t in r.params.index:
                if not t.startswith(("C(", "Intercept")):
                    coefs.append(dict(outcome=y, model=name, term=t, coef=r.params[t], se=r.bse[t]))
        print(f"Q3 coefficient rain:ins = {r3.params['rain:ins']:+.4f} (SE {r3.bse['rain:ins']:.4f})")

        # ---- checks ----
        # (a) other preparedness measures in place of insurance
        for c, label, step_lo, step_hi in [
                ("inc", "median income ($10k)", None, None), ("pre", "homes before 1980 (10 pts)", None, None),
                ("wet", "wetland share (5 pts)", None, None), ("crs", "any CRS community (no/yes)", 0.0, 1.0)]:
            raw = d[c + "_raw"]
            if c == "crs":
                a, bb = step_lo - raw.mean(), step_hi - raw.mean()
                tag = ("no", "yes")
            else:
                a, bb = raw.quantile(0.1) - raw.mean(), raw.quantile(0.9) - raw.mean()
                tag = ("10th pct", "90th pct")
            rc = fit(f"{y} ~ rain * {c} + climate + history + built + {B}", d)
            el2, _ = ame_diff(rc, d, setcol(c, a), both(setcol(c, a), plus("rain")))
            eh2, _ = ame_diff(rc, d, setcol(c, bb), both(setcol(c, bb), plus("rain")))
            gs = [ame(rc, d, f)[3] for f in [setcol(c, a), both(setcol(c, a), plus("rain")),
                                            setcol(c, bb), both(setcol(c, bb), plus("rain"))]]
            g = (gs[3] - gs[2]) - (gs[1] - gs[0])
            sd = float(np.sqrt(g @ rc.cov_params().to_numpy() @ g))
            checks.append(dict(check="Q3 other preparedness", outcome=y, measure=label,
                               low=f"{tag[0]}: {100 * el2:.2f} pts", high=f"{tag[1]}: {100 * eh2:.2f} pts",
                               diff_pts=100 * (eh2 - el2), se_pts=100 * sd, clear=abs(eh2 - el2) > 1.96 * sd))
        # (b) linear probability model
        o1 = fit(f"{y} ~ rain + climate + built + {B}", d, "ols")
        o3 = fit(f"{y} ~ rain * ins + climate + history + built + {B}", d, "ols")
        for lab, est, se in [("Q1 rain +25 mm", o1.params["rain"], o1.bse["rain"]),
                             ("Q2 climate +25 mm", o1.params["climate"], o1.bse["climate"]),
                             ("Q3 rain x insurance (per 1/100 homes)", o3.params["rain:ins"], o3.bse["rain:ins"])]:
            checks.append(dict(check="linear probability model", outcome=y, measure=lab,
                               diff_pts=100 * est, se_pts=100 * se, clear=abs(est) > 1.96 * se))
        # (c) storm relative to the 10-year level (course design), per 0.1
        rr = fit(f"{y} ~ ratio + climate + built + {B}", d)
        e, s, _, _ = ame(rr, d, plus("ratio"))
        checks.append(dict(check="relative storm (per 0.1 of 10-year level)", outcome=y,
                           measure="Q1 storm effect", diff_pts=100 * e, se_pts=100 * s, clear=abs(e) > 1.96 * s))
        e, s, _, _ = ame(rr, d, plus("climate"))
        checks.append(dict(check="relative storm (per 0.1 of 10-year level)", outcome=y,
                           measure="Q2 climate +25 mm", diff_pts=100 * e, se_pts=100 * s, clear=abs(e) > 1.96 * s))

    # (d) expected dollars (PPML): % change in expected loss
    for lab, f, term in [("Q1 rain +25 mm", f"PropertyDmgADJ ~ rain + climate + built + {B}", "rain"),
                         ("Q2 climate +25 mm", f"PropertyDmgADJ ~ rain + climate + built + {B}", "climate"),
                         ("Q3 rain x insurance (per 1/100 homes)",
                          f"PropertyDmgADJ ~ rain * ins + climate + history + built + {B}", "rain:ins"),
                         ("Q4 built-up doubled", f"PropertyDmgADJ ~ built + climate + {B}", "built")]:
        rp = fit(f, d, "ppml")
        b, s = rp.params[term], rp.bse[term]
        checks.append(dict(check="expected dollars (PPML), % change", outcome="dollars", measure=lab,
                           diff_pts=100 * (np.exp(b) - 1), se_pts=100 * s * np.exp(b),
                           clear=abs(b) > 1.96 * s))
    mean_loss = d["PropertyDmgADJ"].mean()
    print(f"\nmean loss per county-month ${mean_loss:,.0f}")

    eff, checks = pd.DataFrame(eff), pd.DataFrame(checks)
    eff.to_csv(os.path.join(args.out_dir, "effects.csv"), index=False)
    checks.to_csv(os.path.join(args.out_dir, "checks.csv"), index=False)
    pd.DataFrame(coefs).to_csv(os.path.join(args.out_dir, "coefs.csv"), index=False)
    show = eff.copy()
    show["effect (pts)"] = [f"{p:+.2f} [{l:+.2f}, {h:+.2f}]{' *' if c else ''}"
                            for p, l, h, c in zip(show.pts, show.lo, show.hi, show.clear)]
    print("\neffects: average change in probability, percentage points [95% interval]; * clear")
    print(show[["question", "outcome", "effect", "effect (pts)", "base_pct"]].round(3).to_string(index=False))
    print("\nchecks:")
    print(checks.round(3).to_string(index=False))

    plot(d, args.out_dir, B, lo, hi, q10, q90)
    print(f"\nresults in {args.out_dir}")


def plot(d, out_dir, B, lo, hi, q10, q90):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    grid = np.arange(0, 201, 10) / 25
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    for ax, (y, yname) in zip(axes, OUTCOMES.items()):
        r = fit(f"{y} ~ rain * ins + climate + history + built + {B}", d)
        di, b = r.model.data.model_spec, r.params.to_numpy()
        for ins, color, lab in [(lo, "#c0504d", f"low insurance ({q10:.2f}/100 homes)"),
                                (hi, "#1f5fa8", f"high insurance ({q90:.2f}/100 homes)")]:
            p = []
            for g in grid:
                x = d.copy()
                x["rain"], x["ins"] = g, ins
                X = np.asarray(patsy.build_design_matrices([di], x)[0])
                p.append(100 * expit(X @ b).mean())
            ax.plot(grid * 25, p, color=color, label=lab)
        ax.set_xlabel("rain in the month's wettest 5 days (mm)")
        ax.set_ylabel(f"chance of {yname} (%)")
        ax.set_title(yname.capitalize(), fontsize=10)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "plot_rain_insurance.png"), dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    main()
