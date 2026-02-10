# SSH & GPIO Status Quick Reference

## 🔌 SSH Connection Details

**Pi Information:**
- **IP Address:** `192.168.1.233`
- **Username:** `monkphx`
- **Password:** `149246116`

### Connect via SSH

**From Windows PowerShell:**
```powershell
ssh monkphx@192.168.1.233
# Enter password: 149246116
```

**From Linux/macOS:**
```bash
ssh monkphx@192.168.1.233
# Enter password: 149246116
```

---

## 🔴🟢 GPIO Pins Configuration

### Main Actuators
| GPIO | Physical Pin | Function | Status |
|------|--------------|----------|--------|
| **17** | 11 | Pump PWM | OUTPUT |
| **19** | 35 | Pump Relay | OUTPUT |
| **18** | 12 | LED PWM | OUTPUT |
| **13** | 33 | LED Relay | OUTPUT |

### Motor Pins (6 Trays - Harvest Belt)
| Tray | PWM | Direction | Home Sensor | End Sensor |
|------|-----|-----------|-------------|-----------|
| 1 | GPIO 2 | GPIO 3 | GPIO 17 | GPIO 27 |
| 2 | GPIO 9 | GPIO 11 | GPIO 5 | GPIO 6 |
| 3 | GPIO 10 | GPIO 22 | GPIO 23 | GPIO 24 |
| 4 | GPIO 14 | GPIO 15 | GPIO 18 | GPIO 25 |
| 5 | GPIO 8 | GPIO 7 | GPIO 1 | GPIO 12 |
| 6 | GPIO 16 | GPIO 20 | GPIO 21 | GPIO 26 |

---

## 📊 Check GPIO Current State

### Method 1: Check Firestore (Most Reliable)

The app stores GPIO state in Firestore. Check in your Firebase console under:
```
Collection: devices
Document: <your hardware_serial>
Field: gpioState
```

Each pin entry shows:
```json
"gpioState": {
  "17": {
    "state": true/false,
    "name": "Pump PWM",
    "pin": 17
  },
  "18": {
    "state": true/false,
    "name": "LED PWM", 
    "pin": 18
  }
  // ... more pins
}
```

### Method 2: Check GPIO Via SSH Commands

Once SSH'd into the Pi:

**View all GPIO states (requires gpiozero or manual script):**
```bash
# Check if GPIO utilities are installed
which pinctrl  # For older Pi OS

# Or use Python to check pin states
cd /home/monkphx/harvestpilot-raspserver
python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
pins = [17, 19, 18, 13, 2, 3, 9, 11, 10, 22, 14, 15, 8, 7, 16, 20]
for pin in pins:
    GPIO.setup(pin, GPIO.IN)
    state = GPIO.input(pin)
    print(f'GPIO{pin}: {\"HIGH\" if state else \"LOW\"}')</)
"
```

**Check specific pin state:**
```bash
# Check GPIO 17 (Pump PWM)
python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.IN)
print('GPIO17:', 'ON (HIGH)' if GPIO.input(17) else 'OFF (LOW)')
"
```

### Method 3: Monitor Real-Time GPIO Activity

**View application logs:**
```bash
# Watch logs in real-time
tail -f /home/monkphx/harvestpilot-raspserver/logs/raspserver.log | grep -i "gpio"

# Or specific pin
tail -f /home/monkphx/harvestpilot-raspserver/logs/raspserver.log | grep "GPIO17"
```

**Check which pins are currently initialized:**
```bash
cd /home/monkphx/harvestpilot-raspserver
python3 -c "
from src.services.gpio_actuator_controller import GPIOActuatorController
controller = GPIOActuatorController()
states = controller.get_pin_states()
for pin, info in sorted(states.items()):
    print(f'GPIO{pin}: Mode={info[\"mode\"]}, State={info[\"state\"]}')" 
```

---

## 🎯 Quick Commands

### SSH Into Pi
```powershell
ssh monkphx@192.168.1.233
```

### Start the Harvest Server
```bash
cd /home/monkphx/harvestpilot-raspserver
python3 main.py
```

### View Recent Logs
```bash
tail -100 /home/monkphx/harvestpilot-raspserver/logs/raspserver.log
```

### Check Hardware Serial (Device ID)
```bash
cat /proc/cpuinfo | grep Serial
```

