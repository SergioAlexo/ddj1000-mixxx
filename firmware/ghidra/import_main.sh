#!/bin/sh
# Import a main-CPU image (USB1 / USB2 / UPDATE) into the DDJ1000 Ghidra project.
# usage: import_main.sh <image file in $DDJ_FW_IMAGES> <flash-base-hex>   e.g. USB1_Ver.1120.bin 0x70000
. "$(dirname "$0")/env.sh"
"$HEADLESS" "$DDJ_GHIDRA_PROJECT" DDJ1000 \
  -import "$DDJ_FW_IMAGES/$1" -overwrite \
  -processor "SuperH:BE:32:SH-2A" -loader BinaryLoader -loader-baseAddr "$2" \
  -scriptPath "$SCRIPTS" -preScript SetupSH2AImage.java 4 \
  -postScript Q.java "sweep; mkio e8000000 e8100000 io_e8; callovr; sweep; callovr; constpool; stats" 2>&1 \
  | awk '/(Q|SetupSH2AImage)\.java> /{sub(/^.*java> /,"");sub(/ \(GhidraScript\)  $/,"");print} /ERROR|Exception/'
