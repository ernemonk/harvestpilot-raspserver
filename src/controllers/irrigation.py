"""Irrigation controller for Raspberry Pi"""

import logging
from ..utils.gpio_import import GPIO
from .. import config

logger = logging.getLogger(__name__)


class IrrigationController:
    """Control irrigation pump"""
    
    def __init__(self):
        if not config.SIMULATE_HARDWARE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(config.PUMP_PWM_PIN, GPIO.OUT)
            self.pwm = GPIO.PWM(config.PUMP_PWM_PIN, config.PUMP_PWM_FREQUENCY)
        
        self.is_running = False
        self.current_speed = 0
        logger.info("Irrigation controller initialized")
    
    async def start(self, duration=30, speed=80):
        """Start pump"""
        if config.SIMULATE_HARDWARE:
            logger.info(f"[SIMULATION] Starting pump: {duration}s at {speed}%")
            self.is_running = True
            self.current_speed = speed
            return
        
        self.pwm.start(speed)
        self.is_running = True
        self.current_speed = speed
        logger.info(f"Pump started at {speed}%")
    
    async def stop(self):
        """Stop pump"""
        if config.SIMULATE_HARDWARE:
            logger.info("[SIMULATION] Stopping pump")
            self.is_running = False
            self.current_speed = 0
            return
        
        self.pwm.stop()
        self.is_running = False
        self.current_speed = 0
        logger.info("Pump stopped")
