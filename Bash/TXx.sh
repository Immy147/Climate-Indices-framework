#!/bin/bash
# Usage: ./txx.sh input.nc output.nc
# Computes TXx (ETCCDI/ECA index): annual maximum of daily maximum temperature (tasmax)

infile=$1
outfile=$2


cdo  subc,273.15  -yearmax "$infile" "$outfile"