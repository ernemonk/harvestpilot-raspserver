# Why Sensors Are Running Without Firestore Configuration

## Executive Summary

**The Problem:** You're seeing DHT22 and water level sensors running even though you haven't configured them in Firestore per-device. This is by design - it's a **hardcoded fallback system**.

---

## The Architecture

### Flow Diagram
```
Server Startup
    ↓
    ├─→ SensorController.__init__()
    │   (no sensors loaded yet)
    │
    ├─→ Firebase connects
    │   ↓
    │   Firestore DB passed to SensorController
    │
    └─→ First sensor read() call
        ├─→ _get_configured_sensors()
        │   ├─→ Try to read from Firestore: devices/{hardware_serial}/gpioState/
        │   │   ✓ Found? Use them
        │   │   ✗ Not found? 
        │   │       ↓
        │   │   ✗ Fall back to _get_default_sensors()
        │   │
        │   └─→ _get_default_sensors() 
        │       └─→ Return hardcoded defaults:
        │           - temperature_humidity → DHT22 on pin 4
        │           - water_level → GPIO 23
        │
        └─→ Sensor loop runs forever with defaults
```

---

## Code Breakdown

### 1. Default Sensors (FALLBACK)
**File:** `src/controllers/sensors.py` lines 76-78

```python
def _get_default_sensors(self):
    """Fallback default sensors"""
    return {
        'temperature_humidity': {'pin': config.SENSOR_DHT22_PIN, 'function': 'temperature_humidity'},
        'water_level': {'pin': config.SENSOR_WATER_LEVEL_PIN, 'function': 'water_level'}
    }
```

**Where these pins come from:** `config.py`
```python
SENSOR_DHT22_PIN = 4
SENSOR_WATER_LEVEL_PIN = 23
```

### 2. Configured Sensors (FIRESTORE)
**File:** `src/controllers/sensors.py` lines 42-61

```python
def _get_configured_sensors(self):
    """Fetch input sensors from device document's gpioState"""
    try:
        if not self.firestore_db:
            logger.warning("No Firestore DB - using default sensors")
            return self._get_default_sensors()  # ← FALLBACK
        
        device_doc = self.firestore_db.collection('devices').document(
            self.hardware_serial  # Uses Pi's hardware serial as key
        ).get()
        
        if not device_doc.exists:
            logger.warning(f"Device {self.hardware_serial} not in Firestore - using defaults")
            return self._get_default_sensors()  # ← FALLBACK
        
        device_data = device_doc.to_dict()
        gpio_state = device_data.get('gpioState', {})  # ← Looks for gpioState
        
        # Extract input sensors from gpioState
        sensors = {}
        for pin_str, pin_config in gpio_state.items():
            if pin_config.get('mode') == 'input':  # ← Only input sensors
                sensors[function] = {...}
        
        if sensors:
            return sensors  # ← FOUND! Use them
        else:
            return self._get_default_sensors()  # ← FALLBACK if empty
```

### 3. Where Sensors Are Used
**File:** `src/core/server.py` line 157-200

```python
async def _sensor_reading_loop(self):
    """Continuously read sensors"""
    while self.running:
        reading = await self.sensors.read_all()  # ← This calls read_all()
        
        # read_all() internally calls:
        # 1. _get_configured_sensors() (first time)
        # 2. For each sensor, calls the read method
        # 3. Publishes to Firebase
```

---

## The Firestore Structure (EXPECTED)

When you set up a device in Firestore, it should look like this:

```json
{
  "devices": {
    "100000002acfd839": {
      "hardware_serial": "100000002acfd839",
      "deviceId": "raspserver-001",
      "status": "online",
      "gpioState": {
        "4": {
          "function": "temperature_humidity",
          "mode": "input",
          "pin": 4
        },
        "23": {
          "function": "water_level",
          "mode": "input",
          "pin": 23
        }
      }
    }
  }
}
```

**Current Status:** This document exists (from `server_init.py` registration) but the `gpioState` section has the SAME pins as the defaults. So you're getting the same sensors either way.

---

## Why This Happens (Initialization Order)

### Step 1: `server_init.py` Creates Default Device Document
**File:** `src/scripts/server_init.py` lines 180-202

```python
def register_in_firestore(self) -> bool:
    device_data = {
        # ... other fields ...
        "gpioState": {
            "17": {"function": "light", "mode": "output", ...},
            "18": {"function": "pump", "mode": "output", ...},
            "dht22": {
                "function": "temperature_humidity",
                "mode": "input",
                "pin": 4
            },
            "water_level": {
                "function": "water_level",
                "mode": "input",
                "pin": 23
            }
        }
    }
    # Writes to Firestore
    self.firestore.collection('devices').document(doc_id).set(device_data, merge=True)
```

