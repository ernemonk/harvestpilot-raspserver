#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Universal HarvestPilot Pi Log Retrieval Script
    
.DESCRIPTION
    Easily retrieve logs from Raspberry Pi with various filters and options
    
.PARAMETER LogType
    Type of logs to retrieve: 'recent', 'errors', 'gpio', 'heartbeat', 'firebase', 'all'
    Default: 'recent'
    
.PARAMETER Lines
    Number of log lines to retrieve. Default: 50
    
.PARAMETER Service
    Service to query: 'harvestpilot-raspserver', 'harvestpilot-autodeploy', 'both'
    Default: 'harvestpilot-raspserver'
    
.PARAMETER Pattern
    Custom grep pattern to filter logs
    
.PARAMETER Follow
    Follow live logs (like 'tail -f')
    
.EXAMPLE
    .\get-pi-logs.ps1                                  # Last 50 recent logs from main service
    .\get-pi-logs.ps1 -LogType errors -Lines 100      # Last 100 error lines
    .\get-pi-logs.ps1 -LogType gpio                   # GPIO state changes
    .\get-pi-logs.ps1 -LogType heartbeat              # Heartbeat activity
    .\get-pi-logs.ps1 -Service both -Lines 30         # Last 30 lines from both services
    .\get-pi-logs.ps1 -LogType recent -Follow         # Live log stream
    .\get-pi-logs.ps1 -Pattern "firebase|sync"        # Custom filter
#>

param(
    [ValidateSet('recent', 'errors', 'gpio', 'heartbeat', 'firebase', 'all')]
    [string]$LogType = 'recent',
    
    [int]$Lines = 50,
    
    [ValidateSet('harvestpilot-raspserver', 'harvestpilot-autodeploy', 'both')]
    [string]$Service = 'harvestpilot-raspserver',
    
    [string]$Pattern = '',
    
    [switch]$Follow
)

$RemoteHost = $env:PI_HOST ?? "192.168.1.233"
$RemoteUser = $env:PI_USER ?? "monkphx"
$RemotePassword = $env:PI_PASSWORD  # Set PI_PASSWORD env var before running
$PlinkPath = $env:PLINK_PATH ?? "C:\Users\User\plink.exe"

if (-not $RemotePassword) {
    Write-Host "ERROR: Set the PI_PASSWORD environment variable first." -ForegroundColor Red
    exit 1
}

function Test-PlinkExists {
    if (-not (Test-Path $PlinkPath)) {
        Write-Host "[!] ERROR: plink.exe not found at: $PlinkPath" -ForegroundColor Red
        Write-Host "Download from: https://the.earth.li/~sgtatham/putty/latest/w64/plink.exe" -ForegroundColor Yellow
        exit 1
    }
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

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "HarvestPilot Pi Log Retrieval" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

Test-PlinkExists
Write-Host "[*] Connecting to $RemoteUser@$RemoteHost..." -ForegroundColor Blue

$testResult = Invoke-RemoteCommand "echo OK"
if ($testResult -notmatch "OK") {
    Write-Host "[!] Connection failed!" -ForegroundColor Red
    exit 1
}
Write-Host "[+] Connected" -ForegroundColor Green
Write-Host ""

# Build service list
$services = if ($Service -eq 'both') {
    @('harvestpilot-raspserver', 'harvestpilot-autodeploy')
} else {
    @($Service)
}

# Handle follow mode
if ($Follow) {
    foreach ($svc in $services) {
        Write-Host ""
        Write-Host "=" * 70 -ForegroundColor Cyan
        Write-Host "Following logs from $svc (Press Ctrl+C to stop)" -ForegroundColor Cyan
        Write-Host "=" * 70 -ForegroundColor Cyan
        Write-Host ""
        $cmd = "sudo journalctl -u $svc -f --no-pager"
        & $PlinkPath -batch -pw $RemotePassword "${RemoteUser}@${RemoteHost}" $cmd
    }
    exit 0
}

# Retrieve logs based on type
foreach ($svc in $services) {
    if ($services.Count -gt 1) {
        Write-Host ""
        Write-Host "=" * 70 -ForegroundColor Yellow
        Write-Host "Service: $svc" -ForegroundColor Yellow
        Write-Host "=" * 70 -ForegroundColor Yellow
        Write-Host ""
    }
    
    $cmd = ""
    
    if ($LogType -eq 'recent') {
        $cmd = "sudo journalctl -u $svc -n $Lines --no-pager"
    }
    elseif ($LogType -eq 'errors') {
        $cmd = "sudo journalctl -u $svc --no-pager | grep -iE 'error|failed|exception|critical' | tail -$Lines"
    }
    elseif ($LogType -eq 'gpio') {
        $cmd = "sudo journalctl -u $svc --no-pager | grep -iE 'gpio|state.*chang|actuator' | tail -$Lines"
    }
    elseif ($LogType -eq 'heartbeat') {
        $cmd = "sudo journalctl -u $svc --no-pager | grep -iE 'heartbeat|sync|firebase' | tail -$Lines"
    }
    elseif ($LogType -eq 'firebase') {
        $cmd = "sudo journalctl -u $svc --no-pager | grep -iE 'firebase|firestore|database' | tail -$Lines"
    }
    elseif ($LogType -eq 'all') {
        $cmd = "sudo journalctl -u $svc -n $Lines --no-pager"
    }
    
    # Handle custom pattern
    if ($Pattern) {
        $cmd = "sudo journalctl -u $svc --no-pager | grep -iE '$Pattern' | tail -$Lines"
    }
    
    Write-Host "[*] Retriev logs from $svc..." -ForegroundColor Blue
    $logs = Invoke-RemoteCommand $cmd
    Write-Host $logs
    Write-Host ""
}

Write-Host "=" * 70 -ForegroundColor Gray
Write-Host "[+] Complete" -ForegroundColor Green
Write-Host ""
Write-Host "Quick commands:" -ForegroundColor Cyan
Write-Host "  .\get-pi-logs.ps1 -LogType errors         # Show errors only" -ForegroundColor Gray
Write-Host "  .\get-pi-logs.ps1 -LogType gpio           # Show GPIO changes" -ForegroundColor Gray
Write-Host "  .\get-pi-logs.ps1 -LogType heartbeat      # Show heartbeat" -ForegroundColor Gray
Write-Host "  .\get-pi-logs.ps1 -LogType firebase       # Show Firebase activity" -ForegroundColor Gray
Write-Host "  .\get-pi-logs.ps1 -Lines 200              # Get more lines" -ForegroundColor Gray
Write-Host "  .\get-pi-logs.ps1 -Pattern 'pattern'      # Custom filter" -ForegroundColor Gray
Write-Host "  .\get-pi-logs.ps1 -Follow                 # Live stream" -ForegroundColor Gray
Write-Host ""
