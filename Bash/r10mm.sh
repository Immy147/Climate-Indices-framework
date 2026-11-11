#!/usr/bin/env bash
set -euo pipefail

# R10mm (ETCCDI): annual count of heavy precipitation days.
#   R10mm_j = number of days in year j with RR >= 10 mm
# Usage: ./r10mm.sh INFILE OUTFILE [mm|flux]
#   INFILE : daily precipitation (mm/day, or kg m-2 s-1)
#   OUTFILE: one value per year, in days
#   3rd arg (optional): force the input units. Default is to auto-detect from the file.

INFILE=$1
OUTFILE=$2
UNITS_OVERRIDE=${3:-auto}
THRESHOLD=10             # mm/day, ETCCDI definition of a heavy precipitation day

# --- 1. Make sure the input is in mm/day (the 10 mm threshold only makes sense in mm/day) ---
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

# --- 2. R10mm = yearly count of days with RR >= 10 mm ---
echo "Computing R10mm (days with RR >= ${THRESHOLD} mm)..."
cdo -L -chname,"$VAR",r10mm -setunit,days -yearsum -gec,"$THRESHOLD" "$SRC" "$OUTFILE"

echo "Done. Saved to $OUTFILE"
