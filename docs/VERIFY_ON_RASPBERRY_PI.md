# How to Verify the SQLite Implementation on Raspberry Pi

**Purpose**: Step-by-step guide to test and verify all fixes on actual Raspberry Pi hardware.

---

## Prerequisites

- Raspberry Pi 4 with Raspberry Pi OS
- Python 3.9+ installed
- HarvestPilot code deployed to `/opt/harvestpilot`
- Systemd service configured

---

## Part 1: Pre-Deployment Verification (On Development Machine)

### 1.1 Verify Async Wrappers Exist

```bash
cd /path/to/harvestpilot-raspserver

# Check async methods are defined
grep -n "async def async_" src/services/database_service.py
```

Expected output:
```
xxx: async def async_save_sensor_reading(self, reading: SensorReading) -> int:
xxx: async def async_mark_reading_synced(self, reading_id: int) -> bool:
xxx: async def async_save_alert(self, alert: dict) -> int:
xxx: async def async_mark_alert_synced(self, alert_id: int) -> bool:
xxx: async def async_log_operation(...) -> int:
```

### 1.2 Verify Thread Safety Lock Added

```bash
# Check Lock is imported
grep "from threading import Lock" src/services/database_service.py

# Check lock is used in methods
grep -c "with self.lock:" src/services/database_service.py
```

Expected output:
```
src/services/database_service.py: from threading import Lock
6  # Should show 6+ uses of self.lock
```

### 1.3 Verify Cleanup Logic Fixed

```bash
# Check for new cleanup query with synced_at
grep -A 3 "DELETE FROM sensor_readings" src/services/database_service.py | head -10
```

Expected output:
```
DELETE FROM sensor_readings 
WHERE synced = 1 AND synced_at IS NOT NULL 
AND datetime(synced_at) < ?
```

### 1.4 Verify RaspServer Uses Async Methods

```bash
# Check sensor loop uses async methods
grep "await self.database.async_save_sensor_reading" src/core/server.py

# Check sync loop uses async methods
grep "await self.database.async_mark_reading_synced" src/core/server.py
```

Should find multiple references to async methods.

---

## Part 2: Raspberry Pi Setup

### 2.1 Create Data Directory

SSH into Raspberry Pi:

```bash
ssh pi@raspberrypi.local

# Create directory structure
sudo mkdir -p /var/lib/harvestpilot/data
sudo mkdir -p /var/lib/harvestpilot/logs

# Create service user
sudo useradd -s /bin/false -m -d /var/lib/harvestpilot harvest-server 2>/dev/null || true

# Set ownership
sudo chown -R harvest-server:harvest-server /var/lib/harvestpilot
sudo chmod 755 /var/lib/harvestpilot
sudo chmod 755 /var/lib/harvestpilot/data
sudo chmod 755 /var/lib/harvestpilot/logs

# Verify
ls -la /var/lib/harvestpilot/
```

Expected output:
```
total 12
drwxr-xr-x 4 harvest-server harvest-server 4096 Jan 23 10:00 .
drwxr-xr-x 18 root           root          4096 Jan 23 10:00 ..
drwxr-xr-x 2 harvest-server harvest-server 4096 Jan 23 10:00 data
drwxr-xr-x 2 harvest-server harvest-server 4096 Jan 23 10:00 logs
```

### 2.2 Create Systemd Service File

```bash
sudo nano /etc/systemd/system/harvest-server.service
```

Add:
```ini
[Unit]
Description=HarvestPilot Raspberry Pi Server
After=network.target

[Service]
Type=simple
User=harvest-server
Group=harvest-server
WorkingDirectory=/opt/harvestpilot

# Set environment variable for database path
Environment="HARVEST_DATA_DIR=/var/lib/harvestpilot/data"
Environment="PYTHONUNBUFFERED=1"

ExecStart=/usr/bin/python3 -m harvestpilot.main
Restart=always
RestartSec=10

StandardOutput=journal
StandardError=journal
SyslogIdentifier=harvest-server

[Install]
WantedBy=multi-user.target
```

Enable and reload:
```bash
sudo systemctl daemon-reload
sudo systemctl enable harvest-server
```

---

## Part 3: Runtime Verification

### 3.1 Start Service and Check Logs

```bash
# Start the service
sudo systemctl start harvest-server

# Wait 5 seconds for initialization
sleep 5

# Check service status
sudo systemctl status harvest-server

# Follow logs in real-time
sudo journalctl -u harvest-server -f
```

Expected log output:
```
Jan 23 10:15:30 raspberrypi harvest-server[1234]: Initializing HarvestPilot RaspServer...
Jan 23 10:15:30 raspberrypi harvest-server[1234]: Database initialized at /var/lib/harvestpilot/data/raspserver.db
Jan 23 10:15:30 raspberrypi harvest-server[1234]: Starting HarvestPilot RaspServer...
Jan 23 10:15:30 raspberrypi harvest-server[1234]: Starting sensor reading loop...
Jan 23 10:15:30 raspberrypi harvest-server[1234]: Starting cloud sync loop
```

### 3.2 Verify Database File Created

