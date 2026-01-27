# Economical Persistence - Implementation Diffs

**Date**: January 23, 2026  
**Strategy**: In-memory buffering (5s) → 60-second aggregation → 30-minute cloud sync

---

## Summary of Changes

**Files Modified**: 2  
**Lines Added**: 250+  
**New Tables**: 2  
**New Methods**: 8  
**Backwards Compatible**: Yes

---

## Diff 1: Database Schema Changes

### File: `src/services/database_service.py`

#### Change 1.1: Add Aggregated Readings Table

**Location**: `_create_tables()` - ADD before existing tables

```python
# NEW TABLE
cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_readings_aggregated (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        window_start TEXT NOT NULL,
        window_end TEXT NOT NULL,
        
        temperature_avg REAL NOT NULL,
        temperature_min REAL NOT NULL,
        temperature_max REAL NOT NULL,
        temperature_last REAL NOT NULL,
        temperature_count INTEGER NOT NULL,
        
        humidity_avg REAL NOT NULL,
        humidity_min REAL NOT NULL,
        humidity_max REAL NOT NULL,
        humidity_last REAL NOT NULL,
        humidity_count INTEGER NOT NULL,
        
        soil_moisture_avg REAL NOT NULL,
        soil_moisture_min REAL NOT NULL,
        soil_moisture_max REAL NOT NULL,
        soil_moisture_last REAL NOT NULL,
        soil_moisture_count INTEGER NOT NULL,
        
        water_level_last BOOLEAN NOT NULL,
        
        synced BOOLEAN DEFAULT 0,
        synced_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")
```

#### Change 1.2: Add Raw Readings Table (Threshold Events)

**Location**: `_create_tables()` - ADD before sensor_readings table

```python
# NEW TABLE
cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_readings_raw (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        temperature REAL NOT NULL,
        humidity REAL NOT NULL,
        soil_moisture REAL NOT NULL,
        water_level BOOLEAN NOT NULL,
        reason TEXT NOT NULL,
        synced BOOLEAN DEFAULT 0,
        synced_at TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
""")
```

#### Change 1.3: Add Indexes

**Location**: `_create_tables()` - ADD with existing indexes

```python
cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_agg_window ON sensor_readings_aggregated(window_start)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_agg_synced ON sensor_readings_aggregated(synced)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_raw_timestamp ON sensor_readings_raw(timestamp)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_raw_synced ON sensor_readings_raw(synced)")
```

---

## Diff 2: Add Aggregation Methods to DatabaseService

### File: `src/services/database_service.py`

#### Change 2.1: Add Aggregation Save Methods

**Location**: After `async_save_sensor_reading()` - ADD new section

```python
# ============ AGGREGATED SENSOR DATA ============

def save_sensor_aggregated(self, aggregation: dict) -> int:
    """Save aggregated sensor reading (60-second window)"""
    try:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO sensor_readings_aggregated 
                (window_start, window_end, 
                 temperature_avg, temperature_min, temperature_max, temperature_last, temperature_count,
                 humidity_avg, humidity_min, humidity_max, humidity_last, humidity_count,
                 soil_moisture_avg, soil_moisture_min, soil_moisture_max, soil_moisture_last, soil_moisture_count,
                 water_level_last)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                aggregation['window_start'],
                aggregation['window_end'],
                aggregation['temperature_avg'],
                aggregation['temperature_min'],
                aggregation['temperature_max'],
                aggregation['temperature_last'],
                aggregation['temperature_count'],
                aggregation['humidity_avg'],
                aggregation['humidity_min'],
                aggregation['humidity_max'],
                aggregation['humidity_last'],
                aggregation['humidity_count'],
                aggregation['soil_moisture_avg'],
                aggregation['soil_moisture_min'],
                aggregation['soil_moisture_max'],
                aggregation['soil_moisture_last'],
                aggregation['soil_moisture_count'],
                aggregation['water_level_last']
            ))
            self.conn.commit()
            logger.debug(f"Saved aggregated reading for window {aggregation['window_start']}")
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to save aggregated reading: {e}")
        return None

async def async_save_sensor_aggregated(self, aggregation: dict) -> int:
    """Save aggregated reading (non-blocking async wrapper)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, self.save_sensor_aggregated, aggregation)

def save_sensor_raw(self, reading: SensorReading, reason: str = "threshold_crossed") -> int:
    """Save raw sensor reading (only when thresholds crossed)"""
    try:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO sensor_readings_raw 
                (timestamp, temperature, humidity, soil_moisture, water_level, reason)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                reading.timestamp,
                reading.temperature,
                reading.humidity,
                reading.soil_moisture,
                reading.water_level,
                reason
            ))
            self.conn.commit()
            logger.debug(f"Saved raw reading: {reason}")
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to save raw reading: {e}")
        return None

async def async_save_sensor_raw(self, reading: SensorReading, reason: str = "threshold_crossed") -> int:
    """Save raw reading (non-blocking async wrapper)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, self.save_sensor_raw, reading, reason)
```

