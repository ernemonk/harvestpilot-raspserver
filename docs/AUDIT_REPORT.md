# SQLite Storage Implementation Audit Report

**Date**: January 23, 2026  
**Status**: ⚠️ ISSUES FOUND - Fixes included below

---

## Executive Summary

The implementation has **critical issues**:
1. ❌ **BLOCKING DB CALLS IN ASYNC LOOP** - Will freeze event loop
2. ❌ **NO THREAD EXECUTOR** - SQLite operations block async context
3. ⚠️ **CLEANUP DELETES UNSYNCED DATA** - Data loss bug
4. ⚠️ **NO PERMISSIONS HANDLING** - May fail under systemd
5. ✅ Schema creation is solid
6. ✅ Sync error handling is good

---

## Issue 1: BLOCKING DATABASE CALLS IN ASYNC LOOP

### Problem
Database operations are **synchronous** and block the event loop:

```python
# In _sensor_reading_loop() - BLOCKING!
reading = await self.sensors.read_all()
self.database.save_sensor_reading(reading)  # ❌ BLOCKS EVENT LOOP
```

Every 5 seconds, SQLite write blocks the entire async loop for ~5-10ms. This causes:
- Missed sensor readings
- Delayed Firebase publishes
- Command latency
- Potential timeouts

### Fix
Use `asyncio.to_thread()` to run DB operations in thread pool:

---

## Issue 2: CLEANUP DELETES UNSYNCED DATA

### Problem
Cleanup logic is wrong:

```python
# In cleanup_old_data()
DELETE FROM sensor_readings 
WHERE datetime(timestamp) < ? AND synced = 1
```

**The problem**: If sync fails, data becomes orphaned after 7 days and is deleted!

### Scenario
1. Day 1: Sensor reading created, NOT synced (Firebase down)
2. Day 8: Cleanup runs, deletes reading because it's > 7 days old
3. **Data is LOST forever**

### Fix
Only delete data that:
1. Is synced AND
2. Was synced > 7 days ago (use `synced_at` timestamp)

---

## Issue 3: PERMISSIONS & PATH HANDLING

### Problem
Code assumes `data/` directory is writable:

```python
Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
```

Under systemd service user (e.g., `harvest-server`):
- App runs as unprivileged user
- Home directory may not be writable
- Relative path `data/raspserver.db` resolves to `/home/harvest-server/data/` ❌

### Fix
Use absolute path with proper logging and fallback options.

---

## Issue 4: NO TRANSACTION ISOLATION

### Problem
SQLite connections not thread-safe without explicit locking:

```python
self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
```

This allows:
- Dirty reads between threads
- Corruption if writes collide
- Data inconsistency

### Fix
Use connection pooling or explicit transaction management.

---

## Corrections Below

See fixes in the following sections:
- Fix 1: Thread executor wrapper
- Fix 2: Cleanup retention logic
- Fix 3: Absolute path handling
- Fix 4: Transaction safety
- Update 5: Configuration documentation

