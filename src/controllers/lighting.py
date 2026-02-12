"""Lighting controller for Raspberry Pi

DEPRECATED: All GPIO control now goes through gpio_actuator_controller.py.
This controller is kept for reference but is not actively used.
Pin configuration comes from Firestore, not config.py.
"""

import logging
from ..utils.gpio_import import GPIO
from .. import config

logger = logging.getLogger(__name__)


class LightingController:
    """Control LED lighting (DEPRECATED - use GPIOActuatorController)"""
    
    def __init__(self, pwm_pin: int = None):
        self.pwm_pin = pwm_pin
        self.pwm = None
        if pwm_pin and not config.SIMULATE_HARDWARE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pwm_pin, GPIO.OUT)
            self.pwm = GPIO.PWM(pwm_pin, 1000)
        
        self.is_on = False
        self.current_intensity = 0
        logger.info("Lighting controller initialized")
    
    async def turn_on(self, intensity=80):
        """Turn lights on"""
        if config.SIMULATE_HARDWARE:
            logger.info(f"[SIMULATION] Lights ON at {intensity}%")
            self.is_on = True
            self.current_intensity = intensity
            return
        
        self.pwm.start(intensity)
        self.is_on = True
        self.current_intensity = intensity
        logger.info(f"Lights ON at {intensity}%")
    
    async def turn_off(self):
        """Turn lights off"""
        if config.SIMULATE_HARDWARE:
            logger.info("[SIMULATION] Lights OFF")
            self.is_on = False
            self.current_intensity = 0
            return
        
        self.pwm.stop()
        self.is_on = False
        self.current_intensity = 0
        logger.info("Lights OFF")
