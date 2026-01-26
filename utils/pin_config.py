#!/usr/bin/env python3
"""
Advanced GPIO Pin Configuration System with Scheduling
Allows per-Raspberry Pi dynamic pin assignment and scheduled operations
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
from datetime import datetime, time


class PinMode(Enum):
    """GPIO Pin mode"""
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
    PWM = "PWM"
    SENSOR = "SENSOR"


class DeviceType(Enum):
    """Device types that can be controlled"""
    PUMP = "pump"
    LIGHT = "light"
    MOTOR = "motor"
    SENSOR_DHT = "sensor_dht"
    SENSOR_WATER = "sensor_water"
    RELAY = "relay"
    CUSTOM = "custom"


class ScheduleType(Enum):
    """Schedule operation types"""
    PWM_CYCLE = "pwm_cycle"          # PWM on/off cycles
    PWM_FADE = "pwm_fade"            # Gradual PWM change
    DIGITAL_TOGGLE = "digital_toggle" # Digital HIGH/LOW
    SENSOR_READ = "sensor_read"       # Read sensor at interval
    TIMED_PULSE = "timed_pulse"       # Single pulse at specific time


@dataclass
class Schedule:
    """Schedule for automated GPIO operations"""
    schedule_id: str                    # Unique schedule ID
    schedule_type: str                  # Type from ScheduleType enum
    enabled: bool = True                # Is this schedule active?
    
    # Time-based scheduling
    start_time: Optional[str] = None    # "HH:MM" (24-hour) or None for immediate
    end_time: Optional[str] = None      # "HH:MM" (24-hour) or None for no end
    days_of_week: Optional[List[int]] = None  # [0-6] where 0=Monday, None=every day
    
    # Interval-based scheduling
    interval_seconds: Optional[int] = None    # Run every N seconds
    duration_seconds: Optional[int] = None    # How long to run each cycle
    
    # PWM-specific parameters
    pwm_duty_start: Optional[int] = None      # Starting duty cycle (0-100)
    pwm_duty_end: Optional[int] = None        # Ending duty cycle (0-100)
    pwm_fade_duration: Optional[int] = None   # Seconds to fade from start to end
    
    # Digital output parameters
    digital_state: Optional[bool] = None      # HIGH (True) or LOW (False)
    
    # Sensor read parameters
    read_interval_seconds: Optional[int] = None  # How often to read sensor
    store_readings: bool = True                   # Store readings to database
    
    # Metadata
    description: str = ""
    created_at: Optional[str] = None
    last_run_at: Optional[str] = None


@dataclass
class GPIOPin:
    """GPIO Pin configuration with scheduling support"""
    gpio_number: int           # BCM GPIO number
    physical_pin: int          # Physical pin number on header
    mode: str                  # INPUT, OUTPUT, PWM, SENSOR
    device_type: str           # pump, light, motor, sensor_dht, sensor_water, etc
    device_id: str             # Unique device ID (e.g., "pump-001")
    name: str                  # Human-readable name
    enabled: bool              # Is this pin active?
    pwm_frequency: Optional[int] = None  # For PWM pins (Hz)
    pull_up: Optional[bool] = None       # For INPUT pins
    active_high: bool = True             # Logic level (True=HIGH active, False=LOW active)
    config: Dict[str, Any] = None        # Device-specific config
    schedules: List[Schedule] = field(default_factory=list)  # Scheduled operations


@dataclass
class GPIOConfiguration:
    """Complete GPIO configuration for a Raspberry Pi"""
    pi_model: str              # e.g., "Raspberry Pi 4 Model B"
    module_id: str             # Which module this controls
    pins: List[GPIOPin]        # All pin configurations
    created_at: str            # ISO timestamp
    modified_at: str           # ISO timestamp
    description: str           # Configuration description


class PinConfigManager:
    """Manage GPIO pin configurations per Raspberry Pi"""
    
    def __init__(self, config_dir: str = "/home/monkphx/harvestpilot-raspserver/config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.pin_config_file = self.config_dir / "gpio_pins.json"
    
    def create_default_config(
        self,
        pi_model: str = "Raspberry Pi 4 Model B",
        module_id: str = "module-001",
        description: str = ""
    ) -> GPIOConfiguration:
        """Create default GPIO configuration for a Pi"""
        
        pins = [
            GPIOPin(
                gpio_number=18,
                physical_pin=12,
                mode="PWM",
                device_type="light",
                device_id="light-001",
                name="LED Strip",
                enabled=True,
                pwm_frequency=1000,
                config={"intensity_min": 0, "intensity_max": 100}
            ),
            GPIOPin(
                gpio_number=17,
                physical_pin=11,
                mode="PWM",
                device_type="pump",
                device_id="pump-001",
                name="Irrigation Pump",
                enabled=True,
                pwm_frequency=1000,
                config={"speed_min": 0, "speed_max": 100}
            ),
            # Motor pins
            GPIOPin(
                gpio_number=2,
                physical_pin=3,
                mode="OUTPUT",
                device_type="motor",
                device_id="motor-1-pwm",
                name="Tray 1 Motor PWM",
                enabled=True,
                pwm_frequency=1000,
                config={"tray_id": 1}
            ),
            GPIOPin(
                gpio_number=3,
                physical_pin=5,
                mode="OUTPUT",
                device_type="motor",
                device_id="motor-1-dir",
                name="Tray 1 Motor Direction",
                enabled=True,
                config={"tray_id": 1}
            ),
            # Sensor pins
            GPIOPin(
                gpio_number=4,
                physical_pin=7,
                mode="SENSOR",
                device_type="sensor_dht",
                device_id="sensor-dht22",
                name="DHT22 (Temp/Humidity)",
                enabled=True,
                config={"sensor_type": "DHT22"}
            ),
            GPIOPin(
                gpio_number=27,
                physical_pin=13,
                mode="INPUT",
                device_type="sensor_water",
                device_id="sensor-water",
                name="Water Level Sensor",
                enabled=True,
                pull_up=True,
                active_high=False,  # Active LOW
                config={"sensor_type": "water_level"}
            ),
        ]
        
        config = GPIOConfiguration(
            pi_model=pi_model,
            module_id=module_id,
            pins=pins,
            created_at=datetime.now().isoformat(),
            modified_at=datetime.now().isoformat(),
            description=description or f"GPIO configuration for {module_id}"
        )
        
        self.save_config(config)
        return config
    
    def save_config(self, config: GPIOConfiguration) -> bool:
        """Save configuration to file"""
        try:
            config.modified_at = datetime.now().isoformat()
            
            with open(self.pin_config_file, 'w') as f:
                # Convert GPIOPin objects to dicts
                pins_data = [asdict(pin) for pin in config.pins]
                config_dict = asdict(config)
                config_dict['pins'] = pins_data
                
                json.dump(config_dict, f, indent=2)
            
            return True
        except Exception as e:
            print(f"❌ Error saving config: {e}")
            return False
    
    def load_config(self) -> Optional[GPIOConfiguration]:
        """Load configuration from file"""
        if not self.pin_config_file.exists():
            return None
        
        try:
            with open(self.pin_config_file) as f:
                data = json.load(f)
                
                # Convert dicts back to GPIOPin objects
                pins = [GPIOPin(**pin_data) for pin_data in data['pins']]
                data['pins'] = pins
                
                return GPIOConfiguration(**data)
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            return None
    
    def assign_pin_to_device(
        self,
        gpio_number: int,
        device_type: str,
        device_id: str,
        name: str,
        mode: str = "OUTPUT",
        pwm_frequency: Optional[int] = None,
        config: Optional[Dict] = None
    ) -> bool:
        """Assign a GPIO pin to a device"""
        
        current_config = self.load_config()
        if not current_config:
            print("❌ No configuration found. Create one first.")
            return False
        
        # Find physical pin number
        physical_pin_map = {
            2: 3, 3: 5, 4: 7, 5: 29, 6: 31,
            7: 26, 8: 24, 9: 21, 10: 19, 11: 23,
            12: 32, 13: 33, 14: 8, 15: 10, 16: 36,
            17: 11, 18: 12, 19: 35, 20: 38, 21: 40,
            22: 15, 23: 16, 24: 18, 25: 22, 26: 37,
            27: 13,
        }
        
        physical_pin = physical_pin_map.get(gpio_number)
        if not physical_pin:
            print(f"❌ GPIO {gpio_number} not found on Raspberry Pi")
            return False
        
        # Check if pin already assigned
        for existing_pin in current_config.pins:
            if existing_pin.gpio_number == gpio_number:
                # Remove existing assignment
                current_config.pins.remove(existing_pin)
                print(f"⚠️  Removed existing assignment for GPIO {gpio_number}")
        
        # Create new pin configuration
        new_pin = GPIOPin(
            gpio_number=gpio_number,
            physical_pin=physical_pin,
            mode=mode,
            device_type=device_type,
            device_id=device_id,
            name=name,
            enabled=True,
            pwm_frequency=pwm_frequency,
            config=config or {}
        )
        
        current_config.pins.append(new_pin)
        current_config.pins.sort(key=lambda p: p.gpio_number)
        
        if self.save_config(current_config):
            print(f"✅ Assigned GPIO {gpio_number} (Physical Pin {physical_pin}) to {device_id}")
            return True
        
        return False
    
    def unassign_pin(self, gpio_number: int) -> bool:
        """Unassign a GPIO pin"""
        
        config = self.load_config()
        if not config:
            return False
        
        for pin in config.pins[:]:
            if pin.gpio_number == gpio_number:
                config.pins.remove(pin)
                if self.save_config(config):
                    print(f"✅ Unassigned GPIO {gpio_number}")
                    return True
        
        print(f"❌ GPIO {gpio_number} not found")
        return False
    
    def get_pin_for_device(self, device_id: str) -> Optional[GPIOPin]:
        """Get GPIO pin for a device"""
        config = self.load_config()
        if not config:
            return None
        
        for pin in config.pins:
            if pin.device_id == device_id:
                return pin
        
        return None
    
    def get_pins_by_type(self, device_type: str) -> List[GPIOPin]:
        """Get all pins assigned to a device type"""
        config = self.load_config()
        if not config:
            return []
        
        return [p for p in config.pins if p.device_type == device_type and p.enabled]
    
    def get_output_pins(self) -> List[GPIOPin]:
        """Get all output pins (OUTPUT, PWM)"""
        config = self.load_config()
        if not config:
            return []
        
        return [p for p in config.pins if p.mode in ["OUTPUT", "PWM"] and p.enabled]
    
    def get_input_pins(self) -> List[GPIOPin]:
        """Get all input pins (INPUT, SENSOR)"""
        config = self.load_config()
        if not config:
            return []
        
        return [p for p in config.pins if p.mode in ["INPUT", "SENSOR"] and p.enabled]
    
    def enable_pin(self, gpio_number: int) -> bool:
        """Enable a pin"""
        config = self.load_config()
        if not config:
            return False
        
        for pin in config.pins:
            if pin.gpio_number == gpio_number:
                pin.enabled = True
                return self.save_config(config)
        
        return False
    
    def disable_pin(self, gpio_number: int) -> bool:
        """Disable a pin"""
        config = self.load_config()
        if not config:
            return False
        
        for pin in config.pins:
            if pin.gpio_number == gpio_number:
                pin.enabled = False
                return self.save_config(config)
        
        return False
    
    def print_config(self):
        """Print current GPIO configuration"""
        config = self.load_config()
        if not config:
            print("❌ No configuration found")
            return
        
        print("\n" + "="*70)
        print("🔌 GPIO Pin Configuration")
        print("="*70)
        
        print(f"\n📱 Pi Model:    {config.pi_model}")
        print(f"📦 Module:     {config.module_id}")
        print(f"📝 Description: {config.description}")
        print(f"🔄 Modified:   {config.modified_at}")
        
        # Group by device type
        grouped = {}
        for pin in config.pins:
            if pin.device_type not in grouped:
                grouped[pin.device_type] = []
            grouped[pin.device_type].append(pin)
        
        print(f"\n🔧 Devices ({len(config.pins)} pins):\n")
        
        for device_type, pins in sorted(grouped.items()):
            print(f"  {device_type.upper()}:")
            for pin in pins:
                status = "✅" if pin.enabled else "❌"
                pwm_str = f", {pin.pwm_frequency}Hz" if pin.pwm_frequency else ""
                print(f"    {status} GPIO {pin.gpio_number:2d} (Pin {pin.physical_pin:2d}) - {pin.name}")
                print(f"       Mode: {pin.mode}, Device: {pin.device_id}{pwm_str}")
                if pin.pull_up is not None:
                    pull = "Pull-UP" if pin.pull_up else "No pull"
                    print(f"       {pull}, Active {'HIGH' if pin.active_high else 'LOW'}")
            print()
        
        # Summary
        print(f"\n📊 Summary:")
        print(f"   Output Pins (OUTPUT/PWM):  {len(self.get_output_pins())}")
        print(f"   Input Pins (INPUT/SENSOR): {len(self.get_input_pins())}")
        
        print("\n" + "="*70 + "\n")
    
    def get_config_for_import(self) -> Dict[str, Any]:
        """Get configuration formatted for use in config.py"""
        config = self.load_config()
        if not config:
            return {}
        
        import_config = {}
        
        for pin in config.pins:
            if pin.enabled:
                if pin.device_type == "pump":
                    import_config["PUMP_PWM_PIN"] = pin.gpio_number
                    if pin.pwm_frequency:
                        import_config["PUMP_PWM_FREQUENCY"] = pin.pwm_frequency
                
                elif pin.device_type == "light":
                    import_config["LED_PWM_PIN"] = pin.gpio_number
                    if pin.pwm_frequency:
                        import_config["LED_PWM_FREQUENCY"] = pin.pwm_frequency
                
                elif pin.device_type == "sensor_dht":
                    import_config["SENSOR_DHT22_PIN"] = pin.gpio_number
                
                elif pin.device_type == "sensor_water":
                    import_config["SENSOR_WATER_LEVEL_PIN"] = pin.gpio_number
        
        return import_config
    
    # ========================================================================
    # SCHEDULING METHODS
    # ========================================================================
    
    def add_schedule(
        self,
        gpio_number: int,
        schedule_type: str,
        schedule_id: Optional[str] = None,
        **kwargs
    ) -> bool:
        """Add a schedule to a GPIO pin
        
        Args:
            gpio_number: GPIO pin number
            schedule_type: Type from ScheduleType enum
            schedule_id: Optional custom ID (auto-generated if not provided)
            **kwargs: Schedule parameters (start_time, interval_seconds, etc.)
        
        Returns:
            bool indicating success
        """
        config = self.load_config()
        if not config:
            print("❌ No configuration found")
            return False
        
        # Find the pin
        pin = None
        for p in config.pins:
            if p.gpio_number == gpio_number:
                pin = p
                break
        
        if not pin:
            print(f"❌ GPIO {gpio_number} not found in configuration")
            return False
        
        # Generate schedule ID if not provided
        if not schedule_id:
            schedule_id = f"schedule-{gpio_number}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Create schedule
        schedule = Schedule(
            schedule_id=schedule_id,
            schedule_type=schedule_type,
            created_at=datetime.now().isoformat(),
            **kwargs
        )
        
        # Initialize schedules list if needed
        if not hasattr(pin, 'schedules') or pin.schedules is None:
            pin.schedules = []
        
        # Add schedule
        pin.schedules.append(schedule)
        
        if self.save_config(config):
            print(f"✅ Added {schedule_type} schedule to GPIO {gpio_number}")
            return True
        
        return False
    
    def remove_schedule(self, gpio_number: int, schedule_id: str) -> bool:
        """Remove a schedule from a GPIO pin"""
        config = self.load_config()
        if not config:
            return False
        
        for pin in config.pins:
            if pin.gpio_number == gpio_number:
                if hasattr(pin, 'schedules') and pin.schedules:
                    pin.schedules = [s for s in pin.schedules if s.schedule_id != schedule_id]
                    if self.save_config(config):
                        print(f"✅ Removed schedule {schedule_id} from GPIO {gpio_number}")
                        return True
        
        print(f"❌ Schedule {schedule_id} not found on GPIO {gpio_number}")
        return False
    
    def get_schedules(self, gpio_number: int) -> List[Schedule]:
        """Get all schedules for a GPIO pin"""
        config = self.load_config()
        if not config:
            return []
        
        for pin in config.pins:
            if pin.gpio_number == gpio_number:
                return getattr(pin, 'schedules', [])
        
        return []
    
    def enable_schedule(self, gpio_number: int, schedule_id: str) -> bool:
        """Enable a specific schedule"""
        config = self.load_config()
        if not config:
            return False
        
        for pin in config.pins:
            if pin.gpio_number == gpio_number:
                if hasattr(pin, 'schedules') and pin.schedules:
                    for schedule in pin.schedules:
                        if schedule.schedule_id == schedule_id:
                            schedule.enabled = True
                            return self.save_config(config)
        
        return False
    
    def disable_schedule(self, gpio_number: int, schedule_id: str) -> bool:
        """Disable a specific schedule"""
        config = self.load_config()
        if not config:
            return False
        
        for pin in config.pins:
            if pin.gpio_number == gpio_number:
                if hasattr(pin, 'schedules') and pin.schedules:
                    for schedule in pin.schedules:
                        if schedule.schedule_id == schedule_id:
                            schedule.enabled = False
                            return self.save_config(config)
        
        return False
    
    def create_pwm_cycle_schedule(
        self,
        gpio_number: int,
        start_time: str,
        end_time: str,
        pwm_duty: int = 100,
        description: str = ""
    ) -> bool:
        """Create a PWM cycle schedule (e.g., lights on 6AM-10PM at 80%)
        
        Args:
            gpio_number: GPIO pin number
            start_time: Start time in "HH:MM" format (24-hour)
            end_time: End time in "HH:MM" format (24-hour)
            pwm_duty: PWM duty cycle (0-100)
            description: Optional description
        """
        return self.add_schedule(
            gpio_number=gpio_number,
            schedule_type=ScheduleType.PWM_CYCLE.value,
            start_time=start_time,
            end_time=end_time,
            pwm_duty_start=pwm_duty,
            description=description or f"PWM cycle {start_time}-{end_time} at {pwm_duty}%"
        )
    
    def create_sensor_read_schedule(
        self,
        gpio_number: int,
        read_interval_seconds: int,
        store_readings: bool = True,
        description: str = ""
    ) -> bool:
        """Create a sensor read schedule (e.g., read every 5 minutes)
        
        Args:
            gpio_number: GPIO pin number
            read_interval_seconds: How often to read in seconds
            store_readings: Whether to store readings to database
            description: Optional description
        """
        return self.add_schedule(
            gpio_number=gpio_number,
            schedule_type=ScheduleType.SENSOR_READ.value,
            read_interval_seconds=read_interval_seconds,
            store_readings=store_readings,
            description=description or f"Read sensor every {read_interval_seconds}s"
        )
    
    def create_irrigation_schedule(
        self,
        gpio_number: int,
        interval_hours: int,
        duration_seconds: int,
        pwm_speed: int = 80,
        description: str = ""
    ) -> bool:
        """Create an irrigation schedule (e.g., run pump every 6 hours for 30 seconds)
        
        Args:
            gpio_number: GPIO pin number (pump)
            interval_hours: Hours between irrigation cycles
            duration_seconds: How long to run pump each cycle
            pwm_speed: Pump speed (0-100)
            description: Optional description
        """
        return self.add_schedule(
            gpio_number=gpio_number,
            schedule_type=ScheduleType.PWM_CYCLE.value,
            interval_seconds=interval_hours * 3600,
            duration_seconds=duration_seconds,
            pwm_duty_start=pwm_speed,
            description=description or f"Irrigate every {interval_hours}h for {duration_seconds}s at {pwm_speed}%"
        )
    
    def create_sunrise_sunset_schedule(
        self,
        gpio_number: int,
        sunrise_time: str,
        sunset_time: str,
        fade_minutes: int = 30,
        description: str = ""
    ) -> bool:
        """Create a sunrise/sunset fade schedule for lights
        
        Args:
            gpio_number: GPIO pin number (light)
            sunrise_time: Sunrise time in "HH:MM" format
            sunset_time: Sunset time in "HH:MM" format
            fade_minutes: Minutes to fade in/out
            description: Optional description
        """
        # Sunrise fade (0% to 100%)
        sunrise_success = self.add_schedule(
            gpio_number=gpio_number,
            schedule_type=ScheduleType.PWM_FADE.value,
            start_time=sunrise_time,
            pwm_duty_start=0,
            pwm_duty_end=100,
            pwm_fade_duration=fade_minutes * 60,
            description=f"Sunrise fade {sunrise_time}"
        )
        
        # Sunset fade (100% to 0%)
        sunset_success = self.add_schedule(
            gpio_number=gpio_number,
            schedule_type=ScheduleType.PWM_FADE.value,
            start_time=sunset_time,
            pwm_duty_start=100,
            pwm_duty_end=0,
            pwm_fade_duration=fade_minutes * 60,
            description=f"Sunset fade {sunset_time}"
        )
        
        return sunrise_success and sunset_success
    
    def print_schedules(self, gpio_number: Optional[int] = None):
        """Print all schedules or schedules for a specific pin"""
        config = self.load_config()
        if not config:
            print("❌ No configuration found")
            return
        
        print("\n" + "="*70)
        print("📅 GPIO Schedules")
        print("="*70)
        
        pins_to_show = [p for p in config.pins if p.gpio_number == gpio_number] if gpio_number else config.pins
        
        for pin in pins_to_show:
            if not hasattr(pin, 'schedules') or not pin.schedules:
                continue
            
            print(f"\n🔌 GPIO {pin.gpio_number} ({pin.name})")
            print(f"   Device: {pin.device_id}")
            
            for schedule in pin.schedules:
                status = "✅" if schedule.enabled else "⏸️"
                print(f"\n   {status} {schedule.schedule_id}")
                print(f"      Type: {schedule.schedule_type}")
                
                if schedule.description:
                    print(f"      Description: {schedule.description}")
                
                if schedule.start_time:
                    print(f"      Start: {schedule.start_time}")
                if schedule.end_time:
                    print(f"      End: {schedule.end_time}")
                
                if schedule.interval_seconds:
                    hours = schedule.interval_seconds / 3600
                    print(f"      Interval: {schedule.interval_seconds}s ({hours:.1f}h)")
                
                if schedule.duration_seconds:
                    print(f"      Duration: {schedule.duration_seconds}s")
                
                if schedule.pwm_duty_start is not None:
                    print(f"      PWM Duty: {schedule.pwm_duty_start}%", end="")
                    if schedule.pwm_duty_end is not None and schedule.pwm_duty_end != schedule.pwm_duty_start:
                        print(f" → {schedule.pwm_duty_end}%")
                    else:
                        print()
                
                if schedule.read_interval_seconds:
                    print(f"      Read Interval: {schedule.read_interval_seconds}s")
                    print(f"      Store Readings: {schedule.store_readings}")
                
                if schedule.last_run_at:
                    print(f"      Last Run: {schedule.last_run_at}")
        
        print("\n" + "="*70 + "\n")


# ============================================================================
# INTERACTIVE SETUP
# ============================================================================

def interactive_pin_assignment():
    """Interactive pin assignment wizard"""
    
    print("\n" + "="*70)
    print("🔌 GPIO Pin Assignment Wizard")
    print("="*70)
    
    manager = PinConfigManager()
    
    # Check existing config
    existing = manager.load_config()
    if existing:
        print(f"\n⚠️  Existing configuration found for {existing.module_id}")
        response = input("Load and modify existing? (y/n) ")
        if response.lower() != 'y':
            print("Creating new configuration...")
            module_id = input("Module ID (e.g., module-001): ").strip()
            manager.create_default_config(module_id=module_id)
    else:
        module_id = input("Module ID (e.g., module-001): ").strip()
        manager.create_default_config(module_id=module_id)
    
    print("\n📝 Available devices:")
    print("  1. Pump (irrigation)")
    print("  2. Light (LED strip)")
    print("  3. Motor (harvest belt)")
    print("  4. Sensor DHT22 (temperature/humidity)")
    print("  5. Sensor Water Level")
    print("  6. Custom device")
    
    while True:
        print("\n" + "-"*70)
        choice = input("Assign a pin? (1-6, or 'done' to finish): ").strip().lower()
        
        if choice == 'done':
            break
        
        if choice == '1':
            gpio = int(input("GPIO number for pump (default 17): ") or "17")
            manager.assign_pin_to_device(
                gpio_number=gpio,
                device_type="pump",
                device_id="pump-001",
                name="Irrigation Pump",
                mode="PWM",
                pwm_frequency=1000,
                config={"speed_min": 0, "speed_max": 100}
            )
        
        elif choice == '2':
            gpio = int(input("GPIO number for light (default 18): ") or "18")
            manager.assign_pin_to_device(
                gpio_number=gpio,
                device_type="light",
                device_id="light-001",
                name="LED Strip",
                mode="PWM",
                pwm_frequency=1000,
                config={"intensity_min": 0, "intensity_max": 100}
            )
        
        elif choice == '3':
            tray = int(input("Tray number (1-6): "))
            pwm_gpio = int(input(f"Motor {tray} PWM GPIO: "))
            dir_gpio = int(input(f"Motor {tray} Direction GPIO: "))
            
            manager.assign_pin_to_device(
                gpio_number=pwm_gpio,
                device_type="motor",
                device_id=f"motor-{tray}-pwm",
                name=f"Tray {tray} Motor PWM",
                mode="PWM",
                pwm_frequency=1000,
                config={"tray_id": tray}
            )
            
            manager.assign_pin_to_device(
                gpio_number=dir_gpio,
                device_type="motor",
                device_id=f"motor-{tray}-dir",
                name=f"Tray {tray} Motor Direction",
                mode="OUTPUT",
                config={"tray_id": tray}
            )
        
        elif choice == '4':
            gpio = int(input("DHT22 GPIO (default 4): ") or "4")
            manager.assign_pin_to_device(
                gpio_number=gpio,
                device_type="sensor_dht",
                device_id="sensor-dht22",
                name="DHT22 (Temp/Humidity)",
                mode="SENSOR",
                config={"sensor_type": "DHT22"}
            )
        
        elif choice == '5':
            gpio = int(input("Water level sensor GPIO (default 27): ") or "27")
            manager.assign_pin_to_device(
                gpio_number=gpio,
                device_type="sensor_water",
                device_id="sensor-water",
                name="Water Level Sensor",
                mode="INPUT",
                config={"sensor_type": "water_level"}
            )
        
        elif choice == '6':
            device_type = input("Device type (e.g., relay, custom): ").strip()
            device_id = input("Device ID (e.g., relay-001): ").strip()
            name = input("Device name (e.g., Aux Relay): ").strip()
            gpio = int(input("GPIO number: "))
            mode = input("Mode (INPUT/OUTPUT/PWM, default OUTPUT): ").strip() or "OUTPUT"
            
            manager.assign_pin_to_device(
                gpio_number=gpio,
                device_type=device_type,
                device_id=device_id,
                name=name,
                mode=mode
            )
    
    manager.print_config()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "setup":
            interactive_pin_assignment()
        elif sys.argv[1] == "load":
            manager = PinConfigManager()
            manager.print_config()
    else:
        manager = PinConfigManager()
        manager.print_config()
