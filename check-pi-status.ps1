#!/usr/bin/env pwsh
# Check HarvestPilot service status - Using plink for password auth
# First run: .\install-plink.ps1

param(
    [string]$PiHost = "192.168.1.233",
    [string]$PiUser = "pi",
    [string]$PiPassword = "149246116"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "HarvestPilot Pi Diagnostics" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Target: $PiUser@$PiHost" -ForegroundColor Yellow
Write-Host ""

# Find plink executable
$plinkPaths = @(
    "C:\Program Files\PuTTY\plink.exe",
    "C:\Program Files (x86)\PuTTY\plink.exe",
    (Join-Path $HOME "plink.exe"),
    (Get-Command plink -ErrorAction SilentlyContinue).Source
)

$plinkExe = $null
foreach ($path in $plinkPaths) {
    if ($path -and (Test-Path $path)) {
        $plinkExe = $path
        break
    }
}

if (-not $plinkExe) {
    Write-Host "[!] plink.exe not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Install plink.exe first:" -ForegroundColor Yellow
    Write-Host "  .\install-plink.ps1" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Or install manually from:" -ForegroundColor Yellow
    Write-Host "  https://www.chiark.greenend.org.uk/~sgtatham/putty/latest.html" -ForegroundColor Yellow
    exit 1
}

Write-Host "[+] Using plink from: $plinkExe" -ForegroundColor Green
Write-Host ""

# Function to run SSH commands with plink and password
function Invoke-PiCmd {
    param([string]$Cmd)
    # Accept new host key with -batchmode off, but use password auth
    & $plinkExe -pw $PiPassword -l $PiUser $PiHost $Cmd 2>&1
}

# Test connection
Write-Host "[*] Testing SSH connection..." -ForegroundColor Cyan
Write-Host "[*] (First time will prompt to accept host key - type 'y')" -ForegroundColor Yellow
$testCmd = & "C:\Users\User\plink.exe" -pw $PiPassword -l $PiUser $PiHost "echo OK" 2>&1

if ($testCmd -like "*OK*" -or $testCmd -match "OK") {
    Write-Host "[+] Connected to Pi" -ForegroundColor Green
} else {
    Write-Host "[!] Connection failed" -ForegroundColor Red
    Write-Host "Output: $testCmd" -ForegroundColor Yellow
    exit 1
}
Write-Host ""

# Service Status
Write-Host "[*] SERVICE STATUS" -ForegroundColor Cyan
Write-Host "-" * 40 -ForegroundColor Cyan
Invoke-PiCmd "sudo systemctl status harvestpilot-autodeploy.service --no-pager"
Write-Host ""

# Process Check
Write-Host "[*] PROCESS CHECK" -ForegroundColor Cyan
Write-Host "-" * 40 -ForegroundColor Cyan
Invoke-PiCmd "ps aux | grep python | grep main"
Write-Host ""

# Recent Logs
Write-Host "[*] RECENT LOGS (Last 50 lines)" -ForegroundColor Cyan
Write-Host "-" * 40 -ForegroundColor Cyan
Invoke-PiCmd "sudo journalctl -u harvestpilot-autodeploy.service -n 50 --no-pager"
Write-Host ""

# Recent Errors
Write-Host "[!] RECENT ERRORS" -ForegroundColor Cyan
Write-Host "-" * 40 -ForegroundColor Cyan
Invoke-PiCmd "sudo journalctl -u harvestpilot-autodeploy.service --no-pager | grep -i error | tail -20"
Write-Host ""

# Heartbeat Info
Write-Host "[*] HEARTBEAT / SYNC INFO" -ForegroundColor Cyan
Write-Host "-" * 40 -ForegroundColor Cyan
Invoke-PiCmd "sudo journalctl -u harvestpilot-autodeploy.service --no-pager | grep -iE 'heartbeat|sync' | tail -15"
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "[+] Diagnostics complete" -ForegroundColor Green
Write-Host ""
Write-Host "[*] For live logs:" -ForegroundColor Cyan
Write-Host "    & `"$plinkExe`" -pw $PiPassword -l $PiUser -hostkey `"key`" $PiHost `"sudo journalctl -u harvestpilot-autodeploy.service -f`"" -ForegroundColor Cyan
Write-Host ""
