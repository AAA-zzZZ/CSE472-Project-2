"""
Step 2b: Compute county x month hazard (W) indices from the county-daily PRISM CSVs.

Input : folder of prism_county_daily_<YEAR>.csv (GEOID, date, ppt, tmin), 1981-2023
Output: w_county_month.csv     one row per county x month, model years only (default 2000-2023)
        w_county_thresholds.csv per-county baseline thresholds (p95, p99, GEV return levels)

Usage:
    pip install pandas numpy scipy
    python w_indices.py --input prism_csvs/ --out-dir out/

Leakage rules followed here:
  * All thresholds (wet-day p95/p99, GEV return levels, SPI distributions) are fitted on the
    baseline period only (default 1981-1999), never on model years.
  * "Prior-month" features (spi1_prev, spi2_prev, frost_days_prev) use only months before the target.
  * Same-month features (p_month, rx*, n_gt_p95, ...) describe the realized hazard in the target month,
    which is how the W block is defined in the plan.

Variables produced (county x month):
  p_month          monthly precipitation total (mm)
  rx1, rx3, rx5    max 1/3/5-day precipitation (mm); multi-day windows are assigned to the month
                   in which they end (ETCCDI convention), so they can span a month boundary
  n_gt_p95/p99     days above the county's baseline wet-day (>=1 mm) 95th/99th percentile
  rx5_gt_rl10      1 if rx5 exceeds the county's baseline 10-year Rx5day return level
  rx5_rl_ratio     rx5 / 10-year return level (continuous version of the flag)
  frost_days       days with Tmin < 0 C in the month
  frost_days_prev  frost days in the previous month (frozen-ground signal)
  spi1_prev        SPI of the previous month's precipitation (gamma, baseline-fitted)
  spi2_prev        SPI of the 2-month total ending in the previous month

Note: the method plan suggests a 1895-1999 SPI baseline from PRISM monthly (ANm). This script
uses the daily record (1981-1999) so everything comes from one export; swap in ANm later
if you want the longer baseline. 19 years is also short for GEV fits; the 25-year level in
particular is an extrapolation and should be treated as rough.
"""

import argparse
import glob
import os
import warnings

import numpy as np
import pandas as pd
from scipy import stats

WET_DAY_MM = 1.0


def load_daily(folder):
    files = sorted(glob.glob(os.path.join(folder, "*.csv")))
    if not files:
        raise SystemExit(f"no CSV files in {folder}")
    df = pd.concat((pd.read_csv(f, dtype={"GEOID": str}) for f in files), ignore_index=True)
    df["GEOID"] = df["GEOID"].str.zfill(5)
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(["GEOID", "date"]).sort_values(["GEOID", "date"]).reset_index(drop=True)
    return df


def check_completeness(df):
    """Warn about missing days, which would break the rolling windows."""
    span = df.groupby("GEOID")["date"].agg(["min", "max", "count"])
    expected = (span["max"] - span["min"]).dt.days + 1
    gaps = span[span["count"] < expected]
    if len(gaps):
        warnings.warn(f"{len(gaps)} counties have missing days; rolling sums are reindexed to fill them with NaN")
    na = df[["ppt", "tmin"]].isna().mean()
    if na.max() > 0:
        warnings.warn(f"share of missing values: {na.to_dict()}")


def add_rolling(df):
    """3- and 5-day trailing precipitation sums per county on a complete daily index."""
    out = []
    for geoid, g in df.groupby("GEOID", sort=False):
        g = g.set_index("date").asfreq("D")
        g["GEOID"] = geoid
        g["ppt3"] = g["ppt"].rolling(3, min_periods=3).sum()
        g["ppt5"] = g["ppt"].rolling(5, min_periods=5).sum()
        out.append(g.reset_index())
    return pd.concat(out, ignore_index=True)


