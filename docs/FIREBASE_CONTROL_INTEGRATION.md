# Firebase Real-time Control System for HarvestPilot

Complete guide to adding Firebase listeners for device control, registration, and GPIO management on your Raspberry Pi.

## Overview

Your HarvestPilot Pi can now be controlled in real-time via Firebase without SSH:

✅ **GPIO Pin Control** (on/off, PWM)  
✅ **Pump Control** (start/stop/pulse)  
✅ **Lighting Control** (on/off with brightness)  
✅ **Harvest Belt Control** (per-tray motor control)  
✅ **Sensor Reading** (temperature, humidity, soil moisture, water level)  
✅ **Device Registration** (auto-register with device ID)  
✅ **Real-time Telemetry** (publish sensor data to Firebase)  

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Webapp / Mobile App / Firebase Console                 │
└────────────────────┬────────────────────────────────────┘
                     │ (sends commands)
                     ▼
        ┌────────────────────────┐
        │   Firebase Realtime    │
        │      Database          │
        │   (/devices/.../       │
        │    commands/)          │
        └────────────┬───────────┘
                     │ (listens)
                     ▼
        ┌────────────────────────────────────┐
        │   Raspberry Pi RaspServer          │
        │  ┌──────────────────────────────┐  │
        │  │ FirebaseDeviceListener       │  │
        │  │ - Listens for commands       │  │
        │  │ - Routes to handlers         │  │
        │  │ - Sends responses back       │  │
        │  └──────────────────────────────┘  │
        │  ┌──────────────────────────────┐  │
        │  │ DeviceManager                │  │
        │  │ - Register device            │  │
        │  │ - Track GPIO pins            │  │
        │  │ - Publish telemetry          │  │
        │  └──────────────────────────────┘  │
        │  ┌──────────────────────────────┐  │
        │  │ Controllers                  │  │
        │  │ - IrrigationController       │  │
        │  │ - LightingController         │  │
        │  │ - HarvestController          │  │
        │  │ - SensorController           │  │
        │  └──────────────────────────────┘  │
        └────────────────────────────────────┘
                     │ (writes responses)
                     ▼
        ┌────────────────────────┐
        │   Firebase Realtime    │
        │      Database          │
        │   (/devices/.../       │
        │    responses/)         │
        └────────────────────────┘
```

---

## File Structure

```
harvestpilot-raspserver/
├── services/
│   ├── __init__.py                      (NEW - Module exports)
│   ├── firebase_listener.py             (NEW - Command listener & handlers)
│   ├── device_manager.py                (NEW - Device registration & telemetry)
│   └── firebase_control_examples.py     (NEW - Examples & documentation)
├── config.py                            (EXISTING - Configuration)
├── firebase_client.py                   (EXISTING - Basic Firebase client)
├── main.py                              (NEEDS UPDATE - Add listener integration)
├── controllers/
│   ├── irrigation.py                    (EXISTING)
│   ├── lighting.py                      (EXISTING)
│   ├── harvest.py                       (EXISTING)
│   └── sensors.py                       (EXISTING)
└── utils/
    └── gpio_manager.py                  (EXISTING)
```

---

## Quick Start (5 Minutes)

### Step 1: Update main.py

In [main.py](../main.py), add Firebase listener integration:

```python
from src.services.firebase_listener import FirebaseDeviceListener
from src.services.device_manager import DeviceManager

class RaspServer:
    def __init__(self):
        # ... existing code ...
        
        # NEW: Initialize device manager and Firebase listener
        self.device_manager = DeviceManager(device_id=config.DEVICE_ID)
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
    
    async def start(self):
        # ... existing code ...
        
        # NEW: Register device and start listeners
        await self.device_manager.register_device()
        await self.firebase_listener.start_listening()
        
        # ... rest of startup ...
