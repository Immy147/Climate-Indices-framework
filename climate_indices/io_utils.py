"""
io_utils.py — Reading climate NetCDF data (single file, multi-file, or a
whole directory), Dask-backed and lazy by default.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import xarray as xr

logger = logging.getLogger("climate_indices.io_utils")

# Common alternate names we try to auto-normalize to CF-standard var/dim names.
_VAR_ALIASES = {
    "tasmax": ["tasmax", "tmax", "tx", "TMAX", "air_temperature_max"],
    "tasmin": ["tasmin", "tmin", "tn", "TMIN", "air_temperature_min"],
    "pr": ["pr", "precip", "precipitation", "PRCP", "rr"],
}
_DIM_ALIASES = {
    "time": ["time", "Time", "t"],
    "lat": ["lat", "latitude", "y", "Y"],
    "lon": ["lon", "longitude", "x", "X"],
}


def _find_files(path: str | Path, pattern: str = "*.nc", recursive: bool = True) -> list[Path]:
    """Resolve a path argument into a sorted list of NetCDF file paths.

    Accepts a single file, a list-like of files (handled by caller), or a
    directory (optionally searched recursively).
    """
    path = Path(path)
    if path.is_file():
        return [path]
    if path.is_dir():
        glob_fn = path.rglob if recursive else path.glob
        files = sorted(glob_fn(pattern))
        if not files:
            raise FileNotFoundError(f"No files matching '{pattern}' found under {path}")
        return files
    raise FileNotFoundError(f"Path does not exist: {path}")


def _normalize_names(ds: xr.Dataset) -> xr.Dataset:
    """Rename known variable/dimension aliases to CF-standard names in place."""
    rename_map = {}
    for canonical, aliases in {**_VAR_ALIASES, **_DIM_ALIASES}.items():
        for alias in aliases:
            if alias in ds.variables or alias in ds.dims:
                if alias != canonical:
                    rename_map[alias] = canonical
                break
    if rename_map:
        logger.info("Renaming to canonical names: %s", rename_map)
        ds = ds.rename(rename_map)
    return ds


def read_dataset(
    path: str | Path | Iterable[str | Path],
    variable: str | None = None,
    pattern: str = "*.nc",
    recursive: bool = True,
    chunks: dict | str = "auto",
    normalize_names: bool = True,
    combine: str = "by_coords",
) -> xr.Dataset:
    """Read one file, a list of files, or a directory of NetCDF files.

    Parameters
    ----------
    path : str, Path, or list of str/Path
        A single NetCDF file, a directory (searched with `pattern`), or an
        explicit list of file paths.
    variable : str, optional
        If given, subset the returned Dataset to just this variable
        (after name normalization), e.g. "tasmax" or "pr".
    pattern : str
        Glob pattern used when `path` is a directory. Default "*.nc".
    recursive : bool
        Whether to search subdirectories when `path` is a directory.
    chunks : dict or "auto"
        Dask chunking spec passed to xarray. Use a dict like
        {"time": 365} for time-chunked lazy loading on large files.
    normalize_names : bool
        If True, rename common variable/dim aliases (tmax->tasmax,
        latitude->lat, etc.) to CF-standard names.
    combine : str
        Passed to `xr.open_mfdataset` when multiple files are found.

    Returns
    -------
    xr.Dataset
        Lazily-loaded (Dask-backed) dataset.
    """
    if isinstance(path, (list, tuple)):
        files = [Path(p) for p in path]
    else:
        files = _find_files(path, pattern=pattern, recursive=recursive)

    logger.info("Reading %d file(s)", len(files))

    if len(files) == 1:
        ds = xr.open_dataset(files[0], chunks=chunks)
    else:
        ds = xr.open_mfdataset(
            [str(f) for f in files],
            chunks=chunks,
            combine=combine,
            parallel=True,
        )

    if normalize_names:
        ds = _normalize_names(ds)

    if variable is not None:
        if variable not in ds.data_vars:
            raise KeyError(
                f"Variable '{variable}' not found after normalization. "
                f"Available: {list(ds.data_vars)}"
            )
        ds = ds[[variable]]

    logger.info(
        "Loaded dataset: dims=%s vars=%s",
        dict(ds.sizes),
        list(ds.data_vars),
    )
    return ds


def detect_variable(ds: xr.Dataset) -> str:
    """Best-effort guess of the primary climate variable in a Dataset."""
    for canonical in _VAR_ALIASES:
        if canonical in ds.data_vars:
            return canonical
    # fall back to the only data var, if there's exactly one
    data_vars = list(ds.data_vars)
    if len(data_vars) == 1:
        return data_vars[0]
    raise ValueError(
        f"Could not auto-detect the climate variable among {data_vars}. "
        "Pass `variable=` explicitly to read_dataset()."
    )
