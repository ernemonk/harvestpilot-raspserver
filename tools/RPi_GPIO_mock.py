"""
Mock GPIO module for simulation mode and systems without RPi.GPIO
"""

import logging

logger = logging.getLogger(__name__)

# Constants
BCM = "BCM"
BOARD = "BOARD"
OUT = "OUT"
IN = "IN"
HIGH = True
LOW = False
PUD_OFF = "PUD_OFF"
PUD_DOWN = "PUD_DOWN"
PUD_UP = "PUD_UP"

class MockPWM:
    """Mock PWM class for testing"""
    def __init__(self, pin, frequency):
        self.pin = pin
        self.frequency = frequency
        self.duty_cycle = 0
        logger.debug(f"[MOCK GPIO] PWM initialized on pin {pin} @ {frequency}Hz")
    
    def start(self, duty_cycle=0):
        self.duty_cycle = duty_cycle
        logger.debug(f"[MOCK GPIO] PWM started on pin {self.pin}: {duty_cycle}%")
    
    def ChangeDutyCycle(self, duty_cycle):
        self.duty_cycle = duty_cycle
        logger.debug(f"[MOCK GPIO] PWM duty cycle changed on pin {self.pin}: {duty_cycle}%")
    
    def stop(self):
        logger.debug(f"[MOCK GPIO] PWM stopped on pin {self.pin}")
    
    def ChangeFrequency(self, frequency):
        self.frequency = frequency
        logger.debug(f"[MOCK GPIO] PWM frequency changed on pin {self.pin}: {frequency}Hz")

# Global pin states
_pin_states = {}
_mode = None

def setmode(mode):
    """Set GPIO mode"""
    global _mode
    _mode = mode
    logger.debug(f"[MOCK GPIO] Mode set to {mode}")

def setup(pin, mode, pull_up_down=PUD_OFF):
    """Setup a GPIO pin"""
    _pin_states[pin] = LOW
    logger.debug(f"[MOCK GPIO] Pin {pin} setup as {mode} mode")

def output(pin, state):
    """Set GPIO pin output"""
    _pin_states[pin] = state
    state_str = "HIGH" if state == HIGH else "LOW"
    logger.debug(f"[MOCK GPIO] Pin {pin} output set to {state_str}")

def input(pin):
    """Read GPIO pin input"""
    return _pin_states.get(pin, LOW)

def PWM(pin, frequency):
    """Create a PWM instance"""
    return MockPWM(pin, frequency)

def cleanup():
    """Cleanup GPIO"""
    global _pin_states, _mode
    _pin_states = {}
    _mode = None
    logger.debug("[MOCK GPIO] Cleanup complete")

def setwarnings(enabled):
    """Set GPIO warnings"""
    logger.debug(f"[MOCK GPIO] Warnings {'enabled' if enabled else 'disabled'}")
