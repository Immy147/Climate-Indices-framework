#!/bin/sh
# ETCCDI percentile-based indices — CNRM-ESM2-1 historical
# Indices: csdi, wsdi  (cdd, cwd, gsl disabled — mirrors original switches)
# Reference period: 1961-2000
# Timeseries files reused from the absolute indices script run.
# pr is not merged — 1961-2000 falls entirely within the second source file.

cdo=cdo

# --- switches ---
prepareTimeseries=Y   # set to N if timeseries files already exist from absolute indices run
percentiles=Y         # must be Y; thresholds are required by csdi and wsdi
csdi=Y
wsdi=Y
cdd=Y
cwd=Y
gsl=Y

# --- metadata ---
source_id=CNRM-ESM2-1
experiment_id=historical
member_id=r1i1p1f2
startyear=1961
endyear=2000

# --- raw input paths ---
base=/media/wcs/Disk3/abbas/geomip_models/CNRM-ESM2-1

rawTasmax=${base}/tasmax/historical/tasmax_day_CNRM-ESM2-1_historical_r1i1p1f2_gr_18500101-20141231.nc
rawTasmin=${base}/tasmin/historical/tasmin_day_CNRM-ESM2-1_historical_r1i1p1f2_gr_18500101-20141231.nc
# 1961-2000 lies entirely within the second pr file; no mergetime needed
rawPr=${base}/pr/historical/pr_day_CNRM-ESM2-1_historical_r1i1p1f2_gr_19500101-20141231.nc

# --- output dirs ---
outBase=/media/wcs/Disk3/abbas/etccdi_extreme_indices/cei_duration
mkdir -p ${outBase}

timeSeriesDir=/media/wcs/Disk3/abbas/etccdi_extreme_indices/cei_absolute
mergedDir=${timeSeriesDir}/timeseries

cdoOutput=${outBase}/indices
mkdir -p ${mergedDir} ${cdoOutput}

# --- timeseries file paths (shared with absolute indices script) ---
tag=${source_id}_${experiment_id}_${member_id}_${startyear}-${endyear}
tasmaxMerged=${mergedDir}/tasmax_${tag}.nc
tasminMerged=${mergedDir}/tasmin_${tag}.nc
prMerged=${mergedDir}/pr_${tag}.nc

# --- prepare timeseries (skip if already created by absolute indices run) ---
if [[ $prepareTimeseries == Y ]]; then
  if [[ ! -f ${tasmaxMerged} ]]; then
    echo "[prepare] tasmax: selyear ${startyear}/${endyear}..."
    $cdo selyear,${startyear}/${endyear} ${rawTasmax} ${tasmaxMerged}
  else
    echo "[prepare] tasmax: already exists, skipping."
  fi

  if [[ ! -f ${tasminMerged} ]]; then
    echo "[prepare] tasmin: selyear ${startyear}/${endyear}..."
    $cdo selyear,${startyear}/${endyear} ${rawTasmin} ${tasminMerged}
  else
    echo "[prepare] tasmin: already exists, skipping."
  fi

  if [[ ! -f ${prMerged} ]]; then
    echo "[prepare] pr: selyear ${startyear}/${endyear} (single source file)..."
    $cdo selyear,${startyear}/${endyear} ${rawPr} ${prMerged}
  else
    echo "[prepare] pr: already exists, skipping."
  fi
fi

# --- percentile threshold files ---
tasminrunmin=${cdoOutput}/tasmin_runmin_${tag}.nc
tasminrunmax=${cdoOutput}/tasmin_runmax_${tag}.nc
tasmaxrunmin=${cdoOutput}/tasmax_runmin_${tag}.nc
tasmaxrunmax=${cdoOutput}/tasmax_runmax_${tag}.nc
tn10thresh=${cdoOutput}/tn10thresh_${tag}.nc
tn90thresh=${cdoOutput}/tn90thresh_${tag}.nc
tx10thresh=${cdoOutput}/tx10thresh_${tag}.nc
tx90thresh=${cdoOutput}/tx90thresh_${tag}.nc

export CDO_PCTL_NBINS=$((5*(endyear-startyear+1)*2+2))

if [[ $percentiles == Y ]]; then
  echo "[percentiles] Computing running min/max and thresholds..."

  $cdo ydrunmin,5,rm=c ${tasminMerged} ${tasminrunmin}
  $cdo ydrunmax,5,rm=c ${tasminMerged} ${tasminrunmax}
  $cdo ydrunmin,5,rm=c ${tasmaxMerged} ${tasmaxrunmin}
  $cdo ydrunmax,5,rm=c ${tasmaxMerged} ${tasmaxrunmax}

  $cdo subc,273.15 -ydrunpctl,10,5,pm=r8,rm=c ${tasminMerged} ${tasminrunmin} ${tasminrunmax} ${tn10thresh}
  $cdo subc,273.15 -ydrunpctl,90,5,pm=r8,rm=c ${tasminMerged} ${tasminrunmin} ${tasminrunmax} ${tn90thresh}
  $cdo subc,273.15 -ydrunpctl,10,5,pm=r8,rm=c ${tasmaxMerged} ${tasmaxrunmin} ${tasmaxrunmax} ${tx10thresh}
  $cdo subc,273.15 -ydrunpctl,90,5,pm=r8,rm=c ${tasmaxMerged} ${tasmaxrunmin} ${tasmaxrunmax} ${tx90thresh}
fi

# --- indices ---

# cold spell duration index
if [[ $csdi == Y ]]; then
  out=${cdoOutput}/csdi_yr_${tag}.nc
  echo "[csdi] Cold spell duration index..."
  $cdo etccdi_cwfi -subc,273.15 ${tasminMerged} ${tn10thresh} ${out}
fi

# warm spell duration index
if [[ $wsdi == Y ]]; then
  out=${cdoOutput}/wsdi_yr_${tag}.nc
  echo "[wsdi] Warm spell duration index..."
  $cdo etccdi_hwfi -subc,273.15 ${tasmaxMerged} ${tx90thresh} ${out}
fi

# consecutive dry days (disabled)
if [[ $cdd == Y ]]; then
  out=${cdoOutput}/cdd_yr_${tag}.nc
  echo "[cdd] Consecutive dry days..."
  $cdo etccdi_cdd -mulc,86400 ${prMerged} ${out}
fi

# consecutive wet days (disabled)
if [[ $cwd == Y ]]; then
  out=${cdoOutput}/cwd_yr_${tag}.nc
  echo "[cwd] Consecutive wet days..."
  $cdo etccdi_cwd -mulc,86400 ${prMerged} ${out}
fi

# growing season length (disabled)
if [[ $gsl == Y ]]; then
  out=${cdoOutput}/gsl_yr_${tag}.nc
  echo "[gsl] Growing season length..."
  $cdo etccdi_gsl -divc,2 -add ${tasminMerged} ${tasmaxMerged} -gtc,1 ${tasmaxMerged} ${out}
fi

echo "Done. Outputs in ${cdoOutput}/"