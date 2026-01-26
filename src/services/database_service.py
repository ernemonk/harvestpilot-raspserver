"""Database service - SQLite local storage for sensor data"""

import sqlite3
import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from ..models import SensorReading

logger = logging.getLogger(__name__)


class DatabaseService:
    """Local SQLite database for sensor readings and logs"""
    
    def __init__(self, db_path: str = None):
        # Resolve absolute path
        if db_path is None:
            # Use absolute path in /var/lib/harvestpilot or user home
            import os
            db_dir = os.getenv('HARVEST_DATA_DIR', None)
            if not db_dir:
                # Fallback: use home directory
                db_dir = Path.home() / "harvestpilot" / "data"
            else:
                db_dir = Path(db_dir)
            db_path = str(db_dir / "raspserver.db")
        
        self.db_path = Path(db_path).resolve()
        self.conn = None
        self.lock = Lock()  # Thread-safe access
        self._init_db()
    
    def _init_db(self):
        """Initialize database and create tables"""
        try:
            # Create data directory if it doesn't exist
            self.db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            
            # Verify directory is writable
            if not self.db_path.parent.is_dir():
                raise RuntimeError(f"Failed to create directory: {self.db_path.parent}")
            
            if not os.access(self.db_path.parent, os.W_OK):
                raise PermissionError(f"Directory not writable: {self.db_path.parent}")
            
            # Connect to SQLite with timeout and proper config
            self.conn = sqlite3.connect(
                str(self.db_path),
                timeout=10.0,
                check_same_thread=False,  # Allow async/thread access
                isolation_level=None  # Use autocommit mode for safety
            )
            self.conn.row_factory = sqlite3.Row
            
            # Enable WAL mode for better concurrency
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            
            self._create_tables()
            
            logger.info(f"Database initialized at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}", exc_info=True)
            raise
    
    def _create_tables(self):
        """Create database tables with transaction isolation"""
        try:
            cursor = self.conn.cursor()
            
            # Aggregated sensor readings (60-second windows)
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
            
            # Raw sensor readings (only when thresholds crossed)
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
            
            # Raw sensor readings (buffered writes - only threshold crossings + alerts)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sensor_readings_raw (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    temperature REAL NOT NULL,
                    humidity REAL NOT NULL,
                    soil_moisture REAL NOT NULL,
                    water_level BOOLEAN NOT NULL,
                    reason TEXT,
                    synced BOOLEAN DEFAULT 0,
                    synced_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Aggregated sensor readings (economical storage - 1 row per 60 seconds)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sensor_readings_aggregated (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    period_start TEXT NOT NULL,
                    period_end TEXT NOT NULL,
                    temperature_avg REAL NOT NULL,
                    temperature_min REAL NOT NULL,
                    temperature_max REAL NOT NULL,
                    temperature_last REAL NOT NULL,
                    humidity_avg REAL NOT NULL,
                    humidity_min REAL NOT NULL,
                    humidity_max REAL NOT NULL,
                    humidity_last REAL NOT NULL,
                    soil_moisture_avg REAL NOT NULL,
                    soil_moisture_min REAL NOT NULL,
                    soil_moisture_max REAL NOT NULL,
                    soil_moisture_last REAL NOT NULL,
                    water_level_last BOOLEAN NOT NULL,
                    sample_count INTEGER NOT NULL,
                    synced BOOLEAN DEFAULT 0,
                    synced_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Legacy table for backward compatibility
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    temperature REAL NOT NULL,
                    humidity REAL NOT NULL,
                    soil_moisture REAL NOT NULL,
                    water_level BOOLEAN NOT NULL,
                    synced BOOLEAN DEFAULT 0,
                    synced_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    sensor_type TEXT NOT NULL,
                    current_value REAL NOT NULL,
                    threshold REAL NOT NULL,
                    synced BOOLEAN DEFAULT 0,
                    synced_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Device operations log (pump, lights, motors)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    device_type TEXT NOT NULL,
                    action TEXT NOT NULL,
                    params TEXT,
                    status TEXT,
                    duration_seconds INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for faster queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_agg_window ON sensor_readings_aggregated(window_start)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_agg_synced ON sensor_readings_aggregated(synced)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_raw_timestamp ON sensor_readings_raw(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_raw_synced ON sensor_readings_raw(synced)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON sensor_readings(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_readings_synced ON sensor_readings(synced)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_synced ON alerts(synced)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_operations_timestamp ON operations(timestamp)")
            
            self.conn.commit()
            logger.debug("Database tables created/verified")
        except Exception as e:
            logger.error(f"Failed to create tables: {e}", exc_info=True)
            self.conn.rollback()
            raise
    
    # ============ SENSOR READINGS ============
    
    def save_sensor_reading(self, reading: SensorReading) -> int:
        """Save sensor reading to database (sync version)"""
        try:
            with self.lock:  # Thread-safe write
                cursor = self.conn.cursor()
                cursor.execute("""
                    INSERT INTO sensor_readings 
                    (timestamp, temperature, humidity, soil_moisture, water_level)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    reading.timestamp,
                    reading.temperature,
                    reading.humidity,
                    reading.soil_moisture,
                    reading.water_level
                ))
                self.conn.commit()
                
                logger.debug(f"Saved sensor reading: {reading.timestamp}")
                return cursor.lastrowid
            
        except Exception as e:
            logger.error(f"Failed to save sensor reading: {e}")
            return None

    async def async_save_sensor_reading(self, reading: SensorReading) -> int:
        """Save sensor reading (non-blocking async wrapper)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.save_sensor_reading, reading)
    
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
    
    def get_readings_since(self, hours: int) -> list[dict]:
        """Get sensor readings from last N hours"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM sensor_readings 
                WHERE datetime(timestamp) > datetime('now', ?)
                ORDER BY timestamp DESC
            """, (f'-{hours} hours',))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Failed to get readings: {e}")
            return []
    
    def get_readings_range(self, start_time: str, end_time: str) -> list[dict]:
        """Get sensor readings in time range"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM sensor_readings 
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp DESC
            """, (start_time, end_time))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Failed to get readings range: {e}")
            return []
    
    def get_unsynced_readings(self, limit: int = 100) -> list[dict]:
        """Get readings not yet synced to cloud"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM sensor_readings 
                WHERE synced = 0
                ORDER BY timestamp ASC
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Failed to get unsynced readings: {e}")
            return []
    
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
    
    def mark_reading_synced(self, reading_id: int) -> bool:
        """Mark reading as synced to cloud"""
        try:
            with self.lock:
                cursor = self.conn.cursor()
                cursor.execute("""
                    UPDATE sensor_readings 
                    SET synced = 1, synced_at = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), reading_id))
                
                self.conn.commit()
                return True
            
        except Exception as e:
            logger.error(f"Failed to mark reading synced: {e}")
            return False

    async def async_mark_reading_synced(self, reading_id: int) -> bool:
        """Mark reading as synced (non-blocking async wrapper)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.mark_reading_synced, reading_id)
    
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
    
    def get_latest_reading(self) -> dict:
        """Get most recent sensor reading"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM sensor_readings 
                ORDER BY timestamp DESC 
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            return dict(row) if row else None
            
        except Exception as e:
            logger.error(f"Failed to get latest reading: {e}")
            return None
    
    # ============ ALERTS ============
    
    def save_alert(self, alert: dict) -> int:
        """Save threshold alert"""
        try:
            with self.lock:
                cursor = self.conn.cursor()
                cursor.execute("""
                    INSERT INTO alerts 
                    (timestamp, severity, sensor_type, current_value, threshold)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    alert.get('timestamp'),
                    alert.get('severity'),
                    alert.get('sensor_type'),
                    alert.get('current_value'),
                    alert.get('threshold')
                ))
                self.conn.commit()
                
                logger.info(f"Alert saved: {alert.get('sensor_type')} ({alert.get('severity')})")
                return cursor.lastrowid
            
        except Exception as e:
            logger.error(f"Failed to save alert: {e}")
            return None

    async def async_save_alert(self, alert: dict) -> int:
        """Save alert (non-blocking async wrapper)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.save_alert, alert)
    
    def get_unsynced_alerts(self, limit: int = 50) -> list[dict]:
        """Get alerts not yet synced to cloud"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM alerts 
                WHERE synced = 0
                ORDER BY timestamp ASC
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Failed to get unsynced alerts: {e}")
            return []
    
    def mark_alert_synced(self, alert_id: int) -> bool:
        """Mark alert as synced"""
        try:
            with self.lock:
                cursor = self.conn.cursor()
                cursor.execute("""
                    UPDATE alerts 
                    SET synced = 1, synced_at = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), alert_id))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to mark alert synced: {e}")
            return False

    async def async_mark_alert_synced(self, alert_id: int) -> bool:
        """Mark alert as synced (non-blocking async wrapper)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.mark_alert_synced, alert_id)
    
    def get_recent_alerts(self, hours: int = 24) -> list[dict]:
        """Get recent alerts"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT * FROM alerts 
                WHERE datetime(timestamp) > datetime('now', ?)
                ORDER BY timestamp DESC
            """, (f'-{hours} hours',))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Failed to get recent alerts: {e}")
            return []
    
    # ============ OPERATIONS ============
    
    def log_operation(self, device_type: str, action: str, params: dict = None, 
                      status: str = "started", duration: int = None) -> int:
        """Log device operation (pump, lights, motors)"""
        try:
            import json
            with self.lock:
                cursor = self.conn.cursor()
                cursor.execute("""
                    INSERT INTO operations 
                    (timestamp, device_type, action, params, status, duration_seconds)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    datetime.now().isoformat(),
                    device_type,
                    action,
                    json.dumps(params) if params else None,
                    status,
                    duration
                ))
                self.conn.commit()
                
                logger.debug(f"Logged operation: {device_type}.{action}")
                return cursor.lastrowid
            
        except Exception as e:
            logger.error(f"Failed to log operation: {e}")
            return None

    async def async_log_operation(self, device_type: str, action: str, params: dict = None,
                                   status: str = "started", duration: int = None) -> int:
        """Log operation (non-blocking async wrapper)"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.log_operation, device_type, action, params, status, duration
        )
    
    def get_operation_history(self, device_type: str = None, hours: int = 24) -> list[dict]:
        """Get operation history"""
        try:
            cursor = self.conn.cursor()
            
            if device_type:
                cursor.execute("""
                    SELECT * FROM operations 
                    WHERE device_type = ? AND datetime(timestamp) > datetime('now', ?)
                    ORDER BY timestamp DESC
                """, (device_type, f'-{hours} hours'))
            else:
                cursor.execute("""
                    SELECT * FROM operations 
                    WHERE datetime(timestamp) > datetime('now', ?)
                    ORDER BY timestamp DESC
                """, (f'-{hours} hours',))
            
            return [dict(row) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Failed to get operation history: {e}")
            return []
    
    # ============ CLEANUP ============
    
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
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
