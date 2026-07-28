"""
validate.py — Data quality checks for climate NetCDF data, run before any
processing. Returns a structured report (dict) rather than raising on most
issues, so you can inspect problems before deciding how to clean the data.
Genuinely fatal problems (no time/lat/lon coordinate at all) still raise.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import xarray as xr

logger = logging.getLogger("climate_indices.validate")

# Plausible physical ranges per variable, PER UNIT SYSTEM. Values outside
# these are flagged, not silently dropped -- see clean.py for turning flags
# into action.
#
# IMPORTANT: these are unit-aware on purpose. A range check that only knows
# about Kelvin will silently nuke an entire array to NaN once units.py has
# converted it to Celsius (150-350 K makes sense; 150-350 degC does not,
# and masking against it rejects every real value). Always look up the
# range for the array's CURRENT `units` attribute via `get_physical_range`,
# never hardcode one system.
_PHYSICAL_RANGES = {
    "tasmax": {
        "K":    {"min": 150.0, "max": 350.0},
        "degC": {"min": -90.0, "max": 60.0},
    },
    "tasmin": {
        "K":    {"min": 150.0, "max": 350.0},
        "degC": {"min": -90.0, "max": 60.0},
    },
    "tas": {
        "K":    {"min": 150.0, "max": 350.0},
        "degC": {"min": -90.0, "max": 60.0},
    },
    "pr": {
        "kg m-2 s-1": {"min": 0.0, "max": 0.05},   # ~4320 mm/day equiv, generous ceiling
        "mm/day":     {"min": 0.0, "max": 2000.0},  # world-record daily totals are ~1800mm
    },
    "hurs": {
        "%": {"min": 0.0, "max": 100.0},
    },
    "sfcWind": {
        "m/s": {"min": 0.0, "max": 150.0},  # generous; strongest recorded gusts are ~110 m/s
    },
}

_UNIT_GROUPS = {
    "K": {"K", "Kelvin", "kelvin", "degK"},
    "degC": {"degC", "Celsius", "celsius", "C"},
    "kg m-2 s-1": {"kg m-2 s-1", "kg/m2/s", "kg m^-2 s^-1"},
    "mm/day": {"mm", "mm/day", "mm day-1"},
    "%": {"%", "percent"},
    "m/s": {"m/s", "m s-1", "m s^-1"},
}


def get_physical_range(variable: str, units: str | None) -> dict:
    """Look up the plausible (min, max) range for `variable`, matched to its
    CURRENT unit system. Returns {"min": None, "max": None, "units_hint": ...}
    if the variable or units are unrecognized (i.e. no check is possible --
    callers should treat that as "unable to validate", not "value is fine").
    """
    var_ranges = _PHYSICAL_RANGES.get(variable)
    if var_ranges is None or units is None:
        return {"min": None, "max": None, "units_hint": "unknown"}

    for canonical, aliases in _UNIT_GROUPS.items():
        if units in aliases and canonical in var_ranges:
            bounds = var_ranges[canonical]
            return {"min": bounds["min"], "max": bounds["max"], "units_hint": canonical}

    return {"min": None, "max": None, "units_hint": f"no range defined for units='{units}'"}


@dataclass
class ValidationReport:
    variable: str
    metadata: dict = field(default_factory=dict)
    coordinates: dict = field(default_factory=dict)
    time: dict = field(default_factory=dict)
    missing_data: dict = field(default_factory=dict)
    physical_range: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"=== Validation report: {self.variable} ==="]
        for section in ("metadata", "coordinates", "time", "missing_data", "physical_range"):
            lines.append(f"\n[{section}]")
            for k, v in getattr(self, section).items():
                lines.append(f"  {k}: {v}")
        if self.warnings:
            lines.append("\n[warnings]")
            lines += [f"  - {w}" for w in self.warnings]
        if self.errors:
            lines.append("\n[errors]")
            lines += [f"  - {e}" for e in self.errors]
        return "\n".join(lines)


def _check_metadata(da: xr.DataArray, report: ValidationReport) -> None:
    attrs = da.attrs
    report.metadata["units"] = attrs.get("units", "MISSING")
    report.metadata["standard_name"] = attrs.get("standard_name", "MISSING")
    report.metadata["long_name"] = attrs.get("long_name", "MISSING")
    if "units" not in attrs:
        report.warnings.append("No 'units' attribute -- unit conversion will need manual confirmation.")
    calendar = getattr(da.indexes.get("time"), "calendar", None) if "time" in da.dims else None
    report.metadata["calendar"] = calendar or "standard (numpy datetime64)"


def _check_coordinates(da: xr.DataArray, report: ValidationReport) -> None:
    for dim in ("time", "lat", "lon"):
        if dim not in da.dims:
            report.errors.append(f"Missing required coordinate/dimension: '{dim}'")
            continue
        coord = da[dim]
        n = coord.size
        n_unique = np.unique(coord.values).size
        report.coordinates[f"{dim}_size"] = n
        if n_unique != n:
            report.warnings.append(f"Duplicate values found in '{dim}' coordinate ({n - n_unique} dupes).")

        if dim in ("lat", "lon"):
            vals = coord.values.astype(float)
            diffs = np.diff(vals)
            if diffs.size > 0:
                irregular = not np.allclose(diffs, diffs[0], rtol=1e-3)
                report.coordinates[f"{dim}_spacing"] = "irregular" if irregular else f"~{diffs[0]:.4f} deg"
                if irregular:
                    report.warnings.append(f"'{dim}' spacing looks irregular -- check the grid.")
            report.coordinates[f"{dim}_range"] = (float(vals.min()), float(vals.max()))
            if dim == "lat" and (vals.min() < -90 or vals.max() > 90):
                report.errors.append("Latitude values fall outside [-90, 90].")
            if dim == "lon" and (vals.min() < -180 or vals.max() > 360):
                report.errors.append("Longitude values fall outside a plausible [-180, 360] range.")


def _check_time(da: xr.DataArray, report: ValidationReport) -> None:
    if "time" not in da.dims:
        return
    time_index = pd.to_datetime(da["time"].values)
    diffs = time_index.to_series().diff().dropna()
    if diffs.empty:
        return
    mode_days = diffs.dt.days.mode()
    step_days = mode_days.iloc[0] if not mode_days.empty else None

    if step_days == 1:
        freq_guess = "daily"
    elif step_days in (28, 29, 30, 31):
        freq_guess = "monthly"
    elif step_days == 0:
        # sub-daily; look at seconds instead
        step_seconds = diffs.dt.total_seconds().mode().iloc[0]
        freq_guess = f"sub-daily (~{step_seconds/3600:.1f}h)"
    else:
        freq_guess = f"irregular (mode step = {step_days} days)"

    report.time["frequency_guess"] = freq_guess
    report.time["start"] = str(time_index.min())
    report.time["end"] = str(time_index.max())

    n_duplicates = int(time_index.duplicated().sum())
    report.time["duplicate_timestamps"] = n_duplicates
    if n_duplicates:
        report.warnings.append(f"{n_duplicates} duplicate timestamps found.")

    # gap detection only meaningful for daily-ish data
    if freq_guess == "daily":
        full_range = pd.date_range(time_index.min(), time_index.max(), freq="D")
        missing_dates = full_range.difference(time_index)
        report.time["missing_dates_count"] = int(len(missing_dates))
        if len(missing_dates) > 0:
            pct = 100 * len(missing_dates) / len(full_range)
            report.warnings.append(
                f"{len(missing_dates)} missing daily timestamps ({pct:.2f}% of expected range)."
            )


def _check_missing_data(da: xr.DataArray, report: ValidationReport, sample: bool = True) -> None:
    """NaN accounting. `sample=True` computes on a small time slice first to
    stay cheap on large Dask arrays; set False to force a full (expensive)
    pass over the whole array.
    """
    target = da.isel(time=slice(0, min(365, da.sizes.get("time", 1)))) if sample and "time" in da.dims else da
    total = target.size
    n_nan = int(target.isnull().sum().compute()) if hasattr(target.data, "chunks") else int(target.isnull().sum())
    pct = 100 * n_nan / total if total else 0.0
    label = "sampled (first ~365 steps)" if sample else "full array"
    report.missing_data[f"nan_count_{label}"] = n_nan
    report.missing_data[f"nan_percent_{label}"] = round(pct, 3)
    if pct > 5:
        report.warnings.append(f"High missing-data fraction in {label}: {pct:.2f}%.")


def _check_physical_range(da: xr.DataArray, variable: str, report: ValidationReport, sample: bool = True) -> None:
    units = da.attrs.get("units")
    bounds = get_physical_range(variable, units)
    if bounds["min"] is None and bounds["max"] is None:
        report.physical_range["note"] = (
            f"No physical range check possible for '{variable}' with units='{units}' "
            f"({bounds['units_hint']})."
        )
        return
    target = da.isel(time=slice(0, min(365, da.sizes.get("time", 1)))) if sample and "time" in da.dims else da

    dmin = float(target.min().compute()) if hasattr(target.data, "chunks") else float(target.min())
    dmax = float(target.max().compute()) if hasattr(target.data, "chunks") else float(target.max())
    report.physical_range["observed_min"] = dmin
    report.physical_range["observed_max"] = dmax
    report.physical_range["expected_range"] = (bounds["min"], bounds["max"])
    report.physical_range["expected_units_hint"] = bounds["units_hint"]

    if bounds["min"] is not None and dmin < bounds["min"]:
        report.warnings.append(
            f"Observed minimum {dmin:.2f} is below plausible physical minimum "
            f"{bounds['min']} for '{variable}' (expected units: {bounds['units_hint']})."
        )
    if bounds["max"] is not None and dmax > bounds["max"]:
        report.warnings.append(
            f"Observed maximum {dmax:.2f} exceeds plausible physical maximum "
            f"{bounds['max']} for '{variable}' (expected units: {bounds['units_hint']})."
        )
    if variable == "pr" and dmin < 0:
        report.warnings.append("Negative precipitation values found -- these are physically invalid.")


def validate_dataset(
    ds: xr.Dataset,
    variable: str,
    sample_for_expensive_checks: bool = True,
) -> ValidationReport:
    """Run the full validation suite on `ds[variable]`.

    Parameters
    ----------
    ds : xr.Dataset
    variable : str
        Name of the variable to validate (e.g. "tasmax", "pr").
    sample_for_expensive_checks : bool
        If True (default), missing-data and physical-range checks run on a
        ~365-timestep sample instead of the full Dask array, to stay cheap
        on multi-GB files. Set False for a full, more expensive pass
        (recommended once, before your final production run).

    Returns
    -------
    ValidationReport
    """
    if variable not in ds.data_vars:
        raise KeyError(f"'{variable}' not in dataset variables: {list(ds.data_vars)}")

    da = ds[variable]
    report = ValidationReport(variable=variable)

    _check_metadata(da, report)
    _check_coordinates(da, report)
    if report.errors:
        # coordinate errors are fatal for everything downstream
        logger.error("Fatal coordinate errors: %s", report.errors)
        return report

    _check_time(da, report)
    _check_missing_data(da, report, sample=sample_for_expensive_checks)
    _check_physical_range(da, variable, report, sample=sample_for_expensive_checks)

    if report.warnings:
        logger.warning("%d warning(s) for '%s' -- see report.summary()", len(report.warnings), variable)
    else:
        logger.info("Validation passed with no warnings for '%s'.", variable)

    return report