```

### Step 2: Restart Service

```bash
sudo systemctl restart harvestpilot-raspserver
```

### Step 3: Verify Registration

Check if device registered in Firebase:

```bash
ssh monkphx@192.168.1.233
sudo journalctl -u harvestpilot-raspserver -n 20
```

Look for:
```
Device registered successfully: hp-XXXXXXXX
Firebase listeners started for device: hp-XXXXXXXX
```

### Step 4: Test Command

Via Firebase Console:

1. Go to: https://console.firebase.google.com
2. Select: **harvest-hub** project
3. Click: **Realtime Database**
4. Navigate to: `devices/hp-XXXXXXXX/commands`
5. Click: **+** (Add child)
6. Name: `cmd-001`
7. Value: 
```json
{
  "type": "pump",
  "action": "start",
  "speed": 80
}
```
8. Click: **Add**

Watch the Pi logs - you should see the pump start! ✅

---

## Command Types

### 1. Pump Control

```json
{
  "type": "pump",
  "action": "start|stop|pulse",
  "speed": 80,
  "duration": 30
}
```

**Actions:**
- `start` - Start pump at speed (0-100%)
- `stop` - Stop pump
- `pulse` - Run for duration seconds then stop

**Example:** Start pump at 75% for 10 seconds
```json
{
  "type": "pump",
  "action": "pulse",
  "speed": 75,
  "duration": 10
}
```

### 2. Lights Control

```json
{
  "type": "lights",
  "action": "on|off",
  "brightness": 100
}
```

**Example:** Turn lights on at 50% brightness
```json
{
  "type": "lights",
  "action": "on",
  "brightness": 50
}
```

### 3. GPIO Pin Control (Low-level)

```json
{
  "type": "pin_control",
  "pin": 17,
  "action": "on|off",
  "duration": 5
}
```

**Example:** Turn GPIO 17 on for 5 seconds then auto-off
```json
{
  "type": "pin_control",
  "pin": 17,
  "action": "on",
  "duration": 5
}
```

### 4. PWM Control (Analog control)

```json
{
  "type": "pwm_control",
  "pin": 17,
  "duty_cycle": 75,
  "frequency": 1000
}
```

**Example:** Set GPIO 18 to 60% PWM (dimming lights)
```json
{
  "type": "pwm_control",
  "pin": 18,
  "duty_cycle": 60,
  "frequency": 1000
}
```

### 5. Harvest Belt Control

```json
{
  "type": "harvest",
  "action": "start|stop|position",
  "belt_id": 1,
  "speed": 50,
  "duration": 10,
  "position": "home|end"
}
```

**Example:** Start belt 2 at 40% speed
```json
{
  "type": "harvest",
  "action": "start",
  "belt_id": 2,
  "speed": 40
}
```

### 6. Sensor Read (Read sensor values on demand)

```json
{
  "type": "sensor_read",
  "sensor": "temperature|humidity|soil_moisture|water_level"
}
```

**Example:** Read current temperature
```json
{
  "type": "sensor_read",
  "sensor": "temperature"
}
```

Response will appear in `/devices/hp-XXXXXXXX/responses/` with sensor value and timestamp.

### 7. Device Configuration

```json
{
  "type": "device_config",
  "config": {
    "AUTO_IRRIGATION_ENABLED": true,
    "SENSOR_READING_INTERVAL": 5
  }
}
```

---

## Device Registration

Device automatically registers on startup with:

- **Device ID**: Unique identifier (hp-XXXXXXXX format)
- **Status**: online/offline
- **Capabilities**: What the device can do
- **Hardware Info**: GPIO pins, PWM frequencies, etc.
- **Timestamp**: When registered

Location in Firebase:
```
devices/hp-XXXXXXXX/
├── device_id: "hp-XXXXXXXX"
├── status: "online"
├── registered_at: "2026-01-25T..."
├── capabilities: {
│   ├── pump_control: true
│   ├── light_control: true
│   ├── motor_control: true
│   └── pwm_support: true
└── hardware: {
    ├── gpio_pins: {...}
    └── pwm_frequency: {...}
}
```

---

## Real-time Telemetry

Device publishes sensor data automatically:

Location: `/devices/hp-XXXXXXXX/telemetry/`

```json
{
  "sensors": {
    "temperature": 72.5,
    "humidity": 65.0,
    "soil_moisture": 75.0,
    "water_level": 80.0
  },
  "actuators": {
    "pump": {
      "running": true,
      "speed": 80
    },
    "lights": {
      "on": true,
      "brightness": 100
    },
    "motors": [...]
  },
  "system": {
    "cpu_temp": 45.2,
    "memory_usage": 45.6,
    "uptime_seconds": 86400
  },
  "timestamp": "2026-01-25T20:30:45..."
}
```

---

## Firebase Database Structure

Complete structure:

```
realtime_database/
├── devices/
│   ├── hp-XXXXXXXX/              (Your device)
│   │   ├── device_id
│   │   ├── status
│   │   ├── registered_at
│   │   ├── capabilities
│   │   ├── hardware
│   │   │
│   │   ├── commands/             (INCOMING - You write here)
│   │   │   ├── cmd-001: {...}
│   │   │   └── cmd-002: {...}
│   │   │
│   │   ├── responses/            (OUTGOING - Pi writes here)
│   │   │   ├── cmd-001: {
│   │   │   │   "status": "success",
│   │   │   │   "data": {...},
│   │   │   │   "timestamp": "..."
│   │   │   │}
│   │   │   └── cmd-002: {...}
│   │   │
│   │   ├── telemetry/           (SENSOR DATA - Pi publishes)
│   │   │   ├── sensors: {...}
│   │   │   ├── actuators: {...}
│   │   │   └── timestamp
│   │   │
│   │   ├── pins/                (GPIO TRACKING)
│   │   │   ├── 17: {
│   │   │   │   "name": "Pump PWM",
│   │   │   │   "type": "pwm",
│   │   │   │   "state": {"value": 80}
│   │   │   │}
│   │   │   └── ...
│   │   │
│   │   └── errors/              (ERROR LOG)
│   │       ├── error-001: {...}
│   │       └── ...
│   │
│   └── hp-YYYYYYYY/            (Another device)
│       └── ...
│
└── registration_requests/
    └── hp-XXXXXXXX: {...}
```

---

## Response Format

Every command gets a response in `/devices/hp-XXXXXXXX/responses/{command_id}`:

**Successful Response:**
```json
{
  "command_id": "cmd-001",
  "command_type": "pump",
  "status": "success",
  "data": {
    "action": "start",
    "speed": 80,
    "status": "running"
  },
  "timestamp": "2026-01-25T20:31:00.123456",
  "device_id": "hp-XXXXXXXX"
}
```

**Error Response:**
```json
{
  "command_id": "cmd-002",
  "command_type": "unknown_type",
  "status": "error",
  "data": "Unknown command type: unknown_type",
  "timestamp": "2026-01-25T20:31:05.654321",
  "device_id": "hp-XXXXXXXX"
}
```

---

## How to Use from Webapp

Example JavaScript integration:

```javascript
// Send command and wait for response
async function sendPiCommand(deviceId, command) {
  const commandId = `cmd-${Date.now()}`;
  
  // Write command to Firebase
  await firebase.database()
    .ref(`devices/${deviceId}/commands`)
    .push({
      id: commandId,
      ...command,
      sent_at: new Date().toISOString()
    });
  
  // Wait for response (timeout after 10 seconds)
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error("Command timeout - no response from device"));
    }, 10000);
    
    firebase.database()
      .ref(`devices/${deviceId}/responses/${commandId}`)
      .on('value', (snapshot) => {
        if (snapshot.exists()) {
          clearTimeout(timeout);
          resolve(snapshot.val());
        }
      });
  });
}