**Result:** Device is registered with HARDCODED defaults including DHT22 + water_level

### Step 2: Main Service Starts
```python
# main.py
def initialize_device():
    # Runs server_init.py ← Creates device with default sensors
    
async def main():
    server = RaspServer()
    await server.start()
    # ← Sensor service initialized
    # ← First sensor read happens
    # ← Calls _get_configured_sensors()
    # ← Reads from Firestore (finds the defaults from step 1!)
```

**Result:** Sensor loop uses Firestore defaults instead of code defaults, but they're identical!

---

## The Problem: CIRCULAR INITIALIZATION

```
server_init.py creates device doc with sensors
    ↓
main.py reads those sensors from Firestore
    ↓
But init script hardcoded the sensors anyway!
    ↓
So you get sensors even if you wanted none or different ones
```

---

## Why This Design Exists

### Good Reasons:
1. **Safety First** - Device has sensible defaults on first boot
2. **No Blank State** - Service doesn't crash if Firestore is empty
3. **Automatic Registration** - Device self-registers on startup

### Bad Reasons:
1. **No User Control** - You can't disable sensors from Firestore
2. **Double Definition** - Sensors defined in TWO places (config.py + server_init.py)
3. **Confusion** - Makes it unclear where sensors actually come from
4. **Can't Disable** - Even if you remove from Firestore, defaults kick in

---

## Where Sensors Are Defined (The Mess)

### 1. **config.py** - Hardcoded pins
```python
SENSOR_DHT22_PIN = 4
SENSOR_WATER_LEVEL_PIN = 23
```

### 2. **server_init.py** - Hardcoded in registration
```python
"dht22": {"function": "temperature_humidity", "mode": "input", "pin": 4},
"water_level": {"function": "water_level", "mode": "input", "pin": 23}
```

### 3. **sensors.py** - Fallback defaults (same as above!)
```python
def _get_default_sensors(self):
    return {
        'temperature_humidity': {'pin': config.SENSOR_DHT22_PIN, ...},
        'water_level': {'pin': config.SENSOR_WATER_LEVEL_PIN, ...}
    }
```

### 4. **Firestore** - What *should* be the source of truth
```json
{
  "gpioState": {
    "4": {"function": "temperature_humidity", ...},
    "23": {"function": "water_level", ...}
  }
}
```

**Result:** 4 places defining the same sensors! 🤦

---

## The Real Issue

**Your Frustration:** "Why are sensors running if I didn't set them up?"

**The Answer:** They're hardcoded at 3 levels:
1. System startup creates them in Firestore automatically
2. Code has fallback defaults that match
3. Sensor controller reads them from Firestore (which has the init defaults)

**You CAN'T disable them without editing code** because:
- `config.py` has the pins
- `server_init.py` registers them
- `sensors.py` falls back to them

---

## How It Should Work (IDEAL)

```
User sets gpioState in Firestore for their device
    ↓
server_init.py skips sensor setup (device doc already exists)
    ↓
SensorController reads ONLY from Firestore
    ↓
No hardcoded defaults, pure Firestore config
```

---

## Current Behavior (ACTUAL)

```
server_init.py ALWAYS creates device with default sensors
    ↓
SensorController tries Firestore
    ↓
Finds sensors (that init.py just created!)
    ↓
Runs with those sensors
    ↓
Even if you change Firestore later, you need to restart service
    ↓
OR remove hardware to disable sensors
```

---

## What Needs to Change

### Option 1: Pure Firestore Control (RECOMMENDED)
**Remove from:**
- `server_init.py` - Don't register sensors, let user do it
- `sensors.py` - Remove fallback defaults
- `config.py` - Remove SENSOR_* constants

**Result:** Empty service waits for user to configure in Firestore

### Option 2: Smart Fallback (MEDIUM)
**Keep defaults but:**
- Only use if device doc doesn't exist in Firestore
- Allow Firestore to override
- Don't re-register sensors on every startup

### Option 3: Code-Based Only (CURRENT)
**Keep it simple:**
- Use `config.py` and `sensors.py` defaults
- Don't sync to Firestore at all
- Accept that sensors are always DHT22 + water level

---

## Summary

**Why sensors are running without Firestore config:**

1. ✅ `server_init.py` auto-registers device with default sensors
2. ✅ `SensorController` reads from Firestore (finds those defaults)
3. ✅ `config.py` has hardcoded fallback pins
4. ✅ Sensor loop runs forever with these sensors

**You need to pick ONE place as source of truth instead of THREE.**

Currently, Firestore *appears* to control it but actually `server_init.py` is pre-populating it with hardcoded values, making Firestore control an illusion.

