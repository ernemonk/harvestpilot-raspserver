"""Harvest controller for Raspberry Pi"""

import logging
import RPi.GPIO as GPIO
import config

logger = logging.getLogger(__name__)


class HarvestController:
    """Control harvest belt motors"""
    
    def __init__(self):
        self.pwms = {}
        
        if not config.SIMULATE_HARDWARE:
            GPIO.setmode(GPIO.BCM)
            
            for motor in config.MOTOR_PINS:
                tray = motor['tray']
                GPIO.setup(motor['pwm'], GPIO.OUT)
                GPIO.setup(motor['dir'], GPIO.OUT)
                self.pwms[tray] = GPIO.PWM(motor['pwm'], config.MOTOR_PWM_FREQUENCY)
        
        self.tray_states = {i: {"running": False} for i in range(1, 7)}
        logger.info("Harvest controller initialized for 6 trays")
    
    async def start_belt(self, tray_id, speed=50):
        """Start belt motor"""
        if config.SIMULATE_HARDWARE:
            logger.info(f"[SIMULATION] Starting belt {tray_id} at {speed}%")
            self.tray_states[tray_id]["running"] = True
            return
        
        # Set direction
        motor = config.MOTOR_PINS[tray_id - 1]
        GPIO.output(motor['dir'], GPIO.HIGH)
        
        # Start motor
        self.pwms[tray_id].start(speed)
        self.tray_states[tray_id]["running"] = True
        logger.info(f"Belt {tray_id} started at {speed}%")
    
    async def stop_belt(self, tray_id):
        """Stop belt motor"""
        if config.SIMULATE_HARDWARE:
            logger.info(f"[SIMULATION] Stopping belt {tray_id}")
            self.tray_states[tray_id]["running"] = False
            return
        
        self.pwms[tray_id].stop()
        self.tray_states[tray_id]["running"] = False
        logger.info(f"Belt {tray_id} stopped")
