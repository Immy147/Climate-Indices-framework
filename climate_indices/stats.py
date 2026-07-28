"""
stats.py — Descriptive statistics, temporal aggregation (seasonal/monthly),
and trend analysis (linear regression, Sen's slope, Mann-Kendall test) for
climate index DataArrays.

Trend functions operate per-gridcell via xr.apply_ufunc(vectorize=True).
This is a Python-level loop under the hood (pymannkendall/scipy don't
vectorize across grid cells natively), so it's the slowest step in the
pipeline for large grids -- see `subsample` args below to keep iteration
fast while developing, then run the full grid once you trust the logic.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import xarray as xr
from scipy import stats as scipy_stats

logger = logging.getLogger("climate_indices.stats")

try:
    import pymannkendall as mk
    _HAS_MK = True
except ImportError:
    _HAS_MK = False
    logger.warning("pymannkendall not installed -- mann_kendall_trend() will raise if called.")


# ---------------------------------------------------------------------------
# Descriptive statistics
# ---------------------------------------------------------------------------

def summary_stats(
    da: xr.DataArray,
    dim: str = "time",
    percentiles: tuple[float, ...] = (5, 25, 50, 75, 95),
) -> xr.Dataset:
    """Mean/median/min/max/std/var/percentiles, reduced over `dim`.

    Returns a Dataset with one variable per statistic (each with `dim`
    removed, so e.g. for dim="time" you get 2D lat/lon maps).
    """
    out = xr.Dataset(
        {
            "mean": da.mean(dim=dim, skipna=True),
            "median": da.median(dim=dim, skipna=True),
            "min": da.min(dim=dim, skipna=True),
            "max": da.max(dim=dim, skipna=True),
            "std": da.std(dim=dim, skipna=True),
            "var": da.var(dim=dim, skipna=True),
        }
    )
    if percentiles:
        q = da.quantile([p / 100 for p in percentiles], dim=dim, skipna=True)
        for p in percentiles:
            out[f"p{p}"] = q.sel(quantile=p / 100, drop=True)
    return out


# ---------------------------------------------------------------------------
# Temporal aggregation
# ---------------------------------------------------------------------------

def annual_mean(da: xr.DataArray) -> xr.DataArray:
    """Annual mean, with a real datetime `time` coordinate (Jan-1 per year)
    rather than a bare integer `year`, so it merges cleanly with other
    annual-frequency variables (e.g. xclim-derived indices).
    """
    out = da.groupby("time.year").mean(dim="time", skipna=True)
    out = out.rename(year="time")
    years = out["time"].values.astype(int)
    new_time = pd.to_datetime([f"{y}-01-01" for y in years])
    out = out.assign_coords(time=new_time)
    return out


def seasonal_climatology(da: xr.DataArray) -> xr.DataArray:
    """Mean by meteorological season (DJF/MAM/JJA/SON), collapsed across all
    years -- a single 4-season climatology, not a per-year seasonal time
    series (use `seasonal_timeseries` for that).
    """
    out = da.groupby("time.season").mean(dim="time", skipna=True)
    return out.reindex(season=["DJF", "MAM", "JJA", "SON"])


def seasonal_timeseries(da: xr.DataArray) -> xr.DataArray:
    """Mean per season PER YEAR (a real time series, e.g. JJA-2010, JJA-2011, ...).
    Uses `resample` on quarter-start anchored to Dec, matching meteorological
    seasons (DJF counted in the January of that year's winter).
    """
    return da.resample(time="QS-DEC").mean(skipna=True)


def monthly_climatology(da: xr.DataArray) -> xr.DataArray:
    """Mean by calendar month (Jan..Dec), collapsed across all years."""
    return da.groupby("time.month").mean(dim="time", skipna=True)


# ---------------------------------------------------------------------------
# Trend analysis
# ---------------------------------------------------------------------------

def linear_trend(da: xr.DataArray, dim: str = "time") -> xr.Dataset:
    """Per-gridcell linear regression (slope, intercept, r, p-value, std_err)
    of `da` against time (in YEARS since the first timestep, so slope units
    are "per year" -- directly comparable to Sen's slope below).

    Fast (vectorized via scipy.stats.linregress + apply_ufunc), but
    sensitive to outliers -- pair with `sens_slope` / `mann_kendall_trend`
    for a more robust (non-parametric) trend estimate.
    """
    time_numeric = (da[dim] - da[dim][0]) / np.timedelta64(365, "D")
    time_numeric = time_numeric.values.astype(float)

    def _fit(y):
        if np.all(np.isnan(y)):
            return np.full(5, np.nan)
        mask = ~np.isnan(y)
        if mask.sum() < 3:
            return np.full(5, np.nan)
        result = scipy_stats.linregress(time_numeric[mask], y[mask])
        return np.array([result.slope, result.intercept, result.rvalue, result.pvalue, result.stderr])

    result = xr.apply_ufunc(
        _fit,
        da,
        input_core_dims=[[dim]],
        output_core_dims=[["stat"]],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[float],
        dask_gufunc_kwargs={"output_sizes": {"stat": 5}},
    )
    result = result.assign_coords(stat=["slope", "intercept", "r", "p_value", "std_err"])
    return result.to_dataset(dim="stat")


def sens_slope(da: xr.DataArray, dim: str = "time") -> xr.DataArray:
    """Per-gridcell Sen's slope estimator (median of all pairwise slopes) --
    robust to outliers, standard companion to the Mann-Kendall test. Units:
    per year (same convention as `linear_trend`).

    NOTE: this loops over EVERY grid cell in Python (pymannkendall has no
    native vectorization). For large grids, subsample first or run this as
    an overnight batch job -- see `mann_kendall_trend` docstring for the
    same caveat with a subsampling example.
    """
    if not _HAS_MK:
        raise ImportError("pymannkendall is required for sens_slope(). pip install pymannkendall")

    def _slope(y):
        if np.all(np.isnan(y)) or np.sum(~np.isnan(y)) < 3:
            return np.nan
        y_clean = y[~np.isnan(y)]
        return mk.sens_slope(y_clean).slope if hasattr(mk.sens_slope(y_clean), "slope") else mk.sens_slope(y_clean)[0]

    result = xr.apply_ufunc(
        _slope,
        da,
        input_core_dims=[[dim]],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[float],
    )
    result.attrs["long_name"] = f"Sen's slope of {da.name}"
    result.attrs["units"] = f"{da.attrs.get('units', '')}/year"
    return result


def mann_kendall_trend(da: xr.DataArray, dim: str = "time", alpha: float = 0.05) -> xr.Dataset:
    """Per-gridcell Mann-Kendall trend test: trend direction, significance,
    p-value, Kendall's Tau, and Sen's slope, all in one pass (more efficient
    than calling `sens_slope` separately, since pymannkendall computes both).

    Returns a Dataset with variables: trend (+1/0/-1), p_value, significant
    (bool, p < alpha), tau, slope.

    PERFORMANCE: loops per-gridcell in Python. For a quick check on a large
    grid, subsample first, e.g.:
        da_sub = da.isel(lat=slice(None, None, 5), lon=slice(None, None, 5))
        mk_sub = mann_kendall_trend(da_sub)
    then run the full-resolution version separately once you're ready to
    commit the time.
    """
    if not _HAS_MK:
        raise ImportError("pymannkendall is required for mann_kendall_trend(). pip install pymannkendall")

    def _mk(y):
        if np.all(np.isnan(y)) or np.sum(~np.isnan(y)) < 4:
            return np.array([0.0, np.nan, np.nan, np.nan])
        y_clean = y[~np.isnan(y)]
        r = mk.original_test(y_clean, alpha=alpha)
        trend_code = {"increasing": 1.0, "decreasing": -1.0, "no trend": 0.0}[r.trend]
        return np.array([trend_code, r.p, r.Tau, r.slope])

    result = xr.apply_ufunc(
        _mk,
        da,
        input_core_dims=[[dim]],
        output_core_dims=[["mk_stat"]],
        vectorize=True,
        dask="parallelized",
        output_dtypes=[float],
        dask_gufunc_kwargs={"output_sizes": {"mk_stat": 4}},
    )
    result = result.assign_coords(mk_stat=["trend", "p_value", "tau", "slope"])
    out = result.to_dataset(dim="mk_stat")
    out["significant"] = out["p_value"] < alpha
    return out
