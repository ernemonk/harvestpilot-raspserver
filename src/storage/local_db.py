"""
Local SQLite database operations for HarvestPilot device.
Handles all local data persistence with 30-day rolling storage.
"""

import sqlite3
import time
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from .models import (
    SensorReading,
    HourlySummary,
    Alert,
    Command,
    DeviceEvent,
    CropConfig,
    CommandStatus,
)


class LocalDatabase:
    """SQLite database manager for local device storage."""

    def __init__(self, db_path: str = "data/device.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Device identity (single row)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS device (
                    device_id TEXT PRIMARY KEY,
                    firmware_version TEXT NOT NULL,
                    hardware_revision TEXT NOT NULL,
                    mac_address TEXT NOT NULL,
                    registered_at INTEGER NOT NULL
                )
            """)

            # Sensor readings (rolling 30 days)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER NOT NULL,
                    temperature REAL NOT NULL,
                    humidity REAL NOT NULL,
                    soil_moisture REAL NOT NULL,
                    water_level REAL NOT NULL,
                    light_on INTEGER NOT NULL,
                    pump_on INTEGER NOT NULL
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_readings_timestamp 
                ON sensor_readings(timestamp)
            """)

            # Hourly summaries (for Firestore sync)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hourly_summaries (
                    hour INTEGER PRIMARY KEY,
                    temp_min REAL,
                    temp_max REAL,
                    temp_avg REAL,
                    humidity_min REAL,
                    humidity_max REAL,
                    humidity_avg REAL,
                    soil_moisture_avg REAL,
                    water_level_avg REAL,
                    light_on_minutes INTEGER,
                    pump_on_minutes INTEGER,
                    reading_count INTEGER,
                    synced INTEGER DEFAULT 0
                )
            """)

            # Alerts
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    explanation TEXT,
                    suggested_action TEXT,
                    triggered_at INTEGER NOT NULL,
                    acknowledged_at INTEGER,
                    resolved_at INTEGER,
                    reading_snapshot TEXT,
                    synced INTEGER DEFAULT 0
                )
            """)

            # Events
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    data TEXT,
                    synced INTEGER DEFAULT 0
                )
            """)

            # Commands (received from cloud)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS commands (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    payload TEXT,
                    issued_at INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    executed_at INTEGER,
                    error_message TEXT
                )
            """)

            # Crop configuration
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS crop_config (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    crop_type TEXT NOT NULL,
                    planted_at INTEGER NOT NULL,
                    expected_harvest_days INTEGER NOT NULL,
                    light_on_hour INTEGER NOT NULL,
                    light_off_hour INTEGER NOT NULL,
                    irrigation_interval_hours INTEGER NOT NULL,
                    irrigation_duration_seconds INTEGER NOT NULL,
                    temp_target_min REAL NOT NULL,
                    temp_target_max REAL NOT NULL,
                    humidity_target_min REAL NOT NULL,
                    humidity_target_max REAL NOT NULL
                )
            """)

            # Schedule state
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schedule_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    autopilot_mode TEXT NOT NULL DEFAULT 'on',
                    last_irrigation_at INTEGER,
                    next_irrigation_at INTEGER,
                    failsafe_triggered INTEGER DEFAULT 0,
                    failsafe_reason TEXT
                )
            """)

            # Initialize schedule state if not exists
            cursor.execute("""
                INSERT OR IGNORE INTO schedule_state (id, autopilot_mode)
                VALUES (1, 'on')
            """)

            # Device configuration (intervals and settings)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS device_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    source TEXT,
                    last_updated INTEGER
                )
            """)

    # =========================================================================
    # SENSOR READINGS
    # =========================================================================

    def insert_reading(self, reading: SensorReading) -> None:
        """Insert a new sensor reading."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sensor_readings 
                (timestamp, temperature, humidity, soil_moisture, water_level, light_on, pump_on)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                reading.timestamp,
                reading.temperature,
                reading.humidity,
                reading.soil_moisture,
                reading.water_level,
                1 if reading.light_on else 0,
                1 if reading.pump_on else 0,
            ))

    def get_readings_since(self, since_timestamp: int) -> list[SensorReading]:
        """Get all readings since a given timestamp."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sensor_readings
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
            """, (since_timestamp,))
            
            return [
                SensorReading(
                    timestamp=row['timestamp'],
                    temperature=row['temperature'],
                    humidity=row['humidity'],
                    soilMoisture=row['soil_moisture'],
                    waterLevel=row['water_level'],
                    lightOn=bool(row['light_on']),
                    pumpOn=bool(row['pump_on']),
                )
                for row in cursor.fetchall()
            ]

    def get_latest_reading(self) -> Optional[SensorReading]:
        """Get the most recent sensor reading."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sensor_readings
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            return SensorReading(
                timestamp=row['timestamp'],
                temperature=row['temperature'],
                humidity=row['humidity'],
                soilMoisture=row['soil_moisture'],
                waterLevel=row['water_level'],
                lightOn=bool(row['light_on']),
                pumpOn=bool(row['pump_on']),
            )

    def cleanup_old_readings(self, days: int = 30) -> int:
        """Delete readings older than specified days. Returns count deleted."""
        cutoff = int(time.time() * 1000) - (days * 24 * 60 * 60 * 1000)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sensor_readings WHERE timestamp < ?", (cutoff,))
            return cursor.rowcount

    # =========================================================================
    # HOURLY SUMMARIES
    # =========================================================================

    def compute_hourly_summary(self, hour_start: int) -> Optional[HourlySummary]:
        """Compute hourly summary from readings."""
        hour_end = hour_start + (60 * 60 * 1000)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    MIN(temperature) as temp_min,
                    MAX(temperature) as temp_max,
                    AVG(temperature) as temp_avg,
                    MIN(humidity) as humidity_min,
                    MAX(humidity) as humidity_max,
                    AVG(humidity) as humidity_avg,
                    AVG(soil_moisture) as soil_moisture_avg,
                    AVG(water_level) as water_level_avg,
                    SUM(light_on) as light_on_count,
                    SUM(pump_on) as pump_on_count,
                    COUNT(*) as reading_count
                FROM sensor_readings
                WHERE timestamp >= ? AND timestamp < ?
            """, (hour_start, hour_end))
            
            row = cursor.fetchone()
            
            if row is None or row['reading_count'] == 0:
                return None
            
            # Convert counts to minutes (assuming 1 reading per minute)
            return HourlySummary(
                hour=hour_start,
                tempMin=row['temp_min'],
                tempMax=row['temp_max'],
                tempAvg=row['temp_avg'],
                humidityMin=row['humidity_min'],
                humidityMax=row['humidity_max'],
                humidityAvg=row['humidity_avg'],
                soilMoistureAvg=row['soil_moisture_avg'],
                waterLevelAvg=row['water_level_avg'],
                lightOnMinutes=row['light_on_count'],
                pumpOnMinutes=row['pump_on_count'],
                readingCount=row['reading_count'],
            )

    def save_hourly_summary(self, summary: HourlySummary) -> None:
        """Save or update an hourly summary."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO hourly_summaries
                (hour, temp_min, temp_max, temp_avg, humidity_min, humidity_max, 
                 humidity_avg, soil_moisture_avg, water_level_avg, light_on_minutes,
                 pump_on_minutes, reading_count, synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                summary.hour,
                summary.temp_min,
                summary.temp_max,
                summary.temp_avg,
                summary.humidity_min,
                summary.humidity_max,
                summary.humidity_avg,
                summary.soil_moisture_avg,
                summary.water_level_avg,
                summary.light_on_minutes,
                summary.pump_on_minutes,
                summary.reading_count,
            ))

    def get_unsynced_summaries(self) -> list[HourlySummary]:
        """Get all hourly summaries that haven't been synced."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM hourly_summaries
                WHERE synced = 0
                ORDER BY hour ASC
            """)
            
            return [
                HourlySummary(
                    hour=row['hour'],
                    tempMin=row['temp_min'],
                    tempMax=row['temp_max'],
                    tempAvg=row['temp_avg'],
                    humidityMin=row['humidity_min'],
                    humidityMax=row['humidity_max'],
                    humidityAvg=row['humidity_avg'],
                    soilMoistureAvg=row['soil_moisture_avg'],
                    waterLevelAvg=row['water_level_avg'],
                    lightOnMinutes=row['light_on_minutes'],
                    pumpOnMinutes=row['pump_on_minutes'],
                    readingCount=row['reading_count'],
                )
                for row in cursor.fetchall()
            ]

    def mark_summaries_synced(self, hours: list[int]) -> None:
        """Mark hourly summaries as synced."""
        if not hours:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?'] * len(hours))
            cursor.execute(f"""
                UPDATE hourly_summaries
                SET synced = 1
                WHERE hour IN ({placeholders})
            """, hours)

    # =========================================================================
    # ALERTS
    # =========================================================================

    def insert_alert(self, alert: Alert) -> None:
        """Insert a new alert."""
        import json
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO alerts
                (id, type, severity, title, message, explanation, suggested_action,
                 triggered_at, acknowledged_at, resolved_at, reading_snapshot, synced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                alert.id,
                alert.type.value,
                alert.severity.value,
                alert.title,
                alert.message,
                alert.explanation,
                alert.suggested_action,
                alert.triggered_at,
                alert.acknowledged_at,
                alert.resolved_at,
                json.dumps(alert.reading_snapshot.model_dump()) if alert.reading_snapshot else None,
            ))

    def get_active_alerts(self) -> list[Alert]:
        """Get all unresolved alerts."""
        import json
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM alerts
                WHERE resolved_at IS NULL
                ORDER BY triggered_at DESC
            """)
            
            alerts = []
            for row in cursor.fetchall():
                snapshot = None
                if row['reading_snapshot']:
                    snapshot = SensorReading(**json.loads(row['reading_snapshot']))
                
                alerts.append(Alert(
                    id=row['id'],
                    type=row['type'],
                    severity=row['severity'],
                    title=row['title'],
                    message=row['message'],
                    explanation=row['explanation'],
                    suggestedAction=row['suggested_action'],
                    triggeredAt=row['triggered_at'],
                    acknowledgedAt=row['acknowledged_at'],
                    resolvedAt=row['resolved_at'],
                    readingSnapshot=snapshot,
                ))
            return alerts

    def resolve_alert(self, alert_id: str, resolved_at: int) -> None:
        """Mark an alert as resolved."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE alerts
                SET resolved_at = ?, synced = 0
                WHERE id = ?
            """, (resolved_at, alert_id))

    # =========================================================================
    # COMMANDS
    # =========================================================================

    def insert_command(self, command: Command) -> None:
        """Insert a new command from cloud."""
        import json
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO commands
                (id, type, payload, issued_at, status, executed_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                command.id,
                command.type.value,
                json.dumps(command.payload),
                command.issued_at,
                command.status.value,
                command.executed_at,
                command.error_message,
            ))

    def get_pending_commands(self) -> list[Command]:
        """Get all pending commands."""
        import json
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM commands
                WHERE status = 'pending'
                ORDER BY issued_at ASC
            """)
            
            return [
                Command(
                    id=row['id'],
                    type=row['type'],
                    payload=json.loads(row['payload']) if row['payload'] else {},
                    issuedAt=row['issued_at'],
                    status=row['status'],
                    executedAt=row['executed_at'],
                    errorMessage=row['error_message'],
                )
                for row in cursor.fetchall()
            ]

    def update_command_status(
        self,
        command_id: str,
        status: CommandStatus,
        executed_at: Optional[int] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Update command execution status."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE commands
                SET status = ?, executed_at = ?, error_message = ?
                WHERE id = ?
            """, (status.value, executed_at, error_message, command_id))

    # =========================================================================
    # EVENTS
    # =========================================================================

    def insert_event(self, event: DeviceEvent) -> None:
        """Insert a new event."""
        import json
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO events (id, type, timestamp, data, synced)
                VALUES (?, ?, ?, ?, 0)
            """, (
                event.id,
                event.type.value,
                event.timestamp,
                json.dumps(event.data) if event.data else None,
            ))

    def get_unsynced_events(self) -> list[DeviceEvent]:
        """Get all events that haven't been synced."""
        import json
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM events
                WHERE synced = 0
                ORDER BY timestamp ASC
            """)
            
            return [
                DeviceEvent(
                    id=row['id'],
                    type=row['type'],
                    timestamp=row['timestamp'],
                    data=json.loads(row['data']) if row['data'] else None,
                )
                for row in cursor.fetchall()
            ]

    def mark_events_synced(self, event_ids: list[str]) -> None:
        """Mark events as synced."""
        if not event_ids:
            return
        with self._get_connection() as conn:
            cursor = conn.cursor()
            placeholders = ','.join(['?'] * len(event_ids))
            cursor.execute(f"""
                UPDATE events
                SET synced = 1
                WHERE id IN ({placeholders})
            """, event_ids)

    # =========================================================================
    # CROP CONFIG
    # =========================================================================

    def get_crop_config(self) -> Optional[CropConfig]:
        """Get current crop configuration."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM crop_config WHERE id = 1")
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            return CropConfig(
                cropType=row['crop_type'],
                plantedAt=row['planted_at'],
                expectedHarvestDays=row['expected_harvest_days'],
                lightOnHour=row['light_on_hour'],
                lightOffHour=row['light_off_hour'],
                irrigationIntervalHours=row['irrigation_interval_hours'],
                irrigationDurationSeconds=row['irrigation_duration_seconds'],
                tempTargetMin=row['temp_target_min'],
                tempTargetMax=row['temp_target_max'],
                humidityTargetMin=row['humidity_target_min'],
                humidityTargetMax=row['humidity_target_max'],
            )

    def save_crop_config(self, config: CropConfig) -> None:
        """Save crop configuration."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO crop_config
                (id, crop_type, planted_at, expected_harvest_days, light_on_hour,
                 light_off_hour, irrigation_interval_hours, irrigation_duration_seconds,
                 temp_target_min, temp_target_max, humidity_target_min, humidity_target_max)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                config.crop_type.value,
                config.planted_at,
                config.expected_harvest_days,
                config.light_on_hour,
                config.light_off_hour,
                config.irrigation_interval_hours,
                config.irrigation_duration_seconds,
                config.temp_target_min,
                config.temp_target_max,
                config.humidity_target_min,
                config.humidity_target_max,
            ))

    # =========================================================================
    # SCHEDULE STATE
    # =========================================================================

    def get_schedule_state(self) -> dict:
        """Get current schedule state."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM schedule_state WHERE id = 1")
            row = cursor.fetchone()
            
            if row is None:
                return {
                    "autopilot_mode": "on",
                    "last_irrigation_at": None,
                    "next_irrigation_at": None,
                    "failsafe_triggered": False,
                    "failsafe_reason": None,
                }
            
            return {
                "autopilot_mode": row['autopilot_mode'],
                "last_irrigation_at": row['last_irrigation_at'],
                "next_irrigation_at": row['next_irrigation_at'],
                "failsafe_triggered": bool(row['failsafe_triggered']),
                "failsafe_reason": row['failsafe_reason'],
            }

    def update_schedule_state(self, **kwargs) -> None:
        """Update schedule state fields."""
        if not kwargs:
            return
        
        valid_fields = {
            'autopilot_mode', 'last_irrigation_at', 'next_irrigation_at',
            'failsafe_triggered', 'failsafe_reason'
        }
        
        fields = {k: v for k, v in kwargs.items() if k in valid_fields}
        if not fields:
            return
        
        set_clause = ', '.join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values())
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE schedule_state
                SET {set_clause}
                WHERE id = 1
            """, values)
