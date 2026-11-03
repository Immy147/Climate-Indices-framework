#!/bin/bash
# Usage: ./hotdays.sh input.nc output.nc
# Computes Hot Days (ETCCDI/ECA index): annual count of days with daily maximum temperature > 25°C

infile=$1
outfile=$2


cdo yearsum -gtc,25 -subc,273.15 "$infile" "$outfile"