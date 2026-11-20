"""
Step 2b: Compute county x month hazard (W) indices from county-daily rainfall and Tmin.

Input : folder of yearly county-daily files (.csv or .csv.gz) with columns GEOID, date, ppt, tmin.
        Made by prep_nclimgrid.py from NOAA nClimGrid-Daily (1951-2023).
        The older PRISM exports (prism_county_daily_YYYY.csv) also work; use --base-start 1981.
Output: w_county_month.csv      one row per county x month, model years only (default 2000-2023)
        w_county_thresholds.csv per-county baseline thresholds (p95, p99, GEV return levels)

Usage:
    pip install pandas numpy scipy
    python w_indices.py --input data/nclimgrid_midwest --out-dir out/

Leakage rules followed here:
  * All thresholds (wet-day p95/p99, GEV return levels, SPI distributions) are fitted on the
    baseline period only (default 1951-1999), never on model years.
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
  n_days           days with data in the month (check for gaps)

Method notes: SPI uses the standard Thom (1958) gamma estimator with a zero-probability term;
return levels come from a GEV fit to baseline annual Rx5day maxima (Gumbel if the fit is unstable).
"""

import argparse
import glob
import os
import time
import warnings

import numpy as np
import pandas as pd
from scipy import stats

WET_DAY_MM = 1.0


def log(msg, t0=[time.time()]):
    """Print a progress message prefixed with seconds elapsed since the script started.

    No math beyond elapsed = now - t0. The mutable default t0 is evaluated once at import,
    so every call measures from the same start time.
    """
    print(f"[{time.time() - t0[0]:6.0f}s] {msg}", flush=True)


def load_wide(folder):
    """Read all yearly files and return two day x county tables (ppt, tmin) on a complete daily index.

    Calculation:
      1. Each yearly file is long format (one row per GEOID x date). It is pivoted to a wide
         table where rows = days and columns = counties, so cell [d, g] = value for county g on day d.
      2. The yearly tables are stacked in time, duplicate days dropped, and sorted.
      3. The table is reindexed onto every calendar day from first to last date, so a missing
         day shows up as NaN instead of silently disappearing. This matters later because the
         rolling 3/5-day sums assume consecutive rows are consecutive days.
      4. Gap rate = mean over all cells of isna(), i.e. (# missing county-days) / (# county-days).
    """
    files = sorted(glob.glob(os.path.join(folder, "*.csv")) + glob.glob(os.path.join(folder, "*.csv.gz")))
    if not files:
        raise SystemExit(f"no .csv or .csv.gz files in {folder}")
    # Pivot each file to day x county as it is read, so the long table never exists in full.
    ppt_parts, tmin_parts = [], []
    n_rows = 0
    for f in files:
        df = pd.read_csv(f, dtype={"GEOID": str, "ppt": "float32", "tmin": "float32"},
                         usecols=["GEOID", "date", "ppt", "tmin"])
        df["GEOID"] = df["GEOID"].str.zfill(5)
        df["date"] = pd.to_datetime(df["date"])
        df = df.drop_duplicates(["GEOID", "date"])
        n_rows += len(df)
        ppt_parts.append(df.pivot(index="date", columns="GEOID", values="ppt"))
        tmin_parts.append(df.pivot(index="date", columns="GEOID", values="tmin"))
        del df
    ppt = pd.concat(ppt_parts).astype("float32")
    tmin = pd.concat(tmin_parts).astype("float32")
    del ppt_parts, tmin_parts
    ppt = ppt[~ppt.index.duplicated()].sort_index()
    tmin = tmin[~tmin.index.duplicated()].sort_index()
    days = pd.date_range(ppt.index.min(), ppt.index.max(), freq="D")
    ppt, tmin = ppt.reindex(days), tmin.reindex(days)
    log(f"read {len(files)} files, {n_rows:,} rows, {ppt.shape[1]} counties, "
        f"{days[0]:%Y-%m-%d} to {days[-1]:%Y-%m-%d}")
    gap = ppt.isna().mean().mean()
    if gap > 0:
        warnings.warn(f"{gap:.3%} of county-days are missing (gaps are left as NaN)")
    return ppt.astype("float32"), tmin.astype("float32")


