# Your RaspServer Code Structure - Analyzed ✅

## Current Structure (What You Have)

```
harvestpilot-raspserver/
│
├── main.py                          ← Entry point (async)
│   └── RaspServer                   ← Main server class
│       ├── __init__()               ← Initializes controllers
│       ├── start()                  ← Async startup
│       └── stop()                   ← Shutdown
│
├── config.py                        ← Configuration (GPIO pins, etc)
├── firebase_client.py               ← Basic Firebase connection
│
├── controllers/                     ← Hardware controllers
│   ├── irrigation.py                ← Pump control
│   │   └── IrrigationController.start(speed, duration)
│   ├── lighting.py                  ← Light control
│   │   └── LightingController.turn_on(brightness)
│   ├── harvest.py                   ← Harvest belt control
│   │   └── HarvestController.start_belt(belt_id, speed)
│   └── sensors.py                   ← Sensor reading
│       └── SensorController.read_sensor(type)
│
├── utils/                           ← Utility modules
│   ├── gpio_manager.py              ← GPIO cleanup
│   ├── logger.py                    ← Logging setup
│   └── config_loader.py             ← Load config
│
└── src/                             ← Newer modular structure
    ├── core/
    │   └── rasp_server.py           ← Main server (newer version)
    ├── controllers/
    ├── hardware/
    ├── services/                    ← NEW SERVICES ADDED HERE
    ├── storage/
    ├── sync/
    └── utils/
```

---

## How Your Code Works

### 1. Entry Point (main.py)

```
main.py:main()
    ↓
    asyncio.run(main())
    ↓
    RaspServer()                        ← Creates server
        ├── __init__() Controllers
        ├── __init__() GPIO Manager
        └── __init__() Firebase Client
    ↓
    server.start()                      ← Async startup
        ├── Initialize all modules
        ├── Start GPIO
        ├── Connect Firebase
        └── Keep running
```

### 2. Controllers Pattern

Each controller follows same pattern:

```python
class IrrigationController:
    def __init__(self):
        # Setup GPIO
        self.pwm = GPIO.PWM(pin, frequency)
    
    async def start(self, speed=80, duration=30):
        # Execute action
        self.pwm.start(speed)
    
    async def stop(self):
        # Stop
        self.pwm.stop()
```

**Same pattern for:**
- IrrigationController (pump)
- LightingController (lights)
- HarvestController (belts)
- SensorController (sensors)

### 3. Firebase Communication

```python
# Current (basic):
firebase_client.py:
    - Connect to Firebase
    - Publish sensor data
    - Get device status

# NEW (real-time):
firebase_listener.py:
    - Listen for commands in /devices/{id}/commands/
    - Route to handlers
    - Respond in /devices/{id}/responses/
    - Use controllers to execute
```

---

## What I Added (New Services Layer)

```
services/                           ← NEW
├── __init__.py                      ← Exports
├── firebase_listener.py             ← Command listener (380 lines)
│   ├── FirebaseDeviceListener
│   │   ├── start_listening()
│   │   ├── _process_command()
│   │   ├── _handle_pump_command()
│   │   ├── _handle_lights_command()
│   │   ├── _handle_pin_control()
│   │   ├── _handle_pwm_control()
│   │   ├── _handle_harvest_command()
│   │   ├── _handle_sensor_read()
│   │   ├── _handle_device_config()
│   │   └── _send_response()
│   │
│   └── Works with your controllers:
│       └── Calls self.controllers_map["pump"].start()
│       └── Calls self.controllers_map["lights"].turn_on()
│       └── Etc...
│
└── device_manager.py                ← Device registration (300 lines)
    ├── DeviceManager
    │   ├── register_device()
    │   ├── update_status()
    │   ├── publish_telemetry()
    │   ├── register_pin()
    │   ├── set_pin_state()
    │   ├── record_error()
    │   └── get_device_logs()
    │
    └── Handles:
        ├── Device registration in Firebase
        ├── Status updates
        ├── Telemetry publishing
        ├── Error logging
        └── Pin tracking
```

---

## Data Flow with New Listeners

### Before (Your Current Setup)

```
Sensors
    ↓
SensorController.read_sensor()
    ↓
Publish to Firebase
    └── One-way: Pi → Cloud
```

### After (With New Listeners)

```
Firebase Console (User sends command)
    ↓
/devices/hp-XXXXXXXX/commands/
    ↓
FirebaseDeviceListener.listen()
    ↓
Detects command: {"type": "pump", "action": "start"}
    ↓
_handle_pump_command()
    ↓
self.controllers_map["pump"].start(speed=80)
    ↓
IrrigationController.start()
    ↓
GPIO 17 PWM starts
    ↓
Pump runs
    ↓
_send_response()
    ↓
/devices/hp-XXXXXXXX/responses/cmd-001/
{
    "status": "success",
    "data": {"action": "start", "speed": 80}
}
    ↓
User sees response in Firebase ✅
```

---

## Integration Points

### 1. In main.py, create instances:

