#!/bin/bash
set -euo pipefail

# Usage: ./cfd.sh input.nc output.nc
# Computes annual CFD using eca_cfd across yearly splits.


infile=$1
outfile=$2

tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT

cdo -L splityear -setrtomiss,1e19,1e21 "$infile" "$tmpdir/year_"

for f in "$tmpdir"/year_*.nc; do
    cdo -L -selname,consecutive_frost_days_index_per_time_period -eca_cfd "$f" "${f%.nc}_cfd.nc"
done

cdo -O -L mergetime "$tmpdir"/year_*_cfd.nc "$outfile"