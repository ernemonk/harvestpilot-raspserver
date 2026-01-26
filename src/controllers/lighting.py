"""Lighting controller for Raspberry Pi"""

import logging
import RPi.GPIO as GPIO
import config

logger = logging.getLogger(__name__)


class LightingController:
    """Control LED lighting"""
    
    def __init__(self):
        if not config.SIMULATE_HARDWARE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(config.LED_PWM_PIN, GPIO.OUT)
            self.pwm = GPIO.PWM(config.LED_PWM_PIN, config.LED_PWM_FREQUENCY)
        
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