```python
class RaspServer:
    def __init__(self):
        # Your existing code
        self.irrigation_controller = IrrigationController()
        self.lighting_controller = LightingController()
        self.harvest_controller = HarvestController()
        self.sensor_controller = SensorController()
        
        # NEW: Add device manager
        from src.services.device_manager import DeviceManager
        self.device_manager = DeviceManager(
            device_id=config.DEVICE_ID
        )
        
        # NEW: Add Firebase listener
        from src.services.firebase_listener import FirebaseDeviceListener
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

### 2. In RaspServer.start():

```python
async def start(self):
    # Your existing startup
    
    # NEW: Register device
    await self.device_manager.register_device()
    
    # NEW: Start listening for commands
    await self.firebase_listener.start_listening()
    
    # Rest of your code
```

---

## How Handlers Work

### Example: Pump Command Handler

```python
async def _handle_pump_command(self, command):
    """
    Command JSON:
    {
        "type": "pump",
        "action": "start|stop|pulse",
        "speed": 80,
        "duration": 30
    }
    """
    
    action = command.get("action")
    speed = command.get("speed", 80)
    
    pump = self.controllers_map["pump"]  # Your IrrigationController
    
    if action == "start":
        await pump.start(speed=speed)  # Calls YOUR existing code
        return {"status": "running"}
    
    elif action == "stop":
        await pump.stop()               # Calls YOUR existing code
        return {"status": "stopped"}
```

**The handlers are just "adapters" that call YOUR existing controller methods!**

---

## Example: How a Command Executes

### Step 1: User sends command

Firebase Console:
```json
{
  "type": "pump",
  "action": "start",
  "speed": 100
}
```

### Step 2: Listener detects

```python
# In firebase_listener.py
def commands_callback(message):
    asyncio.create_task(self._process_command(message.data))
```

### Step 3: Router processes

```python
# In firebase_listener.py
async def _process_command(self, command):
    command_type = command.get("type")  # "pump"
    handler = self.command_handlers.get(command_type)
    # Gets: _handle_pump_command
    result = await handler(command)
```

### Step 4: Handler executes

```python
# In firebase_listener.py
async def _handle_pump_command(self, command):
    action = command.get("action")      # "start"
    speed = command.get("speed")        # 100
    
    pump_controller = self.controllers_map.get("pump")
    # Gets: your IrrigationController instance
    
    await pump_controller.start(speed=speed)
    # Calls YOUR existing code!
```

### Step 5: Your controller runs

```python
# Your existing controllers/irrigation.py
class IrrigationController:
    async def start(self, speed=80):
        if config.SIMULATE_HARDWARE:
            logger.info(f"[SIMULATION] Pump: {speed}%")
        else:
            self.pwm.start(speed)  # Real GPIO
        
        self.is_running = True
        logger.info(f"Pump started at {speed}%")
```

### Step 6: Response sent back

```python
# In firebase_listener.py
await self._send_response(command_id, "pump", "success", {
    "action": "start",
    "speed": 100,
    "status": "running"
})
```

### Step 7: Response in Firebase

```
/devices/hp-XXXXXXXX/responses/cmd-001/
{
    "command_id": "cmd-001",
    "command_type": "pump",
    "status": "success",
    "data": {
        "action": "start",
        "speed": 100,
        "status": "running"
    },
    "timestamp": "2026-01-25T20:31:00..."
}
```

User sees response ✅

---

## Supported Commands by Handler

| Handler | Commands | Controller Used |
|---------|----------|-----------------|
| `_handle_pump_command` | start, stop, pulse | `IrrigationController` |
| `_handle_lights_command` | on, off | `LightingController` |
| `_handle_harvest_command` | start, stop, position | `HarvestController` |
| `_handle_sensor_read` | temperature, humidity, etc | `SensorController` |
| `_handle_pin_control` | on, off | Direct GPIO |
| `_handle_pwm_control` | Set duty cycle | Direct PWM |
| `_handle_device_config` | Update settings | `config.py` |

---

## Key Features of New System

✅ **Uses YOUR existing controllers** - No need to rewrite anything  
✅ **Async/await** - Non-blocking, like your code  
✅ **Error handling** - Catches and logs errors  
✅ **Response messaging** - User always knows if command worked  
✅ **Status tracking** - Device status updates in Firebase  
✅ **Telemetry** - Auto-publishes sensor data  
✅ **Pin tracking** - Records all GPIO state changes  
✅ **Extensible** - Easy to add new handlers  

---

## Summary

Your code structure:
- **Controllers** handle hardware (pump, lights, belts, sensors)
- **Config** defines GPIO pins and settings
- **Firebase client** handles basic connection

What I added:
- **Firebase listener** - Detects commands and routes to handlers
- **Device manager** - Registers device and publishes telemetry
- **Handlers** - "Adapters" that call YOUR existing controllers

**The new code doesn't change your existing code - it just adds a new way to control it!**

---

## Next: Integration

Ready to integrate?

1. Open main.py
2. Add the imports and 3 lines (see FIREBASE_CONTROL_INTEGRATION.md)
3. Restart service
4. Done!

See: [FIREBASE_CONTROL_INTEGRATION.md](./docs/FIREBASE_CONTROL_INTEGRATION.md)
