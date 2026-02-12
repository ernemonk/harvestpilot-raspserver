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
# ALL pin definitions come from Firestore: devices/{hardware_serial}/gpioState
# NO hardcoded pins — the webapp is the single source of truth.
#
# Active-LOW per pin: stored in Firestore gpioState.{pin}.active_low (boolean).
# The Pi reads this field on boot to know relay polarity.

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = "logs/raspserver.log"

# Debug
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
