# HarvestPilot — Vision

## What This Is

HarvestPilot is a vertically integrated platform for automated microgreens production. Five pieces, one system:

| Component | Role | Stack |
|---|---|---|
| **GreenStack Systems** | Open-source modular growing hardware (~$400/unit) | 3D-printed + PVC, 6-tray rack, 22"×12" footprint |
| **harvestpilot-raspserver** | Raspberry Pi controller (THIS REPO) | Python, RPi.GPIO, Firebase Admin SDK |
| **harvestpilot-webapp** | Multi-tenant farm dashboard | React, TypeScript, Firebase |
| **HarvestPilot Agent** | Cloud AI intelligence | FastAPI, Gemini, LangGraph, MQTT |
| **GreenStack Fresh** | Commercial production operation | Physical facility, same-day delivery |

---

## The Hardware

Each GreenStack unit:
- 6-tray growing rack (PVC frame, 3D-printed brackets)
- 12V pump with PWM speed control + relay
- Dimmable LED strips with PWM + relay
- 6 harvest belt motors (PWM + direction per tray, home/end sensors)
- DHT22 temperature/humidity sensor
- Water level sensor (digital, active-low)
- Soil moisture sensor (requires ADC — not yet implemented)

**10x cheaper than commercial alternatives** ($400 vs $2,000–5,000).

---

## The Architecture

```
┌──────────────────────────────────────────────┐
│  harvestpilot-webapp (React + Firebase)       │
│  User toggles GPIO → writes Firestore        │
└──────────────┬───────────────────────────────┘
               │ Firestore real-time listener
┌──────────────▼───────────────────────────────┐
│  harvestpilot-raspserver (Raspberry Pi 4)     │
│                                               │
│  ┌─────────────────────────────────────────┐ │
│  │ GPIOActuatorController                   │ │
│  │  • Listens to gpioState.{pin}.state     │ │
│  │  • Applies to hardware instantly        │ │
│  │  • Reads hardware back (GPIO.input)     │ │
│  │  • Writes hardwareState to Firestore    │ │
│  │  • Detects mismatches every 2 seconds   │ │
│  └─────────────────────────────────────────┘ │
│                                               │
│  ┌─────────────────────────────────────────┐ │
│  │ Controllers (low-level hardware)         │ │
│  │  • IrrigationController (pump PWM)      │ │
│  │  • LightingController (LED PWM)         │ │
│  │  • HarvestController (6 belt motors)    │ │
│  │  • SensorController (DHT22, water)      │ │
│  └─────────────────────────────────────────┘ │
│                                               │
│  ┌─────────────────────────────────────────┐ │
│  │ Services (business logic)                │ │
│  │  • FirebaseService (heartbeat, status)  │ │
│  │  • AutomationService (scheduled jobs)   │ │
│  │  • ConfigManager (dynamic intervals)    │ │
│  │  • DatabaseService (local SQLite)       │ │
│  └─────────────────────────────────────────┘ │
└──────────────┬───────────────────────────────┘
               │ GPIO (BCM mode)
     ┌─────────▼──────────┐
     │ Physical Hardware   │
     │ Pumps, LEDs, Motors │
     │ Sensors             │
     └─────────────────────┘
```

---

## The Data Model

Every GPIO pin has TWO values in Firestore:

| Field | Set By | Meaning |
|---|---|---|
| `state` | Webapp | What the pin SHOULD be (desired) |
| `hardwareState` | Pi | What the pin ACTUALLY is (measured from hardware) |
| `mismatch` | Pi | `true` if state ≠ hardwareState |

**Firestore path:** `devices/{hardware_serial}/gpioState/{bcm_pin}`

```json
{
  "state": true,
  "hardwareState": true,
  "mismatch": false,
  "name": "Pump PWM",
  "pin": 17,
  "mode": "output",
  "enabled": true,
  "lastHardwareRead": "2026-02-09T..."
}
```

---

## GPIO Pin Map

| BCM Pin | Assignment | Type |
|---|---|---|
| 17 | Pump PWM | Output |
| 19 | Pump Relay | Output |
| 18 | LED PWM | Output |
| 13 | LED Relay | Output |
| 2, 3, 4, 27 | Motor 1 (PWM, DIR, Home, End) | Output/Input |
| 9, 11, 5, 6 | Motor 2 | Output/Input |
| 10, 22, 23, 24 | Motor 3 | Output/Input |
| 14, 15, ~~28~~, 25 | Motor 4 | Output/Input |
| 8, 7, ~~29~~, 12 | Motor 5 | Output/Input |
| 16, 20, 21, 26 | Motor 6 | Output/Input |

> **Warning:** GPIO 28 and 29 are NOT valid BCM pins on Raspberry Pi. Motor 4 home and Motor 5 home need reassignment.

---

## What's Actually Working (February 2026)

### Running in Production
- Firebase connect + heartbeat every 30s (device stays "online")
- Real-time GPIO pin control from webapp via Firestore listener
- Hardware state readback + mismatch detection every 2s
- All GPIO pins initialized and synced to Firestore on boot
- Dynamic config intervals from Firestore with local cache
- Time-based automation (scheduled irrigation/lighting)
- Local SQLite database for operations logging
- Device registration to Firestore on startup
- Auto-deploy from GitHub (webhook + systemd)

### Built But Not Connected
- `SyncService` — batch sync local data to Firestore (204 lines, never started)
- `CommandPoller` — polls for pending commands (239 lines, never started)
- `FailsafeManager` — safety checks for water/temp/humidity (246 lines, never instantiated)
- `SensorService.read_all()` — sensor reading logic exists, never called in any loop
- Pin config system — ~1,700 lines of advanced config management, unused

### Not Working
- **No sensor reading loop** — sensors are never read or published to Firebase
- `FirebaseDeviceListener` — uses wrong API (Pyrebase vs firebase_admin)
- `DeviceManager` — partially broken API references
- Root-level controller/service shims — fragile, one is broken
- Soil moisture — hardcoded to 70.0 (no ADC hardware)
- Motor home/end sensors — pins allocated, no homing logic
- High-level Firebase commands (irrigation start/stop) — registered but handler does nothing

---

## The Business

### Revenue Streams
1. **Hardware sales** — $250–600 per GreenStack unit
2. **Cloud subscriptions** — $29/mo Pro, $99/mo Enterprise
3. **Commercial production** — Wholesale microgreens to restaurants ($15–20/lb)
4. **Services** — Installation, training, custom development

### Current Traction
- 30 units assembled, 20 sold
- 5 restaurant LOIs
- 5,000 YouTube subscribers

### Target Scale
- Year 1: 500 units, 96 trays, $1.5M revenue
- Year 3: National expansion, 10,000+ systems
- Year 5: $100M+ revenue, 50+ production locations

---

## The Thesis

Affordable hardware gets farmers started. Real-time data makes them better. AI makes them unstoppable. Commercial production proves it all works. Every piece reinforces the others.

**Equipment sales → Real-world validation → Production revenue → AI platform → Network effects → Market leadership.**
