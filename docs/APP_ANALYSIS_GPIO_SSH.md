# HarvestPilot App Analysis - SSH & GPIO Guide

## 📋 Summary

I've analyzed your HarvestPilot RaspServer codebase. Here's what I found about SSHing into your Pi and checking GPIO states:

---

## 🚀 Quick Start

### 1️⃣ **SSH to Your Raspberry Pi**

**From Windows PowerShell/Terminal:**
```powershell
ssh monkphx@192.168.1.233
# Password: 149246116
```

**From the workspace**, use the PowerShell script:
```powershell
.\check-gpio-status.ps1
```

---

## 🔌 What GPIO Pins Your App Uses

### **Main Actuators** (4 pins)
- **GPIO 17** (Pin 11) → Pump PWM
- **GPIO 19** (Pin 35) → Pump Relay  
- **GPIO 18** (Pin 12) → LED PWM (Brightness)
- **GPIO 13** (Pin 33) → LED Relay

### **Harvest Belt Motors** (6 trays)
Each motor uses 4 pins (PWM, Direction, Home Sensor, End Sensor):
- Tray 1: GPIO 2 (PWM), 3 (Dir), 17 (Home), 27 (End)
- Tray 2: GPIO 9 (PWM), 11 (Dir), 5 (Home), 6 (End)
- Tray 3: GPIO 10 (PWM), 22 (Dir), 23 (Home), 24 (End)  
- Tray 4: GPIO 14 (PWM), 15 (Dir), 18 (Home), 25 (End)
- Tray 5: GPIO 8 (PWM), 7 (Dir), 1 (Home), 12 (End)
- Tray 6: GPIO 16 (PWM), 20 (Dir), 21 (Home), 26 (End)

**Total: 28 GPIO pins configured**

---

## ✅ How to Check Which Pins Are ON/OFF

### **Method 1: Via Windows (PowerShell)** ⭐ Easiest
```powershell
# In your workspace root
.\check-gpio-status.ps1

# Check specific pin
.\check-gpio-status.ps1 -Pin 17

# View logs
.\check-gpio-status.ps1 -Logs -NumLogs 50
```

### **Method 2: SSH Into Pi & Run Python Script**
```bash
ssh monkphx@192.168.1.233
cd /home/monkphx/harvestpilot-raspserver

# Use the script I created for you
python3 src/scripts/check_gpio_status.py
```

### **Method 3: Check Firestore (Source of Truth)** 🔥
This is what your app uses to track state:

1. Open Firebase Console
2. Go to **Firestore** → **Collections**
3. Navigate to: `devices` → `{your-device-id}` 
4. Look at the **`gpioState`** field
5. Each pin shows `"state": true` (ON) or `"state": false` (OFF)

Example structure:
```json
"gpioState": {
  "17": {
    "state": true,      // ✅ PUMP IS ON
    "name": "Pump PWM",
    "pin": 17
  },
  "18": {
    "state": false,     // ⚫ LED IS OFF
    "name": "LED PWM",
    "pin": 18
  }
  // ... more pins
}
```

### **Method 4: SSH Commands**

After SSH'd in:

```bash
# View real-time logs filtered for GPIO
tail -f logs/raspserver.log | grep GPIO

# Quick Python check of GPIO 17
python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN)
print('GPIO17:', 'ON (HIGH)' if GPIO.input(17) else 'OFF (LOW)')
"

# Check device serial (needed for Firestore look-up)
cat /proc/cpuinfo | grep Serial
```

---

## 🏗️ App Architecture - How GPIO Works

```
Your Raspberry Pi (SSH Access)
    ↓
HarvestPilot RaspServer (main.py)
    ↓
GPIOActuatorController Service
    ├─ Listens to Firestore for commands
    ├─ Directly controls GPIO pins via RPi.GPIO
    └─ Updates pin states back to Firestore
    ↓
Firestore Database (Cloud)
    └─ Stores gpioState for each pin
```

