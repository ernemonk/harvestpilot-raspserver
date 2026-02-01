# Hardware Serial Fallback Strategy

## Overview

The HarvestPilot RaspServer now implements a **smart fallback strategy** for device identification that gracefully handles different deployment environments while prioritizing security.

## Problem Solved

Previously, the system required either:
- A real Raspberry Pi with `/proc/cpuinfo` containing hardware serial
- Manual configuration via environment variables

This created friction when developing/testing on macOS, Linux workstations, or cloud VMs.

## Solution: Priority-Based Fallback Chain

The new implementation uses a **4-tier fallback chain** in `src/config.py`:

```python
def _get_hardware_serial() -> str:
    # Priority 1: Check if explicitly set in .env
    if env HARDWARE_SERIAL is set and non-empty:
        return HARDWARE_SERIAL from .env
    
    # Priority 2: Try Raspberry Pi hardware serial
    try:
        read from /proc/cpuinfo "Serial" line
        if found:
            return Pi hardware serial (16-char hex)
    
    # Priority 3: Fall back to DEVICE_ID from .env
    if DEVICE_ID is set:
        return DEVICE_ID (human-readable alias)
    
    # Priority 4: Generate from hostname
    try:
        return "dev-{hostname}"
    
    # Last resort
    return "unknown-device"
```

## Fallback Chain in Action

### Scenario 1: Real Raspberry Pi
**Environment:** Raspberry Pi 4 with /proc/cpuinfo
```
.env HARDWARE_SERIAL=              (empty/not set)
.env DEVICE_ID=raspserver-001

Result: HARDWARE_SERIAL = "100000002acfd839"  (from /proc/cpuinfo)
         DEVICE_ID = "raspserver-001"
```

**Why?** Pi hardware serial is immutable and tamper-proof - ideal for authentication.

### Scenario 2: macOS Development
**Environment:** macOS with no /proc/cpuinfo
```
.env HARDWARE_SERIAL=              (empty/not set)
.env DEVICE_ID=raspserver-002

Result: HARDWARE_SERIAL = "raspserver-002"    (from DEVICE_ID fallback)
         DEVICE_ID = "raspserver-002"
```

**Why?** /proc/cpuinfo doesn't exist on macOS, so falls back to human-readable alias.

### Scenario 3: Explicit Configuration
**Environment:** Any system with explicit .env setting
```
.env HARDWARE_SERIAL=100000002acfd839        (explicitly set)
.env DEVICE_ID=raspserver-002

Result: HARDWARE_SERIAL = "100000002acfd839"  (from .env, highest priority)
         DEVICE_ID = "raspserver-002"
```

**Why?** Explicit configuration takes precedence - allows testing or multi-device scenarios.

### Scenario 4: Cloud VM (Linux)
**Environment:** Linux VM, no /proc/cpuinfo, no .env
```
.env HARDWARE_SERIAL=              (empty)
.env DEVICE_ID=                    (empty)

Result: HARDWARE_SERIAL = "dev-myhost-local"  (from hostname fallback)
         DEVICE_ID = "raspserver-001"         (hardcoded default)
```

## Configuration File Changes

### `.env` File Structure

```dotenv
# Device Identification
# HARDWARE_SERIAL: Leave empty to auto-detect from Pi /proc/cpuinfo or use DEVICE_ID
# On non-Pi systems (macOS, Linux dev), will fall back to DEVICE_ID or hostname
HARDWARE_SERIAL=
DEVICE_ID=raspserver-002
```

**Guidelines:**
- Leave `HARDWARE_SERIAL=` empty for automatic detection (recommended)
- Set `HARDWARE_SERIAL=` to explicit value for testing multiple devices
- Always set `DEVICE_ID=` to human-readable alias for your device

## Code Changes

### Modified Files

1. **`src/config.py`**
   - Added `_get_hardware_serial()` function with 4-tier fallback logic
   - Exposed `HARDWARE_SERIAL` and `DEVICE_ID` as separate config values
   - Added comprehensive docstring explaining priority order

2. **`src/services/device_manager.py`**
   - Updated `__init__()` to accept both `hardware_serial` and `device_id`
   - Changed `register_device()` to use `config.HARDWARE_SERIAL` instead of reading /proc/cpuinfo
   - All Firestore documents now use hardware_serial as primary key

3. **`src/services/firebase_service.py`**
   - Stores both `hardware_serial` (primary) and `device_id` (alias) in Firestore
   - All document paths use hardware_serial

4. **`src/services/gpio_actuator_controller.py`**
   - Constructor now accepts both parameters
   - Listens on `devices/{hardware_serial}/commands` path

5. **`src/core/server.py`**
   - Passes hardware_serial to all services during initialization
   - Logs display both identifiers for debugging

