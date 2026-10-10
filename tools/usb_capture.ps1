# Captures USB traffic of the DDJ-1000 (VID 2B73 / PID 0020) with USBPcap.
# Self-elevates. Start it BEFORE opening rekordbox, press Enter to stop.
# Output: ddj1000-mixxx\captures\<name>-<timestamp>.pcap  (open in Wireshark)
# Only one process can hold a USBPcap hub, so leftover USBPcapCMD processes are stopped first.
param([string]$Name = 'ddj1000', [int]$Hub = 0)   # Hub 0 = auto-detect

$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Name $Name -Hub $Hub"
    exit
}

$cmd = 'C:\Program Files\USBPcap\USBPcapCMD.exe'
$dir = Join-Path (Split-Path $PSScriptRoot -Parent) 'captures'
New-Item -ItemType Directory -Force $dir | Out-Null
Get-Process USBPcapCMD -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 1

function Test-Ddj($file) {
    # DDJ-1000 device descriptor: idVendor 73 2B, idProduct 20 00
    $fs = [IO.File]::Open($file, 'Open', 'Read', 'ReadWrite'); $b = New-Object byte[] $fs.Length; [void]$fs.Read($b, 0, $b.Length); $fs.Close()
    for ($k = 0; $k -le $b.Length - 4; $k++) { if ($b[$k] -eq 0x73 -and $b[$k+1] -eq 0x2B -and $b[$k+2] -eq 0x20 -and $b[$k+3] -eq 0) { return $true } }
    return $false
}
if ($Hub -eq 0) {
    foreach ($i in 1..6) {
        $probe = Join-Path $dir "probe$i.pcap"
        $q = Start-Process $cmd -ArgumentList "-d \\.\USBPcap$i -o `"$probe`" -A --inject-descriptors" -PassThru -WindowStyle Hidden
        Start-Sleep 2
        if (-not $q.HasExited) { $q.Kill(); $q.WaitForExit() }
        Start-Sleep 1
        if ((Test-Path $probe) -and (Test-Ddj $probe)) { $Hub = $i }
        Remove-Item $probe -ErrorAction SilentlyContinue
        if ($Hub) { break }
    }
    if (-not $Hub) { Write-Host 'DDJ-1000 not found on any USBPcap hub.'; Read-Host 'Enter to close'; exit 1 }
}

$out = Join-Path $dir ("{0}-{1}.pcap" -f $Name, (Get-Date -Format 'yyyyMMdd-HHmmss'))
Write-Host "Capturing USBPcap$Hub to $out"
$p = Start-Process $cmd -ArgumentList "-d \\.\USBPcap$Hub -o `"$out`" -A --inject-descriptors -s 65535" -PassThru -WindowStyle Hidden
Start-Sleep 2
if ($p.HasExited) { Write-Host 'USBPcapCMD exited immediately - hub not available.'; Read-Host 'Enter to close'; exit 1 }
Write-Host 'NOW open rekordbox and use the controller. Press Enter here to stop.'
Read-Host | Out-Null
$p.Kill(); $p.WaitForExit()
Start-Sleep 1

# Sanity check: device descriptor of the DDJ-1000 (idVendor 73 2B, idProduct 20 00) should be in the file
$fs = [IO.File]::Open($out, 'Open', 'Read', 'ReadWrite'); $b = New-Object byte[] $fs.Length; [void]$fs.Read($b, 0, $b.Length); $fs.Close()
$found = $false
for ($k = 0; $k -le $b.Length - 4; $k++) {
    if ($b[$k] -eq 0x73 -and $b[$k+1] -eq 0x2B -and $b[$k+2] -eq 0x20 -and $b[$k+3] -eq 0) { $found = $true; break }
}
Write-Host ("Saved {0} ({1:N0} bytes). DDJ-1000 descriptor present: {2}" -f $out, $b.Length, $found)
Read-Host 'Enter to close'
