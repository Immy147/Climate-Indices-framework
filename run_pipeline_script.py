#!/usr/bin/env python3
"""
run_pipeline.py — Standalone CLI version of the climate indices pipeline.

Mirrors run_pipeline.ipynb: read -> validate -> convert units -> clean ->
compute ETCCDI indices (tasmax + pr) -> [optional] trend stats -> plots ->
export, all through the `climate_indices` package.

Usage
-----
    python run_pipeline.py --tasmax tasmax.nc --pr pr.nc \
        --ref-start 1985 --ref-end 2014 \
        --output-dir outputs

    # Skip the slow per-gridcell Mann-Kendall trend test:
    python run_pipeline.py --tasmax tasmax.nc --pr pr.nc --no-trends

    # Point at a directory of files instead of a single file:
    python run_pipeline.py --tasmax data/tasmax/ --pr data/pr/ --output-dir outputs

Run `python run_pipeline.py --help` for all options.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless-safe; script is meant to run unattended

import numpy as np
import xarray as xr

sys.path.insert(0, str(Path(__file__).resolve().parent))
import climate_indices as ci


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compute ETCCDI climate indices from tasmax/pr NetCDF data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--tasmax", required=True, help="Path to a tasmax .nc file, or a directory of them.")
    p.add_argument("--pr", required=True, help="Path to a pr .nc file, or a directory of them.")
    p.add_argument("--output-dir", default="outputs", help="Root output directory.")
    p.add_argument("--ref-start", default="1985", help="Reference period start year (percentile-based indices).")
    p.add_argument("--ref-end", default="2014", help="Reference period end year.")
    p.add_argument("--time-chunk", type=int, default=365, help="Dask chunk size along the time dimension.")
    p.add_argument("--su-thresh", default="25.0 degC", help="Threshold for Summer Days (SU) index.")
    p.add_argument("--wet-thresh", type=float, default=1.0, help="Wet-day threshold (mm/day) for CDD/CWD/R10mm/etc.")
    p.add_argument("--no-clean", action="store_true", help="Skip physical-range masking.")
    p.add_argument("--interpolate", action="store_true", help="Interpolate small NaN gaps (max_gap=5 by default).")
    p.add_argument(
        "--no-trends", action="store_true",
        help="Skip Mann-Kendall trend analysis (slow, per-gridcell loop -- see stats.py docstring).",
    )
    p.add_argument("--no-plots", action="store_true", help="Skip generating summary plots.")
    p.add_argument("--full-validation", action="store_true",
                    help="Run validation on the FULL array instead of a ~365-step sample (slower, thorough).")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    dirs = ci.export.make_output_dirs(args.output_dir)
    log_path = ci.logging_utils.setup_logging(dirs["base"] / "logs", run_name="cli")
    logger = logging.getLogger("climate_indices")
    logger.info("Run configuration: %s", vars(args))

    chunks = {"time": args.time_chunk, "lat": -1, "lon": -1}

    # --- 1. Read ---
    with ci.logging_utils.timed_step("Reading tasmax/pr", logger):
        ds_tasmax = ci.io_utils.read_dataset(args.tasmax, variable="tasmax", chunks=chunks)
        ds_pr = ci.io_utils.read_dataset(args.pr, variable="pr", chunks=chunks)

    # --- 2. Validate ---
    with ci.logging_utils.timed_step("Validating tasmax", logger):
        report_tasmax = ci.validate.validate_dataset(
            ds_tasmax, "tasmax", sample_for_expensive_checks=not args.full_validation
        )
        logger.info("\n%s", report_tasmax.summary())
        if report_tasmax.errors:
            logger.error("Fatal errors in tasmax validation -- aborting. See log for details.")
            return 1

    with ci.logging_utils.timed_step("Validating pr", logger):
        report_pr = ci.validate.validate_dataset(
            ds_pr, "pr", sample_for_expensive_checks=not args.full_validation
        )
        logger.info("\n%s", report_pr.summary())
        if report_pr.errors:
            logger.error("Fatal errors in pr validation -- aborting. See log for details.")
            return 1

    # --- 3. Units ---
    with ci.logging_utils.timed_step("Converting units", logger):
        ds_tasmax = ci.units.convert_dataset_units(ds_tasmax, {"tasmax": "degC"})
        ds_pr = ci.units.convert_dataset_units(ds_pr, {"pr": "mm/day"})

    # --- 4. Clean ---
    if not args.no_clean:
        with ci.logging_utils.timed_step("Cleaning tasmax/pr", logger):
            ds_tasmax = ci.clean.clean_dataset(
                ds_tasmax, "tasmax", mask_out_of_range=True, interpolate=args.interpolate
            )
            ds_pr = ci.clean.clean_dataset(
                ds_pr, "pr", mask_out_of_range=True, interpolate=args.interpolate
            )

    # --- 5. Indices ---
    with ci.logging_utils.timed_step("Computing temperature indices", logger):
        temp_indices = ci.indices_temp.compute_temperature_indices(
            ds_tasmax["tasmax"], ref_start=args.ref_start, ref_end=args.ref_end, su_thresh=args.su_thresh
        )

    with ci.logging_utils.timed_step("Computing precipitation indices", logger):
        precip_indices = ci.indices_precip.compute_precipitation_indices(
            ds_pr["pr"], ref_start=args.ref_start, ref_end=args.ref_end, wet_thresh=args.wet_thresh
        )

    all_indices = xr.merge([temp_indices, precip_indices])

    # --- 6. Save indices (this is where computation actually triggers) ---
    with ci.logging_utils.timed_step("Saving indices to NetCDF", logger):
        ci.export.to_netcdf(all_indices, dirs["indices"] / "all_indices.nc")

    # reopen the (much smaller) output for stats/plots/export downstream,
    # rather than re-triggering the full Dask graph repeatedly
    all_indices = xr.open_dataset(dirs["indices"] / "all_indices.nc", decode_timedelta=False)

    # --- 7. Stats ---
    if not args.no_trends:
        with ci.logging_utils.timed_step("Trend analysis (linear + Mann-Kendall)", logger):
            for var in ["TXx", "TX90p", "WSDI", "RX1day", "CDD"]:
                if var not in all_indices.data_vars:
                    continue
                lt = ci.stats.linear_trend(all_indices[var])
                ci.export.to_netcdf(lt, dirs["statistics"] / f"{var}_linear_trend.nc")
                mk = ci.stats.mann_kendall_trend(all_indices[var])
                ci.export.to_netcdf(mk, dirs["statistics"] / f"{var}_mann_kendall.nc")
    else:
        logger.info("Skipping trend analysis (--no-trends).")

    # --- 8. Plots ---
    if not args.no_plots:
        with ci.logging_utils.timed_step("Generating summary plots", logger):
            available = [v for v in ["TXx", "TX90p", "WSDI", "RX1day", "CDD", "R95p"] if v in all_indices.data_vars]
            fig, _ = ci.plotting.plot_multi_map(all_indices, variables=available)
            ci.export.savefig(fig, dirs["plots"] / "index_climatology_maps.png")

            weights = np.cos(np.deg2rad(all_indices.lat))
            weights.name = "weights"
            for var in available:
                fig, ax = ci.plotting.plot_timeseries(
                    all_indices[var], weights=weights, title=f"Area-weighted annual {var}"
                )
                ci.export.savefig(fig, dirs["plots"] / f"{var}_timeseries.png")
    else:
        logger.info("Skipping plots (--no-plots).")

    # --- 9. CSV/Excel summary export ---
    with ci.logging_utils.timed_step("Exporting CSV/Excel summaries", logger):
        for var in all_indices.data_vars:
            ci.export.to_csv(all_indices[var], dirs["statistics"] / f"{var}_annual_areamean.csv")
        ci.export.to_excel(all_indices, dirs["statistics"] / "all_indices_summary.xlsx")

    logger.info("Pipeline complete. Outputs under: %s", dirs["base"])
    logger.info("Log file: %s", log_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
