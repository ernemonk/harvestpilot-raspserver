"""MQTT command handlers"""

import logging
import asyncio

logger = logging.getLogger(__name__)


class CommandHandler:
    """Handle MQTT commands from cloud agent"""
    
    def __init__(self, irrigation, lighting, harvest, sensors):
        self.irrigation = irrigation
        self.lighting = lighting
        self.harvest = harvest
        self.sensors = sensors
        logger.info("Command handler initialized")
    
    def handle_command(self, topic, payload):
        """Route command to appropriate handler"""
        try:
            # Parse command type from topic
            parts = topic.split('/')
            if len(parts) < 3:
                return
            
            command_type = parts[2]  # harvestpilot/commands/{type}
            
            # Route to handler
            if command_type == "irrigation":
                asyncio.create_task(self._handle_irrigation(payload))
            elif command_type == "lighting":
                asyncio.create_task(self._handle_lighting(payload))
            elif command_type == "harvest":
                asyncio.create_task(self._handle_harvest(payload))
            elif command_type == "sensors":
                asyncio.create_task(self._handle_sensors(payload))
            else:
                logger.warning(f"Unknown command type: {command_type}")
                
        except Exception as e:
            logger.error(f"Error handling command: {e}")
    
    async def _handle_irrigation(self, payload):
        """Handle irrigation commands"""
        action = payload.get('action')
        
        if action == 'start':
            duration = payload.get('duration', 30)
            speed = payload.get('speed', 80)
            await self.irrigation.start(duration, speed)
            logger.info(f"Started irrigation: {duration}s at {speed}%")
            
        elif action == 'stop':
            await self.irrigation.stop()
            logger.info("Stopped irrigation")
    
    async def _handle_lighting(self, payload):
        """Handle lighting commands"""
        action = payload.get('action')
        
        if action == 'set':
            state = payload.get('state', True)
            intensity = payload.get('intensity', 80)
            
            if state:
                await self.lighting.turn_on(intensity)
                logger.info(f"Lights ON at {intensity}%")
            else:
                await self.lighting.turn_off()
                logger.info("Lights OFF")
    
    async def _handle_harvest(self, payload):
        """Handle harvest commands"""
        action = payload.get('action')
        tray_id = payload.get('tray_id', 1)
        
        if action == 'start':
            speed = payload.get('speed', 50)
            await self.harvest.start_belt(tray_id, speed)
            logger.info(f"Started harvest belt {tray_id} at {speed}%")
            
        elif action == 'stop':
            await self.harvest.stop_belt(tray_id)
            logger.info(f"Stopped harvest belt {tray_id}")
    
    async def _handle_sensors(self, payload):
        """Handle sensor commands"""
        action = payload.get('action')
        
        if action == 'read':
            reading = await self.sensors.read_all()
            # Publish result back
            # (MQTT client will be passed in to publish)
            logger.info(f"Sensor reading: {reading}")
