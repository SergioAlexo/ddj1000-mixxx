#!/bin/sh
# Export names and comments of every program in the DDJ1000 Ghidra project to ../annotations/<program>.tsv.
# usage: export_annotations.sh [program]     (default: all programs)
. "$(dirname "$0")/env.sh"
"$HEADLESS" "$DDJ_GHIDRA_PROJECT" DDJ1000 -process ${1:+"$1"} -noanalysis -readOnly \
  -scriptPath "$SCRIPTS" -postScript ExportAnnotations.java "$FW/annotations" 2>&1 \
  | awk '/ExportAnnotations\.java> /{sub(/^.*java> /,"");sub(/ \(GhidraScript\)  $/,"");print} /ERROR|Exception/'
