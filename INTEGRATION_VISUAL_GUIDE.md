# Visual Integration Guide

## 🎯 What You Need to Do (2 Minutes)

Open: `harvestpilot-raspserver/main.py` (or `src/core/rasp_server.py`)

### 1️⃣ Add Imports (Top of file)

```python
from src.services.firebase_listener import FirebaseDeviceListener
from src.services.device_manager import DeviceManager
```

### 2️⃣ Add to `__init__` Method

Find where controllers are created, add AFTER them:

```python
def __init__(self):
    # ... your existing code ...
    # (irrigation_controller, lighting_controller, etc.)
    
    # ← ADD HERE: NEW CODE BELOW
    
    # Device manager for registration & telemetry
    self.device_manager = DeviceManager(device_id=config.DEVICE_ID)
    
    # Firebase listener for real-time commands
    self.firebase_listener = FirebaseDeviceListener(
        device_id=config.DEVICE_ID,
        gpio_controller=self.gpio_manager,
        controllers_map={
            "pump": self.irrigation_controller,
            "lights": self.lighting_controller,
            "harvest": self.harvest_controller,
            "sensors": self.sensor_controller,
        }
    )
```

### 3️⃣ Add to `start()` Method

Find the `async def start(self):`, add AFTER setup code:

```python
async def start(self):
    # ... your existing startup code ...
    
    # ← ADD HERE: NEW CODE BELOW
    
    # Register device and start Firebase listeners
    await self.device_manager.register_device()
    await self.firebase_listener.start_listening()
    
    # ... rest of your code ...
```

### 4️⃣ Restart Service

```bash
sudo systemctl restart harvestpilot-raspserver
```

### 5️⃣ Verify

```bash
sudo journalctl -u harvestpilot-raspserver -n 20
```

Look for:
```
Device registered successfully: hp-XXXXXXXX
Firebase listeners started for device: hp-XXXXXXXX
```

---

## 🔄 Life Cycle

```
┌─ Service Starts ─┐
│                  │
│ RaspServer()     │ ← __init__() called
│   ├─ Controllers │    - Creates pump, lights, belts, sensors
│   ├─ GPIO Manager│    - Creates gpio manager
│   ├─ Device Mgr  │    - NEW: Creates device manager
│   └─ Listener    │    - NEW: Creates Firebase listener
│                  │
│ .start()         │ ← Async startup begins
│   ├─ Setup GPIO  │
│   ├─ Connect FB  │
│   │              │
│   ├─ Register Dv │ ← NEW: Device registers in Firebase
│   ├─ Listen FB   │ ← NEW: Start listening for commands
│   │              │
│   ├─ Read Sensors│    Updates telemetry
│   ├─ Run Logic   │    Main loop
│   └─ Loop...     │    Waits for commands
│                  │
│ (Firebase Cloud) │
│   ├─ Command In  │ ← User sends command
│   ├─ Response    │ ← Listener sends response
│   └─ Telemetry   │ ← Device publishes data
│                  │
└──────────────────┘
```

---

## 📱 How Commands Flow

```
┌─────────────────────────┐
│  Firebase Console       │
│  (or Webapp)            │
└────────────┬────────────┘
             │ Write command
             ▼
┌────────────────────────────────────┐
│ Firebase Realtime Database         │
│ /devices/hp-XXXXXXXX/commands/     │
│                                    │
│ cmd-001: {                         │
│   "type": "pump",                  │
│   "action": "start",               │
│   "speed": 80                      │
│ }                                  │
└────────────┬───────────────────────┘
             │ Listener detects
             ▼
┌────────────────────────────────────┐
│  Raspberry Pi (RaspServer)         │
│                                    │
│  FirebaseDeviceListener            │
│   ├─ Detects: type=pump            │
│   ├─ Routes to handler             │
│   │                                │
│   └─ _handle_pump_command()        │
│       ├─ Gets controller           │
│       ├─ Calls: pump.start(80)     │
│       └─ Gets result               │
│                                    │
│  IrrigationController              │
│   └─ start(speed=80)               │
│       └─ GPIO PWM → Pump           │
│                                    │
└────────────┬───────────────────────┘
             │ Send response
             ▼
┌────────────────────────────────────┐
│ Firebase Realtime Database         │
│ /devices/hp-XXXXXXXX/responses/    │
│                                    │
│ cmd-001: {                         │
│   "status": "success",             │
│   "data": {                        │
│     "action": "start",             │
│     "speed": 80,                   │
│     "status": "running"            │
│   },                               │
│   "timestamp": "2026-01-25T..."    │
│ }                                  │
└────────────┬───────────────────────┘
             │ Read response
             ▼
┌─────────────────────────┐
│  Firebase Console       │
│  Shows response ✅      │
│                        │
│  Pump is RUNNING       │
└─────────────────────────┘
```

