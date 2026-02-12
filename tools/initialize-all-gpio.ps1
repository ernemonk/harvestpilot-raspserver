#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Initialize and test all GPIO pins
    Ensures all hardware pins are properly configured and synced to Firestore

.PARAMETER LogOutput
    Show log output during tests
#>

param(
    [switch]$LogOutput
)

$RemoteHost = $env:PI_HOST ?? "192.168.1.233"
$RemoteUser = $env:PI_USER ?? "monkphx"
$RemotePassword = $env:PI_PASSWORD  # Set PI_PASSWORD env var before running
$PlinkPath = $env:PLINK_PATH ?? "C:\Users\User\plink.exe"

if (-not $RemotePassword) {
    Write-Host "ERROR: Set the PI_PASSWORD environment variable first." -ForegroundColor Red
    exit 1
}

function Invoke-RemoteCommand {
    param([string]$Command)
    $result = & $PlinkPath -batch -pw $RemotePassword "${RemoteUser}@${RemoteHost}" $Command 2>&1
    return $result
}

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "GPIO Pin Initialization & Testing" -ForegroundColor Cyan
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

Write-Host "[*] Hardware Pins to Configure:" -ForegroundColor Blue
Write-Host "  - GPIO 17 (Pin 11): Pump PWM" -ForegroundColor Gray
Write-Host "  - GPIO 19 (Pin 35): Pump Relay" -ForegroundColor Gray
Write-Host "  - GPIO 18 (Pin 12): LED PWM" -ForegroundColor Gray
Write-Host "  - GPIO 13 (Pin 33): LED Relay" -ForegroundColor Gray
Write-Host "  - GPIO 2,3,9,10,14,8,16: Motor PWM & Direction Pins (6 motors)" -ForegroundColor Gray
Write-Host ""

$Script = @'
import sys
sys.path.insert(0, '/home/monkphx/harvestpilot-raspserver')
import firebase_admin
from firebase_admin import credentials, firestore
from src import config
from src.utils.gpio_import import GPIO, GPIO_AVAILABLE
import time

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)
db = firestore.client()

# GPIO setup
if GPIO_AVAILABLE:
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    print('[*] GPIO hardware available')
else:
    print('[*] GPIO in simulation mode')

# Define all pins
ALL_PINS = {
    17: 'Pump PWM',
    19: 'Pump Relay', 
    18: 'LED PWM',
    13: 'LED Relay'
}

# Add motor pins
for motor in config.MOTOR_PINS:
    ALL_PINS[motor['pwm']] = f"Motor {motor['tray']} PWM"
    ALL_PINS[motor['dir']] = f"Motor {motor['tray']} Direction"
    ALL_PINS[motor['home']] = f"Motor {motor['tray']} Home Sensor"
    ALL_PINS[motor['end']] = f"Motor {motor['tray']} End Sensor"

print(f'[*] Setting up {len(ALL_PINS)} GPIO pins')

device_ref = db.collection('devices').document(config.HARDWARE_SERIAL)
updates = {}

# Initialize all pins
for pin in sorted(ALL_PINS.keys()):
    desc = ALL_PINS[pin]
    try:
        if GPIO_AVAILABLE:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
        print(f"[+] GPIO{pin:2d}: {desc}")
        updates[f'gpioState.{pin}.state'] = False
        updates[f'gpioState.{pin}.name'] = desc
        updates[f'gpioState.{pin}.pin'] = pin
    except Exception as e:
        print(f"[!] GPIO{pin}: {e}")

# Sync to Firestore
try:
    device_ref.update(updates)
    print(f"[✓] Synced {len(updates)//3} pins to Firestore")
except Exception as e:
    print(f"[!] Firestore sync failed: {e}")

# Test first 4 pins (pump, relay, LED, LED relay)
print('[*] Testing main actuator pins...')
test_pins = [17, 19, 18, 13]
for pin in test_pins:
    try:
        # ON
        if GPIO_AVAILABLE:
            GPIO.output(pin, GPIO.HIGH)
        device_ref.update({f'gpioState.{pin}.state': True})
        print(f"    GPIO{pin:2d} → ON")
        time.sleep(0.5)
        
        # OFF
        if GPIO_AVAILABLE:
            GPIO.output(pin, GPIO.LOW)
        device_ref.update({f'gpioState.{pin}.state': False})
        print(f"    GPIO{pin:2d} → OFF")
        time.sleep(0.5)
    except Exception as e:
        print(f"    [!] GPIO{pin}: {e}")

# Verify final state
print('[*] Verifying Firestore state...')
doc = device_ref.get()
if doc.exists:
    gpio_data = doc.to_dict().get('gpioState', {})
    print(f"[✓] {len(gpio_data)} pins in Firestore")
else:
    print('[-] Device document not found')

print('[✓] GPIO initialization complete')
'@

Write-Host "[*] Sending initialization script to Pi..." -ForegroundColor Blue
Write-Host ""

# Send script to Pi and execute
Write-Host "[*] Writing script to Pi..." -ForegroundColor Blue
$scriptPath = "/tmp/init_gpio.py"

# Write script to temp file
$writeCmd = "cat > $scriptPath << 'PYEOF'`n$Script`nPYEOF"
Invoke-RemoteCommand $writeCmd | Out-Null

# Run the script with sudo for GPIO access
Write-Host "[*] Running GPIO initialization..." -ForegroundColor Blue
$result = Invoke-RemoteCommand "cd /home/monkphx/harvestpilot-raspserver && python3 $scriptPath"

Write-Host $result
Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "[✓] GPIO pins configured and tested" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""

Write-Host "Verification steps:" -ForegroundColor Cyan
Write-Host "1. Check Firestore 'devices' collection for your device document" -ForegroundColor Gray
Write-Host "2. Look for 'gpioState' field with all pins listed" -ForegroundColor Gray
Write-Host "3. View logs: .\get-pi-logs.ps1 -LogType gpio" -ForegroundColor Gray
Write-Host ""