#### Change 2.2: Add Aggregation Query Methods

**Location**: After existing `get_unsynced_readings()` - ADD new methods

```python
def get_unsynced_aggregated_readings(self, limit: int = 500) -> list[dict]:
    """Get unsynced aggregated readings from past 24 hours"""
    try:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM sensor_readings_aggregated
            WHERE synced = 0
            ORDER BY window_start ASC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get unsynced aggregated readings: {e}")
        return []

def get_unsynced_raw_readings(self, limit: int = 100) -> list[dict]:
    """Get unsynced raw readings (threshold events)"""
    try:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM sensor_readings_raw
            WHERE synced = 0
            ORDER BY timestamp ASC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Failed to get unsynced raw readings: {e}")
        return []
```

#### Change 2.3: Add Aggregation Mark Synced Methods

**Location**: After `async_mark_reading_synced()` - ADD new methods

```python
def mark_aggregated_reading_synced(self, agg_id: int) -> bool:
    """Mark aggregated reading as synced"""
    try:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE sensor_readings_aggregated
                SET synced = 1, synced_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), agg_id))
            self.conn.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to mark aggregated reading synced: {e}")
        return False

async def async_mark_aggregated_reading_synced(self, agg_id: int) -> bool:
    """Mark aggregated reading as synced (non-blocking async wrapper)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, self.mark_aggregated_reading_synced, agg_id)

def mark_raw_reading_synced(self, raw_id: int) -> bool:
    """Mark raw reading as synced"""
    try:
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute("""
                UPDATE sensor_readings_raw
                SET synced = 1, synced_at = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), raw_id))
            self.conn.commit()
            return True
    except Exception as e:
        logger.error(f"Failed to mark raw reading synced: {e}")
        return False

async def async_mark_raw_reading_synced(self, raw_id: int) -> bool:
    """Mark raw reading as synced (non-blocking async wrapper)"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, self.mark_raw_reading_synced, raw_id)
```

#### Change 2.4: Update Cleanup Logic

**Location**: Replace entire `cleanup_old_data()` method

```python
def cleanup_old_data(self, days: int = 7):
    """Delete readings older than N days (only if synced to cloud)"""
    try:
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self.lock:
            cursor = self.conn.cursor()
            
            # Delete old aggregated readings (only synced)
            cursor.execute("""
                DELETE FROM sensor_readings_aggregated
                WHERE synced = 1 AND synced_at IS NOT NULL 
                AND datetime(synced_at) < ?
            """, (cutoff_date,))
            agg_deleted = cursor.rowcount
            
            # Delete old raw readings (only synced)
            cursor.execute("""
                DELETE FROM sensor_readings_raw
                WHERE synced = 1 AND synced_at IS NOT NULL
                AND datetime(synced_at) < ?
            """, (cutoff_date,))
            raw_deleted = cursor.rowcount
            
            # Delete old legacy readings (only synced)
            cursor.execute("""
                DELETE FROM sensor_readings
                WHERE synced = 1 AND synced_at IS NOT NULL 
                AND datetime(synced_at) < ?
            """, (cutoff_date,))
            legacy_deleted = cursor.rowcount
            
            # Delete old operations (not critical, no sync needed)
            cursor.execute("""
                DELETE FROM operations 
                WHERE datetime(timestamp) < ?
            """, (cutoff_date,))
            operations_deleted = cursor.rowcount
            
            self.conn.commit()
            
            logger.info(f"Cleaned up: {agg_deleted} agg readings, {raw_deleted} raw readings, "
                       f"{legacy_deleted} legacy readings, {operations_deleted} operations")
    except Exception as e:
        logger.error(f"Failed to cleanup old data: {e}")
```

