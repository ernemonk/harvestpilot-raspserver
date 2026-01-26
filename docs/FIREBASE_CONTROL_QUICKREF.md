# Firebase Control - Quick Reference

## 🚀 5-Minute Setup

### 1. Update main.py

Add to your RaspServer class:

```python
from src.services.firebase_listener import FirebaseDeviceListener
from src.services.device_manager import DeviceManager

# In __init__:
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

# In start() method:
await self.device_manager.register_device()
await self.firebase_listener.start_listening()
```

### 2. Restart Service

```bash
sudo systemctl restart harvestpilot-raspserver
```

### 3. Test

Send a command via Firebase Console:

```json
{
  "type": "pump",
  "action": "start",
  "speed": 80
}
```

---

## 📋 Command Cheat Sheet

### Pump Control

```json
// Start
{"type": "pump", "action": "start", "speed": 80}

// Stop
{"type": "pump", "action": "stop"}

// Pulse (5 sec at 50%)
{"type": "pump", "action": "pulse", "speed": 50, "duration": 5}
```

### Lights Control

```json
// Turn on
{"type": "lights", "action": "on", "brightness": 100}

// Dim to 50%
{"type": "lights", "action": "on", "brightness": 50}

// Turn off
{"type": "lights", "action": "off"}
```

### GPIO Pin Control

```json
// Turn on
{"type": "pin_control", "pin": 17, "action": "on"}

// Turn off
{"type": "pin_control", "pin": 17, "action": "off"}

// Turn on for 5 seconds
{"type": "pin_control", "pin": 17, "action": "on", "duration": 5}
```

### PWM Control

```json
// 75% duty cycle at 1000Hz
{"type": "pwm_control", "pin": 17, "duty_cycle": 75, "frequency": 1000}

// 50% (dimming)
{"type": "pwm_control", "pin": 18, "duty_cycle": 50}
```

### Harvest Belt

```json
// Start belt 1
{"type": "harvest", "action": "start", "belt_id": 1, "speed": 50}

// Stop belt 2
{"type": "harvest", "action": "stop", "belt_id": 2}

// Move belt 3 home
{"type": "harvest", "action": "position", "belt_id": 3, "position": "home"}
```

### Sensor Read

```json
// Temperature
{"type": "sensor_read", "sensor": "temperature"}

// Humidity
{"type": "sensor_read", "sensor": "humidity"}

// Soil moisture
{"type": "sensor_read", "sensor": "soil_moisture"}

// Water level
{"type": "sensor_read", "sensor": "water_level"}
```

### Device Config

```json
// Enable auto irrigation
{"type": "device_config", "config": {"AUTO_IRRIGATION_ENABLED": true}}

// Change sensor interval
{"type": "device_config", "config": {"SENSOR_READING_INTERVAL": 10}}
```

---

## 🔍 Firebase Paths

**Where to send commands:**
```
devices/{device_id}/commands/
```

**Where to find responses:**
```
devices/{device_id}/responses/
```

**Device info:**
```
devices/{device_id}/
```

**Sensor data:**
```
devices/{device_id}/telemetry/
```

**GPIO tracking:**
```
devices/{device_id}/pins/
```

**Error logs:**
```
devices/{device_id}/errors/
```

---

## 📊 Response Format

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
  "timestamp": "2026-01-25T20:31:00...",
  "device_id": "hp-XXXXXXXX"
}
```

---

## 🧪 Testing via Firebase Console

1. Go to: https://console.firebase.google.com
2. Select: **harvest-hub** project
3. Click: **Realtime Database**
4. Navigate to: `devices/hp-XXXXXXXX/commands`
5. Click: **+** (Add child)
6. Name: `cmd-001`
7. Paste command JSON as value
8. Click: **Add**

Watch response appear in `responses/` folder!

---

## 🐛 Verify Setup

Check if device registered:

```bash
ssh monkphx@192.168.1.233
sudo journalctl -u harvestpilot-raspserver -n 20
```

Should see:
```
Device registered successfully: hp-XXXXXXXX
Firebase listeners started for device: hp-XXXXXXXX
```

Check device in Firebase:
```
devices/
└── hp-XXXXXXXX/
    ├── device_id: "hp-XXXXXXXX"
    ├── status: "online"
    └── capabilities: {...}
```

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| Device not registering | Check Firebase credentials, check service restart logs |
| Commands not executing | Verify device_id, check command JSON format, watch Pi logs |
| GPIO not responding | Verify pin number, check if pin already in use, test manually |
| No response in Firebase | Check device is online, watch Pi logs for errors |
| Timeout errors | Check Firebase rules, increase timeout, check network |

---

## 📚 Full Documentation

See: [FIREBASE_CONTROL_INTEGRATION.md](./FIREBASE_CONTROL_INTEGRATION.md)

---

## 💡 Examples

**Webapp integration:**
```javascript
async function sendCommand(deviceId, command) {
  const id = `cmd-${Date.now()}`;
  await firebase.database()
    .ref(`devices/${deviceId}/commands/${id}`)
    .set(command);
  
  return new Promise((resolve) => {
    firebase.database()
      .ref(`devices/${deviceId}/responses/${id}`)
      .on('value', (snap) => {
        if (snap.exists()) resolve(snap.val());
      });
  });
}

// Usage
const result = await sendCommand('hp-XXXXXXXX', {
  type: 'pump',
  action: 'start',
  speed: 80
});
```

---

## 🎯 What's Supported

✅ GPIO pin on/off  
✅ GPIO PWM (analog control)  
✅ Pump start/stop/pulse  
✅ Lights on/off with brightness  
✅ Harvest belt per-tray control  
✅ Sensor reading on demand  
✅ Device configuration updates  
✅ Real-time telemetry  
✅ Error logging  
✅ Pin tracking  

---

## 📱 Next: Webapp Integration

See [harvestpilot-webapp](../../harvestpilot-webapp) for complete web app integration examples.
