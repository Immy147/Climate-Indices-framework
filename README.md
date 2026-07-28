# climate-indices-framework

Modular, tested Python pipeline for computing ETCCDI climate extreme indices (TXx, TX90p,
WSDI, RX1day, RX5day, CDD, CWD, R95p, R99p, and more) from daily `tasmax` and `pr` NetCDF
data — built for large (multi-GB), Dask-backed CMIP6/CORDEX/ISIMIP/ERA5-scale datasets.

## Scope

Computes the **19 ETCCDI indices derivable from `tasmax` + `pr` alone**:

| Category | Indices |
|---|---|
| Temperature (tasmax) | TXx, TXn, TX90p, TX10p, WSDI, SU, ID |
| Precipitation (pr) | RX1day, RX5day, PRCPTOT, SDII, R10mm, R20mm, CDD, CWD, R95p, R99p, P95D, P99D |

**Not included** (needs inputs this pipeline doesn't ingest):
- `TNx, TNn, TN90p, TN10p, CSDI, TR, DTR, GSL` — require `tasmin` or `tas` (daily mean)
- `SPI, SPEI` — SPEI requires PET (potential evapotranspiration)
- Shapefile/GeoPackage spatial clipping — requires a boundary file

## Installation

```bash
git clone <this-repo>
cd climate-indices-framework
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`rioxarray` (GeoTIFF export only) is the sole non-essential dependency — everything else is
required.

## Quick start

### Notebook
Open `run_pipeline.ipynb`, set `tasmax_path`/`pr_path` near the top (a single `.nc` file OR a
directory — searched recursively), run top to bottom.

### CLI
```bash
python run_pipeline_script.py \
    --tasmax data/tasmax --pr data/pr \
    --ref-start 1985 --ref-end 2014 \
    --output-dir outputs
```
Run `python run_pipeline_script.py --help` for the full flag list (unit conversion, cleaning,
trend skip, plot skip, etc.).

## Package layout

```
climate_indices/
├── io_utils.py          Reading: single file / multi-file / directory, name normalization
├── validate.py           Metadata, coordinate, time, missing-data, physical-range checks
├── clean.py                Invalid-value masking, gap interpolation
├── units.py                 Kelvin<->Celsius, flux<->mm/day conversion
├── indices_temp.py           TXx, TXn, TX90p, TX10p, WSDI, SU, ID
├── indices_precip.py          RX1day, RX5day, PRCPTOT, SDII, R10mm, R20mm, CDD, CWD, R95p, R99p, P95D, P99D
├── stats.py                    Summary stats, climatology, linear trend, Sen's slope, Mann-Kendall
├── plotting.py                  11 plot types (maps, time series, trend maps, distributions, ...)
├── export.py                     NetCDF / CSV / Excel / PNG / GeoTIFF, structured output dirs
└── logging_utils.py                File logging + timed_step() context manager
```

## Output structure

```
outputs/
├── indices/        all_indices.nc
├── statistics/      *_annual_areamean.csv, *_linear_trend.nc, *_mann_kendall.nc, *.xlsx
├── plots/             *.png
└── logs/                run_*.log
```

## ⚠️ Known gotchas (read before a production run)

These were all hit and fixed during real use on a full CMIP6 (ACCESS-ESM1-5, historical +
ssp126) dataset — documenting them here so you don't lose time rediscovering them.

1. **Percentile/quantile operations need a single chunk along `time`.**
   `TX90p`, `TX10p`, `WSDI`, `R95p`, `R99p`, `P95D`, `P99D`, and every `stats.py` function
   (`summary_stats`, `linear_trend`, `sens_slope`, `mann_kendall_trend`) reduce over `time`.
   If you see:
   ```
   ValueError: dimension time on 0th function argument to apply_ufunc with
   dask='parallelized' consists of multiple chunks, but is also a core dimension.
   ```
   rechunk first: `da = da.chunk({"time": -1})`. The indices module functions handle this
   internally; if you're calling `stats.py` directly on data reopened from disk (which gets
   its own arbitrary chunking), rechunk once right after loading:
   ```python
   all_indices = all_indices.chunk({"time": -1})
   ```

2. **Percentile thresholds also need lat/lon chunked, not left whole**, or a single
   reference-period chunk can be gigabytes and Dask will appear to hang. Both
   `compute_tx_percentile_thresholds` and `compute_wetday_percentile_thresholds` take a
   `spatial_chunk` parameter (default 50) — lower it (e.g. 20–30) on large/high-res grids:
   ```python
   compute_temperature_indices(tasmax, ref_start, ref_end, spatial_chunk=30)
   compute_precipitation_indices(pr, ref_start, ref_end, spatial_chunk=30)
   ```

3. **Physical-range validation/cleaning is unit-aware — order of operations matters.**
   `validate.py`/`clean.py` look up plausible ranges keyed to the array's *current* `units`
   attribute. Always run `units.convert_dataset_units()` BEFORE `clean.clean_dataset()`, or
   the range check will compare Celsius values against a Kelvin range (or vice versa) and
   mask everything to NaN.

4. **NumPy 2.x removed `+` concatenation between unicode string arrays.**
   Anywhere converting an integer `year` coordinate to a real datetime (`_year_to_datetime`
   in `indices_temp.py`/`indices_precip.py`, `annual_mean` in `stats.py`) uses a Python
   list-comprehension (`[f"{y}-01-01" for y in years]`) rather than `.astype(str) + "-01-01"`
   for this reason — the latter throws `UFuncTypeError` on some NumPy versions.

5. **`rioxarray` defaults to `x`/`y` dim names.** `export.to_geotiff()` explicitly declares
   `lat`/`lon` as the spatial dims via `rio.set_spatial_dims()` before writing — if you add
   your own GeoTIFF export code elsewhere, remember to do the same.

6. **Save large final outputs one variable at a time**, not as one big merged `to_netcdf()`
   call — safer to debug (know exactly which variable is slow/failing) and resumable:
   ```python
   from dask.diagnostics import ProgressBar
   for name, da in all_indices.data_vars.items():
       with ProgressBar():
           da.to_dataset(name=name).to_netcdf(f"indices_partial/{name}.nc")
   ```

7. **Reference period must fall entirely inside the historical experiment**, not spill into
   a scenario (ssp126/ssp585/etc.) — otherwise percentile baselines get contaminated with
   future-scenario values. Check `ds_tasmax.time.min()/.max()` after loading, before setting
   `ref_start`/`ref_end`.

## Testing

Every module was validated against synthetic data with known trends/thresholds before being
used on real data. Bugs caught this way (all fixed in the current code): a unit-unaware
physical-range check, a GeoTIFF dim-naming crash, and the NumPy string-concatenation issue
above.

---

## Citation

If you use this repository in your research, please cite the relevant climate datasets, ETCCDI methodology, and software packages used in your analysis.

---

## Contributing

Contributions are welcome. Feel free to submit issues, feature requests, or pull requests to improve the workflow.

---

## License

This project is distributed under the MIT License.

---

## Author

**Imran Ul Haq**

Research Engineer
Weather and Climate Services, Islamabad, Pakistan.


Research interests include:

- Climate Attribution
- Climate Indices
- Climate Change
- Climate Extremes
- Geospatial Data Science
- Earth System Modelling
- Environmental Analytics
