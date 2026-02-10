# RFC — harvestpilot-raspserver

> Technical reference for what is currently built and working.
> Last updated: 2025-02-10

## Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python 3 (asyncio) | 3.11+ |
| GPIO | RPi.GPIO | 0.7.1 |
| Sensors | adafruit-circuitpython-dht | latest |
| Backend | firebase-admin | 6.1.0 |
| Local DB | SQLite3 (stdlib) | — |
| Config | python-dotenv | 1.0.1 |

## Architecture

```
Firestore ←→ GPIOActuatorController ←→ RPi.GPIO ←→ Physical Pins
               ↕
         RaspServer (asyncio)
               ↕
    Controllers (Irrigation, Lighting, Harvest)
               ↕
         SensorService → Firestore
```

- **Entry point:** `main.py` → subprocess `server_init.py` → `RaspServer.start()`
- **All real-time.** GPIO state changes come through Firestore `on_snapshot` listeners.
- **No polling for commands.** Commands arrive via real-time `on_snapshot` on `commands` subcollection.
- **Hardware sync loop:** Every 30s (configurable), reads all pins and batch-writes `hardwareState` to Firestore. Also serves as heartbeat.

## Directory Structure

```
src/
├── config.py               # Central config (env vars, pin defs, thresholds)
├── core/
│   └── server.py           # RaspServer — main orchestrator
├── controllers/
│   ├── irrigation.py       # Pump PWM control (GPIO 17)
│   ├── lighting.py         # LED PWM control (GPIO 18)
│   ├── harvest.py          # 6-tray belt motor control
│   └── sensors.py          # DHT22 + sensor reading
├── services/
│   ├── firebase_service.py          # Firebase Admin SDK wrapper
│   ├── gpio_actuator_controller.py  # Real-time Firestore↔GPIO bridge (CORE)
│   ├── schedule_listener.py         # In-memory schedule cache
│   ├── firestore_schedule_listener.py # Real-time schedule change listener
│   ├── sensor_service.py            # Sensor reads + threshold checks
│   ├── automation_service.py        # Local time-based automation loop
│   ├── config_manager.py            # Dynamic interval config from Firestore
│   ├── database_service.py          # Local SQLite logging
│   └── diagnostics.py               # Metrics counters
├── models/
│   ├── sensor_data.py      # SensorReading, ThresholdAlert dataclasses
│   └── command.py          # Command, DeviceStatus dataclasses
├── storage/
│   ├── local_db.py         # SQLite manager (30-day retention)
│   └── models.py           # Pydantic models + system constants
├── utils/
│   ├── gpio_import.py      # GPIO abstraction (real or mock)
│   ├── gpio_manager.py     # cleanup_gpio()
│   ├── gpio_naming.py      # Smart default GPIO names (non-destructive)
│   └── logger.py           # Logging setup
├── scripts/
│   ├── server_init.py      # Device registration on boot
│   └── (test/setup scripts)
└── admin/
    └── clear_devices.py    # Firestore cleanup utility
```

## Startup Sequence

```
main.py
  ├── subprocess: server_init.py (registers device in Firestore)
  └── asyncio.run(main())
        └── RaspServer.__init__()
              ├── IrrigationController
              ├── LightingController
              ├── HarvestController
              ├── FirebaseService
              ├── SensorService
              ├── AutomationService
              ├── DatabaseService
              ├── DiagnosticsService
              ├── ConfigManager
              ├── GPIOActuatorController
              └── LocalDatabase
            RaspServer.start()
              ├── Firebase connect
              ├── ConfigManager.initialize()
              ├── GPIOActuatorController.connect()
              │     ├── _initialize_hardware_pins()
              │     ├── _sync_initial_state_to_firestore()
              │     ├── _start_state_listener()       # on_snapshot
              │     ├── _start_command_listener()      # on_snapshot
              │     ├── _start_schedule_listener()     # on_snapshot
              │     ├── _start_schedule_checker()       # 60s loop
              │     └── _start_hardware_sync_loop()    # 5s read, 30s write
              ├── AutomationService.run_automation_loop() (if enabled)
              └── _keep_alive() (60s sleep loop)
```

## GPIOActuatorController — The Core

This is the most important file. It manages all GPIO↔Firestore communication.

### Listeners (all real-time `on_snapshot`)

| Listener | Firestore Path | Purpose |
|----------|---------------|---------|
| State listener | `devices/{serial}` | Detects `gpioState.{pin}.state` changes → applies to hardware |
| Command listener | `devices/{serial}/commands` | Processes `pin_control` commands → applies to hardware |
| Schedule listener | `devices/{serial}` | Monitors `gpioState.{pin}.schedules` for add/modify/delete |

