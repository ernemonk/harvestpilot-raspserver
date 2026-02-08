# DESIGN INVESTIGATION: Configurable Interval Architecture

## Executive Summary

After analyzing your entire codebase, I've identified what's **currently implemented** and what's **missing** for dynamic interval configuration. This design document outlines the optimal strategy.

---

## Current State Analysis

### ✅ What's Already Implemented

**1. Hardcoded Intervals (Defined in Code)**
```python
# src/core/server.py
_heartbeat_loop:        await asyncio.sleep(30)      # 30 seconds
_metrics_loop:          await asyncio.sleep(300)     # 5 minutes
_sync_to_cloud_loop:    await asyncio.sleep(1800)    # 30 minutes
_aggregation_loop:      await asyncio.sleep(60)      # 60 seconds
_sensor_reading_loop:   config.SENSOR_READING_INTERVAL  # 5 seconds

# src/storage/models.py
SYNC_INTERVAL_MS = 30 * 60 * 1000      # 30 minutes
HEARTBEAT_INTERVAL_MS = 30 * 1000     # 30 seconds
```

**2. Firestore as Observable State**
- Device registers to Firestore: `devices/{hardware_serial}/`
- Publishes heartbeat, metrics, status every interval
- Firebase shows `lastHeartbeat`, `lastSyncAt`, diagnostics
- ✅ All readable from web app

**3. Local SQLite Database**
- `src/storage/local_db.py` stores all data locally
- Sensor readings, summaries, alerts, commands all persisted
- 30-day rolling storage with cleanup
- ✅ Survives reboots, network outages

**4. Firebase Auto-Reconnection**
- `src/services/firebase_service.py` has `reconnect()` method
- Sensor blocking fix ensures event loop responsive
- Heartbeat keeps publishing even after Firebase issues
- ✅ Resilient design

---

## What's MISSING (Gap Analysis)

### ❌ No Dynamic Interval Listening

Currently:
1. Service starts with hardcoded intervals
2. Service publishes heartbeat/metrics/sync at fixed times
3. **User can observe** intervals in Firestore
4. **But user CANNOT change** intervals from web app
5. Service doesn't listen for config changes
6. Service doesn't persist interval preferences locally

### Missing Components:

```
1. Firestore Listener
   - Path: devices/{hardware_serial}/config/intervals/
   - Listens for: heartbeat_interval_ms, sync_interval_ms, etc
   - Updates in real-time
   
2. Local Config Storage
   - Table: device_config (in SQLite)
   - Stores: interval overrides
   - Persists across reboots
   
3. Interval Manager Service
   - Reads local config on startup
   - Listens to Firestore for changes
   - Dynamically updates loop intervals
   - Handles graceful transitions
   
4. Web App Integration
   - UI to change intervals per device
   - Writes to: devices/{hardware_serial}/config/intervals/
   - Device listens and applies changes
```

---

## Proposed Architecture (OPTIMAL DESIGN)

### Phase 1: Foundation
```
Device Startup
    ↓
    ├─ Load intervals from Firestore
    │  (falls back to code defaults if missing)
    │
    └─ Cache in local SQLite: device_config table
       - heartbeat_interval_ms
       - sync_interval_ms
       - metrics_interval_ms
       - aggregation_interval_ms
       - sensor_read_interval_ms
       - last_updated timestamp
```

### Phase 2: Real-Time Listening (Firestore Listener)
```
After startup, set up listener:

Firestore Listener on: devices/{hardware_serial}/config/intervals/
    ↓
    When changes detected:
    ├─ Update local SQLite cache
    ├─ Signal loop managers to update intervals
    └─ Log change with old/new values
```

### Phase 3: Dynamic Loop Updates
```
Each loop (heartbeat, sync, metrics) becomes configurable:

OLD CODE:
    async def _heartbeat_loop(self):
        while self.running:
            await asyncio.sleep(30)  # HARDCODED ❌
            ...

NEW CODE:
    async def _heartbeat_loop(self):
        while self.running:
            interval = self.config_manager.get_heartbeat_interval()
            await asyncio.sleep(interval)
            ...
```

### Phase 4: Graceful Transition
```
When interval changes mid-execution:

Example: Change heartbeat from 30s → 60s
    ↓
Current heartbeat waiting 15s more
    ↓
On next cycle, reads new interval: 60s
    ↓
Sleeps 60s instead of 30s
    ↓
No service restart needed ✅
```

---

## Data Structures

### Firestore Schema (Web App Configures)
```json
{
  "devices": {
    "100000002acfd839": {
      "status": "online",
      "lastHeartbeat": "...",
      "config": {
        "intervals": {
          "heartbeat_interval_ms": 30000,
          "metrics_interval_ms": 300000,
          "sync_interval_ms": 1800000,
          "aggregation_interval_ms": 60000,
          "sensor_read_interval_ms": 5000,
          "last_updated": "2026-02-07T18:00:00Z",
          "changed_by": "web_app_user_123"
        }
      }
    }
  }
}
```

### Local SQLite Schema (Device Caches)
```sql
CREATE TABLE device_config (
    key TEXT PRIMARY KEY,
    value TEXT,
    last_updated INTEGER,
    source TEXT  -- 'firestore', 'code_default', 'manual'
);

-- Rows:
INSERT INTO device_config VALUES 
('heartbeat_interval_ms', '30000', 1707432000, 'firestore'),
('sync_interval_ms', '1800000', 1707432000, 'code_default'),
('metrics_interval_ms', '300000', 1707432000, 'firestore');
```

