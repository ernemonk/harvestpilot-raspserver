"""GPIO cleanup utility"""

import logging
import RPi.GPIO as GPIO
import config

logger = logging.getLogger(__name__)


def cleanup_gpio():
    """Cleanup GPIO pins on shutdown"""
    if not config.SIMULATE_HARDWARE:
        try:
            GPIO.cleanup()
            logger.info("GPIO cleanup complete")
        except Exception as e:
            logger.error(f"Error during GPIO cleanup: {e}")
