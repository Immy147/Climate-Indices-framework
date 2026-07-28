"""
clean.py — Turn validate.py's findings into action: mask physically
invalid values, optionally interpolate small gaps, always preserve the
original array so cleaning is auditable/reversible.
"""

from __future__ import annotations

import logging

import xarray as xr

from .validate import get_physical_range

logger = logging.getLogger("climate_indices.clean")


def mask_invalid(da: xr.DataArray, variable: str) -> xr.DataArray:
    """Replace physically-implausible values with NaN, based on the same
    unit-aware range table used by validate.py. Does not touch already-NaN
    cells. Looks up the range for the array's CURRENT `units` attribute --
    if that attribute is missing or unrecognized, this is a safe no-op
    (never guesses a range and masks against it blind).
    """
    out = da.copy()
    units = da.attrs.get("units")
    bounds = get_physical_range(variable, units)
    if bounds["min"] is None and bounds["max"] is None:
        logger.warning(
            "No physical range for '%s' with units='%s' (%s) -- mask_invalid is a no-op.",
            variable, units, bounds["units_hint"],
        )
        return out

    cond = xr.ones_like(out, dtype=bool)
    if bounds["min"] is not None:
        cond = cond & (out >= bounds["min"])
    if bounds["max"] is not None:
        cond = cond & (out <= bounds["max"])
    if variable == "pr":
        cond = cond & (out >= 0)

    n_before_nan = None  # avoid an eager compute just for logging; log post-hoc if needed
    out = out.where(cond)
    out.attrs = da.attrs
    logger.info("Masked out-of-range values for '%s' (lazy -- not yet computed).", variable)
    return out


def interpolate_gaps(
    da: xr.DataArray,
    dim: str = "time",
    method: str = "linear",
    max_gap: int | None = 5,
) -> xr.DataArray:
    """Fill small NaN gaps along `dim` via interpolation.

    Parameters
    ----------
    max_gap : int, optional
        Maximum consecutive-NaN run length (in index steps) to fill.
        Longer gaps are left as NaN on purpose -- interpolating across,
        say, a 60-day gap would fabricate data, not fix it. Set to None
        to fill gaps of any length (use with caution).
    """
    kwargs = {}
    if max_gap is not None:
        kwargs["max_gap"] = max_gap
        kwargs["use_coordinate"] = True
    out = da.interpolate_na(dim=dim, method=method, **kwargs)
    out.attrs = da.attrs
    logger.info("Interpolated gaps along '%s' (method=%s, max_gap=%s).", dim, method, max_gap)
    return out


def clean_dataset(
    ds: xr.Dataset,
    variable: str,
    mask_out_of_range: bool = True,
    interpolate: bool = False,
    interpolate_max_gap: int = 5,
    keep_original: bool = True,
) -> xr.Dataset:
    """Full cleaning pipeline for one variable in a Dataset.

    Returns a new Dataset. If `keep_original`, the pre-cleaning array is
    kept alongside as `f"{variable}_raw"` so you can always compare or
    revert.
    """
    ds = ds.copy()
    da = ds[variable]

    if keep_original:
        ds[f"{variable}_raw"] = da

    if mask_out_of_range:
        da = mask_invalid(da, variable)

    if interpolate:
        da = interpolate_gaps(da, max_gap=interpolate_max_gap)

    ds[variable] = da
    return ds
