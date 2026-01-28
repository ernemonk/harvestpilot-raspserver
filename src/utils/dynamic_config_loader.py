#!/usr/bin/env python3
"""
Dynamic Config Loader - Loads pins from pin_config.py
Supports dynamic pin assignment per Raspberry Pi
"""

import json
from pathlib import Path
from typing import Optional, Dict, List, Any


class DynamicConfigLoader:
    """Load GPIO configuration dynamically from pin_config.json"""
    
    def __init__(self, config_dir: str = "/home/monkphx/harvestpilot-raspserver/config"):
        self.config_dir = Path(config_dir)
        self.pin_config_file = self.config_dir / "gpio_pins.json"
        self.pin_config = self._load_pin_config()
    
    def _load_pin_config(self) -> Optional[Dict[str, Any]]:
        """Load gpio_pins.json"""
        if not self.pin_config_file.exists():
            return None
        
        try:
            with open(self.pin_config_file) as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading pin config: {e}")
            return None
    
    def get_pin_for_device_type(self, device_type: str) -> Optional[int]:
        """Get GPIO pin number for a device type"""
        if not self.pin_config:
            return None
        
        for pin in self.pin_config.get("pins", []):
            if pin["device_type"] == device_type and pin["enabled"]:
                return pin["gpio_number"]
        
        return None
    
    def get_pin_for_device_id(self, device_id: str) -> Optional[int]:
        """Get GPIO pin number for a specific device ID"""
        if not self.pin_config:
            return None
        
        for pin in self.pin_config.get("pins", []):
            if pin["device_id"] == device_id and pin["enabled"]:
                return pin["gpio_number"]
        
        return None
    
    def get_pwm_frequency(self, device_type: str) -> Optional[int]:
        """Get PWM frequency for a device"""
        if not self.pin_config:
            return None
        
        for pin in self.pin_config.get("pins", []):
            if pin["device_type"] == device_type and pin["enabled"]:
                return pin.get("pwm_frequency")
        
        return None
    
    def get_all_output_pins(self) -> List[Dict[str, Any]]:
        """Get all output/PWM pins"""
        if not self.pin_config:
            return []
        
        return [
            p for p in self.pin_config.get("pins", [])
            if p["mode"] in ["OUTPUT", "PWM"] and p["enabled"]
        ]
    
    def get_all_input_pins(self) -> List[Dict[str, Any]]:
        """Get all input/sensor pins"""
        if not self.pin_config:
            return []
        
        return [
            p for p in self.pin_config.get("pins", [])
            if p["mode"] in ["INPUT", "SENSOR"] and p["enabled"]
        ]
    
    def get_motors(self) -> List[Dict[str, Any]]:
        """Get all motor pins"""
        if not self.pin_config:
            return []
        
        return [
            p for p in self.pin_config.get("pins", [])
            if p["device_type"] == "motor" and p["enabled"]
        ]
    
    def get_device_config(self, device_type: str) -> Optional[Dict[str, Any]]:
        """Get config dict for a device type"""
        if not self.pin_config:
            return None
        
        for pin in self.pin_config.get("pins", []):
            if pin["device_type"] == device_type and pin["enabled"]:
                return pin.get("config", {})
        
        return None
    
    def is_pin_enabled(self, gpio_number: int) -> bool:
        """Check if a pin is enabled"""
        if not self.pin_config:
            return False
        
        for pin in self.pin_config.get("pins", []):
            if pin["gpio_number"] == gpio_number:
                return pin["enabled"]
        
        return False
    
    def get_pi_model(self) -> Optional[str]:
        """Get Raspberry Pi model"""
        if not self.pin_config:
            return None
        
        return self.pin_config.get("pi_model")
    
    def get_module_id(self) -> Optional[str]:
        """Get module ID"""
        if not self.pin_config:
            return None
        
        return self.pin_config.get("module_id")
    
    def print_summary(self):
        """Print configuration summary"""
        if not self.pin_config:
            print("❌ No configuration found")
            return
        
        print("\n" + "="*60)
        print("📋 Dynamic GPIO Configuration")
        print("="*60)
        
        print(f"\nPi Model:  {self.pin_config.get('pi_model', 'Unknown')}")
        print(f"Module:    {self.pin_config.get('module_id', 'Unknown')}")
        
        print("\n🔌 Devices:")
        
        # Group by type
        grouped = {}
        for pin in self.pin_config.get("pins", []):
            dtype = pin["device_type"]
            if dtype not in grouped:
                grouped[dtype] = []
            grouped[dtype].append(pin)
        
        for dtype, pins in sorted(grouped.items()):
            print(f"\n  {dtype.upper()}:")
            for pin in pins:
                status = "✅" if pin["enabled"] else "❌"
                pwm = f", {pin.get('pwm_frequency')}Hz" if pin.get("pwm_frequency") else ""
                print(f"    {status} GPIO {pin['gpio_number']:2d} - {pin['name']}{pwm}")
        
        print("\n" + "="*60 + "\n")


# ============================================================================
# USAGE IN config.py
# ============================================================================

def generate_config_py_code() -> str:
    """Generate code snippet for config.py"""
    
    code = '''
# config.py - Add this at the top

import os
from utils.pin_config import DynamicConfigLoader

# Load dynamic pin configuration
loader = DynamicConfigLoader()

# Get GPIO pins from dynamic config (with fallbacks to .env)
PUMP_PWM_PIN = loader.get_pin_for_device_type("pump") or int(os.getenv("PUMP_PWM_PIN", "17"))
LED_PWM_PIN = loader.get_pin_for_device_type("light") or int(os.getenv("LED_PWM_PIN", "18"))
SENSOR_DHT22_PIN = loader.get_pin_for_device_type("sensor_dht") or int(os.getenv("SENSOR_DHT22_PIN", "4"))
SENSOR_WATER_LEVEL_PIN = loader.get_pin_for_device_type("sensor_water") or int(os.getenv("SENSOR_WATER_LEVEL_PIN", "27"))

# Get PWM frequencies from config
PUMP_PWM_FREQUENCY = loader.get_pwm_frequency("pump") or 1000
LED_PWM_FREQUENCY = loader.get_pwm_frequency("light") or 1000

# Get all motor pins dynamically
motors = loader.get_motors()
MOTOR_PINS = [
    {
        "tray": pin["config"].get("tray_id", i+1),
        "pwm": pin["gpio_number"],
        "dir": motors[i+1]["gpio_number"] if i+1 < len(motors) else None
    }
    for i, pin in enumerate([p for p in motors if "pwm" in p["device_id"]])
]

# Module info
MODULE_ID = loader.get_module_id()
PI_MODEL = loader.get_pi_model()
'''
    
    return code


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "example":
        print(generate_config_py_code())
    else:
        loader = DynamicConfigLoader()
        loader.print_summary()
