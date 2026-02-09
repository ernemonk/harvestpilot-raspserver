#Requires -Version 5.0
<#
.SYNOPSIS
    HarvestPilot Heartbeat Status - Check 30-minute sync
#>

$RemoteHost = "192.168.1.233"
$RemoteUser = "monkphx"
$RemotePassword = "149246116"
$PlinkPath = ".\plink.exe"

function Invoke-Cmd {
    param([string]$Command)
    & $PlinkPath -batch -pw $RemotePassword "${RemoteUser}@${RemoteHost}" $Command 2>&1
}

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "HarvestPilot Heartbeat & Sync Diagnostics" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

# ============================================================================
# HEARTBEAT LOGS - Last 30 minutes
# ============================================================================

Write-Host "[*] Recent Heartbeat Events (Last 30 minutes)" -ForegroundColor Yellow
Write-Host "-" * 70
$logs = Invoke-Cmd "sudo journalctl -u harvestpilot-raspserver.service --since '30 min ago' --no-pager 2>/dev/null | grep -i heartbeat"
if ($logs) {
    Write-Host $logs
} else {
    Write-Host "No heartbeat entries found in last 30 minutes" -ForegroundColor Red
}

# ============================================================================
# SYNC LOGS - Last hour
# ============================================================================

Write-Host ""
Write-Host "[*] Sync Events (Last hour)" -ForegroundColor Yellow
Write-Host "-" * 70
$syncLogs = Invoke-Cmd "sudo journalctl -u harvestpilot-raspserver.service --since '1 hour ago' --no-pager 2>/dev/null | grep -i sync"
if ($syncLogs) {
    Write-Host $syncLogs
} else {
    Write-Host "No sync entries found in last hour" -ForegroundColor Yellow
}

# ============================================================================
# FIREBASE CONNECTION STATUS
# ============================================================================

Write-Host ""
Write-Host "[*] Firebase Connection Status" -ForegroundColor Yellow
Write-Host "-" * 70
$firebaseStatus = Invoke-Cmd "sudo journalctl -u harvestpilot-raspserver.service --no-pager 2>/dev/null | grep -i 'firebase\|connected' | tail -5"
Write-Host $firebaseStatus

# ============================================================================
# CURRENT SERVICE STATUS
# ============================================================================

Write-Host ""
Write-Host "[*] Current Service Status" -ForegroundColor Yellow
Write-Host "-" * 70
$status = Invoke-Cmd "sudo systemctl status harvestpilot-raspserver.service --no-pager 2>/dev/null | head -10"
Write-Host $status

# ============================================================================
# PYTHON PROCESS - Verify it's actually running
# ============================================================================

Write-Host ""
Write-Host "[*] Process Details" -ForegroundColor Yellow
Write-Host "-" * 70
$process = Invoke-Cmd "ps aux | grep '/usr/bin/python3 main.py' | grep -v grep"
if ($process) {
    Write-Host $process -ForegroundColor Green
} else {
    Write-Host "Process not found!" -ForegroundColor Red
}

# ============================================================================
# LAST 10 LOG LINES
# ============================================================================

Write-Host ""
Write-Host "[*] Last 10 Log Lines" -ForegroundColor Yellow
Write-Host "-" * 70
$lastLogs = Invoke-Cmd "sudo journalctl -u harvestpilot-raspserver.service -n 10 --no-pager 2>/dev/null"
Write-Host $lastLogs

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Diagnostics Complete" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "INTERPRETATION:" -ForegroundColor Yellow
Write-Host "  • Heartbeat should appear every 30 seconds in logs" -ForegroundColor Gray
Write-Host "  • Sync should appear every 30 minutes in logs" -ForegroundColor Gray
Write-Host "  • Service should show 'active (running)'" -ForegroundColor Gray
Write-Host ""
