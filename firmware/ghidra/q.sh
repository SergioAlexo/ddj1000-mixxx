#!/bin/sh
# usage: q.sh <program> "<cmd; cmd; ...>"   (runs Q.java headless against the DDJ1000 Ghidra project)
. "$(dirname "$0")/env.sh"
prog=$1; shift
"$HEADLESS" "$DDJ_GHIDRA_PROJECT" DDJ1000 -process "$prog" -noanalysis \
  -scriptPath "$SCRIPTS" -postScript Q.java "$@" 2>&1 \
  | awk '/Q\.java> /{sub(/^.*Q\.java> /,""); sub(/ \(GhidraScript\)  $/,""); print; inq=1; next}
         /^(INFO|WARN|WARNING|DEBUG|openjdk)/{inq=0; next}
         /ERROR|Exception/{print; next}
         inq{sub(/ \(GhidraScript\)  $/,""); print}'
