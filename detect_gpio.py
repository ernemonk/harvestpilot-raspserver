"""Detect all GPIO pins available on this Raspberry Pi hardware."""
import json
try:
    import RPi.GPIO as GPIO
except ImportError:
    print("RPi.GPIO not available - not running on a Raspberry Pi")
    exit(1)

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Pi hardware info
info = GPIO.RPI_INFO
print("=== RASPBERRY PI HARDWARE ===")
print(f"  Type: {info.get('TYPE', 'unknown')}")
print(f"  Revision: {info.get('REVISION', 'unknown')}")
print(f"  RAM: {info.get('RAM', 'unknown')}MB")
print(f"  Processor: {info.get('PROCESSOR', 'unknown')}")
print(f"  Manufacturer: {info.get('MANUFACTURER', 'unknown')}")
print(f"  P1 Header Revision: {info.get('P1_REVISION', 'unknown')}")
print()

# All usable BCM GPIO pins on the 40-pin header
ALL_BCM = [2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27]

MODE_NAMES = {
    0: 'OUTPUT',
    1: 'INPUT', 
    40: 'SERIAL',
    41: 'SPI',
    42: 'I2C',
    43: 'HARD_PWM',
    -1: 'UNKNOWN'
}

in_use = []
free = []
reserved = []

for pin in ALL_BCM:
    try:
        mode = GPIO.gpio_function(pin)
        mode_name = MODE_NAMES.get(mode, f'ALT({mode})')
        
        if mode in (0, 1):  # OUTPUT or INPUT = GPIO configured
            in_use.append((pin, mode_name))
        elif mode in (40, 41, 42, 43):  # Bus protocols
            reserved.append((pin, mode_name))
        else:
            free.append(pin)
    except Exception as e:
        free.append(pin)

print(f"=== GPIO PINS IN USE ({len(in_use)}) ===")
for pin, mode in in_use:
    print(f"  GPIO{pin}: {mode}")

print(f"\n=== RESERVED FOR BUS ({len(reserved)}) ===")
for pin, mode in reserved:
    print(f"  GPIO{pin}: {mode}")

print(f"\n=== FREE/AVAILABLE ({len(free)}) ===")
print(f"  {free}")

print(f"\n=== SUMMARY ===")
print(f"  Total GPIO: {len(ALL_BCM)}")
print(f"  In use: {len(in_use)}")
print(f"  Reserved: {len(reserved)}")
print(f"  Free: {len(free)}")

# Output as JSON for programmatic use
result = {
    "hardware": dict(info),
    "all_bcm_pins": ALL_BCM,
    "in_use": [{"pin": p, "mode": m} for p, m in in_use],
    "reserved": [{"pin": p, "mode": m} for p, m in reserved],  
    "free": free
}
print(f"\n=== JSON ===")
print(json.dumps(result, indent=2))

GPIO.cleanup()
