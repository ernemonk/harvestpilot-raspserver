# 🎯 Server Initialization Quick Reference

## What Just Got Added

**3 new pieces automatically created:**

1. ✅ **`scripts/server_init.py`** - Initialization script that runs on startup
2. ✅ **Updated `main.py`** - Now calls init script before starting server
3. ✅ **Updated `.github/workflows/deploy.yml`** - Runs init script during deployment

---

## 🚀 What Happens When Server Starts

```
$ python3 main.py

[main.py loads]
  ↓
[Calls initialize_device()]
  ↓
[Subprocess runs scripts/server_init.py]
  ↓
[Captures Pi Serial: 1000 8000 c29f]
[Captures Pi MAC: b8:27:eb:...]
[Gets Hostname: raspberrypi]
[Loads Config ID: raspserver-001]
  ↓
[Initializes Firebase]
  ↓
[Registers to Firestore at: devices/{pi_serial}]
  ↓
[Saves local info to: .device_info.json]
  ↓
[Returns to main.py]
  ↓
[Main server starts - Firebase listeners active]
```

---

## 🔍 What Gets Registered

### In Firestore (`harvest-hub` project):

**Location:** `devices/{1000 8000 c29f}` (your Pi's serial number)

```json
{
  "uid": "1000 8000 c29f",
  "hardware_serial": "1000 8000 c29f",
  "mac_address": "b8:27:eb:12:34:56",
  "hostname": "raspberrypi",
  "ip_address": "192.168.1.233",
  "config_device_id": "raspserver-001",
  "status": "online",
  "registered_at": "2024-01-15T10:30:45...",
  "mapping": {
    "hardware_serial": "1000 8000 c29f",
    "config_id": "raspserver-001",
    "mac": "b8:27:eb:12:34:56",
    "hostname": "raspberrypi"
  }
}
```

### Locally (`.device_info.json`):

```json
{
  "pi_serial": "1000 8000 c29f",
  "pi_mac": "b8:27:eb:12:34:56",
  "hostname": "raspberrypi",
  "ip_address": "192.168.1.233",
  "config_device_id": "raspserver-001",
  "registered_at": "2024-01-15T10:30:45..."
}
```

---

## 🧪 Manual Testing

### Run Init Script Directly:

```bash
cd /home/monkphx/harvestpilot-raspserver

# Run initialization manually
python3 scripts/server_init.py

# Output should look like:
# ✅ Got Pi Serial: 1000 8000 c29f
# ✅ Got Pi MAC: b8:27:eb:12:34:56
# ✅ Got hostname: raspberrypi
# ✅ Got config DEVICE_ID: raspserver-001
# ✅ Firebase initialized
# ✅ Registered in Firestore: devices/1000 8000 c29f
# ✅ Device info saved to .device_info.json
```

### Check Local Device Info:

```bash
cat /home/monkphx/harvestpilot-raspserver/.device_info.json
```

### Check Firestore Registration:

```
Firebase Console → harvest-hub project → Firestore Database
  → devices collection → {your_pi_serial} document
```

---

## ⚡ GitHub Actions Integration

When you push to main:

```bash
git push origin main
```

GitHub Actions workflow now:
1. Checks out code
2. Validates Firebase credentials
3. Sets up GPIO
4. **Runs initialization script** ← NEW STEP
5. Deploys code
6. Restarts service

You'll see in Actions logs:

```
Initialize Pi and register to Firestore
✅ Got Pi Serial: 1000 8000 c29f
✅ Got Pi MAC: b8:27:eb:12:34:56
✅ Registered in Firestore: devices/1000 8000 c29f
✅ Device initialization completed
```

---

## 🔗 Three-Tier Device ID System

This creates a **permanent link** between three identifiers:

```
HARDWARE ID (Immutable)
  ↓ Serial from /proc/cpuinfo: 1000 8000 c29f
  ↓ This never changes - it's burned into the chip
  
  ↓ [LINKED IN FIRESTORE]
  
CONFIG ID (Changeable)
  ↓ Set in config.py: raspserver-001
  ↓ Can be changed anytime
  
  ↓ [LINKED IN MAPPING]
  
FIREBASE ID (Auto-generated)
  ↓ Created by Firebase when device registers
  ↓ Enables cloud commands via Firebase
```

**Why This Matters:**
- Hardware serial ensures device accountability
- Config ID is human-readable for operations
- Firebase ID enables cloud control
- Mapping connects all three together

---

## 🛠️ Common Tasks

### Find My Pi's Hardware Serial:

```bash
cat /proc/cpuinfo | grep Serial
# Output: Serial : 1000 8000 c29f
```

### Find My Pi's MAC Address:

```bash
cat /sys/class/net/eth0/address
# or
cat /sys/class/net/wlan0/address
```

### Check Service Status:

```bash
sudo systemctl status harvestpilot-raspserver

# Shows: Device initialization completed, listening on Firebase
```

### View Service Logs:

```bash
sudo journalctl -u harvestpilot-raspserver -n 50 -f
# -n 50 = last 50 lines
# -f = follow (watch in real-time)
```

### Manual Device Update:

```bash
# If you just changed config.py DEVICE_ID, re-initialize:
python3 scripts/server_init.py

# This will update Firestore with new config_device_id
```

---

## ✅ Verification Steps

After first deployment, verify everything worked:

```bash
# 1. Check local device info created
ls -la /home/monkphx/harvestpilot-raspserver/.device_info.json
cat /home/monkphx/harvestpilot-raspserver/.device_info.json

# 2. Check service is running
sudo systemctl is-active harvestpilot-raspserver
# Output: active

# 3. Check initialization logs
sudo journalctl -u harvestpilot-raspserver -n 20 | grep "✅"

# 4. Check Firestore has your device
# Go to Firebase Console → Firestore → devices collection
# Should see document: {your_pi_serial}
```

---

## 🔐 Troubleshooting

### Init Script Failed

```bash
# Run it manually to see detailed error
python3 scripts/server_init.py

# Common issues:
# ❌ Firebase credentials missing
#    → Check: ls -la firebase-key.json
#
# ❌ Firestore rules block write
#    → Check: Firebase Console → Firestore → Rules
#
# ❌ Network unavailable
#    → Check: ping 8.8.8.8
```

### Device Not in Firestore

```bash
# Check local registration happened
cat .device_info.json

# If .device_info.json exists but Firestore is empty:
# → Credentials issue or Firestore rules blocking writes
# → Service can still run without Firestore (just less cloud integration)
```

### Multiple Devices Register

```bash
# Each Pi registers with its OWN hardware serial as document ID
# In Firestore, you'll see:
# devices/
#   └─ 1000 8000 c29f  (Pi #1)
#   └─ 1000 8000 ab12  (Pi #2)
#   └─ 1000 8000 cd34  (Pi #3)

# Each is separate, fully independent
```

---

## 📊 Files Modified/Created

| File | Change | Purpose |
|------|--------|---------|
| `scripts/server_init.py` | ✨ NEW | Hardware ID capture & Firestore registration |
| `scripts/setup-init.sh` | ✨ NEW | Setup script (optional) |
| `main.py` | ✏️ UPDATED | Now calls init on startup |
| `.github/workflows/deploy.yml` | ✏️ UPDATED | Added init step to workflow |
| `docs/SERVER_INITIALIZATION.md` | ✨ NEW | Comprehensive guide |

---

## 📞 Quick Links

- **Manual Init:** `python3 scripts/server_init.py`
- **View Info:** `cat .device_info.json`
- **Check Logs:** `sudo journalctl -u harvestpilot-raspserver -n 50`
- **Firebase Console:** https://console.firebase.google.com → harvest-hub → Firestore
- **Config:** `config.py` - Change DEVICE_ID here
- **Full Guide:** `docs/SERVER_INITIALIZATION.md`