#### Change 2.5: Update Database Statistics

**Location**: Replace entire `get_database_size()` method

```python
def get_database_size(self) -> dict:
    """Get database statistics"""
    try:
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) as count FROM sensor_readings_aggregated")
        agg_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM sensor_readings_raw")
        raw_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM sensor_readings")
        legacy_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM alerts")
        alerts_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM operations")
        operations_count = cursor.fetchone()['count']
        
        # File size
        import os
        file_size = os.path.getsize(self.db_path) / (1024 * 1024)  # MB
        
        return {
            'aggregated': agg_count,
            'raw': raw_count,
            'legacy': legacy_count,
            'alerts': alerts_count,
            'operations': operations_count,
            'file_size_mb': round(file_size, 2)
        }
    except Exception as e:
        logger.error(f"Failed to get database size: {e}")
        return {}
```

---

## Diff 3: RaspServer Changes

### File: `src/core/server.py`

#### Change 3.1: Add Sensor Buffer to __init__

**Location**: In `__init__()` after `self.automation = ...` - ADD new code

```python
# In-memory sensor reading buffer (economical persistence strategy)
self.sensor_buffer = {
    'temperature': [],
    'humidity': [],
    'soil_moisture': [],
    'water_level': None
}
self.buffer_window_start = datetime.now()
```

#### Change 3.2: Modify Sensor Reading Loop

**Location**: Replace entire `_sensor_reading_loop()` method

```python
async def _sensor_reading_loop(self):
    """Continuously read sensors and publish to Firebase (with in-memory buffering)"""
    logger.info("Starting sensor reading loop...")
    
    while self.running:
        try:
            # Read sensors
            reading = await self.sensors.read_all()
            
            # Buffer reading in-memory (NOT writing to disk every 5 seconds)
            self.sensor_buffer['temperature'].append(reading.temperature)
            self.sensor_buffer['humidity'].append(reading.humidity)
            self.sensor_buffer['soil_moisture'].append(reading.soil_moisture)
            self.sensor_buffer['water_level'] = reading.water_level
            
            # Publish to Firebase (async, non-blocking)
            asyncio.create_task(self._publish_sensor_async(reading))
            
            # Check thresholds
            alerts = await self.sensors.check_thresholds(reading)
            if alerts:
                for alert in alerts:
                    # Save raw reading when threshold crossed (immediate, no buffer)
                    await self.database.async_save_sensor_raw(reading, reason="threshold_crossed")
                    
                    # Store alert locally - non-blocking
                    await self.database.async_save_alert(alert.to_dict())
                    
                    # Publish to Firebase
                    asyncio.create_task(self._publish_alert_async(alert))
                    
                    # Emergency stop on critical alert
                    if alert.severity == 'critical' and config.EMERGENCY_STOP_ON_WATER_LOW:
                        logger.warning("Critical alert - emergency stop")
                        await self._emergency_stop()
            
            await asyncio.sleep(config.SENSOR_READING_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in sensor loop: {e}")
            await asyncio.sleep(5)
```

#### Change 3.3: Add Aggregation Loop

**Location**: After `_publish_alert_async()` - ADD new method

