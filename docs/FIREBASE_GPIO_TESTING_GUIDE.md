# HarvestPilot RaspServer - Comprehensive Status Analysis

**Date**: January 31, 2026  
**Status**: Ready for Firebase GPIO Testing  
**Documentation**: Complete with Enhanced Logging

---

## 📊 Project Overview

You have a Raspberry Pi server application designed to:
- ✅ Control hardware via GPIO pins (pump, lights, motors)
- ✅ Receive real-time commands from Firestore/Firebase
- ✅ Register device and track state in Firebase
- ✅ Execute irrigation, lighting, and harvest automation
- ✅ Support both simulated and real GPIO hardware

**Mode**: Currently configured for **SIMULATION MODE** (can run anywhere)

---

## 🎯 Architecture Summary

### Core Components

```
harvestpilot-raspserver/
├── main.py                          # Entry point
├── src/
│   ├── core/                        # Main server logic
│   ├── services/                    # Firebase & GPIO services
│   │   ├── firebase_listener.py     # Listens for Firestore commands ✅ ENHANCED
│   │   ├── device_manager.py        # Device registration & status ✅ ENHANCED
│   │   ├── gpio_actuator_controller.py  # GPIO pin control
│   │   └── ...other services
│   ├── controllers/                 # Hardware controllers
│   │   ├── irrigation.py
│   │   ├── lighting.py
│   │   ├── harvest.py
│   │   └── sensors.py
│   ├── config.py                    # Configuration
│   └── utils/
│       ├── logger.py                # Logging setup
│       └── ...utilities
├── test_local_firebase_commands.py  # ✅ NEW TEST SCRIPT
└── docs/                            # Documentation
```

---

## 🔍 What's Working

### ✅ Firebase Integration
- Device listens for commands at: `devices/{DEVICE_ID}/commands/`
- Supports command types:
  - `pin_control` - Direct GPIO on/off
  - `pwm_control` - PWM duty cycle control
  - `pump` - Pump control (start/stop/pulse)
  - `lights` - Light control (on/off + brightness)
  - `harvest` - Motor belt control
  - `device_config` - Configuration updates
  - `sensor_read` - On-demand sensor readings

### ✅ Device Registration
- Device automatically registers itself in Firebase on startup
- Stores:
  - Hardware IDs (Pi serial, MAC address)
  - GPIO configuration
  - Capabilities/features
  - Status and metadata

### ✅ Real-time Command Processing
- Firebase listener detects new commands instantly
- Routes commands to appropriate handlers
- Executes GPIO operations
- Sends responses back to Firestore

### ✅ Response Tracking
- Each command gets a response written to: `devices/{DEVICE_ID}/responses/{command_id}`
- Response includes status, data, timestamps

---

## 🆕 Logging Enhancements Added

### Enhanced Logging in `firebase_listener.py`

Comprehensive logging for command lifecycle:

```
[FIREBASE LISTENER] 🔔 NEW COMMAND DETECTED from Firebase
[COMMAND PROCESSOR] 🚀 Processing command: pin_control (ID: test_1)
[PIN CONTROL] 🔌 GPIO17 control requested: ON
[PIN CONTROL] ⚡ Setting GPIO17 to HIGH (ON)
[PIN CONTROL] ✅ PIN CONTROL SUCCESS: GPIO17 -> ON
[RESPONSE] 📤 Sending response for command test_1
[RESPONSE] ✅ Response written to config device ID path
```

**Key Logging Points**:
- Command reception & validation
- Handler routing
- GPIO state changes
- Duration/auto-off operations
- Response sending
- Error conditions with full stack traces

### Enhanced Logging in `device_manager.py`

Device lifecycle logging:

```
[DEVICE REGISTRATION] 🔧 Starting device registration process...
[DEVICE REGISTRATION] 📱 Pi Serial: XXXX, Mac: XX:XX:XX:XX:XX:XX
[DEVICE REGISTRATION] 📝 Writing registration to: devices/{DEVICE_ID}
[DEVICE REGISTRATION] ✅ DEVICE REGISTRATION COMPLETE
[DEVICE STATUS] ✓ Device status updated: online
```

### Enhanced Logging in `main.py`

Server lifecycle logging:

```
======================================================================
🎬 HARVEST PILOT RASPSERVER - STARTING UP
======================================================================
======================================================================
🚀 STARTING RASP SERVER CORE...
======================================================================
======================================================================
✅ SERVER SHUTDOWN COMPLETE
======================================================================
```

---

## 🧪 Testing Your Setup

### Step 1: Run the Server Locally (Simulation Mode)

```bash
cd /Users/user/Projects/HarvestPilot/Repos/harvestpilot-raspserver

# Run with simulation (no GPIO hardware needed)
SIMULATE_HARDWARE=true python main.py
```