```bash
# Check file exists
ls -la /var/lib/harvestpilot/data/

# Check file size (should grow as readings are added)
du -h /var/lib/harvestpilot/data/raspserver.db
```

### 3.3 Verify Database Schema

```bash
# Connect to database as harvest-server user
sudo -u harvest-server sqlite3 /var/lib/harvestpilot/data/raspserver.db

# In SQLite prompt:
.tables
```

Expected output:
```
alerts     operations  sensor_readings
```

### 3.4 Verify WAL Mode Enabled

```bash
# Still in SQLite prompt:
PRAGMA journal_mode;
```

Expected output:
```
wal
```

### 3.5 Verify Tables Structure

```bash
# Still in SQLite prompt:
.schema sensor_readings
```

Expected output:
```
CREATE TABLE sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    temperature REAL NOT NULL,
    humidity REAL NOT NULL,
    soil_moisture REAL NOT NULL,
    water_level BOOLEAN NOT NULL,
    synced BOOLEAN DEFAULT 0,
    synced_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

### 3.6 Check Indexes

```bash
# Still in SQLite prompt:
.indexes sensor_readings
```

Expected output:
```
idx_readings_synced
idx_readings_timestamp
```

### 3.7 Exit SQLite

```bash
.quit
```

---

## Part 4: Functional Testing

### 4.1 Let Service Run and Collect Data

```bash
# Wait for 10 minutes of readings (120 readings at 5-second intervals)
sleep 600

# Check reading count
sudo -u harvest-server sqlite3 /var/lib/harvestpilot/data/raspserver.db \
  "SELECT COUNT(*) as count FROM sensor_readings;"
```

Expected output:
```
count
120
```

*(May vary slightly depending on timing and any errors)*

### 4.2 Check Unsynced Data

```bash
# Count unsynced readings (should be all of them until Firebase sync)
sudo -u harvest-server sqlite3 /var/lib/harvestpilot/data/raspserver.db \
  "SELECT COUNT(*) FROM sensor_readings WHERE synced = 0;"
```

Expected output:
```
120
```

### 4.3 Check for Blocking Issues

Look at logs for consistent timing - no large gaps:

```bash
sudo journalctl -u harvest-server | grep "Saved sensor reading" | tail -20
```

Expected: Readings approximately every 5 seconds with no gaps > 10 seconds.

### 4.4 Sample Data Query

```bash
# Get last 5 readings
sudo -u harvest-server sqlite3 /var/lib/harvestpilot/data/raspserver.db \
  "SELECT timestamp, temperature, humidity FROM sensor_readings ORDER BY timestamp DESC LIMIT 5;"
```

Expected output:
```
2026-01-23T10:15:30.123456|23.45|65.2
2026-01-23T10:15:25.098765|23.44|65.1
2026-01-23T10:15:20.087654|23.46|65.3
2026-01-23T10:15:15.076543|23.45|65.2
2026-01-23T10:15:10.065432|23.43|65.0
```

---

## Part 5: Stress Testing

### 5.1 Run for Extended Period

Let the service run for at least 2-3 hours to test:
- Continuous operation
- Database size growth
- No data corruption
- Consistent performance

```bash
# Check database size after 2 hours
du -h /var/lib/harvestpilot/data/raspserver.db

# Check record count
sudo -u harvest-server sqlite3 /var/lib/harvestpilot/data/raspserver.db \
  "SELECT COUNT(*) FROM sensor_readings;"
```

Expected for 2 hours:
- ~1,440 readings (2 hours × 60 min × 12 per min)
- Database size: 100KB - 200KB

### 5.2 Monitor Service Health

```bash
# Check service is still running
sudo systemctl status harvest-server

# Check for errors in logs
sudo journalctl -u harvest-server | grep -i error | tail -20
```

Should show minimal errors (only expected ones like Firebase connection issues).

---

## Part 6: Cleanup Testing

### 6.1 Insert Old Test Data

```bash
# Connect to database
sudo -u harvest-server sqlite3 /var/lib/harvestpilot/data/raspserver.db

# Insert test reading from 8 days ago (synced)
INSERT INTO sensor_readings (timestamp, temperature, humidity, soil_moisture, water_level, synced, synced_at)
VALUES (datetime('now', '-8 days'), 25.0, 60.0, 70.0, 1, datetime('now', '-8 days'));

# Insert test reading from 30 days ago (NOT synced)
INSERT INTO sensor_readings (timestamp, temperature, humidity, soil_moisture, water_level, synced, synced_at)
VALUES (datetime('now', '-30 days'), 25.0, 60.0, 70.0, 0, NULL);

# Verify insertion
SELECT count(*), max(datetime(timestamp)) FROM sensor_readings;

# Exit
.quit
```

### 6.2 Trigger Cleanup

```bash
# Restart service (cleanup runs in sync loop)
sudo systemctl restart harvest-server

# Wait for cleanup to run (sync loop runs every 60 seconds)
sleep 70

# Check what remains
sudo -u harvest-server sqlite3 /var/lib/harvestpilot/data/raspserver.db \
  "SELECT COUNT(*) FROM sensor_readings;"