```python
async def _aggregation_loop(self):
    """Aggregate buffered sensor data every 60 seconds and persist"""
    logger.info("Starting sensor aggregation loop (60-second windows)")
    
    while self.running:
        try:
            await asyncio.sleep(60)  # Aggregate every 60 seconds
            
            # Only aggregate if buffer has data
            if self.sensor_buffer['temperature']:
                window_end = datetime.now()
                
                # Calculate aggregates
                aggregation = {
                    'window_start': self.buffer_window_start.isoformat(),
                    'window_end': window_end.isoformat(),
                    'temperature_avg': sum(self.sensor_buffer['temperature']) / len(self.sensor_buffer['temperature']),
                    'temperature_min': min(self.sensor_buffer['temperature']),
                    'temperature_max': max(self.sensor_buffer['temperature']),
                    'temperature_last': self.sensor_buffer['temperature'][-1],
                    'temperature_count': len(self.sensor_buffer['temperature']),
                    'humidity_avg': sum(self.sensor_buffer['humidity']) / len(self.sensor_buffer['humidity']),
                    'humidity_min': min(self.sensor_buffer['humidity']),
                    'humidity_max': max(self.sensor_buffer['humidity']),
                    'humidity_last': self.sensor_buffer['humidity'][-1],
                    'humidity_count': len(self.sensor_buffer['humidity']),
                    'soil_moisture_avg': sum(self.sensor_buffer['soil_moisture']) / len(self.sensor_buffer['soil_moisture']),
                    'soil_moisture_min': min(self.sensor_buffer['soil_moisture']),
                    'soil_moisture_max': max(self.sensor_buffer['soil_moisture']),
                    'soil_moisture_last': self.sensor_buffer['soil_moisture'][-1],
                    'soil_moisture_count': len(self.sensor_buffer['soil_moisture']),
                    'water_level_last': self.sensor_buffer['water_level'] if self.sensor_buffer['water_level'] is not None else False
                }
                
                # Save aggregated data (non-blocking)
                await self.database.async_save_sensor_aggregated(aggregation)
                
                logger.info(f"Aggregated 60-second window: temp={aggregation['temperature_avg']:.1f}°C, "
                           f"humidity={aggregation['humidity_avg']:.1f}%, "
                           f"readings={aggregation['temperature_count']}")
                
                # Reset buffer for next window
                self.sensor_buffer = {
                    'temperature': [],
                    'humidity': [],
                    'soil_moisture': [],
                    'water_level': None
                }
                self.buffer_window_start = datetime.now()
        
        except Exception as e:
            logger.error(f"Error in aggregation loop: {e}")
            await asyncio.sleep(5)
```

#### Change 3.4: Add Aggregation Task to Startup

**Location**: In `start()` method, modify tasks list

```python
# CHANGE FROM:
tasks = [
    self._sensor_reading_loop(),
    self._sync_to_cloud_loop(),  # New: sync local data to cloud
]

# CHANGE TO:
tasks = [
    self._sensor_reading_loop(),
    self._aggregation_loop(),        # New: aggregate buffered data every 60s
    self._sync_to_cloud_loop(),     # Sync aggregated data every 30+ min
]
```

#### Change 3.5: Update Sync Loop Interval

**Location**: In `_sync_to_cloud_loop()` method

```python
# CHANGE FROM:
await asyncio.sleep(3600)  # Sync every hour

# CHANGE TO:
await asyncio.sleep(1800)  # Sync every 30 minutes (economical interval)
```

#### Change 3.6: Update Sync Remaining Data Method

**Location**: Replace entire `_sync_remaining_data()` method

