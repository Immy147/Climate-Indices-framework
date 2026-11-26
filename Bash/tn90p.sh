#!/bin/bash
# Usage: ./tn90p.sh input.nc output.nc refstart refend
# Computes TN90p (ETCCDI core index, bootstrapped, Zhang et al. 2005):
# annual % of days with tasmin above the calendar-day 90th percentile
# of the reference period (refstart-refend), 5-day circular window.

set -euo pipefail

infile=$1
outfile=$2
refstart=$3
refend=$4

export CDO_PCTL_NBINS=$((5*(refend-refstart+1)*2+2))
echo "CDO_PCTL_NBINS=${CDO_PCTL_NBINS}"

clean=$(mktemp --suffix=.nc)
baseline=$(mktemp --suffix=.nc)
runmin=$(mktemp --suffix=.nc)
runmax=$(mktemp --suffix=.nc)
trap 'rm -f "$clean" "$baseline" "$runmin" "$runmax"' EXIT

# rm=c (circular mode) cannot be piped, so each step reads a materialized file.
echo "[1/4] Masking fill values and extracting reference period ${refstart}-${refend}..."
cdo -O setrtomiss,1e19,1e21 "$infile" "$clean"
cdo -O selyear,${refstart}/${refend} "$clean" "$baseline"

echo "[2/4] Computing 5-day running min..."
cdo -O ydrunmin,5,rm=c "$baseline" "$runmin"

echo "[3/4] Computing 5-day running max..."
cdo -O ydrunmax,5,rm=c "$baseline" "$runmax"

echo "[4/4] Computing bootstrapped TN90p..."
cdo -O etccdi_tn90p,5,${refstart},${refend} "$clean" "$runmin" "$runmax" "$outfile"

echo "Done. Saved to $outfile"