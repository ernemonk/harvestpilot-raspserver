"""
Firebase Control Integration Guide and Examples

This module shows how to integrate Firebase listeners into your RaspServer main.py

STRUCTURE:
```
src/
├── core/
│   └── rasp_server.py      (Main server class)
├── services/
│   ├── firebase_listener.py (NEW - Command listener)
│   └── device_manager.py    (NEW - Device registration)
└── controllers/
    ├── irrigation.py
    ├── lighting.py
    ├── harvest.py
    └── sensors.py
```

USAGE IN MAIN.PY:

from src.services.firebase_listener import FirebaseDeviceListener
from src.services.device_manager import DeviceManager
from src.core import RaspServer

# In RaspServer.__init__:
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

# In RaspServer.start():
await self.device_manager.register_device()
await self.firebase_listener.start_listening()
"""

# FIREBASE COMMAND EXAMPLES FOR TESTING
# Send these via Firebase Console or REST API

PUMP_CONTROL_EXAMPLES = [
    {
        "description": "Start pump at 80% speed",
        "command": {
            "type": "pump",
            "action": "start",
            "speed": 80
        }
    },
    {
        "description": "Stop pump",
        "command": {
            "type": "pump",
            "action": "stop"
        }
    },
    {
        "description": "Pulse pump for 10 seconds at 50%",
        "command": {
            "type": "pump",
            "action": "pulse",
            "speed": 50,
            "duration": 10
        }
    }
]

LIGHTS_CONTROL_EXAMPLES = [
    {
        "description": "Turn lights on at 100% brightness",
        "command": {
            "type": "lights",
            "action": "on",
            "brightness": 100
        }
    },
    {
        "description": "Turn lights on at 50% brightness",
        "command": {
            "type": "lights",
            "action": "on",
            "brightness": 50
        }
    },
    {
        "description": "Turn lights off",
        "command": {
            "type": "lights",
            "action": "off"
        }
    }
]

PIN_CONTROL_EXAMPLES = [
    {
        "description": "Turn GPIO 17 high (on)",
        "command": {
            "type": "pin_control",
            "pin": 17,
            "action": "on"
        }
    },
    {
        "description": "Turn GPIO 17 low (off)",
        "command": {
            "type": "pin_control",
            "pin": 17,
            "action": "off"
        }
    },
    {
        "description": "Turn GPIO 27 on for 5 seconds then auto-off",
        "command": {
            "type": "pin_control",
            "pin": 27,
            "action": "on",
            "duration": 5
        }
    }
]

PWM_CONTROL_EXAMPLES = [
    {
        "description": "Set GPIO 17 PWM to 75% duty cycle at 1000Hz",
        "command": {
            "type": "pwm_control",
            "pin": 17,
            "duty_cycle": 75,
            "frequency": 1000
        }
    },
    {
        "description": "Set GPIO 18 PWM to 50% (light dimming)",
        "command": {
            "type": "pwm_control",
            "pin": 18,
            "duty_cycle": 50
        }
    },
    {
        "description": "Set GPIO 2 PWM to 100% (full speed motor)",
        "command": {
            "type": "pwm_control",
            "pin": 2,
            "duty_cycle": 100,
            "frequency": 1000
        }
    }
]

HARVEST_CONTROL_EXAMPLES = [
    {
        "description": "Start belt 1 at 50% speed",
        "command": {
            "type": "harvest",
            "action": "start",
            "belt_id": 1,
            "speed": 50
        }
    },
    {
        "description": "Stop belt 3",
        "command": {
            "type": "harvest",
            "action": "stop",
            "belt_id": 3
        }
    },
    {
        "description": "Move belt 2 to home position",
        "command": {
            "type": "harvest",
            "action": "position",
            "belt_id": 2,
            "position": "home"
        }
    }
]

SENSOR_READ_EXAMPLES = [
    {
        "description": "Read temperature sensor",
        "command": {
            "type": "sensor_read",
            "sensor": "temperature"
        }
    },
    {
        "description": "Read humidity sensor",
        "command": {
            "type": "sensor_read",
            "sensor": "humidity"
        }
    },
    {
        "description": "Read soil moisture",
        "command": {
            "type": "sensor_read",
            "sensor": "soil_moisture"
        }
    }
]

DEVICE_CONFIG_EXAMPLES = [
    {
        "description": "Enable auto irrigation",
        "command": {
            "type": "device_config",
            "config": {
                "AUTO_IRRIGATION_ENABLED": True
            }
        }
    },
    {
        "description": "Update sensor reading interval to 10 seconds",
        "command": {
            "type": "device_config",
            "config": {
                "SENSOR_READING_INTERVAL": 10
            }
        }
    }
]

# FIREBASE DATABASE STRUCTURE