def fit_gev_levels(annual_max, periods=(2, 10, 25)):
    """GEV return levels from annual maxima; falls back to Gumbel if the GEV fit is unstable.

    Input is one county's baseline annual maxima (e.g. the largest 5-day rainfall in each year).
    Extreme value theory says block maxima follow a Generalized Extreme Value distribution:
        F(x) = exp( -[1 + xi * (x - mu) / sigma]^(-1/xi) )
    with location mu, scale sigma > 0 and shape xi. (scipy's shape c = -xi.)

    The T-year return level is the amount exceeded on average once every T years, i.e. with
    probability 1/T in any year. So it is the quantile at non-exceedance probability p = 1 - 1/T:
        RL_T = F^-1(1 - 1/T)        e.g. T=10 -> 90th percentile of the annual-max distribution.

    Steps:
      * Drop non-finite values; need >= 10 years or return NaN (too few to fit 3 parameters).
      * Fit (c, loc, scale) by maximum likelihood.
      * If |c| >= 0.5 or scale <= 0 the fit is treated as unstable (heavy-tailed shapes blow up
        the long return levels), and a Gumbel is fitted instead. Gumbel is the GEV with xi = 0:
            F(x) = exp( -exp( -(x - mu) / sigma ) )
      * Return F^-1(1 - 1/T) for each T in periods (default 2, 10, 25 years).
    """
    x = np.asarray(annual_max, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) < 10:
        return [np.nan] * len(periods)
    probs = [1 - 1 / T for T in periods]
    try:
        c, loc, scale = stats.genextreme.fit(x)
        if not (-0.5 < c < 0.5) or scale <= 0:
            raise ValueError
        return list(stats.genextreme.ppf(probs, c, loc, scale))
    except Exception:
        loc, scale = stats.gumbel_r.fit(x)
        return list(stats.gumbel_r.ppf(probs, loc, scale))


def spi_wide(p, base_mask):
    """SPI for a month x county table, fitted separately for each calendar month on baseline rows.

    SPI (Standardized Precipitation Index) converts a precipitation total into a z-score:
    how unusually wet or dry it is compared with the same calendar month in the baseline.
    SPI = 0 is normal, +2 is very wet, -2 is very dry.

    For each calendar month m (so Januaries are compared only with Januaries) and each county:
      1. Take the baseline values for month m (one per baseline year).
      2. Zero probability: q = (# baseline years with 0 precipitation) / (# valid baseline years).
         The gamma distribution only covers x > 0, so dry months are handled separately.
      3. Fit a gamma distribution to the positive values with Thom's (1958) estimator:
             A     = ln(mean(x)) - mean(ln(x))
             alpha = (1 + sqrt(1 + 4A/3)) / (4A)       shape
             beta  = mean(x) / alpha                   scale
      4. Mixed CDF for every year (baseline and model years) using the baseline fit:
             H(x) = q + (1 - q) * G(x; alpha, beta)
         where G is the gamma CDF (G(0) = 0, so a dry month gets H = q).
      5. Transform the probability to a standard normal z-score:
             SPI = Phi^-1(H)
         H is clipped to [0.001, 0.999] first, so SPI stays within about +/-3.09.
      6. A county-month is set to NaN if there are fewer than 10 baseline years, fewer than 5
         positive baseline values, or alpha is invalid; and wherever the input value is NaN.

    Passing 1-month totals gives SPI-1; passing rolling 2-month totals gives SPI-2.
    """
    out = pd.DataFrame(np.nan, index=p.index, columns=p.columns, dtype="float64")
    for m in range(1, 13):
        rows = p.index.month == m
        sub = p[rows].to_numpy(dtype="float64")                 # years x counties
        base = sub[base_mask[rows]]
        valid = np.isfinite(base)
        n = valid.sum(0)
        q = np.where(n > 0, ((base <= 0) & valid).sum(0) / np.maximum(n, 1), np.nan)
        pos = np.where(valid & (base > 0), base, np.nan)
        with np.errstate(invalid="ignore", divide="ignore"):
            mean = np.nanmean(pos, 0)
            A = np.log(mean) - np.nanmean(np.log(pos), 0)
            alpha = (1 + np.sqrt(1 + 4 * A / 3)) / (4 * A)
            beta = mean / alpha
            ok = (np.isfinite(pos).sum(0) >= 5) & (n >= 10) & np.isfinite(alpha) & (alpha > 0)
            cdf = q + (1 - q) * stats.gamma.cdf(np.clip(sub, 0, None), alpha, scale=beta)
            z = stats.norm.ppf(np.clip(cdf, 0.001, 0.999))
        z[:, ~ok] = np.nan
        z[~np.isfinite(sub)] = np.nan
        out.loc[rows] = z
    return out


