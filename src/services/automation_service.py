"""Automation service - handles scheduled tasks and automation"""

import logging
import asyncio
from datetime import datetime
import config

logger = logging.getLogger(__name__)


class AutomationService:
    """Handles local automation and scheduled tasks"""
    
    def __init__(self, irrigation_controller, lighting_controller):
        self.irrigation = irrigation_controller
        self.lighting = lighting_controller
        logger.info("Automation service initialized")
    
    async def run_automation_loop(self):
        """Main automation loop"""
        logger.info("Starting automation loop")
        
        while True:
            try:
                current_time = datetime.now().strftime("%H:%M")
                
                # Check irrigation schedule
                if config.AUTO_IRRIGATION_ENABLED:
                    await self._check_irrigation_schedule(current_time)
                
                # Check lighting schedule
                if config.AUTO_LIGHTING_ENABLED:
                    await self._check_lighting_schedule(current_time)
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in automation loop: {e}")
                await asyncio.sleep(60)
    
    async def _check_irrigation_schedule(self, current_time: str):
        """Check if irrigation should run"""
        try:
            if current_time in config.IRRIGATION_SCHEDULE:
                logger.info(f"Starting scheduled irrigation at {current_time}")
                await self.irrigation.start(
                    duration=config.IRRIGATION_CYCLE_DURATION,
                    speed=config.PUMP_DEFAULT_SPEED
                )
        except Exception as e:
            logger.error(f"Error scheduling irrigation: {e}")
    
    async def _check_lighting_schedule(self, current_time: str):
        """Check if lights should turn on/off"""
        try:
            if current_time == config.LIGHT_ON_TIME:
                logger.info(f"Turning lights ON at {current_time}")
                await self.lighting.turn_on(config.LED_DEFAULT_INTENSITY)
            
            elif current_time == config.LIGHT_OFF_TIME:
                logger.info(f"Turning lights OFF at {current_time}")
                await self.lighting.turn_off()
                
        except Exception as e:
            logger.error(f"Error scheduling lights: {e}")
