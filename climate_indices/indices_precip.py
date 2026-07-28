"""
indices_precip.py — ETCCDI (+ common extension) precipitation indices from
`pr` (mm/day).

R95p/R99p (total mm from very/extremely wet days) and P95D/P99D (count of
such days) share the same wet-day percentile threshold, computed once from
a reference period and reused for both -- this mirrors the ETCCDI
convention and the source "Projection Explorer" methodology (threshold is
per-grid-cell, from the whole wet-day distribution, NOT day-of-year windowed
like the temperature percentile indices).
"""

from __future__ import annotations

import logging

import pandas as pd
import xarray as xr
from xclim import indices as xci

logger = logging.getLogger("climate_indices.indices_precip")


def _year_to_datetime(da: xr.DataArray) -> xr.DataArray:
    da = da.rename(year="time")
    years = da["time"].values.astype(int)
    new_time = pd.to_datetime([f"{y}-01-01" for y in years])
    da = da.assign_coords(time=new_time)
    return da


def compute_wetday_percentile_thresholds(
    pr: xr.DataArray,
    ref_start: str,
    ref_end: str,
    wet_thresh: float = 1.0,
    spatial_chunk: int = 50,
) -> xr.Dataset:
    """Compute the 95th/99th percentile of WET-day (pr >= wet_thresh mm/day)
    precipitation over a reference period. One scalar threshold per grid
    cell (not day-of-year windowed -- see module docstring).
    """
    pr_ref = pr.sel(time=slice(ref_start, ref_end))
    wet_ref = pr_ref.where(pr_ref >= wet_thresh)
    # quantile is a whole-column op -- must not be chunked along time.
    # lat/lon ARE rechunked to stay memory-safe on large grids.
    wet_ref = wet_ref.chunk({"time": -1, "lat": spatial_chunk, "lon": spatial_chunk})

    p95 = wet_ref.quantile(0.95, dim="time", skipna=True).drop_vars("quantile")
    p99 = wet_ref.quantile(0.99, dim="time", skipna=True).drop_vars("quantile")
    return xr.Dataset({"p95": p95, "p99": p99})


def compute_precipitation_indices(
    pr: xr.DataArray,
    ref_start: str,
    ref_end: str,
    wet_thresh: float = 1.0,
    freq: str = "YS",
    spatial_chunk: int = 50,
) -> xr.Dataset:
    """Compute ETCCDI + common precipitation indices from daily pr (mm/day).

    Parameters
    ----------
    pr : xr.DataArray
        Daily precipitation in mm/day.
    ref_start, ref_end : str
        Reference period for R95p/R99p/P95D/P99D thresholds.
    wet_thresh : float
        Wet-day threshold in mm/day, default 1.0 (ETCCDI standard).
    freq : str
        Resampling frequency, default "YS" (annual).

    Returns
    -------
    xr.Dataset with variables:
        RX1day, RX5day, PRCPTOT, SDII, R10mm, R20mm, CDD, CWD,
        R95p, R99p (mm, sum on very/extremely wet days),
        P95D, P99D (days, count of very/extremely wet days)
    """
    logger.info("Computing RX1day, RX5day ...")
    rx1day = xci.max_1day_precipitation_amount(pr, freq=freq)
    rx5day = xci.max_n_day_precipitation_amount(pr, window=5, freq=freq)

    logger.info("Computing PRCPTOT, SDII ...")
    prcptot = xci.prcptot(pr, thresh=f"{wet_thresh} mm/d", freq=freq)
    sdii = xci.daily_pr_intensity(pr, thresh=f"{wet_thresh} mm/day", freq=freq)

    logger.info("Computing R10mm, R20mm ...")
    r10mm = xci.wetdays(pr, thresh="10 mm/day", freq=freq)
    r20mm = xci.wetdays(pr, thresh="20 mm/day", freq=freq)

    logger.info("Computing CDD, CWD ...")
    cdd = xci.maximum_consecutive_dry_days(pr, thresh=f"{wet_thresh} mm/day", freq=freq)
    cwd = xci.maximum_consecutive_wet_days(pr, thresh=f"{wet_thresh} mm/day", freq=freq)

    logger.info("Computing wet-day percentile thresholds (ref %s-%s) ...", ref_start, ref_end)
    thresholds = compute_wetday_percentile_thresholds(pr, ref_start, ref_end, wet_thresh, spatial_chunk=spatial_chunk)

    logger.info("Computing R95p, R99p, P95D, P99D ...")
    above_p95 = pr.where(pr > thresholds["p95"])
    above_p99 = pr.where(pr > thresholds["p99"])

    r95p = above_p95.groupby("time.year").sum(dim="time", skipna=True)
    r99p = above_p99.groupby("time.year").sum(dim="time", skipna=True)
    p95d = (pr > thresholds["p95"]).groupby("time.year").sum(dim="time")
    p99d = (pr > thresholds["p99"]).groupby("time.year").sum(dim="time")

    r95p = _year_to_datetime(r95p)
    r99p = _year_to_datetime(r99p)
    p95d = _year_to_datetime(p95d)
    p99d = _year_to_datetime(p99d)

    out = xr.Dataset(
        {
            "RX1day": rx1day,
            "RX5day": rx5day,
            "PRCPTOT": prcptot,
            "SDII": sdii,
            "R10mm": r10mm,
            "R20mm": r20mm,
            "CDD": cdd,
            "CWD": cwd,
            "R95p": r95p,
            "R99p": r99p,
            "P95D": p95d,
            "P99D": p99d,
        }
    )
    out["R95p"].attrs.update(units="mm", long_name="Total precip on very wet days (>95th pctl)")
    out["R99p"].attrs.update(units="mm", long_name="Total precip on extremely wet days (>99th pctl)")
    out["P95D"].attrs.update(units="days", long_name="Count of very wet days (>95th pctl)")
    out["P99D"].attrs.update(units="days", long_name="Count of extremely wet days (>99th pctl)")
    out.attrs["reference_period"] = f"{ref_start}-{ref_end}"
    out.attrs["description"] = "ETCCDI precipitation indices computed from pr"
    return out
