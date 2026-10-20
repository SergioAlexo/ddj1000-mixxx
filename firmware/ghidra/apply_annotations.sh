#!/bin/sh
# Re-apply ../annotations/<program>.tsv to a freshly imported program.
# usage: apply_annotations.sh <program>      e.g. USB1_Ver.1120.bin
. "$(dirname "$0")/env.sh"
"$HEADLESS" "$DDJ_GHIDRA_PROJECT" DDJ1000 -process "$1" -noanalysis \
  -scriptPath "$SCRIPTS" -postScript ApplyAnnotations.java "$FW/annotations/${1%.bin}.tsv" 2>&1 \
  | awk '/ApplyAnnotations\.java> /{sub(/^.*java> /,"");sub(/ \(GhidraScript\)  $/,"");print} /ERROR|Exception/'