def main():
    """Build every W variable for every county x month and write the two output CSVs.

    Calculations (per county g, month t, day d; P_d = daily precipitation, T_d = daily Tmin):
      p_month      = sum of P_d over days in t
      rx1          = max over days in t of P_d
      rx3, rx5     = max over days in t of the trailing k-day sum S_d = P_{d-k+1} + ... + P_d
                     (k = 3 or 5); a window is assigned to the month of its last day
      frost_days   = count of days in t with T_d < 0 C
      n_days       = count of days in t with non-missing P_d
      p95, p99     = 95th / 99th percentile of baseline wet days (P_d >= 1 mm) for county g
      n_gt_p95/p99 = count of days in t with P_d > p95 (or p99)
      rl10         = 10-year return level from a GEV fit to baseline annual max of S_d (k = 5)
      rx5_gt_rl10  = 1 if rx5 > rl10 else 0
      rx5_rl_ratio = rx5 / rl10    (> 1 means a worse-than-10-year 5-day event)
      spi1_prev    = SPI of p_month in month t-1
      spi2_prev    = SPI of (p_month_{t-2} + p_month_{t-1}), the 2-month total ending in t-1
      frost_days_prev = frost_days in month t-1
    The "_prev" features are shifted one month so they only use information before month t.
    All thresholds (p95, p99, rl10, SPI fits) use baseline years only; output keeps model years only.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="folder of yearly county-daily files")
    ap.add_argument("--out-dir", default=".")
    ap.add_argument("--base-start", type=int, default=1951)
    ap.add_argument("--base-end", type=int, default=1999)
    ap.add_argument("--model-start", type=int, default=2000)
    ap.add_argument("--model-end", type=int, default=2023)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    # ppt = daily precipitation averaged over a county in milimeters 
    # tmin = daily minimum temp averaged over a county in celcius
    ppt, tmin = load_wide(args.input)
    if ppt.index.year.min() > args.base_start:
        warnings.warn(f"data start in {ppt.index.year.min()}, after --base-start {args.base_start}; "
                      f"the baseline will be shorter than requested")
    base_days = (ppt.index.year >= args.base_start) & (ppt.index.year <= args.base_end)

    # Daily -> monthly
    ppt3 = ppt.rolling(3, min_periods=3).sum()
    ppt5 = ppt.rolling(5, min_periods=5).sum()
    frost = (tmin < 0).astype("float32").where(tmin.notna())
    M = {
        "p_month": ppt.resample("MS").sum(min_count=1),
        "rx1": ppt.resample("MS").max(),
        "rx3": ppt3.resample("MS").max(),
        "rx5": ppt5.resample("MS").max(),
        "frost_days": frost.resample("MS").sum(min_count=1),
        "n_days": ppt.notna().resample("MS").sum(),
    }
    del ppt3, frost
    log("monthly totals and Rx done")

    # Baseline thresholds
    wet = ppt[base_days].where(ppt[base_days] >= WET_DAY_MM)
    p95, p99 = wet.quantile(0.95), wet.quantile(0.99)
    del wet
    M["n_gt_p95"] = ppt.gt(p95, axis=1).resample("MS").sum()
    M["n_gt_p99"] = ppt.gt(p99, axis=1).resample("MS").sum()

    rx5_annual = ppt5[base_days].resample("YS").max()
    del ppt5
    rl = pd.DataFrame({g: fit_gev_levels(rx5_annual[g].to_numpy()) for g in rx5_annual.columns},
                      index=["rl2", "rl10", "rl25"]).T
    thr = pd.concat([p95.rename("p95"), p99.rename("p99"), rl], axis=1)
    thr.index.name = "GEOID"
    M["rx5_gt_rl10"] = M["rx5"].gt(thr["rl10"], axis=1).astype(int)
    M["rx5_rl_ratio"] = M["rx5"].div(thr["rl10"], axis=1)
    log("thresholds and return levels done")

    # SPI and prior-month features
    base_months = (M["p_month"].index.year >= args.base_start) & (M["p_month"].index.year <= args.base_end)
    p2 = M["p_month"].rolling(2, min_periods=2).sum()
    M["spi1_prev"] = spi_wide(M["p_month"], base_months).shift(1)
    M["spi2_prev"] = spi_wide(p2, base_months).shift(1)
    M["frost_days_prev"] = M["frost_days"].shift(1)
    log("SPI done")

    # Wide -> long, model years only
    cols = ["p_month", "rx1", "rx3", "rx5", "n_gt_p95", "n_gt_p99", "rx5_gt_rl10", "rx5_rl_ratio",
            "frost_days", "frost_days_prev", "spi1_prev", "spi2_prev", "n_days"]
    keep = (M["p_month"].index.year >= args.model_start) & (M["p_month"].index.year <= args.model_end)
    long = pd.concat({c: M[c][keep].stack(future_stack=True) for c in cols}, axis=1)
    long.index.names = ["date", "GEOID"]
    long = long.reset_index()
    long["year"] = long["date"].dt.year
    long["month"] = long["date"].dt.month
    long = long[["GEOID", "year", "month"] + cols].sort_values(["GEOID", "year", "month"])

    short = long["n_days"] < pd.to_datetime(dict(year=long.year, month=long.month, day=1)).dt.days_in_month
    if short.any():
        warnings.warn(f"{short.sum()} county-months have incomplete daily data (see n_days)")

    long.to_csv(os.path.join(args.out_dir, "w_county_month.csv"), index=False, float_format="%.4f")
    thr.to_csv(os.path.join(args.out_dir, "w_county_thresholds.csv"), float_format="%.4f")
    log(f"wrote {len(long):,} county-months for {long['GEOID'].nunique()} counties to {args.out_dir}")


if __name__ == "__main__":
    main()