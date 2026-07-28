"""
climate_indices — a modular framework for reading, validating, cleaning,
and computing ETCCDI climate indices from tasmax/pr NetCDF data.
"""

from . import io_utils, validate, clean, units, indices_temp, indices_precip, stats, plotting, export, logging_utils

__all__ = [
    "io_utils",
    "validate",
    "clean",
    "units",
    "indices_temp",
    "indices_precip",
    "stats",
    "plotting",
    "export",
    "logging_utils",
]
