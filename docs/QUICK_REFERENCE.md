# Quick Reference - HarvestPilot Architecture

## File Organization

```
harvestpilot-raspserver/
│
├── main.py                              # ✅ THIN entry point (45 lines)
│                                         #    Just bootstraps the app
│
├── config.py                            # Configuration (thresholds, pins, etc)
│
├── src/                                 # ⭐ All business logic here
│   │
│   ├── core/
│   │   └── server.py                   # RaspServer (main orchestrator)
│   │
│   ├── services/                       # HIGH-LEVEL LOGIC
│   │   ├── firebase_service.py        # ☁️  Cloud sync
│   │   ├── sensor_service.py          # 📊 Sensor logic & alerts
│   │   └── automation_service.py      # ⏰ Scheduled tasks
│   │
│   ├── controllers/                    # LOW-LEVEL HARDWARE
│   │   ├── sensors.py                 # 🌡️  Read DHT22, water, etc
│   │   ├── irrigation.py              # 💧 Pump control
│   │   ├── lighting.py                # 💡 LED control
│   │   └── harvest.py                 # 🔄 Motor control
│   │
│   ├── models/                         # DATA STRUCTURES
│   │   ├── sensor_data.py             # SensorReading, ThresholdAlert
│   │   └── command.py                 # Command, DeviceStatus
│   │
│   └── utils/                          # HELPERS
│       ├── logger.py                  # Logging setup
│       └── gpio_manager.py            # GPIO cleanup
│
└── MODULAR_SUMMARY.md                 # 📖 This architecture explained
```

---

## Who Does What?

| File | Does | Example |
|------|------|---------|
| **main.py** | Starts app | Creates RaspServer, runs event loop |
| **RaspServer** | Orchestrates | Initializes services, runs loops, routes commands |
| **FirebaseService** | Cloud sync | Publishes data, listens for commands |
| **SensorService** | Sensor logic | Reads data, validates thresholds, creates alerts |
| **AutomationService** | Scheduling | Runs irrigation/lights at specific times |
| **SensorController** | Hardware | Reads GPIO pins, returns raw sensor values |
| **IrrigationController** | Hardware | Activates pump via GPIO |
| **LightingController** | Hardware | Dims/brightens LEDs via PWM |
| **HarvestController** | Hardware | Spins harvest motors via GPIO |
| **Models** | Data | Provides typed structures (SensorReading, etc) |
| **Utils** | Helpers | Logging, GPIO cleanup |

---

## Layer Responsibilities

### Layer 1: Entry Point (main.py)
```python
async def main():
    server = RaspServer()
    await server.start()
```
- **Responsibility:** Bootstrap application
- **Complexity:** Very low
- **Dependencies:** RaspServer only

---

### Layer 2: Core (RaspServer)
```python
class RaspServer:
    def __init__(self):
        self.firebase = FirebaseService()
        self.sensors = SensorService()
        self.automation = AutomationService(...)
        self.irrigation = IrrigationController()
        ...
```
- **Responsibility:** Initialize and orchestrate services
- **Complexity:** Medium
- **Key method:** `async def start()` - runs all loops

---

### Layer 3: Services (Business Logic)
```python
# FirebaseService
self.firebase.publish_sensor_data(reading)

# SensorService
alerts = await self.sensors.check_thresholds(reading)

# AutomationService
await self.automation.run_automation_loop()
```
- **Responsibility:** Implement business rules
- **Complexity:** High
- **Examples:** Threshold checking, scheduling, cloud sync

---

### Layer 4: Controllers (Hardware)
```python
# SensorController
reading = await self.dht_sensor.read()

# IrrigationController
await self.pump.start(speed=80)

# LightingController
await self.led.set_intensity(100)
```
- **Responsibility:** Direct hardware control
- **Complexity:** Low (just wraps GPIO)
- **No business logic:** Just hardware interface

---

### Layer 5: Data Models
```python
@dataclass
class SensorReading:
    temperature: float
    humidity: float
    soil_moisture: float
    water_level: bool
```
- **Responsibility:** Define data structures
- **Complexity:** None
- **Benefits:** Type safety, autocomplete, documentation

---

