# HarvestPilot RaspServer — Tasks

Prioritized, executable tasks. Do them in order.

---

## CRITICAL — System is Broken Without These

### 1. Fix Invalid GPIO Pins (28, 29)
**Status:** NOT DONE
**What:** GPIO 28 and 29 are not valid BCM pins on Raspberry Pi. Motor 4 home sensor (pin 28) and Motor 5 home sensor (pin 29) will throw `ValueError` when `GPIO.setup()` is called on real hardware.
**Where:** [src/config.py](../src/config.py) — `MOTOR_PINS` list
**Action:** Pick valid, unused BCM pins. Available after current assignments: GPIO 0, GPIO 1 (use with caution — I2C). Or physically rewire to available pins.
**Impact:** Server crashes on boot if these pins are initialized.

### 2. Add Sensor Reading Loop
**Status:** NOT DONE
**What:** `SensorService.read_all()` exists and works, but is NEVER called. No sensor data (temperature, humidity, water level) is ever collected or published. The Pi connects to Firebase and sends heartbeats, but never reads a single sensor.
**Where:** [src/core/server.py](../src/core/server.py) — needs a `_sensor_reading_loop()` async task added to the `tasks` list in `start()`.
**Action:**
```python
# In server.py start(), add to tasks list:
tasks = [
    self._heartbeat_loop(),
    self._sensor_reading_loop(),  # ADD THIS
]

# Add the method:
async def _sensor_reading_loop(self):
    while self.running:
        try:
            readings = self.sensors.read_all()
            if readings:
                await self.firebase.publish_sensor_data(readings)
                self.database.save_sensor_reading(readings)
        except Exception as e:
            logger.error(f"Sensor read error: {e}")
        interval = self.config_manager.get_sensor_read_interval()
        await asyncio.sleep(interval)
```
**Impact:** Without this, the webapp shows NO environmental data. Temperature, humidity, water level — all blank.

### 3. Set `hardware_state_sync_interval_s` in Firestore
**Status:** NOT DONE
**What:** The new configurable Firestore write interval needs to be set in Firestore. The Pi reads this from `devices/{serial}/config/intervals/hardware_state_sync_interval_s`.
**Where:** Firestore Console → `devices/100000002acfd839/config/intervals`
**Action:** Add field `hardware_state_sync_interval_s` with value (number). Start with `30` (every 30 seconds). Adjust as needed.
**Impact:** Without this, falls back to default 30s. Not broken, but you should set it explicitly.

---

## HIGH — Production Reliability

### 4. Wire In FailsafeManager
**Status:** NOT DONE
**What:** `FailsafeManager` (246 lines) is complete but never instantiated. It checks water level (prevent dry pump), temperature (overheat protection), and humidity (mold prevention). For production crops, this is essential.
**Where:** [src/hardware/failsafe.py](../src/hardware/failsafe.py) — exists, needs to be instantiated in `server.py`
**Action:**
- Import `FailsafeManager` in `server.py`
- Create instance in `__init__`
- Run failsafe checks in the sensor reading loop
- Wire failsafe triggers to irrigation/lighting controllers (e.g., kill pump if water level critical)

### 5. Wire In SyncService
**Status:** NOT DONE
**What:** `SyncService` (204 lines) is complete. It batch-syncs local SQLite data (sensor readings, alerts, operations) to Firestore every 30 minutes. Without this, local data never reaches the cloud.
**Where:** [src/sync/sync_service.py](../src/sync/sync_service.py)
**Action:**
- Import in `server.py`
- Start as a background task in `start()`
- Interval is already configurable via `config_manager.get_sync_interval()`

### 6. Connect Relay Pins to Controllers
**Status:** NOT DONE
**What:** Pump relay (GPIO 19) and LED relay (GPIO 13) are listed in config and controlled by `GPIOActuatorController`, but `IrrigationController` and `LightingController` only drive PWM pins (17, 18). The relay should be switched ON before PWM starts and OFF when PWM stops.
**Where:** [src/controllers/irrigation.py](../src/controllers/irrigation.py), [src/controllers/lighting.py](../src/controllers/lighting.py)
**Action:**
- In `IrrigationController.start()`: set GPIO 19 HIGH before starting PWM
- In `IrrigationController.stop()`: set GPIO 19 LOW after stopping PWM
- Same pattern for lighting with GPIO 13

### 7. Implement Soil Moisture Sensor
**Status:** NOT DONE
**What:** `SensorController.read_all()` returns `soil_moisture: 70.0` hardcoded. No ADC is connected. Soil moisture sensors output analog signals — the Pi has no analog inputs.
**Where:** [src/controllers/sensors.py](../src/controllers/sensors.py)
**Action:**
- Get an ADC module (ADS1115 recommended, ~$5, I2C interface)
- Wire soil moisture sensor through ADC
- Install `adafruit-circuitpython-ads1x15` package
- Replace hardcoded `70.0` with real ADC reading
**Hardware needed:** ADS1115 ADC module + soil moisture probe

