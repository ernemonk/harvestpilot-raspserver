# Heartbeat Diagnostics Guide

## Problem
Your Firestore `lastHeartbeat` and `lastSyncAt` timestamps are frozen - not updating every 30 seconds as expected.

## What We Fixed
✅ **Commit: 56bffe2** - Enhanced heartbeat logging and error visibility

### Changes Made:
1. **Better error detection** - Added logging when Firebase is not connected
2. **Heartbeat counter** - Track how many heartbeats actually sent
3. **Detailed error stack traces** - See exact failure reasons
4. **Health check metrics** - New metrics loop logging for every 5-minute health check

---

## How to Diagnose on Your Raspberry Pi

### Step 1: Pull Latest Code
```bash
cd /home/pi/harvestpilot-raspserver
git pull origin main
```

### Step 2: Check the Logs
Monitor the heartbeat in real-time:
```bash
# Option A: Follow systemd service logs
journalctl -u harvestpilot-autodeploy.service -f --no-pager

# Look for these lines:
# 💓 Heartbeat #1 sent successfully
# 💓 Heartbeat #2 sent successfully  
# 💔 Heartbeat failed: [error details]
# 💥 Cannot publish heartbeat - Firebase not connected
```

### Step 3: Check Firestore Console
While watching the logs:
1. Open Firestore Console
2. Navigate to `devices` > `100000002acfd839`
3. Watch the `lastHeartbeat` field
4. It should update every 30 seconds (showing current timestamp)

---

## What Each Log Message Means

### ✅ Success
```
💓 Heartbeat #1 sent successfully
📈 Health check #1 published - Status: healthy, Uptime: 32s, Errors: 0
```
**Action:** Everything is working! The timestamp in Firestore should be updating.

### ⚠️ Not Connected
```
💥 Cannot publish heartbeat - Firebase not connected
```
**Causes:**
- Firebase credentials not found
- Permission denied on credentials file
- Network connectivity issue
- Firebase initialization failed

**Fix:**
```bash
# Check if credentials file exists
ls -la /home/pi/harvestpilot-raspserver/config/harvest-hub-2025-firebase-adminsdk-fbsvc-460b441782.json

# Check permissions
sudo chmod 644 /home/pi/harvestpilot-raspserver/config/*.json

# Restart service
sudo systemctl restart harvestpilot-autodeploy.service
```

### 💔 Firestore Write Failed
```
💔 Heartbeat failed: Permission denied writing to Firestore
```
**Causes:**
- Firebase security rules blocking write
- Authentication token expired
- Network issue during write

**Fix:**
```bash
# Check Firebase security rules in Console
# Default rule allows reads/writes if authenticated

# Restart the service to refresh auth token
sudo systemctl restart harvestpilot-autodeploy.service
```

---

## Timeline of Heartbeats
- **Every 30 seconds:** Heartbeat sent (updates `lastHeartbeat`)
- **Every 5 minutes:** Health metrics published (updates diagnostics)
- **Every 30 minutes:** Full cloud sync (updates full device state)

---

## Quick Debugging Checklist

- [ ] Can see log messages starting with `💓`, `📈`, or `💔`?
- [ ] Firestore timestamps updating every 30 seconds?
- [ ] Device status showing as "online"?
- [ ] No Firebase connection errors in logs?
- [ ] All 3 loops running: heartbeat, metrics, sync?

---

## Test Command
Monitor heartbeat count over 2 minutes:
```bash
# Count heartbeats in last 120 seconds
journalctl -u harvestpilot-autodeploy.service --since "2 minutes ago" | grep "Heartbeat #" | wc -l

# Should show ~4 heartbeats (one every 30 seconds)
# If less than 3, something is wrong
```

---

## Still Not Working?
Collect diagnostic data and share:
```bash
# Get detailed service status
systemctl status harvestpilot-autodeploy.service

# Get last 100 lines of logs
journalctl -u harvestpilot-autodeploy.service -n 100

# Check if service is actually running
ps aux | grep python | grep main.py
```

Share these outputs for deeper troubleshooting!
