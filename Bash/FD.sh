#!/bin/bash
# Usage: ./fd.sh input.nc output.nc
# Computes FD (ETCCDI index): number of frost days per year (tasmin < 0 degC)

infile=$1
outfile=$2

cdo etccdi_fd "$infile" "$outfile"