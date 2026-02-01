#!/usr/bin/env python3
"""DEPRECATED: Moved to docs/examples/

This shim is maintained for backward compatibility.
Run the example from: docs/examples/dynamic_config_example.py
"""

import sys
import warnings
from pathlib import Path

warnings.warn(
    "examples_dynamic_config.py moved to docs/examples/dynamic_config_example.py",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
sys.path.insert(0, str(Path(__file__).parent / "docs" / "examples"))
from dynamic_config_example import *  # noqa: F401, F403

if __name__ == "__main__":
    main()


def setup_pi_1_standard():
    """Pi 1: Standard configuration (most common pins)"""
    print("\n" + "="*70)
    print("Setting up Raspberry Pi 1 - Standard Configuration (Rack A)")
    print("="*70)
    
    manager = PinConfigManager()
    
    # Create default config (uses GPIO 17, 18, etc)
    manager.create_default_config(
        pi_model="Raspberry Pi 4 Model B",
        module_id="module-001",
        description="Rack A - Vertical (standard pins)"
    )
    
    manager.print_config()
    return manager


def setup_pi_2_custom_pins():
    """Pi 2: Custom pins (some GPIOs unavailable due to other devices)"""
    print("\n" + "="*70)
    print("Setting up Raspberry Pi 2 - Custom Pin Configuration (Rack B)")
    print("="*70)
    
    manager = PinConfigManager()
    
    # Create base config
    manager.create_default_config(
        pi_model="Raspberry Pi 4 Model B",
        module_id="module-002",
        description="Rack B - Vertical (custom pins due to I2C/SPI on GPIO 2-3)"
    )
    
    # Reassign pump to different pin (GPIO 17 is already used by I2C)
    manager.unassign_pin(17)
    manager.assign_pin_to_device(
        gpio_number=26,
        device_type="pump",
        device_id="pump-002",
        name="Irrigation Pump (Module 2)",
        mode="PWM",
        pwm_frequency=1000,
        config={"speed_min": 0, "speed_max": 100}
    )
    
    # Reassign light to different pin
    manager.unassign_pin(18)
    manager.assign_pin_to_device(
        gpio_number=25,
        device_type="light",
        device_id="light-002",
        name="LED Strip (Module 2)",
        mode="PWM",
        pwm_frequency=1000,
        config={"intensity_min": 0, "intensity_max": 100}
    )
    
    manager.print_config()
    return manager


def setup_pi_3_mixed_devices():
    """Pi 3: Mixed configuration with relay and additional devices"""
    print("\n" + "="*70)
    print("Setting up Raspberry Pi 3 - Mixed Configuration (Rack C)")
    print("="*70)
    
    manager = PinConfigManager()
    
    # Create base config
    manager.create_default_config(
        pi_model="Raspberry Pi 4 Model B",
        module_id="module-003",
        description="Rack C - Horizontal (with auxiliary relay)"
    )
    
    # Add auxiliary relay
    manager.assign_pin_to_device(
        gpio_number=23,
        device_type="relay",
        device_id="relay-aux-001",
        name="Auxiliary Relay (Co2, Misting, etc)",
        mode="OUTPUT",
        config={"function": "auxiliary"}
    )
    
    # Add second relay for backup pump
    manager.assign_pin_to_device(
        gpio_number=24,
        device_type="relay",
        device_id="relay-backup-pump",
        name="Backup Pump Relay",
        mode="OUTPUT",
        config={"function": "backup_pump"}
    )
    
    manager.print_config()
    return manager


def show_comparison():
    """Show comparison of all three Pi configurations"""
    print("\n" + "="*70)
    print("📊 COMPARISON: Three Different Pi Configurations")
    print("="*70)
    
    configs = {
        "Pi 1 (Rack A)": {
            "Pump": "GPIO 17 (Pin 11)",
            "Light": "GPIO 18 (Pin 12)",
            "Motors": "GPIO 2,3,9,11,10,22,14,15,8,7,16,20",
            "Sensors": "GPIO 4 (DHT22), GPIO 27 (Water Level)",
            "Extra": "None"
        },
        "Pi 2 (Rack B)": {
            "Pump": "GPIO 26 (Pin 37) - Custom!",
            "Light": "GPIO 25 (Pin 22) - Custom!",
            "Motors": "GPIO 2,3,9,11,10,22,14,15,8,7,16,20",
            "Sensors": "GPIO 4 (DHT22), GPIO 27 (Water Level)",
            "Extra": "None"
        },
        "Pi 3 (Rack C)": {
            "Pump": "GPIO 17 (Pin 11)",
            "Light": "GPIO 18 (Pin 12)",
            "Motors": "GPIO 2,3,9,11,10,22,14,15,8,7,16,20",
            "Sensors": "GPIO 4 (DHT22), GPIO 27 (Water Level)",
            "Extra": "GPIO 23 (Aux Relay), GPIO 24 (Backup Pump)"
        }
    }
    
    for pi_name, devices in configs.items():
        print(f"\n{pi_name}:")
        for device, pin in devices.items():
            print(f"  {device:12s} → {pin}")


def code_example_usage():
    """Show how to use dynamic config in your code"""
    print("\n" + "="*70)
    print("💻 CODE EXAMPLE: Using Dynamic Configuration")
    print("="*70)
    
    code = '''
# In your hardware controller (e.g., controllers/lighting.py)
from utils.dynamic_config_loader import DynamicConfigLoader

class LightingController:
    def __init__(self):
        loader = DynamicConfigLoader()
        
        # Get light pin from configuration
        self.pin = loader.get_pin_for_device_type("light")
        
        if not self.pin:
            print("❌ Light device not configured!")
            return
        
        # Get PWM frequency
        self.frequency = loader.get_pwm_frequency("light") or 1000
        
        print(f"✅ Light configured on GPIO {self.pin} @ {self.frequency}Hz")
    
    async def set_lights(self, state: bool, intensity: int = 100):
        if not self.pin:
            return
        
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        
        if state:
            pwm = GPIO.PWM(self.pin, self.frequency)
            pwm.start(intensity)
        else:
            GPIO.output(self.pin, GPIO.LOW)


# In your hardware controller (e.g., controllers/irrigation.py)
class IrrigationController:
    def __init__(self):
        loader = DynamicConfigLoader()
        
        # Get pump pin from configuration
        self.pin = loader.get_pin_for_device_type("pump")
        self.frequency = loader.get_pwm_frequency("pump") or 1000
        
        print(f"✅ Pump configured on GPIO {self.pin}")
    
    async def start_pump(self, duration: int = 30, speed: int = 80):
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pin, GPIO.OUT)
        
        pwm = GPIO.PWM(self.pin, self.frequency)
        pwm.start(speed)
        # ... rest of implementation


# In config.py
import os
from utils.dynamic_config_loader import DynamicConfigLoader

loader = DynamicConfigLoader()

# Load from config or .env
PUMP_PWM_PIN = loader.get_pin_for_device_type("pump") or int(os.getenv("PUMP_PWM_PIN", "17"))
LED_PWM_PIN = loader.get_pin_for_device_type("light") or int(os.getenv("LED_PWM_PIN", "18"))
PUMP_PWM_FREQUENCY = loader.get_pwm_frequency("pump") or 1000
LED_PWM_FREQUENCY = loader.get_pwm_frequency("light") or 1000

# Get module info
MODULE_ID = loader.get_module_id()
PI_MODEL = loader.get_pi_model()

print(f"Running {PI_MODEL} as {MODULE_ID}")
print(f"Pump on GPIO {PUMP_PWM_PIN}, Light on GPIO {LED_PWM_PIN}")
'''
    
    print(code)


def main():
    """Main setup wizard"""
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "pi1":
            setup_pi_1_standard()
        elif sys.argv[1] == "pi2":
            setup_pi_2_custom_pins()
        elif sys.argv[1] == "pi3":
            setup_pi_3_mixed_devices()
        elif sys.argv[1] == "compare":
            show_comparison()
        elif sys.argv[1] == "example":
            code_example_usage()
        elif sys.argv[1] == "all":
            setup_pi_1_standard()
            setup_pi_2_custom_pins()
            setup_pi_3_mixed_devices()
            show_comparison()
            code_example_usage()
    else:
        print("\n" + "="*70)
        print("🔌 Dynamic GPIO Configuration - Setup Examples")
        print("="*70)
        print("\nUsage:")
        print("  python3 examples_dynamic_config.py [command]")
        print("\nCommands:")
        print("  pi1      - Setup Raspberry Pi 1 (standard pins)")
        print("  pi2      - Setup Raspberry Pi 2 (custom pins)")
        print("  pi3      - Setup Raspberry Pi 3 (with relay)")
        print("  compare  - Show comparison of all three")
        print("  example  - Show code examples")
        print("  all      - Run all setups")
        print()


if __name__ == "__main__":
    main()
