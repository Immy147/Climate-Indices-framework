#!/bin/bash
set -e

#---------------------------------------------------------
# Calculate P99D (Annual Number of Days >= 99th Percentile)
#
# Usage:
#   ./calc_p99d.sh input.nc output.nc 1980-01-01 2009-12-31
#
# Example:
#   ./calc_p99d.sh \
#       pr_daily.nc \
#       P99D_annual.nc \
#       1980-01-01 \
#       2009-12-31
#---------------------------------------------------------

if [ $# -ne 4 ]; then
    echo "Usage: $0 <input.nc> <output.nc> <reference_start> <reference_end>"
    exit 1
fi

INFILE=$1
OUTFILE=$2
REF_START=$3
REF_END=$4

# Check input file exists
if [ ! -f "$INFILE" ]; then
    echo "Error: Input file '$INFILE' not found."
    exit 1
fi

# Create temporary working directory
TMPDIR=$(mktemp -d)

# Remove temporary files automatically on exit
trap 'rm -rf "$TMPDIR"' EXIT

echo "========================================"
echo "Calculating P99D"
echo "Input File      : $INFILE"
echo "Output File     : $OUTFILE"
echo "Reference Period: $REF_START to $REF_END"
echo "========================================"

#---------------------------------------------------------
# Step 1: Extract reference period
#---------------------------------------------------------
cdo selyear,$REF_START,$REF_END \
    "$INFILE" \
    "$TMPDIR/reference.nc"

#---------------------------------------------------------
# Step 2: Keep only wet days (>1 mm)
#---------------------------------------------------------
cdo setrtomiss,-1000,1 \
    "$TMPDIR/reference.nc" \
    "$TMPDIR/reference_wet.nc"

#---------------------------------------------------------
# Step 3: Calculate the 99th percentile threshold
# (one threshold per grid cell)
#---------------------------------------------------------
cdo timpctl,99 \
    "$TMPDIR/reference_wet.nc" \
    -timmin "$TMPDIR/reference_wet.nc" \
    -timmax "$TMPDIR/reference_wet.nc" \
    "$TMPDIR/p99_threshold.nc"

#---------------------------------------------------------
# Step 4: Create binary exceedance field
# 1 = precipitation >= P99 threshold
# 0 = otherwise
#---------------------------------------------------------
cdo ge \
    "$INFILE" \
    "$TMPDIR/p99_threshold.nc" \
    "$TMPDIR/p99_binary.nc"

#---------------------------------------------------------
# Step 5: Count annual exceedance days (P99D)
#---------------------------------------------------------
cdo yearsum \
    "$TMPDIR/p99_binary.nc" \
    "$OUTFILE"

echo "========================================"
echo "P99D calculation completed successfully."
echo "Output written to:"
echo "  $OUTFILE"
echo "========================================"