DATABASE_STRUCTURE = """
Realtime Database:

devices/
├── hp-XXXXXXXX/              (Device ID)
│   ├── device_id: "hp-XXXXXXXX"
│   ├── status: "online"
│   ├── registered_at: "2026-01-25T..."
│   ├── last_seen: "2026-01-25T..."
│   ├── platform: "raspberry_pi"
│   ├── capabilities: {...}
│   ├── hardware: {...}
│   │
│   ├── commands/              (INCOMING)
│   │   ├── cmd-001: {...}
│   │   └── cmd-002: {...}
│   │
│   ├── responses/             (OUTGOING)
│   │   ├── cmd-001: {
│   │   │   "status": "success",
│   │   │   "data": {...},
│   │   │   "timestamp": "..."
│   │   │}
│   │   └── cmd-002: {...}
│   │
│   ├── telemetry/            (SENSOR DATA)
│   │   ├── sensors: {
│   │   │   "temperature": 72.5,
│   │   │   "humidity": 65.0,
│   │   │   "soil_moisture": 75.0
│   │   │}
│   │   ├── actuators: {...}
│   │   └── timestamp: "..."
│   │
│   ├── pins/                 (GPIO TRACKING)
│   │   ├── 17: {
│   │   │   "name": "Pump PWM",
│   │   │   "type": "pwm",
│   │   │   "purpose": "irrigation",
│   │   │   "state": {"value": 80, "mode": "pwm"}
│   │   │}
│   │   ├── 18: {...}
│   │   └── ...
│   │
│   ├── errors/               (ERROR LOG)
│   │   ├── error-001: {
│   │   │   "type": "sensor_error",
│   │   │   "message": "DHT22 read failed",
│   │   │   "timestamp": "..."
│   │   │}
│   │   └── ...
│   │
│   └── logs/                 (ACTIVITY LOG)
│       ├── log-001: {...}
│       └── ...
│
└── hp-YYYYYYYY/              (Another device)
    └── ...

registration_requests/
├── hp-XXXXXXXX: {
│   "request_timestamp": "2026-01-25T...",
│   "requesting_app": "harvestpilot-webapp"
│}
└── ...
"""

# HOW TO TEST VIA FIREBASE CONSOLE

TESTING_STEPS = """
1. Go to: https://console.firebase.google.com
2. Select: harvest-hub project
3. Click: Realtime Database
4. Navigate to: devices/hp-XXXXXXXX/commands
5. Click: + (Add child)
6. Name: cmd-001
7. Value: Paste any command from examples above
8. Click: Add

Then check:
- Pi logs: sudo journalctl -u harvestpilot-raspserver -f
- Firebase: responses/ folder for command result
"""

# HOW TO SEND COMMANDS FROM WEBAPP

WEBAPP_INTEGRATION = """
// In harvestpilot-webapp, send command like:

const sendCommand = async (deviceId, command) => {
  const commandId = `cmd-${Date.now()}`;
  
  // Write command to Firebase
  await database.ref(`devices/${deviceId}/commands`).push({
    id: commandId,
    ...command,
    sent_at: new Date().toISOString()
  });
  
  // Wait for response
  return new Promise((resolve) => {
    database.ref(`devices/${deviceId}/responses/${commandId}`)
      .on('value', (snapshot) => {
        if (snapshot.exists()) {
          resolve(snapshot.val());
        }
      });
  });
};

// Example usage:
const result = await sendCommand('hp-XXXXXXXX', {
  type: 'pump',
  action: 'start',
  speed: 80
});

console.log(result); // { status: 'success', data: {...} }
"""

if __name__ == "__main__":
    import json
    
    print("=" * 80)
    print("FIREBASE CONTROL INTEGRATION EXAMPLES")
    print("=" * 80)
    
    print("\n📋 PUMP CONTROL:")
    for example in PUMP_CONTROL_EXAMPLES:
        print(f"\n  {example['description']}:")
        print(f"  {json.dumps(example['command'], indent=4)}")
    
    print("\n\n💡 LIGHTS CONTROL:")
    for example in LIGHTS_CONTROL_EXAMPLES:
        print(f"\n  {example['description']}:")
        print(f"  {json.dumps(example['command'], indent=4)}")
    
    print("\n\n🔌 PIN CONTROL (GPIO):")
    for example in PIN_CONTROL_EXAMPLES:
        print(f"\n  {example['description']}:")
        print(f"  {json.dumps(example['command'], indent=4)}")
    
    print("\n\n⚡ PWM CONTROL:")
    for example in PWM_CONTROL_EXAMPLES:
        print(f"\n  {example['description']}:")
        print(f"  {json.dumps(example['command'], indent=4)}")
    
    print("\n\n🌾 HARVEST BELT CONTROL:")
    for example in HARVEST_CONTROL_EXAMPLES:
        print(f"\n  {example['description']}:")
        print(f"  {json.dumps(example['command'], indent=4)}")
    
    print("\n\n📊 SENSOR READ:")
    for example in SENSOR_READ_EXAMPLES:
        print(f"\n  {example['description']}:")
        print(f"  {json.dumps(example['command'], indent=4)}")
    
    print("\n\n⚙️ DEVICE CONFIGURATION:")
    for example in DEVICE_CONFIG_EXAMPLES:
        print(f"\n  {example['description']}:")
        print(f"  {json.dumps(example['command'], indent=4)}")
    
    print("\n\n" + "=" * 80)
    print("DATABASE STRUCTURE")
    print("=" * 80)
    print(DATABASE_STRUCTURE)
    
    print("\n\n" + "=" * 80)
    print("TESTING VIA FIREBASE CONSOLE")
    print("=" * 80)
    print(TESTING_STEPS)
    
    print("\n\n" + "=" * 80)
    print("WEBAPP INTEGRATION")
    print("=" * 80)
    print(WEBAPP_INTEGRATION)
