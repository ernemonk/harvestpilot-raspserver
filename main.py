"""
HarvestPilot RaspServer - Raspberry Pi Hardware Control Server

Runs on Raspberry Pi to control physical hardware and communicate with
the cloud agent via Firebase Realtime Database.
"""

import asyncio
import logging
import signal
import sys
from firebase_client import FirebaseClient
from controllers.sensors import SensorController
from controllers.irrigation import IrrigationController
from controllers.lighting import LightingController
from controllers.harvest import HarvestController
from utils.logger import setup_logging
from utils.gpio_manager import cleanup_gpio
import config

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


class RaspServer:
    """Main Raspberry Pi server for hardware control"""
    
    def __init__(self):
        logger.info("Initializing HarvestPilot RaspServer...")
        
        # Initialize controllers
        self.sensors = SensorController()
        self.irrigation = IrrigationController()
        self.lighting = LightingController()
        self.harvest = HarvestController()
        
        # Initialize Firebase client
        self.firebase = FirebaseClient()
        
        # Register command handlers
        self.firebase.register_command_handler("irrigation", "start", self._handle_irrigation_start)
        self.firebase.register_command_handler("irrigation", "stop", self._handle_irrigation_stop)
        self.firebase.register_command_handler("lighting", "on", self._handle_lighting_on)
        self.firebase.register_command_handler("lighting", "off", self._handle_lighting_off)
        self.firebase.register_command_handler("harvest", "start", self._handle_harvest_start)
        self.firebase.register_command_handler("harvest", "stop", self._handle_harvest_stop)
        
        self.running = False
        
        logger.info("RaspServer initialized successfully")
    
    async def start(self):
        """Start the server"""
        try:
            logger.info("Starting HarvestPilot RaspServer...")
            
            # Connect to Firebase
            self.firebase.connect()
            
            # Start sensor reading loop
            self.running = True
            asyncio.create_task(self.sensor_reading_loop())
            
            # Start local automation (if enabled)
            if config.AUTO_IRRIGATION_ENABLED:
                asyncio.create_task(self.automation_loop())
            
            logger.info("RaspServer started successfully")
            
            # Keep running
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error starting RaspServer: {e}", exc_info=True)
            raise
    
    async def stop(self):
        """Stop the server gracefully"""
        logger.info("Stopping HarvestPilot RaspServer...")
        
        self.running = False
        
        # Stop all hardware
        await self.irrigation.stop()
        await self.lighting.turn_off()
        for tray_id in range(1, 7):
            await self.harvest.stop_belt(tray_id)
        
        # Disconnect Firebase
        self.firebase.disconnect()
        
        # Cleanup GPIO
        cleanup_gpio()
        
        logger.info("RaspServer stopped")
    
    async def sensor_reading_loop(self):
        """Continuously read sensors and publish to Firebase"""
        logger.info("Starting sensor reading loop...")
        
        while self.running:
            try:
                # Read all sensors
                reading = await self.sensors.read_all()
                
                # Publish to Firebase
                self.firebase.publish_sensor_data(reading)
                
                # Check thresholds and send alerts
                alerts = await self.sensors.check_thresholds(reading)
                if alerts:
                    for alert in alerts:
                        self.firebase.publish_status_update({
                            "lastAlert": alert
                        })
                        
                        # Emergency stop if critical
                        if alert.get('severity') == 'critical' and config.EMERGENCY_STOP_ON_WATER_LOW:
                            logger.warning("Critical alert - initiating emergency stop")
                            await self.emergency_stop()
                
                # Wait before next reading
                await asyncio.sleep(config.SENSOR_READING_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in sensor reading loop: {e}")
                await asyncio.sleep(5)  # Wait before retry
    
    async def automation_loop(self):
        """Local automation and scheduled tasks"""
        logger.info("Starting automation loop...")
        
        from datetime import datetime
        
        while self.running:
            try:
                current_time = datetime.now().strftime("%H:%M")
                
                # Check irrigation schedule
                if current_time in config.IRRIGATION_SCHEDULE:
                    logger.info(f"Scheduled irrigation at {current_time}")
                    await self.irrigation.start(
                        duration=config.IRRIGATION_CYCLE_DURATION,
                        speed=config.PUMP_DEFAULT_SPEED
                    )
                    
                    # Publish status
                    self.mqtt_client.publish(
                        "harvestpilot/status/irrigation",
                        {"scheduled_run": True, "time": current_time}
                    )
                
                # Check lighting schedule
                if current_time == config.LIGHT_ON_TIME:
                    logger.info(f"Scheduled lights ON at {current_time}")
                    await self.lighting.turn_on(intensity=config.LED_DEFAULT_INTENSITY)
                elif current_time == config.LIGHT_OFF_TIME:
                    logger.info(f"Scheduled lights OFF at {current_time}")
                    await self.lighting.turn_off()
                
                # Wait for next minute
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in automation loop: {e}")
                await asyncio.sleep(60)
    
    async def emergency_stop(self):
        """Emergency stop all hardware"""
        logger.warning("EMERGENCY STOP ACTIVATED")
        
        await self.irrigation.stop()
        await self.lighting.turn_off()
        for tray_id in range(1, 7):
            await self.harvest.stop_belt(tray_id)
        
        # Publish emergency status
        self.firebase.publish_status_update({
            "emergencyStop": True,
            "timestamp": asyncio.get_event_loop().time()
        })
    
    # Command handlers for Firebase
    def _handle_irrigation_start(self, params):
        """Handle irrigation start command"""
        try:
            duration = params.get("duration", config.IRRIGATION_CYCLE_DURATION)
            speed = params.get("speed", config.PUMP_DEFAULT_SPEED)
            
            asyncio.create_task(
                self.irrigation.start(duration=duration, speed=speed)
            )
            
            self.firebase.publish_status_update({
                "irrigation": {"status": "running", "speed": speed}
            })
            
            logger.info(f"Irrigation started - duration: {duration}s, speed: {speed}%")
        except Exception as e:
            logger.error(f"Error starting irrigation: {e}")
    
    def _handle_irrigation_stop(self, params):
        """Handle irrigation stop command"""
        try:
            asyncio.create_task(self.irrigation.stop())
            
            self.firebase.publish_status_update({
                "irrigation": {"status": "stopped"}
            })
            
            logger.info("Irrigation stopped")
        except Exception as e:
            logger.error(f"Error stopping irrigation: {e}")
    
    def _handle_lighting_on(self, params):
        """Handle lighting ON command"""
        try:
            intensity = params.get("intensity", config.LED_DEFAULT_INTENSITY)
            
            asyncio.create_task(
                self.lighting.turn_on(intensity=intensity)
            )
            
            self.firebase.publish_status_update({
                "lighting": {"status": "on", "intensity": intensity}
            })
            
            logger.info(f"Lighting turned ON - intensity: {intensity}%")
        except Exception as e:
            logger.error(f"Error turning on lighting: {e}")
    
    def _handle_lighting_off(self, params):
        """Handle lighting OFF command"""
        try:
            asyncio.create_task(self.lighting.turn_off())
            
            self.firebase.publish_status_update({
                "lighting": {"status": "off"}
            })
            
            logger.info("Lighting turned OFF")
        except Exception as e:
            logger.error(f"Error turning off lighting: {e}")
    
    def _handle_harvest_start(self, params):
        """Handle harvest start command"""
        try:
            tray_id = params.get("tray_id", 1)
            speed = params.get("speed", config.HARVEST_BELT_SPEED)
            
            asyncio.create_task(
                self.harvest.start_belt(tray_id=tray_id, speed=speed)
            )
            
            self.firebase.publish_status_update({
                f"harvest_tray_{tray_id}": {"status": "harvesting", "speed": speed}
            })
            
            logger.info(f"Harvest started - tray: {tray_id}, speed: {speed}%")
        except Exception as e:
            logger.error(f"Error starting harvest: {e}")
    
    def _handle_harvest_stop(self, params):
        """Handle harvest stop command"""
        try:
            tray_id = params.get("tray_id", 1)
            
            asyncio.create_task(self.harvest.stop_belt(tray_id=tray_id))
            
            self.firebase.publish_status_update({
                f"harvest_tray_{tray_id}": {"status": "stopped"}
            })
            
            logger.info(f"Harvest stopped - tray: {tray_id}")
        except Exception as e:
            logger.error(f"Error stopping harvest: {e}")


async def main():
    """Main entry point"""
    server = RaspServer()
    
    # Handle shutdown signals
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(server.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        await server.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server crashed: {e}", exc_info=True)
        sys.exit(1)
