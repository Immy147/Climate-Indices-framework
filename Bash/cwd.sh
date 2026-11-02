#!/usr/bin/env bash
set -euo pipefail

# CWD: Consecutive Wet Days - the longest run of consecutive days per year

INFILE=$1
OUTFILE=$2

# find the longest run of wet days
# (>= 1 mm) in each year.
echo "Computing Consecutive Wet Days (CWD)..."
cdo -L etccdi_cwd "$INFILE" "$OUTFILE"

echo "Done. Saved to $OUTFILE"