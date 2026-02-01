# HarvestPilot Pi Deployment & Verification Guide

**Hardware Serial Fallback Implementation - Post-Deployment Verification**

---

## 📍 Your Pi Details (From Docs)

```
Username:    monkphx
IP Address:  192.168.1.233
Hostname:    raspberrypi
Network:     WiFi (wlan0)
Deploy Tool: GitHub Actions (auto-deploy on git push)
```

---

## 🔐 SSH Connection Methods

### Method 1: SSH Key (Passwordless - Recommended)
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233
```

### Method 2: SSH with Password
```bash
ssh monkphx@192.168.1.233
```

### Method 3: Via Hostname (if on same network)
```bash
ssh monkphx@raspberrypi.local
```

---

## 🚀 Deployment Steps

### Step 1: Push Code to GitHub
```bash
cd /Users/user/Projects/HarvestPilot/Repos/harvestpilot-raspserver

# Stage all changes
git add -A

# Commit
git commit -m "hardware_serial: Implement smart fallback strategy"

# Push to main (triggers auto-deployment via GitHub Actions)
git push origin main
```

### Step 2: Monitor GitHub Actions
```
Go to: https://github.com/ernemonk/harvestpilot-raspserver/actions
Watch the workflow deploy to your Pi
Expected time: 1-2 minutes
```

### Step 3: Verify Deployment Started
```bash
# SSH into Pi
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233

# Check if new code is there
cd /home/monkphx/harvestpilot-raspserver
git log -1 --oneline
# Should show your commit message
```

---

## ✅ Verification Checklist - Hardware Serial Changes

### Part A: Code Deployment Verification

**1. Verify Latest Code is Deployed**
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 << 'EOF'
cd /home/monkphx/harvestpilot-raspserver
git log -1 --format="%h %s"
EOF
```
✅ **Expected**: Shows "hardware_serial: Implement smart fallback strategy" (your commit)

**2. Verify Config.py Has Fallback Logic**
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 << 'EOF'
grep -A 3 "def _get_hardware_serial" /home/monkphx/harvestpilot-raspserver/src/config.py | head -5
EOF
```
✅ **Expected**: Shows function definition with smart fallback logic

**3. Verify .env File is Present**
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 << 'EOF'
cat /home/monkphx/harvestpilot-raspserver/.env | grep HARDWARE_SERIAL
EOF
```
✅ **Expected**: Shows `HARDWARE_SERIAL=` field (may be empty or have value)

---

### Part B: Runtime Verification (While Server is Running)

**1. Check Service Status**
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 << 'EOF'
sudo systemctl status harvestpilot-raspserver --no-pager | head -20
EOF
```
✅ **Expected**: 
```
● harvestpilot-raspserver.service - HarvestPilot RaspServer
   Loaded: loaded
   Active: active (running)
```

**2. Check If Hardware Serial is Being Logged**
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 << 'EOF'
sudo journalctl -u harvestpilot-raspserver -n 50 --no-pager | grep -i "hardware_serial"
EOF
```
✅ **Expected**: One or more lines containing:
```
Firebase service initialized (hardware_serial: <serial>, device_id: raspserver-001)
```

**3. Check Recent Service Restart**
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@212.168.1.233 << 'EOF'
sudo journalctl -u harvestpilot-raspserver --since "5 minutes ago" --no-pager | head -30
EOF
```
✅ **Expected**: Shows recent service startup with all initialization messages

---

### Part C: Configuration Verification

**1. Verify Hardware Serial Was Detected**
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 << 'EOF'
# Run Python to check config
python3 -c "
import sys
sys.path.insert(0, '/home/monkphx/harvestpilot-raspserver')
from src import config
print(f'HARDWARE_SERIAL: {config.HARDWARE_SERIAL}')
print(f'DEVICE_ID: {config.DEVICE_ID}')
"
EOF
```
✅ **Expected**: Shows both values:
```
HARDWARE_SERIAL: 100000002acfd839  (or your Pi's actual serial)
DEVICE_ID: raspserver-001
```

**2. Check If Fallback Chain Worked**
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 << 'EOF'
# If HARDWARE_SERIAL shows actual 16-char hex = came from /proc/cpuinfo (PRIORITY 2) ✅
# If HARDWARE_SERIAL shows "raspserver-001" = came from DEVICE_ID (PRIORITY 3) ✅
# If HARDWARE_SERIAL shows something else = came from .env (PRIORITY 1) ✅

cat /home/monkphx/harvestpilot-raspserver/.env
EOF
```
✅ **Expected**: See `HARDWARE_SERIAL=` field (confirm empty or explicit)

---

### Part D: Firebase/Firestore Verification

**1. Check If Firestore Connection is Working**
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 << 'EOF'
sudo journalctl -u harvestpilot-raspserver -n 100 --no-pager | grep -i "firebase\|firestore"
EOF
```
✅ **Expected**: Shows messages like:
```
Connected to Firebase successfully
Device status updated to: online
```

**2. Verify Firestore Document Was Created**
Go to your Firebase Console:
- Navigate to: **Firestore Database** → **Collections** → **devices**
- Look for document with key matching your hardware_serial
- Document should contain:
  ```
  hardware_serial: "100000002acfd839"
  device_id: "raspserver-001"
  status: "online"
  lastHeartbeat: <timestamp>
  ```

✅ **Expected**: Document exists and contains both hardware_serial and device_id

---

## 🔍 Complete Verification Script (All-in-One)

Save this as `verify_deployment.sh`:

