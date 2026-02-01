"""Sensor service - high-level sensor management"""

import logging
import asyncio
from datetime import datetime
from ..controllers.sensors import SensorController
from ..models import SensorReading, ThresholdAlert
from .. import config

logger = logging.getLogger(__name__)


class SensorService:
    """Manages sensor reading and threshold checking"""
    
    def __init__(self):
        self.controller = SensorController()
        logger.info("Sensor service initialized")
    
    async def read_all(self) -> SensorReading:
        """Read all sensors and return structured data"""
        try:
            raw_data = await self.controller.read_all()
            
            return SensorReading(
                timestamp=raw_data.get("timestamp"),
                temperature=raw_data.get("temperature"),
                humidity=raw_data.get("humidity"),
                soil_moisture=raw_data.get("soil_moisture"),
                water_level=raw_data.get("water_level"),
                simulation=raw_data.get("simulation", False)
            )
            
        except Exception as e:
            logger.error(f"Failed to read sensors: {e}")
            raise
    
    async def check_thresholds(self, reading: SensorReading) -> list[ThresholdAlert]:
        """Check if reading exceeds defined thresholds"""
        alerts = []
        
        # Temperature thresholds
        if reading.temperature < config.TEMP_MIN:
            alerts.append(ThresholdAlert(
                severity="warning",
                sensor_type="temperature",
                current_value=reading.temperature,
                threshold=config.TEMP_MIN,
                timestamp=datetime.now().isoformat()
            ))
        elif reading.temperature > config.TEMP_MAX:
            alerts.append(ThresholdAlert(
                severity="warning",
                sensor_type="temperature",
                current_value=reading.temperature,
                threshold=config.TEMP_MAX,
                timestamp=datetime.now().isoformat()
            ))
        
        # Humidity thresholds
        if reading.humidity < config.HUMIDITY_MIN:
            alerts.append(ThresholdAlert(
                severity="warning",
                sensor_type="humidity",
                current_value=reading.humidity,
                threshold=config.HUMIDITY_MIN,
                timestamp=datetime.now().isoformat()
            ))
        elif reading.humidity > config.HUMIDITY_MAX:
            alerts.append(ThresholdAlert(
                severity="warning",
                sensor_type="humidity",
                current_value=reading.humidity,
                threshold=config.HUMIDITY_MAX,
                timestamp=datetime.now().isoformat()
            ))
        
        # Soil moisture thresholds
        if reading.soil_moisture < config.SOIL_MOISTURE_MIN:
            alerts.append(ThresholdAlert(
                severity="warning",
                sensor_type="soil_moisture",
                current_value=reading.soil_moisture,
                threshold=config.SOIL_MOISTURE_MIN,
                timestamp=datetime.now().isoformat()
            ))
        elif reading.soil_moisture > config.SOIL_MOISTURE_MAX:
            alerts.append(ThresholdAlert(
                severity="warning",
                sensor_type="soil_moisture",
                current_value=reading.soil_moisture,
                threshold=config.SOIL_MOISTURE_MAX,
                timestamp=datetime.now().isoformat()
            ))
        
        # Water level critical
        if not reading.water_level:
            alerts.append(ThresholdAlert(
                severity="critical",
                sensor_type="water_level",
                current_value=0,
                threshold=1,
                timestamp=datetime.now().isoformat()
            ))
        
        return alerts
