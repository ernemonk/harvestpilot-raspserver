#!/usr/bin/env python3
"""
Config Loader - Bridges module_config.py with existing config.py
Loads module-specific settings at startup
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any


class ConfigLoader:
    """Load configuration from module JSON files"""
    
    def __init__(self, config_dir: str = "/home/monkphx/harvestpilot-raspserver/config"):
        self.config_dir = Path(config_dir)
        self.module_config = self._load_module_config()
    
    def _load_module_config(self) -> Optional[Dict[str, Any]]:
        """Load module.json"""
        module_file = self.config_dir / "module.json"
        if not module_file.exists():
            return None
        
        with open(module_file) as f:
            return json.load(f)
    
    def get_gpio_pin(self, device_id: str, pin_type: str = "pwm") -> Optional[int]:
        """
        Get GPIO pin for a device
        
        Args:
            device_id: e.g., "pump-001", "light-001", "motor-1"
            pin_type: e.g., "pwm", "dir", "relay"
        
        Returns:
            GPIO pin number or None
        """
        if not self.module_config:
            return None
        
        for device in self.module_config.get("devices", []):
            if device["device_id"] == device_id:
                return device["gpio_pins"].get(pin_type)
        
        return None
    
    def get_device_config(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get full config for a device"""
        if not self.module_config:
            return None
        
        for device in self.module_config.get("devices", []):
            if device["device_id"] == device_id:
                return device.get("config", {})
        
        return None
    
    def get_all_devices(self) -> list:
        """Get all devices in this module"""
        if not self.module_config:
            return []
        
        return self.module_config.get("devices", [])
    
    def get_devices_by_type(self, device_type: str) -> list:
        """Get all devices of a specific type"""
        if not self.module_config:
            return []
        
        return [
            d for d in self.module_config.get("devices", [])
            if d["device_type"] == device_type
        ]
    
    def get_module_info(self) -> Optional[Dict[str, Any]]:
        """Get module information (id, location, num_trays)"""
        if not self.module_config:
            return None
        
        return {
            "module_id": self.module_config["module_id"],
            "location": self.module_config["location"],
            "num_trays": self.module_config["num_trays"],
            "description": self.module_config.get("description", "")
        }


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def use_in_config_py():
    """
    Example: Update config.py to use ModuleConfigLoader
    
    In config.py:
    """
    
    code_example = """
# config.py
import os
from utils.config_loader import ConfigLoader

# Load module configuration
loader = ConfigLoader()

# Get GPIO pins from module config (with fallbacks)
PUMP_PWM_PIN = loader.get_gpio_pin("pump-001", "pwm") or int(os.getenv("PUMP_PWM_PIN", "17"))
LED_PWM_PIN = loader.get_gpio_pin("light-001", "pwm") or int(os.getenv("LED_PWM_PIN", "18"))

# Get device configs
pump_config = loader.get_device_config("pump-001") or {}
led_config = loader.get_device_config("light-001") or {}

PUMP_PWM_FREQUENCY = pump_config.get("pwm_frequency", 1000)
LED_PWM_FREQUENCY = led_config.get("pwm_frequency", 1000)
LED_DEFAULT_INTENSITY = led_config.get("default_intensity", 80)

# Get lighting schedule from module config
LIGHT_ON_TIME = led_config.get("on_time", "06:00")
LIGHT_OFF_TIME = led_config.get("off_time", "22:00")

# Get module info
module_info = loader.get_module_info()
MODULE_ID = module_info["module_id"]
MODULE_LOCATION = module_info["location"]
NUM_TRAYS = module_info["num_trays"]
    """
    
    return code_example


