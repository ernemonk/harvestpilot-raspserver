#!/usr/bin/env python3
"""
HarvestPilot Module Configuration System
Per-Raspberry Pi device configuration for modular farm automation
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# ============================================================================
# ARCHITECTURE: One Pi = One Module (Multiple devices per module)
# ============================================================================
# 
# Each Raspberry Pi controls ONE growing module (e.g., one vertical rack)
# Each module contains:
#   - 1 x Pump (irrigation for all trays)
#   - 1 x LED light strip (shared across all trays)
#   - 6 x Harvest motors (one per tray)
#   - 1 x Sensor pod (DHT22, soil moisture, water level)
#
# CONFIG STRUCTURE:
# /home/monkphx/harvestpilot-raspserver/
# ├── config/
# │   ├── device.json          # This Pi's identity
# │   ├── module.json          # This module's configuration
# │   └── gpio_map.json        # Pin assignments (customizable per Pi)
# └── data/
#     └── module.db            # Local SQLite with tray/crop data
#

@dataclass
class ModuleDevice:
    """Individual device on a module (pump, light, motor, sensor)"""
    device_type: str        # "pump", "light", "motor", "sensor"
    device_id: str          # Unique ID (e.g., "pump-001")
    name: str               # Human-readable name (e.g., "Irrigation Pump")
    gpio_pins: Dict[str, int]  # Pin assignments (e.g., {"pwm": 17, "dir": 3})
    enabled: bool           # Is this device active?
    config: Dict[str, any]  # Device-specific config (frequency, speed, etc)


@dataclass
class ControlModule:
    """One Raspberry Pi = One Control Module"""
    module_id: str              # e.g., "module-001"
    location: str               # e.g., "Rack A - Vertical"
    num_trays: int              # Number of growing trays (typically 6)
    devices: List[ModuleDevice] # All devices in this module
    created_at: str             # ISO timestamp
    description: str            # Module description


@dataclass
class DeviceIdentity:
    """This Raspberry Pi's identity"""
    device_id: str              # e.g., "raspserver-001"
    module_id: str              # Which module this Pi controls
    hostname: str               # Network name
    mac_address: str            # Network MAC
    firmware_version: str       # Current firmware
    registered_at: str          # ISO timestamp


