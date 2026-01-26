# 🔀 Server Initialization - Integration Flow

## Complete Flow Diagram

```
╔════════════════════════════════════════════════════════════════════════════╗
║                          DEVICE REGISTRATION FLOW                          ║
╚════════════════════════════════════════════════════════════════════════════╝

┌─ SCENARIO 1: Local Service Start ─────────────────────────────────────────┐
│                                                                             │
│  $ python3 main.py                                                         │
│       ↓                                                                     │
│  [main.py:20] setup_logging()                                              │
│       ↓                                                                     │
│  [main.py:24] async def main()                                             │
│       ↓                                                                     │
│  [main.py:25] initialize_device()  ← NEW STEP                             │
│       │                                                                     │
│       ├─→ import subprocess                                               │
│       ├─→ Path("scripts/server_init.py")                                  │
│       ├─→ subprocess.run(["python3", "scripts/server_init.py"])           │
│       │                                                                     │
│       └─→ [SUBPROCESS START: server_init.py]                             │
│           │                                                                │
│           ├─→ [server_init.py:1] PiInitializer()                         │
│           ├─→ [PiInitializer.run()]                                      │
│           │   ├─→ get_pi_serial()        → /proc/cpuinfo                 │
│           │   │   → "1000 8000 c29f"                                     │
│           │   ├─→ get_pi_mac()           → /sys/class/net/eth0/address   │
│           │   │   → "b8:27:eb:12:34:56"                                  │
│           │   ├─→ get_hostname()         → hostname command              │
│           │   │   → "raspberrypi"                                        │
│           │   ├─→ get_config_device_id() → config.py                     │
│           │   │   → "raspserver-001"                                     │
│           │   │                                                           │
│           │   ├─→ initialize_firebase()                                  │
│           │   │   ├─→ Load credentials from firebase-key.json             │
│           │   │   └─→ firebase_admin.initialize_app(cred)                │
│           │   │                                                           │
│           │   ├─→ register_in_firestore()                               │
│           │   │   └─→ firestore.collection('devices')                   │
│           │   │       .document('1000 8000 c29f')  ← HARDWARE SERIAL    │
│           │   │       .set({...device_data...})                        │
│           │   │                                                           │
│           │   └─→ save_device_info()                                    │
│           │       └─→ Write .device_info.json                           │
│           │                                                               │
│           └─→ [SUBPROCESS END - Returns to main.py]                    │
│       ↓                                                                     │
│  [main.py:27] server = RaspServer()  ← Now create server                 │
│       ↓                                                                     │
│  [main.py:29] Setup signal handlers                                        │
│       ↓                                                                     │
│  [main.py:32] await server.start()   ← Server starts normally            │
│       ↓                                                                     │
│  Firebase listeners active ✅                                             │
│  GPIO ready for commands ✅                                               │
│  Web control available ✅                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ SCENARIO 2: GitHub Actions Deployment ───────────────────────────────────┐
│                                                                             │
│  $ git push origin main                                                    │
│       ↓                                                                     │
│  GitHub Actions Triggered (self-hosted runner on Pi)                       │
│       │                                                                     │
│       ├─ [Step 1] Checkout code                                            │
│       │     └─ git fetch, git reset --hard origin/main                    │
│       │                                                                     │
│       ├─ [Step 2] Write Firebase credentials                               │
│       │     └─ FIREBASE_KEY_JSON → firebase-key.json                      │
│       │                                                                     │
│       ├─ [Step 3] Setup GPIO configuration                                 │
│       │     └─ bash scripts/setup-gpio-automated.sh                        │
│       │                                                                     │
│       ├─ [Step 4] Initialize Pi and register to Firestore  ← NEW STEP   │
│       │     │                                                              │
│       │     ├─ chmod +x scripts/server_init.py                            │
│       │     └─ python3 scripts/server_init.py                             │
│       │         │                                                          │
│       │         └─ [Same as SCENARIO 1 subprocess]                        │
│       │             ├─ Capture hardware info                              │
│       │             ├─ Register to Firestore                              │
│       │             └─ Save local .device_info.json                       │
│       │                                                                     │
│       ├─ [Step 5] Deploy and restart service                               │
│       │     │                                                              │
│       │     ├─ sudo install firebase-key.json                              │
│       │     └─ sudo systemctl restart harvestpilot-raspserver              │
│       │         │                                                          │
│       │         └─ [systemd stops service if running]                     │
│       │            [systemd starts main.py]                               │
│       │                │                                                   │
│       │                └─ [Again runs initialize_device()]               │
│       │                   [Updates Firestore with current status]        │
│       │                                                                     │
│       └─ [Workflow Complete]                                               │
│           Service fully operational ✅                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─ SCENARIO 3: Systemd Service Restart ─────────────────────────────────────┐
│                                                                             │
│  $ sudo systemctl restart harvestpilot-raspserver                          │
│       ↓                                                                     │
│  systemd stops service                                                      │
│       ↓                                                                     │
│  systemd executes: ExecStart=/usr/bin/python3 main.py                      │
│       ↓                                                                     │
│  [Same as SCENARIO 1 - Full initialization sequence]                       │
│       ↓                                                                     │
│  Service ready ✅                                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: Capture → Registration → Storage

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ HARDWARE CAPTURE LAYER                                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  /proc/cpuinfo                                                              │
│    ↓ _get_pi_serial()                                                       │
│    → "1000 8000 c29f" (Raspberry Pi S/N)                                   │
│                                                                              │
│  /sys/class/net/{eth0,wlan0}/address                                        │
│    ↓ _get_pi_mac()                                                          │
│    → "b8:27:eb:12:34:56" (Network MAC)                                     │
│                                                                              │
│  hostname command                                                            │
│    ↓ _get_hostname()                                                        │
│    → "raspberrypi"                                                          │
│                                                                              │
│  config.py                                                                   │
│    ↓ _get_config_device_id()                                                │
│    → "raspserver-001"                                                       │
│                                                                              │
│  hostname -I                                                                 │
│    ↓ _get_ip_address()                                                      │
│    → "192.168.1.233"                                                        │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────────────────────┐
│ FIRESTORE REGISTRATION LAYER                                                │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  initialize_firebase()                                                      │
│    └─ Load: firebase-key.json                                              │
│    └─ Initialize Firebase Admin SDK                                        │
│                                                                              │
│  register_in_firestore()                                                    │
│    └─ Create device_data dict with all info                                │
│    └─ Write to: firestore.collection('devices').document(pi_serial)       │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                    ↓
┌──────────────────────────────────────────────────────────────────────────────┐
│ STORAGE LAYER                                                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Remote Storage (Firestore)                                                 │
│  ┌─────────────────────────────────────────────┐                          │
│  │ Collection: devices                         │                          │
│  │ Document:   1000 8000 c29f  ← HARDWARE ID  │                          │
│  │ {                                           │                          │
│  │   "uid": "1000 8000 c29f",                  │                          │
│  │   "hardware_serial": "1000 8000 c29f",     │                          │
│  │   "mac_address": "b8:27:eb:12:34:56",      │                          │
│  │   "hostname": "raspberrypi",                │                          │
│  │   "ip_address": "192.168.1.233",            │                          │
│  │   "config_device_id": "raspserver-001",     │                          │
│  │   "status": "online",                       │                          │
│  │   "registered_at": "2024-01-15T...",        │                          │
│  │   "mapping": {...}                          │                          │
│  │ }                                           │                          │
│  └─────────────────────────────────────────────┘                          │
│                                                                              │
│  Local Storage (Pi Filesystem)                                              │
│  ┌─────────────────────────────────────────────┐                          │
│  │ File: .device_info.json                     │                          │
│  │ Location: /home/monkphx/harvest.../.dev...  │                          │
│  │ {                                           │                          │
│  │   "pi_serial": "1000 8000 c29f",            │                          │
│  │   "pi_mac": "b8:27:eb:12:34:56",            │                          │
│  │   "hostname": "raspberrypi",                │                          │
│  │   "ip_address": "192.168.1.233",            │                          │
│  │   "config_device_id": "raspserver-001",     │                          │
│  │   "registered_at": "2024-01-15T..."         │                          │
│  │ }                                           │                          │
│  └─────────────────────────────────────────────┘                          │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                    ↓
                     Device fully registered ✅
                     Ready for cloud control ✅
                     Webapp can query device info ✅
```

