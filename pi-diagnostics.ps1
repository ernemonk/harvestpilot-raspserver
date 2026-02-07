#Requires -Version 5.0
# HarvestPilot Pi Complete Diagnostics
# ONE comprehensive script for all diagnostics and logs

$Host = "192.168.1.233"
$User = "monkphx"
$Pass = "149246116"
$Plink = ".\plink.exe"

function Cmd {
    param([string]$C)
    & $Plink -batch -pw $Pass "${User}@${Host}" $C 2>&1
}

Clear-Host
Write-Host ""
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "  HarvestPilot Raspberry Pi Complete Diagnostics" -ForegroundColor Cyan
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host ""

# Test connection
Write-Host "[*] Testing SSH Connection..." -ForegroundColor Yellow
$test = Cmd "echo OK"
if ($test -notmatch "OK") {
    Write-Host "[!] Connection failed!" -ForegroundColor Red
    exit 1
}
Write-Host "[+] Connected to ${User}@${Host}" -ForegroundColor Green
Write-Host ""

# ============================================================================
# SECTION 1: SYSTEM STATUS
# ============================================================================
Write-Host "--- SYSTEM STATUS ---" -ForegroundColor Cyan
$uptime = (Cmd "uptime").Trim()
$disk = (Cmd "df -h / | tail -1 | awk '{print `$5}'").Trim()
$mem = (Cmd "free -h | grep Mem | awk '{print `$3\"/\"$2}'").Trim()
$temp = (Cmd "vcgencmd measure_temp 2>/dev/null | cut -d= -f2").Trim()

Write-Host "Uptime: $uptime" -ForegroundColor Gray
Write-Host "Disk: $disk used" -ForegroundColor Gray
Write-Host "Memory: $mem" -ForegroundColor Gray
Write-Host "Temperature: $temp" -ForegroundColor Gray
Write-Host ""

# ============================================================================
# SECTION 2: SERVICE STATUS
# ============================================================================
Write-Host "--- SERVICE STATUS ---" -ForegroundColor Cyan
$mainStatus = (Cmd "sudo systemctl is-active harvestpilot-raspserver.service 2>/dev/null").Trim()
if ($mainStatus -eq "active") {
    Write-Host "[+] Main Service: RUNNING" -ForegroundColor Green
} else {
    Write-Host "[-] Main Service: NOT RUNNING" -ForegroundColor Red
}

$pidInfo = (Cmd "ps aux | grep '/usr/bin/python3 main.py' | grep -v grep | awk '{print \"PID:\" `$2 \" CPU:\" `$3 \"%  MEM:\" `$4 \"%\"}'").Trim()
if ($pidInfo) {
    Write-Host "    $pidInfo" -ForegroundColor Gray
}

Write-Host ""

# ============================================================================
# SECTION 3: FIREBASE CONNECTION
# ============================================================================
Write-Host "--- FIREBASE CONNECTION ---" -ForegroundColor Cyan
$firebase = Cmd "sudo journalctl -u harvestpilot-raspserver.service --no-pager 2>/dev/null | grep -i 'connected to firebase' | tail -1"
if ($firebase) {
    Write-Host "[+] $($firebase -replace '.*INFO - ', '')" -ForegroundColor Green
} else {
    Write-Host "[!] Firebase status unclear - check logs" -ForegroundColor Yellow
}
Write-Host ""

# ============================================================================
# SECTION 4: HEARTBEAT & SYNC - THE CRITICAL CHECK
# ============================================================================
Write-Host "--- HEARTBEAT & SYNC ACTIVITY (Last 30 minutes) ---" -ForegroundColor Cyan

$recentLogs = Cmd "sudo journalctl -u harvestpilot-raspserver.service --since '30 min ago' --no-pager 2>/dev/null"
if ($recentLogs) {
    $recentLogs | ForEach-Object {
        if ($_ -match "ERROR|error|failed|Failed") {
            Write-Host "[ERROR] $_" -ForegroundColor Red
        } elseif ($_ -match "heartbeat|Heartbeat") {
            Write-Host "[HB]    $_" -ForegroundColor Green
        } elseif ($_ -match "sync|Sync") {
            Write-Host "[SYNC]  $_" -ForegroundColor Cyan
        } else {
            Write-Host "        $_" -ForegroundColor Gray
        }
    }
} else {
    Write-Host "No recent logs found" -ForegroundColor Yellow
}
Write-Host ""

# ============================================================================
# SECTION 5: ERROR ANALYSIS
# ============================================================================
Write-Host "--- ERROR SUMMARY (Last 1 hour) ---" -ForegroundColor Cyan

$errors = Cmd "sudo journalctl -u harvestpilot-raspserver.service --since '1 hour ago' --no-pager 2>/dev/null | grep -iE 'ERROR|CRITICAL|Exception' | head -20"
if ($errors) {
    $errors | ForEach-Object {
        Write-Host "[!] $_" -ForegroundColor Red
    }
} else {
    Write-Host "[+] No critical errors found" -ForegroundColor Green
}
Write-Host ""

# ============================================================================
# SECTION 6: FULL SERVICE OUTPUT
# ============================================================================
Write-Host "--- FULL SERVICE STATUS ---" -ForegroundColor Cyan

$fullStatus = Cmd "sudo systemctl status harvestpilot-raspserver.service --no-pager 2>/dev/null"
$fullStatus | ForEach-Object {
    Write-Host "$_" -ForegroundColor Gray
}
Write-Host ""

# ============================================================================
# SECTION 7: DIAGNOSTICS & RECOMMENDATIONS
# ============================================================================
Write-Host "--- DIAGNOSTICS & RECOMMENDATIONS ---" -ForegroundColor Yellow

if ($mainStatus -eq "active") {
    Write-Host "[+] Service is running" -ForegroundColor Green
    
    if ($firebase) {
        Write-Host "[+] Firebase connected" -ForegroundColor Green
    } else {
        Write-Host "[!] Firebase connection status unclear" -ForegroundColor Yellow
    }
    
    if ($recentLogs -match "heartbeat|sync") {
        Write-Host "[+] Heartbeat/Sync activity detected" -ForegroundColor Green
    } else {
        Write-Host "[!] NO HEARTBEAT/SYNC ACTIVITY IN LAST 30 MIN" -ForegroundColor Red
        Write-Host ""
        Write-Host "    Possible issues:" -ForegroundColor Yellow
        Write-Host "    1. Heartbeat loop not running (code exception)" -ForegroundColor Yellow
        Write-Host "    2. Logging not capturing heartbeat events" -ForegroundColor Yellow
        Write-Host "    3. Service stalled/frozen" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "    To debug live logs:" -ForegroundColor Magenta
        Write-Host "    sudo journalctl -u harvestpilot-raspserver -f" -ForegroundColor Magenta
    }
} else {
    Write-Host "[-] Service NOT RUNNING" -ForegroundColor Red
    Write-Host ""
    Write-Host "    Restart with:" -ForegroundColor Magenta
    Write-Host "    sudo systemctl restart harvestpilot-raspserver.service" -ForegroundColor Magenta
}

Write-Host ""
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "Diagnostics Complete - $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Cyan
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host ""
