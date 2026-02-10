#!/usr/bin/env python3
"""Initialize all GPIO pins to Firestore and test them"""

import sys
sys.path.insert(0, '/home/monkphx/harvestpilot-raspserver')

import firebase_admin
from firebase_admin import credentials, firestore
from src import config
from src.utils.gpio_import import GPIO, GPIO_AVAILABLE
import time

# Initialize Firebase
cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Initialize GPIO hardware
if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    print("[*] GPIO hardware initialized")
else:
    print("[*] GPIO simulation mode")

# All pins to initialize
ALL_PINS = {
    17: "Pump PWM",
    19: "Pump Relay",
    18: "LED PWM",
    13: "LED Relay",
}

# Motor pins
for motor in config.MOTOR_PINS:
    ALL_PINS[motor['pwm']] = f"Motor {motor['tray']} PWM"
    ALL_PINS[motor['dir']] = f"Motor {motor['tray']} Direction"
    ALL_PINS[motor['home']] = f"Motor {motor['tray']} Home"
    ALL_PINS[motor['end']] = f"Motor {motor['tray']} End"

print(f"\n[*] Initializing {len(ALL_PINS)} GPIO pins...")
print(f"[*] Device: {config.HARDWARE_SERIAL}\n")

# Firestore batch update
device_ref = db.collection('devices').document(config.HARDWARE_SERIAL)

gpio_updates = {}

for pin, description in sorted(ALL_PINS.items()):
    try:
        # Setup pin as output
        if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
            print(f"[+] GPIO{pin:2d} ({description:20s}) - Setup as OUTPUT, set to LOW")
        else:
            print(f"[+] GPIO{pin:2d} ({description:20s}) - [SIM] Setup as OUTPUT")
        
        # Prepare Firestore update
        gpio_updates[f'gpioState.{pin}.state'] = False
        gpio_updates[f'gpioState.{pin}.pin'] = pin
        gpio_updates[f'gpioState.{pin}.mode'] = 'output'
        gpio_updates[f'gpioState.{pin}.name'] = description
        
    except Exception as e:
        print(f"[!] GPIO{pin} initialization failed: {e}")

# Update Firestore with all pins
try:
    print(f"\n[*] Syncing {len(ALL_PINS)} pins to Firestore...")
    device_ref.update(gpio_updates)
    print(f"[+] All pins synced to Firestore successfully!")
except Exception as e:
    print(f"[!] Firestore update failed: {e}")

# Test each pin
print(f"\n[*] Testing each pin (2 cycles)...\n")
for pin, description in sorted(ALL_PINS.items()):
    try:
        # Test ON
        if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
            GPIO.output(pin, GPIO.HIGH)
            print(f"[→] GPIO{pin:2d} ({description:20s}) - ON  (HIGH)")
        else:
            print(f"[→] GPIO{pin:2d} ({description:20s}) - [SIM] ON  (HIGH)")
        
        device_ref.update({f'gpioState.{pin}.state': True})
        time.sleep(0.5)
        
        # Test OFF
        if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
            GPIO.output(pin, GPIO.LOW)
            print(f"[←] GPIO{pin:2d} ({description:20s}) - OFF (LOW)")
        else:
            print(f"[←] GPIO{pin:2d} ({description:20s}) - [SIM] OFF (LOW)")
        
        device_ref.update({f'gpioState.{pin}.state': False})
        time.sleep(0.5)
        
    except Exception as e:
        print(f"[!] GPIO{pin} test failed: {e}")

# Verify final state
print(f"\n[*] Verifying Firestore state...")
device_doc = device_ref.get()
if device_doc.exists:
    gpio_state = device_doc.to_dict().get('gpioState', {})
    print(f"[+] {len(gpio_state)} GPIO pins in Firestore:")
    for pin_str in sorted(gpio_state.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        pin_data = gpio_state[pin_str]
        state = pin_data.get('state', False)
        mode = pin_data.get('mode', 'unknown')
        name = pin_data.get('name', '')
        print(f"    GPIO{pin_str:2s}: {state!s:5} ({mode}) - {name}")

print(f"\n[✓] GPIO initialization complete!")
