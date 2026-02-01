"""Configuration for HarvestPilot RaspServer"""

import os
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
_repo_root = Path(__file__).parent.parent.resolve()
_env_file = _repo_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file)

# Base directory
BASE_DIR = Path(__file__).parent.resolve()

# Hardware Platform
HARDWARE_PLATFORM = os.getenv("HARDWARE_PLATFORM", "raspberry_pi")
SIMULATE_HARDWARE = os.getenv("SIMULATE_HARDWARE", "false").lower() == "true"

# Hardware Serial Detection (Primary Device Identifier)
def _get_hardware_serial() -> str:
    """Get Raspberry Pi hardware serial with smart fallback strategy.
    
    Priority:
    1. Environment variable HARDWARE_SERIAL (if explicitly set)
    2. /proc/cpuinfo (Raspberry Pi hardware serial - immutable, tamper-proof)
    3. .env DEVICE_ID (fallback for non-Pi systems like macOS/Linux dev)
    4. Generated from DEVICE_ID with prefix (final fallback)
    
    Returns:
        Hardware serial identifier for device authentication
    """
    # Priority 1: Check if explicitly set in environment
    env_serial = os.getenv("HARDWARE_SERIAL")
    if env_serial and env_serial.strip():
        return env_serial.strip()
    
    # Priority 2: Try to read from /proc/cpuinfo (Raspberry Pi)
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if line.startswith('Serial'):
                    serial = line.split(':')[1].strip()
                    if serial:
                        return serial
    except Exception:
        pass
    
    # Priority 3: Fall back to DEVICE_ID from .env (for dev environments)
    device_id = os.getenv("DEVICE_ID", "").strip()
    if device_id:
        # Use DEVICE_ID as-is if it already looks like a hardware identifier
        if "-" in device_id or len(device_id) > 8:
            return device_id
        # Otherwise prefix it to make it unique
        return f"dev-{device_id}"
    
    # Priority 4: Final fallback with hostname
    try:
        import socket
        hostname = socket.gethostname().lower().replace('.', '-')
        return f"dev-{hostname}"
    except Exception:
        pass
    
    # Last resort
    return "unknown-device"

HARDWARE_SERIAL = _get_hardware_serial()  # Primary identifier (immutable, tamper-proof)
DEVICE_ID = os.getenv("DEVICE_ID", "raspserver-001")  # Human-readable alias

# Default to relative path (./firebase-key.json) but allow environment override
_repo_root = Path(__file__).parent.parent.resolve()
_default_creds = str(_repo_root / "firebase-key.json")
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", _default_creds)

FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "harvest-hub")

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
