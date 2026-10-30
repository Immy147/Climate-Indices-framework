
#!/bin/bash
# Usage: ./wind_days.sh input.nc output.nc
# Index: Annual number of windy days
# Definition: Daily mean sfcWind >= 10 m/s
# Output units: days/year

set -euo pipefail

infile=$1
outfile=$2

# Count days with wind speed >= 10 m/s.
cdo -O yearcount -gec,10 "$infile" "$outfile"
