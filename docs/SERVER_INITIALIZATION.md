# 🚀 Server Initialization & Device Registration Guide

## Overview

When your HarvestPilot RaspServer starts (either locally or via GitHub Actions), it now automatically:

1. **Captures Pi's unique hardware ID** from `/proc/cpuinfo`
2. **Reads MAC address** for network identification
3. **Registers the device in Firestore** using the hardware serial as the document UID
4. **Creates a device mapping** linking hardware → config → Firebase IDs
5. **Saves local device info** for debugging and reference

---

## 📋 Architecture

```
[Service Start] 
    ↓
[main.py] 
    ↓ (calls on startup)
[scripts/server_init.py] 
    ↓ (captures hardware info)
[Get Pi Serial from /proc/cpuinfo]
[Get MAC from /sys/class/net/]
[Get Hostname, IP, Config ID]
    ↓ (initializes Firebase)
[Firebase Admin SDK] 
    ↓ (registers in Firestore)
[Firestore: devices/{pi_serial}]
    ↓ (saves locally)
[.device_info.json]
    ↓
[Server Startup Continues]
```

---

## 🔧 Components

### 1. **Server Init Script** (`scripts/server_init.py`)

**Purpose:** Runs on startup to initialize and register the Pi

**Key Methods:**
```python
get_pi_serial()          # Read from /proc/cpuinfo
get_pi_mac()             # Read from /sys/class/net/{eth0|wlan0}/address
get_hostname()           # Get system hostname
get_ip_address()         # Get primary IP
get_config_device_id()   # Load from config.py
initialize_firebase()    # Init Firebase Admin SDK
register_in_firestore()  # Create Firestore document
save_device_info()       # Save .device_info.json locally
```

**Firestore Document Created:**
```
Collection: devices
Document ID: {pi_serial}  ← UNIQUE HARDWARE SERIAL

{
  "uid": "1000...",                    # Pi serial from /proc/cpuinfo
  "hardware_serial": "1000...",        # Same as UID
  "mac_address": "b8:27:...",          # Network MAC
  "hostname": "raspberrypi",           # System hostname
  "ip_address": "192.168.1.233",       # Current IP
  "config_device_id": "raspserver-001",# From config.py
  "status": "online",                  # Current status
  "registered_at": "2024-...",         # Registration time
  "initialized_at": "2024-...",        # Init time
  "platform": "raspberry_pi",
  "os": "linux",
  "mapping": {                         # Device ID linking
    "hardware_serial": "1000...",
    "config_id": "raspserver-001",
    "mac": "b8:27:...",
    "hostname": "raspberrypi"
  }
}
```

---

## 🔄 Integration Points

### **Entry Point 1: Service Startup (main.py)**

```python
# In main.py, before RaspServer starts:

def initialize_device():
    """Initialize Pi and register to Firestore"""
    init_script = Path(__file__).parent / "scripts" / "server_init.py"
    result = subprocess.run([sys.executable, str(init_script)], ...)
    
async def main():
    initialize_device()  # ← Runs FIRST
    server = RaspServer()
    await server.start()  # ← THEN starts main service
```

**What Happens:**
1. Python subprocess runs `server_init.py`
2. Waits for completion (max 30 seconds)
3. Captures hardware ID and registers to Firestore
4. Continues with main service startup

---

### **Entry Point 2: GitHub Actions Deployment**

**Step added to `.github/workflows/deploy.yml`:**

```yaml
- name: Initialize Pi and register to Firestore
  shell: bash
  env:
    FIREBASE_CREDENTIALS_PATH: /home/monkphx/harvestpilot-raspserver/firebase-key.json
  run: |
    chmod +x scripts/server_init.py
    python3 scripts/server_init.py || true  # Non-fatal if fails
```

**Workflow Sequence:**
1. ✅ Checkout code
2. ✅ Write Firebase credentials
3. ✅ Setup GPIO configuration
4. ✅ **Initialize Pi and register to Firestore** ← NEW STEP
5. ✅ Deploy and restart service

**Why `|| true`?**
- Init script failures are **non-fatal**
- Service can start without Firestore if network unavailable
- Logs will show what happened
- Device info is still available locally

---

## 🔐 Firebase Credentials

The init script looks for credentials at:
```bash
$FIREBASE_CREDENTIALS_PATH  # Set by GitHub Actions
# or
/home/monkphx/harvestpilot-raspserver/firebase-key.json  # Default
```

**In GitHub Actions:**
1. Secret `FIREBASE_KEY_JSON` contains base64-encoded credentials
2. Workflow writes to `firebase-key.json` in repo root
3. Deploy step installs to `/home/monkphx/harvestpilot-raspserver/`
4. Init script finds it via environment variable or default path

---

## 📊 Device ID Linking

The initialization creates a **three-tier device identity system:**

```
┌─────────────────────────────────────────────┐
│ HARDWARE TIER (Physical Device)            │
├─────────────────────────────────────────────┤
│ Serial: 1000 8000 c29f (from /proc/cpuinfo)│
│ MAC:    b8:27:eb:... (from /sys/class/net) │
│ This is IMMUTABLE - tied to the Pi forever │
└─────────────────────────────────────────────┘
            ↓ (linked via Firestore)
┌─────────────────────────────────────────────┐
│ CONFIG TIER (Software Configuration)       │
├─────────────────────────────────────────────┤
│ Device ID: "raspserver-001"  (from config) │
│ This can be changed in config.py            │
└─────────────────────────────────────────────┘
            ↓ (linked via Firebase)
┌─────────────────────────────────────────────┐
│ FIREBASE TIER (Cloud Identity)             │
├─────────────────────────────────────────────┤
│ Database ID: Auto-generated by Firebase    │
│ Doc ID in Firestore: {hardware_serial}     │
│ This enables cloud commands/control        │
└─────────────────────────────────────────────┘
```

