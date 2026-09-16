#!/bin/sh
# ETCCDI climate indices — CNRM-ESM2-1 historical
# All 9 indices; 1961-2000 subset for testing.
# pr has two source files and is merged before subsetting.

cdo=cdo

# --- switches ---
prepareTimeseries=Y
tnn=Y
tnx=Y
txn=Y
txx=Y
dtr=Y
rx1day=Y
rx5day=Y
sdii=Y
prcptot=Y

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
rawPr1=${base}/pr/historical/pr_day_CNRM-ESM2-1_historical_r1i1p1f2_gr_18500101-19491231.nc
rawPr2=${base}/pr/historical/pr_day_CNRM-ESM2-1_historical_r1i1p1f2_gr_19500101-20141231.nc

# --- output dirs ---
outBase=/media/wcs/Disk3/abbas/etccdi_extreme_indices/cei_absolute
mkdir -p ${outBase}
mergedDir=${outBase}/timeseries
cdoOutput=${outBase}/indices
mkdir -p ${mergedDir} ${cdoOutput}

# --- subsetted timeseries files ---
tag=${source_id}_${experiment_id}_${member_id}_${startyear}-${endyear}
tasmaxMerged=${mergedDir}/tasmax_${tag}.nc
tasminMerged=${mergedDir}/tasmin_${tag}.nc
prMerged=${mergedDir}/pr_${tag}.nc

# --- prepare timeseries ---
if [[ $prepareTimeseries == Y ]]; then
  echo "[prepare] tasmax: selyear ${startyear}/${endyear}..."
  $cdo selyear,${startyear}/${endyear} ${rawTasmax} ${tasmaxMerged}

  echo "[prepare] tasmin: selyear ${startyear}/${endyear}..."
  $cdo selyear,${startyear}/${endyear} ${rawTasmin} ${tasminMerged}

  echo "[prepare] pr: selyear ${startyear}/${endyear}..."
  $cdo selyear,${startyear}/${endyear} ${rawPr2} ${prMerged}
fi

# --- indices ---

# TNn --> minimum of daily minimum temperature each year
if [[ $tnn == Y ]]; then
  out=${cdoOutput}/tnn_yr_${tag}.nc
  echo "[tnn] annual min of tasmin..."
  $cdo subc,273.15 -yearmin ${tasminMerged} ${out}
fi

# TNx --> maximum of daily minimum temperature each year
if [[ $tnx == Y ]]; then
  out=${cdoOutput}/tnx_yr_${tag}.nc
  echo "[tnx] annual max of tasmin..."
  $cdo subc,273.15 -yearmax ${tasminMerged} ${out}
fi

# TXn --> minimum of daily maximum temperature each year
if [[ $txn == Y ]]; then
  out=${cdoOutput}/txn_yr_${tag}.nc
  echo "[txn] annual min of tasmax..."
  $cdo subc,273.15 -yearmin ${tasmaxMerged} ${out}
fi

# TXx --> maximum of daily maximum temperature each year
if [[ $txx == Y ]]; then
  out=${cdoOutput}/txx_yr_${tag}.nc
  echo "[txx] annual max of tasmax..."
  $cdo subc,273.15 -yearmax ${tasmaxMerged} ${out}
fi

# DTR --> diurnal temperature range
if [[ $dtr == Y ]]; then
  out=${cdoOutput}/dtr_yr_${tag}.nc
  echo "[dtr] annual mean of (tasmax - tasmin)..."
  $cdo yearmean -sub ${tasmaxMerged} ${tasminMerged} ${out}
fi

# RX1Day --> highest one-day precipitation
if [[ $rx1day == Y ]]; then
  out=${cdoOutput}/rx1day_yr_${tag}.nc
  echo "[rx1day] annual max 1-day precip..."
  $cdo etccdi_rx1day -mulc,86400 ${prMerged} ${out}
fi

# RX5Day --> highest five-day precipitation
if [[ $rx5day == Y ]]; then
  out=${cdoOutput}/rx5day_yr_${tag}.nc
  echo "[rx5day] annual max 5-day precip..."
  CDO_TIMESTAT_DATE="last" $cdo etccdi_rx5day -runsum,5 -mulc,86400 ${prMerged} ${out}
fi

# sdii --> simple daily intensity index
if [[ $sdii == Y ]]; then
  out=${cdoOutput}/sdii_yr_${tag}.nc
  echo "[sdii] simple daily intensity index..."
  $cdo etccdi_sdii -mulc,86400 ${prMerged} ${out}
fi

# prcptot --> total wet-day precipitation
if [[ $prcptot == Y ]]; then
  out=${cdoOutput}/prcptot_yr_${tag}.nc
  echo "[prcptot] annual total wet-day precip..."
  $cdo mulc,86400 -yearsum -mul ${prMerged} -gtc,1 -mulc,86400 ${prMerged} ${out}
fi

echo "Done. Outputs in ${cdoOutput}/"