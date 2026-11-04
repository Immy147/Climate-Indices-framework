#!/usr/bin/env bash
set -euo pipefail

# SDII (ETCCDI): Simple Daily Intensity Index.
#   SDII_j = sum(RR_wj) / W
#   RR_wj = daily precipitation on wet days (RR >= 1 mm) in year j,  W = number of wet days in year j
#   i.e. the mean precipitation on wet days, in mm/day.
# Usage: ./sdii.sh INFILE OUTFILE [mm|flux]
#   INFILE : daily precipitation (mm/day, or kg m-2 s-1)
#   OUTFILE: one value per year, in mm/day (missing in years with no wet days, as in ETCCDI/climdex)
#   3rd arg (optional): force the input units. Default is to auto-detect from the file.

INFILE=$1
OUTFILE=$2
UNITS_OVERRIDE=${3:-auto}
WET_DAY_THRESHOLD=1      # mm/day, ETCCDI definition of a wet day

# --- 1. Make sure the input is in mm/day (the 1 mm threshold only makes sense in mm/day) ---
VAR=$(cdo -s showname "$INFILE" | awk '{print $1}')
UNITS=$(cdo -s showunit "$INFILE" | tr -d '[:space:]')

if [[ "$UNITS_OVERRIDE" == "auto" ]]; then
    case "$UNITS" in
        kgm-2s-1|kg/m2/s|kgm^-2s^-1) UNITS_OVERRIDE=flux ;;
        mm|mm/day|mmd-1|mmday-1|mm/d) UNITS_OVERRIDE=mm ;;
        *) echo "ERROR: cannot tell the units of '$VAR' (found: '${UNITS:-none}')." >&2
           echo "       Re-run with a third argument: mm  or  flux" >&2
           exit 1 ;;
    esac
fi

SRC="$INFILE"
if [[ "$UNITS_OVERRIDE" == "flux" ]]; then
    TMP=$(mktemp --suffix=.nc)
    trap 'rm -f "$TMP"' EXIT
    echo "Converting $VAR from kg m-2 s-1 to mm/day..."
    cdo -s -L mulc,86400 "$INFILE" "$TMP"
    SRC="$TMP"
fi

# --- 2. SDII = (yearly sum of RR on wet days) / (yearly number of wet days) ---
echo "Computing SDII (wet days: RR >= ${WET_DAY_THRESHOLD} mm)..."
cdo -L -chname,"$VAR",sdii -setunit,"mm/day" \
    -div -yearsum -mul "$SRC" -gec,"$WET_DAY_THRESHOLD" "$SRC" \
         -yearsum -gec,"$WET_DAY_THRESHOLD" "$SRC" \
    "$OUTFILE"

echo "Done. Saved to $OUTFILE"
