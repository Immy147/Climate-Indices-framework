#!/bin/bash
# Usage: ./hwfi.sh input.nc output.nc refstart refend
# Computes WSDI (Warm Spell Duration Index, ETCCDI): annual count of days in
# spells of >= 6 consecutive days where tasmax > calendar-day 90th percentile
# (base period refstart-refend, 5-day window).

infile=$1
outfile=$2
refstart=$3
refend=$4

export CDO_PCTL_NBINS=$((5*(refend-refstart+1)*2+2))

baseline=$(mktemp --suffix=.nc)
runmin=$(mktemp --suffix=.nc)
runmax=$(mktemp --suffix=.nc)
tx90thresh=$(mktemp --suffix=.nc)

cdo selyear,${refstart}/${refend} "$infile" "$baseline"
cdo ydrunmin,5,rm=c "$baseline" "$runmin"
cdo ydrunmax,5,rm=c "$baseline" "$runmax"
cdo ydrunpctl,90,5,pm=r8,rm=c "$baseline" "$runmin" "$runmax" "$tx90thresh"

cdo etccdi_wsdi "$infile" "$tx90thresh" "$outfile"

rm -f "$baseline" "$runmin" "$runmax" "$tx90thresh"
 