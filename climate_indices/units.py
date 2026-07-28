"""
units.py — Automatic unit conversion for climate variables.

Deliberately conservative: only converts when the `units` attribute
matches a known pattern, and always sets the correct output `units`
attribute afterward so downstream code (and xclim) can trust it.
"""

from __future__ import annotations

import logging

import xarray as xr

logger = logging.getLogger("climate_indices.units")

_KELVIN_ALIASES = {"K", "Kelvin", "kelvin", "degK"}
_CELSIUS_ALIASES = {"degC", "Celsius", "celsius", "C"}
_FLUX_ALIASES = {"kg m-2 s-1", "kg/m2/s", "kg m^-2 s^-1"}
_MM_ALIASES = {"mm", "mm/day", "mm day-1"}


def convert_units(da: xr.DataArray, target: str) -> xr.DataArray:
    """Convert a DataArray's units, based on its current `units` attribute.

    Parameters
    ----------
    da : xr.DataArray
        Must have a `units` attribute for automatic conversion to trigger.
        If missing, the array is returned unchanged with a warning logged
        -- silently guessing units is how bugs like Kelvin-vs-Celsius
        mismatches slip through unnoticed.
    target : str
        One of "degC" (temperature) or "mm/day" (precipitation).

    Returns
    -------
    xr.DataArray
        Converted array with an updated `units` attribute. Original array
        is not modified in place.
    """
    current = da.attrs.get("units")
    if current is None:
        logger.warning(
            "No 'units' attribute on '%s' -- skipping automatic conversion. "
            "Inspect a few raw values manually and set da.attrs['units'] yourself.",
            da.name,
        )
        return da

    if target == "degC":
        if current in _CELSIUS_ALIASES:
            return da
        if current in _KELVIN_ALIASES:
            out = da - 273.15
            out.attrs = {**da.attrs, "units": "degC"}
            logger.info("Converted '%s' from Kelvin to Celsius.", da.name)
            return out
        raise ValueError(f"Don't know how to convert units '{current}' to degC.")

    if target == "mm/day":
        if current in _MM_ALIASES:
            return da
        if current in _FLUX_ALIASES:
            out = da * 86400.0
            out.attrs = {**da.attrs, "units": "mm/day"}
            logger.info("Converted '%s' from %s to mm/day.", da.name, current)
            return out
        raise ValueError(f"Don't know how to convert units '{current}' to mm/day.")

    raise ValueError(f"Unsupported target unit: '{target}'. Use 'degC' or 'mm/day'.")


def convert_dataset_units(ds: xr.Dataset, var_targets: dict[str, str]) -> xr.Dataset:
    """Apply `convert_units` across multiple variables in a Dataset.

    Example
    -------
    >>> ds = convert_dataset_units(ds, {"tasmax": "degC", "pr": "mm/day"})
    """
    ds = ds.copy()
    for var, target in var_targets.items():
        if var in ds.data_vars:
            ds[var] = convert_units(ds[var], target)
    return ds
