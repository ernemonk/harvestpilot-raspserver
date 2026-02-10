# VISION — harvestpilot-raspserver

## What This Is

The HarvestPilot raspserver is the on-device brain running on a Raspberry Pi. It bridges the physical world (GPIO pins, pumps, lights, sensors) with the cloud (Firebase Firestore). When a farmer toggles a pump from their phone, this server makes the motor spin.

## Core Principles

1. **Firestore is the API.** No REST server, no WebSocket server. All commands and state flow through Firestore documents. This means the Pi works behind NAT, firewalls, cellular — anywhere with internet.
2. **Real-time listeners, not polling.** State changes, commands, and schedule updates all arrive via `on_snapshot`. The only polling is the hardware sync loop (reading physical pin values).
3. **Survive reboots.** On startup, the server registers itself in Firestore, initializes all GPIO pins, and picks up wherever it left off.
4. **Simulation mode.** Runs on any machine (Mac, Windows, Linux) without GPIO hardware for development and testing.

## Target Hardware

- Raspberry Pi 4B / 3B+ (any model with GPIO header)
- DHT22 temperature/humidity sensors
- Relay modules for pump/light switching
- PWM-capable pins for speed/intensity control
- 6-tray harvest belt motor system

## Where It's Going

- **Camera streaming** — serve Pi Camera frames via WebRTC or MJPEG
- **Sensor data pipeline** — periodic reads pushed to `hourly` subcollection for trend analytics
- **Failsafe system** — auto-shutoff when water runs out or temperature exceeds limits
- **OTA updates** — pull new code from GitHub Actions automatically
- **Multi-sensor support** — soil moisture, EC, pH, light intensity
- **Edge computation** — local decision-making when Firestore is unreachable (offline resilience)
