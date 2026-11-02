#!/bin/bash
# Usage: ./heatwavefreq.sh input.nc output.nc refstart refend
# Computes Heat Wave Frequency: annual count of heat wave events
# (heat wave = 3+ consecutive days with tasmax > calendar-day 90th percentile, base period refstart-refend)

infile=$1
outfile=$2
refstart=$3
refend=$4

script_dir=$(dirname "$0")
pctlfile=$(mktemp --suffix=.nc)
maskfile=$(mktemp --suffix=.nc)

# 90th percentile threshold (calendar day, 5-day window, base period)
cdo -L ydrunpctl,90,5 -selyear,${refstart}/${refend} "$infile" \
    -ydrunmin,5 -selyear,${refstart}/${refend} "$infile" \
    -ydrunmax,5 -selyear,${refstart}/${refend} "$infile" \
    "$pctlfile"

# Daily exceedance mask: 1 = tasmax above threshold, 0 = below
cdo -L gtc,0 -ydaysub "$infile" "$pctlfile" "$maskfile"

# Count runs of >=3 consecutive exceedance days, per year
python3 "$script_dir/heatwavefreq_runlength.py" "$maskfile" "$outfile"

rm -f "$pctlfile" "$maskfile"
