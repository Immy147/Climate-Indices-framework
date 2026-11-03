#!/usr/bin/env bash
set -euo pipefail

# PRCPTOT (ETCCDI): annual total precipitation on wet days.
#   PRCPTOT_j = sum of RR_ij for all days i in year j with RR_ij >= 1 mm
# Usage: ./prcptot.sh INFILE OUTFILE [mm|flux]
#   INFILE : daily precipitation (mm/day, or kg m-2 s-1)
#   OUTFILE: one value per year, in mm
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

# --- 2. PRCPTOT = yearly sum of RR on days with RR >= 1 mm (dry days contribute 0) ---
echo "Computing PRCPTOT (wet days: RR >= ${WET_DAY_THRESHOLD} mm)..."
cdo -L -chname,"$VAR",prcptot -setunit,mm \
    -yearsum -mul "$SRC" -gec,"$WET_DAY_THRESHOLD" "$SRC" "$OUTFILE"

echo "Done. Saved to $OUTFILE"
