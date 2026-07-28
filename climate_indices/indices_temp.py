"""
indices_temp.py — ETCCDI temperature indices computable from tasmax alone.

Excluded on purpose (need tasmin or tas, not provided in this pipeline):
TNx, TNn, TN90p, TN10p, CSDI, TR (tropical nights), DTR, GSL.
If you get tasmin later, mirror this module: swap max<->min and
90th<->10th percentile where relevant, and thresh direction for CSDI.

All functions expect `tasmax` already in degC (see units.py) and Dask-backed
if working with large files.
"""

from __future__ import annotations

import logging

import pandas as pd
import xarray as xr
from xclim import indices as xci
from xclim.core.calendar import percentile_doy

logger = logging.getLogger("climate_indices.indices_temp")


def compute_tx_percentile_thresholds(
    tasmax: xr.DataArray,
    ref_start: str,
    ref_end: str,
    window: int = 5,
    spatial_chunk: int = 50,
) -> xr.Dataset:
    """Compute the day-of-year 10th and 90th percentile thresholds of tasmax
    over a reference period, ETCCDI-style (5-day centred window by default).

    Returns a Dataset with `p10` and `p90` DataArrays (dims: dayofyear, lat, lon).
    Reused by TX90p, TX10p, and WSDI so it's only computed once.
    """
    tasmax_ref = tasmax.sel(time=slice(ref_start, ref_end))
    # percentile_doy requires a single chunk along time -- percentiles are a
    # whole-column operation and can't be computed chunk-by-chunk. lat/lon
    # ARE rechunked so this stays memory-safe on large grids.
    tasmax_ref = tasmax_ref.chunk({"time": -1, "lat": spatial_chunk, "lon": spatial_chunk})

    doy_pctl = percentile_doy(tasmax_ref, window=window, per=[10, 90])
    return xr.Dataset(
        {
            "p10": doy_pctl.sel(percentiles=10, drop=True),
            "p90": doy_pctl.sel(percentiles=90, drop=True),
        }
    )


def _year_to_datetime(da: xr.DataArray) -> xr.DataArray:
    """Convert a `year`-indexed DataArray (from groupby('time.year')) to a
    `time`-indexed one with Jan-1 timestamps, matching xclim's YS convention
    so it can be merged into the same Dataset as xclim-derived variables.
    """
    da = da.rename(year="time")
    da = da.assign_coords(time=pd.to_datetime(da["time"].values.astype(str) + "-01-01"))
    return da


def compute_temperature_indices(
    tasmax: xr.DataArray,
    ref_start: str,
    ref_end: str,
    su_thresh: str = "25.0 degC",
    ice_thresh: str = "0 degC",
    freq: str = "YS",
    spatial_chunk: int = 50,
) -> xr.Dataset:
    """Compute all applicable ETCCDI temperature indices from tasmax.

    Parameters
    ----------
    tasmax : xr.DataArray
        Daily maximum temperature in degC.
    ref_start, ref_end : str
        Reference period (e.g. "1985", "2014") for percentile-based indices.
    su_thresh : str
        Threshold for "Summer Days" (SU). Default matches ETCCDI (25 degC);
        adjust for tropical climates where 25degC may barely discriminate.
    ice_thresh : str
        Threshold for "Ice Days" (ID). Default matches ETCCDI (0 degC).
        Note: in most tropical settings (e.g. Philippines lowlands) this
        will be ~0 for every year -- keep it for completeness / high-elevation
        cells, don't be alarmed if it's all zeros at low elevation.
    freq : str
        Resampling frequency, default "YS" (annual).

    Returns
    -------
    xr.Dataset with variables: TXx, TXn, TX90p, TX10p, WSDI, SU, ID
    """
    logger.info("Computing percentile thresholds from reference period %s-%s", ref_start, ref_end)
    thresholds = compute_tx_percentile_thresholds(tasmax, ref_start, ref_end, spatial_chunk=spatial_chunk)

    logger.info("Computing TXx, TXn ...")
    txx = xci.tx_max(tasmax, freq=freq)
    txn = xci.tx_min(tasmax, freq=freq)

    logger.info("Computing TX90p, TX10p ...")
    tx90p = xci.tx90p(tasmax, thresholds["p90"], freq=freq)
    tx10p = xci.tx10p(tasmax, thresholds["p10"], freq=freq)

    logger.info("Computing WSDI ...")
    wsdi = xci.warm_spell_duration_index(tasmax, thresholds["p90"], window=6, freq=freq)

    logger.info("Computing SU (summer days), ID (ice days) ...")
    su = xci.tx_days_above(tasmax, thresh=su_thresh, freq=freq)
    ice = xci.ice_days(tasmax, thresh=ice_thresh, freq=freq)

    out = xr.Dataset(
        {
            "TXx": txx,
            "TXn": txn,
            "TX90p": tx90p,
            "TX10p": tx10p,
            "WSDI": wsdi,
            "SU": su,
            "ID": ice,
        }
    )
    out.attrs["reference_period"] = f"{ref_start}-{ref_end}"
    out.attrs["description"] = "ETCCDI temperature indices computed from tasmax"
    return out
