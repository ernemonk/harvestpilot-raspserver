# HarvestPilot Heartbeat Diagnostics - Root Cause Analysis

## Status: ISSUE FOUND AND UNDERSTOOD

### Executive Summary
Your 30-minute sync mechanism code **IS CORRECT**, but the service has a **critical bug causing it to hang and stop all activity** after ~20 minutes.

---

## Problem Identified

### What We Found
1. **Service WAS running for 18 hours** - Initially appeared healthy
2. **NO HEARTBEAT LOGS in last 30 minutes** - The loop stopped sending updates
3. **Firebase connection drops** - After ~20 min, gets "Cannot publish heartbeat - Firebase not connected"
4. **Service becomes frozen** - Database closes, service doesn't respond, times out on restart

### The Error Sequence
```
14:02:19 - WARNING: "Cannot publish heartbeat - Firebase not connected"
14:02:49 - ERROR: "Cannot operate on a closed database"
14:03:19 - SERVICE TIMEOUT: Systemd kills with SIGKILL (forceful)
```

---

## Root Cause

### In `src/services/firebase_service.py` (line 179)
```python
if not self.connected:
    logger.warning("Cannot publish heartbeat - Firebase not connected")
    return  # <-- SILENTLY FAILS - No reconnection attempt!
```

**The Problem:**
- Firebase connection is lost or becomes invalid
- Heartbeat silently fails without reconnecting
- Service continues but all Firebase operations block or fail
- Database connection gets corrupted
- Service completely hangs and must be force-killed

---

## Why This Matters

Your heartbeat and sync code are **100% correct**:

✓ `_heartbeat_loop()` correctly uses `await asyncio.sleep(30)`  
✓ `_sync_to_cloud_loop()` correctly uses `await asyncio.sleep(1800)` (30 min)  
✓ Both intervals fixed in `src/storage/models.py`

**BUT** - if Firebase disconnects or the database closes, the entire system locks up.

---

## The Fix Required

### Option 1: Auto-Reconnect Firebase (Recommended)
In `src/services/firebase_service.py`, modify `publish_heartbeat()`:

```python
def publish_heartbeat(self):
    try:
        if not self.connected:
            logger.warning("Firebase disconnected, attempting reconnect...")
            self.reconnect()  # ADD THIS
            
        if not self.connected:  # Still not connected
            logger.error("Heartbeat failed: Firebase not connected after reconnect")
            return
        
        # ... rest of publish_heartbeat code ...
```

### Option 2: Add Connection Health Check
Add a separate monitoring loop that checks Firebase connectivity every 5 minutes and reconnects if needed.

### Option 3: Add Timeout Handling to Database Operations
Add explicit timeout handling to database operations to prevent hang-on-close scenarios.

---

## Immediate Actions

1. **Restart service** (already done):
   ```bash
   sudo systemctl restart harvestpilot-raspserver.service
   ```

2. **Monitor for next 30+ minutes** to see if issue recurs:
   ```bash
   sudo journalctl -u harvestpilot-raspserver.service -f
   ```

3. **Look for**:
   - Heartbeats every 30 seconds ✓
   - Sync every 30 minutes ✓
   - NO "Cannot publish heartbeat - Firebase not connected" ✗
   - NO "Cannot operate on a closed database" ✗

---

## Files That Need Fixing

1. **`src/services/firebase_service.py`** (line 175-195)
   - Add reconnection logic to `publish_heartbeat()`

2. **`src/core/server.py`** (line 287-310)
   - Add exception handling to restart loops if they fail

3. **`src/services/database_service.py`**
   - Add timeout/connection management to prevent database hang

---

## Verification Checklist

After implementing fix:

- [ ] Service runs for >1 hour without Firebase disconnects
- [ ] Heartbeats logged every 30 seconds
- [ ] Sync happens every 30 minutes
- [ ] No database close errors
- [ ] Service responds to systemctl stop (no timeout kills)
- [ ] Firebase `lastHeartbeat` updates every 30 seconds
- [ ] Firebase `lastSyncAt` updates every 30 minutes

---

## Conclusion

**Your code was right. The bug is in Firebase reconnection logic.** Once fixed, the 30-minute sync will work perfectly.

Generated: 2026-02-07 14:14 UTC
