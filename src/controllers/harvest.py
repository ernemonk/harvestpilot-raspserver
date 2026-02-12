"""Harvest controller for Raspberry Pi

DEPRECATED: All GPIO control now goes through gpio_actuator_controller.py.
This controller is kept for reference but is not actively used.
Pin configuration comes from Firestore, not config.py.
"""

import logging
from ..utils.gpio_import import GPIO
from .. import config

logger = logging.getLogger(__name__)


class HarvestController:
    """Control harvest belt motors (DEPRECATED - use GPIOActuatorController)"""
    
    def __init__(self):
        self.pwms = {}
        self.tray_states = {}
        logger.info("Harvest controller initialized (deprecated — use GPIOActuatorController)")
    
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
