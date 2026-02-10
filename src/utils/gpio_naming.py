"""
GPIO Naming Utility - Smart default naming based on GPIO number + capabilities.

PHILOSOPHY:
  When a GPIO is initialized for the first time:
  1. Generate a smart default name based on GPIO number + physical pin + capabilities
  2. Allow user to customize this name at any time
  3. NEVER overwrite user-customized names - this is business-critical

DEFAULT NAMING FORMAT:
  "GPIO{number} (PIN{physical}) - {device_type} {capability}"
  Example: "GPIO17 (PIN11) - PUMP (PWM Speed Control)"

USER CUSTOMIZATION:
  Once a user sets a custom name, the system marks it with:
  - `name_customized: true` flag in Firestore
  - `customized_at` timestamp for audit trail
  - `customized_by` user or system identifier

NON-DESTRUCTIVE INITIALIZATION:
  - Check if pin exists and has custom name → PRESERVE IT
  - Check if pin exists with default name → UPDATE with new smarter default
  - Check if pin is NEW → CREATE with smart default name
"""

from typing import Dict, Optional, Tuple
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class GPIOCapability(Enum):
    """GPIO hardware capabilities"""
    PWM = "PWM Speed/Intensity Control"
    RELAY = "Relay Control (On/Off)"
    SENSOR_DIGITAL = "Digital Sensor (Reading)"
    SENSOR_ANALOG = "Analog Sensor (ADC Required)"
    MOTOR_PWM = "Motor PWM Speed"
    MOTOR_DIRECTION = "Motor Direction Control"
    MOTOR_SENSOR = "Motor Home/End Sensor"
    DHT_SENSOR = "Temperature+Humidity Sensor"
    WATER_LEVEL = "Water Level Detection"
    CUSTOM = "Custom Device"


class GPIOCapabilityMap:
    """Map GPIO numbers to their typical capabilities and hardware info"""
    
    # Raspberry Pi 40-pin header GPIO to physical pin number
    GPIO_TO_PHYSICAL_PIN = {
        2: 3, 3: 5, 4: 7, 5: 29, 6: 31,
        7: 26, 8: 24, 9: 21, 10: 19, 11: 23,
        12: 32, 13: 33, 14: 8, 15: 10, 16: 36,
        17: 11, 18: 12, 19: 35, 20: 38, 21: 40,
        22: 15, 23: 16, 24: 18, 25: 22, 26: 37,
        27: 13, 28: 5, 29: 0, 30: 0, 31: 0,
    }
    
    # GPIO pins reserved for I2C/SPI (shouldn't be used for general GPIO)
    RESERVED_PINS = {2, 3}  # I2C pins
    
    # Typical allocation for HarvestPilot system
    TYPICAL_ALLOCATION = {
        17: {
            "device_type": "pump",
            "primary_capability": GPIOCapability.PWM,
            "description": "Irrigation System"
        },
        19: {
            "device_type": "pump",
            "primary_capability": GPIOCapability.RELAY,
            "description": "Pump Relay Control"
        },
        18: {
            "device_type": "light",
            "primary_capability": GPIOCapability.PWM,
            "description": "LED Strip Lighting"
        },
        13: {
            "device_type": "light",
            "primary_capability": GPIOCapability.RELAY,
            "description": "LED Relay Control"
        },
        4: {
            "device_type": "sensor",
            "primary_capability": GPIOCapability.DHT_SENSOR,
            "description": "Environment Monitoring"
        },
        27: {
            "device_type": "sensor",
            "primary_capability": GPIOCapability.WATER_LEVEL,
            "description": "Water Level Monitoring"
        },
        2: {
            "device_type": "motor",
            "primary_capability": GPIOCapability.MOTOR_PWM,
            "description": "Harvest Motor Control"
        },
        3: {
            "device_type": "motor",
            "primary_capability": GPIOCapability.MOTOR_DIRECTION,
            "description": "Harvest Motor Direction"
        },
        5: {
            "device_type": "motor",
            "primary_capability": GPIOCapability.MOTOR_SENSOR,
            "description": "Harvest Motor Home Sensor"
        },
        6: {
            "device_type": "motor",
            "primary_capability": GPIOCapability.MOTOR_SENSOR,
            "description": "Harvest Motor End Sensor"
        },
        12: {
            "device_type": "motor",
            "primary_capability": GPIOCapability.MOTOR_PWM,
            "description": "Secondary Motor Control"
        },
        13: {
            "device_type": "motor",
            "primary_capability": GPIOCapability.MOTOR_DIRECTION,
            "description": "Secondary Motor Direction"
        },
    }


