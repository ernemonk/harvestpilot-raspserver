# ✅ Implementation Checklist

## 📋 Pre-Integration

- [ ] Read [INTEGRATION_VISUAL_GUIDE.md](INTEGRATION_VISUAL_GUIDE.md)
- [ ] Backup main.py (just in case)
- [ ] Have Firebase credentials ready
- [ ] Know your device ID (hp-XXXXXXXX)
- [ ] SSH access to Pi (for testing)

---

## 🔧 Integration (5 minutes)

### Add Imports
- [ ] Open `harvestpilot-raspserver/main.py`
- [ ] Add import: `from src.services.firebase_listener import FirebaseDeviceListener`
- [ ] Add import: `from src.services.device_manager import DeviceManager`

### Update `__init__()` Method
- [ ] Find where controllers are initialized
- [ ] After controllers, add device manager:
  ```python
  self.device_manager = DeviceManager(device_id=config.DEVICE_ID)
  ```
- [ ] Add Firebase listener:
  ```python
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

### Update `start()` Method
- [ ] Find where async startup code is
- [ ] After setup code, add:
  ```python
  await self.device_manager.register_device()
  await self.firebase_listener.start_listening()
  ```

### Verification
- [ ] Code compiles (no syntax errors)
- [ ] All imports resolve
- [ ] File saves properly

---

## 🚀 Deployment

### Restart Service
- [ ] SSH into Pi: `ssh monkphx@192.168.1.233`
- [ ] Run: `sudo systemctl restart harvestpilot-raspserver`
- [ ] Wait 5 seconds for startup

### Verify Startup
- [ ] Check logs: `sudo journalctl -u harvestpilot-raspserver -n 20`
- [ ] Look for: "Device registered successfully: hp-XXXXXXXX"
- [ ] Look for: "Firebase listeners started for device: hp-XXXXXXXX"
- [ ] No error messages

---

## 🧪 Testing

### Device Registration
- [ ] Go to: https://console.firebase.google.com
- [ ] Select: harvest-hub project
- [ ] Click: Realtime Database
- [ ] Navigate to: `devices/hp-XXXXXXXX/`
- [ ] Verify: device_id exists
- [ ] Verify: status = "online"
- [ ] Verify: capabilities listed

### Test Pump Command
- [ ] In Firebase, create: `devices/hp-XXXXXXXX/commands/cmd-pump-1`
- [ ] Set value:
  ```json
  {
    "type": "pump",
    "action": "start",
    "speed": 80
  }
  ```
- [ ] Check logs: `sudo journalctl -u harvestpilot-raspserver -f`
- [ ] Look for: "Processing command: pump"
- [ ] Look for: "Pump command: start"
- [ ] Check Firebase: `devices/hp-XXXXXXXX/responses/`
- [ ] Verify: Response with status "success"
- [ ] Listen: Pump should start running

### Test Lights Command
- [ ] Create: `devices/hp-XXXXXXXX/commands/cmd-lights-1`
- [ ] Set value:
  ```json
  {
    "type": "lights",
    "action": "on",
    "brightness": 75
  }
  ```
- [ ] Check response in Firebase
- [ ] Verify: Lights turn on at 75%
- [ ] Test off: `{"type": "lights", "action": "off"}`
- [ ] Verify: Lights turn off

### Test GPIO Command
- [ ] Create: `devices/hp-XXXXXXXX/commands/cmd-gpio-1`
- [ ] Set value:
  ```json
  {
    "type": "pin_control",
    "pin": 17,
    "action": "on"
  }
  ```
- [ ] Check response
- [ ] Verify: GPIO 17 goes HIGH
- [ ] Test off: `{"type": "pin_control", "pin": 17, "action": "off"}`
- [ ] Verify: GPIO 17 goes LOW

### Test PWM Command
- [ ] Create: `devices/hp-XXXXXXXX/commands/cmd-pwm-1`
- [ ] Set value:
  ```json
  {
    "type": "pwm_control",
    "pin": 18,
    "duty_cycle": 60
  }
  ```
- [ ] Check response
- [ ] Verify: PWM frequency set correctly

### Test Harvest Command
- [ ] Create: `devices/hp-XXXXXXXX/commands/cmd-harvest-1`
- [ ] Set value:
  ```json
  {
    "type": "harvest",
    "action": "start",
    "belt_id": 1,
    "speed": 50
  }
  ```
- [ ] Check response
- [ ] Verify: Belt 1 starts moving

### Test Sensor Read
- [ ] Create: `devices/hp-XXXXXXXX/commands/cmd-sensor-1`
- [ ] Set value:
  ```json
  {
    "type": "sensor_read",
    "sensor": "temperature"
  }
  ```
- [ ] Check response in `devices/hp-XXXXXXXX/responses/`
- [ ] Verify: Temperature value returned
- [ ] Test humidity: `{"type": "sensor_read", "sensor": "humidity"}`
- [ ] Test soil moisture: `{"type": "sensor_read", "sensor": "soil_moisture"}`
- [ ] Test water level: `{"type": "sensor_read", "sensor": "water_level"}`

### Test Device Config
- [ ] Create: `devices/hp-XXXXXXXX/commands/cmd-config-1`
- [ ] Set value:
  ```json
  {
    "type": "device_config",
    "config": {
      "AUTO_IRRIGATION_ENABLED": true
    }
  }
  ```
- [ ] Check response
- [ ] Verify: Configuration updated

### Check Telemetry
- [ ] Navigate to: `devices/hp-XXXXXXXX/telemetry/`
- [ ] Verify: sensors data (temperature, humidity, etc.)
- [ ] Verify: actuators data (pump, lights, motors)
- [ ] Verify: timestamp is recent

### Check Pin Tracking
- [ ] Navigate to: `devices/hp-XXXXXXXX/pins/`
- [ ] Verify: GPIO pins listed (17, 18, etc.)
- [ ] Verify: Pin states recorded

### Check Error Logging
- [ ] Navigate to: `devices/hp-XXXXXXXX/errors/`
- [ ] If any errors, review them
- [ ] Verify: Error messages are helpful

---

## 🎯 Success Criteria

- ✅ Device registers in Firebase
- ✅ Pump command works
- ✅ Lights command works
- ✅ GPIO command works
- ✅ PWM command works
- ✅ Harvest command works
- ✅ Sensor read works
- ✅ Responses appear in Firebase
- ✅ Telemetry data publishes
- ✅ No errors in logs
- ✅ All 7 command types tested

---

## 📊 Status Report

After completing above:

- [ ] **Device Registration:** Working? YES / NO
- [ ] **Pump Control:** Working? YES / NO
- [ ] **Lights Control:** Working? YES / NO
- [ ] **GPIO Control:** Working? YES / NO
- [ ] **PWM Control:** Working? YES / NO
- [ ] **Harvest Control:** Working? YES / NO
- [ ] **Sensor Reading:** Working? YES / NO
- [ ] **Telemetry:** Publishing? YES / NO
- [ ] **Error Logging:** Recording? YES / NO
- [ ] **Response System:** Working? YES / NO

**Overall Status:** ✅ COMPLETE / 🔴 NEEDS WORK

---

## 🐛 Troubleshooting Checklist

If something isn't working:

### Service Won't Start
- [ ] Check Python syntax in main.py
- [ ] Run: `python3 -m py_compile main.py`
- [ ] Check import paths exist
- [ ] Check permissions on files
- [ ] Restart with: `sudo systemctl restart harvestpilot-raspserver`

### Device Not Registering
- [ ] Check Firebase credentials file exists
- [ ] Check Firebase connection works
- [ ] Check service logs: `sudo journalctl -u harvestpilot-raspserver -n 50`
- [ ] Check Firebase rules allow writes
- [ ] Verify DEVICE_ID in config.py

### Commands Not Executing
- [ ] Check device_id in Firebase path (hp-XXXXXXXX format)
- [ ] Check command JSON syntax is valid
- [ ] Check command type is spelled correctly
- [ ] Check required fields are present
- [ ] Check Pi logs for error messages
- [ ] Verify device status is "online" in Firebase

### No Response in Firebase
- [ ] Check device is online
- [ ] Check command ID exists
- [ ] Look for response in correct path
- [ ] Check Pi logs: `sudo journalctl -u harvestpilot-raspserver -f`
- [ ] Try simpler command first

### GPIO Not Responding
- [ ] Verify pin number is correct (GPIO 17, not pin 11)
- [ ] Check pin isn't already in use
- [ ] Test manually: `gpio mode {pin} out; gpio write {pin} 1`
- [ ] Check permissions: `sudo` required?
- [ ] Verify GPIO library installed

### Timeout Errors
- [ ] Check Firebase connection is stable
- [ ] Increase timeout in webapp code
- [ ] Check network between Pi and Firebase
- [ ] Monitor Firebase write limits

---

## 📞 If Stuck

1. **Check logs first:**
   ```bash
   sudo journalctl -u harvestpilot-raspserver -n 100 | grep -i error
   ```

2. **Check Firebase paths:**
   - Commands: `/devices/{id}/commands/`
   - Responses: `/devices/{id}/responses/`
   - Device: `/devices/{id}/`

3. **Review documentation:**
   - [INTEGRATION_VISUAL_GUIDE.md](INTEGRATION_VISUAL_GUIDE.md) - Integration steps
   - [docs/FIREBASE_CONTROL_INTEGRATION.md](docs/FIREBASE_CONTROL_INTEGRATION.md) - Troubleshooting
   - [CODE_STRUCTURE_ANALYSIS.md](CODE_STRUCTURE_ANALYSIS.md) - How it works

4. **Test manually:**
   ```bash
   # SSH to Pi
   ssh monkphx@192.168.1.233
   
   # Check service running
   sudo systemctl status harvestpilot-raspserver
   
   # Watch logs
   sudo journalctl -u harvestpilot-raspserver -f
   ```

---

## ✨ Next Steps

Once all tests pass:

- [ ] **Integrate webapp** (see webapp documentation)
- [ ] **Add mobile control** (same Firebase API)
- [ ] **Set up automations** (Firebase triggers)
- [ ] **Build dashboard** (real-time monitoring)
- [ ] **Add notifications** (Firebase Cloud Functions)
- [ ] **Expand to more Pis** (same process)

---

## 🎉 Completion

When all checkboxes are checked:

✅ **Firebase Real-time Control System is LIVE**

You can now:
- Control pump from Firebase Console
- Control lights from Firebase Console
- Control GPIO pins from Firebase Console
- Control PWM from Firebase Console
- Control harvest belts from Firebase Console
- Read sensors on demand from Firebase Console
- Monitor device status in real-time
- See telemetry data live
- Track all errors automatically
- Control multiple devices

**No SSH needed!**

---

**Date Started:** _____________  
**Date Completed:** _____________  
**Status:** ✅ COMPLETE

---

*See [FIREBASE_CONTROL_INDEX.md](FIREBASE_CONTROL_INDEX.md) for documentation map*
