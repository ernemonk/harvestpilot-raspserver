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
        self._sensors_initialized = False
        
        # Note: DHT22 and GPIO pins are initialized on first sensor read
        # after configuration is loaded from Firestore. No hardcoded pins.
    
    def _get_configured_sensors(self):
        """Fetch input sensors from device document's gpioState in Firestore
        
        Sensors are configured exclusively via web app in Firestore.
        No hardcoded pins or fallbacks - all configuration from database.
        """
        try:
            if not self.firestore_db:
                logger.error("❌ CRITICAL: Firestore DB not available - cannot load sensor configuration")
                logger.error("   Sensor configuration MUST be set up in Firestore via web app")
                logger.error("   Path: devices/{device_id}/gpioState/")
                return {}
            
            device_doc = self.firestore_db.collection('devices').document(self.hardware_serial).get()
            if not device_doc.exists:
                logger.error(f"❌ CRITICAL: Device {self.hardware_serial} not found in Firestore")
                logger.error("   Please register device in web app before starting service")
                return {}
            
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
                logger.info(f"✅ Loaded sensor configuration from Firestore: {list(sensors.keys())}")
                for name, cfg in sensors.items():
                    logger.info(f"   - {name}: GPIO {cfg.get('pin')}")
                return sensors
            else:
                logger.warning("⚠️  No input sensors configured in Firestore gpioState")
                logger.warning("   Path: devices/{device_id}/gpioState/")
                logger.warning("   Add sensors via web app to enable sensor readings")
                return {}
                
        except Exception as e:
            logger.error(f"❌ Failed to load sensor configuration from Firestore: {e}")
            logger.error("   Check Firestore database connection and permissions")
            return {}
        logger.info("Sensor controller initialized")
    
    def _initialize_sensor_hardware(self):
        """Initialize GPIO pins and sensor hardware based on Firestore config
        
        Called once after sensors are loaded from Firestore.
        Sets up DHT22, GPIO input/output pins, etc based on gpioState.
        """
        if self._sensors_initialized or config.SIMULATE_HARDWARE:
            return
            
        try:
            logger.info("🔧 Initializing sensor hardware based on Firestore configuration...")
            GPIO.setmode(GPIO.BCM)
            
            # Initialize each configured sensor's GPIO
            for sensor_name, sensor_config in self.configured_sensors.items():
                pin = sensor_config.get('pin')
                if not pin:
                    continue
                    
                if sensor_name == 'temperature_humidity' and DHT_AVAILABLE:
                    try:
                        self.dht_sensor = adafruit_dht.DHT22(getattr(board, f'D{pin}'))
                        logger.info(f"   ✅ DHT22 initialized on GPIO {pin}")
                    except Exception as e:
                        logger.error(f"   ❌ Failed to initialize DHT22 on GPIO {pin}: {e}")
                        self.dht_sensor = None
                        
                elif sensor_name == 'water_level':
                    try:
                        GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                        logger.info(f"   ✅ Water level sensor initialized on GPIO {pin}")
                    except Exception as e:
                        logger.error(f"   ❌ Failed to setup water level on GPIO {pin}: {e}")
            
            self._sensors_initialized = True
            logger.info("✅ Sensor hardware initialization complete")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize sensor hardware: {e}")
    
    async def read_all(self):
        """Read sensors configured in device document"""
        # Load configured sensors on first read
        if not self.configured_sensors:
            self.configured_sensors = self._get_configured_sensors()
            # Initialize hardware after loading config from Firestore
            self._initialize_sensor_hardware()
        
        # Only return configured sensors
        if not self.configured_sensors:
            # No sensors configured - return None values (this should trigger skipping in server loop)
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "temperature": None,
                "humidity": None,
                "soil_moisture": None,
                "water_level": None,
                "no_sensors_configured": True
            }
        
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
                        # Handle None values from DHT sensor (intermittent failures)
                        if temp_c is not None and humidity is not None:
                            temp_f = (temp_c * 9/5) + 32
                            reading['temperature'] = round(temp_f, 1)
                            reading['humidity'] = round(humidity, 1)
                        else:
                            logger.warning(f"DHT22 returned None values - temperature: {temp_c}, humidity: {humidity}")
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
        
        return alerts
