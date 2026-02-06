"""
Sync Schedule Analyzer - Shows exactly what's syncing and when

This file documents the current sync strategy for HarvestPilot RaspServer.
"""

# ============================================================================
# SYNC SCHEDULE BREAKDOWN
# ============================================================================

SYNC_STRATEGY = {
    "heartbeat": {
        "interval_seconds": 30,
        "interval_formatted": "Every 30 seconds",
        "daily_operations": 2880,  # 86400 / 30
        "what_syncs": [
            "status: 'online'",
            "lastHeartbeat: SERVER_TIMESTAMP",
            "lastSyncAt: SERVER_TIMESTAMP",
            "device_id",
            "hardware_serial"
        ],
        "location": "src/core/server.py:_heartbeat_loop()",
        "firestore_path": "devices/{hardware_serial}",
        "cost": "~2,880 writes/day = ~0.0576 cents/month"
    },
    
    "health_metrics": {
        "interval_seconds": 300,  # 5 minutes
        "interval_formatted": "Every 5 minutes",
        "daily_operations": 288,  # 86400 / 300
        "what_syncs": [
            "diagnostics.status",
            "diagnostics.uptime_seconds",
            "diagnostics.total_errors",
            "diagnostics.error_rate_percent",
            "diagnostics.firebase_connected",
            "diagnostics.heartbeats_sent",
            "diagnostics.timestamp"
        ],
        "location": "src/core/server.py:_metrics_loop()",
        "firestore_path": "devices/{hardware_serial}",
        "cost": "~288 writes/day = ~0.0058 cents/month"
    },
    
    "full_cloud_sync": {
        "interval_seconds": 1800,  # 30 minutes
        "interval_formatted": "Every 30 minutes",
        "daily_operations": 48,  # 86400 / 1800
        "what_syncs": [
            "Hourly summaries (temperature, humidity, soil_moisture)",
            "Alerts (unsynced)",
            "Events (unsynced)",
            "Device state (current reading, crop config, schedule state)"
        ],
        "location": "src/core/server.py:_sync_to_cloud_loop() -> sync_service.sync_all()",
        "firestore_path": "devices/{hardware_serial}/hourly/*",
        "cost": "~48 writes/day = ~0.001 cents/month"
    },
    
    "sensor_readings": {
        "interval_seconds": 5,
        "interval_formatted": "Every 5 seconds",
        "daily_operations": 17280,  # 86400 / 5
        "what_syncs": [
            "Temperature",
            "Humidity",
            "Soil moisture",
            "Water level",
            "Timestamp"
        ],
        "note": "NOT synced to Firestore immediately - buffered locally",
        "location": "src/core/server.py:_sensor_reading_loop()",
        "buffering": "Stored in memory, flushed to local SQLite every 60s",
        "firestore_cost": "0 (local only)"
    },
    
    "data_aggregation": {
        "interval_seconds": 60,
        "interval_formatted": "Every 60 seconds",
        "daily_operations": 1440,  # 86400 / 60
        "what_syncs": [
            "60-second averages of temperature, humidity, soil_moisture",
            "Min/max values",
            "Sample counts"
        ],
        "location": "src/core/server.py:_aggregation_loop()",
        "storage": "Persisted to local SQLite (not Firestore)",
        "firestore_cost": "0 (local only, synced in 30-min batch)"
    }
}

# ============================================================================
# EXPECTED FIRESTORE UPDATE FREQUENCY
# ============================================================================

"""
If everything is working correctly, you should see these update patterns:

EVERY 30 SECONDS:
  - lastHeartbeat updates
  - lastSyncAt updates
  - status stays "online"
  - heartbeats_sent counter increases

EVERY 5 MINUTES:
  - diagnostics object updates with new metrics
  - Health status may change (healthy/degraded/offline)
  - Error rate recalculated

EVERY 30 MINUTES:
  - Hourly summaries added to devices/{id}/hourly/ subcollection
  - Full device state refreshed
  - All buffered data synced

WHAT YOU SHOULD NOT SEE:
  - status: "offline" (unless service is actually stopped)
  - lastHeartbeat frozen for > 30 seconds
  - No updates for > 30 minutes
"""

# ============================================================================
# DIAGNOSTIC CHECKLIST
# ============================================================================

