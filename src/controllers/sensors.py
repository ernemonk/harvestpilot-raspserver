"""Sensor controller for Raspberry Pi"""

import logging
import random
import asyncio
from datetime import datetime
try:
    import adafruit_dht
    import board
    DHT_AVAILABLE = True
except ImportError:
    DHT_AVAILABLE = False
    adafruit_dht = None
    board = None

logger = logging.getLogger(__name__)
if not DHT_AVAILABLE:
    logger.warning("adafruit_dht not available - sensor readings will be simulated")

from ..utils.gpio_import import GPIO
from .. import config


class SensorController:
    """Read sensors defined in device document's gpioState"""
    
    def __init__(self, firestore_db=None, hardware_serial=None):
        self.firestore_db = firestore_db
        self.hardware_serial = hardware_serial or config.HARDWARE_SERIAL
        self.configured_sensors = {}  # Cache of sensors from device doc
        self.dht_sensor = None
        
        if not config.SIMULATE_HARDWARE and DHT_AVAILABLE:
            self.dht_sensor = adafruit_dht.DHT22(getattr(board, f'D{config.SENSOR_DHT22_PIN}'))
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(config.SENSOR_WATER_LEVEL_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        else:
            self.dht_sensor = None
    
    def _get_configured_sensors(self):
        """Fetch input sensors from device document's gpioState"""
        try:
            if not self.firestore_db:
                logger.warning("No Firestore DB - using default sensors")
                return self._get_default_sensors()
            
            device_doc = self.firestore_db.collection('devices').document(self.hardware_serial).get()
            if not device_doc.exists:
                logger.warning(f"Device {self.hardware_serial} not in Firestore - using defaults")
                return self._get_default_sensors()
            
            device_data = device_doc.to_dict()
            gpio_state = device_data.get('gpioState', {})
            
            # Extract input sensors from gpioState
            sensors = {}
            for pin_str, pin_config in gpio_state.items():
                if pin_config.get('mode') == 'input':
                    function = pin_config.get('function', '')
                    sensors[function] = {
                        'pin': int(pin_str) if pin_str.isdigit() else pin_str,
                        'function': function
                    }
            
            if sensors:
                logger.info(f"Loaded configured sensors from device doc: {list(sensors.keys())}")
                return sensors
            else:
                logger.info("No input sensors in gpioState - using defaults")
                return self._get_default_sensors()
                
        except Exception as e:
            logger.error(f"Failed to get configured sensors: {e}")
            return self._get_default_sensors()
    
    def _get_default_sensors(self):
        """Fallback default sensors"""
        return {
            'temperature_humidity': {'pin': config.SENSOR_DHT22_PIN, 'function': 'temperature_humidity'},
            'water_level': {'pin': config.SENSOR_WATER_LEVEL_PIN, 'function': 'water_level'}
        }
        
        logger.info("Sensor controller initialized")
    
    async def read_all(self):
        """Read sensors configured in device document"""
        # Load configured sensors on first read
        if not self.configured_sensors:
            self.configured_sensors = self._get_configured_sensors()
        
        if config.SIMULATE_HARDWARE:
            return self._simulate_sensors()
        
        try:
            reading = {
                "timestamp": datetime.utcnow().isoformat(),
            }
            
            # Only read configured sensors
            for sensor_name, sensor_config in self.configured_sensors.items():
                if sensor_name == 'temperature_humidity' and self.dht_sensor is not None:
                    try:
                        # Run blocking DHT sensor read in thread executor
                        temp_c = await asyncio.to_thread(lambda: self.dht_sensor.temperature)
                        humidity = await asyncio.to_thread(lambda: self.dht_sensor.humidity)
                        temp_f = (temp_c * 9/5) + 32
                        reading['temperature'] = round(temp_f, 1)
                        reading['humidity'] = round(humidity, 1)
                    except Exception as e:
                        logger.error(f"Failed to read DHT22: {e}")
                        
                elif sensor_name == 'water_level':
                    try:
                        water_level = not bool(GPIO.input(sensor_config['pin']))
                        reading['water_level'] = water_level
                    except Exception as e:
                        logger.error(f"Failed to read water level: {e}")
            
            # If no temperature was read but was configured, simulate it
            if 'temperature' not in reading and 'temperature_humidity' in self.configured_sensors:
                logger.info("DHT sensor not available - simulating temperature/humidity")
                reading['temperature'] = round(72.0 + random.uniform(-2, 2), 1)
                reading['humidity'] = round(65.0 + random.uniform(-5, 5), 1)
            
            # Always add soil_moisture if in defaults (ADC not implemented)
            if 'soil_moisture' not in reading:
                reading['soil_moisture'] = 70.0
            
            return reading
            
        except Exception as e:
            logger.error(f"Error reading sensors: {e}")
            raise
    
    def _simulate_sensors(self):
        """Return simulated sensor readings"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "temperature": round(72.0 + random.uniform(-2, 2), 1),
            "humidity": round(65.0 + random.uniform(-5, 5), 1),
            "soil_moisture": round(70.0 + random.uniform(-5, 5), 1),
            "water_level": True,
            "simulation": True
        }
    
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
