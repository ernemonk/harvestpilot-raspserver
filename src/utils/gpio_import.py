"""Conditional GPIO import handler for cross-platform compatibility"""

import logging
from .. import config

logger = logging.getLogger(__name__)

# Try to import RPi.GPIO, fall back to mock if not available
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
    logger.debug("✅ RPi.GPIO imported successfully")
except ImportError:
    GPIO_AVAILABLE = False
    logger.warning("⚠️  RPi.GPIO not available - using simulation mode")
    
    # Create mock GPIO module for testing
    class MockGPIO:
        """Mock GPIO for testing on non-Pi systems"""
        BCM = "BCM"
        OUT = "OUT"
        IN = "IN"
        HIGH = 1
        LOW = 0
        
        @staticmethod
        def setmode(mode):
            logger.debug(f"[MOCK GPIO] setmode({mode})")
        
        @staticmethod
        def setup(pin, mode):
            logger.debug(f"[MOCK GPIO] setup(pin={pin}, mode={mode})")
        
        @staticmethod
        def output(pin, state):
            state_str = "HIGH" if state == 1 else "LOW"
            logger.info(f"[MOCK GPIO] output(pin={pin}, state={state_str})")
        
        @staticmethod
        def input(pin):
            logger.debug(f"[MOCK GPIO] input(pin={pin})")
            return 0
        
        @staticmethod
        def cleanup():
            logger.debug(f"[MOCK GPIO] cleanup()")
        
        class PWM:
            def __init__(self, pin, frequency):
                self.pin = pin
                self.frequency = frequency
                logger.info(f"[MOCK GPIO] PWM(pin={pin}, frequency={frequency})")
            
            def start(self, duty_cycle):
                logger.info(f"[MOCK GPIO] PWM.start(pin={self.pin}, duty_cycle={duty_cycle}%)")
            
            def ChangeDutyCycle(self, duty_cycle):
                logger.info(f"[MOCK GPIO] PWM.ChangeDutyCycle(pin={self.pin}, duty_cycle={duty_cycle}%)")
            
            def stop(self):
                logger.info(f"[MOCK GPIO] PWM.stop(pin={self.pin})")
    
    GPIO = MockGPIO()

# Use mock GPIO if in simulation mode
if config.SIMULATE_HARDWARE:
    logger.info("🎭 SIMULATION MODE ENABLED - Using mock GPIO")
    class SimulatedGPIO:
        """Simulated GPIO for testing"""
        BCM = "BCM"
        OUT = "OUT"
        IN = "IN"
        HIGH = 1
        LOW = 0
        
        @staticmethod
        def setmode(mode):
            logger.debug(f"[SIMULATED GPIO] setmode({mode})")
        
        @staticmethod
        def setup(pin, mode):
            logger.info(f"[SIMULATED GPIO] setup(pin={pin}, mode={mode})")
        
        @staticmethod
        def output(pin, state):
            state_str = "HIGH" if state == 1 else "LOW"
            logger.info(f"[SIMULATED GPIO] 🔌 output(pin={pin}, state={state_str})")
        
        @staticmethod
        def input(pin):
            logger.debug(f"[SIMULATED GPIO] input(pin={pin})")
            return 0
        
        @staticmethod
        def cleanup():
            logger.debug(f"[SIMULATED GPIO] cleanup()")
        
        class PWM:
            def __init__(self, pin, frequency):
                self.pin = pin
                self.frequency = frequency
                logger.info(f"[SIMULATED GPIO] 📊 PWM(pin={pin}, frequency={frequency}Hz)")
            
            def start(self, duty_cycle):
                logger.info(f"[SIMULATED GPIO] ⚡ PWM.start(pin={self.pin}, duty_cycle={duty_cycle}%)")
            
            def ChangeDutyCycle(self, duty_cycle):
                logger.info(f"[SIMULATED GPIO] ⚡ PWM.ChangeDutyCycle(pin={self.pin}, duty_cycle={duty_cycle}%)")
            
            def stop(self):
                logger.info(f"[SIMULATED GPIO] ⏹️  PWM.stop(pin={self.pin})")
    
    GPIO = SimulatedGPIO()

__all__ = ['GPIO', 'GPIO_AVAILABLE']