class ModuleConfigManager:
    """Manage per-module configuration files"""
    
    def __init__(self, config_dir: str = "/home/monkphx/harvestpilot-raspserver/config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        self.device_file = self.config_dir / "device.json"
        self.module_file = self.config_dir / "module.json"
        self.gpio_file = self.config_dir / "gpio_map.json"
    
    def create_device_identity(
        self,
        device_id: str,
        module_id: str,
        hostname: str,
        mac_address: str,
        firmware_version: str = "1.0.0"
    ) -> DeviceIdentity:
        """Create and save device identity"""
        identity = DeviceIdentity(
            device_id=device_id,
            module_id=module_id,
            hostname=hostname,
            mac_address=mac_address,
            firmware_version=firmware_version,
            registered_at=datetime.now().isoformat()
        )
        
        with open(self.device_file, 'w') as f:
            json.dump(asdict(identity), f, indent=2)
        
        print(f"✅ Device identity saved: {device_id} → {module_id}")
        return identity
    
    def load_device_identity(self) -> Optional[DeviceIdentity]:
        """Load device identity"""
        if not self.device_file.exists():
            return None
        
        with open(self.device_file) as f:
            data = json.load(f)
            return DeviceIdentity(**data)
    
    def create_module(
        self,
        module_id: str,
        location: str,
        num_trays: int = 6,
        description: str = ""
    ) -> ControlModule:
        """Create a new module configuration"""
        
        # Default devices for a module
        devices = [
            ModuleDevice(
                device_type="pump",
                device_id="pump-001",
                name="Irrigation Pump",
                gpio_pins={"pwm": 17, "relay": 19},
                enabled=True,
                config={
                    "pwm_frequency": 1000,
                    "default_speed": 80,
                    "max_duration": 60
                }
            ),
            ModuleDevice(
                device_type="light",
                device_id="light-001",
                name="LED Strip",
                gpio_pins={"pwm": 18},
                enabled=True,
                config={
                    "pwm_frequency": 1000,
                    "default_intensity": 80,
                    "on_time": "06:00",
                    "off_time": "22:00"
                }
            ),
            ModuleDevice(
                device_type="sensor",
                device_id="sensor-001",
                name="Environmental Sensor Pod",
                gpio_pins={"dht22": 4, "water_level": 27},
                enabled=True,
                config={
                    "dht22_pin": 4,
                    "water_level_pin": 27,
                    "read_interval": 5
                }
            )
        ]
        
        # Add harvest motors for each tray
        motor_pins = [
            {"tray": 1, "pwm": 2, "dir": 3},
            {"tray": 2, "pwm": 9, "dir": 11},
            {"tray": 3, "pwm": 10, "dir": 22},
            {"tray": 4, "pwm": 14, "dir": 15},
            {"tray": 5, "pwm": 8, "dir": 7},
            {"tray": 6, "pwm": 16, "dir": 20},
        ]
        
        for motor_pin in motor_pins[:num_trays]:
            devices.append(ModuleDevice(
                device_type="motor",
                device_id=f"motor-{motor_pin['tray']}",
                name=f"Harvest Belt - Tray {motor_pin['tray']}",
                gpio_pins=motor_pin,
                enabled=True,
                config={
                    "tray_id": motor_pin['tray'],
                    "pwm_frequency": 1000,
                    "speed": 50
                }
            ))
        
        module = ControlModule(
            module_id=module_id,
            location=location,
            num_trays=num_trays,
            devices=devices,
            created_at=datetime.now().isoformat(),
            description=description
        )
        
        with open(self.module_file, 'w') as f:
            json.dump(asdict(module), f, indent=2)
        
        print(f"✅ Module configuration saved: {module_id} ({location})")
        return module
    
    def load_module(self) -> Optional[ControlModule]:
        """Load module configuration"""
        if not self.module_file.exists():
            return None
        
        with open(self.module_file) as f:
            data = json.load(f)
            # Convert device dicts back to ModuleDevice objects
            devices = [ModuleDevice(**d) for d in data['devices']]
            data['devices'] = devices
            return ControlModule(**data)
    
    def update_device_pins(self, device_id: str, gpio_pins: Dict[str, int]) -> bool:
        """Update GPIO pins for a specific device"""
        module = self.load_module()
        if not module:
            return False
        
        for device in module.devices:
            if device.device_id == device_id:
                device.gpio_pins = gpio_pins
                with open(self.module_file, 'w') as f:
                    json.dump(asdict(module), f, indent=2)
                print(f"✅ Updated pins for {device_id}: {gpio_pins}")
                return True
        
        print(f"❌ Device {device_id} not found")
        return False
    
    def get_device(self, device_id: str) -> Optional[ModuleDevice]:
        """Get a specific device from the module"""
        module = self.load_module()
        if not module:
            return None
        
        for device in module.devices:
            if device.device_id == device_id:
                return device
        
        return None
    
    def get_devices_by_type(self, device_type: str) -> List[ModuleDevice]:
        """Get all devices of a specific type"""
        module = self.load_module()
        if not module:
            return []
        
        return [d for d in module.devices if d.device_type == device_type]
    
    def list_all_devices(self) -> Dict[str, List[ModuleDevice]]:
        """List all devices grouped by type"""
        module = self.load_module()
        if not module:
            return {}
        
        grouped = {}
        for device in module.devices:
            if device.device_type not in grouped:
                grouped[device.device_type] = []
            grouped[device.device_type].append(device)
        
        return grouped
    
    def print_config(self):
        """Print current configuration"""
        identity = self.load_device_identity()
        module = self.load_module()
        
        if not identity or not module:
            print("❌ Configuration not found")
            return
        
        print("\n" + "="*60)
        print("🌾 HarvestPilot Module Configuration")
        print("="*60)
        
        print(f"\n📱 Device Identity:")
        print(f"  Device ID:    {identity.device_id}")
        print(f"  Module ID:    {identity.module_id}")
        print(f"  Hostname:     {identity.hostname}")
        print(f"  MAC Address:  {identity.mac_address}")
        print(f"  Firmware:     {identity.firmware_version}")
        
        print(f"\n📦 Module Configuration:")
        print(f"  Module ID:    {module.module_id}")
        print(f"  Location:     {module.location}")
        print(f"  Trays:        {module.num_trays}")
        print(f"  Description:  {module.description}")
        
        print(f"\n🔧 Devices ({len(module.devices)} total):")
        devices_by_type = self.list_all_devices()
        
        for device_type, devices in devices_by_type.items():
            print(f"\n  {device_type.upper()}:")
            for device in devices:
                status = "✅" if device.enabled else "❌"
                print(f"    {status} {device.name} ({device.device_id})")
                if device.gpio_pins:
                    pins_str = ", ".join([f"{k}={v}" for k, v in device.gpio_pins.items()])
                    print(f"       GPIO: {pins_str}")
        
        print("\n" + "="*60 + "\n")


def setup_new_pi(
    device_id: str,
    module_id: str,
    location: str,
    hostname: str,
    mac_address: str,
    num_trays: int = 6
) -> bool:
    """One-command setup for a new Raspberry Pi"""
    
    print("\n" + "="*60)
    print("🚀 Setting up new HarvestPilot Pi Module")
    print("="*60)
    
    manager = ModuleConfigManager()
    
    # Create device identity
    print(f"\n1️⃣  Creating device identity...")
    manager.create_device_identity(
        device_id=device_id,
        module_id=module_id,
        hostname=hostname,
        mac_address=mac_address
    )
    
    # Create module configuration
    print(f"\n2️⃣  Creating module configuration...")
    manager.create_module(
        module_id=module_id,
        location=location,
        num_trays=num_trays,
        description=f"Module {module_id} at {location}"
    )
    
    # Print configuration
    print(f"\n3️⃣  Configuration saved!")
    manager.print_config()
    
    return True


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        # Setup example: python3 module_config.py setup
        setup_new_pi(
            device_id="raspserver-001",
            module_id="module-001",
            location="Rack A - Vertical",
            hostname="raspserver",
            mac_address="b8:27:eb:xx:xx:xx",
            num_trays=6
        )
    else:
        # Just print current config
        manager = ModuleConfigManager()
        manager.print_config()
