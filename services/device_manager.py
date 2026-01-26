"""Device Management - Registration, Discovery, and Status"""

import logging
import json
import uuid
import os
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Optional
from firebase_admin import db
import config

logger = logging.getLogger(__name__)


class DeviceManager:
    """Manage device registration, discovery, and status tracking"""
    
    def __init__(self, device_id: str = None):
        """
        Initialize device manager
        
        Args:
            device_id: Custom device ID (optional, auto-generated if not provided)
        """
        self.device_id = device_id or self._generate_device_id()
        self.db = db.reference()
        self.device_info = {}
        
        logger.info(f"Device Manager initialized with ID: {self.device_id}")
    
    def _generate_device_id(self) -> str:
        """Generate unique device ID with 'hp-' prefix"""
        unique_suffix = str(uuid.uuid4())[:8].upper()
        return f"hp-{unique_suffix}"
    
    def _get_pi_serial(self) -> str:
        """Get Raspberry Pi serial number from /proc/cpuinfo"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        return line.split(':')[1].strip()
        except Exception as e:
            logger.warning(f"Could not read Pi serial: {e}")
        return "unknown"
    
    def _get_pi_mac(self) -> str:
        """Get Raspberry Pi MAC address"""
        try:
            # Try to get eth0 MAC
            mac = subprocess.check_output(
                "cat /sys/class/net/eth0/address 2>/dev/null || cat /sys/class/net/wlan0/address",
                shell=True
            ).decode().strip()
            return mac
        except Exception as e:
            logger.warning(f"Could not read Pi MAC: {e}")
        return "unknown"
    
    async def register_device(self, device_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Register device in Firebase
        
        Args:
            device_info: Optional device metadata
        
        Returns:
            Device registration data
        """
        try:
            # Get Pi hardware identifiers
            pi_serial = self._get_pi_serial()
            pi_mac = self._get_pi_mac()
            
            registration_data = {
                # TIER 1: Hardware IDs (Raspberry Pi unique identifiers)
                "hardware_serial": pi_serial,
                "mac_address": pi_mac,
                
                # TIER 2: Config Device ID
                "config_device_id": config.DEVICE_ID,
                
                # TIER 3: Firebase Device ID
                "device_id": self.device_id,
                
                # Device Mapping (links all three)
                "device_mapping": {
                    "hardware_serial": pi_serial,
                    "hardware_mac": pi_mac,
                    "config_id": config.DEVICE_ID,
                    "firebase_id": self.device_id,
                    "linked_at": datetime.now().isoformat()
                },
                
                # Status and metadata
                "status": "online",
                "registered_at": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
                "platform": config.HARDWARE_PLATFORM,
                "simulate_hardware": config.SIMULATE_HARDWARE,
                "capabilities": {
                    "pump_control": True,
                    "light_control": True,
                    "motor_control": True,
                    "pwm_support": True,
                    "sensor_read": True,
                    "scheduling": True,
                },
                "hardware": {
                    "model": "Raspberry Pi 4B",
                    "serial": pi_serial,
                    "mac": pi_mac,
                    "gpio_pins": {
                        "pump_pwm": config.PUMP_PWM_PIN,
                        "light_pwm": config.LED_PWM_PIN,
                        "dht_sensor": config.SENSOR_DHT22_PIN,
                        "water_level": config.SENSOR_WATER_LEVEL_PIN,
                        "soil_moisture": config.SENSOR_SOIL_MOISTURE_PIN,
                    },
                    "pwm_frequency": {
                        "pump": config.PUMP_PWM_FREQUENCY,
                        "light": config.LED_PWM_FREQUENCY,
                        "motor": config.MOTOR_PWM_FREQUENCY,
                    }
                },
                "metadata": device_info or {}
            }
            
            # Write to Firebase
            self.db.child(f"devices/{self.device_id}").set(registration_data)
            self.device_info = registration_data
            
            logger.info(f"Device registered successfully: {self.device_id}")
            return registration_data
        
        except Exception as e:
            logger.error(f"Device registration failed: {e}", exc_info=True)
            raise
    
    async def update_status(self, status: str = "online", status_data: Dict[str, Any] = None):
        """
        Update device status
        
        Args:
            status: Device status (online|offline|error)
            status_data: Additional status information
        """
        try:
            update_data = {
                "status": status,
                "last_seen": datetime.now().isoformat(),
            }
            
            if status_data:
                update_data.update(status_data)
            
            self.db.child(f"devices/{self.device_id}").update(update_data)
            logger.info(f"Device status updated: {status}")
        
        except Exception as e:
            logger.error(f"Error updating device status: {e}", exc_info=True)
    
    async def publish_telemetry(self, telemetry: Dict[str, Any]):
        """
        Publish device telemetry data
        
        Telemetry structure:
        {
            "sensors": {
                "temperature": 72.5,
                "humidity": 65.0,
                "soil_moisture": 75.0,
                "water_level": 80.0
            },
            "actuators": {
                "pump": {"running": true, "speed": 80},
                "lights": {"on": true, "brightness": 100},
                "motors": [...]
            },
            "system": {
                "cpu_temp": 45.2,
                "memory_usage": 45.6,
                "uptime_seconds": 86400
            }
        }
        """
        try:
            telemetry_data = {
                **telemetry,
                "timestamp": datetime.now().isoformat(),
            }
            
            self.db.child(f"devices/{self.device_id}/telemetry").set(telemetry_data)
        
        except Exception as e:
            logger.error(f"Error publishing telemetry: {e}", exc_info=True)
    
    async def get_device_info(self) -> Dict[str, Any]:
        """Get device information from Firebase"""
        try:
            data = self.db.child(f"devices/{self.device_id}").get()
            return data.val() or {}
        except Exception as e:
            logger.error(f"Error getting device info: {e}")
            return {}
    
    async def list_all_devices(self) -> List[Dict[str, Any]]:
        """List all registered devices"""
        try:
            data = self.db.child("devices").get()
            devices = []
            
            if data.val():
                for device_id, device_data in data.val().items():
                    devices.append({
                        "device_id": device_id,
                        **device_data
                    })
            
            return devices
        
        except Exception as e:
            logger.error(f"Error listing devices: {e}")
            return []
    
    async def register_pin(self, pin_number: int, pin_name: str, 
                          pin_type: str, purpose: str):
        """
        Register a GPIO pin for tracking
        
        Args:
            pin_number: GPIO pin number
            pin_name: Pin name/label
            pin_type: Type (input|output|pwm)
            purpose: What the pin controls (pump|light|sensor|etc)
        """
        try:
            pin_data = {
                "pin": pin_number,
                "name": pin_name,
                "type": pin_type,
                "purpose": purpose,
                "registered_at": datetime.now().isoformat(),
            }
            
            self.db.child(f"devices/{self.device_id}/pins/{pin_number}").set(pin_data)
            logger.info(f"Pin registered: GPIO{pin_number} ({pin_name})")
        
        except Exception as e:
            logger.error(f"Error registering pin: {e}")
    
    async def get_pins_config(self) -> Dict[int, Dict[str, Any]]:
        """Get all registered pins configuration"""
        try:
            data = self.db.child(f"devices/{self.device_id}/pins").get()
            return data.val() or {}
        except Exception as e:
            logger.error(f"Error getting pins config: {e}")
            return {}
    
    async def set_pin_state(self, pin_number: int, state: Dict[str, Any]):
        """
        Record pin state change
        
        State can include:
        - value: High/Low or PWM duty cycle (0-100)
        - mode: Digital/PWM
        - timestamp: When changed
        """
        try:
            state_data = {
                **state,
                "timestamp": datetime.now().isoformat(),
            }
            
            self.db.child(f"devices/{self.device_id}/pins/{pin_number}/state").set(state_data)
        
        except Exception as e:
            logger.error(f"Error setting pin state: {e}")
    
    async def record_error(self, error_type: str, error_message: str, 
                          context: Dict[str, Any] = None):
        """Record device error for debugging"""
        try:
            error_data = {
                "type": error_type,
                "message": error_message,
                "timestamp": datetime.now().isoformat(),
                "context": context or {}
            }
            
            error_id = str(uuid.uuid4())[:8]
            self.db.child(f"devices/{self.device_id}/errors/{error_id}").set(error_data)
            
            logger.info(f"Error recorded: {error_type}")
        
        except Exception as e:
            logger.error(f"Error recording error: {e}")
    
    async def get_device_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent device logs"""
        try:
            data = self.db.child(f"devices/{self.device_id}/logs").limit_to_last(limit).get()
            logs = []
            
            if data.val():
                for log_id, log_data in data.val().items():
                    logs.append({
                        "log_id": log_id,
                        **log_data
                    })
            
            return logs
        
        except Exception as e:
            logger.error(f"Error getting device logs: {e}")
            return []
