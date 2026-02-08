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
        self.gpio_actuator = GPIOActuatorController(
            hardware_serial=config.HARDWARE_SERIAL,
            device_id=config.DEVICE_ID
        )
        
        # In-memory sensor reading buffer (economical persistence strategy)
        self.sensor_buffer = {
            'temperature': [],
            'humidity': [],
            'soil_moisture': [],
            'water_level': None
        }
        self.buffer_window_start = datetime.now()
        
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
            
            # Connect GPIO Actuator Controller (real-time Firestore listener)
            self.gpio_actuator.connect()
            logger.info("GPIO Actuator Controller connected - listening to Firestore for GPIO commands")
            
            # Set Firebase status in diagnostics
            self.diagnostics.set_firebase_status(True)
            
            # Start all background tasks
            self.running = True
            
            tasks = [
                self._sensor_reading_loop(),
                self._aggregation_loop(),        # New: aggregate buffered data every 60s
                self._sync_to_cloud_loop(),     # Sync aggregated data every 30+ min
                self._heartbeat_loop(),         # Keep-alive signal to Firebase every 30s
                self._metrics_loop(),           # Publish metrics every 5 minutes
            ]
            
            if config.AUTO_IRRIGATION_ENABLED or config.AUTO_LIGHTING_ENABLED:
                tasks.append(self.automation.run_automation_loop())
            
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
            # Sync remaining data to cloud before shutdown
            await self._sync_remaining_data()
            
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
            
            # Cleanup GPIO
            cleanup_gpio()
            
            logger.info("RaspServer stopped successfully")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
    
    async def _sensor_reading_loop(self):
        """Continuously read sensors and publish to Firebase (with in-memory buffering, dynamic interval)"""
        logger.info("Starting sensor reading loop...")
        
        while self.running:
            try:
                # Read sensors
                reading = await self.sensors.read_all()
                self.diagnostics.record_sensor_read()
                
                # Buffer reading in-memory (NOT writing to disk every 5 seconds)
                self.sensor_buffer['temperature'].append(reading.temperature)
                self.sensor_buffer['humidity'].append(reading.humidity)
                self.sensor_buffer['soil_moisture'].append(reading.soil_moisture)
                self.sensor_buffer['water_level'] = reading.water_level
                
                # Publish to Firebase (async, non-blocking)
                asyncio.create_task(self._publish_sensor_async(reading))
                
                # Check thresholds
                alerts = await self.sensors.check_thresholds(reading)
                if alerts:
                    for alert in alerts:
                        self.diagnostics.record_alert()
                        
                        # Save raw reading when threshold crossed (immediate, no buffer)
                        await self.database.async_save_sensor_raw(reading, reason="threshold_crossed")
                        
                        # Store alert locally - non-blocking
                        await self.database.async_save_alert(alert.to_dict())
                        
                        # Publish to Firebase
                        asyncio.create_task(self._publish_alert_async(alert))
                        
                        # Emergency stop on critical alert
                        if alert.severity == 'critical' and config.EMERGENCY_STOP_ON_WATER_LOW:
                            logger.warning("Critical alert - emergency stop")
                            await self._emergency_stop()
                
                interval = self.config_manager.get_sensor_read_interval()
                await asyncio.sleep(interval)  # Dynamic interval from ConfigManager
                
            except Exception as e:
                logger.error(f"Error in sensor loop: {e}")
                self.diagnostics.record_error('sensor')
                await asyncio.sleep(5)
    
    async def _publish_sensor_async(self, reading):
        """Publish sensor data to Firebase asynchronously"""
        try:
            self.firebase.publish_sensor_data(reading)
        except Exception as e:
            logger.error(f"Failed to publish sensor data: {e}")
            self.diagnostics.record_error('firebase')
    
    async def _publish_alert_async(self, alert):
        """Publish alert to Firebase asynchronously"""
        try:
            self.firebase.publish_status_update({
                "lastAlert": alert.to_dict()
            })
        except Exception as e:
            logger.error(f"Failed to publish alert: {e}")
    
    async def _aggregation_loop(self):
        """Aggregate buffered sensor data and persist (dynamic interval from ConfigManager)"""
        logger.info("Starting sensor aggregation loop")
        
        while self.running:
            try:
                interval = self.config_manager.get_aggregation_interval()
                await asyncio.sleep(interval)  # Dynamic interval from ConfigManager
                
                # Only aggregate if buffer has data
                if self.sensor_buffer['temperature']:
                    window_end = datetime.now()
                    
                    # Calculate aggregates
                    aggregation = {
                        'window_start': self.buffer_window_start.isoformat(),
                        'window_end': window_end.isoformat(),
                        'temperature_avg': sum(self.sensor_buffer['temperature']) / len(self.sensor_buffer['temperature']),
                        'temperature_min': min(self.sensor_buffer['temperature']),
                        'temperature_max': max(self.sensor_buffer['temperature']),
                        'temperature_last': self.sensor_buffer['temperature'][-1],
                        'temperature_count': len(self.sensor_buffer['temperature']),
                        'humidity_avg': sum(self.sensor_buffer['humidity']) / len(self.sensor_buffer['humidity']),
                        'humidity_min': min(self.sensor_buffer['humidity']),
                        'humidity_max': max(self.sensor_buffer['humidity']),
                        'humidity_last': self.sensor_buffer['humidity'][-1],
                        'humidity_count': len(self.sensor_buffer['humidity']),
                        'soil_moisture_avg': sum(self.sensor_buffer['soil_moisture']) / len(self.sensor_buffer['soil_moisture']),
                        'soil_moisture_min': min(self.sensor_buffer['soil_moisture']),
                        'soil_moisture_max': max(self.sensor_buffer['soil_moisture']),
                        'soil_moisture_last': self.sensor_buffer['soil_moisture'][-1],
                        'soil_moisture_count': len(self.sensor_buffer['soil_moisture']),
                        'water_level_last': self.sensor_buffer['water_level'] if self.sensor_buffer['water_level'] is not None else False
                    }
                    
                    # Save aggregated data (non-blocking)
                    await self.database.async_save_sensor_aggregated(aggregation)
                    
                    logger.info(f"Aggregated 60-second window: temp={aggregation['temperature_avg']:.1f}°C, "
                               f"humidity={aggregation['humidity_avg']:.1f}%, "
                               f"readings={aggregation['temperature_count']}")
                    
                    # Reset buffer for next window
                    self.sensor_buffer = {
                        'temperature': [],
                        'humidity': [],
                        'soil_moisture': [],
                        'water_level': None
                    }
                    self.buffer_window_start = datetime.now()
                
            except Exception as e:
                logger.error(f"Error in aggregation loop: {e}")
                await asyncio.sleep(5)
    
    async def _sync_to_cloud_loop(self):
        """Periodically sync local data to cloud (dynamic interval from ConfigManager)"""
        logger.info("Starting cloud sync loop")
        
        while self.running:
            try:
                interval = self.config_manager.get_sync_interval()
                await asyncio.sleep(interval)  # Dynamic interval from ConfigManager
                await self._sync_remaining_data()
                
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                await asyncio.sleep(60)
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat to Firebase to keep device online (dynamic interval from ConfigManager)"""
        logger.info("🎯 Starting heartbeat loop")
        heartbeat_count = 0
        
        while self.running:
            try:
                interval = self.config_manager.get_heartbeat_interval()
                await asyncio.sleep(interval)  # Dynamic interval from ConfigManager
                
                # Publish heartbeat to Firebase (keeps device status as "online")
                try:
                    self.firebase.publish_heartbeat()
                    heartbeat_count += 1
                    self.diagnostics.record_heartbeat()
                    logger.info(f"💓 Heartbeat #{heartbeat_count} sent successfully")
                except Exception as hb_error:
                    logger.error(f"💔 Heartbeat failed: {hb_error}", exc_info=True)
                    self.diagnostics.record_error('firebase')
                
            except asyncio.CancelledError:
                logger.info("Heartbeat loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in heartbeat loop: {e}", exc_info=True)
                self.diagnostics.record_error('firebase')
                await asyncio.sleep(5)
    
    async def _metrics_loop(self):
        """Publish diagnostic metrics to Firebase (dynamic interval from ConfigManager)"""
        logger.info("📊 Starting metrics loop")
        metrics_count = 0
        
        while self.running:
            try:
                interval = self.config_manager.get_metrics_interval()
                await asyncio.sleep(interval)  # Dynamic interval from ConfigManager
                
                # Get health summary and publish to Firebase
                health_summary = self.diagnostics.get_compact_summary()
                try:
                    self.firebase.publish_status_update({
                        "diagnostics": health_summary
                    })
                    metrics_count += 1
                    logger.info(f"📈 Health check #{metrics_count} published - Status: {health_summary['status']}, "
                               f"Uptime: {health_summary['uptime_seconds']}s, "
                               f"Errors: {health_summary['total_errors']}")
                except Exception as metric_error:
                    logger.error(f"Failed to publish metrics: {metric_error}", exc_info=True)
                
                # Log summary to journal
                self.diagnostics.log_summary()
                
            except asyncio.CancelledError:
                logger.info("Metrics loop cancelled")
                break
            except Exception as e:
                logger.error(f"❌ Error in metrics loop: {e}", exc_info=True)
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Error in metrics loop: {e}")
                self.diagnostics.record_error('firebase')
                await asyncio.sleep(10)
    
    async def _sync_remaining_data(self):
        """Sync all unsynced data to cloud (non-blocking)"""
        try:
            # Sync aggregated sensor readings (primary data source)
            unsynced_agg = self.database.get_unsynced_aggregated_readings(limit=1000)
            for agg_dict in unsynced_agg:
                try:
                    # Publish aggregated data to Firebase
                    self.firebase.publish_status_update({
                        "aggregated_reading": {
                            "window_start": agg_dict['window_start'],
                            "window_end": agg_dict['window_end'],
                            "temperature_avg": agg_dict['temperature_avg'],
                            "humidity_avg": agg_dict['humidity_avg'],
                            "soil_moisture_avg": agg_dict['soil_moisture_avg'],
                            "water_level": agg_dict['water_level_last']
                        }
                    })
                    await self.database.async_mark_aggregated_reading_synced(agg_dict['id'])
                except Exception as e:
                    logger.error(f"Error syncing aggregated reading: {e}")
            
            # Sync raw readings (threshold events)
            unsynced_raw = self.database.get_unsynced_raw_readings(limit=500)
            for raw_dict in unsynced_raw:
                try:
                    self.firebase.publish_status_update({
                        "raw_reading": {
                            "timestamp": raw_dict['timestamp'],
                            "temperature": raw_dict['temperature'],
                            "reason": raw_dict['reason']
                        }
                    })
                    await self.database.async_mark_raw_reading_synced(raw_dict['id'])
                except Exception as e:
                    logger.error(f"Error syncing raw reading: {e}")
            
            # Sync legacy readings (for backwards compatibility if any)
            unsynced_readings = self.database.get_unsynced_readings(limit=100)
            for reading_dict in unsynced_readings:
                try:
                    from ..models import SensorReading
                    reading = SensorReading(
                        timestamp=reading_dict['timestamp'],
                        temperature=reading_dict['temperature'],
                        humidity=reading_dict['humidity'],
                        soil_moisture=reading_dict['soil_moisture'],
                        water_level=reading_dict['water_level']
                    )
                    self.firebase.publish_sensor_data(reading)
                    await self.database.async_mark_reading_synced(reading_dict['id'])
                except Exception as e:
                    logger.error(f"Error syncing legacy reading: {e}")
            
            # Sync alerts
            unsynced_alerts = self.database.get_unsynced_alerts(limit=200)
            for alert_dict in unsynced_alerts:
                try:
                    self.firebase.publish_status_update({"alert": alert_dict})
                    await self.database.async_mark_alert_synced(alert_dict['id'])
                except Exception as e:
                    logger.error(f"Error syncing alert: {e}")
            
            # Cleanup old data (keep 7 days)
            self.database.cleanup_old_data(days=7)
            
            # Log sync status
            stats = self.database.get_database_size()
            logger.info(f"Sync complete. DB: {stats.get('aggregated')} agg, "
                       f"{stats.get('raw')} raw, {stats.get('alerts')} alerts, "
                       f"{stats.get('file_size_mb')}MB")
            
        except Exception as e:
            logger.error(f"Error syncing data: {e}")
    
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
            
            asyncio.create_task(self.irrigation.start(duration=duration, speed=speed))
            
            # Log operation locally (non-blocking)
            asyncio.create_task(self.database.async_log_operation(
                device_type="irrigation",
                action="start",
                params={"duration": duration, "speed": speed},
                status="started"
            ))
            
            self.firebase.publish_status_update({
                "irrigation": {"status": "running", "speed": speed}
            })
            
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
            
            self.firebase.publish_status_update({
                "irrigation": {"status": "stopped"}
            })
            
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
            
            self.firebase.publish_status_update({
                "lighting": {"status": "on", "intensity": intensity}
            })
            
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
            
            self.firebase.publish_status_update({
                "lighting": {"status": "off"}
            })
            
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
            
            self.firebase.publish_status_update({
                f"harvest_tray_{tray_id}": {"status": "harvesting", "speed": speed}
            })
            
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
            
            self.firebase.publish_status_update({
                f"harvest_tray_{tray_id}": {"status": "stopped"}
            })
            
            logger.info(f"Harvest stopped: tray={tray_id}")
        except Exception as e:
            logger.error(f"Error stopping harvest: {e}")