### Background Threads

| Thread | Interval | Purpose |
|--------|----------|---------|
| Hardware sync | 5s read / 30s write | Reads all GPIO pins, writes `hardwareState` + heartbeat to Firestore |
| Schedule checker | 60s | Validates schedule time windows, starts/stops executor threads |

### State Tracking Dicts

| Dict | Purpose |
|------|---------|
| `_desired_states` | What Firestore `state` says the pin should be |
| `_hardware_states` | What the pin actually is (read from hardware) |
| `_last_firestore_state` | Last known Firestore `state` (for change detection, never corrupted by schedules) |
| `_user_override_pins` | Pins where user manually overrode a running schedule |
| `_simulated_output` | Pin states in simulation mode |

### Command Processing Flow

```
1. Command arrives via on_snapshot (command_listener)
2. _process_command(): type=pin_control, pin=N, action=on/off
3. Update _desired_states, _last_firestore_state, _hardware_states
4. _apply_to_hardware(pin, state) — sets physical GPIO
5. Immediately write state + hardwareState to Firestore (async)
6. If duration specified, spawn auto-off timer thread
```

### Schedule Execution

```
1. Schedule change detected by firestore_schedule_listener
2. Schedule checker spawns _execute_schedule thread
3. Executor loops: ON for durationSeconds, OFF for (frequency - duration)
4. Repeats within startTime–endTime window
5. Checks user_override_pins each cycle
6. On completion: pin OFF, write hardwareState + last_run_at
```

## GPIO Pin Map

| Pin | Type | Purpose | PWM |
|-----|------|---------|-----|
| 4 | Sensor | Temperature + Humidity (DHT22) | No |
| 27 | Sensor | Water Level Detection | No |
| 17 | Pump | PWM Speed/Intensity Control | Yes |
| 18 | Light | PWM Speed/Intensity Control | Yes |
| 19 | Pump | Relay Control (On/Off) | No |
| 13 | Light | Direction Control | No |
| 2 | Motor | PWM Speed | Yes |
| 3 | Motor | Direction Control | No |
| 5, 6 | Motor | Home/End Sensors | No |
| 12 | Motor | PWM Speed | Yes |
| 7-11, 14-16, 20-26, 28-29 | Motor | General Purpose I/O | No |

## Firestore Document Structure

```
devices/{hardware_serial}
├── device_id: string (human alias)
├── hardware_serial: string
├── status: "online" | "offline"
├── lastHeartbeat: Timestamp
├── gpioState: {
│   [bcmPin]: {
│     state: bool            # desired
│     hardwareState: bool    # actual
│     mismatch: bool
│     type: "sensor" | "actuator"
│     subtype: "pump" | "light" | "motor" | "sensor"
│     name: string
│     name_customized: bool
│     enabled: bool
│     mode: "output" | "input"
│     lastUpdated: Timestamp
│     lastHardwareRead: Timestamp
│     schedules: { [id]: ScheduleData }
│   }
│ }
├── config/
│   └── intervals/
│       ├── heartbeat_interval_s: 30
│       ├── sync_interval_s: 1800
│       └── hardware_state_sync_interval_s: 30
├── commands/{id}     # subcollection, deleted after processing
└── alerts/{id}       # subcollection
```

## Configuration

All in `src/config.py`, overridable via `.env`:

| Key | Default | Purpose |
|-----|---------|---------|
| `HARDWARE_SERIAL` | Auto-detect from /proc/cpuinfo | Firestore document ID |
| `DEVICE_ID` | `raspserver-001` | Human-readable alias |
| `SIMULATE_HARDWARE` | `False` | Mock GPIO for dev |
| `SENSOR_READING_INTERVAL` | `5` | Seconds between sensor reads |
| `IRRIGATION_CYCLE_DURATION` | `30` | Default pump ON time (seconds) |
| `AUTO_IRRIGATION_ENABLED` | `True` | Enable local automation |
| `AUTO_LIGHTING_ENABLED` | `True` | Enable local lighting schedule |
| `FIREBASE_CREDENTIALS_PATH` | `firebase-key.json` | Service account key |

## Simulation Mode

When `SIMULATE_HARDWARE=True` or RPi.GPIO is unavailable:
- `MockGPIO` class replaces RPi.GPIO
- `_simulated_output` dict tracks pin states in memory
- All controller operations log but don't touch hardware
- Sensor reads return realistic random values