---

## Implementation Strategy (4 New Files)

### 1. `src/services/config_manager.py`
**Responsibility**: Read/cache/sync interval configuration
```python
class ConfigManager:
    """Manage device configuration with Firestore sync"""
    
    def __init__(self, database, firestore_db, hardware_serial):
        self.database = database
        self.firestore_db = firestore_db
        self.hardware_serial = hardware_serial
        self.intervals = {}  # In-memory cache
        self._listener = None
    
    def load_config_from_firestore(self):
        """Get config from Firestore or use defaults"""
        
    def cache_locally(self, config: dict):
        """Save to SQLite for persistence"""
        
    def get_heartbeat_interval(self) -> int:
        """Return heartbeat interval in seconds"""
        
    def get_sync_interval(self) -> int:
        """Return sync interval in seconds"""
        
    def listen_for_changes(self):
        """Set up Firestore listener for real-time updates"""
        
    def handle_interval_change(self, old_interval, new_interval):
        """Called when Firestore config changes"""
```

### 2. `src/storage/schema_updates.sql`
**Responsibility**: Add device_config table to SQLite
```sql
CREATE TABLE IF NOT EXISTS device_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    last_updated INTEGER,
    source TEXT
);
```

### 3. Update `src/core/server.py`
**Changes**: Inject ConfigManager, use dynamic intervals
```python
class RaspServer:
    def __init__(self):
        # ... existing code ...
        self.config_manager = ConfigManager(
            database=self.database,
            firestore_db=None,  # Set after Firebase init
            hardware_serial=config.HARDWARE_SERIAL
        )
    
    async def _heartbeat_loop(self):
        while self.running:
            interval = self.config_manager.get_heartbeat_interval()
            await asyncio.sleep(interval)
            # ... rest of loop ...
```

### 4. Update `src/services/firebase_service.py`
**Changes**: Register ConfigManager listener on connection
```python
def connect(self):
    # ... existing connect code ...
    
    # Set up interval config listening
    if hasattr(self, 'config_manager'):
        self.config_manager.listen_for_changes()
```

---

## Rollout Strategy (3 Phases)

### Phase A: Foundation (Non-Breaking)
- ✅ Add device_config table to SQLite
- ✅ Create ConfigManager class
- ✅ Load defaults from code (no changes to intervals yet)
- **Deploy**: Service still uses hardcoded intervals, but infrastructure ready
- **Risk**: Low - ConfigManager is read-only, doesn't change behavior

### Phase B: Reading Firestore Config
- ✅ ConfigManager reads from Firestore on startup
- ✅ Falls back to code defaults if Firestore missing
- ✅ Caches locally
- **Deploy**: Service now reads Firestore, but loops still hardcoded
- **Risk**: Low - Firestore values match code defaults initially

### Phase C: Dynamic Updates
- ✅ Set up Firestore listener in ConfigManager
- ✅ Update loop intervals to use ConfigManager
- ✅ Web app can change intervals dynamically
- **Deploy**: Full dynamic interval support
- **Risk**: Medium - loops now dynamic, need monitoring

---

## Advantages of This Design

✅ **Single Source of Truth**: Firestore (with local cache fallback)
✅ **Survives Reboots**: Local SQLite persists interval preferences
✅ **Real-Time Updates**: No service restart needed
✅ **Backward Compatible**: Code defaults work if Firestore missing
✅ **Testable**: ConfigManager isolated, easy to unit test
✅ **Observable**: Firestore shows what intervals are active
✅ **Secure**: Device-specific config, hardware_serial scoped
✅ **Economical**: Minimal Firestore reads (only on startup + listener)

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Loop stuck on old interval after change | Listener updates in-memory cache immediately |
| Firestore listener disconnects | Fallback to code defaults, retry connection |
| Invalid interval value from web app (0s, negative) | Validate: 5s minimum, 24hr maximum |
| Device boots before web app configures intervals | Use sensible code defaults as fallback |
| Too many Firestore listener events | Single listener, batch updates |
| Interval change during sleep | Not a problem - reads new value on next cycle |

---

## What To Implement

**Recommended: Full Implementation (Phases A, B, C)**

This gives you:
1. ✅ Device is source of truth (hardcoded → Firestore → local cache)
2. ✅ Web app can observe intervals (Firestore shows config)
3. ✅ Web app can control intervals (listener receives changes)
4. ✅ Intervals persist across reboots (local SQLite)
5. ✅ No service restart needed (dynamic loops)

**Rollout**: 3 commits, each deployable independently, no breaking changes

---

## Next Steps if Approved

1. I'll create `ConfigManager` class with Firestore listening
2. Add SQLite schema for device_config table
3. Update server.py loops to use ConfigManager intervals
4. Add validation for interval values
5. Create setup guide for web app integration
6. Add monitoring logs to track interval changes

---

## Open Questions

1. **Min/Max interval limits**: Should we enforce bounds? (e.g., 5s - 1hr)
2. **Logging interval changes**: Log to device doc in Firestore?
3. **Rate limiting**: Prevent web app from changing interval too frequently?
4. **Gradual rollout**: Roll out to specific devices first?

Would you like me to proceed with the full 4-phase implementation?
