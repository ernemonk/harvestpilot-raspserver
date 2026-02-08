# Instructions to Configure Sensors in Firestore

## Current Status

✅ Service is running
✅ Reading configuration from Firestore  
❌ No sensors found in Firestore (because server_init.py now registers empty gpioState)

## What Happened

When you removed the hardcoded sensors from `server_init.py`, the device registration now creates an **empty** `gpioState: {}`.

This is correct! The idea is that YOU configure the sensors via the web app. However, since your web app setup might not be complete yet, here's how to add the sensors manually:

---

## Option 1: Add Sensors via Firebase Console (MANUAL)

Go to: **Firebase Console → Cloud Firestore → devices → 100000002acfd839**

In the `gpioState` field, add these documents:

### Add first sensor: "dht22"
- Type: **Map**
- Document ID: **dht22**
- Fields:
  - `function` (string): `temperature_humidity`
  - `mode` (string): `input`
  - `pin` (number): `4`

### Add second sensor: "water_level"
- Type: **Map**
- Document ID: **water_level`  
- Fields:
  - `function` (string): `water_level`
  - `mode` (string): `input`
  - `pin` (number): `23`

---

## Option 2: Manually Update Firestore Document (via CLI or script)

Your current Firestore structure should look like:

```json
{
  "devices": {
    "100000002acfd839": {
      "deviceId": "raspserver-001",
      "hardware_serial": "100000002acfd839",
      "gpioState": {
        "17": { "function": "light", "mode": "output", ... },
        "18": { "function": "pump", "mode": "output", ... },
        "4": {
          "function": "temperature_humidity",
          "mode": "input",
          "pin": 4
        },
        "23": {
          "function": "water_level",
          "mode": "input",
          "pin": 23
        }
      }
    }
  }
}
```

Note the difference from before:
- **OLD** (hardcoded): `"dht22": { "pin": 4 }`
- **NEW** (Firestore config): `"4": { "pin": 4 }` - Using pin as the key

Actually, either should work. The code looks for `mode: "input"` and extracts the function and pin.

---

## Option 3: Revert to Having Default Sensors (If You Want)

If you want to go back to having default sensors in the code, you can add them back to `server_init.py` in the `gpioState` field. This is NOT recommended - web app control is better.

---

## Next Steps

1. **Add sensors to Firestore** using Option 1 or 2 above
2. **Restart the service**:
   ```bash
   sudo systemctl restart harvestpilot-raspserver.service
   ```
3. **Check logs** for sensor configuration:
   ```bash
   sudo journalctl -u harvestpilot-raspserver.service -f | grep -i sensor
   ```
4. You should see:
   ```
   ✅ Loaded sensor configuration from Firestore: ['temperature_humidity', 'water_level']
      - temperature_humidity: GPIO 4
      - water_level: GPIO 23
   ```

This ensures sensors are always configured **via your web app**, not hardcoded in the application.
