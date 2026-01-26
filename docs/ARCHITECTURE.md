# HarvestPilot RaspServer - Architecture Guide

## Overview

The HarvestPilot RaspServer has been reorganized into a **modular, layered architecture** that separates concerns and improves maintainability. Each layer has a specific responsibility.

---

## Directory Structure

```
harvestpilot-raspserver/
├── src/                          # Main source code
│   ├── __init__.py
│   ├── core/                     # Core server orchestration
│   │   ├── __init__.py
│   │   └── server.py            # RaspServer class (main orchestrator)
│   │
│   ├── controllers/              # Hardware control layer (LOW-LEVEL)
│   │   ├── __init__.py
│   │   ├── sensors.py           # Read sensor data
│   │   ├── irrigation.py        # Control pump
│   │   ├── lighting.py          # Control LED
│   │   └── harvest.py           # Control harvest belts
│   │
│   ├── services/                 # Business logic layer (MID-LEVEL)
│   │   ├── __init__.py
│   │   ├── firebase_service.py  # Firebase communication
│   │   ├── sensor_service.py    # Sensor data management & validation
│   │   └── automation_service.py # Scheduled tasks
│   │
│   ├── models/                   # Data structures (SCHEMAS)
│   │   ├── __init__.py
│   │   ├── sensor_data.py       # SensorReading, ThresholdAlert
│   │   └── command.py           # Command, DeviceStatus
│   │
│   ├── controllers/              # (copied from root)
│   ├── utils/                    # (copied from root)
│   │   ├── __init__.py
│   │   ├── logger.py
│   │   └── gpio_manager.py
│   └── __init__.py
│
├── main.py                       # Entry point (THIN)
├── config.py                     # Global configuration
└── requirements.txt
```

---

## Architecture Layers

### 1. **Entry Point** (`main.py`)
- **Responsibility:** Application bootstrap
- **What it does:**
  - Sets up logging
  - Initializes the RaspServer
  - Handles signal/shutdown events
  - Runs the async event loop

**Key principle:** Keep this thin - no business logic here!

---

### 2. **Core Layer** (`src/core/server.py`)
- **Responsibility:** Orchestration & command routing
- **Contains:** `RaspServer` class
- **What it does:**
  - Creates and manages all services
  - Registers command handlers
  - Runs sensor reading loop
  - Coordinates emergency stops

**Key principle:** Orchestrator, not worker. Delegates actual work to services.

---

### 3. **Services Layer** (`src/services/`)
- **Responsibility:** Business logic & coordination
- **Contains high-level operations:**

#### **FirebaseService** (`firebase_service.py`)
- Abstracts Firebase operations
- Publishes sensor data
- Listens for commands
- Manages device status
- No hardware access directly

#### **SensorService** (`sensor_service.py`)
- Reads sensor data
- Validates readings against thresholds
- Generates alerts
- Uses SensorController internally

#### **AutomationService** (`automation_service.py`)
- Scheduled tasks (irrigation, lighting)
- Time-based automation
- References to controllers

**Key principle:** Services are *stateless orchestrators*. They coordinate controllers and external systems.

---

### 4. **Controllers Layer** (`src/controllers/`)
- **Responsibility:** Direct hardware control
- **Contains low-level operations:**
  - `sensors.py` - Read GPIO/sensors
  - `irrigation.py` - Control pump
  - `lighting.py` - Control LEDs
  - `harvest.py` - Control motors

**Key principle:** Pure hardware interface. No business logic or validation.

---

### 5. **Models Layer** (`src/models/`)
- **Responsibility:** Data structures & schemas
- **Contains:**
  - `SensorReading` - Typed sensor data
  - `ThresholdAlert` - Alert structure
  - `Command` - Command structure
  - `DeviceStatus` - Status snapshot

**Key principle:** Immutable data classes. Makes code type-safe and self-documenting.

---

### 6. **Utils Layer** (`src/utils/`)
- **Responsibility:** Reusable utilities
- **Contains:**
  - `logger.py` - Logging setup
  - `gpio_manager.py` - GPIO cleanup

**Key principle:** No dependencies on app logic. Completely reusable.

---

## Data Flow

### **Sensor Reading → Firebase → Cloud**

```
┌─────────────────────────────────────────────────────────────┐
│  main.py (Entry Point)                                      │
│  └─> RaspServer.start()                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  RaspServer (Orchestrator)                                  │
│  └─> await _sensor_reading_loop()                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  SensorService (Business Logic)                             │
│  ├─> sensor_reading = await read_all()                      │
│  └─> alerts = await check_thresholds(reading)               │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  SensorController (Hardware)                                │
│  └─> await self.dht_sensor.read()                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                    [GPIO]
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  FirebaseService (Cloud Sync)                               │
│  ├─> publish_sensor_data(reading)                           │
│  └─> publish_status_update(alerts)                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                   [Network]
                       │
                      ▼
              Firebase Cloud ☁️
```

### **Cloud Command → Local Hardware**

