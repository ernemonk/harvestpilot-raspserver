"""
Pydantic models derived from contracts/schema.ts
This file is the Python equivalent of the canonical TypeScript schema.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional
from enum import Enum

# =============================================================================
# SYSTEM CONSTANTS (mirrored from schema.ts)
# =============================================================================

SYNC_INTERVAL_MS = 30 * 60 * 1000  # 30 minutes (economical batch sync)
SENSOR_POLL_INTERVAL_MS = 60 * 1000  # 60 seconds
HEARTBEAT_INTERVAL_MS = 30 * 1000  # 30 seconds (keep-alive)
COMMAND_POLL_INTERVAL_MS = 30 * 1000  # 30 seconds

FAILSAFE_WATER_LEVEL_PERCENT = 20
FAILSAFE_TEMP_HIGH_F = 95
FAILSAFE_TEMP_HIGH_DURATION_MIN = 30


# =============================================================================
# ENUMS
# =============================================================================

class CropType(str, Enum):
    BROCCOLI_MICROGREENS = "broccoli_microgreens"
    BASIL = "basil"
    SUNFLOWER = "sunflower"
    RADISH = "radish"
    ARUGULA = "arugula"
    CHIA = "chia"
    CUSTOM = "custom"


class DeviceStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"


class AutopilotMode(str, Enum):
    ON = "on"
    OFF = "off"
    PAUSED = "paused"


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertType(str, Enum):
    WATER_LOW = "water_low"
    WATER_EMPTY = "water_empty"
    TEMP_HIGH = "temp_high"
    TEMP_LOW = "temp_low"
    HUMIDITY_HIGH = "humidity_high"
    HUMIDITY_LOW = "humidity_low"
    SENSOR_FAILURE = "sensor_failure"
    PUMP_FAILURE = "pump_failure"
    OFFLINE = "offline"


class CommandType(str, Enum):
    PUMP_ON = "pump_on"
    PUMP_OFF = "pump_off"
    LIGHTS_ON = "lights_on"
    LIGHTS_OFF = "lights_off"
    LIGHTS_BRIGHTNESS = "lights_brightness"
    SET_AUTOPILOT_MODE = "set_autopilot_mode"
    UPDATE_CROP_CONFIG = "update_crop_config"
    EMERGENCY_STOP = "emergency_stop"
    REBOOT = "reboot"


class CommandStatus(str, Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"


class EventType(str, Enum):
    IRRIGATION_START = "irrigation_start"
    IRRIGATION_END = "irrigation_end"
    ALERT_TRIGGERED = "alert_triggered"
    ALERT_RESOLVED = "alert_resolved"
    COMMAND_EXECUTED = "command_executed"
    FAILSAFE_TRIGGERED = "failsafe_triggered"
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    CONFIG_CHANGED = "config_changed"
    SYNC_COMPLETED = "sync_completed"


# =============================================================================
# DATA MODELS
# =============================================================================

class DeviceIdentity(BaseModel):
    device_id: str = Field(alias="deviceId")
    firmware_version: str = Field(alias="firmwareVersion")
    hardware_revision: str = Field(alias="hardwareRevision")
    mac_address: str = Field(alias="macAddress")
    registered_at: int = Field(alias="registeredAt")

    class Config:
        populate_by_name = True


class SensorReading(BaseModel):
    timestamp: int
    temperature: float  # Fahrenheit
    humidity: float  # Percent (0-100)
    soil_moisture: float = Field(alias="soilMoisture")
    water_level: float = Field(alias="waterLevel")
    light_on: bool = Field(alias="lightOn")
    pump_on: bool = Field(alias="pumpOn")

    class Config:
        populate_by_name = True


class HourlySummary(BaseModel):
    hour: int  # Unix timestamp (ms) - start of hour
    temp_min: float = Field(alias="tempMin")
    temp_max: float = Field(alias="tempMax")
    temp_avg: float = Field(alias="tempAvg")
    humidity_min: float = Field(alias="humidityMin")
    humidity_max: float = Field(alias="humidityMax")
    humidity_avg: float = Field(alias="humidityAvg")
    soil_moisture_avg: float = Field(alias="soilMoistureAvg")
    water_level_avg: float = Field(alias="waterLevelAvg")
    light_on_minutes: int = Field(alias="lightOnMinutes")
    pump_on_minutes: int = Field(alias="pumpOnMinutes")
    reading_count: int = Field(alias="readingCount")

    class Config:
        populate_by_name = True


class CropConfig(BaseModel):
    crop_type: CropType = Field(alias="cropType")
    planted_at: int = Field(alias="plantedAt")
    expected_harvest_days: int = Field(alias="expectedHarvestDays")
    light_on_hour: int = Field(alias="lightOnHour")
    light_off_hour: int = Field(alias="lightOffHour")
    irrigation_interval_hours: int = Field(alias="irrigationIntervalHours")
    irrigation_duration_seconds: int = Field(alias="irrigationDurationSeconds")
    temp_target_min: float = Field(alias="tempTargetMin")
    temp_target_max: float = Field(alias="tempTargetMax")
    humidity_target_min: float = Field(alias="humidityTargetMin")
    humidity_target_max: float = Field(alias="humidityTargetMax")

    class Config:
        populate_by_name = True


class Alert(BaseModel):
    id: str
    type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    explanation: Optional[str] = None
    suggested_action: Optional[str] = Field(default=None, alias="suggestedAction")
    triggered_at: int = Field(alias="triggeredAt")
    acknowledged_at: Optional[int] = Field(default=None, alias="acknowledgedAt")
    resolved_at: Optional[int] = Field(default=None, alias="resolvedAt")
    reading_snapshot: Optional[SensorReading] = Field(default=None, alias="readingSnapshot")

    class Config:
        populate_by_name = True


class Command(BaseModel):
    id: str
    type: CommandType
    payload: dict = Field(default_factory=dict)
    issued_at: int = Field(alias="issuedAt")
    status: CommandStatus
    executed_at: Optional[int] = Field(default=None, alias="executedAt")
    error_message: Optional[str] = Field(default=None, alias="errorMessage")

    class Config:
        populate_by_name = True


class DeviceEvent(BaseModel):
    id: str
    type: EventType
    timestamp: int
    data: Optional[dict] = None

    class Config:
        populate_by_name = True


class DeviceState(BaseModel):
    """Full device state document for Firestore"""
    device_id: str = Field(alias="deviceId")
    owner_id: str = Field(alias="ownerId")
    status: DeviceStatus
    autopilot_mode: AutopilotMode = Field(alias="autopilotMode")
    last_heartbeat: int = Field(alias="lastHeartbeat")
    last_sync_at: Optional[int] = Field(default=None, alias="lastSyncAt")
    current_reading: Optional[SensorReading] = Field(default=None, alias="currentReading")
    crop_config: Optional[CropConfig] = Field(default=None, alias="cropConfig")
    failsafe_triggered: bool = Field(default=False, alias="failsafeTriggered")
    failsafe_reason: Optional[str] = Field(default=None, alias="failsafeReason")
    firmware_version: str = Field(alias="firmwareVersion")
    lights_on: bool = Field(default=False, alias="lightsOn")
    last_irrigation_at: Optional[int] = Field(default=None, alias="lastIrrigationAt")
    next_irrigation_at: Optional[int] = Field(default=None, alias="nextIrrigationAt")

    class Config:
        populate_by_name = True


# =============================================================================
# CROP PRESETS
# =============================================================================

CROP_PRESETS: dict[CropType, dict] = {
    CropType.BROCCOLI_MICROGREENS: {
        "expectedHarvestDays": 10,
        "lightOnHour": 6,
        "lightOffHour": 20,
        "irrigationIntervalHours": 4,
        "irrigationDurationSeconds": 120,
        "tempTargetMin": 65,
        "tempTargetMax": 75,
        "humidityTargetMin": 50,
        "humidityTargetMax": 70,
    },
    CropType.BASIL: {
        "expectedHarvestDays": 14,
        "lightOnHour": 6,
        "lightOffHour": 20,
        "irrigationIntervalHours": 6,
        "irrigationDurationSeconds": 90,
        "tempTargetMin": 70,
        "tempTargetMax": 85,
        "humidityTargetMin": 40,
        "humidityTargetMax": 60,
    },
    CropType.SUNFLOWER: {
        "expectedHarvestDays": 12,
        "lightOnHour": 6,
        "lightOffHour": 20,
        "irrigationIntervalHours": 4,
        "irrigationDurationSeconds": 120,
        "tempTargetMin": 65,
        "tempTargetMax": 80,
        "humidityTargetMin": 50,
        "humidityTargetMax": 70,
    },
    CropType.RADISH: {
        "expectedHarvestDays": 8,
        "lightOnHour": 6,
        "lightOffHour": 20,
        "irrigationIntervalHours": 4,
        "irrigationDurationSeconds": 90,
        "tempTargetMin": 60,
        "tempTargetMax": 70,
        "humidityTargetMin": 50,
        "humidityTargetMax": 70,
    },
    CropType.ARUGULA: {
        "expectedHarvestDays": 10,
        "lightOnHour": 6,
        "lightOffHour": 20,
        "irrigationIntervalHours": 4,
        "irrigationDurationSeconds": 90,
        "tempTargetMin": 60,
        "tempTargetMax": 70,
        "humidityTargetMin": 50,
        "humidityTargetMax": 70,
    },
    CropType.CHIA: {
        "expectedHarvestDays": 14,
        "lightOnHour": 6,
        "lightOffHour": 20,
        "irrigationIntervalHours": 3,
        "irrigationDurationSeconds": 60,
        "tempTargetMin": 65,
        "tempTargetMax": 75,
        "humidityTargetMin": 60,
        "humidityTargetMax": 80,
    },
    CropType.CUSTOM: {
        "expectedHarvestDays": 10,
        "lightOnHour": 6,
        "lightOffHour": 20,
        "irrigationIntervalHours": 4,
        "irrigationDurationSeconds": 90,
        "tempTargetMin": 65,
        "tempTargetMax": 75,
        "humidityTargetMin": 50,
        "humidityTargetMax": 70,
    },
}


# =============================================================================
# ALERT TEMPLATES
# =============================================================================

ALERT_TEMPLATES: dict[AlertType, dict] = {
    AlertType.WATER_LOW: {
        "severity": AlertSeverity.WARNING,
        "title": "Water Level Low",
        "message": "Reservoir is below 20%. Refill soon.",
        "explanation": "The water level sensor detected low water. Irrigation will pause automatically if it drops further to protect the pump.",
        "suggestedAction": "Refill the reservoir within the next few hours.",
    },
    AlertType.WATER_EMPTY: {
        "severity": AlertSeverity.CRITICAL,
        "title": "Reservoir Empty",
        "message": "Water level critical. Irrigation paused.",
        "explanation": "The reservoir is nearly empty. The system has paused irrigation to prevent pump damage.",
        "suggestedAction": "Refill the reservoir immediately to resume normal operation.",
    },
    AlertType.TEMP_HIGH: {
        "severity": AlertSeverity.WARNING,
        "title": "Temperature High",
        "message": "Temperature exceeded {value}°F for {duration} minutes.",
        "explanation": "Sustained high temperatures can stress plants and reduce crop quality.",
        "suggestedAction": "Improve ventilation or move trays to a cooler location.",
    },
    AlertType.TEMP_LOW: {
        "severity": AlertSeverity.WARNING,
        "title": "Temperature Low",
        "message": "Temperature dropped below {value}°F.",
        "explanation": "Low temperatures slow growth and can damage sensitive crops.",
        "suggestedAction": "Add heating or insulation to the growing area.",
    },
    AlertType.HUMIDITY_HIGH: {
        "severity": AlertSeverity.INFO,
        "title": "Humidity High",
        "message": "Humidity above {value}% for extended period.",
        "explanation": "High humidity can promote mold growth on microgreens.",
        "suggestedAction": "Increase air circulation with a fan.",
    },
    AlertType.HUMIDITY_LOW: {
        "severity": AlertSeverity.INFO,
        "title": "Humidity Low",
        "message": "Humidity below {value}%.",
        "explanation": "Low humidity can cause faster soil drying.",
        "suggestedAction": "Consider more frequent irrigation or adding a humidifier.",
    },
    AlertType.SENSOR_FAILURE: {
        "severity": AlertSeverity.CRITICAL,
        "title": "Sensor Failure",
        "message": "Unable to read from {sensor} sensor.",
        "explanation": "A sensor connection may be loose or the sensor may be damaged.",
        "suggestedAction": "Check sensor connections and restart the device.",
    },
    AlertType.PUMP_FAILURE: {
        "severity": AlertSeverity.CRITICAL,
        "title": "Pump Failure",
        "message": "Pump did not respond to irrigation command.",
        "explanation": "The pump may be clogged, disconnected, or failed.",
        "suggestedAction": "Check pump connections and clear any blockages.",
    },
    AlertType.OFFLINE: {
        "severity": AlertSeverity.WARNING,
        "title": "Device Offline",
        "message": "No heartbeat received for {duration} minutes.",
        "explanation": "The device may have lost power or network connection.",
        "suggestedAction": "Check device power and WiFi connection.",
    },
}