// Usage examples:
try {
  // Start pump
  const pumpResult = await sendPiCommand('hp-XXXXXXXX', {
    type: 'pump',
    action: 'start',
    speed: 80
  });
  console.log('Pump started:', pumpResult);
  
  // Turn on lights
  const lightResult = await sendPiCommand('hp-XXXXXXXX', {
    type: 'lights',
    action: 'on',
    brightness: 100
  });
  console.log('Lights on:', lightResult);
  
} catch (error) {
  console.error('Command failed:', error);
}
```

---

## Troubleshooting

### Device not registering

Check Pi logs:
```bash
sudo journalctl -u harvestpilot-raspserver -n 50
```

Look for errors like:
- `Firebase connection failed` - Check credentials
- `Device registration failed` - Check Firebase rules
- `Listeners not started` - Check listener initialization in main.py

### Commands not working

1. Check command format in Firebase
   - Must have valid "type"
   - Check spelling of fields
   
2. Verify controller is available
   - Check `controllers_map` in main.py
   - All controllers must be initialized

3. Check Pi logs for handler errors
   ```bash
   sudo journalctl -u harvestpilot-raspserver -f
   ```

### GPIO pins not responding

1. Verify pin number is correct
   - GPIO 17 = Physical pin 11
   - GPIO 18 = Physical pin 12
   - Check pinout diagram

2. Check if pin is already in use
   ```bash
   cat ~/harvestpilot-raspserver/config/gpio_pins.json
   ```

3. Test manually:
   ```bash
   python3
   >>> import RPi.GPIO as GPIO
   >>> GPIO.setmode(GPIO.BCM)
   >>> GPIO.setup(17, GPIO.OUT)
   >>> GPIO.output(17, GPIO.HIGH)  # Should turn on
   >>> GPIO.output(17, GPIO.LOW)   # Should turn off
   ```

---

## Testing Examples

### Test 1: Pump Start

Command:
```json
{
  "type": "pump",
  "action": "start",
  "speed": 100
}
```

Expected response:
```json
{
  "status": "success",
  "data": {
    "action": "start",
    "speed": 100,
    "status": "running"
  }
}
```

Pi logs should show:
```
INFO - Pump command: start (speed: 100%)
INFO - Pump started at 100%
```

### Test 2: GPIO PWM

Command:
```json
{
  "type": "pwm_control",
  "pin": 18,
  "duty_cycle": 50,
  "frequency": 1000
}
```

Expected response:
```json
{
  "status": "success",
  "data": {
    "pin": 18,
    "duty_cycle": 50,
    "frequency": 1000,
    "status": "success"
  }
}
```

### Test 3: Sensor Reading

Command:
```json
{
  "type": "sensor_read",
  "sensor": "temperature"
}
```

Expected response:
```json
{
  "status": "success",
  "data": {
    "sensor": "temperature",
    "value": 72.5,
    "unit": "°F",
    "timestamp": "2026-01-25T20:31:45..."
  }
}
```

---

## Advanced Features

### Per-Pi GPIO Configuration

Each Pi can have different GPIO pins by setting in config.py:

```python
PUMP_PWM_PIN = 17  # Change as needed
LIGHT_PWM_PIN = 18
DHT22_PIN = 4
WATER_LEVEL_PIN = 27
```

### GPIO Pin Tracking

All pin states are tracked in Firebase:

```
devices/hp-XXXXXXXX/pins/
├── 17/
│   ├── name: "Pump PWM"
│   ├── type: "pwm"
│   ├── purpose: "irrigation"
│   └── state: {
│       ├── value: 80
│       └── mode: "pwm"
│   }
└── 18/
    └── ...