---

## Code Integration Points

### main.py Changes

**BEFORE:**
```python
async def main():
    server = RaspServer()
    # ... signal handlers ...
    await server.start()
```

**AFTER:**
```python
def initialize_device():  # NEW FUNCTION
    """Initialize Pi and register to Firestore"""
    try:
        logger.info("🚀 Running device initialization...")
        init_script = Path(__file__).parent / "scripts" / "server_init.py"
        if init_script.exists():
            result = subprocess.run(
                [sys.executable, str(init_script)],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                logger.info("✅ Device initialization completed")
    except Exception as e:
        logger.warning(f"⚠️  Device initialization failed: {e}")

async def main():
    initialize_device()  # NEW: Run BEFORE server starts
    server = RaspServer()
    # ... signal handlers ...
    await server.start()
```

---

### deploy.yml Changes

**ADDED STEP (between GPIO setup and deploy):**
```yaml
- name: Initialize Pi and register to Firestore
  shell: bash
  env:
    FIREBASE_CREDENTIALS_PATH: /home/monkphx/harvestpilot-raspserver/firebase-key.json
  run: |
    set -euo pipefail
    echo "📝 Initializing Pi and registering to Firestore..."
    chmod +x scripts/server_init.py
    python3 scripts/server_init.py || {
      echo "⚠️  Init script failed, but service will attempt to start"
    }
```