```bash
#!/bin/bash

PI_USER="monkphx"
PI_HOST="192.168.1.233"
SSH_KEY="$HOME/.ssh/harvestpilot_pi"

echo "=========================================="
echo "HarvestPilot Hardware Serial Verification"
echo "=========================================="
echo ""

# Check 1: Latest code deployed
echo "✓ Check 1: Latest code deployment"
ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" "cd /home/$PI_USER/harvestpilot-raspserver && git log -1 --format='%h %s'"
echo ""

# Check 2: Service status
echo "✓ Check 2: Service status"
ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" "sudo systemctl is-active harvestpilot-raspserver"
echo ""

# Check 3: Hardware serial detection
echo "✓ Check 3: Hardware serial detection"
ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" "python3 -c 'import sys; sys.path.insert(0, \"/home/$PI_USER/harvestpilot-raspserver\"); from src import config; print(f\"HARDWARE_SERIAL: {config.HARDWARE_SERIAL}\"); print(f\"DEVICE_ID: {config.DEVICE_ID}\")'"
echo ""

# Check 4: Firebase connection
echo "✓ Check 4: Firebase connection logs"
ssh -i "$SSH_KEY" "$PI_USER@$PI_HOST" "sudo journalctl -u harvestpilot-raspserver -n 5 --no-pager | grep -i 'firebase\|hardware_serial'"
echo ""

echo "=========================================="
echo "✅ Verification Complete!"
echo "=========================================="
```

Run it:
```bash
chmod +x verify_deployment.sh
./verify_deployment.sh
```

---

## 🛠️ Troubleshooting

### Issue: Can't SSH into Pi
```bash
# Check if Pi is on network
ping 192.168.1.233

# If no response, check your WiFi and try hostname instead
ping raspberrypi.local

# Verify SSH key permissions
ls -la ~/.ssh/harvestpilot_pi
# Should show: -rw------- (600)

# Verify SSH key is loaded
ssh-add ~/.ssh/harvestpilot_pi

# Try verbose SSH to debug
ssh -vvv -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233
```

### Issue: Service Not Running
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 << 'EOF'
# Check service status
sudo systemctl status harvestpilot-raspserver

# View error logs
sudo journalctl -u harvestpilot-raspserver -n 50 -p err

# Restart manually
sudo systemctl restart harvestpilot-raspserver

# Check again
sudo systemctl status harvestpilot-raspserver
EOF
```

### Issue: Hardware Serial Shows as "unknown-device"
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 << 'EOF'
# Check if /proc/cpuinfo exists
cat /proc/cpuinfo | grep Serial

# If empty or missing, fallback is working correctly:
cat /home/monkphx/harvestpilot-raspserver/.env | grep DEVICE_ID

# Both DEVICE_ID and HARDWARE_SERIAL should be set to same value
EOF
```

### Issue: Firestore Document Not Created
```bash
ssh -i ~/.ssh/harvestpilot_pi monkphx@192.168.1.233 << 'EOF'
# Check Firebase credentials
ls -la /home/monkphx/harvestpilot-raspserver/firebase-key.json

# Check Firebase connection logs
sudo journalctl -u harvestpilot-raspserver -n 20 --no-pager | grep -i "firebase\|credentials"

# Verify .env has correct project ID
cat /home/monkphx/harvestpilot-raspserver/.env | grep FIREBASE
EOF
```

---

## 📋 Post-Deployment Checklist

- [ ] Code pushed to GitHub main branch
- [ ] GitHub Actions workflow completed successfully
- [ ] SSH into Pi successful
- [ ] Latest commit deployed to Pi
- [ ] Service status is "active (running)"
- [ ] Hardware_serial is logged in service output
- [ ] Config shows correct HARDWARE_SERIAL value
- [ ] Firestore connection working (no errors in logs)
- [ ] Device document created in Firestore
- [ ] Both hardware_serial and device_id in Firestore doc
- [ ] Status field shows "online" in Firestore

---

## 📊 Expected Firestore Document Structure

```
devices/
  └── {hardware_serial}           ← Document key (immutable on Pi)
      ├── hardware_serial: "100000002acfd839"
      ├── device_id: "raspserver-001"
      ├── status: "online"
      ├── lastHeartbeat: 2026-02-01T...
      ├── device_mapping
      │   ├── hardware_serial: "100000002acfd839"
      │   ├── device_id: "raspserver-001"
      │   └── linked_at: 2026-02-01T...
      └── commands/ (subcollection)
```

---

## 🎯 What Changed on the Pi

**Files Modified:**
- ✅ `src/config.py` - Smart fallback in _get_hardware_serial()
- ✅ `src/services/firebase_service.py` - Uses hardware_serial for Firestore paths
- ✅ `src/services/device_manager.py` - Registers with hardware_serial
- ✅ `src/services/gpio_actuator_controller.py` - Listens on hardware_serial paths
- ✅ `src/core/server.py` - Passes hardware_serial to all services
- ✅ `.env` - Added HARDWARE_SERIAL field

**Behavior Changes:**
- ✅ No longer crashes if /proc/cpuinfo is missing
- ✅ Falls back to DEVICE_ID on non-Pi systems
- ✅ Firestore documents keyed by hardware_serial (immutable)
- ✅ Logs show both hardware_serial and device_id

---

## ✨ Success Indicators

Your deployment is successful when you see:

```
✅ Service active (running)
✅ Hardware_serial logged in initialization
✅ Firebase connected successfully
✅ Firestore document created with hardware_serial as key
✅ Device status shows "online" in Firestore
```

**Document created at:** `devices/{hardware_serial}/`

Where `{hardware_serial}` is either:
- Real Pi: `100000002acfd839` (from /proc/cpuinfo)
- Dev system: `raspserver-001` (from DEVICE_ID)