class GPIONamer:
    """Generate intelligent GPIO names based on number + capabilities"""
    
    def __init__(self):
        self.capability_map = GPIOCapabilityMap()
    
    def get_physical_pin(self, gpio_number: int) -> Optional[int]:
        """Get physical pin number for a GPIO number"""
        return self.capability_map.GPIO_TO_PHYSICAL_PIN.get(gpio_number)
    
    def get_gpio_info(self, gpio_number: int) -> Dict:
        """Get all known information about a GPIO pin"""
        physical_pin = self.get_physical_pin(gpio_number)
        typical = self.capability_map.TYPICAL_ALLOCATION.get(gpio_number)
        is_reserved = gpio_number in self.capability_map.RESERVED_PINS
        
        info = {
            "gpio_number": gpio_number,
            "physical_pin": physical_pin,
            "is_reserved": is_reserved,
            "typical_allocation": typical,
        }
        return info
    
    def generate_default_name(
        self,
        gpio_number: int,
        device_type: Optional[str] = None,
        capability: Optional[str] = None
    ) -> str:
        """
        Generate a smart default name for a GPIO pin.
        
        Format: "GPIO{number} (PIN{physical}) - {device_type} {capability}"
        Example: "GPIO17 (PIN11) - PUMP (PWM Speed Control)"
        
        Args:
            gpio_number: BCM GPIO number (e.g., 17)
            device_type: Device type if known (e.g., "pump", "light", "motor")
            capability: Capability descriptor if known
            
        Returns:
            Human-readable default name for the GPIO
        """
        physical_pin = self.get_physical_pin(gpio_number)
        if physical_pin is None:
            return f"GPIO{gpio_number} - UNKNOWN PIN"
        
        # Get typical allocation info
        typical = self.capability_map.TYPICAL_ALLOCATION.get(gpio_number)
        
        if device_type is None and typical:
            device_type = typical.get("device_type", "custom").upper()
        elif device_type:
            device_type = device_type.upper()
        else:
            device_type = "CUSTOM"
        
        if capability is None and typical:
            cap = typical.get("primary_capability")
            if cap:
                capability = cap.value
        elif capability is None:
            capability = "General Purpose I/O"
        
        return f"GPIO{gpio_number} (PIN{physical_pin}) - {device_type} ({capability})"
    
    def generate_legacy_name(
        self,
        gpio_number: int,
        device_type: str,
        motor_tray: Optional[int] = None
    ) -> str:
        """
        Generate names matching the OLD naming convention for backwards compatibility.
        
        This is used when migrating existing configurations.
        
        Args:
            gpio_number: GPIO number
            device_type: Device type
            motor_tray: Tray number if motor
            
        Returns:
            Legacy-style name
        """
        mappings = {
            17: "Pump PWM",
            19: "Pump Relay",
            18: "LED PWM",
            13: "LED Relay",
        }
        
        if gpio_number in mappings:
            return mappings[gpio_number]
        
        if device_type == "motor" and motor_tray:
            # Motor pin - figure out if PWM, dir, home, or end
            if gpio_number in [2, 12]:
                return f"Motor {motor_tray} PWM"
            elif gpio_number in [3, 13]:
                return f"Motor {motor_tray} Direction"
            elif gpio_number in [5]:
                return f"Motor {motor_tray} Home Sensor"
            elif gpio_number in [6]:
                return f"Motor {motor_tray} End Sensor"
        
        if gpio_number == 4:
            return "DHT22 (Temp/Humidity)"
        elif gpio_number == 27:
            return "Water Level Sensor"
        
        return f"GPIO {gpio_number} (Unknown)"


