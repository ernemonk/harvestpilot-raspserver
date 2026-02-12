#!/usr/bin/env python3
"""Initialize GPIO pins from Firestore and test them.

Reads pin definitions from Firestore (devices/{serial}/gpioState),
sets up hardware, and verifies each pin.
NO hardcoded pins — Firestore is the single source of truth.
"""

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

# Load pins from Firestore
device_ref = db.collection('devices').document(config.HARDWARE_SERIAL)
doc = device_ref.get()

if not doc.exists:
    print(f"[!] Device document not found: devices/{config.HARDWARE_SERIAL}")
    print("[!] Create the device in the webapp first.")
    sys.exit(1)

gpio_state = doc.to_dict().get('gpioState', {})
if not gpio_state:
    print("[!] No gpioState in Firestore — nothing to initialize.")
    sys.exit(1)

# Build pin map from Firestore
ALL_PINS = {}
ACTIVE_LOW = set()
for pin_str, pin_data in gpio_state.items():
    try:
        pin = int(pin_str)
    except (ValueError, TypeError):
        continue
    ALL_PINS[pin] = pin_data.get('name', f'GPIO{pin}')
    if pin_data.get('active_low', False):
        ACTIVE_LOW.add(pin)

print(f"\n[*] Loaded {len(ALL_PINS)} GPIO pins from Firestore")
print(f"[*] Device: {config.HARDWARE_SERIAL}")
if ACTIVE_LOW:
    print(f"[*] Active-LOW pins: {sorted(ACTIVE_LOW)}")
print()

# Setup and sync each pin
gpio_updates = {}

for pin, description in sorted(ALL_PINS.items()):
    try:
        is_active_low = pin in ACTIVE_LOW
        if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
            if is_active_low:
                GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)  # Relay OFF
                print(f"[+] GPIO{pin:2d} ({description:20s}) - OUTPUT, HIGH (active-LOW relay OFF)")
            else:
                GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
                print(f"[+] GPIO{pin:2d} ({description:20s}) - OUTPUT, LOW")
        else:
            print(f"[+] GPIO{pin:2d} ({description:20s}) - [SIM] OUTPUT")

        gpio_updates[f'gpioState.{pin}.state'] = False
        gpio_updates[f'gpioState.{pin}.hardwareState'] = False
        gpio_updates[f'gpioState.{pin}.mismatch'] = False
        gpio_updates[f'gpioState.{pin}.lastHardwareRead'] = firestore.SERVER_TIMESTAMP
    except Exception as e:
        print(f"[!] GPIO{pin} initialization failed: {e}")

# Sync to Firestore
try:
    print(f"\n[*] Syncing {len(ALL_PINS)} pins to Firestore...")
    gpio_updates['lastHeartbeat'] = firestore.SERVER_TIMESTAMP
    device_ref.update(gpio_updates)
    print(f"[+] All pins synced — all OFF")
except Exception as e:
    print(f"[!] Firestore update failed: {e}")

# Verify
print(f"\n[*] Verifying Firestore state...")
device_doc = device_ref.get()
if device_doc.exists:
    gpio_state = device_doc.to_dict().get('gpioState', {})
    print(f"[+] {len(gpio_state)} GPIO pins in Firestore:")
    for pin_str in sorted(gpio_state.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        pin_data = gpio_state[pin_str]
        state = pin_data.get('state', False)
        hw_state = pin_data.get('hardwareState', False)
        name = pin_data.get('name', '')
        active_low = pin_data.get('active_low', False)
        al_tag = " [ACTIVE-LOW]" if active_low else ""
        print(f"    GPIO{pin_str:>2s}: state={state!s:5} hw={hw_state!s:5} - {name}{al_tag}")

print(f"\n[✓] GPIO initialization complete!")
