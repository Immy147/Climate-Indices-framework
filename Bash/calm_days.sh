
#!/bin/bash
# Usage: ./calm_days.sh input.nc output.nc
# Index: Annual number of calm days
# Definition: Daily mean sfcWind < 0.5 m/s
# Output units: days/year

set -euo pipefail

infile=$1
outfile=$2

# Count calm days at each grid cell for each year.
cdo -O yearcount -ltc,0.5 "$infile" "$outfile"