**Key Classes in Code:**
- `GPIOActuatorController` ([src/services/gpio_actuator_controller.py](src/services/gpio_actuator_controller.py#L27)) - Controls pins
- `PinConfigManager` ([src/utils/pin_config.py](src/utils/pin_config.py#L105)) - Manages pin configs

---

## 📊 Current GPIO State - Where to Find It

### **In Your App Code:**
```python
# This is what tracks state
self._pin_states: Dict[int, bool] = {}  # Pin → On/Off

# Methods to read state
controller.read_pin(17)           # Read GPIO 17
controller.get_pin_states()       # Get all pins
```

### **In Firestore Database:**
- **Collection:** `devices`
- **Document:** `{hardware_serial}` (found in `/proc/cpuinfo`)
- **Field:** `gpioState`
- **Each pin shows:** `{pin}.state = true|false`

---

## 🛠️ Test Commands

### **Test Pump (GPIO 17) - Turn ON then OFF**
```bash
ssh monkphx@192.168.1.233
cd /home/monkphx/harvestpilot-raspserver

# Turn ON
sudo python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.OUT)
GPIO.output(17, GPIO.HIGH)
print('✅ Pump turned ON')
"

# Wait a few seconds, then turn OFF
sudo python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.OUT)
GPIO.output(17, GPIO.LOW)
print('⚫ Pump turned OFF')
"
```

### **Run Full Hardware Test**
```bash
cd /home/monkphx/harvestpilot-raspserver
sudo python3 src/scripts/test_gpio_pins.py
```

### **Test LED (GPIO 18) Brightness**
```bash
sudo python3 src/scripts/test_led_brightness.py
```

---

## 📁 Key Files in Your App

| File | Purpose |
|------|---------|
| [src/config.py](src/config.py) | All GPIO pin definitions |
| [src/services/gpio_actuator_controller.py](src/services/gpio_actuator_controller.py) | GPIO control & Firestore sync |
| [src/scripts/check_gpio_status.py](src/scripts/check_gpio_status.py) | NEW: Status checker I created |
| [check-gpio-status.ps1](check-gpio-status.ps1) | NEW: Windows PowerShell checker |
| [initialize-all-gpio.ps1](initialize-all-gpio.ps1) | GPIO initialization (has SSH credentials) |
| [initialize-gpio-pins.py](initialize-gpio-pins.py) | GPIO setup script |

---

## ⚠️ SECURITY ISSUES TO FIX

1. **Hardcoded SSH Password** in `initialize-all-gpio.ps1`
   - Current: `$RemotePassword = "149246116"`  
   - Fix: Use SSH keys instead

2. **Firebase Credentials** stored in repo
   - File: `config/harvest-hub-2025-firebase-adminsdk-fbsvc-460b441782.json`
   - Fix: Add to `.gitignore`, use environment variables

3. **Password in PowerShell Scripts**
   - Logged in command history
   - Fix: Store in secure credential files

---

## 📖 New Resources I Created

I've created these files to make it easier for you:

### 1. **[docs/SSH_GPIO_QUICK_REFERENCE.md](docs/SSH_GPIO_QUICK_REFERENCE.md)**
   - Complete SSH & GPIO reference guide
   - All pin layouts and functions
   - Multiple methods to check GPIO state
   - Troubleshooting tips

### 2. **[src/scripts/check_gpio_status.py](src/scripts/check_gpio_status.py)**
   - Run on Pi to see colored GPIO status
   - Usage: `python3 src/scripts/check_gpio_status.py`
   - Shows ON/OFF for all configured pins

### 3. **[check-gpio-status.ps1](check-gpio-status.ps1)**
   - Run from Windows to check Pi GPIO remotely
   - Usage: `.\check-gpio-status.ps1`
   - No need to SSH manually

---

## 🎯 Quick Cheat Sheet

```powershell
# Windows: Check GPIO from your PC
.\check-gpio-status.ps1

# Windows: Check specific pin
.\check-gpio-status.ps1 -Pin 17

# Windows: View GPIO logs
.\check-gpio-status.ps1 -Logs
```

```bash
# SSH to Pi
ssh monkphx@192.168.1.233    # Password: 149246116

# Check all GPIO states (on Pi)
python3 src/scripts/check_gpio_status.py

# Check logs
tail -f logs/raspserver.log | grep GPIO

# Test Pump (GPIO 17)
sudo python3 -c "import RPi.GPIO as GPIO; GPIO.setmode(GPIO.BCM); GPIO.setup(17, GPIO.OUT); GPIO.output(17, GPIO.HIGH)"
```

---

## 🚦 GPIO Pin Reference

```
MAIN ACTUATORS:
├─ GPIO 17 (Pin 11) = Pump PWM      ← Probably ON for irrigation
├─ GPIO 19 (Pin 35) = Pump Relay    ← Supporting pin
├─ GPIO 18 (Pin 12) = LED PWM       ← Brightness control
└─ GPIO 13 (Pin 33) = LED Relay     ← Supporting pin

MOTORS (6 trays):
├─ Tray 1: GPIO 2, 3, 17, 27
├─ Tray 2: GPIO 9, 11, 5, 6
├─ Tray 3: GPIO 10, 22, 23, 24
├─ Tray 4: GPIO 14, 15, 18, 25
├─ Tray 5: GPIO 8, 7, 1, 12
└─ Tray 6: GPIO 16, 20, 21, 26
```

---

## 💾 How App Stores GPIO State

In your Firestore:
- **ON pins** → `gpioState.{pinNumber}.state = true`
- **OFF pins** → `gpioState.{pinNumber}.state = false`

This is updated in real-time by `_cache_pin_state_to_device()` method in [GPIOActuatorController](src/services/gpio_actuator_controller.py#L372).

---

## ✨ Summary

You can now:
1. ✅ SSH into your Pi: `ssh monkphx@192.168.1.233`
2. ✅ Check which GPIO pins are ON/OFF using:
   - Firestore Console (best for UI)
   - Windows PowerShell: `.\check-gpio-status.ps1`
   - Python script on Pi: `python3 src/scripts/check_gpio_status.py`
   - Raw SSH commands

Your app maintains GPIO state in **Firestore** which is the source of truth for what's ON/OFF.

---

Need help with anything else? Check the new [SSH_GPIO_QUICK_REFERENCE.md](docs/SSH_GPIO_QUICK_REFERENCE.md) file for more detailed info!
