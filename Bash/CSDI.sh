#!/bin/bash
# Usage: ./csdi.sh input.nc output.nc refstart refend
# Computes CSDI (ETCCDI core index, Zhang et al. 2011): annual count of days
# in spells of at least 6 consecutive days with tasmin below the calendar-day
# 10th percentile of the reference period (5-day window).

set -euo pipefail

infile=$1
outfile=$2
refstart=$3
refend=$4

export CDO_PCTL_NBINS=$((5*(refend-refstart+1)*2+2))

clean=$(mktemp --suffix=.nc)
baseline=$(mktemp --suffix=.nc)
runmin=$(mktemp --suffix=.nc)
runmax=$(mktemp --suffix=.nc)
pctl10=$(mktemp --suffix=.nc)
trap 'rm -f "$clean" "$baseline" "$runmin" "$runmax" "$pctl10"' EXIT

echo "[1/4] Masking fill values and extracting reference period ${refstart}-${refend}..."
cdo -O setrtomiss,1e19,1e21 "$infile" "$clean"
cdo -O selyear,${refstart}/${refend} "$clean" "$baseline"

echo "[2/4] Computing 5-day running min and max..."
cdo -O ydrunmin,5,rm=c "$baseline" "$runmin"
cdo -O ydrunmax,5,rm=c "$baseline" "$runmax"

echo "[3/4] Computing calendar-day 10th percentile..."
cdo -O ydrunpctl,10,5,rm=c "$baseline" "$runmin" "$runmax" "$pctl10"

echo "[4/4] Computing CSDI..."
cdo -O etccdi_csdi,6 "$clean" "$pctl10" "$outfile"

echo "Done. Saved to $outfile"