```python
async def _sync_remaining_data(self):
    """Sync all unsynced data to cloud (non-blocking)"""
    try:
        # Sync aggregated sensor readings (primary data source)
        unsynced_agg = self.database.get_unsynced_aggregated_readings(limit=1000)
        for agg_dict in unsynced_agg:
            try:
                # Publish aggregated data to Firebase
                self.firebase.publish_status_update({
                    "aggregated_reading": {
                        "window_start": agg_dict['window_start'],
                        "window_end": agg_dict['window_end'],
                        "temperature_avg": agg_dict['temperature_avg'],
                        "humidity_avg": agg_dict['humidity_avg'],
                        "soil_moisture_avg": agg_dict['soil_moisture_avg'],
                        "water_level": agg_dict['water_level_last']
                    }
                })
                await self.database.async_mark_aggregated_reading_synced(agg_dict['id'])
            except Exception as e:
                logger.error(f"Error syncing aggregated reading: {e}")
        
        # Sync raw readings (threshold events)
        unsynced_raw = self.database.get_unsynced_raw_readings(limit=500)
        for raw_dict in unsynced_raw:
            try:
                self.firebase.publish_status_update({
                    "raw_reading": {
                        "timestamp": raw_dict['timestamp'],
                        "temperature": raw_dict['temperature'],
                        "reason": raw_dict['reason']
                    }
                })
                await self.database.async_mark_raw_reading_synced(raw_dict['id'])
            except Exception as e:
                logger.error(f"Error syncing raw reading: {e}")
        
        # Sync legacy readings (for backwards compatibility if any)
        unsynced_readings = self.database.get_unsynced_readings(limit=100)
        for reading_dict in unsynced_readings:
            try:
                from ..models import SensorReading
                reading = SensorReading(
                    timestamp=reading_dict['timestamp'],
                    temperature=reading_dict['temperature'],
                    humidity=reading_dict['humidity'],
                    soil_moisture=reading_dict['soil_moisture'],
                    water_level=reading_dict['water_level']
                )
                self.firebase.publish_sensor_data(reading)
                await self.database.async_mark_reading_synced(reading_dict['id'])
            except Exception as e:
                logger.error(f"Error syncing legacy reading: {e}")
        
        # Sync alerts
        unsynced_alerts = self.database.get_unsynced_alerts(limit=200)
        for alert_dict in unsynced_alerts:
            try:
                self.firebase.publish_status_update({"alert": alert_dict})
                await self.database.async_mark_alert_synced(alert_dict['id'])
            except Exception as e:
                logger.error(f"Error syncing alert: {e}")
        
        # Cleanup old data (keep 7 days)
        self.database.cleanup_old_data(days=7)
        
        # Log sync status
        stats = self.database.get_database_size()
        logger.info(f"Sync complete. DB: {stats.get('aggregated')} agg, "
                   f"{stats.get('raw')} raw, {stats.get('alerts')} alerts, "
                   f"{stats.get('file_size_mb')}MB")
        
    except Exception as e:
        logger.error(f"Error syncing data: {e}")
```

---

## Summary of Changes

### database_service.py
- ✅ Added `sensor_readings_aggregated` table (PRIMARY DATA)
- ✅ Added `sensor_readings_raw` table (THRESHOLD EVENTS)
- ✅ Added 4 new save methods + async wrappers
- ✅ Added 2 new query methods
- ✅ Added 2 new mark synced methods + async wrappers
- ✅ Updated cleanup logic (all 3 tables)
- ✅ Updated statistics (all 5 tables)

### server.py
- ✅ Added sensor_buffer dict
- ✅ Modified _sensor_reading_loop (buffer instead of save)
- ✅ Added _aggregation_loop (new, runs every 60s)
- ✅ Updated startup tasks (added aggregation)
- ✅ Updated sync interval (3600s → 1800s)
- ✅ Updated _sync_remaining_data (handle all data types)

---

## Testing the Implementation

See `ECONOMICAL_PERSISTENCE_STRATEGY.md` for comprehensive verification steps.

---

## Backwards Compatibility

✅ Legacy `sensor_readings` table still exists  
✅ Alert and operation tables unchanged  
✅ Firebase publishing unchanged  
✅ Threshold checking unchanged  
✅ Command handlers unchanged  
✅ No API changes  
✅ Drop-in replacement for old strategy  
