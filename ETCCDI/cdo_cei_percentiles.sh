#!/bin/sh
# ETCCDI percentile-based indices — CNRM-ESM2-1 ssp585
# Indices: tx90p, tx10p, tn90p, tn10p, r95p, r99p
# Period : 2071-2100 (30-year subset)
# All three variables are single files (2015-2100); selyear 
# used to match reference script pattern exactly.

cdo=cdo

# --- switches ---
prepareTimeseries=Y
prepareHistogram=Y
tx90p=Y
tx10p=Y
tn90p=Y
tn10p=Y
r95p=Y
r99p=Y

# --- metadata ---
source_id=CNRM-ESM2-1
experiment_id=ssp585
member_id=r1i1p1f2
startyear=2071
endyear=2100

# --- raw input paths ---
base=/media/wcs/Disk3/abbas/geomip_models/CNRM-ESM2-1

rawTasmax=${base}/tasmax/ssp585/tasmax_day_CNRM-ESM2-1_ssp585_r1i1p1f2_gr_20150101-21001231.nc
rawTasmin=${base}/tasmin/ssp585/tasmin_day_CNRM-ESM2-1_ssp585_r1i1p1f2_gr_20150101-21001231.nc
rawPr=${base}/pr/ssp585/pr_day_CNRM-ESM2-1_ssp585_r1i1p1f2_gr_20150101-21001231.nc

# --- output dirs ---
outBase=/media/wcs/Disk3/abbas/etccdi_extreme_indices/cei_percentiles
mkdir -p ${outBase}

mergedDir=${outBase}/timeseries
cdoOutput=${outBase}/indices
mkdir -p ${mergedDir} ${cdoOutput}

# --- timeseries file paths ---
tag=${source_id}_${experiment_id}_${member_id}_${startyear}-${endyear}
tasmaxMerged=${mergedDir}/tasmax_${tag}.nc
tasminMerged=${mergedDir}/tasmin_${tag}.nc
prMerged=${mergedDir}/pr_${tag}.nc

# --- prepare timeseries (selyear + mergetime; single-file case) ---
if [[ $prepareTimeseries == Y ]]; then
  echo "[prepare] tasmax: selyear ${startyear}/${endyear}..."
  $cdo selyear,${startyear}/${endyear} -mergetime ${rawTasmax} ${tasmaxMerged}

  echo "[prepare] tasmin: selyear ${startyear}/${endyear}..."
  $cdo selyear,${startyear}/${endyear} -mergetime ${rawTasmin} ${tasminMerged}

  echo "[prepare] pr: selyear ${startyear}/${endyear}..."
  $cdo selyear,${startyear}/${endyear} -mergetime ${rawPr} ${prMerged}
fi

# --- running min/max for histogram limits ---
tasminrunmin=${cdoOutput}/tasmin_runmin_${tag}.nc
tasminrunmax=${cdoOutput}/tasmin_runmax_${tag}.nc
tasmaxrunmin=${cdoOutput}/tasmax_runmin_${tag}.nc
tasmaxrunmax=${cdoOutput}/tasmax_runmax_${tag}.nc
prtimmin=${cdoOutput}/pr_timmin_${tag}.nc
prtimmax=${cdoOutput}/pr_timmax_${tag}.nc

if [[ $prepareHistogram == Y ]]; then
  echo "[histogram] Computing running min/max and pr time bounds..."
  $cdo ydrunmin,5,rm=c ${tasminMerged} ${tasminrunmin}
  $cdo ydrunmax,5,rm=c ${tasminMerged} ${tasminrunmax}
  $cdo ydrunmin,5,rm=c ${tasmaxMerged} ${tasmaxrunmin}
  $cdo ydrunmax,5,rm=c ${tasmaxMerged} ${tasmaxrunmax}
  $cdo timmin -setrtomiss,0,1 -mulc,86400 ${prMerged} ${prtimmin}
  $cdo timmax -setrtomiss,0,1 -mulc,86400 ${prMerged} ${prtimmax}
fi

# --- CDO options ---
window=5
threads="32"
# nbins: window * (period_length * 2 + 2)  [fixes undefined endboot/startboot in original]
nbins=$((window*(endyear-startyear+1)*2+2))   # = 5*30*2+2 = 302

# --- percentile indices ---

# % days when tasmax > 90th percentile
if [[ $tx90p == Y ]]; then
  out=${cdoOutput}/tx90p_yr_${tag}.nc
  echo "[tx90p] tasmax above 90th percentile..."
  export CDO_PCTL_NBINS=${nbins}
  $cdo -v -P ${threads} etccdi_tx90p,${window},${startyear},${endyear},freq=year \
    ${tasmaxMerged} ${tasmaxrunmin} ${tasmaxrunmax} ${out}
fi

# % days when tasmax < 10th percentile
if [[ $tx10p == Y ]]; then
  out=${cdoOutput}/tx10p_yr_${tag}.nc
  echo "[tx10p] tasmax below 10th percentile..."
  export CDO_PCTL_NBINS=${nbins}
  $cdo -v -P ${threads} etccdi_tx10p,${window},${startyear},${endyear},freq=year \
    ${tasmaxMerged} ${tasmaxrunmin} ${tasmaxrunmax} ${out}
fi

# % days when tasmin > 90th percentile
if [[ $tn90p == Y ]]; then
  out=${cdoOutput}/tn90p_yr_${tag}.nc
  echo "[tn90p] tasmin above 90th percentile..."
  export CDO_PCTL_NBINS=${nbins}
  $cdo -v -P ${threads} etccdi_tn90p,${window},${startyear},${endyear},freq=year \
    ${tasminMerged} ${tasminrunmin} ${tasminrunmax} ${out}
fi

# % days when tasmin < 10th percentile
if [[ $tn10p == Y ]]; then
  out=${cdoOutput}/tn10p_yr_${tag}.nc
  echo "[tn10p] tasmin below 10th percentile..."
  export CDO_PCTL_NBINS=${nbins}
  $cdo -v -P ${threads} etccdi_tn10p,${window},${startyear},${endyear},freq=year \
    ${tasminMerged} ${tasminrunmin} ${tasminrunmax} ${out}
fi

# annual total precip from days > 95th percentile
if [[ $r95p == Y ]]; then
  prtemp=${mergedDir}/pr_wet_${tag}.nc
  out=${cdoOutput}/r95p_yr_${tag}.nc
  echo "[r95p] precip above 95th percentile..."
  $cdo -setrtomiss,0,1 -mulc,86400 ${prMerged} ${prtemp}
  export CDO_PCTL_NBINS=${nbins}
  $cdo -v -P ${threads} etccdi_r95p,${startyear},${endyear},freq=year \
    ${prtemp} ${prtimmin} ${prtimmax} ${out}
  rm ${prtemp}
fi

# annual total precip from days > 99th percentile
if [[ $r99p == Y ]]; then
  prtemp=${mergedDir}/pr_wet_${tag}.nc
  out=${cdoOutput}/r99p_yr_${tag}.nc
  echo "[r99p] precip above 99th percentile..."
  $cdo -setrtomiss,0,1 -mulc,86400 ${prMerged} ${prtemp}
  export CDO_PCTL_NBINS=${nbins}
  $cdo -v -P ${threads} etccdi_r99p,${startyear},${endyear},freq=year \
    ${prtemp} ${prtimmin} ${prtimmax} ${out}
  rm ${prtemp}
fi

echo "Done. Outputs in ${cdoOutput}/"