#!/usr/bin/env pwsh
<#
.SYNOPSIS
    HarvestPilot GPIO & System Diagnostics
    Comprehensive Pi status checker with GPIO, service status, logs, and more

.DESCRIPTION
    Complete diagnostics for HarvestPilot Raspberry Pi deployment:
    - GPIO pin states and configuration
    - System health (uptime, disk, memory, temperature)
    - Service status and process info
    - Recent logs and errors
    - Firebase connectivity
    - Schedule listener status

.PARAMETER CheckType
    Type of check to run: gpio, system, service, logs, firebase, all (default: gpio)

.PARAMETER NumLogs
    Number of log lines to display (default: 50)

.PARAMETER Tail
    Tail logs in real-time instead of one-time view

.EXAMPLE
    .\check-gpio-status.ps1                    # Check GPIO status
    .\check-gpio-status.ps1 -CheckType all     # Full diagnostics
    .\check-gpio-status.ps1 -CheckType logs -NumLogs 100
    .\check-gpio-status.ps1 -CheckType logs -Tail
#>

param(
    [ValidateSet("gpio", "system", "service", "logs", "firebase", "all")]
    [string]$CheckType = "gpio",
    [int]$NumLogs = 50,
    [switch]$Tail,
    [string]$RemoteHost = "192.168.1.233",
    [string]$RemoteUser = "monkphx"
)

# ============================================================================
# CONFIGURATION & COLORS
# ============================================================================

$ErrorActionPreference = 'Continue'

$Colors = @{
    Header = "Cyan"
    Success = "Green"
    Error = "Red"
    Warning = "Yellow"
    Info = "Blue"
    Section = "Cyan"
    Muted = "Gray"
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

function Write-Header {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 70) -ForegroundColor $Colors.Header
    Write-Host "  $Title" -ForegroundColor $Colors.Header
    Write-Host ("=" * 70) -ForegroundColor $Colors.Header
    Write-Host ""
}

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "[*] $Title" -ForegroundColor $Colors.Section
    Write-Host ("-" * 70) -ForegroundColor $Colors.Muted
}

function Write-Success {
    param([string]$Message)
    Write-Host "[+] $Message" -ForegroundColor $Colors.Success
}

function Write-Error-Custom {
    param([string]$Message)
    Write-Host "[!] $Message" -ForegroundColor $Colors.Error
}

function Write-Warning-Custom {
    param([string]$Message)
    Write-Host "[~] $Message" -ForegroundColor $Colors.Warning
}

function Write-Info {
    param([string]$Message)
    Write-Host "[i] $Message" -ForegroundColor $Colors.Info
}

