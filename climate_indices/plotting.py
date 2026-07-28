"""
plotting.py — Publication-oriented plots for climate index DataArrays.
Matplotlib only (no cartopy dependency) so this works in any environment;
pass a `projection`/`ax` from cartopy yourself if you want coastlines and
already have it installed -- see `plot_map`'s `ax` parameter.

Every function returns the Figure (and often Axes) it created rather than
calling plt.show(), so you can compose, save, or further edit before
displaying.
"""

from __future__ import annotations

import logging

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

logger = logging.getLogger("climate_indices.plotting")


def plot_map(
    da: xr.DataArray,
    title: str | None = None,
    cmap: str = "viridis",
    ax: plt.Axes | None = None,
    center: float | None = None,
    **kwargs,
):
    """Single spatial map of a 2D (lat, lon) DataArray.

    Parameters
    ----------
    center : float, optional
        Pass 0 for diverging change/anomaly maps (uses a diverging cmap
        centred on zero automatically, e.g. for `late - early` differences).
    """
    if da.ndim != 2:
        raise ValueError(f"plot_map expects a 2D (lat, lon) array, got dims {da.dims}")

    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(7, 5))
    else:
        fig = ax.figure

    plot_cmap = "RdBu_r" if center is not None else cmap
    da.plot(ax=ax, cmap=plot_cmap, center=center, cbar_kwargs={"label": da.attrs.get("units", "")}, **kwargs)
    ax.set_title(title or da.name or "")
    return fig, ax


def plot_multi_map(
    ds: xr.Dataset,
    variables: list[str] | None = None,
    ncols: int = 3,
    cmap_map: dict[str, str] | None = None,
    reduce_dim: str = "time",
    reduce_how: str = "mean",
):
    """Grid of maps, one per variable in `ds` (each first reduced over
    `reduce_dim`, e.g. mean over all years). Handy for "one map per index".
    """
    variables = variables or list(ds.data_vars)
    cmap_map = cmap_map or {}
    n = len(variables)
    nrows = int(np.ceil(n / ncols))

    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows))
    axes = np.atleast_1d(axes).flatten()

    for ax, var in zip(axes, variables):
        da2d = getattr(ds[var], reduce_how)(dim=reduce_dim, skipna=True)
        plot_map(da2d, title=var, cmap=cmap_map.get(var, "viridis"), ax=ax)

    for ax in axes[n:]:
        ax.axis("off")

    fig.tight_layout()
    return fig, axes


def plot_timeseries(
    da: xr.DataArray,
    weights: xr.DataArray | None = None,
    spatial_dims: tuple[str, ...] = ("lat", "lon"),
    title: str | None = None,
    ax: plt.Axes | None = None,
    **kwargs,
):
    """Spatial-mean (optionally area-weighted) annual time series line plot.

    Pass `weights=np.cos(np.deg2rad(da.lat))` for proper area weighting on
    a lat/lon grid.
    """
    ts = da.weighted(weights).mean(dim=spatial_dims) if weights is not None else da.mean(dim=spatial_dims, skipna=True)

    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 4))
    else:
        fig = ax.figure

    ax.plot(ts["time"], ts, **kwargs)
    ax.set_title(title or da.name or "")
    ax.set_ylabel(da.attrs.get("units", ""))
    ax.set_xlabel("Year")
    return fig, ax


def plot_seasonal_cycle(da_seasonal: xr.DataArray, title: str | None = None, ax: plt.Axes | None = None):
    """Bar plot of a 4-season climatology (output of stats.seasonal_climatology,
    already spatially reduced to a 1D `season`-indexed array)."""
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 4))
    else:
        fig = ax.figure
    ax.bar(da_seasonal["season"].values, da_seasonal.values)
    ax.set_title(title or "Seasonal climatology")
    ax.set_ylabel(da_seasonal.attrs.get("units", ""))
    return fig, ax


def plot_monthly_climatology(da_monthly: xr.DataArray, title: str | None = None, ax: plt.Axes | None = None):
    """Line plot of a 12-month climatology (output of stats.monthly_climatology,
    already spatially reduced to a 1D `month`-indexed array)."""
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(7, 4))
    else:
        fig = ax.figure
    month_labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    ax.plot(month_labels, da_monthly.values, marker="o")
    ax.set_title(title or "Monthly climatology")
    ax.set_ylabel(da_monthly.attrs.get("units", ""))
    return fig, ax