---

## MEDIUM — Code Health

### 8. Delete Dead Code Files
**Status:** NOT DONE
**What:** Multiple files that are broken, unused, or redundant:
- `src/services/firebase_listener.py` — uses wrong API (Pyrebase), never instantiated
- `src/services/device_manager.py` — partially broken, never instantiated
- `src/services/firebase_control_examples.py` — documentation, not code
- Root-level `controllers/`, `services/`, `utils/` shims — fragile, one broken
- `src/utils/pin_config.py` (889 lines), `config_loader.py`, `dynamic_config_loader.py`, `module_config.py`, `gpio_scheduler.py`, `schedule_examples.py` — ~1,700 lines of unused code
- `src/admin/clear_devices.py` — broken path reference
**Action:** Delete all of the above. Everything that matters is in `src/core/`, `src/controllers/`, `src/services/` (the working ones), `src/models/`, `src/storage/`.

### 9. Fix ConfigManager Missing Default Values
**Status:** NOT DONE
**What:** `get_metrics_interval()` and `get_aggregation_interval()` fall back to `DEFAULT_INTERVALS` dict, but those keys don't exist in `DEFAULT_INTERVALS`. Returns `None` instead of a number.
**Where:** [src/services/config_manager.py](../src/services/config_manager.py)
**Action:** Either add all interval keys to `DEFAULT_INTERVALS` with sensible values, or change the fallback to hardcoded numbers:
```python
def get_metrics_interval(self) -> float:
    return self.intervals.get("metrics_interval_s", 60)

def get_aggregation_interval(self) -> float:
    return self.intervals.get("aggregation_interval_s", 60)
```

### 10. Fix Duplicate SQLite Database Systems
**Status:** NOT DONE
**What:** Two separate SQLite systems exist:
- `DatabaseService` (740 lines) — used by the server, writes to one SQLite file
- `LocalDatabase` (667 lines) — used by ConfigManager, writes to a different SQLite file
**Where:** [src/services/database_service.py](../src/services/database_service.py) and [src/storage/local_db.py](../src/storage/local_db.py)
**Action:** Consolidate into one database. `LocalDatabase` should be the single SQLite interface. `DatabaseService` methods should delegate to it.

### 11. Implement Motor Homing Logic
**Status:** NOT DONE
**What:** Motor home/end sensor pins are allocated in config but `HarvestController` has no homing logic. Motors can run but have no position awareness — they don't know when they've reached the end or returned home.
**Where:** [src/controllers/harvest.py](../src/controllers/harvest.py)
**Action:** Add methods:
- `home_belt(tray_id)` — run motor until home sensor triggers
- `run_to_end(tray_id)` — run motor until end sensor triggers
- Change home/end pins from OUTPUT to INPUT in config and GPIO setup

---

## LOW — Nice to Have

### 12. Add `sensor_read_interval_s` to Firestore Config
**Status:** NOT DONE
**What:** The sensor reading interval should be configurable from Firestore like the other intervals.
**Where:** Firestore Console → `devices/100000002acfd839/config/intervals`
**Action:** Add field `sensor_read_interval_s` with a number value (e.g., `5` for every 5 seconds).

### 13. Add systemd Service File to Repo
**Status:** NOT DONE
**What:** Auto-deploy restarts `harvestpilot-raspserver.service`, but that unit file isn't in the repo. If the Pi is reimaged, the service needs to be manually recreated.
**Where:** `deployment/`
**Action:** Create `deployment/harvestpilot-raspserver.service` with the proper `ExecStart`, `WorkingDirectory`, `User`, etc.

### 14. Secure Webhook Endpoint
**Status:** NOT DONE
**What:** `github-webhook-receiver.py` uses `"change-me-in-production"` as the webhook secret. No SSL.
**Where:** [deployment/github-webhook-receiver.py](../deployment/github-webhook-receiver.py)
**Action:** Set a real GitHub webhook secret. Consider adding nginx reverse proxy with SSL.

### 15. Add Tests for GPIO Controller
**Status:** NOT DONE
**What:** The `GPIOActuatorController` is the most critical component but has zero tests. In simulation mode (`SIMULATE_HARDWARE=True`), it can run on any machine.
**Where:** `tests/`
**Action:** Write tests for:
- State listener receives Firestore change → correct pin state set
- Command listener processes `pin_control` → correct pin toggled
- Mismatch detection fires on disagreement
- `_apply_to_hardware` reads back and verifies
- `get_pin_states()` returns correct dual-state format

### 16. Clean Up Firestore gpioState Schema
**Status:** NOT DONE
**What:** Pin 18 (LED PWM) has extra legacy fields (`createdAt`, `gpioPin`, `lastUpdated`, `subtype`, `type`) that other pins don't have. Schema should be consistent.
**Where:** Firestore Console → `devices/100000002acfd839/gpioState/18`
**Action:** Delete the extra fields so pin 18 matches the schema of all other pins.
