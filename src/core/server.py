"""Core RaspServer - main application server"""

import asyncio
import logging
from datetime import datetime
from ..controllers.irrigation import IrrigationController
from ..controllers.lighting import LightingController
from ..controllers.harvest import HarvestController
from ..services import FirebaseService, SensorService, AutomationService, DatabaseService
from ..services.diagnostics import DiagnosticsService
from ..services.config_manager import ConfigManager
from ..utils.gpio_manager import cleanup_gpio
from .. import config

# Import GPIO Actuator Controller for real-time Firestore control
from ..services.gpio_actuator_controller import GPIOActuatorController
from ..services.log_server import start_log_server, stop_log_server

logger = logging.getLogger(__name__)


class RaspServer:
    """Main Raspberry Pi server orchestrating all components"""
    
    def __init__(self):
        logger.info("Initializing HarvestPilot RaspServer...")
        
        # Initialize diagnostics (tracks metrics)
        self.diagnostics = DiagnosticsService()
        
        # Initialize database (local storage)
        self.database = DatabaseService()
        
        # Initialize controllers (low-level hardware)
        self.irrigation = IrrigationController()
        self.lighting = LightingController()
        self.harvest = HarvestController()
        
        # Initialize services (high-level logic)
        self.firebase = FirebaseService()
        self.sensors = SensorService(
            firestore_db=None,  # Will get Firestore after Firebase init
            hardware_serial=config.HARDWARE_SERIAL
        )
        self.automation = AutomationService(self.irrigation, self.lighting)
        
        # Initialize configuration manager (dynamic intervals)
        # Create LocalDatabase instance for ConfigManager persistence
        from ..storage.local_db import LocalDatabase
        local_db = LocalDatabase()
        self.config_manager = ConfigManager(
            hardware_serial=config.HARDWARE_SERIAL,
            database=local_db  # Pass LocalDatabase instance
        )
        
        # Initialize GPIO Actuator Controller for real-time Firestore control
        # Use hardware_serial as primary identifier for secure device authentication
        # Pass config_manager so GPIO controller uses YOUR Firestore-defined intervals
        self.gpio_actuator = GPIOActuatorController(
            hardware_serial=config.HARDWARE_SERIAL,
            device_id=config.DEVICE_ID,
            config_manager=self.config_manager
        )
        
        # Register command handlers
        self._register_command_handlers()
        
        self.running = False
        logger.info(f"RaspServer initialized successfully (hardware_serial: {config.HARDWARE_SERIAL}, device_id: {config.DEVICE_ID})")
    
    def _register_command_handlers(self):
        """Register all command handlers with Firebase service"""
        self.firebase.register_command_handler("irrigation", "start", self._handle_irrigation_start)
        self.firebase.register_command_handler("irrigation", "stop", self._handle_irrigation_stop)
        self.firebase.register_command_handler("lighting", "on", self._handle_lighting_on)
        self.firebase.register_command_handler("lighting", "off", self._handle_lighting_off)
        self.firebase.register_command_handler("harvest", "start", self._handle_harvest_start)
        self.firebase.register_command_handler("harvest", "stop", self._handle_harvest_stop)
    
    async def start(self):
        """Start the server and all services"""
        try:
            logger.info("Starting HarvestPilot RaspServer...")
            
            # Connect to Firebase
            self.firebase.connect()
            
            # After Firebase connects, pass Firestore DB to sensor service and config manager
            # This allows sensors to read their config from device document
            # and config_manager to listen for interval changes
            try:
                from firebase_admin import firestore
                firestore_db = firestore.client()
                self.sensors = SensorService(
                    firestore_db=firestore_db,
                    hardware_serial=config.HARDWARE_SERIAL
                )
                self.config_manager.set_firestore_client(firestore_db)
                logger.info("Sensor service and ConfigManager updated with Firestore DB")
            except Exception as e:
                logger.warning(f"Could not update services with Firestore: {e}")
            
            # Initialize configuration (load intervals from Firestore/cache/defaults)
            await self.config_manager.initialize()
            logger.info(f"Configuration loaded: {self.config_manager.get_all_intervals()}")
            
            # Start listening for configuration changes
            self.config_manager.listen_for_changes()
            
            # Start log server (HTTP endpoint for remote log viewing)
            start_log_server()
            
            # Connect GPIO Actuator Controller (real-time Firestore listener)
            self.gpio_actuator.connect()
            logger.info("GPIO Actuator Controller connected - listening to Firestore for GPIO commands")
            
            # Set Firebase status in diagnostics
            self.diagnostics.set_firebase_status(True)
            
            # Start all background tasks
            self.running = True
            
            tasks = []
            # Heartbeat is now handled inside gpio_actuator's hardware sync loop
            # (merged into the same Firestore write to save ~2880 writes/day)
            
            if config.AUTO_IRRIGATION_ENABLED or config.AUTO_LIGHTING_ENABLED:
                tasks.append(self.automation.run_automation_loop())
            
            # Keep server alive — all real work happens in daemon threads
            # (GPIO listener, hardware sync, schedule checker, config listener)
            tasks.append(self._keep_alive())
            
            # Run all tasks concurrently
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"Error starting RaspServer: {e}", exc_info=True)
            raise
    
    async def stop(self):
        """Stop server and cleanup"""
        logger.info("Stopping HarvestPilot RaspServer...")
        
        self.running = False
        
        # Stop listening for config changes
        self.config_manager.stop_listening()
        
        try:
            # Stop all hardware
            await self.irrigation.stop()
            await self.lighting.turn_off()
            for tray_id in range(1, 7):
                await self.harvest.stop_belt(tray_id)
            
            # Disconnect Firebase
            self.firebase.disconnect()
            
            # Disconnect GPIO Actuator Controller
            self.gpio_actuator.disconnect()
            
            # Close database
            self.database.close()
            
            # Stop log server
            stop_log_server()
            
            # Cleanup GPIO
            cleanup_gpio()
            
            logger.info("RaspServer stopped successfully")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def _keep_alive(self):
        """Keep the asyncio event loop alive while daemon threads do the real work."""
        logger.info("🎯 Server running — all listeners active")
        while self.running:
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
    
    async def _emergency_stop(self):
        """Stop all operations immediately"""
        logger.warning("EMERGENCY STOP ACTIVATED")
        
        try:
            await self.irrigation.stop()
            await self.lighting.turn_off()
            for tray_id in range(1, 7):
                await self.harvest.stop_belt(tray_id)
            
            self.firebase.publish_status_update({
                "emergencyStop": True,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error during emergency stop: {e}")
    
    # ============ Command Handlers ============
    
    def _handle_irrigation_start(self, params: dict):
        """Handle irrigation start command"""
        try:
            duration = params.get("duration", config.IRRIGATION_CYCLE_DURATION)
            speed = params.get("speed", config.PUMP_DEFAULT_SPEED)
            
            # Log operation locally (non-blocking)
            asyncio.create_task(self.database.async_log_operation(
                device_type="irrigation",
                action="start",
                params={"duration": duration, "speed": speed},
                status="started"
            ))
            
            logger.info(f"Irrigation started: duration={duration}s, speed={speed}%")
        except Exception as e:
            logger.error(f"Error starting irrigation: {e}")
    
    def _handle_irrigation_stop(self, params: dict):
        """Handle irrigation stop command"""
        try:
            asyncio.create_task(self.irrigation.stop())
            
            # Log operation locally (non-blocking)
            asyncio.create_task(self.database.async_log_operation(
                device_type="irrigation",
                action="stop",
                status="stopped"
            ))
            
            logger.info("Irrigation stopped")
        except Exception as e:
            logger.error(f"Error stopping irrigation: {e}")
    
    def _handle_lighting_on(self, params: dict):
        """Handle lights ON command"""
        try:
            intensity = params.get("intensity", config.LED_DEFAULT_INTENSITY)
            
            asyncio.create_task(self.lighting.turn_on(intensity=intensity))
            
            # Log operation locally (non-blocking)
            asyncio.create_task(self.database.async_log_operation(
                device_type="lighting",
                action="on",
                params={"intensity": intensity},
                status="on"
            ))
            
            logger.info(f"Lighting ON: intensity={intensity}%")
        except Exception as e:
            logger.error(f"Error turning on lighting: {e}")
    
    def _handle_lighting_off(self, params: dict):
        """Handle lights OFF command"""
        try:
            asyncio.create_task(self.lighting.turn_off())
            
            # Log operation locally (non-blocking)
            asyncio.create_task(self.database.async_log_operation(
                device_type="lighting",
                action="off",
                status="off"
            ))
            
            logger.info("Lighting OFF")
        except Exception as e:
            logger.error(f"Error turning off lighting: {e}")
    
    def _handle_harvest_start(self, params: dict):
        """Handle harvest start command"""
        try:
            tray_id = params.get("tray_id", 1)
            speed = params.get("speed", config.HARVEST_BELT_SPEED)
            
            asyncio.create_task(self.harvest.start_belt(tray_id=tray_id, speed=speed))
            
            # Log operation locally (non-blocking)
            asyncio.create_task(self.database.async_log_operation(
                device_type="harvest",
                action="start",
                params={"tray_id": tray_id, "speed": speed},
                status="harvesting"
            ))
            
            logger.info(f"Harvest started: tray={tray_id}, speed={speed}%")
        except Exception as e:
            logger.error(f"Error starting harvest: {e}")
    
    def _handle_harvest_stop(self, params: dict):
        """Handle harvest stop command"""
        try:
            tray_id = params.get("tray_id", 1)
            
            asyncio.create_task(self.harvest.stop_belt(tray_id=tray_id))
            
            # Log operation locally (non-blocking)
            asyncio.create_task(self.database.async_log_operation(
                device_type="harvest",
                action="stop",
                params={"tray_id": tray_id},
                status="stopped"
            ))
            
            logger.info(f"Harvest stopped: tray={tray_id}")
        except Exception as e:
            logger.error(f"Error stopping harvest: {e}")