---

## 📊 All Commands at a Glance

### Send These Commands to Firebase

**Pump:**
```json
{"type": "pump", "action": "start", "speed": 80}
{"type": "pump", "action": "stop"}
{"type": "pump", "action": "pulse", "speed": 50, "duration": 10}
```

**Lights:**
```json
{"type": "lights", "action": "on", "brightness": 100}
{"type": "lights", "action": "on", "brightness": 50}
{"type": "lights", "action": "off"}
```

**GPIO:**
```json
{"type": "pin_control", "pin": 17, "action": "on"}
{"type": "pin_control", "pin": 17, "action": "off"}
{"type": "pin_control", "pin": 17, "action": "on", "duration": 5}
```

**PWM (Analog):**
```json
{"type": "pwm_control", "pin": 17, "duty_cycle": 75}
{"type": "pwm_control", "pin": 18, "duty_cycle": 50}
```

**Harvest Belt:**
```json
{"type": "harvest", "action": "start", "belt_id": 1, "speed": 50}
{"type": "harvest", "action": "stop", "belt_id": 1}
{"type": "harvest", "action": "position", "belt_id": 1, "position": "home"}
```

**Sensor:**
```json
{"type": "sensor_read", "sensor": "temperature"}
{"type": "sensor_read", "sensor": "humidity"}
{"type": "sensor_read", "sensor": "soil_moisture"}
{"type": "sensor_read", "sensor": "water_level"}
```

---

## ✅ Verification Steps

After updating main.py:

```
Step 1: Restart service
  $ sudo systemctl restart harvestpilot-raspserver
  
Step 2: Check logs
  $ sudo journalctl -u harvestpilot-raspserver -n 20
  
  Should see:
  ✓ Device registered successfully: hp-XXXXXXXX
  ✓ Firebase listeners started for device: hp-XXXXXXXX
  
Step 3: Test pump command
  - Open Firebase Console
  - Go to: /devices/hp-XXXXXXXX/commands/
  - Add: cmd-001 = {"type": "pump", "action": "start", "speed": 80}
  - Watch Pi logs
  - Check: /devices/hp-XXXXXXXX/responses/cmd-001/
  
  Should see response within 1 second ✓
  
Step 4: Verify hardware
  - Pump should start spinning
  - Listen for GPIO change
  - Check telemetry: /devices/hp-XXXXXXXX/telemetry/
```

---

## 🆘 Troubleshooting

| Problem | Solution |
|---------|----------|
| Service won't start | Check syntax error in main.py, check imports exist |
| Device not registering | Check Firebase credentials, check service logs |
| Commands not executing | Verify device_id format (hp-XXXXXXXX), check logs |
| No response | Check device status is "online", check Firebase path |
| GPIO not working | Verify pin number, test manually, check permissions |

---

## 📂 File Locations

**Add imports to:**
```
harvestpilot-raspserver/main.py
  OR
harvestpilot-raspserver/src/core/rasp_server.py
```

**New services are in:**
```
harvestpilot-raspserver/services/
  ├── firebase_listener.py
  ├── device_manager.py
  └── __init__.py
```

**Documentation:**
```
harvestpilot-raspserver/docs/
  ├── FIREBASE_CONTROL_INTEGRATION.md
  ├── FIREBASE_CONTROL_QUICKREF.md
  └── FIREBASE_IMPLEMENTATION_COMPLETE.md
```

**Current analysis:**
```
harvestpilot-raspserver/
  ├── FIREBASE_CONTROL_SUMMARY.md
  └── CODE_STRUCTURE_ANALYSIS.md
```

---

## 🎯 Goal

After these 3 steps:

✅ Device registers automatically in Firebase  
✅ Commands execute in real-time  
✅ Responses appear instantly  
✅ No SSH needed for control  
✅ Control from webapp, mobile, console  

**Total time: 5 minutes** ⏱️

---

## 🚀 You're Ready!

1. Open main.py
2. Add 2 imports
3. Add 8 lines to __init__
4. Add 2 lines to start()
5. Restart service
6. Done! 🎉

See detailed guide: [FIREBASE_CONTROL_INTEGRATION.md](./docs/FIREBASE_CONTROL_INTEGRATION.md)