def fit_gev_levels(annual_max, periods=(2, 10, 25)):
    """GEV return levels from annual maxima; falls back to Gumbel if the GEV fit is unstable."""
    x = np.asarray(annual_max, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 10:
        return {f"rl{T}": np.nan for T in periods}
    probs = [1 - 1 / T for T in periods]
    try:
        c, loc, scale = stats.genextreme.fit(x)
        if not (-0.5 < c < 0.5) or scale <= 0:   # implausible shape for 19 points
            raise ValueError
        levels = stats.genextreme.ppf(probs, c, loc, scale)
    except Exception:
        loc, scale = stats.gumbel_r.fit(x)
        levels = stats.gumbel_r.ppf(probs, loc, scale)
    return {f"rl{T}": float(v) for T, v in zip(periods, levels)}


def baseline_thresholds(daily, monthly, base_start, base_end):
    """Per-county thresholds fitted on baseline years only."""
    b = daily[daily["date"].dt.year.between(base_start, base_end)]
    wet = b[b["ppt"] >= WET_DAY_MM]
    pct = wet.groupby("GEOID")["ppt"].quantile([0.95, 0.99]).unstack()
    pct.columns = ["p95", "p99"]

    bm = monthly[monthly["year"].between(base_start, base_end)]
    ann_rx5 = bm.groupby(["GEOID", "year"])["rx5"].max()
    rl = ann_rx5.groupby("GEOID").apply(lambda s: pd.Series(fit_gev_levels(s.values))).unstack()
    return pct.join(rl, how="outer")


def spi_gamma(values, base_mask):
    """SPI for one county x calendar-month series, gamma fitted on baseline values (zeros handled)."""
    v = np.asarray(values, dtype=float)
    base = v[base_mask & np.isfinite(v)]
    out = np.full_like(v, np.nan)
    if len(base) < 10:
        return out
    q = np.mean(base <= 0)                        # probability of a zero total
    pos = base[base > 0]
    if len(pos) < 5:
        return out
    a, _, sc = stats.gamma.fit(pos, floc=0)
    ok = np.isfinite(v)
    cdf = q + (1 - q) * stats.gamma.cdf(np.clip(v[ok], 0, None), a, loc=0, scale=sc)
    out[ok] = stats.norm.ppf(np.clip(cdf, 0.001, 0.999))
    return out


def add_spi(monthly, base_start, base_end):
    m = monthly.sort_values(["GEOID", "year", "month"]).copy()
    m["p2"] = m.groupby("GEOID")["p_month"].transform(lambda s: s.rolling(2, min_periods=2).sum())
    base = m["year"].between(base_start, base_end).to_numpy()
    for src, dst in [("p_month", "spi1"), ("p2", "spi2")]:
        m[dst] = np.nan
        for _, idx in m.groupby(["GEOID", "month"]).groups.items():
            idx = np.asarray(idx)
            m.loc[idx, dst] = spi_gamma(m.loc[idx, src].to_numpy(), base[m.index.get_indexer(idx)])
    # Shift to "previous month" so only information before the target month is used.
    g = m.groupby("GEOID")
    m["spi1_prev"] = g["spi1"].shift(1)
    m["spi2_prev"] = g["spi2"].shift(1)
    return m.drop(columns=["p2", "spi1", "spi2"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="folder with prism_county_daily_*.csv")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--base-start", type=int, default=1981)
    ap.add_argument("--base-end", type=int, default=1999)
    ap.add_argument("--model-start", type=int, default=2000)
    ap.add_argument("--model-end", type=int, default=2023)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    daily = load_daily(args.input)
    check_completeness(daily)
    daily = add_rolling(daily)
    daily["year"] = daily["date"].dt.year
    daily["month"] = daily["date"].dt.month
    daily["frost"] = (daily["tmin"] < 0).astype(float).where(daily["tmin"].notna())

    keys = ["GEOID", "year", "month"]
    monthly = daily.groupby(keys).agg(
        p_month=("ppt", "sum"),
        rx1=("ppt", "max"),
        rx3=("ppt3", "max"),
        rx5=("ppt5", "max"),
        frost_days=("frost", "sum"),
        n_days=("ppt", "count"),
    ).reset_index()

    thr = baseline_thresholds(daily, monthly, args.base_start, args.base_end)

    # Days above the county's baseline wet-day percentiles.
    d = daily.merge(thr[["p95", "p99"]], left_on="GEOID", right_index=True, how="left")
    d["gt95"] = (d["ppt"] > d["p95"]).astype(int)
    d["gt99"] = (d["ppt"] > d["p99"]).astype(int)
    exc = d.groupby(keys)[["gt95", "gt99"]].sum().rename(columns={"gt95": "n_gt_p95", "gt99": "n_gt_p99"})
    monthly = monthly.merge(exc, left_on=keys, right_index=True, how="left")

    monthly = monthly.merge(thr[["rl10"]], left_on="GEOID", right_index=True, how="left")
    monthly["rx5_gt_rl10"] = (monthly["rx5"] > monthly["rl10"]).astype(int)
    monthly["rx5_rl_ratio"] = monthly["rx5"] / monthly["rl10"]

    monthly = monthly.sort_values(keys)
    monthly["frost_days_prev"] = monthly.groupby("GEOID")["frost_days"].shift(1)
    monthly = add_spi(monthly, args.base_start, args.base_end)

    out = monthly[monthly["year"].between(args.model_start, args.model_end)]
    short = out[out["n_days"] < out.apply(lambda r: pd.Period(f"{r.year}-{r.month}").days_in_month, axis=1)]
    if len(short):
        warnings.warn(f"{len(short)} county-months have incomplete daily data (see n_days)")

    cols = ["GEOID", "year", "month", "p_month", "rx1", "rx3", "rx5", "n_gt_p95", "n_gt_p99",
            "rx5_gt_rl10", "rx5_rl_ratio", "frost_days", "frost_days_prev", "spi1_prev", "spi2_prev", "n_days"]
    out[cols].to_csv(os.path.join(args.out_dir, "w_county_month.csv"), index=False, float_format="%.4f")
    thr.to_csv(os.path.join(args.out_dir, "w_county_thresholds.csv"), float_format="%.4f")
    print(f"wrote {len(out):,} county-months for {out['GEOID'].nunique()} counties to {args.out_dir}")


if __name__ == "__main__":
    main()