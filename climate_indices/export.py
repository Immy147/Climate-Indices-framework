"""
export.py — Save results to NetCDF, CSV, Excel, and PNG, into a structured
output directory tree:

outputs/
├── cleaned/
├── indices/
├── statistics/
├── plots/
└── reports/

GeoTIFF export is included but requires `rioxarray` (optional dependency --
raises a clear ImportError with install instructions if missing, rather
than failing silently or crashing the whole module on import).
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import xarray as xr

logger = logging.getLogger("climate_indices.export")

_SUBDIRS = ["cleaned", "indices", "statistics", "plots", "reports"]


def make_output_dirs(base_dir: str | Path) -> dict[str, Path]:
    """Create the standard output directory tree under `base_dir` (existing
    dirs are left as-is). Returns a dict of {name: Path} for convenient use,
    e.g. `dirs["indices"] / "temperature.nc"`.
    """
    base = Path(base_dir)
    dirs = {"base": base}
    for sub in _SUBDIRS:
        p = base / sub
        p.mkdir(parents=True, exist_ok=True)
        dirs[sub] = p
    logger.info("Output directories ready under %s", base)
    return dirs


def to_netcdf(ds: xr.Dataset, path: str | Path, compress: bool = True) -> Path:
    """Write a Dataset to NetCDF with zlib compression by default."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoding = {var: {"zlib": True, "complevel": 4} for var in ds.data_vars} if compress else None
    ds.to_netcdf(path, encoding=encoding)
    logger.info("Wrote NetCDF: %s", path)
    return path


def to_csv(
    da: xr.DataArray,
    path: str | Path,
    reduce_spatial: str | None = "mean",
) -> Path:
    """Write a DataArray to CSV. Since CSV is inherently 2D/tabular:
    - If `reduce_spatial` is given (default "mean"), spatial dims are
      collapsed first (e.g. area mean per year) -> a simple time-indexed CSV.
    - If `reduce_spatial=None`, the full array is flattened via
      `.to_dataframe()` (long-format: one row per time/lat/lon combination
      -- can be large for big grids/long time series).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if reduce_spatial is not None:
        spatial_dims = [d for d in da.dims if d in ("lat", "lon")]
        reduced = getattr(da, reduce_spatial)(dim=spatial_dims, skipna=True)
        df = reduced.to_dataframe(name=da.name or "value")
    else:
        df = da.to_dataframe(name=da.name or "value")

    df.to_csv(path)
    logger.info("Wrote CSV: %s (%d rows)", path, len(df))
    return path


def to_excel(
    data: xr.Dataset | dict[str, xr.DataArray],
    path: str | Path,
    reduce_spatial: str | None = "mean",
) -> Path:
    """Write multiple variables to one Excel file, one sheet per variable.
    Same spatial-reduction behaviour as `to_csv` (Excel is also fundamentally
    tabular). Requires `openpyxl` (pip install openpyxl).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if isinstance(data, xr.Dataset):
        items = {name: data[name] for name in data.data_vars}
    else:
        items = data

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for name, da in items.items():
            if reduce_spatial is not None:
                spatial_dims = [d for d in da.dims if d in ("lat", "lon")]
                reduced = getattr(da, reduce_spatial)(dim=spatial_dims, skipna=True) if spatial_dims else da
                df = reduced.to_dataframe(name=name)
            else:
                df = da.to_dataframe(name=name)
            # Excel sheet names are capped at 31 chars
            df.to_excel(writer, sheet_name=name[:31])

    logger.info("Wrote Excel workbook: %s (%d sheet(s))", path, len(items))
    return path


def savefig(fig: plt.Figure, path: str | Path, dpi: int = 300, close: bool = True) -> Path:
    """Save a matplotlib Figure as PNG (or PDF if `path` ends in .pdf),
    publication-resolution by default (300 dpi). Closes the figure after
    saving by default to avoid accumulating open figures in long batch runs.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    logger.info("Saved figure: %s", path)
    if close:
        plt.close(fig)
    return path


def to_geotiff(da: xr.DataArray, path: str | Path) -> Path:
    """Write a 2D (lat, lon) DataArray to GeoTIFF. Requires `rioxarray`.

    Raises a clear, actionable ImportError if rioxarray isn't installed,
    rather than letting this whole module fail to import for everyone just
    because one optional geospatial dependency is missing.
    """
    try:
        import rioxarray  # noqa: F401
    except ImportError as e:
        raise ImportError(
            "to_geotiff() requires rioxarray. Install with: pip install rioxarray"
        ) from e

    if da.ndim != 2:
        raise ValueError(f"to_geotiff expects a 2D (lat, lon) array, got dims {da.dims}")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    da_geo = da.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    da_geo = da_geo.rio.write_crs("EPSG:4326", inplace=False)
    da_geo.rio.to_raster(path)
    logger.info("Wrote GeoTIFF: %s", path)
    return path