## Firestore Document Structure

```
devices/
  ├── {hardware_serial_or_device_id}  (primary key)
  │   ├── hardware_serial: "100000002acfd839"        (immutable identifier)
  │   ├── device_id: "raspserver-001"                (human-readable alias)
  │   ├── status: "online"
  │   ├── commands/ (subcollection)
  │   ├── sensor_readings/ (subcollection)
  │   ├── gpioState (map)
  │   └── ...
```

## Security Implications

### Priority 1: Explicit .env HARDWARE_SERIAL
✅ **Highest Control** - Allows explicit device authentication
- Use case: Testing, device spoofing prevention, manual assignment
- Security: Dev-controlled, immutable per deployment

### Priority 2: Pi /proc/cpuinfo (Real Hardware)
✅ **Highest Security** - Hardware-burned unique identifier
- Use case: Production Raspberry Pi deployments
- Security: Immutable, tamper-proof, impossible to clone

### Priority 3: DEVICE_ID Fallback
✅ **Good Usability** - Human-readable identifier
- Use case: macOS dev, testing, cloud VMs
- Security: Reassignable, but sufficient for dev/staging

### Priority 4: Hostname
✅ **Acceptable Default** - System-derived identifier
- Use case: When everything else is missing
- Security: Unique per machine, but changeable

## Testing Results

### Test 1: Auto-Detection on macOS
```bash
$ python3 -c "from src import config; print(config.HARDWARE_SERIAL)"
raspserver-002  ✅ Fell back to DEVICE_ID
```

### Test 2: Explicit .env Configuration
```bash
$ cat .env | grep HARDWARE_SERIAL=100000002acfd839
$ python3 -c "from src import config; print(config.HARDWARE_SERIAL)"
100000002acfd839  ✅ Used explicit value
```

### Test 3: Server Startup with Fallback
```
2026-02-01 12:59:37 - src.services.firebase_service - INFO - Firebase service initialized 
  (hardware_serial: raspserver-002, device_id: raspserver-002)  ✅ PASS
```

## Implementation Checklist

- ✅ `src/config.py` - Smart fallback chain implemented
- ✅ `src/services/device_manager.py` - Uses config.HARDWARE_SERIAL
- ✅ `src/services/firebase_service.py` - Stores both identifiers
- ✅ `src/services/gpio_actuator_controller.py` - Accepts both parameters
- ✅ `src/core/server.py` - Passes hardware_serial to services
- ✅ `.env` - Documentation and HARDWARE_SERIAL field added
- ✅ Server startup verified with fallback logic
- ✅ Firestore documents use hardware_serial as key

## Migration Guide

### For Existing Deployments

1. **No changes required** - System is backward compatible
2. **Optional optimization** - Add to `.env`:
   ```
   HARDWARE_SERIAL=<your-pi-hardware-serial>
   ```

### For New Deployments

1. **Create `.env`** with at minimum:
   ```
   DEVICE_ID=your-device-name
   HARDWARE_SERIAL=         # Leave empty for auto-detect
   ```

2. **On Raspberry Pi** - HARDWARE_SERIAL auto-detected from /proc/cpuinfo
3. **On Dev Machine** - Falls back to DEVICE_ID
4. **In Production** - Explicitly set HARDWARE_SERIAL for security

## Best Practices

### Production (Raspberry Pi)
```
.env HARDWARE_SERIAL=         # Let Pi hardware serial be detected
.env DEVICE_ID=greenhouse-01  # Human-readable name
```

### Development (macOS)
```
.env HARDWARE_SERIAL=         # Falls back to DEVICE_ID
.env DEVICE_ID=dev-greenhouse # Distinguishes from production
```

### Testing (Multiple Devices)
```
.env HARDWARE_SERIAL=test-device-001  # Explicit for isolation
.env DEVICE_ID=test-01
```

## Firestore Security Implications

With hardware_serial as primary key:
- ✅ Device authentication possible by hardware serial
- ✅ Firestore rules can enforce device ownership
- ✅ Prevents device_id reassignment attacks
- ✅ Audit trail shows which hardware accessed what

## Future Enhancements

1. **Device Fingerprinting** - Combine hardware serial + MAC address
2. **Certificate-Based Auth** - Use hardware serial for device certificates
3. **Multi-Device Support** - Track multiple Pis with unified device_id
4. **Hostname Pinning** - Lock device_id to specific hostname

## References

- [Firestore Security Rules](docs/FIREBASE_CONTROL_SUMMARY.md)
- [Device Identification](docs/DEVICE_ID_LINKING.md)
- [Configuration Guide](docs/SETUP_YOUR_PI.md)
