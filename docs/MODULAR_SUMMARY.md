# HarvestPilot RaspServer - Modular Architecture Summary

## What Changed?

Your app went from **monolithic** (everything in one `main.py`) to **modular** (organized into logical layers).

---

## The 5-Layer Architecture

```
┌─────────────────────────────────────────────────┐
│ 1. ENTRY POINT (main.py)                        │  ← Starts the app
│    └─ Application bootstrap                     │
└─────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────┐
│ 2. CORE (src/core/server.py)                    │  ← Orchestrates everything
│    └─ RaspServer class                          │
│       - Creates services                        │
│       - Routes commands                         │
│       - Manages loops                           │
└─────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────┐
│ 3. SERVICES (src/services/)                     │  ← Business logic
│    ├─ FirebaseService (cloud sync)              │
│    ├─ SensorService (sensor logic)              │
│    └─ AutomationService (scheduling)            │
└─────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────┐
│ 4. CONTROLLERS (src/controllers/)               │  ← Hardware control
│    ├─ SensorController (read GPIO)              │
│    ├─ IrrigationController (pump)               │
│    ├─ LightingController (LEDs)                 │
│    └─ HarvestController (motors)                │
└─────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────┐
│ 5. HARDWARE (GPIO/PWM)                          │  ← Physical devices
└─────────────────────────────────────────────────┘
```

---

## Quick Comparison

| Aspect | Old | New |
|--------|-----|-----|
| **Files** | 1 big main.py | Organized src/ folder |
| **Logic** | Mixed together | Separated into layers |
| **Testing** | Hard to isolate | Easy to test in isolation |
| **Adding features** | Touch main.py | Add new service/model |
| **Understanding** | One file to learn | Clear layer responsibilities |

---

## Key Improvements

### ✅ **Separation of Concerns**
- Hardware control → Controllers
- Business logic → Services
- Data structures → Models
- Entry point → main.py

### ✅ **Type Safety**
New models with type hints:
```python
@dataclass
class SensorReading:
    temperature: float
    humidity: float
    soil_moisture: float
    water_level: bool
```

### ✅ **Easier Testing**
Test a service without hardware:
```python
sensor_service = SensorService()
alerts = await sensor_service.check_thresholds(reading)
# No GPIO needed!
```

### ✅ **Cleaner Code Flow**
Before (mixed):
```python
# main.py - 300 lines, does everything
```

After (organized):
```python
# main.py - 45 lines, just bootstraps
# src/core/server.py - Orchestration
# src/services/* - Business logic
# src/controllers/* - Hardware control
```

---

## Directory Structure Explained

```
src/
├── core/
│   └── server.py          ← Main orchestrator class (RaspServer)
│                            - Initializes everything
│                            - Runs loops
│                            - Routes commands
│
├── services/
│   ├── firebase_service.py ← Cloud communication
│   ├── sensor_service.py   ← Sensor logic & validation
│   └── automation_service.py ← Scheduled tasks
│
├── controllers/
│   ├── sensors.py          ← Read DHT22, water level, etc
│   ├── irrigation.py       ← Control pump
│   ├── lighting.py         ← Control LEDs
│   └── harvest.py          ← Control harvest motors
│
├── models/
│   ├── sensor_data.py      ← SensorReading, ThresholdAlert
│   └── command.py          ← Command, DeviceStatus
│
└── utils/
    ├── logger.py           ← Logging setup
    └── gpio_manager.py     ← GPIO cleanup
```

---

## Data Flow Example: Sensor Reading

```
1. main.py starts app
   └─ Creates RaspServer()
   
2. RaspServer.start()
   └─ Runs _sensor_reading_loop()
   
3. Loop every 5 seconds
   ├─ SensorService.read_all()
   │  └─ SensorController.read_all()  (reads GPIO)
   │     └─ Returns SensorReading (typed data)
   │
   ├─ SensorService.check_thresholds()
   │  └─ Compares against config values
   │     └─ Returns list of ThresholdAlert
   │
   └─ FirebaseService.publish_sensor_data()
      └─ Sends to Firebase Cloud
```

---

## Command Flow Example: Irrigation Start

```
1. Cloud sends command
   └─ FirebaseService._listen_for_commands()
   
2. Command arrives
   └─ FirebaseService._route_command()
      └─ Calls registered callback
      
3. RaspServer._handle_irrigation_start()
   └─ Calls self.irrigation.start()
   
4. IrrigationController.start()
   └─ Activates GPIO pins (pump runs)
   
5. Status published back to cloud
   └─ FirebaseService.publish_status_update()
```

---

## Adding a New Feature: Easy!

### Old Way (Monolithic)
1. Edit main.py (300+ lines)
2. Add imports
3. Modify RaspServer class
4. Add new loop method
5. Risk breaking existing code

### New Way (Modular)
1. Create new service file
2. Import in RaspServer
3. Instantiate in `__init__`
4. Done!

**Example: Add soil moisture auto-irrigation**

```python
# src/services/soil_service.py
class SoilAutomationService:
    def __init__(self, irrigation, sensor_service):
        self.irrigation = irrigation
        self.sensors = sensor_service
    
    async def auto_irrigate_if_dry(self):
        reading = await self.sensors.read_all()
        if reading.soil_moisture < 50:
            await self.irrigation.start()
```

Register in RaspServer:
```python
self.soil_automation = SoilAutomationService(self.irrigation, self.sensors)
```

That's it! No touching existing code.

---

## Performance & Reliability

### ✅ **Async/Await**
All I/O is non-blocking:
```python
reading = await self.sensors.read_all()  # Doesn't block other tasks
```

### ✅ **Error Isolation**
Errors in one service don't crash others:
```python
try:
    await self.sensors.read_all()
except Exception as e:
    logger.error(f"Sensor error: {e}")
    # Continue running other tasks
```

### ✅ **Graceful Shutdown**
RaspServer.stop() cleanly stops everything:
```python
await self.irrigation.stop()
await self.lighting.turn_off()
cleanup_gpio()
```

---

## Testing Examples

### Test a Service (No Hardware)
```python
async def test_temperature_alert():
    service = SensorService()
    reading = SensorReading(
        temperature=85,  # Over max
        humidity=65,
        soil_moisture=70,
        water_level=True
    )
    alerts = await service.check_thresholds(reading)
    assert len(alerts) > 0
    assert alerts[0].sensor_type == "temperature"
```

### Test a Controller (Hardware Mock)
```python
async def test_pump_starts():
    controller = IrrigationController()
    await controller.start(duration=30, speed=80)
    # Check GPIO pins were activated
    assert controller.is_running
```

---

## Summary

**Your app is now:**
- ✅ **Organized** - Logical layer structure
- ✅ **Maintainable** - Easy to understand and modify
- ✅ **Testable** - Each layer independent
- ✅ **Scalable** - Add features without touching core
- ✅ **Professional** - Industry standard architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed documentation!
