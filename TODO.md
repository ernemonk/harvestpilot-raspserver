# TODO — harvestpilot-raspserver

## Bugs

- [ ] **GPIO 17 & 18 can get stuck ON** if the Pi crashes mid-schedule (no persistent recovery). On reboot, `_sync_initial_state_to_firestore()` sets all pins LOW, but Firestore `state` may still say `true`.
- [ ] **Schedule time window uses string comparison** (`"08:00" <= now <= "22:00"`) which fails across midnight for overnight windows. Partially fixed with `now >= start or now <= end` path but edge cases may exist.

## Technical Debt

- [ ] **AutomationService partially superseded** — Local time-based irrigation/lighting schedules duplicate the Firestore schedule system. Evaluate consolidating into one mechanism.
- [ ] **No reconnection logic for Firestore listeners** — if the Firestore `on_snapshot` connection drops, there's no automatic retry. Firebase Admin SDK may handle this internally, but it's not explicit.
- [ ] **Thread safety** — `_desired_states`, `_hardware_states`, `_last_firestore_state` dicts are accessed from multiple threads without locks (state listener, command listener, hardware sync, schedule executor). Add `threading.Lock` per dict.
- [ ] **`_processed_commands` set grows unbounded** — commands are added but only removed on `REMOVED` change type. If commands are deleted after processing, this is fine, but old entries never expire.
- [ ] **`hardware_state_sync_interval_s` default is 30s** — configurable via Firestore but no UI exists to change it. Document or add to webapp settings.
- [ ] **No graceful schedule cancellation** — when a schedule is deleted from Firestore while its executor thread is running, the thread continues until the next `is_in_time_window()` check (up to 1 second). Consider using `threading.Event` for immediate interruption.

## Features

- [ ] **PWM duty cycle control** — `_process_command` handles `pwm_control` type but actual PWM implementation is only in IrrigationController and LightingController. Wire up generic PWM for any pin.
- [ ] **Sensor data push to Firestore** — `SensorService.read_all()` works but periodic pushing of sensor readings to `devices/{serial}/hourly` is not implemented in the current startup sequence.
- [ ] **Alert generation** — `SensorService.check_thresholds()` generates `ThresholdAlert` objects but they're not written to Firestore `alerts` subcollection automatically.
- [ ] **Camera streaming** — No camera service exists. CameraSection in webapp expects a stream URL.
- [ ] **OTA updates** — `deployment/` has update scripts but no auto-update mechanism from Firestore.
- [ ] **Failsafe system** — `FailsafeManager` was deleted as dead code. Consider implementing emergency shutoff based on water level (<20%) or temperature (>95°F).
- [ ] **Structured logging to Firestore** — `DiagnosticsService` tracks counters but doesn't push them to Firestore for remote monitoring.
