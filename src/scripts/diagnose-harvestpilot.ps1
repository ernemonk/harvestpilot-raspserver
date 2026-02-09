#Requires -Version 5.0
<#
.SYNOPSIS
    HarvestPilot Diagnostics - Complete SSH-based Pi Health Monitor
    
.DESCRIPTION
    Comprehensive diagnostics for HarvestPilot Raspberry Pi deployment
    
.EXAMPLE
    .\diagnose-harvestpilot.ps1
#>

# Configuration
$RemoteHost = "192.168.1.233"
$RemoteUser = "monkphx"
$RemotePassword = "149246116"
$PlinkPath = ".\plink.exe"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

function Write-Header {
    param([string]$Title)
    Write-Host ""
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host $Title -ForegroundColor Cyan
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host ""
}

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "[*] $Title" -ForegroundColor Yellow
    Write-Host "-" * 70 -ForegroundColor Gray
}

function Write-Success {
    param([string]$Message)
    Write-Host "[+] $Message" -ForegroundColor Green
}

function Write-ErrorMsg {
    param([string]$Message)
    Write-Host "[-] $Message" -ForegroundColor Red
}

function Write-InfoMsg {
    param([string]$Message)
    Write-Host "[i] $Message" -ForegroundColor Blue
}

function Invoke-RemoteCommand {
    param([string]$Command)
    
    try {
        $result = & $PlinkPath -batch -pw $RemotePassword "${RemoteUser}@${RemoteHost}" $Command 2>&1
        return $result
    }
    catch {
        return "ERROR: $_"
    }
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

Write-Header "HarvestPilot Raspberry Pi Diagnostics"
Write-InfoMsg "Target: ${RemoteUser}@${RemoteHost}"
Write-InfoMsg "Method: SSH with plink.exe"
Write-InfoMsg "Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

# Check plink exists
if (-not (Test-Path $PlinkPath)) {
    Write-ErrorMsg "plink.exe not found at: $PlinkPath"
    Write-InfoMsg "Download from: https://the.earth.li/~sgtatham/putty/latest/w64/plink.exe"
    exit 1
}
Write-Success "plink.exe found"

# Test connectivity
Write-Section "Testing SSH Connectivity"
$testResult = Invoke-RemoteCommand "echo OK"
if ($testResult -match "OK") {
    Write-Success "SSH Connection Successful"
} else {
    Write-ErrorMsg "SSH Connection Failed"
    Write-InfoMsg "Result: $testResult"
    exit 1
}

# ============================================================================
# SYSTEM DIAGNOSTICS
# ============================================================================

Write-Header "System Information"

Write-Section "OS and Hardware"
$output = Invoke-RemoteCommand "uname -a"
Write-Host $output

Write-Section "Disk Usage"
$output = Invoke-RemoteCommand "df -h /"
Write-Host $output

Write-Section "Memory Usage"
$output = Invoke-RemoteCommand "free -h"
Write-Host $output

Write-Section "CPU Temperature"
$output = Invoke-RemoteCommand "vcgencmd measure_temp 2>/dev/null || echo 'N/A'"
Write-Host $output

Write-Section "System Uptime"
$output = Invoke-RemoteCommand "uptime"
Write-Host $output

# ============================================================================
# HARVESTPILOT SERVICE STATUS
# ============================================================================

Write-Header "HarvestPilot Service Status"

Write-Section "Main Service (harvestpilot-raspserver)"
$output = Invoke-RemoteCommand "sudo systemctl status harvestpilot-raspserver.service --no-pager 2>/dev/null | head -15"
Write-Host $output

$activeStatus = Invoke-RemoteCommand "sudo systemctl is-active harvestpilot-raspserver.service 2>/dev/null || echo 'unknown'"
if ($activeStatus -match "active") {
    Write-Success "Service is RUNNING"
} else {
    Write-ErrorMsg "Service is NOT RUNNING or inactive"
}

Write-Section "Auto-Deploy Service (harvestpilot-autodeploy)"
$output = Invoke-RemoteCommand "sudo systemctl status harvestpilot-autodeploy.service --no-pager 2>/dev/null | head -15"
Write-Host $output

# ============================================================================
# HARVESTPILOT PROCESSES
# ============================================================================

Write-Section "Running HarvestPilot Processes"
$output = Invoke-RemoteCommand "ps aux | grep -E 'python.*main|harvestpilot' | grep -v grep"
if ($output) {
    Write-Host $output
} else {
    Write-ErrorMsg "No HarvestPilot processes found"
}

# ============================================================================
# HARVESTPILOT LOGS
# ============================================================================

Write-Header "HarvestPilot Logs & Diagnostics"

Write-Section "Recent Service Logs (Last 50 lines)"
$output = Invoke-RemoteCommand "sudo journalctl -u harvestpilot-raspserver.service -n 50 --no-pager 2>/dev/null || echo 'No logs'"
Write-Host $output

Write-Section "Recent Errors & Warnings"
$output = Invoke-RemoteCommand "sudo journalctl -u harvestpilot-raspserver.service --no-pager 2>/dev/null | grep -iE 'error|failed|exception|critical' | tail -15"
if ($output) {
    Write-ErrorMsg "Found errors:"
    Write-Host $output
} else {
    Write-Success "No critical errors in recent logs"
}

Write-Section "Heartbeat & Sync Activity"
$output = Invoke-RemoteCommand "sudo journalctl -u harvestpilot-raspserver.service --no-pager 2>/dev/null | grep -iE 'heartbeat|sync|firebase' | tail -15"
if ($output) {
    Write-Host $output
} else {
    Write-InfoMsg "No heartbeat/sync entries - service may not be running"
}

# ============================================================================
# FIREBASE DIAGNOSTICS
# ============================================================================

Write-Section "Firebase Configuration"
$output = Invoke-RemoteCommand "ls -la /home/${RemoteUser}/harvestpilot-raspserver/config/"
Write-Host $output

Write-Section "Firebase SDK Check"
$output = Invoke-RemoteCommand "python3 -c 'import firebase_admin; print(\"Firebase SDK: OK\")' 2>&1"
Write-Host $output

# ============================================================================
# NETWORK DIAGNOSTICS
# ============================================================================

Write-Header "Network Status"

Write-Section "Network Interfaces"
$output = Invoke-RemoteCommand "ip -4 addr show | grep -E 'inet|eth|wlan'"
Write-Host $output

Write-Section "Internet Connectivity"
$output = Invoke-RemoteCommand "ping -c 1 8.8.8.8 2>&1 | grep -E 'time=|unreachable|timeout' | head -3"
Write-Host $output

# ============================================================================
# DEPLOYMENT STATUS
# ============================================================================

Write-Header "Deployment Status"

Write-Section "Repository Status"
$output = Invoke-RemoteCommand "cd /home/${RemoteUser}/harvestpilot-raspserver && git status --short 2>/dev/null || echo 'No git repo'"
if ($output -match "^M|^A|^\?\?") {
    Write-ErrorMsg "Modified files detected:"
    Write-Host $output
} else {
    Write-Success "Repository is clean"
}

Write-Section "Recent Deployments"
$output = Invoke-RemoteCommand "cd /home/${RemoteUser}/harvestpilot-raspserver && git log --oneline -5 2>/dev/null || echo 'No git repo'"
Write-Host $output

# ============================================================================
# SUMMARY & RECOMMENDATIONS
# ============================================================================

Write-Header "Diagnostics Summary"

Write-Section "System Health Check"

# Get service status for summary
$mainServiceStatus = Invoke-RemoteCommand "sudo systemctl is-active harvestpilot-raspserver.service 2>/dev/null || echo 'unknown'"
$autoDeployStatus = Invoke-RemoteCommand "sudo systemctl is-active harvestpilot-autodeploy.service 2>/dev/null || echo 'unknown'"

if ($mainServiceStatus -match "active") {
    Write-Success "[OK] Main service is running"
} else {
    Write-ErrorMsg "[FAIL] Main service is NOT running"
}

if ($autoDeployStatus -match "active") {
    Write-Success "[OK] Auto-deploy service is active"
}

# Get disk usage
$diskOutput = Invoke-RemoteCommand "df / | tail -1 | awk '{print $5}' | sed 's/%//'"
try {
    $diskPercent = [int]($diskOutput.Trim())
    if ($diskPercent -gt 85) {
        Write-ErrorMsg "Disk usage is ${diskPercent}% - CRITICAL"
    } elseif ($diskPercent -gt 70) {
        Write-InfoMsg "Disk usage is ${diskPercent}% - Monitor"
    } else {
        Write-Success "Disk usage is ${diskPercent}% - OK"
    }
}
catch { }

Write-Section "Recommended Actions"

if ($mainServiceStatus -notmatch "active") {
    Write-InfoMsg "To restart main service, run:"
    Write-Host "  sudo systemctl restart harvestpilot-raspserver.service" -ForegroundColor Magenta
}

Write-InfoMsg "To view live logs, run:"
Write-Host "  sudo journalctl -u harvestpilot-raspserver.service -f" -ForegroundColor Magenta

Write-InfoMsg "To check heartbeat timestamp, visit Firebase Console"

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Diagnostics Complete - $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
