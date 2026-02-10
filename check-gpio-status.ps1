#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Check HarvestPilot GPIO status via SSH

.DESCRIPTION
    Remotely checks GPIO pin states on the Raspberry Pi
    Shows which pins are ON/OFF with visual indicators

.EXAMPLE
    .\check-gpio-status.ps1
    .\check-gpio-status.ps1 -ShowAll
    .\check-gpio-status.ps1 -Logs -NumLogs 50
#>

param(
    [switch]$ShowAll,
    [switch]$Logs,
    [int]$NumLogs = 20
)

$RemoteHost = "192.168.1.233"
$RemoteUser = "monkphx"

function Invoke-RemoteCommand {
    param([string]$Command)
    try {
        # Use ssh command (requires OpenSSH or WSL)
        $result = ssh -o StrictHostKeyChecking=no "${RemoteUser}@${RemoteHost}" $Command 2>&1
        return $result
    } catch {
        Write-Host "SSH Error: $_" -ForegroundColor Red
        Write-Host "Tip: Make sure you have SSH access set up. You can test with:" -ForegroundColor Yellow
        Write-Host "  ssh ${RemoteUser}@${RemoteHost}" -ForegroundColor Cyan
        return $null
    }
}

function Show-Header {
    Write-Host ""
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host "  🔌 HarvestPilot GPIO Status" -ForegroundColor Cyan
    Write-Host "=" * 70 -ForegroundColor Cyan
    Write-Host ""
}

function Check-GPIO-Status {
    Write-Host "Checking GPIO status on Pi..." -ForegroundColor Blue
    
    $cmd = "cd /home/monkphx/harvestpilot-raspserver && python3 src/scripts/check_gpio_status.py"
    $result = Invoke-RemoteCommand $cmd
    
    if ($result) {
        Write-Host $result
    } else {
        Write-Host "Failed to retrieve GPIO status" -ForegroundColor Red
        Write-Host ""
        Write-Host "Try running this command manually from PowerShell:" -ForegroundColor Yellow
        Write-Host "  ssh monkphx@192.168.1.233" -ForegroundColor Cyan
        Write-Host "Then on the Pi:" -ForegroundColor Yellow
        Write-Host "  python3 src/scripts/check_gpio_status.py" -ForegroundColor Cyan
    }
}

function Show-GPIO-Logs {
    param([int]$NumLines = 20)
    
    Write-Host "Retrieving GPIO logs (last $NumLines lines)..." -ForegroundColor Blue
    
    $cmd = "tail -$NumLines /home/monkphx/harvestpilot-raspserver/logs/raspserver.log | grep -i 'gpio|pin|state' || echo 'No recent GPIO activity found'"
    $result = Invoke-RemoteCommand $cmd
    
    Write-Host ""
    if ($result) {
        Write-Host $result
    } else {
        Write-Host "Could not retrieve logs" -ForegroundColor Yellow
    }
}

function Show-Advanced-Info {
    Write-Host ""
    Write-Host "💡 Useful Commands:" -ForegroundColor Green
    Write-Host ""
    Write-Host "  # SSH into Pi and check status:"
    Write-Host "  ssh monkphx@192.168.1.233" -ForegroundColor Cyan
    Write-Host "  python3 src/scripts/check_gpio_status.py"
    Write-Host ""
    Write-Host "  # View logs in real-time:"
    Write-Host "  tail -f logs/raspserver.log | grep GPIO" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  # Check specific pin state:"
    Write-Host "  python3 -c \"import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); GPIO.setup(17, GPIO.IN); print('GPIO17:', 'ON' if GPIO.input(17) else 'OFF')\"" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  # Check Firestore directly (source of truth):" -ForegroundColor Yellow
    Write-Host "  Firebase Console > Firestore > devices > [your-device-id] > gpioState"
    Write-Host ""
}

# Main execution
Show-Header

if ($Logs) {
    Show-GPIO-Logs -NumLines $NumLogs
} else {
    Check-GPIO-Status
}

Show-Advanced-Info

Write-Host ""

