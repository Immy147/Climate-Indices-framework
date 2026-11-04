#!/bin/bash
# Usage: ./su.sh input.nc output.nc
# Computes SU (ETCCDI index): number of summer days per year (tasmax > 25 degC)

infile=$1
outfile=$2

cdo etccdi_su "$infile" "$outfile"