**Expected Output**:
```
2026-01-31 10:15:23 - root - INFO - ======================================================================
2026-01-31 10:15:23 - root - INFO - 🎬 HARVEST PILOT RASPSERVER - STARTING UP
2026-01-31 10:15:23 - root - INFO - ======================================================================
2026-01-31 10:15:24 - src.services.device_manager - INFO - [DEVICE REGISTRATION] ✅ DEVICE REGISTRATION COMPLETE
2026-01-31 10:15:25 - src.services.firebase_listener - INFO - [FIREBASE LISTENER] ✅ Command listener STARTED for raspserver-001
```

### Step 2: Send Test Commands

**Option A: Using Test Script (Recommended)**

```bash
# In another terminal, run the test script
python test_local_firebase_commands.py
```

This will:
1. Start the server
2. Run automated GPIO tests
3. Offer interactive command menu

**What to Test**:
- GPIO 17 ON/OFF
- GPIO 27 ON with auto-off timer
- Pump start/stop/pulse
- Lights on/off with brightness

**Option B: Send via Firebase Console**

1. Go to Firebase Console → Realtime Database
2. Navigate to: `devices/{your-device-id}/commands/`
3. Add a new command:

```json
{
  "type": "pin_control",
  "pin": 17,
  "action": "on",
  "id": "test-cmd-1"
}
```

### Step 3: Watch the Logs

As commands execute, you'll see detailed logs like:

```
[FIREBASE LISTENER] 🔔 NEW COMMAND DETECTED from Firebase: {'type': 'pin_control', 'pin': 17, 'action': 'on', 'id': 'test-cmd-1'}
[COMMAND PROCESSOR] 🚀 Processing command: pin_control (ID: test-cmd-1)
[COMMAND PROCESSOR] ✓ Handler found for type 'pin_control', executing...
[PIN CONTROL] 🔌 GPIO17 control requested: ON
[PIN CONTROL] 🎭 [SIMULATION MODE] GPIO17 -> ON
[PIN CONTROL] ✅ PIN CONTROL SUCCESS: GPIO17 -> ON
[COMMAND PROCESSOR] ✓ Handler completed successfully for 'pin_control'
[RESPONSE] 📤 Sending response for command test-cmd-1
[RESPONSE] ✅ Response written to config device ID path
[RESPONSE] ✅ RESPONSE COMPLETE: test-cmd-1 -> success
```

### Step 4: Verify Response in Firebase

Check: `devices/{your-device-id}/responses/test-cmd-1`

You should see:
```json
{
  "command_id": "test-cmd-1",
  "command_type": "pin_control",
  "status": "success",
  "data": {
    "pin": 17,
    "action": "on",
    "status": "success"
  },
  "timestamp": "2026-01-31T10:15:47.123456"
}
```

---

## 🔧 Configuration

### Key Settings in `src/config.py`

```python
# Hardware Simulation (essential for testing)
SIMULATE_HARDWARE = True  # Set to False on Raspberry Pi

# Device ID (shows up in Firebase)
DEVICE_ID = "raspserver-001"  # Change as needed

# GPIO Pins
PUMP_PWM_PIN = 17
LED_PWM_PIN = 18
SENSOR_DHT22_PIN = 4

# Logging
LOG_LEVEL = logging.DEBUG  # Full detail
LOG_FILE = "logs/raspserver.log"  # Persisted logs
```

### Enable Firebase Credentials

Make sure you have your Firebase credentials:
```bash
export FIREBASE_CREDENTIALS="/path/to/serviceAccountKey.json"
# OR set in code before importing firebase_admin
```

---

## 📋 Firebase Database Structure

### Command Path
```
devices
├── raspserver-001
│   ├── commands/          ← Write commands here
│   │   ├── cmd-001 {type, pin, action}
│   │   └── cmd-002 {type, ...}
│   ├── responses/         ← Responses appear here
│   │   ├── cmd-001 {status, data, timestamp}
│   │   └── cmd-002 {status, ...}
│   ├── status/            ← Current device status
│   │   └── {online, last_seen, ...}
│   └── gpioState/         ← Current GPIO state
│       ├── 17 {state, lastUpdated}
│       └── 18 {state, lastUpdated}
```

---

## 📝 Log Files

All logs are written to: `logs/raspserver.log`

**Log Levels**:
- `DEBUG`: Everything (for development)
- `INFO`: Important events (✅, 📤, etc.)
- `WARNING`: Issues but continuing (⚠️)
- `ERROR`: Failed operations (❌)

**View live logs**:
```bash
tail -f logs/raspserver.log
```

**Filter for GPIO actions**:
```bash
grep "PIN CONTROL" logs/raspserver.log
```

**Filter for Firebase events**:
```bash
grep "FIREBASE\|COMMAND" logs/raspserver.log
```

