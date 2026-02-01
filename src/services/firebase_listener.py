"""Firestore Listeners for Device Control"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Callable, Dict, Any, Optional
import firebase_admin
from firebase_admin import firestore
from .. import config

logger = logging.getLogger(__name__)


class FirebaseDeviceListener:
    """Listen for Firebase commands and manage device control using hardware_serial"""
    
    def __init__(self, hardware_serial: str, device_id: str = None, gpio_controller=None, controllers_map: Dict[str, Any] = None):
        """
        Initialize Firebase listener
        
        Args:
            hardware_serial: Hardware serial (primary device identifier)
            device_id: Device ID alias (human-readable, optional)
            gpio_controller: GPIO manager instance
            controllers_map: Dict mapping controller names to controller instances
                {
                    "pump": IrrigationController,
                    "lights": LightingController,
                    "harvest": HarvestController,
                    "sensors": SensorController
                }
        """
        self.hardware_serial = hardware_serial
        self.device_id = device_id or config.DEVICE_ID
        self.gpio_controller = gpio_controller
        self.controllers_map = controllers_map or {}
        self.firestore_db = firestore.client()
        self.listeners = []
        self.command_handlers = {}
        self._setup_handlers()
        
        logger.info(f"Firebase listener initialized (hardware_serial: {hardware_serial}, device_id: {device_id})")
    
    def _setup_handlers(self):
        """Setup command handlers"""
        self.command_handlers = {
            "pin_control": self._handle_pin_control,
            "pwm_control": self._handle_pwm_control,
            "pump": self._handle_pump_command,
            "lights": self._handle_lights_command,
            "harvest": self._handle_harvest_command,
            "device_config": self._handle_device_config,
            "sensor_read": self._handle_sensor_read,
        }
    
    async def start_listening(self):
        """Start listening for Firebase commands"""
        try:
            # Listen for device commands
            await self._listen_for_commands()
            
            # Listen for device registration requests
            await self._listen_for_registration()
            
            logger.info(f"Firebase listeners started for device: {self.device_id}")
        except Exception as e:
            logger.error(f"Error starting Firebase listeners: {e}", exc_info=True)
            raise
    
    async def _listen_for_commands(self):
        """Listen for control commands in Firebase"""
        try:
            # Listen on config device ID (primary path for webapp commands)
            commands_ref = self.db.child(f"devices/{config.DEVICE_ID}/commands")
            
            def commands_callback(message):
                """Handle incoming commands"""
                logger.debug(f"[FIREBASE LISTENER] Raw message received: {message}")
                if message.data:
                    logger.info(f"[FIREBASE LISTENER] 🔔 NEW COMMAND DETECTED from Firebase: {message.data}")
                    asyncio.create_task(self._process_command(message.data))
                else:
                    logger.debug("[FIREBASE LISTENER] Message has no data payload")
            
            # Set up stream listener
            commands_ref.listen(commands_callback)
            logger.info(f"[FIREBASE LISTENER] ✅ Command listener STARTED for {config.DEVICE_ID}")
            logger.info(f"[FIREBASE LISTENER] 👂 Listening on path: devices/{config.DEVICE_ID}/commands")
            
            # Also listen on generated Firebase ID if different
            if self.device_id != config.DEVICE_ID:
                commands_ref_fb = self.db.child(f"devices/{self.device_id}/commands")
                commands_ref_fb.listen(commands_callback)
                logger.info(f"[FIREBASE LISTENER] ✅ Command listener also STARTED for {self.device_id}")
                logger.info(f"[FIREBASE LISTENER] 👂 Listening on path: devices/{self.device_id}/commands")
            
        except Exception as e:
            logger.error(f"[FIREBASE LISTENER] ❌ Error setting up command listener: {e}", exc_info=True)
    
    async def _listen_for_registration(self):
        """Listen for device registration requests"""
        try:
            # Register device on startup
            await self._register_device()
            
            # Listen for re-registration requests
            reg_ref = self.db.child("registration_requests").child(self.device_id)
            
            def reg_callback(message):
                """Handle registration requests"""
                if message.data:
                    asyncio.create_task(self._register_device())
            
            reg_ref.listen(reg_callback)
            logger.info(f"Registration listener started")
            
        except Exception as e:
            logger.error(f"Error setting up registration listener: {e}", exc_info=True)
    
    async def _register_device(self):
        """Register device with Firebase"""
        try:
            device_data = {
                "device_id": self.device_id,
                "config_device_id": config.DEVICE_ID,
                "status": "online",
                "registered_at": datetime.now().isoformat(),
                "last_seen": datetime.now().isoformat(),
                "platform": config.HARDWARE_PLATFORM,
                "capabilities": {
                    "pump_control": True,
                    "light_control": True,
                    "motor_control": True,
                    "pwm_support": True,
                    "sensor_read": True,
                },
                "gpio_config": self._get_gpio_config(),
            }
            
            # Write device info to Firebase using config DEVICE_ID (primary lookup key)
            # This allows webapp to find device by "raspserver-001" instead of "hp-XXXXXXXX"
            self.db.child(f"devices/{config.DEVICE_ID}").update(device_data)
            logger.info(f"Device registered with ID: {config.DEVICE_ID}")
            
            # Also register with generated Firebase ID for redundancy
            if self.device_id != config.DEVICE_ID:
                self.db.child(f"devices/{self.device_id}").update(device_data)
                logger.info(f"Device also registered with Firebase ID: {self.device_id}")
            
            return device_data
            
        except Exception as e:
            logger.error(f"Error registering device: {e}", exc_info=True)
            raise
    
    async def _process_command(self, command_data: Dict[str, Any]):
        """Process incoming Firebase command"""
        try:
            if not isinstance(command_data, dict):
                logger.warning(f"[COMMAND PROCESSOR] ❌ Invalid command format (not dict): {command_data}")
                return
            
            command_type = command_data.get("type")
            command_id = command_data.get("id", "unknown")
            
            if not command_type:
                logger.warning("[COMMAND PROCESSOR] ❌ Command missing 'type' field")
                return
            
            logger.info(f"[COMMAND PROCESSOR] 🚀 Processing command: {command_type} (ID: {command_id})")
            logger.debug(f"[COMMAND PROCESSOR] Full command data: {command_data}")
            
            # Route to appropriate handler
            handler = self.command_handlers.get(command_type)
            if handler:
                logger.info(f"[COMMAND PROCESSOR] ✓ Handler found for type '{command_type}', executing...")
                result = await handler(command_data)
                logger.info(f"[COMMAND PROCESSOR] ✓ Handler completed successfully for '{command_type}'")
                logger.debug(f"[COMMAND PROCESSOR] Handler result: {result}")
                await self._send_response(command_id, command_type, "success", result)
            else:
                logger.warning(f"[COMMAND PROCESSOR] ❌ Unknown command type: {command_type}")
                logger.warning(f"[COMMAND PROCESSOR] Available handlers: {list(self.command_handlers.keys())}")
                await self._send_response(command_id, command_type, "error", 
                                        f"Unknown command type: {command_type}")
        
        except Exception as e:
            logger.error(f"[COMMAND PROCESSOR] ❌ Error processing command: {e}", exc_info=True)
            logger.error(f"[COMMAND PROCESSOR] Command data was: {command_data}")
            await self._send_response(command_data.get("id", "unknown"), 
                                    command_data.get("type", "unknown"),
                                    "error", str(e))
    
    async def _handle_pin_control(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle raw GPIO pin control (on/off)
        
        Command format:
        {
            "type": "pin_control",
            "pin": 17,
            "action": "on|off",
            "duration": 5  # optional, in seconds
        logger.debug(f"[PIN CONTROL] Validating command: pin={pin}, action={action}, duration={duration}")
        
        if not pin or action not in ["on", "off"]:
            raise ValueError("pin_control requires: pin (int) and action ('on'|'off')")
        
        logger.info(f"[PIN CONTROL] 🔌 GPIO{pin} control requested: {action.upper()}")
        
        if config.SIMULATE_HARDWARE:
            logger.info(f"[PIN CONTROL] 🎭 [SIMULATION MODE] GPIO{pin} -> {action.upper()}")
            return {"pin": pin, "action": action, "status": "simulated"}
        
        try:
            import RPi.GPIO as GPIO
            logger.debug(f"[PIN CONTROL] Setting GPIO mode to BCM")
            GPIO.setmode(GPIO.BCM)
            logger.debug(f"[PIN CONTROL] Setting GPIO{pin} as OUTPUT")
            GPIO.setup(pin, GPIO.OUT)
            
            if action == "on":
                logger.info(f"[PIN CONTROL] ⚡ Setting GPIO{pin} to HIGH (ON)")
                GPIO.output(pin, GPIO.HIGH)
            else:
                logger.info(f"[PIN CONTROL] ⚫ Setting GPIO{pin} to LOW (OFF)")
                GPIO.output(pin, GPIO.LOW)
            
            # If duration specified, schedule turn-off
            if duration and action == "on":
                logger.info(f"[PIN CONTROL] ⏱️  GPIO{pin} will auto-turn off in {duration}s")
                await asyncio.sleep(duration)
                logger.info(f"[PIN CONTROL] ⚫ Auto-turning off GPIO{pin} after {duration}s")
                GPIO.output(pin, GPIO.LOW)
                logger.info(f"[PIN CONTROL] ✓ GPIO{pin} auto-turned off successfully")
            
            logger.info(f"[PIN CONTROL] ✅ PIN CONTROL SUCCESS: GPIO{pin} -> {action.upper()}")
            return {
                "pin": pin,
                "action": action,
                "status": "success",
                "duration": duration
            }
        except Exception as e:
            logger.error(f"[PIN CONTROL] ❌ Pin control FAILED for GPIO{pin}: {e}", exc_info=True
                "action": action,
                "status": "success",
                "duration": duration
            }
        except Exception as e:
            logger.error(f"Pin control failed: {e}")
            raise
    
    async def _handle_pwm_control(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle PWM pin control (0-100%)
        
        Command format:
        {
            "type": "pwm_control",
            "pin": 17,
            "duty_cycle": 75,  # 0-100 %
            "frequency": 1000  # Hz (optional)
        }
        """
        pin = command.get("pin")
        duty_cycle = command.get("duty_cycle", 0)
        frequency = command.get("frequency", 1000)
        
        if not pin or not (0 <= duty_cycle <= 100):
            raise ValueError("pwm_control requires: pin (int) and duty_cycle (0-100)")
        
        logger.info(f"PWM control: GPIO{pin} -> {duty_cycle}% @ {frequency}Hz")
        
        if config.SIMULATE_HARDWARE:
            logger.info(f"[SIMULATION] GPIO{pin} PWM -> {duty_cycle}% @ {frequency}Hz")
            return {"pin": pin, "duty_cycle": duty_cycle, "frequency": frequency, "status": "simulated"}
        
        try:
            import RPi.GPIO as GPIO
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pin, GPIO.OUT)
            
            pwm = GPIO.PWM(pin, frequency)
            pwm.start(duty_cycle)
            
            return {
                "pin": pin,
                "duty_cycle": duty_cycle,
                "frequency": frequency,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"PWM control failed: {e}")
            raise
    
    async def _handle_pump_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle pump control
        
        Command format:
        {
            "type": "pump",
            "action": "start|stop|pulse",
            "speed": 75,  # 0-100 % (optional, default: 80)
            "duration": 30  # seconds (optional, for pulse/timed)
        }
        """
        action = command.get("action", "").lower()
        speed = command.get("speed", 80)
        duration = command.get("duration")
        
        if action not in ["start", "stop", "pulse"]:
            raise ValueError("pump action must be: start|stop|pulse")
        
        pump_controller = self.controllers_map.get("pump")
        if not pump_controller:
            raise RuntimeError("Pump controller not available")
        
        logger.info(f"Pump command: {action} (speed: {speed}%)")
        
        if action == "start":
            await pump_controller.start(speed=speed)
            return {"action": "start", "speed": speed, "status": "running"}
        
        elif action == "stop":
            await pump_controller.stop()
            return {"action": "stop", "status": "stopped"}
        
        elif action == "pulse":
            duration = duration or 5
            await pump_controller.start(duration=duration, speed=speed)
            await asyncio.sleep(duration)
            await pump_controller.stop()
            return {"action": "pulse", "speed": speed, "duration": duration, "status": "complete"}
    
    async def _handle_lights_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle lighting control
        
        Command format:
        {
            "type": "lights",
            "action": "on|off",
            "brightness": 80,  # 0-100 % (optional)
            "color_temp": 3000  # Kelvin (optional)
        }
        """
        action = command.get("action", "").lower()
        brightness = command.get("brightness", 100)
        
        if action not in ["on", "off"]:
            raise ValueError("lights action must be: on|off")
        
        lights_controller = self.controllers_map.get("lights")
        if not lights_controller:
            raise RuntimeError("Lights controller not available")
        
        logger.info(f"Lights command: {action} (brightness: {brightness}%)")
        
        if action == "on":
            await lights_controller.turn_on(brightness=brightness)
            return {"action": "on", "brightness": brightness, "status": "on"}
        else:
            await lights_controller.turn_off()
            return {"action": "off", "status": "off"}
    
    async def _handle_harvest_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle harvest belt control
        
        Command format:
        {
            "type": "harvest",
            "action": "start|stop|position",
            "belt_id": 1,  # 1-6
            "speed": 50,  # 0-100 % (optional)
            "duration": 10  # seconds (optional)
        }
        """
        action = command.get("action", "").lower()
        belt_id = command.get("belt_id")
        speed = command.get("speed", 50)
        duration = command.get("duration")
        
        if action not in ["start", "stop", "position"]:
            raise ValueError("harvest action must be: start|stop|position")
        
        harvest_controller = self.controllers_map.get("harvest")
        if not harvest_controller:
            raise RuntimeError("Harvest controller not available")
        
        logger.info(f"Harvest command: Belt {belt_id} -> {action} (speed: {speed}%)")
        
        if action == "start":
            await harvest_controller.start_belt(belt_id, speed=speed)
            return {"belt": belt_id, "action": "start", "speed": speed, "status": "running"}
        
        elif action == "stop":
            await harvest_controller.stop_belt(belt_id)
            return {"belt": belt_id, "action": "stop", "status": "stopped"}
        
        elif action == "position":
            position = command.get("position", "home")
            await harvest_controller.move_to_position(belt_id, position)
            return {"belt": belt_id, "action": "position", "target": position, "status": "moving"}
    
    async def _handle_device_config(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Handle device configuration updates
        
        Command format:
        {
            "type": "device_config",
            "config": {
                "auto_irrigation": true,
                "auto_lighting": true,
                "sensor_interval": 5
            }
        }
        """
        config_update = command.get("config", {})
        
        logger.info(f"Device config update: {config_update}")
        
        # Update config module (or use config loader)
        for key, value in config_update.items():
            if hasattr(config, key):
                setattr(config, key, value)
                logger.info(f"Updated config: {key} = {value}")
        
        return {"status": "updated", "config": config_update}
    
    async def _handle_sensor_read(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Read sensor values on demand
        
        Command format:
        {
            "type": "sensor_read",
            "sensor": "temperature|humidity|soil_moisture|water_level"
        }
        """
        sensor_type = command.get("sensor", "").lower()
        
        sensors_controller = self.controllers_map.get("sensors")
        if not sensors_controller:
            raise RuntimeError("Sensors controller not available")
        
        logger.info(f"Reading sensor: {sensor_type}")
        
        # Get sensor reading
        reading = await sensors_controller.read_sensor(sensor_type)
        
        return {
            "sensor": sensor_type,
            "value": reading.get("value"),
            "unit": reading.get("unit"),
            "timestamp": datetime.now().isoformat()
        }
    logger.info(f"[RESPONSE] 📤 Sending response for command {command_id} (type: {command_type}, status: {status})")
            logger.debug(f"[RESPONSE] Response payload: {response}")
            
            # Send response to config device ID (where webapp expects it)
            logger.debug(f"[RESPONSE] Writing to: devices/{config.DEVICE_ID}/responses/{command_id}")
            self.db.child(f"devices/{config.DEVICE_ID}/responses/{command_id}").set(response)
            logger.info(f"[RESPONSE] ✅ Response written to config device ID path")
            
            # Also send to Firebase ID if different
            if self.device_id != config.DEVICE_ID:
                logger.debug(f"[RESPONSE] Writing to: devices/{self.device_id}/responses/{command_id}")
                self.db.child(f"devices/{self.device_id}/responses/{command_id}").set(response)
                logger.info(f"[RESPONSE] ✅ Response also written to Firebase ID path")
            
            logger.info(f"[RESPONSE] ✅ RESPONSE COMPLETE: {command_id} -> {status}")
            
        except Exception as e:
            logger.error(f"[RESPONSE] ❌ Error sending response for {command_id}: {e}", exc_info=True)
            logger.error(f"[RESPONSE] Response was: {response}"
                "device_id": self.device_id,
                "config_device_id": config.DEVICE_ID
            }
            
            # Send response to config device ID (where webapp expects it)
            self.db.child(f"devices/{config.DEVICE_ID}/responses/{command_id}").set(response)
            
            # Also send to Firebase ID if different
            if self.device_id != config.DEVICE_ID:
                self.db.child(f"devices/{self.device_id}/responses/{command_id}").set(response)
            
            logger.info(f"Response sent for command {command_id}: {status}")
            
        except Exception as e:
            logger.error(f"Error sending response: {e}", exc_info=True)
    
    def _get_gpio_config(self) -> Dict[str, Any]:
        """Get current GPIO configuration"""
        return {
            "pump_pin": config.PUMP_PWM_PIN,
            "light_pin": config.LED_PWM_PIN,
            "dht_pin": config.SENSOR_DHT22_PIN,
            "water_level_pin": config.SENSOR_WATER_LEVEL_PIN,
            "motor_pins": config.MOTOR_PINS,
        }
    
    async def publish_status(self, status_data: Dict[str, Any]):
        """Publish device status to Firebase"""
        try:
            status_data["timestamp"] = datetime.now().isoformat()
            # Publish to both config device ID and Firebase ID
            self.db.child(f"devices/{config.DEVICE_ID}/status").update(status_data)
            
            if self.device_id != config.DEVICE_ID:
                self.db.child(f"devices/{self.device_id}/status").update(status_data)
        except Exception as e:
            logger.error(f"Error publishing status: {e}")
    
    async def stop(self):
        """Stop all listeners"""
        try:
            logger.info("Stopping Firebase listeners")
            # Listeners will stop when app closes
        except Exception as e:
            logger.error(f"Error stopping listeners: {e}")