def use_in_hardware_controller():
    """
    Example: Use ConfigLoader in hardware controllers
    """
    
    code_example = """
# app/core/hardware/lighting.py
from utils.config_loader import ConfigLoader

class LightingController:
    def __init__(self):
        self.config_loader = ConfigLoader()
        
        # Get LED pin from module config
        self.pin = self.config_loader.get_gpio_pin("light-001", "pwm")
        
        # Get device config
        device_config = self.config_loader.get_device_config("light-001")
        self.frequency = device_config.get("pwm_frequency", 1000)
        self.default_intensity = device_config.get("default_intensity", 80)
    
    async def set_lights(self, state: bool, intensity: int = None):
        intensity = intensity or self.default_intensity
        
        if self.pin and settings.GPIO_ENABLED:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.pin, GPIO.OUT)
            
            if state:
                pwm = GPIO.PWM(self.pin, self.frequency)
                pwm.start(intensity)
            else:
                GPIO.output(self.pin, GPIO.LOW)
    """
    
    return code_example


def use_in_hardware_setup():
    """
    Example: Dynamic hardware setup based on module config
    """
    
    code_example = """
# Setup multiple motors based on module config
from utils.config_loader import ConfigLoader

loader = ConfigLoader()
motors = loader.get_devices_by_type("motor")

for motor in motors:
    tray_id = motor["config"]["tray_id"]
    pwm_pin = motor["gpio_pins"]["pwm"]
    dir_pin = motor["gpio_pins"]["dir"]
    
    print(f"Setting up Tray {tray_id}: PWM={pwm_pin}, DIR={dir_pin}")
    GPIO.setup(pwm_pin, GPIO.OUT)
    GPIO.setup(dir_pin, GPIO.OUT)
    
    self.motor_pwms[tray_id] = GPIO.PWM(pwm_pin, 1000)
    """
    
    return code_example


# ============================================================================
# INTEGRATION CHECKLIST
# ============================================================================

INTEGRATION_CHECKLIST = """
✅ MULTI-MODULE INTEGRATION CHECKLIST

1. CONFIG INTEGRATION
   [ ] Update config.py to use ConfigLoader
   [ ] Set fallback values for .env compatibility
   [ ] Test with and without module.json

2. HARDWARE CONTROLLERS
   [ ] Update LightingController to use ConfigLoader
   [ ] Update IrrigationController to use ConfigLoader
   [ ] Update HarvestController to use ConfigLoader
   [ ] Update SensorController to use ConfigLoader

3. INITIALIZATION
   [ ] Load module config at startup
   [ ] Log module information on boot
   [ ] Validate GPIO pins are assigned

4. TESTING
   [ ] Run test_gpio_pins.py (verifies pins from config)
   [ ] Run test_led_brightness.py (uses LED_PWM_PIN from config)
   [ ] Run test_pump_control.py (uses PUMP_PWM_PIN from config)

5. DEPLOYMENT
   [ ] Run setup-pi-module.sh on each Pi
   [ ] Verify module.json created
   [ ] Restart harvestpilot-raspserver
   [ ] Check logs for config load messages

6. MULTI-PI SETUP
   [ ] Setup Pi 1 as module-001
   [ ] Setup Pi 2 as module-002
   [ ] Setup Pi 3 as module-003
   [ ] Verify Firebase sync for each module
"""


if __name__ == "__main__":
    print(INTEGRATION_CHECKLIST)
    
    # Test loading
    print("\n" + "="*60)
    print("Testing ConfigLoader...")
    print("="*60 + "\n")
    
    loader = ConfigLoader()
    
    if loader.module_config:
        print("✅ Module config loaded!")
        print(f"   Module: {loader.get_module_info()['module_id']}")
        print(f"   Pump PWM Pin: {loader.get_gpio_pin('pump-001', 'pwm')}")
        print(f"   Light PWM Pin: {loader.get_gpio_pin('light-001', 'pwm')}")
        
        motors = loader.get_devices_by_type("motor")
        print(f"   Motors: {len(motors)} trays")
    else:
        print("❌ No module config found")
        print("   Run: bash scripts/setup-pi-module.sh")
