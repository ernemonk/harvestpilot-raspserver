"""Device Management - Registration, Discovery, and Status"""

import logging
import json
import uuid
import os
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Optional
from firebase_admin import firestore
from .. import config

logger = logging.getLogger(__name__)


class DeviceManager:
    """Manage device registration, discovery, and status tracking using hardware_serial"""
    
    def __init__(self, hardware_serial: str = None, device_id: str = None):
        """
        Initialize device manager
        
        Args:
            hardware_serial: Hardware serial (primary identifier, immutable)
            device_id: Custom device ID (human-readable alias)
        """
        self.hardware_serial = hardware_serial or config.HARDWARE_SERIAL
        self.device_id = device_id or config.DEVICE_ID
        self.firestore_db = firestore.client()
        self.device_info = {}
        
        logger.info(f"Device Manager initialized (hardware_serial: {self.hardware_serial}, device_id: {self.device_id})")
    
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
        Register device in Firestore using hardware_serial as primary key
        
        Args:
            device_info: Optional device metadata
        
        Returns:
            Device registration data
        """
        try:
            logger.info("[DEVICE REGISTRATION] 🔧 Starting device registration process...")
            
            # Use hardware_serial from config (already has smart fallback logic)
            logger.debug("[DEVICE REGISTRATION] Reading device identifiers...")
            hardware_serial = self.hardware_serial  # From config: Pi serial → .env HARDWARE_SERIAL → DEVICE_ID → hostname
            pi_mac = self._get_pi_mac()  # Try to get MAC if available
            logger.info(f"[DEVICE REGISTRATION] 📱 Hardware Serial: {hardware_serial}, Mac: {pi_mac}")
            
            registration_data = {
                # PRIMARY KEY: Hardware Serial (immutable, tamper-proof)
                # Fallback chain: Pi /proc/cpuinfo → .env HARDWARE_SERIAL → DEVICE_ID → hostname
                "hardware_serial": hardware_serial,
                "mac_address": pi_mac,
                
                # HUMAN-READABLE ALIAS
                "device_id": self.device_id,
                "config_device_id": config.DEVICE_ID,
                
                # Device Mapping (links all identifiers)
                "device_mapping": {
                    "hardware_serial": hardware_serial,
                    "hardware_mac": pi_mac,
                    "device_id": self.device_id,
                    "config_id": config.DEVICE_ID,
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
                    "serial": hardware_serial,
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
            
            # Write to Firestore using hardware_serial as primary key
            logger.info(f"[DEVICE REGISTRATION] 📝 Writing registration to: devices/{hardware_serial}")
            self.firestore_db.collection("devices").document(hardware_serial).set(registration_data, merge=True)
            logger.info(f"[DEVICE REGISTRATION] ✅ Successfully registered at hardware_serial key")
            
            self.device_info = registration_data
            
            logger.info(f"[DEVICE REGISTRATION] ✅ DEVICE REGISTRATION COMPLETE")
            logger.info(f"[DEVICE REGISTRATION] Device Identifiers:")
            logger.info(f"[DEVICE REGISTRATION]   - Primary Key (hardware_serial): {hardware_serial}")
            logger.info(f"[DEVICE REGISTRATION]   - Human-readable alias (device_id): {self.device_id}")
            logger.info(f"[DEVICE REGISTRATION]   - Config ID: {config.DEVICE_ID}")
            
            return registration_data
        
        except Exception as e:
            logger.error(f"[DEVICE REGISTRATION] ❌ Device registration FAILED: {e}", exc_info=True)
            raise
    
    async def update_status(self, status: str = "online", status_data: Dict[str, Any] = None):
        """
        Update device status in Firestore using hardware_serial
        
        Args:
            status: Device status (online|offline|error)
            status_data: Additional status information
        """
        try:
            logger.debug(f"[DEVICE STATUS] Updating device status to: {status}")
            
            update_data = {
                "status": status,
                "last_seen": datetime.now().isoformat(),
                "device_id": self.device_id,
                "hardware_serial": self.hardware_serial,
            }
            
            if status_data:
                update_data.update(status_data)
            
            # Update in Firestore using hardware_serial as key
            logger.debug(f"[DEVICE STATUS] Writing to: devices/{self.hardware_serial}")
            self.firestore_db.collection("devices").document(self.hardware_serial).set(update_data, merge=True)
            
            logger.info(f"[DEVICE STATUS] ✓ Device status updated: {status}")
        
        except Exception as e:
            logger.error(f"[DEVICE STATUS] ❌ Error updating device status: {e}", exc_info=True)
    
    async def publish_telemetry(self, telemetry: Dict[str, Any]):
        """
        Publish device telemetry data to Firestore
        
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
                "device_id": self.device_id,
                "hardware_serial": self.hardware_serial,
                "timestamp": datetime.now().isoformat(),
            }
            
            # Publish to Firestore using hardware_serial as key
            self.firestore_db.collection("devices").document(self.hardware_serial).collection("telemetry").add(telemetry_data)
        
        except Exception as e:
            logger.error(f"Error publishing telemetry: {e}", exc_info=True)
    
    async def get_device_info(self) -> Dict[str, Any]:
        """Get device information from Firestore using hardware_serial"""
        try:
            # Get document from Firestore using hardware_serial
            doc = self.firestore_db.collection("devices").document(self.hardware_serial).get()
            if data.val():
                return data.val()
            
            # Fallback to Firebase ID if not found
            if self.device_id != config.DEVICE_ID:
                data = self.db.child(f"devices/{self.device_id}").get()
                return data.val() or {}
            
            return {}
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
            
            # Register at config device ID (primary path)
            self.db.child(f"devices/{config.DEVICE_ID}/pins/{pin_number}").set(pin_data)
            
            # Also register at Firebase ID if different
            if self.device_id != config.DEVICE_ID:
                self.db.child(f"devices/{self.device_id}/pins/{pin_number}").set(pin_data)
            
            logger.info(f"Pin registered: GPIO{pin_number} ({pin_name})")
        
        except Exception as e:
            logger.error(f"Error registering pin: {e}")
    
    async def get_pins_config(self) -> Dict[int, Dict[str, Any]]:
        """Get all registered pins configuration"""
        try:
            # Try config device ID first (primary path)
            data = self.db.child(f"devices/{config.DEVICE_ID}/pins").get()
            if data.val():
                return data.val()
            
            # Fallback to Firebase ID if not found
            if self.device_id != config.DEVICE_ID:
                data = self.db.child(f"devices/{self.device_id}/pins").get()
                return data.val() or {}
            
            return {}
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
            
            # Update at config device ID (primary path)
            self.db.child(f"devices/{config.DEVICE_ID}/pins/{pin_number}/state").set(state_data)
            
            # Also update at Firebase ID if different
            if self.device_id != config.DEVICE_ID:
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
            # Record at config device ID (primary path)
            self.db.child(f"devices/{config.DEVICE_ID}/errors/{error_id}").set(error_data)
            
            # Also record at Firebase ID if different
            if self.device_id != config.DEVICE_ID:
                self.db.child(f"devices/{self.device_id}/errors/{error_id}").set(error_data)
            
            logger.info(f"Error recorded: {error_type}")
        
        except Exception as e:
            logger.error(f"Error recording error: {e}")
    
    async def get_device_logs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent device logs"""
        try:
            # Try config device ID first (primary path)
            data = self.db.child(f"devices/{config.DEVICE_ID}/logs").limit_to_last(limit).get()
            
            if data.val():
                return [log for log in data.val().values() if isinstance(log, dict)]
            
            # Fallback to Firebase ID if not found
            if self.device_id != config.DEVICE_ID:
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
