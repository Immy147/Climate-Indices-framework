
#!/bin/bash
# Usage: ./sfcwind_mean.sh input.nc output.nc
# Index: Annual mean surface wind speed
# Output units: m/s

set -euo pipefail

infile=$1
outfile=$2

cdo -O yearmean "$infile" "$outfile"
