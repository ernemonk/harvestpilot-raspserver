"""Sensor service - high-level sensor management"""

import logging
from ..controllers.sensors import SensorController
from ..models import SensorReading

logger = logging.getLogger(__name__)


class SensorService:
    """Manages sensor reading.
    
    Thresholds are configured in Firestore, not in config.py.
    """
    
    def __init__(self, firestore_db=None, hardware_serial=None):
        self.controller = SensorController(firestore_db=firestore_db, hardware_serial=hardware_serial)
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
