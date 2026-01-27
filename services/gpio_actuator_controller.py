"""
GPIO Actuator Controller with Firestore Real-time Listener
Listens to Firestore gpioState changes and controls physical GPIO pins
"""

import asyncio
import logging
import threading
from typing import Dict, Any, Optional, Callable

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

import firebase_admin
from firebase_admin import firestore

import config

logger = logging.getLogger(__name__)


class GPIOActuatorController:
    """
    Controls GPIO pins based on Firestore gpioState updates.
    
    When the webapp toggles an actuator:
    1. Webapp writes to Firestore: devices/{deviceId}/gpioState/{bcmPin}/state
    2. This controller receives the update in real-time
    3. Controller sets the physical GPIO pin HIGH or LOW
    """
    
    def __init__(self, device_id: str = None):
        self.device_id = device_id or config.DEVICE_ID
        self.firestore_db = None
        self.listener = None
        self._running = False
        self._pins_initialized: Dict[int, str] = {}  # bcmPin -> mode
        self._state_callbacks: Dict[int, Callable] = {}
        
        # Setup GPIO
        if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            logger.info("GPIO initialized in BCM mode")
        else:
            logger.info("GPIO simulation mode (no hardware)")
    
    def connect(self):
        """Connect to Firestore and start listening for gpioState changes"""
        try:
            if not firebase_admin._apps:
                logger.error("Firebase not initialized. Call firebase connect first.")
                return False
            
            self.firestore_db = firestore.client()
            self._running = True
            
            # Start the real-time listener
            self._start_gpio_listener()
            
            logger.info(f"GPIO Actuator Controller connected for device: {self.device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect GPIO controller: {e}")
            return False
    
    def _start_gpio_listener(self):
        """Start listening to gpioState changes in Firestore"""
        try:
            device_ref = self.firestore_db.collection('devices').document(self.device_id)
            
            def on_snapshot(doc_snapshot, changes, read_time):
                """Callback when device document changes"""
                for doc in doc_snapshot:
                    if doc.exists:
                        data = doc.to_dict()
                        gpio_state = data.get('gpioState', {})
                        
                        if gpio_state:
                            self._process_gpio_state(gpio_state)
            
            # Attach the listener
            self.listener = device_ref.on_snapshot(on_snapshot)
            logger.info("GPIO state listener started")
            
        except Exception as e:
            logger.error(f"Failed to start GPIO listener: {e}")
    
    def _process_gpio_state(self, gpio_state: Dict[str, Any]):
        """Process GPIO state updates from Firestore"""
        for bcm_pin_str, pin_data in gpio_state.items():
            try:
                bcm_pin = int(bcm_pin_str)
                mode = pin_data.get('mode', 'output')
                state = pin_data.get('state', False)
                function = pin_data.get('function', '')
                
                # Initialize pin if not already done
                if bcm_pin not in self._pins_initialized:
                    self._setup_pin(bcm_pin, mode)
                
                # Set pin state if it's an output
                if mode == 'output':
                    self._set_pin_state(bcm_pin, state, function)
                
            except Exception as e:
                logger.error(f"Error processing GPIO pin {bcm_pin_str}: {e}")
    
    def _setup_pin(self, bcm_pin: int, mode: str):
        """Setup a GPIO pin"""
        try:
            if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
                if mode == 'output':
                    GPIO.setup(bcm_pin, GPIO.OUT, initial=GPIO.LOW)
                elif mode == 'input':
                    GPIO.setup(bcm_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
                
                logger.info(f"GPIO{bcm_pin} setup as {mode}")
            else:
                logger.info(f"[SIM] GPIO{bcm_pin} setup as {mode}")
            
            self._pins_initialized[bcm_pin] = mode
            
        except Exception as e:
            logger.error(f"Failed to setup GPIO{bcm_pin}: {e}")
    
    def _set_pin_state(self, bcm_pin: int, state: bool, function: str = ''):
        """Set a GPIO pin HIGH or LOW"""
        try:
            if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
                GPIO.output(bcm_pin, GPIO.HIGH if state else GPIO.LOW)
                logger.info(f"GPIO{bcm_pin} ({function}) -> {'HIGH' if state else 'LOW'}")
            else:
                logger.info(f"[SIM] GPIO{bcm_pin} ({function}) -> {'HIGH' if state else 'LOW'}")
            
            # Call any registered callbacks
            if bcm_pin in self._state_callbacks:
                self._state_callbacks[bcm_pin](state)
                
        except Exception as e:
            logger.error(f"Failed to set GPIO{bcm_pin} state: {e}")
    
    def register_callback(self, bcm_pin: int, callback: Callable[[bool], None]):
        """Register a callback for when a pin state changes"""
        self._state_callbacks[bcm_pin] = callback
    
    def read_pin(self, bcm_pin: int) -> Optional[bool]:
        """Read the current state of an input pin"""
        try:
            if bcm_pin not in self._pins_initialized:
                logger.warning(f"GPIO{bcm_pin} not initialized")
                return None
            
            if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
                return GPIO.input(bcm_pin) == GPIO.HIGH
            else:
                logger.info(f"[SIM] Read GPIO{bcm_pin}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to read GPIO{bcm_pin}: {e}")
            return None
    
    def set_pin(self, bcm_pin: int, state: bool):
        """Manually set a pin state (bypasses Firestore)"""
        if bcm_pin in self._pins_initialized:
            self._set_pin_state(bcm_pin, state)
        else:
            logger.warning(f"GPIO{bcm_pin} not initialized, setting up first")
            self._setup_pin(bcm_pin, 'output')
            self._set_pin_state(bcm_pin, state)
    
    async def update_firestore_state(self, bcm_pin: int, state: bool):
        """Update the pin state back to Firestore (for sensor readings, etc)"""
        try:
            device_ref = self.firestore_db.collection('devices').document(self.device_id)
            
            await device_ref.set({
                f'gpioState.{bcm_pin}.state': state,
                f'gpioState.{bcm_pin}.lastUpdated': firestore.SERVER_TIMESTAMP,
            }, merge=True)
            
            logger.debug(f"Updated Firestore GPIO{bcm_pin} state to {state}")
            
        except Exception as e:
            logger.error(f"Failed to update Firestore state: {e}")
    
    def disconnect(self):
        """Stop listening and cleanup GPIO"""
        self._running = False
        
        if self.listener:
            self.listener.unsubscribe()
            logger.info("GPIO listener stopped")
        
        if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
            GPIO.cleanup()
            logger.info("GPIO cleanup complete")
    
    def get_pin_states(self) -> Dict[int, Dict[str, Any]]:
        """Get current state of all initialized pins"""
        states = {}
        for bcm_pin, mode in self._pins_initialized.items():
            if mode == 'input':
                value = self.read_pin(bcm_pin)
            else:
                value = None  # Output pins don't have readable state in BCM mode
            states[bcm_pin] = {
                'mode': mode,
                'state': value
            }
        return states


# Singleton instance
_gpio_controller: Optional[GPIOActuatorController] = None


def get_gpio_controller() -> GPIOActuatorController:
    """Get or create the GPIO controller singleton"""
    global _gpio_controller
    if _gpio_controller is None:
        _gpio_controller = GPIOActuatorController()
    return _gpio_controller


async def init_gpio_controller(device_id: str = None) -> GPIOActuatorController:
    """Initialize and connect the GPIO controller"""
    controller = get_gpio_controller()
    if device_id:
        controller.device_id = device_id
    controller.connect()
    return controller
