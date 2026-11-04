#!/usr/bin/env bash
# calm_days  : annual count of days with sfcWind <  2    m/s
# windy_days : annual count of days with sfcWind >= 10.8 m/s

IN_DIR="/mnt/wcs-s1-d1/BOLT_ISIMIP_BCSD/SAMOA/data/final/rcp26/sfcWind"   # <- set to your input folder
OUT_DIR="/mnt/wcs-s3-d1/BOLT_ISIMIP_BCSD/VANUATU/data/interim/Indicators/sfcWind"
# PATTERN='3km_BC_(.+)_(r[0-9]+i[0-9]+p[0-9]+)_(.+)_v[0-9]+_day'

for f in "$IN_DIR"/*.nc; do
  fname=$(basename "$f")
  [[ "$fname" == *rcp26* ]] && scen=rcp26 || { [[ "$fname" == *rcp85* ]] && scen=rcp85 || continue; }
  [[ "$fname" =~ $PATTERN ]] || continue
  model="${BASH_REMATCH[1]}__${BASH_REMATCH[3]}"

  for ind in calm_days windy_days; do
    out="$OUT_DIR/$ind/${ind}_${scen}_${model}.nc"
    mkdir -p "$OUT_DIR/$ind"
    [[ -s "$out" ]] && continue

    [[ $ind == calm_days ]] && op="ltc,2" || op="gec,10.8"

    cdo -s -yearsum -"$op" -setrtomiss,-1e30,-1e-9 -selname,sfcWind "$f" "$out.tmp" \
      && mv "$out.tmp" "$out" || rm -f "$out.tmp"
  done
done