```

Expected:
- Old synced reading from 8 days ago: DELETED ✅
- Old unsynced reading from 30 days ago: PRESERVED ✅

### 6.3 Verify Cleanup Logic

```bash
# Query to see remaining old data
sudo -u harvest-server sqlite3 /var/lib/harvestpilot/data/raspserver.db \
  "SELECT datetime(timestamp) as age, synced, synced_at FROM sensor_readings ORDER BY timestamp ASC LIMIT 5;"
```

The 30-day-old unsynced reading should be there; the 8-day-old synced one should be gone.

---

## Part 7: Error Recovery Testing

### 7.1 Test Permission Handling

```bash
# Remove write permission temporarily
sudo chmod 444 /var/lib/harvestpilot/data

# Try to restart service
sudo systemctl restart harvest-server

# Should fail with permission error in logs
sudo journalctl -u harvest-server | grep -i "permission\|writable"

# Restore permissions
sudo chmod 755 /var/lib/harvestpilot/data

# Service should start successfully now
sudo systemctl restart harvest-server
sleep 5
sudo systemctl status harvest-server
```

### 7.2 Test Database Recovery

```bash
# Check database can be repaired if corruption occurs
sudo -u harvest-server sqlite3 /var/lib/harvestpilot/data/raspserver.db "PRAGMA integrity_check;"
```

Expected output:
```
ok
```

---

## Part 8: Performance Metrics

### 8.1 Check Performance

```bash
# Get database page count and file size
sudo -u harvest-server sqlite3 /var/lib/harvestpilot/data/raspserver.db \
  "PRAGMA page_count; PRAGMA page_size;"

# Query execution time
time sudo -u harvest-server sqlite3 /var/lib/harvestpilot/data/raspserver.db \
  "SELECT COUNT(*) FROM sensor_readings;"
```

Queries should complete in < 100ms even with 10,000+ records.

### 8.2 Index Effectiveness

```bash
# Show index usage
sudo -u harvest-server sqlite3 /var/lib/harvestpilot/data/raspserver.db \
  "SELECT * FROM sqlite_stat1 ORDER BY tbl;"
```

Should show indexes are being used for timestamp and synced queries.

---

## Troubleshooting Guide

### Issue: Database file not created

**Symptoms**:
```
ERROR: Failed to initialize database: [Errno 13] Permission denied
```

**Solution**:
```bash
sudo chown harvest-server:harvest-server /var/lib/harvestpilot/data
sudo chmod 755 /var/lib/harvestpilot/data
sudo systemctl restart harvest-server
```

### Issue: No sensor readings being saved

**Symptoms**:
```
SELECT COUNT(*) FROM sensor_readings;
0
```

**Solution**:
1. Check service is running: `sudo systemctl status harvest-server`
2. Check logs: `sudo journalctl -u harvest-server -f`
3. Look for error messages about database or sensors
4. Verify GPIO pins are connected properly

### Issue: Database grows too quickly

**Symptoms**:
```
du -h /var/lib/harvestpilot/data/raspserver.db
# Shows 1GB+ after 1 day
```

**Solution**:
This likely means readings are not being synced to Firebase.
1. Check Firebase connectivity: `sudo journalctl -u harvest-server | grep -i firebase`
2. Manually trigger sync: Restart service to force sync
3. Check synced column: `SELECT COUNT(*) FROM sensor_readings WHERE synced = 1;`

### Issue: Cleanup not running

**Symptoms**:
Old data not being deleted after 7 days.

**Solution**:
1. Check sync loop is running: `sudo journalctl -u harvest-server | grep "Sync complete"`
2. Verify synced_at timestamps exist: `SELECT COUNT(*) FROM sensor_readings WHERE synced_at IS NOT NULL;`
3. Manual cleanup:
   ```bash
   sudo -u harvest-server sqlite3 /var/lib/harvestpilot/data/raspserver.db \
     "DELETE FROM sensor_readings WHERE synced = 1 AND synced_at IS NOT NULL AND datetime(synced_at) < datetime('now', '-7 days');"
   ```

---

## Success Criteria

✅ All tests pass if:

1. **Database created** at correct path with proper permissions
2. **WAL mode enabled** (PRAGMA journal_mode = wal)
3. **Schema created** with all 3 tables and indexes
4. **Readings collected** ~1 per 5 seconds (120+ per 10 minutes)
5. **No blocking issues** - logs show consistent timing, no gaps
6. **Thread safety works** - no errors, no data corruption
7. **Cleanup logic correct** - synced old data deleted, unsynced preserved
8. **Service stable** - runs > 3 hours without errors
9. **Queries fast** - execution < 100ms even with 10,000+ records
10. **Error handling** - permission errors caught and logged properly

---

## Summary

This comprehensive testing guide verifies:
- ✅ Database schema reliability
- ✅ Async non-blocking operations
- ✅ Thread safety and transaction isolation
- ✅ Cleanup logic preserves unsynced data
- ✅ Permission handling for systemd services
- ✅ Performance under load
- ✅ Error recovery

Once all tests pass, the implementation is **production-ready** for Raspberry Pi deployment.