DIAGNOSTICS = """
If your system IS syncing correctly:

✅ HEARTBEAT SYNC (every 30 seconds)
   - Check: lastHeartbeat timestamp updates
   - Check: status field stays "online"
   - Expected: ~2,880 Firestore writes per day

✅ HEALTH METRICS (every 5 minutes)
   - Check: diagnostics.timestamp updates every 300 seconds
   - Check: diagnostics.uptime_seconds increases monotonically
   - Check: diagnostics.heartbeats_sent keeps growing
   - Expected: ~288 Firestore writes per day

✅ CLOUD SYNC (every 30 minutes)
   - Check: devices/{id}/hourly/* collection gets new documents
   - Check: currentReading field in main document updates
   - Expected: ~48 Firestore writes per day

✅ SENSOR DATA (every 5 seconds)
   - Check: Local SQLite has readings every 5 seconds
   - Check: No Firestore writes (buffered locally)
   - Expected: ~0 Firestore writes (local only)

✅ DATA AGGREGATION (every 60 seconds)
   - Check: Local SQLite has 60-second summaries
   - Check: No immediate Firestore writes
   - Expected: Synced during 30-minute batch


IF YOU'RE NOT SEEING UPDATES:

❌ Heartbeat not syncing (lastHeartbeat frozen)?
   - Check: Pi service status: sudo systemctl status harvestpilot-autodeploy
   - Check: Logs: journalctl -u harvestpilot-autodeploy.service -f
   - Check: Firebase connection in logs (look for connection errors)

❌ Metrics not updating?
   - Check: diagnostics.py is initialized in RaspServer.__init__()
   - Check: _metrics_loop is in the tasks list
   - Check: No exceptions in logs during 5-minute intervals

❌ No hourly syncs?
   - Check: sync_service.py is being called
   - Check: Local data has entries to sync
   - Check: Firestore write permissions are correct

❌ Status shows "offline"?
   - Check: Service is actually running
   - Check: Firebase connection status (look for connection warnings)
   - Check: Last heartbeat time - if recent, connection is working but status not updating
"""

# ============================================================================
# FIRESTORE USAGE & COST
# ============================================================================

FIRESTORE_COSTS = """
Daily Operations Breakdown:
  - Heartbeats:        2,880 writes/day
  - Health metrics:      288 writes/day
  - Cloud sync:           48 writes/day
  - ──────────────────────────────
  - TOTAL:            ~3,216 writes/day

Monthly Cost Estimate:
  - 3,216 writes × 30 days = 96,480 writes/month
  - Firestore Spark plan: 50,000 free reads/day
  - COST: < $0.01/month (well under free tier!)

Note: These calculations assume single device.
With multiple devices, scale accordingly.
"""

# ============================================================================
# CODE REFERENCES
# ============================================================================

CODE_LOCATIONS = """
Where the sync happens in code:

1. HEARTBEAT (every 30 seconds)
   File: src/core/server.py, line 287
   Function: _heartbeat_loop()
   
2. HEALTH METRICS (every 5 minutes)
   File: src/core/server.py, line 314
   Function: _metrics_loop()
   
3. CLOUD SYNC (every 30 minutes)
   File: src/core/server.py, line 274
   Function: _sync_to_cloud_loop()
   Calls: src/sync/sync_service.py:sync_all()

4. SENSOR READING (every 5 seconds)
   File: src/core/server.py, line 157
   Function: _sensor_reading_loop()
   
5. DATA AGGREGATION (every 60 seconds)
   File: src/core/server.py, line 220
   Function: _aggregation_loop()
   Storage: Local SQLite via src/services/database_service.py

6. FIREBASE HEARTBEAT PUBLISH
   File: src/services/firebase_service.py, line 175
   Function: publish_heartbeat()
   Sets: status, lastHeartbeat, lastSyncAt, device_id, hardware_serial
"""

if __name__ == "__main__":
    import json
    
    print("=" * 80)
    print("HarvestPilot RaspServer - SYNC SCHEDULE DOCUMENTATION")
    print("=" * 80)
    print()
    
    print("SYNC INTERVALS:")
    print("-" * 80)
    for key, config in SYNC_STRATEGY.items():
        print(f"\n{key.upper()}")
        print(f"  Interval: {config['interval_formatted']}")
        if 'daily_operations' in config:
            print(f"  Daily ops: {config['daily_operations']}")
        if 'cost' in config:
            print(f"  Cost: {config['cost']}")
    
    print("\n" + "=" * 80)
    print("EXPECTED BEHAVIOR")
    print("=" * 80)
    print(DIAGNOSTICS)
    
    print("\n" + "=" * 80)
    print("FIRESTORE USAGE & COST")
    print("=" * 80)
    print(FIRESTORE_COSTS)
    
    print("\n" + "=" * 80)
    print("CODE REFERENCES")
    print("=" * 80)
    print(CODE_LOCATIONS)
