# Firestore Configuration Setup for HarvestPilot

## ✅ COMPLETE: Firestore-Only Configuration

All hardcoded sensor and GPIO pin definitions have been removed. Your Firestore database is now the **single source of truth** for all device configuration.

---

## Current Firestore Structure

Your device document in Firestore at `devices/100000002acfd839/` already has the `gpioState` field:

```json
{
  "100000002acfd839": {
    "deviceId": "raspserver-001",
    "hardware_serial": "100000002acfd839",
    "gpioState": {
      "17": {
        "function": "light",
        "mode": "output",
        "state": false,
        "lastUpdated": 1770504050871
      },
      "18": {
        "function": "pump",
        "mode": "output",
        "state": false,
        "lastUpdated": 1770504050871
      },
      "dht22": {
        "function": "temperature_humidity",
        "mode": "input",
        "pin": 4
      },
      "water_level": {
        "function": "water_level",
        "mode": "input",
        "pin": 23
      }
    }
  }
}
```

---

## How It Works Now

### Startup Sequence

```
1. Service starts (main.py)
   ↓
2. server_init.py runs
   - Reads Pi hardware serial
   - Checks if device exists in Firestore
   - If NOT EXISTS: Creates empty document with empty gpioState: {}
   - If EXISTS: Leaves document unchanged (doesn't overwrite)
   ↓
3. SensorService initializes
   - Receives Firestore DB connection
   ↓
4. First sensor read
   - Calls _get_configured_sensors()
   - Reads from Firestore: devices/{hardware_serial}/gpioState/
   - Extracts all pins with mode: "input"
   - Uses those pins for all sensor reads
   ↓
5. Service runs
   - Reads sensors from the pins defined in Firestore
   - Publishes data to Firebase
```

---

## To Configure Sensors

### Via Web App (RECOMMENDED)

1. Open HarvestPilot web app
2. Navigate to **Device Configuration** or **GPIO Setup**
3. Add input sensors:
   - **Temperature/Humidity**: GPIO 4 (DHT22 data pin)
   - **Water Level**: GPIO 23 (water level sensor input)
   - Any other sensors you need
4. Save configuration
5. Restart the Pi service

### Via Firestore Console (IF web app not available)

Go to Firebase Console → Cloud Firestore → Databases → `devices/{device_id}/gpioState/`

Add new documents for each sensor:

**Temperature/Humidity Sensor:**
```json
{
  "function": "temperature_humidity",
  "mode": "input",
  "pin": 4
}
```

**Water Level Sensor:**
```json
{
  "function": "water_level", 
  "mode": "input",
  "pin": 23
}
```

---

## Key Points

### ✅ What Changed
- ❌ No more `SENSOR_DHT22_PIN` in config.py
- ❌ No more `SENSOR_WATER_LEVEL_PIN` in config.py
- ❌ No more `_get_default_sensors()` fallback
- ✅ ALL configuration from Firestore `gpioState`

### ✅ What This Means
- One source of truth: Firestore
- Easy to reconfigure without code changes
- Different hardware? Just update Firestore
- Web app controls everything

### ✅ Error Handling
If sensors not configured:
- Service logs: `⚠️ No input sensors configured in Firestore gpioState`
- Sensor loop still runs but reads no sensors
- No sensor data published to Firebase
- Service stays stable

### ⚠️ Important
- **You MUST configure sensors in Firestore BEFORE the service reads them**
- Restart service after changing Firestore config
- Current Firestore has correct config already - should work immediately

---

## Next Steps

1. **Verify Current Config**
   - Check Firestore: `devices/100000002acfd839/gpioState/`
   - Should have `dht22` (pin 4) and `water_level` (pin 23)

2. **Restart Service**
   ```bash
   sudo systemctl restart harvestpilot-raspserver.service
   ```

3. **Check Logs**
   ```bash
   sudo journalctl -u harvestpilot-raspserver.service -f
   ```
   
   You should see:
   ```
   ✅ Loaded sensor configuration from Firestore: ['temperature_humidity', 'water_level']
      - temperature_humidity: GPIO 4
      - water_level: GPIO 23
   ```

4. **Verify Sensor Reads**
   - Check Firebase: `/devices/100000002acfd839/sensors/latest/`
   - Should see temperature, humidity, water_level updates

---

## Troubleshooting

### Service won't start or hangs on sensor read
**Cause:** No Firestore connection or invalid config

**Fix:**
1. Check Firestore is reachable
2. Verify Firebase credentials are valid
3. Check device doc exists: `devices/100000002acfd839/`
4. Logs should show: `✅ Loaded sensor configuration from Firestore`

### Sensors show no data
**Cause:** Firestore config exists but sensor still has issues

**Fix:**
1. Check logs: `sudo journalctl -u harvestpilot-raspserver.service | grep -i sensor`
2. Verify GPIO pins in Firestore match actual hardware
3. Check DHT22/water sensor hardware is connected
4. Restart service after any Firestore changes

### "CRITICAL: Device not found in Firestore"
**Cause:** Device never registered

**Fix:**
1. Service will auto-register on startup
2. Check Firestore collection: `devices/`
3. Look for your hardware_serial as document ID
4. Restart service if missing

---

## Summary

**Old way (REMOVED):**
- Pins hardcoded in config.py
- Pins hardcoded in server_init.py  
- Pins hardcoded in sensors.py
- 3 places to change if you want different hardware

**New way (FIRESTORE ONLY):**
- Device auto-registers on startup
- User configures pins in web app
- Service reads from Firestore on startup
- Change pins anytime from web app
- No code changes needed

This is much cleaner! 🎉
