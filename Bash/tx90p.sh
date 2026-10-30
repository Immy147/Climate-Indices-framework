#!/bin/bash
# Usage: ./tx90p_final.sh input.nc output.nc refstart refend
# Computes TX90p (ETCCDI index, bootstrapped, Zhang et al. 2005):
# annual % of days with tasmax above the calendar-day 90th percentile
# of the reference period (refstart-refend), 5-day circular window,
# R8 percentile method, exact-value CDO_PCTL_NBINS binning.

set -euo pipefail

infile=$1
outfile=$2
refstart=$3
refend=$4

export CDO_PCTL_NBINS=$((5*(refend-refstart+1)*2+2))
echo "CDO_PCTL_NBINS=${CDO_PCTL_NBINS}"

baseline=$(mktemp --suffix=.nc)
runmin=$(mktemp --suffix=.nc)
runmax=$(mktemp --suffix=.nc)
trap 'rm -f "$baseline" "$runmin" "$runmax"' EXIT

# NOTE: rm=c (circular mode) cannot be piped -- ydrunmin/ydrunmax,rm=c must
# read from a materialized file, not from a chained "-selyear ..." operator.
# Piping into it fails with: "Operators cannot be piped in circular mode".
echo "[1/4] Extracting reference period ${refstart}-${refend}..."
time cdo -O selyear,${refstart}/${refend} "$infile" "$baseline"

echo "[2/4] Computing 5-day running min..."
time cdo -O ydrunmin,5,rm=c "$baseline" "$runmin"

echo "[3/4] Computing 5-day running max..."
time cdo -O ydrunmax,5,rm=c "$baseline" "$runmax"

echo "[4/4] Computing bootstrapped TX90p..."
time cdo -O etccdi_tx90p,5,${refstart},${refend} "$infile" "$runmin" "$runmax" "$outfile"

echo "Done. Saved to $outfile"