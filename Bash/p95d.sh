#!/bin/bash
set -e

#---------------------------------------------------------
# Calculate P95D (Annual Number of Days >= 95th Percentile)
#
# Usage:
#   ./calc_p95d.sh input.nc output.nc 1980-01-01 2009-12-31
#
# Example:
#   ./calc_p95d.sh \
#       pr_daily.nc \
#       P95D_annual.nc \
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

# Automatically remove temporary files on exit
trap 'rm -rf "$TMPDIR"' EXIT

echo "========================================"
echo "Calculating P95D"
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
# Step 3: Calculate the 95th percentile threshold
# (single threshold for each grid cell)
#---------------------------------------------------------
cdo timpctl,95 \
    "$TMPDIR/reference_wet.nc" \
    -timmin "$TMPDIR/reference_wet.nc" \
    -timmax "$TMPDIR/reference_wet.nc" \
    "$TMPDIR/p95_threshold.nc"

#---------------------------------------------------------
# Step 4: Create binary exceedance field
# 1 = precipitation >= P95 threshold
# 0 = otherwise
#---------------------------------------------------------
cdo ge \
    "$INFILE" \
    "$TMPDIR/p95_threshold.nc" \
    "$TMPDIR/p95_binary.nc"

#---------------------------------------------------------
# Step 5: Count exceedances for each year (P95D)
#---------------------------------------------------------
cdo yearsum \
    "$TMPDIR/p95_binary.nc" \
    "$OUTFILE"

echo "========================================"
echo "P95D calculation completed successfully."
echo "Output written to:"
echo "  $OUTFILE"
echo "========================================"