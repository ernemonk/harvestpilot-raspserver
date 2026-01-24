"""
HarvestPilot RaspServer - Raspberry Pi Hardware Control Server

Runs on Raspberry Pi to control physical hardware and communicate with
the cloud agent via MQTT.
"""

import asyncio
import logging
import signal
import sys
from mqtt.client import MQTTClient
from mqtt.handlers import CommandHandler
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
        
        # Initialize MQTT client
        self.mqtt_client = MQTTClient()
        self.command_handler = CommandHandler(
            irrigation=self.irrigation,
            lighting=self.lighting,
            harvest=self.harvest,
            sensors=self.sensors
        )
        
        # Register MQTT callbacks
        self.mqtt_client.register_callback(
            "harvestpilot/commands/#",
            self.command_handler.handle_command
        )
        
        self.running = False
        
        logger.info("RaspServer initialized successfully")
    
    async def start(self):
        """Start the server"""
        try:
            logger.info("Starting HarvestPilot RaspServer...")
            
            # Connect to MQTT broker
            await self.mqtt_client.connect()
            
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
        
        # Disconnect MQTT
        await self.mqtt_client.disconnect()
        
        # Cleanup GPIO
        cleanup_gpio()
        
        logger.info("RaspServer stopped")
    
    async def sensor_reading_loop(self):
        """Continuously read sensors and publish to MQTT"""
        logger.info("Starting sensor reading loop...")
        
        while self.running:
            try:
                # Read all sensors
                reading = await self.sensors.read_all()
                
                # Publish to MQTT
                self.mqtt_client.publish(
                    "harvestpilot/sensors/reading",
                    reading
                )
                
                # Check thresholds and send alerts
                alerts = await self.sensors.check_thresholds(reading)
                if alerts:
                    for alert in alerts:
                        self.mqtt_client.publish(
                            "harvestpilot/alerts/threshold",
                            alert
                        )
                        
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
        self.mqtt_client.publish(
            "harvestpilot/alerts/emergency",
            {"status": "emergency_stop", "reason": "critical_threshold"}
        )


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
