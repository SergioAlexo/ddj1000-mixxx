#!/bin/sh
# Re-create the LCD_M Ghidra program from scratch (overwrites it in the DDJ1000 project) and apply
# the base names. Use apply_annotations.sh afterwards to restore every saved name and comment.
. "$(dirname "$0")/env.sh"
"$HEADLESS" "$DDJ_GHIDRA_PROJECT" DDJ1000 \
  -import "$DDJ_FW_IMAGES/LCD_M_Ver.1060.bin" -overwrite \
  -processor "SuperH:BE:32:SH-2A" -loader BinaryLoader -loader-baseAddr 0x18040000 \
  -scriptPath "$SCRIPTS" -preScript SetupSH2AImage.java \
  -postScript Q.java "sweep; mkio e8000000 e8100000 io_e8; callovr; sweep; callovr; constpool"
"$SCRIPTS/q.sh" LCD_M_Ver.1060.bin "ren 1c20b280 task_gui; ren 1c20e230 task_hid; ren 1c20ecba task_lcd; ren 1c20f064 task_led; ren 1c20f6a8 task_root; ren 1c20f7d8 task_midi; ren 1c211dfc task_serial_flash; ren 1c212d02 task_sh; ren 1c213580 task_system; ren 1c213a54 task_cpu; ren 1c212fd2 sh_link_init; ren 1c20eec4 lcd_scif4_init; ren 1c212888 spibsc_init; ren fff84bdc acre_tsk; ren 1c212fa6 sh_set_rx_handler; ren 1c2001b2 crc16; ren 1c2138fc sh_rx_dispatch; ren 1c20eb3a route_hid; ren 1c20fa5c route_midi; ren 1c2000de mask_shift; ren 1c2107b8 blobA_finish; ren 1c211084 blobB_status; ren 1c210ac2 wave_render; ren 1c2107ec wave_init; ren 1c2108c4 wave_store; ren 1c200e20 gui_draw_deck; ren 1c23e15e img_detect_format; ren 1c200b9a gui_draw_image; ren 1c2105c4 art_init; ren 1c210610 art_store; ren 1c20da74 wave_publish; ren 1c20d9c2 art_publish; ren 1c20db76 beatgrid_publish"
