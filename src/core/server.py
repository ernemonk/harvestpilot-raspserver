"""Core RaspServer - main application server"""

import asyncio
import logging
from ..services import FirebaseService, SensorService
from ..services.diagnostics import DiagnosticsService
from ..services.config_manager import ConfigManager
from ..utils.gpio_manager import cleanup_gpio
from .. import config

# Import GPIO Actuator Controller for real-time Firestore control
from ..services.gpio_actuator_controller import GPIOActuatorController
from ..services.log_server import start_log_server, stop_log_server

logger = logging.getLogger(__name__)


class RaspServer:
    """Main Raspberry Pi server orchestrating all components.
    
    All GPIO control goes through GPIOActuatorController which reads
    pin definitions from Firestore (no hardcoded pins).
    """
    
    def __init__(self):
        logger.info("Initializing HarvestPilot RaspServer...")
        
        # Initialize diagnostics (tracks metrics)
        self.diagnostics = DiagnosticsService()
        
        # Initialize services
        self.firebase = FirebaseService()
        self.sensors = SensorService(
            firestore_db=None,  # Will get Firestore after Firebase init
            hardware_serial=config.HARDWARE_SERIAL
        )
        
        # Initialize configuration manager (dynamic intervals from Firestore)
        from ..storage.local_db import LocalDatabase
        local_db = LocalDatabase()
        self.config_manager = ConfigManager(
            hardware_serial=config.HARDWARE_SERIAL,
            database=local_db
        )
        
        # Initialize GPIO Actuator Controller for real-time Firestore control
        # Pin definitions come from Firestore, not config.py
        self.gpio_actuator = GPIOActuatorController(
            hardware_serial=config.HARDWARE_SERIAL,
            device_id=config.DEVICE_ID,
            config_manager=self.config_manager
        )
        
        self.running = False
        logger.info(f"RaspServer initialized (hardware_serial: {config.HARDWARE_SERIAL}, device_id: {config.DEVICE_ID})")
    
    async def start(self):
        """Start the server and all services"""
        try:
            logger.info("Starting HarvestPilot RaspServer...")
            
            # Connect to Firebase
            self.firebase.connect()
            
            # Pass Firestore DB to services that need it
            try:
                from firebase_admin import firestore
                firestore_db = firestore.client()
                self.sensors = SensorService(
                    firestore_db=firestore_db,
                    hardware_serial=config.HARDWARE_SERIAL
                )
                self.config_manager.set_firestore_client(firestore_db)
                logger.info("Services updated with Firestore DB")
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
            # This loads pins from Firestore, initializes hardware, starts listeners
            self.gpio_actuator.connect()
            logger.info("GPIO Actuator Controller connected — listening to Firestore")
            
            # Set Firebase status in diagnostics
            self.diagnostics.set_firebase_status(True)
            
            # Keep server alive — all real work happens in daemon threads
            # (GPIO listener, hardware sync, schedule checker, config listener)
            self.running = True
            await self._keep_alive()
            
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
            # Disconnect Firebase
            self.firebase.disconnect()
            
            # Disconnect GPIO Actuator Controller
            self.gpio_actuator.disconnect()
            
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