---

## 📝 Local Device Info File

After initialization, device info is saved locally:

**File:** `.device_info.json` (in repo root, alongside main.py)

**Contents:**
```json
{
  "pi_serial": "1000 8000 c29f",
  "pi_mac": "b8:27:eb:12:34:56",
  "hostname": "raspberrypi",
  "ip_address": "192.168.1.233",
  "config_device_id": "raspserver-001",
  "registered_at": "2024-01-15T10:30:45.123456"
}
```

**Use Cases:**
- Debugging device identification
- Webapp queries local info if Firestore unavailable
- Device troubleshooting and logs
- Manual device mapping verification

---

## 🚀 Startup Sequence (Full Picture)

### **Local Testing:**
```bash
cd /home/monkphx/harvestpilot-raspserver
python3 main.py
```

**Flow:**
1. Python loads main.py
2. Sets up logging
3. Calls `initialize_device()` which runs `server_init.py` as subprocess
4. Subprocess captures hardware info + registers to Firestore
5. Returns control to main.py
6. Subprocess output logged to console
7. Main RaspServer starts
8. Firebase listeners activate
9. GPIO controllers ready for commands

---

### **GitHub Actions Deployment:**
```bash
git push origin main
```

**Flow (in Actions runner on Pi):**
1. Checkout code
2. Validate Firebase credentials
3. Setup GPIO
4. Run `python3 scripts/server_init.py` (initialization step)
   - Captures Pi serial/MAC
   - Initializes Firebase
   - Registers to Firestore (`devices/{pi_serial}`)
   - Saves `.device_info.json`
5. Deploy code and restart systemd service
6. Systemd starts `main.py`
7. main.py runs `initialize_device()` again
   - Updates Firestore with new status
   - Ensures device info is current
8. Server fully operational

---

### **Systemd Service Restart:**
```bash
sudo systemctl restart harvestpilot-raspserver
```

**Flow:**
1. systemd stops current service
2. systemd starts main.py
3. main.py runs `initialize_device()` subprocess
4. Device registration updated in Firestore
5. Server continues normal operation

---

## ⚙️ Configuration

### **In `config.py`:**
```python
DEVICE_ID = "raspserver-001"           # Used by init script
FIREBASE_DATABASE_URL = "https://..."  # For device_manager
FIREBASE_PROJECT_ID = "harvest-hub"    # For Firestore
```

### **Environment Variables:**
```bash
FIREBASE_CREDENTIALS_PATH=/path/to/firebase-key.json
DEVICE_ID=custom-id-123  # Overrides config.py
```

### **GitHub Secrets:**
- `FIREBASE_KEY_JSON` - Base64 encoded credentials
- `PI_MODEL` - Optional, defaults to 'pi4'
- `MODULE_ID` - Optional module identifier

---

## 🐛 Troubleshooting

### **"Could not read Pi serial"**
```
❌ Ensure /proc/cpuinfo is readable
💡 Run: cat /proc/cpuinfo | grep Serial
```

### **"Firebase initialization failed"**
```
❌ Check credentials path exists
💡 Run: ls -la /home/monkphx/harvestpilot-raspserver/firebase-key.json
❌ Check credentials are valid JSON
💡 Run: python3 -m json.tool firebase-key.json
```

### **"Firestore registration failed"**
```
❌ Check network connectivity
💡 Run: ping 8.8.8.8
❌ Check Firestore rules allow writes
💡 Check Firebase Console → Firestore Rules
```

### **Device info not in Firestore**
```
💡 Check initialization logs: sudo journalctl -u harvestpilot-raspserver -n 100
💡 Try manual init: python3 scripts/server_init.py
💡 Check .device_info.json exists locally
```

---

## ✅ Verification Checklist

After deployment, verify:

- [ ] GitHub Actions workflow runs without errors
- [ ] Init script step completes (even if warnings)
- [ ] Service starts successfully: `sudo systemctl status harvestpilot-raspserver`
- [ ] `.device_info.json` exists in `/home/monkphx/harvestpilot-raspserver/`
- [ ] Firebase Console → Firestore → `devices` collection has document with Pi serial
- [ ] Document contains `hardware_serial`, `mac_address`, `config_device_id`
- [ ] Service logs show initialization completed: `sudo journalctl -u harvestpilot-raspserver -n 50`

---

## 🔗 Related Files

- **Init Script:** [scripts/server_init.py](scripts/server_init.py)
- **Entry Point:** [main.py](main.py)
- **Workflow:** [.github/workflows/deploy.yml](.github/workflows/deploy.yml)
- **Config:** [config.py](config.py)
- **Device Manager:** [services/device_manager.py](services/device_manager.py)
- **Setup Script:** [scripts/setup-init.sh](scripts/setup-init.sh)

---

## 📚 Next Steps

1. **Webapp Integration:** Query Firestore `devices/{pi_serial}` to get device info
2. **Device Dashboard:** Display all registered devices with their hardware/config IDs
3. **Multi-Device Support:** Handle multiple Pis registering to same Firestore project
4. **Automated Updates:** Update device status/telemetry periodically
5. **Device Linking:** Allow web UI to map config IDs to hardware serials