function Invoke-RemoteCommand {
    param(
        [string]$Command,
        [switch]$FailSilent
    )
    
    try {
        # Use SSH with bash to ensure commands work
        $result = ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 `
            "${RemoteUser}@${RemoteHost}" $Command 2>&1
        
        if ($LASTEXITCODE -ne 0 -and -not $FailSilent) {
            Write-Error-Custom "SSH command failed (exit code: $LASTEXITCODE)"
        }
        return $result
    } catch {
        if (-not $FailSilent) {
            Write-Error-Custom "SSH connection failed: $_"
            Write-Info "Make sure SSH is configured: ssh ${RemoteUser}@${RemoteHost}"
        }
        return $null
    }
}

function Test-SSHConnection {
    Write-Section "Testing SSH Connection"
    
    $result = Invoke-RemoteCommand "echo 'SSH_OK'" -FailSilent
    
    if ($result -match "SSH_OK") {
        Write-Success "Connected to ${RemoteUser}@${RemoteHost}"
        return $true
    } else {
        Write-Error-Custom "SSH connection failed"
        Write-Info "Troubleshooting:"
        Write-Host "  1. Test manually: ssh ${RemoteUser}@${RemoteHost}" -ForegroundColor $Colors.Muted
        Write-Host "  2. Ensure SSH key is configured or password-less auth is enabled" -ForegroundColor $Colors.Muted
        Write-Host "  3. Check firewall: ping 192.168.1.233" -ForegroundColor $Colors.Muted
        return $false
    }
}

# ============================================================================
# GPIO STATUS CHECK
# ============================================================================

function Check-GPIO-Status {
    Write-Header "🔌 HarvestPilot GPIO Status"
    
    if (-not (Test-SSHConnection)) { return 1 }
    
    Write-Section "Fetching GPIO State from Firestore"
    
    $cmd = "cd /home/monkphx/harvestpilot-raspserver; python3 src/scripts/check_gpio_status.py"
    $result = Invoke-RemoteCommand $cmd
    
    if ($result) {
        Write-Host $result
        return 0
    } else {
        Write-Error-Custom "Failed to retrieve GPIO status"
        Write-Info "Troubleshooting:"
        Write-Host "  1. Check Python dependencies: ssh ${RemoteUser}@${RemoteHost} 'pip3 list | grep firebase'" -ForegroundColor $Colors.Muted
        Write-Host "  2. Check firebase-key.json: ssh ${RemoteUser}@${RemoteHost} 'ls -la ~/harvestpilot-raspserver/firebase-key.json'" -ForegroundColor $Colors.Muted
        Write-Host "  3. Check logs: .\check-gpio-status.ps1 -CheckType logs" -ForegroundColor $Colors.Muted
        return 1
    }
}

# ============================================================================
# SYSTEM STATUS CHECK
# ============================================================================

function Check-SystemStatus {
    Write-Header "📊 System Status"
    
    if (-not (Test-SSHConnection)) { return 1 }
    
    Write-Section "System Metrics"
    
    # Get simple uptime
    $uptime = Invoke-RemoteCommand "uptime"
    if ($uptime) {
        Write-Info "Uptime: $uptime"
    }
    
    # Get disk space
    $disk = Invoke-RemoteCommand "df -h /"
    if ($disk) {
        Write-Info "Disk usage:"
        $disk | ForEach-Object { Write-Host "  $_" -ForegroundColor $Colors.Muted }
    }
    
    # Get memory
    $memory = Invoke-RemoteCommand "free -h"
    if ($memory) {
        Write-Info "Memory:"
        $memory | ForEach-Object { Write-Host "  $_" -ForegroundColor $Colors.Muted }
    }
    
    return 0
}

# ============================================================================
# SERVICE STATUS CHECK
# ============================================================================

function Check-ServiceStatus {
    Write-Header "🔧 Service Status"
    
    if (-not (Test-SSHConnection)) { return 1 }
    
    Write-Section "HarvestPilot Services"
    
    # Check main service
    $status = Invoke-RemoteCommand "sudo systemctl is-active harvestpilot-raspserver.service 2>/dev/null; true"
    
    if ($status -eq "active") {
        Write-Success "Main Service (harvestpilot-raspserver): RUNNING"
    } else {
        Write-Error-Custom "Main Service (harvestpilot-raspserver): $status"
    }
    
    # Check python process
    $procInfo = Invoke-RemoteCommand "ps aux | grep 'python3 main.py' | grep -v grep | awk '{print \"PID:\" \$2 \" CPU:\" \$3 \"% MEM:\" \$4 \"%\"}'"
    
    if ($procInfo) {
        Write-Success "Python Process: $procInfo"
    } else {
        Write-Error-Custom "Python Process: Not running"
    }
    
    # Check auto-deploy service if exists
    $autoDeploy = Invoke-RemoteCommand "sudo systemctl is-active harvestpilot-autodeploy.service 2>/dev/null; true" -FailSilent
    if ($autoDeploy -eq "active") {
        Write-Success "Auto-Deploy Service: RUNNING"
    } elseif ($autoDeploy -ne "not-found") {
        Write-Warning-Custom "Auto-Deploy Service: $autoDeploy"
    }
    
    return 0
}

# ============================================================================
# FIREBASE CONNECTIVITY CHECK
# ============================================================================

function Check-FirebaseStatus {
    Write-Header "🔥 Firebase Connectivity"
    
    if (-not (Test-SSHConnection)) { return 1 }
    
    Write-Section "Firebase Connection Status"
    
    # Check if credentials exist
    $credsExist = Invoke-RemoteCommand "test -f ~/harvestpilot-raspserver/firebase-key.json && echo 'exists' || echo 'missing'"
    
    if ($credsExist -eq "missing") {
        Write-Error-Custom "Firebase credentials not found"
        Write-Info "Expected location: /home/monkphx/harvestpilot-raspserver/firebase-key.json"
        return 1
    }
    
    Write-Success "Firebase credentials found"
    
    # Check recent Firestore activity in logs
    $recentActivity = Invoke-RemoteCommand "tail -5 /home/monkphx/harvestpilot-raspserver/logs/raspserver.log 2>/dev/null; true" -FailSilent
    
    if ($recentActivity) {
        Write-Section "Recent Firebase Activity"
        $recentActivity | ForEach-Object {
            if ($_ -match "ERROR|error|failed") {
                Write-Error-Custom $_
            } elseif ($_ -match "connected|Connected|SUCCESS") {
                Write-Success $_
            } else {
                Write-Info $_
            }
        }
    } else {
        Write-Warning-Custom "No recent Firebase activity in logs"
    }
    
    # Check schedule listener status
    $scheduleListener = Invoke-RemoteCommand "grep 'FirestoreScheduleListener' /home/monkphx/harvestpilot-raspserver/logs/raspserver.log 2>/dev/null; true" -FailSilent
    
    if ($scheduleListener) {
        Write-Success "Schedule Listener Status: $scheduleListener"
    } else {
        Write-Warning-Custom "Schedule Listener: No recent activity in logs"
        Write-Info "  (This is normal if no schedules have been created in Firestore)"
    }
    
    return 0
}

# ============================================================================
# LOGS CHECK
# ============================================================================

function Check-Logs {
    Write-Header "📋 Server Logs"
    
    if (-not (Test-SSHConnection)) { return 1 }
    
    if ($Tail) {
        Write-Section "Tailing logs in real-time (Ctrl+C to stop)"
        $cmd = "tail -f /home/monkphx/harvestpilot-raspserver/logs/raspserver.log"
        Invoke-RemoteCommand $cmd
    } else {
        Write-Section "Last $NumLogs log entries"
        $cmd = "tail -$NumLogs /home/monkphx/harvestpilot-raspserver/logs/raspserver.log 2>/dev/null; true"
        $logs = Invoke-RemoteCommand $cmd
        
        if ($logs) {
            $logs | ForEach-Object {
                if ($_ -match "ERROR|error|failed|FATAL") {
                    Write-Error-Custom $_
                } elseif ($_ -match "WARNING|warning") {
                    Write-Warning-Custom $_
                } elseif ($_ -match "SUCCESS|success|connected|Connected") {
                    Write-Success $_
                } else {
                    Write-Host $_ -ForegroundColor $Colors.Muted
                }
            }
        }
    }
    
    return 0
}

# ============================================================================
# FULL DIAGNOSTICS
# ============================================================================

function Check-All {
    Write-Header "🔍 HarvestPilot Complete Diagnostics"
    Write-Info "Timestamp: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    
    $results = @()
    
    # Run all checks
    $results += @{ Name = "System Status"; Exit = (Check-SystemStatus) }
    $results += @{ Name = "Service Status"; Exit = (Check-ServiceStatus) }
    $results += @{ Name = "Firebase Status"; Exit = (Check-FirebaseStatus) }
    $results += @{ Name = "GPIO Status"; Exit = (Check-GPIO-Status) }
    
    # Summary
    Write-Host ""
    Write-Header "📊 Diagnostics Summary"
    
    $allGood = $true
    $results | ForEach-Object {
        if ($_.Exit -eq 0) {
            Write-Success "$($_.Name): OK"
        } else {
            Write-Error-Custom "$($_.Name): ISSUES FOUND"
            $allGood = $false
        }
    }
    
    Write-Host ""
    if ($allGood) {
        Write-Success "All diagnostics passed!"
        return 0
    } else {
        Write-Warning-Custom "Some issues detected - see above for details"
        Write-Info "For more details, run: .\check-gpio-status.ps1 -CheckType logs"
        return 1
    }
}

# ============================================================================
# HELPER COMMANDS
# ============================================================================

function Show-Help {
    Write-Host @"
🔌 HarvestPilot GPIO & System Diagnostics

USAGE:
  .\check-gpio-status.ps1 [options]

EXAMPLES:
  Check GPIO status:
    .\check-gpio-status.ps1
    .\check-gpio-status.ps1 -CheckType gpio

  Full diagnostics:
    .\check-gpio-status.ps1 -CheckType all

  View logs:
    .\check-gpio-status.ps1 -CheckType logs
    .\check-gpio-status.ps1 -CheckType logs -NumLogs 100
    .\check-gpio-status.ps1 -CheckType logs -Tail

  Check specific system info:
    .\check-gpio-status.ps1 -CheckType system
    .\check-gpio-status.ps1 -CheckType service
    .\check-gpio-status.ps1 -CheckType firebase

TROUBLESHOOTING:
  If SSH connection fails:
    1. Test SSH manually: ssh ${RemoteUser}@${RemoteHost}
    2. Ensure SSH key ~/.ssh/id_rsa exists
    3. Check firewall: ping ${RemoteHost}

  If GPIO status shows errors:
    1. Check logs: .\check-gpio-status.ps1 -CheckType logs
    2. Verify firebase-key.json exists on Pi
    3. Check Firestore has devices/{serial}/gpioState structure
"@ -ForegroundColor $Colors.Info
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

switch ($CheckType.ToLower()) {
    "gpio" {
        $exitCode = Check-GPIO-Status
    }
    "system" {
        $exitCode = Check-SystemStatus
    }
    "service" {
        $exitCode = Check-ServiceStatus
    }
    "firebase" {
        $exitCode = Check-FirebaseStatus
    }
    "logs" {
        $exitCode = Check-Logs
    }
    "all" {
        $exitCode = Check-All
    }
    default {
        Show-Help
        $exitCode = 0
    }
}

Write-Host ""
exit $exitCode