### Test Specific Pin (GPIO 17 - Pump)
```bash
# Turn ON
python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.OUT)
GPIO.output(17, GPIO.HIGH)
print('GPIO17 set to HIGH (ON)')
"

# Turn OFF
python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(17, GPIO.OUT)
GPIO.output(17, GPIO.LOW)
print('GPIO17 set to LOW (OFF)')
"
```

### Run Full GPIO Test Suite
```bash
cd /home/monkphx/harvestpilot-raspserver
sudo python3 src/scripts/test_gpio_pins.py
```

### Check Service Status
```bash
ps aux | grep main.py
sudo systemctl status harvestpilot-raspserver
```

---

## 📍 GPIO Pin Layout (Physical vs BCM)

```
Raspberry Pi 4 GPIO Header (40-pin)

    ╔═══════════════════════════╗
  1 ║ 3.3V      GND         PIN 2║  5V
  3 ║ GPIO2 (I2C)      5V   PIN 4║
  5 ║ GPIO3 (I2C)      GND  PIN 6║
  7 ║ GPIO4            GPIO17 PIN11║ ✓ (Pump PWM)
  9 ║ GND         GPIO27     PIN13║
 11 ║ GPIO17      GPIO22     PIN15║
 12 ║ GPIO18 ✓    GND        PIN14║ (LED PWM)
 13 ║ GPIO27      GPIO23     PIN16║
 15 ║ GND         GPIO24     PIN18║
 17 ║ GPIO22      GPIO25     PIN19║
 19 ║ GPIO10      GND        PIN20║
 21 ║ GPIO9       GPIO11     PIN23║
 23 ║ GPIO11      GPIO8      PIN24║
 25 ║ GND         GPIO7      PIN25║
 27 ║ GPIO4       GPIO5      PIN29║
 29 ║ GPIO5       GND        PIN30║
 31 ║ GPIO6       GPIO12     PIN32║
 33 ║ GPIO13      GPIO19 ✓   PIN35║ (Pump Relay)
 35 ║ GPIO19      GPIO26     PIN37║
 37 ║ GPIO26      GPIO20     PIN38║
 39 ║ GND         GPIO21     PIN40║

✓ = Key pins for main actuators
```

---

## ⚠️ Security Note

The SSH credentials are currently hardcoded in `initialize-all-gpio.ps1`. Consider:
1. Using SSH keys instead of passwords
2. Moving credentials to environment variables
3. Using a `.env` file (gitignored)
4. Changing the Pi password

---

## 🔧 Troubleshooting GPIO Issues

### Permission Denied Errors
```bash
# Many GPIO operations need root
sudo python3 script.py

# Or add user to gpio group (requires reboot)
sudo usermod -aG gpio monkphx
```

### GPIO Already in Use
```bash
# Kill stuck GPIO processes
ps aux | grep python3
sudo kill -9 <PID>
sudo python3 src/scripts/test_gpio_pins.py  # Reset GPIO
```

### Check if GPIO is Available
```bash
# On Raspberry Pi
ls /sys/class/gpio/
# Should show gpio0, gpio1, etc.
```

---

## 📝 Log File Location

```bash
/home/monkphx/harvestpilot-raspserver/logs/raspserver.log

# View with filter
tail -f logs/raspserver.log | grep "GPIO\|state\|pin"
```

---

## 🎯 Which Pins are ON/OFF - Best Method

**Firestore is the source of truth:**

1. Open Firebase Console
2. Go to `devices` collection
3. Find your device by hardware serial (shown in logs)
4. Expand `gpioState` field
5. Each pin shows `"state": true` (ON) or `"state": false` (OFF)

**From command line after SSH:**

```bash
# Quick check via Python
python3 << 'EOF'
import firebase_admin
from firebase_admin import credentials, firestore
from src import config

cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

doc = db.collection('devices').document(config.HARDWARE_SERIAL).get()
gpio_state = doc.to_dict().get('gpioState', {})

print("\n🔌 GPIO Pin States:")
print("="*50)
for pin_str, pin_data in sorted(gpio_state.items()):
    if isinstance(pin_data, dict):
        state = "🟢 ON " if pin_data.get('state') else "⚫ OFF"
        name = pin_data.get('name', 'Unknown')
        print(f"GPIO{pin_str:2s}: {state} - {name}")
print("="*50)
EOF
```

This will show you exactly which pins are ON (HIGH) and OFF (LOW).