```
Firebase Cloud ☁️
       │
       │ [Network]
       │
┌──────▼──────────────────────────────────────────────────────┐
│  FirebaseService (Listens)                                  │
│  └─> on_command_update(message)                             │
└──────┬──────────────────────────────────────────────────────┘
       │
       │ Routes to registered handler
       │
┌──────▼──────────────────────────────────────────────────────┐
│  RaspServer._handle_irrigation_start(params)                │
│  └─> asyncio.create_task(self.irrigation.start(...))        │
└──────┬──────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│  IrrigationController (Hardware Control)                    │
│  └─> await pump.start()                                     │
└──────┬──────────────────────────────────────────────────────┘
       │
    [GPIO/PWM]
       │
      ▼
   Pump starts 💧
```

---

## Why This Architecture?

| Benefit | Why |
|---------|-----|
| **Separation of Concerns** | Each layer has one job. Easy to understand and modify. |
| **Testability** | Services can be tested independently of hardware. |
| **Reusability** | Services don't depend on each other. Can be mixed/matched. |
| **Scalability** | Adding new features doesn't require touching core code. |
| **Type Safety** | Models provide structure. IDE autocomplete works. |
| **Maintainability** | Changes are localized. Less cascading bugs. |

---

## Example: Adding a New Feature

### **Scenario:** Add automatic light control based on temperature

#### Step 1: Create a Model
```python
# src/models/sensor_data.py
@dataclass
class EnvironmentalThreshold:
    sensor_type: str
    min_value: float
    max_value: float
    action: str  # "increase_light", "decrease_light"
```

#### Step 2: Create a Service
```python
# src/services/light_automation_service.py
class LightAutomationService:
    def __init__(self, lighting_controller):
        self.lighting = lighting_controller
    
    async def adjust_light_by_temperature(self, temp: float):
        if temp < 65:
            await self.lighting.increase_intensity(10)
        elif temp > 80:
            await self.lighting.decrease_intensity(10)
```

#### Step 3: Register in RaspServer
```python
# src/core/server.py
def __init__(self):
    self.light_automation = LightAutomationService(self.lighting)

async def _sensor_reading_loop(self):
    reading = await self.sensors.read_all()
    await self.light_automation.adjust_light_by_temperature(reading.temperature)
```

**No changes to:**
- Entry point
- Controllers
- Firebase service
- Existing logic

---

## Key Principles

### 1. **Dependency Injection**
Services receive their dependencies in `__init__`:
```python
def __init__(self, irrigation_controller, lighting_controller):
    self.irrigation = irrigation_controller
    self.lighting = lighting_controller
```

### 2. **Single Responsibility**
Each class does ONE thing:
- `FirebaseService` → Firebase operations
- `SensorService` → Sensor logic
- `SensorController` → Hardware reading

### 3. **Async/Await Pattern**
All I/O is async:
```python
reading = await self.sensors.read_all()  # Non-blocking
```

### 4. **Type Hints**
Functions declare input/output types:
```python
async def read_all(self) -> SensorReading:
async def check_thresholds(self, reading: SensorReading) -> list[ThresholdAlert]:
```

### 5. **Error Handling**
Each layer handles its own errors:
```python
try:
    await self.irrigation.start()
except Exception as e:
    logger.error(f"Error: {e}")
    # Recover gracefully
```

---

## Testing Strategy

### Unit Testing Controllers
```python
# Test hardware control in isolation
def test_pump_starts():
    controller = IrrigationController()
    await controller.start(duration=30)
    assert pump.is_running
```

### Unit Testing Services
```python
# Test logic without hardware
def test_alert_on_high_temperature():
    service = SensorService()
    reading = SensorReading(temperature=85, ...)
    alerts = await service.check_thresholds(reading)
    assert any(a.sensor_type == "temperature" for a in alerts)
```

### Integration Testing
```python
# Test end-to-end with mocks
def test_command_flow():
    server = RaspServer()
    server._handle_irrigation_start({"duration": 30})
    await asyncio.sleep(0.1)
    assert server.irrigation.is_running
```

---

## Configuration

All settings live in `config.py`:
```python
# Hardware
SENSOR_DHT22_PIN = 4
PUMP_PWM_PIN = 26

# Thresholds
TEMP_MIN = 65.0
TEMP_MAX = 80.0

# Automation
AUTO_IRRIGATION_ENABLED = True
IRRIGATION_SCHEDULE = ["06:00", "12:00", "18:00"]
```

Services read config when needed:
```python
await self.irrigation.start(
    duration=config.IRRIGATION_CYCLE_DURATION,
    speed=config.PUMP_DEFAULT_SPEED
)
```

---

## Future Improvements

1. **Database Layer** - Persist readings to SQLite
2. **Event Bus** - Decouple services using pub/sub
3. **Middleware** - Add rate limiting, retries
4. **API Layer** - REST endpoints for direct control
5. **Caching** - Cache recent readings

---

## Summary

**Old Code:** Monolithic main.py with everything mixed together

**New Code:** Layered architecture with clear responsibilities:
- **Core** → Orchestration
- **Services** → Business logic
- **Controllers** → Hardware
- **Models** → Data structures
- **Utils** → Helpers

This makes the app easier to understand, test, modify, and extend! 🚀
