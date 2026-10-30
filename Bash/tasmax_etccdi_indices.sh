#!/bin/bash
# Usage: ./tasmax_etccdi_indices.sh infile infile outfile refstart refend
# infile   : target tasmax file the indices are computed over
# outfile  : output prefix
# refstart : reference period start year (e.g. 1980)
# refend   : reference period end year (e.g. 2000)

infile=$1
outfile=$2
refstart=$3
refend=$4

# # --- TXx: annual maximum of daily maximum temperature ---
# cdo subc,273.15 -yearmax "$infile" "${outfile}_TXx.nc"
# echo "TXx is calculated successfully"

# --- Hot Days: days > 25°C
cdo yearsum -gtc,25 -subc,273.15 "$infile" "${outfile}_HotDays25.nc"
echo "Hot Days are calculated successfully"

# --- restrict infile to the fixed reference period ---
refperiod=${outfile}_tasmax_ref.nc
cdo selyear,${refstart}/${refend} "$infile" "$refperiod"

# --- percentile threshold prep (shared by TX90p and WSDI) ---
runmin=${outfile}_tasmax_runmin.nc
runmax=${outfile}_tasmax_runmax.nc
tx90thresh=${outfile}_tx90thresh.nc

export CDO_PCTL_NBINS=$((5*(refend-refstart+1)*2+2))

cdo ydrunmin,5,rm=c "$refperiod" "$runmin"
cdo ydrunmax,5,rm=c "$refperiod" "$runmax"
cdo subc,273.15 -ydrunpctl,90,5,pm=r8,rm=c "$refperiod" "$runmin" "$runmax" "$tx90thresh"

# --- TX90p: % days tasmax > 90th percentile (threshold built from infile) ---
cdo etccdi_tx90p,5,${refstart},${refend},freq=year "$infile" "$runmin" "$runmax" "${outfile}_TX90p.nc"
echo "TX90p is calculated successfully"

# --- WSDI (warm spell duration index, threshold built from infile) ---
cdo etccdi_wsdi -subc,273.15 "$infile" "$tx90thresh" "${outfile}_WSDI.nc"
echo "WSDI is calculated successfully"

# --- HWFI (Heat Wave Frequency Index, threshold built form infile) ---
cdo etccdi_hwfi -subc,273.15 "$infile" "$tx90thresh" "${outfile}_HWFI.nc"
echo "HWFI is calculated successfully"

rm -f "$refperiod" "$runmin" "$runmax" "$tx90thresh"