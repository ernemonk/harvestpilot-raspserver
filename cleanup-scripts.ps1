#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Cleanup obsolete diagnostic scripts from src/scripts folder
    These have been consolidated into the root check-gpio-status.ps1
#>

$ScriptsDir = ".\src\scripts"

# List of files to remove (now consolidated into root check-gpio-status.ps1)
$ToRemove = @(
    # Check/Diagnose scripts - REPLACED by root check-gpio-status.ps1
    "check-pi-status.ps1",
    "check-pi-status.py",
    "check-pi-status.sh",
    "check-heartbeat.ps1",
    "diagnose-harvestpilot.ps1",
    "diagnose-ssh.py",
    "pi-diagnostics.ps1",
    "get-pi-status.bat",
    
    # SSH/plink related - no longer needed
    "install-plink.ps1",
    "test-plink.ps1",
    "test-ssh-password.py",
    "ssh-brute-force.py",
    
    # Heartbeat monitoring - replaced by schedule listener
    "heartbeat_monitor.py",
    "HEARTBEAT_ROOT_CAUSE_ANALYSIS.md",
    "HEARTBEAT_TEST_DIAGNOSTIC.sh"
)

Write-Host ""
Write-Host "Cleanup: Removing obsolete scripts from src/scripts/" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$removed = 0
$notfound = 0

foreach ($file in $ToRemove) {
    $path = Join-Path $ScriptsDir $file
    
    if (Test-Path $path) {
        Remove-Item $path -Force -ErrorAction SilentlyContinue
        Write-Host "[✓] Removed: $file" -ForegroundColor Green
        $removed++
    } else {
        $notfound++
    }
}

Write-Host ""
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "  Removed: $removed files"
Write-Host "  Not found: $notfound files"
Write-Host ""
Write-Host "Remaining scripts in src/scripts/:" -ForegroundColor Yellow
Get-ChildItem $ScriptsDir -Name | Sort-Object
Write-Host ""