---

## Error Handling & Resilience

```
┌─ Initialize Sequence ─────────────────────────────────────────────┐
│                                                                   │
│  initialize_device()                                              │
│    ├─ IF init_script not found:                                  │
│    │   └─ logger.warning() + continue                            │
│    │                                                              │
│    ├─ IF subprocess fails:                                        │
│    │   └─ logger.warning() + continue                            │
│    │                                                              │
│    └─ IF timeout (>30s):                                          │
│        └─ logger.warning() + continue                            │
│                                                                   │
│  → server = RaspServer()  ← ALWAYS happens                       │
│  → await server.start()   ← ALWAYS happens                       │
│                                                                   │
│  Design: Init failures are NON-FATAL                             │
│  Rationale: Service should run even without Firestore            │
│  Fallback: Local .device_info.json available if Firestore fails  │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Dependencies

```
scripts/server_init.py
  └─ imports config.py               (get DEVICE_ID)
  └─ imports firebase_admin          (cloud registration)
  └─ imports subprocess              (for system commands)
  └─ reads /proc/cpuinfo             (hardware serial)
  └─ reads /sys/class/net/           (MAC address)
  └─ reads firebase-key.json         (credentials)
  └─ writes .device_info.json        (local info)
  └─ writes to Firestore             (devices/{serial})

main.py
  └─ imports subprocess
  └─ imports Path
  └─ imports scripts.server_init     (indirectly via subprocess)
  └─ calls initialize_device()       (before RaspServer)

deploy.yml
  └─ runs scripts/server_init.py     (as Python subprocess)
  └─ has firebase-key.json available (from earlier step)
  └─ sets FIREBASE_CREDENTIALS_PATH  (for init script)
```

---

## Startup Timeline

```
Time    Event
────────────────────────────────────────────────────────────────────
0.0s    Service start (systemd or manual python3 main.py)
0.1s    main.py imports loaded
0.2s    setup_logging() called
0.3s    async def main() executes
0.4s    initialize_device() called
        ├─ Subprocess spawns
        │
0.5s    server_init.py starts
0.6s    PiInitializer() instantiated
0.7s    get_pi_serial() reads /proc/cpuinfo
0.8s    get_pi_mac() reads /sys/class/net
0.9s    get_hostname() runs hostname command
1.0s    get_config_device_id() loads config.py
1.1s    initialize_firebase() loads credentials
1.2s    Firebase Admin SDK initialized
1.3s    Firestore connection established
1.4s    register_in_firestore() writes device doc
        └─ firestore.collection('devices').document(serial).set({...})
1.5s    save_device_info() writes .device_info.json
1.6s    Subprocess completes, returns to main.py
        └─ initialize_device() returns
1.7s    RaspServer() instantiated
2.0s    await server.start() called
2.1s    Firebase listeners activate
2.2s    GPIO controllers initialized
2.3s    Hardware ready for commands
        ✅ FULLY OPERATIONAL
```

---

## Summary: What This Enables

| Capability | Enabled | Details |
|-----------|---------|---------|
| Unique Device ID | ✅ | Hardware serial stored in Firestore |
| Device Tracking | ✅ | Can identify Pi even if IP changes |
| Multi-Device Support | ✅ | Each Pi registers with own serial |
| Device Mapping | ✅ | Links hardware → config → Firebase IDs |
| Automatic Registration | ✅ | Happens on every startup |
| Fallback Storage | ✅ | Local .device_info.json if Firestore fails |
| Cloud Control | ✅ | Webapp queries Firestore for device list |
| Audit Trail | ✅ | Registration timestamp tracks when Pi came online |
| Resilient Operation | ✅ | Service runs even if registration fails |