## Communication Patterns

### ➡️ **Request/Response** (Command)
```
Cloud → Firebase → FirebaseService 
  → RaspServer._handle_irrigation_start()
    → IrrigationController.start()
      → GPIO pins activate
        → ✅ Pump runs
```

### ⬅️ **Async Publish** (Data)
```
SensorController.read_all()
  → SensorService.read_all()
    → SensorService.check_thresholds()
      → Alerts created
        → FirebaseService.publish_status_update()
          → Firebase Cloud ☁️
```

---

## Key Concepts

### 🎯 **Separation of Concerns**
Each layer has ONE responsibility:
- Entry point starts app
- Core orchestrates
- Services implement logic
- Controllers control hardware
- Models define data

### ♻️ **Dependency Injection**
Services receive dependencies in `__init__`:
```python
class AutomationService:
    def __init__(self, irrigation, lighting):
        self.irrigation = irrigation  # Dependency
        self.lighting = lighting      # Dependency
```

### 📦 **Async/Await**
All I/O is non-blocking:
```python
reading = await self.sensors.read_all()  # Non-blocking I/O
await asyncio.sleep(1)                   # Non-blocking delay
```

### 🔍 **Type Hints**
Every function declares input/output types:
```python
async def read_all(self) -> SensorReading:
async def check_thresholds(self, reading: SensorReading) -> list[ThresholdAlert]:
```

---

## Why Each Layer?

| Layer | Why Separate? |
|-------|---------------|
| **Entry Point** | Keep simple, maintainable startup logic |
| **Core** | Single place to coordinate services |
| **Services** | Business logic independent of hardware |
| **Controllers** | Swap hardware without changing logic |
| **Models** | Type-safe, self-documenting data |
| **Utils** | Reusable across layers |

---

## Common Tasks

### Add Sensor Reading
1. Update SensorController.read_all()
2. Update SensorReading model
3. SensorService automatically uses it

### Add Automation
1. Create new AutomationService subclass
2. Register in RaspServer.__init__()
3. Done!

### Handle New Command
1. Add handler method: `_handle_new_command(params)`
2. Register: `self.firebase.register_command_handler(...)`
3. Done!

### Test Logic
1. Create service instance (no hardware)
2. Call method with test data
3. Assert results

---

## Debugging Tips

### Find a bug in sensor readings?
→ Check `src/controllers/sensors.py` (hardware) or `src/services/sensor_service.py` (logic)

### Commands not working?
→ Check `src/services/firebase_service.py` (command listener) or `src/core/server.py` (handler)

### Alerts not triggering?
→ Check `src/services/sensor_service.py` (threshold checking) or `config.py` (threshold values)

### App won't start?
→ Check `main.py` (entry point) or `src/core/server.py` (initialization)

---

## Files to Know

| Need to do | Edit | Line count |
|-----------|------|-----------|
| Change thresholds | `config.py` | ~80 |
| Change GPIO pins | `config.py` | ~80 |
| Handle new command | `src/core/server.py` | Add method |
| Add sensor logic | `src/services/sensor_service.py` | Add method |
| Read hardware differently | `src/controllers/*.py` | Edit controller |
| Change cloud behavior | `src/services/firebase_service.py` | Edit methods |
| Schedule tasks | `src/services/automation_service.py` | Edit methods |

---

## Test Examples

### Test: Sensor alert triggers correctly
```python
async def test_high_temp_alert():
    svc = SensorService()
    reading = SensorReading(temperature=85, ...)  # Over max (80)
    alerts = await svc.check_thresholds(reading)
    assert len(alerts) == 1
    assert alerts[0].sensor_type == "temperature"
```

### Test: Pump starts on command
```python
async def test_irrigation_start():
    server = RaspServer()
    server._handle_irrigation_start({"duration": 30})
    await asyncio.sleep(0.1)
    assert server.irrigation.is_running
```

---

## Next Steps

1. **Understand the layers** - Read ARCHITECTURE.md
2. **Run the app** - `python main.py`
3. **Add a feature** - Follow the patterns
4. **Write tests** - Test each layer independently
5. **Monitor logs** - Logging configured per layer

**Happy coding! 🚀**