---

## 🔌 Testing Scenarios

### Scenario 1: Simple GPIO On/Off
**Goal**: Verify GPIO pin control works

```json
{
  "id": "test-1",
  "type": "pin_control",
  "pin": 17,
  "action": "on"
}
```

**Expected Flow**:
1. Firebase listener detects command
2. Command processor routes to pin_control handler
3. GPIO 17 set HIGH
4. Response sent back with status: "success"

### Scenario 2: GPIO with Auto-Off
**Goal**: Verify timed control works

```json
{
  "id": "test-2",
  "type": "pin_control",
  "pin": 27,
  "action": "on",
  "duration": 5
}
```

**Expected Flow**:
1. GPIO 27 set HIGH
2. Waits 5 seconds
3. GPIO 27 set LOW automatically
4. Logs show "auto-turned off"

### Scenario 3: Pump Control
**Goal**: Verify pump controller integration

```json
{
  "id": "test-3",
  "type": "pump",
  "action": "start",
  "speed": 80
}
```

**Expected Flow**:
1. Pump controller receives start command
2. PWM set to 80%
3. Pump status updated in device_manager
4. Response includes current pump state

### Scenario 4: Multiple Commands
**Goal**: Verify concurrent command handling

Send multiple commands in quick succession. The server should:
- Queue them appropriately
- Process in order
- Return responses for each
- Not lose any commands

---

## 🚨 Troubleshooting

### Issue: Commands Not Received

**Check**:
```bash
# 1. Is server running?
ps aux | grep "python.*main.py"

# 2. Are Firebase credentials valid?
cat $FIREBASE_CREDENTIALS

# 3. Check logs for listener errors
grep "FIREBASE LISTENER" logs/raspserver.log
```

### Issue: Commands Received But Not Executing

**Check**:
```bash
# 1. Is SIMULATE_HARDWARE set correctly?
echo $SIMULATE_HARDWARE

# 2. Check if handler exists
grep "Available handlers:" logs/raspserver.log

# 3. Look for PIN CONTROL errors
grep "PIN CONTROL.*❌" logs/raspserver.log
```

### Issue: No Response in Firebase

**Check**:
```bash
# 1. Look for response sending errors
grep "RESPONSE.*❌" logs/raspserver.log

# 2. Verify Firebase write permissions
# Check Firebase console for security rules

# 3. Check response path format
grep "Writing to: devices" logs/raspserver.log
```

---

## 📊 Real-Time Monitoring

### Monitor Command Flow

```bash
# Terminal 1: Watch logs in real-time
tail -f logs/raspserver.log | grep -E "FIREBASE|COMMAND|PIN"

# Terminal 2: Send test commands
python test_local_firebase_commands.py

# Terminal 3: Watch Firebase in console
# Open: https://console.firebase.google.com/project/YOUR-PROJECT/database
```

### Log Analysis

**Extract command timeline**:
```bash
grep -E "PROCESSING|PIN CONTROL|RESPONSE" logs/raspserver.log | grep "test_1"
```

**Show error sequence**:
```bash
grep "❌\|Error\|Exception" logs/raspserver.log
```

---

## ✅ Validation Checklist

Before considering this "tested and ready":

- [ ] Server starts without errors
- [ ] Device registers in Firebase
- [ ] GPIO ON command executes
- [ ] GPIO OFF command executes
- [ ] GPIO auto-off timer works
- [ ] Pump control works
- [ ] Lights control works
- [ ] Response appears in Firebase for each command
- [ ] Logs show detailed execution flow
- [ ] No permission errors
- [ ] No lost commands

---

## 🎯 Next Steps

1. **Run locally**: `SIMULATE_HARDWARE=true python main.py`
2. **Test GPIO**: Use `test_local_firebase_commands.py`
3. **Deploy to Pi**: Copy code to Raspberry Pi, set `SIMULATE_HARDWARE=false`
4. **Test on hardware**: Run actual GPIO commands
5. **Monitor production**: Keep watching logs for issues

---

## 📚 Key Files Modified

- `src/services/firebase_listener.py` - ✅ Enhanced logging for all command handling
- `src/services/device_manager.py` - ✅ Enhanced device lifecycle logging  
- `main.py` - ✅ Enhanced startup/shutdown logging
- `test_local_firebase_commands.py` - ✅ NEW testing utility

---

## 📞 Support

If commands aren't working:

1. **Check logs**: `tail -f logs/raspserver.log`
2. **Enable debug**: `export LOG_LEVEL=DEBUG`
3. **Test manually**: Use Firebase console to send commands
4. **Verify paths**: Make sure device ID matches in Firebase and config

---

**Last Updated**: January 31, 2026  
**Status**: Ready for Testing  
**Next Phase**: Live GPIO Testing on Raspberry Pi
