"""DEPRECATED: Configuration moved to src/config.py

This shim maintains backward compatibility. Import from src instead.
"""
import warnings
warnings.warn("config module moved to src.config; import from there instead", DeprecationWarning, stacklevel=2)

# Re-export everything from src.config
from src.config import *  # noqa: F401, F403


# GPIO Pin Configuration
SENSOR_DHT22_PIN = 4
SENSOR_SOIL_MOISTURE_PIN = 17  # Via external ADC
SENSOR_WATER_LEVEL_PIN = 27
SENSOR_FLOW_METER_PIN = 22

PUMP_PWM_PIN = 17  # GPIO 17 (Physical Pin 11) - Pump MOSFET
PUMP_RELAY_PIN = 19

LED_PWM_PIN = 18  # GPIO 18 (Physical Pin 12) - LED strip MOSFET (PWM brightness)
LED_RELAY_PIN = 13

# Harvest belt motors (6 trays)
MOTOR_PINS = [
    {"tray": 1, "pwm": 2, "dir": 3, "home": 17, "end": 27},
    {"tray": 2, "pwm": 9, "dir": 11, "home": 5, "end": 6},
    {"tray": 3, "pwm": 10, "dir": 22, "home": 23, "end": 24},
    {"tray": 4, "pwm": 14, "dir": 15, "home": 18, "end": 25},
    {"tray": 5, "pwm": 8, "dir": 7, "home": 1, "end": 12},
    {"tray": 6, "pwm": 16, "dir": 20, "home": 21, "end": 26},
]

# PWM Configuration
PUMP_PWM_FREQUENCY = 1000  # Hz
LED_PWM_FREQUENCY = 1000  # Hz
MOTOR_PWM_FREQUENCY = 1000  # Hz

# Environmental Thresholds
TEMP_MIN = 65.0  # °F
TEMP_MAX = 80.0
HUMIDITY_MIN = 50.0  # %
HUMIDITY_MAX = 70.0
SOIL_MOISTURE_MIN = 60.0  # %
SOIL_MOISTURE_MAX = 80.0

# Sensor Reading
SENSOR_READING_INTERVAL = 5  # seconds

# Irrigation Configuration
IRRIGATION_CYCLE_DURATION = 30  # seconds
PUMP_DEFAULT_SPEED = 80  # %
IRRIGATION_SCHEDULE = ["06:00", "12:00", "18:00"]

# Lighting Configuration
LIGHT_ON_TIME = "06:00"
LIGHT_OFF_TIME = "22:00"
LED_DEFAULT_INTENSITY = 80  # %

# Harvest Configuration
HARVEST_BELT_SPEED = 50  # %
HARVEST_BELT_TIMEOUT = 60  # seconds

# Automation
AUTO_IRRIGATION_ENABLED = True
AUTO_LIGHTING_ENABLED = True
EMERGENCY_STOP_ON_WATER_LOW = True

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "logs/raspserver.log"

# Debug
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
