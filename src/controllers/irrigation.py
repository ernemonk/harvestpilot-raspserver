"""Irrigation controller for Raspberry Pi

DEPRECATED: All GPIO control now goes through gpio_actuator_controller.py.
This controller is kept for reference but is not actively used.
Pin configuration comes from Firestore, not config.py.
"""

import logging
from ..utils.gpio_import import GPIO
from .. import config

logger = logging.getLogger(__name__)


class IrrigationController:
    """Control irrigation pump (DEPRECATED - use GPIOActuatorController)"""
    
    def __init__(self, pwm_pin: int = None):
        self.pwm_pin = pwm_pin
        self.pwm = None
        if pwm_pin and not config.SIMULATE_HARDWARE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pwm_pin, GPIO.OUT)
            self.pwm = GPIO.PWM(pwm_pin, 1000)
        
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