class GPIONameManager:
    """Manage GPIO names with user customization tracking"""
    
    def __init__(self):
        self.namer = GPIONamer()
    
    def create_firestore_entry(
        self,
        gpio_number: int,
        device_type: Optional[str] = None,
        user_custom_name: Optional[str] = None
    ) -> Dict:
        """
        Create a Firestore-ready GPIO entry with smart naming.
        
        If user_custom_name is provided, use it and mark as customized.
        Otherwise, generate smart default name and mark as not customized.
        
        Args:
            gpio_number: GPIO number
            device_type: Device type if known
            user_custom_name: If user provided a custom name
            
        Returns:
            Dictionary ready for Firestore gpioState.{pin} field
        """
        physical_pin = self.namer.get_physical_pin(gpio_number)
        now = datetime.now().isoformat()
        
        if user_custom_name:
            # User provided a custom name
            name = user_custom_name
            name_customized = True
            customized_at = now
            default_name = self.namer.generate_default_name(gpio_number, device_type)
        else:
            # Generate smart default
            name = self.namer.generate_default_name(gpio_number, device_type)
            name_customized = False
            customized_at = None
            default_name = name
        
        entry = {
            "pin": gpio_number,
            "physical_pin": physical_pin,
            "name": name,
            "default_name": default_name,
            "name_customized": name_customized,
            "device_type": device_type or "unknown",
        }
        
        if customized_at:
            entry["customized_at"] = customized_at
        
        return entry
    
    def should_preserve_name(
        self,
        existing_pin_data: Dict
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if we should preserve an existing pin's name.
        
        Returns:
            (preserve: bool, reason: str)
            
        Logic:
        - If name_customized=true: PRESERVE (user set this deliberately)
        - If name exists but not marked customized: Can update to smarter default
        - If no name: Generate new smart default
        """
        if not existing_pin_data:
            return False, "Pin does not exist yet"
        
        if existing_pin_data.get("name_customized", False):
            return True, "User customized this name"
        
        existing_name = existing_pin_data.get("name", "")
        if not existing_name:
            return False, "No name set yet"
        
        # Check if it looks like an old default (hardcoded like "Pump PWM")
        old_defaults = {
            "Pump PWM", "Pump Relay", "LED PWM", "LED Relay",
            "DHT22 (Temp/Humidity)", "Water Level Sensor"
        }
        
        if existing_name in old_defaults or "Motor" in existing_name:
            return False, f"Old default name: {existing_name} (can update)"
        
        # Looks custom-ish but not marked - preserve for safety
        return True, "Name looks customized but not flagged (preserving for safety)"
    
    def update_pin_with_smart_name(
        self,
        gpio_number: int,
        existing_pin_data: Optional[Dict],
        device_type: Optional[str] = None
    ) -> Dict:
        """
        Update or create pin entry with smart naming.
        
        SAFE OPERATION: Never overwrites user-customized names.
        
        Args:
            gpio_number: GPIO number
            existing_pin_data: Current Firestore data for pin (or None if new)
            device_type: Device type if known
            
        Returns:
            Updated entry dict
        """
        # Check if we should preserve existing name
        if existing_pin_data:
            preserve, reason = self.should_preserve_name(existing_pin_data)
            if preserve:
                logger.info(f"GPIO{gpio_number}: Preserving name - {reason}")
                # Return existing data with any updates
                return existing_pin_data
        
        # Generate smart default name
        logger.info(f"GPIO{gpio_number}: Creating smart default name")
        return self.create_firestore_entry(gpio_number, device_type)
    
    def rename_gpio_pin(
        self,
        gpio_number: int,
        new_name: str,
        existing_pin_data: Dict
    ) -> Dict:
        """
        Safely rename a GPIO pin, marking it as user-customized.
        
        Args:
            gpio_number: GPIO number
            new_name: User-provided new name
            existing_pin_data: Current pin data from Firestore
            
        Returns:
            Updated entry dict
        """
        if not new_name or not new_name.strip():
            raise ValueError("Custom name cannot be empty")
        
        new_name = new_name.strip()
        now = datetime.now().isoformat()
        
        # Preserve smart defaults if needed
        device_type = existing_pin_data.get("device_type")
        default_name = existing_pin_data.get(
            "default_name",
            self.namer.generate_default_name(gpio_number, device_type)
        )
        
        updated = {
            **existing_pin_data,
            "name": new_name,
            "default_name": default_name,
            "name_customized": True,
            "customized_at": now,
        }
        
        logger.info(f"GPIO{gpio_number}: Renamed to '{new_name}' (marked as customized)")
        return updated
    
    def reset_to_smart_default(
        self,
        gpio_number: int,
        existing_pin_data: Dict
    ) -> Dict:
        """
        Revert a GPIO pin name back to the smart default.
        
        Args:
            gpio_number: GPIO number
            existing_pin_data: Current pin data from Firestore
            
        Returns:
            Updated entry dict
        """
        device_type = existing_pin_data.get("device_type")
        smart_name = self.namer.generate_default_name(gpio_number, device_type)
        
        updated = {
            **existing_pin_data,
            "name": smart_name,
            "default_name": smart_name,
            "name_customized": False,
        }
        
        # Remove customization metadata
        updated.pop("customized_at", None)
        
        logger.info(f"GPIO{gpio_number}: Reset name to smart default: {smart_name}")
        return updated