def plot_trend_map(
    slope: xr.DataArray,
    p_value: xr.DataArray | None = None,
    alpha: float = 0.05,
    title: str | None = None,
    ax: plt.Axes | None = None,
):
    """Trend (slope) map, diverging colormap centred at 0. If `p_value` is
    given, stippled hatching marks cells where p < alpha (statistically
    significant trend) -- the standard convention in climate trend figures.
    """
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(7, 5))
    else:
        fig = ax.figure

    slope.plot(ax=ax, cmap="RdBu_r", center=0, cbar_kwargs={"label": slope.attrs.get("units", "per year")})
    ax.set_title(title or "Trend (slope per year)")

    if p_value is not None:
        sig = (p_value < alpha).astype(float)
        # hatch significant cells
        lon2d, lat2d = np.meshgrid(sig["lon"], sig["lat"])
        ax.contourf(
            lon2d, lat2d, sig.values,
            levels=[0.5, 1.5], colors="none", hatches=["///"],
        )
    return fig, ax


def plot_histogram(da: xr.DataArray, bins: int = 30, title: str | None = None, ax: plt.Axes | None = None):
    """Histogram of all (flattened) values in `da` -- e.g. distribution of
    an index across all years and grid cells."""
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 4))
    else:
        fig = ax.figure
    values = da.values.flatten()
    values = values[~np.isnan(values)]
    ax.hist(values, bins=bins, edgecolor="black", alpha=0.7)
    ax.set_title(title or f"Distribution of {da.name}")
    ax.set_xlabel(da.attrs.get("units", ""))
    ax.set_ylabel("Count")
    return fig, ax


def plot_boxplot(
    ds: xr.Dataset,
    variables: list[str],
    reduce_dims: tuple[str, ...] = ("time", "lat", "lon"),
    title: str | None = None,
    ax: plt.Axes | None = None,
):
    """Boxplot comparing the full-distribution spread of multiple variables
    side by side (e.g. compare CDD vs CWD spread)."""
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(7, 5))
    else:
        fig = ax.figure
    data = []
    for var in variables:
        vals = ds[var].values.flatten()
        data.append(vals[~np.isnan(vals)])
    ax.boxplot(data, labels=variables)
    ax.set_title(title or "Distribution comparison")
    return fig, ax


def plot_violin(
    ds: xr.Dataset,
    variables: list[str],
    title: str | None = None,
    ax: plt.Axes | None = None,
):
    """Violin plot variant of plot_boxplot -- shows distribution shape, not
    just quartiles."""
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(7, 5))
    else:
        fig = ax.figure
    data = []
    for var in variables:
        vals = ds[var].values.flatten()
        data.append(vals[~np.isnan(vals)])
    ax.violinplot(data, showmeans=True)
    ax.set_xticks(range(1, len(variables) + 1))
    ax.set_xticklabels(variables)
    ax.set_title(title or "Distribution comparison")
    return fig, ax


def plot_heatmap(
    da_2d: xr.DataArray,
    title: str | None = None,
    cmap: str = "coolwarm",
    ax: plt.Axes | None = None,
):
    """Generic 2D heatmap for any 2D DataArray that isn't lat/lon (e.g.
    year x month table of an index)."""
    fig = None
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 5))
    else:
        fig = ax.figure
    im = ax.imshow(da_2d.values, aspect="auto", cmap=cmap)
    ax.set_xticks(range(len(da_2d.coords[da_2d.dims[1]])))
    ax.set_xticklabels(da_2d.coords[da_2d.dims[1]].values, rotation=45)
    ax.set_yticks(range(len(da_2d.coords[da_2d.dims[0]])))
    ax.set_yticklabels(da_2d.coords[da_2d.dims[0]].values)
    plt.colorbar(im, ax=ax, label=da_2d.attrs.get("units", ""))
    ax.set_title(title or da_2d.name or "")
    return fig, ax


def plot_anomaly_map(
    da: xr.DataArray,
    baseline_start: str,
    baseline_end: str,
    period_start: str,
    period_end: str,
    title: str | None = None,
    ax: plt.Axes | None = None,
):
    """Map of (period mean - baseline mean), diverging colormap centred at
    0. This is the standard "climate change signal" map."""
    baseline = da.sel(time=slice(baseline_start, baseline_end)).mean(dim="time", skipna=True)
    period = da.sel(time=slice(period_start, period_end)).mean(dim="time", skipna=True)
    anomaly = period - baseline
    anomaly.attrs["units"] = da.attrs.get("units", "")
    label = title or f"{da.name}: {period_start}-{period_end} minus {baseline_start}-{baseline_end}"
    return plot_map(anomaly, title=label, center=0, ax=ax)
