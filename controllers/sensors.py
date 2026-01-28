"""Compatibility shim: use `src.controllers.sensors` instead.

This module is kept for backward compatibility and will re-export the
implementation from `src.controllers.sensors`.
"""

import warnings
from src.controllers.sensors import SensorController  # type: ignore

warnings.warn("controllers.sensors moved to src.controllers.sensors; please update imports.", DeprecationWarning)

__all__ = ["SensorController"]


class SensorController:
    """Read sensors"""
    
    def __init__(self):
        self.dht_sensor = None
        self.sensor_error = None
        
        if not config.SIMULATE_HARDWARE:
            try:
                self.dht_sensor = adafruit_dht.DHT22(getattr(board, f'D{config.SENSOR_DHT22_PIN}'))
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(config.SENSOR_WATER_LEVEL_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                logger.info("Real sensors initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize real sensors, falling back to simulation: {e}")
                self.sensor_error = e
                config.SIMULATE_HARDWARE = True
        else:
            logger.info("Using hardware simulation")
        
        logger.info("Sensor controller initialized")
    
    async def read_all(self):
        """Read all sensors"""
        if config.SIMULATE_HARDWARE or self.dht_sensor is None:
            import random
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "temperature": round(72.0 + random.uniform(-2, 2), 1),
                "humidity": round(65.0 + random.uniform(-5, 5), 1),
                "soil_moisture": round(70.0 + random.uniform(-5, 5), 1),
                "water_level": True,
                "simulation": True
            }
        
        try:
            # Read DHT22
            temp_c = self.dht_sensor.temperature
            humidity = self.dht_sensor.humidity
            temp_f = (temp_c * 9/5) + 32
            
            # Read water level
            water_level = not bool(GPIO.input(config.SENSOR_WATER_LEVEL_PIN))
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "temperature": round(temp_f, 1),
                "humidity": round(humidity, 1),
                "soil_moisture": 70.0,  # TODO: Implement with ADC
                "water_level": water_level
            }
        except Exception as e:
            logger.error(f"Error reading sensors: {e}")
            raise
    
    async def check_thresholds(self, reading):
        """Check sensor thresholds"""
        alerts = []
        
        if reading['temperature'] < config.TEMP_MIN:
            alerts.append({
                "type": "temperature_low",
                "value": reading['temperature'],
                "threshold": config.TEMP_MIN,
                "severity": "warning"
            })
        elif reading['temperature'] > config.TEMP_MAX:
            alerts.append({
                "type": "temperature_high",
                "value": reading['temperature'],
                "threshold": config.TEMP_MAX,
                "severity": "warning"
            })
        
        if not reading['water_level']:
            alerts.append({
                "type": "water_level_low",
                "severity": "critical"
            })
        
        return alerts