```

### Error Logging

Errors are automatically logged:

```
devices/hp-XXXXXXXX/errors/
├── error-001/
│   ├── type: "sensor_error"
│   ├── message: "DHT22 read failed"
│   ├── timestamp: "..."
│   └── context: {...}
```

### Multi-Device Management

Control multiple Pis:

```javascript
// List all devices
const devices = await firebase.database()
  .ref('devices')
  .once('value');

devices.forEach(device => {
  console.log(device.key, device.val().status);
});

// Send command to each device
for (const deviceId in devices.val()) {
  await sendPiCommand(deviceId, { ... });
}
```

---

## API Reference

See [firebase_listener.py](./firebase_listener.py) for complete API.

Key classes:

**FirebaseDeviceListener**
- `start_listening()` - Start command listener
- `publish_status()` - Publish device status
- `_handle_pump_command()` - Pump handler
- `_handle_lights_command()` - Lights handler
- `_handle_pin_control()` - GPIO control
- `_handle_pwm_control()` - PWM control
- And more...

**DeviceManager**
- `register_device()` - Register in Firebase
- `update_status()` - Update status
- `publish_telemetry()` - Publish sensor data
- `register_pin()` - Track GPIO pin
- `set_pin_state()` - Record pin state
- And more...

---

## Next Steps

1. ✅ Update main.py with listener integration
2. ✅ Restart Pi service
3. ✅ Test pump control via Firebase Console
4. ✅ Test lights control
5. ✅ Test GPIO pins
6. ✅ Test PWM control
7. 🔲 Add webapp integration (JavaScript)
8. 🔲 Add mobile app integration
9. 🔲 Set up automated scheduling

---

## Questions?

Check these files:
- [firebase_listener.py](./firebase_listener.py) - Command handlers
- [device_manager.py](./device_manager.py) - Device management
- [firebase_control_examples.py](./firebase_control_examples.py) - Example commands
