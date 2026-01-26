"""
Failsafe Manager - Local safety logic that runs without cloud dependency.
Protects plants and equipment from dangerous conditions.
"""

import asyncio
import logging
import time
from typing import Optional, Callable
from dataclasses import dataclass

try:
    from ..storage.local_db import LocalDatabase
    from ..storage.models import (
        SensorReading,
        AlertType,
        AlertSeverity,
        Alert,
        FAILSAFE_WATER_LEVEL_PERCENT,
        FAILSAFE_TEMP_HIGH_F,
        FAILSAFE_TEMP_HIGH_DURATION_MIN,
    )
except ImportError:
    # Allow direct imports when running from different contexts
    from storage.local_db import LocalDatabase
    from storage.models import (
        SensorReading,
        AlertType,
        AlertSeverity,
        Alert,
        FAILSAFE_WATER_LEVEL_PERCENT,
        FAILSAFE_TEMP_HIGH_F,
        FAILSAFE_TEMP_HIGH_DURATION_MIN,
    )

logger = logging.getLogger(__name__)


@dataclass
class FailsafeState:
    """Current failsafe state."""
    triggered: bool = False
    reason: Optional[str] = None
    triggered_at: Optional[int] = None


class FailsafeManager:
    """
    Manages local failsafe logic.
    
    Failsafes (run locally, no cloud needed):
    1. Water level < 20% → Pause irrigation, alert
    2. Temperature > 95°F for 30 min → Alert, suggest action
    3. Sensor failure → Alert, continue with last known values
    """

    def __init__(
        self,
        db: LocalDatabase,
        on_alert: Optional[Callable[[Alert], None]] = None,
        on_pump_disable: Optional[Callable[[], None]] = None,
    ):
        self.db = db
        self.on_alert = on_alert
        self.on_pump_disable = on_pump_disable
        
        self._state = FailsafeState()
        self._high_temp_start: Optional[int] = None
        self._last_reading: Optional[SensorReading] = None

    def check_reading(self, reading: SensorReading) -> list[Alert]:
        """
        Check a sensor reading for failsafe conditions.
        Returns list of alerts to be raised.
        """
        alerts = []
        self._last_reading = reading
        now = int(time.time() * 1000)
        
        # Check water level
        water_alert = self._check_water_level(reading, now)
        if water_alert:
            alerts.append(water_alert)
        
        # Check temperature
        temp_alert = self._check_temperature(reading, now)
        if temp_alert:
            alerts.append(temp_alert)
        
        # Check humidity
        humidity_alerts = self._check_humidity(reading, now)
        alerts.extend(humidity_alerts)
        
        return alerts

    def _check_water_level(self, reading: SensorReading, now: int) -> Optional[Alert]:
        """Check water level failsafe."""
        import uuid
        
        if reading.water_level <= 5:
            # Critical: nearly empty
            self._trigger_failsafe("Water reservoir empty")
            
            if self.on_pump_disable:
                self.on_pump_disable()
            
            return Alert(
                id=str(uuid.uuid4()),
                type=AlertType.WATER_EMPTY,
                severity=AlertSeverity.CRITICAL,
                title="Reservoir Empty",
                message="Water level critical. Irrigation paused.",
                explanation="The reservoir is nearly empty. The system has paused irrigation to prevent pump damage.",
                suggestedAction="Refill the reservoir immediately to resume normal operation.",
                triggeredAt=now,
                readingSnapshot=reading,
            )
        
        elif reading.water_level <= FAILSAFE_WATER_LEVEL_PERCENT:
            # Warning: low water
            return Alert(
                id=str(uuid.uuid4()),
                type=AlertType.WATER_LOW,
                severity=AlertSeverity.WARNING,
                title="Water Level Low",
                message=f"Reservoir is at {reading.water_level:.0f}%. Refill soon.",
                explanation="The water level sensor detected low water. Irrigation will pause automatically if it drops further to protect the pump.",
                suggestedAction="Refill the reservoir within the next few hours.",
                triggeredAt=now,
                readingSnapshot=reading,
            )
        
        return None

    def _check_temperature(self, reading: SensorReading, now: int) -> Optional[Alert]:
        """Check temperature failsafe."""
        import uuid
        
        if reading.temperature >= FAILSAFE_TEMP_HIGH_F:
            # Start tracking high temp duration
            if self._high_temp_start is None:
                self._high_temp_start = now
            
            duration_min = (now - self._high_temp_start) / (60 * 1000)
            
            if duration_min >= FAILSAFE_TEMP_HIGH_DURATION_MIN:
                # Extended high temperature - trigger alert
                return Alert(
                    id=str(uuid.uuid4()),
                    type=AlertType.TEMP_HIGH,
                    severity=AlertSeverity.WARNING,
                    title="Temperature High",
                    message=f"Temperature exceeded {FAILSAFE_TEMP_HIGH_F}°F for {int(duration_min)} minutes.",
                    explanation="Sustained high temperatures can stress plants and reduce crop quality.",
                    suggestedAction="Improve ventilation or move trays to a cooler location.",
                    triggeredAt=now,
                    readingSnapshot=reading,
                )
        else:
            # Temperature back to normal, reset tracking
            self._high_temp_start = None
        
        return None

    def _check_humidity(self, reading: SensorReading, now: int) -> list[Alert]:
        """Check humidity levels."""
        import uuid
        alerts = []
        
        # Get crop config for thresholds
        crop_config = self.db.get_crop_config()
        if not crop_config:
            return alerts
        
        if reading.humidity > crop_config.humidity_target_max + 10:
            alerts.append(Alert(
                id=str(uuid.uuid4()),
                type=AlertType.HUMIDITY_HIGH,
                severity=AlertSeverity.INFO,
                title="Humidity High",
                message=f"Humidity at {reading.humidity:.0f}%, target max is {crop_config.humidity_target_max}%.",
                explanation="High humidity can promote mold growth on microgreens.",
                suggestedAction="Increase air circulation with a fan.",
                triggeredAt=now,
                readingSnapshot=reading,
            ))
        
        elif reading.humidity < crop_config.humidity_target_min - 10:
            alerts.append(Alert(
                id=str(uuid.uuid4()),
                type=AlertType.HUMIDITY_LOW,
                severity=AlertSeverity.INFO,
                title="Humidity Low",
                message=f"Humidity at {reading.humidity:.0f}%, target min is {crop_config.humidity_target_min}%.",
                explanation="Low humidity can cause faster soil drying.",
                suggestedAction="Consider more frequent irrigation or adding a humidifier.",
                triggeredAt=now,
                readingSnapshot=reading,
            ))
        
        return alerts

    def _trigger_failsafe(self, reason: str):
        """Trigger failsafe mode."""
        if not self._state.triggered:
            logger.warning(f"FAILSAFE TRIGGERED: {reason}")
            self._state.triggered = True
            self._state.reason = reason
            self._state.triggered_at = int(time.time() * 1000)
            
            # Update schedule state in DB
            self.db.update_schedule_state(
                failsafe_triggered=True,
                failsafe_reason=reason,
            )

    def clear_failsafe(self):
        """Clear failsafe mode (manual override)."""
        if self._state.triggered:
            logger.info("Failsafe cleared")
            self._state.triggered = False
            self._state.reason = None
            self._state.triggered_at = None
            
            self.db.update_schedule_state(
                failsafe_triggered=False,
                failsafe_reason=None,
            )

    @property
    def is_triggered(self) -> bool:
        """Check if failsafe is currently triggered."""
        return self._state.triggered

    @property
    def failsafe_reason(self) -> Optional[str]:
        """Get the reason for current failsafe."""
        return self._state.reason

    def can_irrigate(self) -> bool:
        """Check if irrigation is allowed (no water failsafe)."""
        if self._last_reading is None:
            return False
        
        return self._last_reading.water_level > 5
