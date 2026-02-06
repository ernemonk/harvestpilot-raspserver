# 🔍 Heartbeat Frozen - Troubleshooting Guide

**Current Status:** Firestore timestamps frozen at Feb 6, 3:08:47 PM

This means the device was initialized but **heartbeats stopped updating**.

---

## 🎯 Why This Happens

The service may have:
1. ✅ Started successfully
2. ✅ Ran device initialization (timestamp updated)
3. ❌ **Failed to start heartbeat loop** - crashed or didn't execute

---

## 🔧 Quick Diagnostic Commands

**Run these on your Raspberry Pi:**

### Check 1: Service Status
```bash
sudo systemctl status harvestpilot-raspserver
```

**Expected output:**
```
● harvestpilot-raspserver.service - HarvestPilot RaspServer
   Active: active (running)
```

**If not running:**
```bash
sudo systemctl start harvestpilot-raspserver
sleep 2
sudo systemctl status harvestpilot-raspserver
```

---

### Check 2: View Recent Logs
```bash
journalctl -u harvestpilot-raspserver -n 50 --no-pager
```

**Look for:**
- ✅ `🎯 Starting heartbeat loop` = Heartbeat task created
- ❌ `Error` or `Traceback` = Python error
- ❌ `ImportError` = Missing dependencies
- ❌ `Firebase` = Connection issue

---

### Check 3: Watch Heartbeats in Real-Time
```bash
timeout 60 journalctl -u harvestpilot-raspserver -f --no-pager
```

**Watch for:**
- ✅ `💓 Heartbeat #X sent successfully` = Working!
- ✅ Multiple heartbeat messages = Good
- ❌ No heartbeat messages = Loop not running
- ❌ `💔 Heartbeat failed` = Firebase issue

---

### Check 4: Count Heartbeats (2-minute window)
```bash
journalctl -u harvestpilot-raspserver --since "2 minutes ago" | grep "Heartbeat #" | wc -l
```

**Expected:** 3-4 lines (one every 30 seconds)  
**If 0:** Loop not running

---

### Check 5: Full Diagnostic
```bash
# Status
echo "=== SERVICE STATUS ===" 
sudo systemctl status harvestpilot-raspserver --no-pager | head -3

# Heartbeat count
echo ""
echo "=== HEARTBEATS IN LAST 2 MINUTES ===" 
journalctl -u harvestpilot-raspserver --since "2 minutes ago" | grep -c "Heartbeat #"

# Recent errors
echo ""
echo "=== RECENT ERRORS ===" 
journalctl -u harvestpilot-raspserver --since "5 minutes ago" | grep -i "error\|failed" | head -5

# Last 10 log lines
echo ""
echo "=== LAST 10 LOG LINES ===" 
journalctl -u harvestpilot-raspserver -n 10 --no-pager
```

---

## 🛠️ Common Fixes

### If Service Not Running:
```bash
sudo systemctl start harvestpilot-raspserver
sleep 3
journalctl -u harvestpilot-raspserver -f --no-pager  # Watch logs
```

### If You See Errors:
```bash
# Restart with full log output
sudo systemctl stop harvestpilot-raspserver
cd /home/monkphx/harvestpilot-raspserver
python3 main.py  # Run manually to see actual errors
```

### If Firebase Credentials Missing:
```bash
ls -la /home/monkphx/harvestpilot-raspserver/firebase-key.json

# If not found, add it:
# 1. Obtain firebase-key.json from Firebase Console
# 2. Copy to Pi: scp firebase-key.json monkphx@192.168.1.233:/home/monkphx/harvestpilot-raspserver/
```

### If Dependencies Missing:
```bash
cd /home/monkphx/harvestpilot-raspserver
pip3 install -r requirements.txt
sudo systemctl restart harvestpilot-raspserver
```

---

## 🚀 Expected Behavior After Fix

Once heartbeat is working:

1. **Firestore updates every 30 seconds:**
   - `lastHeartbeat` timestamp changes
   - `lastSyncAt` timestamp changes
   - `status` becomes "online"

2. **Logs show heartbeats:**
   ```
   💓 Heartbeat #1 sent successfully
   💓 Heartbeat #2 sent successfully
   💓 Heartbeat #3 sent successfully
   ...
   ```

3. **Health checks every 5 minutes:**
   ```
   📈 Health check #1 published - Status: healthy, Uptime: 304s
   ```

---

## 📋 Capture & Share Results

Please run the "Full Diagnostic" command above and share:

```
=== SERVICE STATUS === 
[paste output]

=== HEARTBEATS IN LAST 2 MINUTES === 
[paste count]

=== RECENT ERRORS === 
[paste errors or "none"]

=== LAST 10 LOG LINES === 
[paste logs]
```

This will help determine the exact issue! 🔍

