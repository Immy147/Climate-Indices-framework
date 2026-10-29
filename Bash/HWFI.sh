#!/bin/bash
# Usage: ./hwfi.sh input.nc output.nc refstart refend [nday]
# Computes Heat Wave Frequency (ECA index): count of days in spells of >= nday
# consecutive days where tasmax > calendar-day 90th percentile (base period refstart-refend)
# nday defaults to 3 (heat wave = 3+ consecutive hot days); ECA default is 6 if omitted.

infile=$1
outfile=$2
refstart=$3
refend=$4
nday=${5:-3}

pctlfile=$(mktemp --suffix=.nc)

# 90th percentile threshold (calendar day, 5-day window, base period)
cdo -L ydrunpctl,90,5 -selyear,${refstart}/${refend} "$infile" \
    -ydrunmin,5 -selyear,${refstart}/${refend} "$infile" \
    -ydrunmax,5 -selyear,${refstart}/${refend} "$infile" \
    "$pctlfile"

# Warm-spell / heat wave index: days in spells >= nday, annually
cdo eca_hwfi,${nday},freq=year "$infile" "$pctlfile" "$outfile"

rm -f "$pctlfile"