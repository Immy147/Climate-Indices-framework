
#!/bin/bash
# Usage: ./sfcwind_max.sh input.nc output.nc
# Index: Annual maximum daily surface wind speed
# Output units: m/s

set -euo pipefail

infile=$1
outfile=$2

cdo -O yearmax "$infile" "$outfile"

