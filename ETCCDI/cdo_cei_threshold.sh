#!/bin/sh
# ETCCDI threshold-based indices — CNRM-ESM2-1 ssp585
# Indices: fd, su, id, tr, r1mm, r10mm, r20mm
# Period : 2071-2100 (30-year subset)
# All three variables are single files (2015-2100); selyear + mergetime
# used to match reference script pattern exactly.

cdo=cdo

# --- switches ---
prepareTimeseries=Y
fd=Y
su=Y
id=Y
tr=Y
r1=Y
r10=Y
r20=Y

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
outBase=/media/wcs/Disk3/abbas/etccdi_extreme_indices/cei_threshold
mkdir -p ${outBase}

timeSeriesDir=/media/wcs/Disk3/abbas/etccdi_extreme_indices/cei_percentiles
mergedDir=${timeSeriesDir}/timeseries

cdoOutput=${outBase}/indices
mkdir -p ${mergedDir} ${cdoOutput}

# --- timeseries file paths ---
tag=${source_id}_${experiment_id}_${member_id}_${startyear}-${endyear}
tasmaxMerged=${mergedDir}/tasmax_${tag}.nc
tasminMerged=${mergedDir}/tasmin_${tag}.nc
prMerged=${mergedDir}/pr_${tag}.nc

# --- prepare timeseries (skip if already exists) ---
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
    echo "[prepare] pr: selyear ${startyear}/${endyear}..."
    $cdo selyear,${startyear}/${endyear} ${rawPr} ${prMerged}
  else
    echo "[prepare] pr: already exists, skipping."
  fi
fi

# --- indices ---

# frost days: annual count of days when tasmin < 0°C
if [[ $fd == Y ]]; then
  out=${cdoOutput}/fd_yr_${tag}.nc
  echo "[fd] Frost days..."
  $cdo etccdi_fd ${tasminMerged} ${out}
fi

# summer days: annual count of days when tasmax > 25°C
if [[ $su == Y ]]; then
  out=${cdoOutput}/su_yr_${tag}.nc
  echo "[su] Summer days..."
  $cdo etccdi_su ${tasmaxMerged} ${out}
fi

# ice days: annual count of days when tasmax < 0°C
if [[ $id == Y ]]; then
  out=${cdoOutput}/id_yr_${tag}.nc
  echo "[id] Ice days..."
  $cdo etccdi_id ${tasmaxMerged} ${out}
fi

# tropical nights: annual count of days when tasmin > 20°C
if [[ $tr == Y ]]; then
  out=${cdoOutput}/tr_yr_${tag}.nc
  echo "[tr] Tropical nights..."
  $cdo etccdi_tr ${tasminMerged} ${out}
fi

# r1mm: annual count of days when pr >= 1 mm
if [[ $r1 == Y ]]; then
  out=${cdoOutput}/r1mm_yr_${tag}.nc
  echo "[r1mm] Days with precip >= 1mm..."
  $cdo etccdi_r1mm -mulc,86400 ${prMerged} ${out}
fi

# r10mm: annual count of days when pr >= 10 mm
if [[ $r10 == Y ]]; then
  out=${cdoOutput}/r10mm_yr_${tag}.nc
  echo "[r10mm] Days with precip >= 10mm..."
  $cdo etccdi_r10mm -mulc,86400 ${prMerged} ${out}
fi

# r20mm: annual count of days when pr >= 20 mm
if [[ $r20 == Y ]]; then
  out=${cdoOutput}/r20mm_yr_${tag}.nc
  echo "[r20mm] Days with precip >= 20mm..."
  $cdo etccdi_r20mm -mulc,86400 ${prMerged} ${out}
fi

echo "Done. Outputs in ${cdoOutput}/"