"""GPIO Actuator Controller - Real-time Firestore ↔ GPIO Hardware Bridge

ARCHITECTURE:
  Firestore `state` = DESIRED state (set by webapp)
  Firestore `hardwareState` = ACTUAL state (read from physical GPIO pin)
  Firestore `schedules` = Recurring GPIO operations with time windows
  
  Flow:
  1. Webapp sets gpioState.{pin}.state = true/false (desired)
  2. Pi listener picks it up INSTANTLY
  3. Pi sets physical GPIO pin HIGH/LOW
  4. Pi READS the actual pin value back from hardware
  5. Pi writes gpioState.{pin}.hardwareState = true/false (actual)
  6. If state != hardwareState → MISMATCH ALERT

  SCHEDULES (Real-time):
  1. Firestore schedule added/modified/deleted
  2. Real-time listener updates cache atomically
  3. Time windows strictly enforced (start_time → end_time)
  4. Hardware cache stays in perfect sync
  5. Schedule executions track hardware state

NAMING SYSTEM:
  - Default names are now smart GPIO-based: "GPIO{num} (PIN{phys}) - {type} ({capability})"
  - User can customize names - marked with name_customized=true flag
  - NON-DESTRUCTIVE: User-customized names are NEVER overwritten
  - Preserves business-critical naming and configurations
"""

import logging
import threading
import time
from typing import Dict, Callable, Optional, Any
from datetime import datetime
import firebase_admin
from firebase_admin import firestore
from ..utils.gpio_import import GPIO, GPIO_AVAILABLE
from ..utils.gpio_naming import GPIONameManager, GPIONamer
from .schedule_listener import get_schedule_cache, get_schedule_state_tracker, ScheduleCache, ScheduleStateTracker
from .firestore_schedule_listener import create_firestore_schedule_listener
from .. import config

logger = logging.getLogger(__name__)

# Local hardware read interval (fast, in-memory only, no Firestore write)
LOCAL_HARDWARE_READ_INTERVAL = 5.0


class GPIOActuatorController:
    """
    Production-grade GPIO controller with real-time Firestore sync.
    
    TWO sources of truth per pin:
      - state:         What the webapp WANTS (desired)
      - hardwareState: What the GPIO pin ACTUALLY IS (measured)
    
    They should always match. If they don't, something is wrong.
    
    TIMING:
      - Local hardware read: every 5s (in-memory, no network)
      - Firestore hardwareState write: at YOUR configured interval
        (set in Firestore config/intervals/hardware_state_sync_interval_s)
    """
    
    def __init__(self, hardware_serial: str = None, device_id: str = None,
                 config_manager=None):
        self.hardware_serial = hardware_serial or config.HARDWARE_SERIAL
        self.device_id = device_id or config.DEVICE_ID
        self.firestore_db = None
        self._running = False
        self._config_manager = config_manager  # For dynamic intervals from Firestore
        
        # GPIO naming system
        self._name_manager = GPIONameManager()
        self._gpio_namer = GPIONamer()
        
        # Pin tracking
        self._pins_initialized: Dict[int, str] = {}       # bcmPin -> mode ('output'/'input')
        self._desired_states: Dict[int, bool] = {}         # What Firestore says the pin should be
        self._hardware_states: Dict[int, bool] = {}        # What the pin ACTUALLY is (read from hardware)
        self._pin_names: Dict[int, str] = {}               # bcmPin -> human name
        self._active_low_pins: set = set()                 # Pins using active-LOW relay logic
        
        # Firestore state tracking (CRITICAL: separate from _desired_states)
        # _last_firestore_state ONLY tracks what Firestore's `state` field says.
        # Used by the state listener for REAL change detection.
        # _desired_states gets clobbered by schedules; this dict does NOT.
        self._last_firestore_state: Dict[int, bool] = {}
        
        # User override tracking — when user explicitly toggles a pin OFF
        # while a schedule is running, the schedule should stop.
        self._user_override_pins: set = set()
        
        # PWM tracking for duty cycle control
        self._pwm_objects: Dict[int, GPIO.PWM] = {}        # bcmPin -> PWM object
        self._pwm_duty_cycles: Dict[int, float] = {}       # bcmPin -> current duty cycle (0-100)
        
        # Schedule management (CRITICAL: real-time listening + cache + execution)
        self._schedule_cache: ScheduleCache = get_schedule_cache()
        self._schedule_state_tracker: ScheduleStateTracker = get_schedule_state_tracker()
        self._schedule_listener = None
        self._schedule_checker_thread: Optional[threading.Thread] = None
        self._schedule_execution_lock = threading.RLock()
        
        # Listeners
        self._state_listener = None
        self._command_listener = None
        self._hardware_sync_thread: Optional[threading.Thread] = None
        self._processed_commands: set = set()
        
        # Callbacks
        self._state_callbacks: Dict[int, Callable] = {}
        
        # Setup GPIO hardware
        if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            logger.info("✓ GPIO initialized in BCM mode (REAL HARDWARE)")
        else:
            logger.info("⚠️  GPIO simulation mode (no hardware)")
    
    def connect(self):
        """Connect to Firestore and start real-time listeners"""
        try:
            if not firebase_admin._apps:
                logger.error("Firebase not initialized")
                return False
            
            self.firestore_db = firestore.client()
            self._running = True
            
            # 1. Load pin definitions FROM Firestore (single source of truth)
            self._load_pins_from_firestore()
            
            # 2. Initialize GPIO pins on hardware (using Firestore-loaded config)
            self._initialize_hardware_pins()
            
            # 3. Sync initial state TO Firestore (all pins LOW on boot)
            self._sync_initial_state_to_firestore()
            
            # 3. Start REAL-TIME listener on gpioState (Firestore → GPIO)
            self._start_state_listener()
            
            # 4. Start command listener (for explicit commands)
            self._start_command_listener()
            
            # 5. Start SCHEDULE listener (real-time schedule execution with time windows)
            self._start_schedule_listener()
            
            # 6. Start schedule checker (validates time windows periodically)
            self._start_schedule_checker()
            
            # 7. Start hardware readback loop (GPIO → Firestore hardwareState)
            self._start_hardware_sync_loop()
            
            sync_interval = self._get_firestore_sync_interval()
            logger.info(f"✅ GPIO Controller ONLINE - hardware_serial: {self.hardware_serial}")
            logger.info(f"   Listening: devices/{self.hardware_serial}/gpioState")
            logger.info(f"   Listening: schedules (real-time)")
            logger.info(f"   Local hardware read: every {LOCAL_HARDWARE_READ_INTERVAL}s")
            logger.info(f"   Firestore hardwareState write: every {sync_interval}s (configurable)")
            logger.info(f"   Schedule time window check: every 60s")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect GPIO controller: {e}", exc_info=True)
            return False
    
    # ──────────────────────────────────────────────────────────────────
    # INITIALIZATION
    # ──────────────────────────────────────────────────────────────────
    
    def _load_pins_from_firestore(self):
        """Load ALL pin definitions from Firestore (single source of truth).
        
        Reads devices/{hardware_serial}/gpioState to discover which pins exist,
        their names, device types, and active-LOW configuration.
        No hardcoded pins — Firestore is the only authority.
        """
        try:
            device_ref = self.firestore_db.collection('devices').document(self.hardware_serial)
            doc = device_ref.get()
            
            if not doc.exists:
                logger.error(f"Device document not found: devices/{self.hardware_serial}")
                logger.error("No pins to initialize — create the device in the webapp first.")
                return
            
            gpio_state = doc.to_dict().get('gpioState', {})
            if not gpio_state:
                logger.info("No gpioState in Firestore yet — waiting for pins to be added from the webapp.")
                return
            
            self._active_low_pins = set()
            
            for pin_str, pin_data in gpio_state.items():
                try:
                    pin = int(pin_str)
                except (ValueError, TypeError):
                    continue
                
                name = pin_data.get('name', f'GPIO{pin}')
                self._pin_names[pin] = name
                
                # Load PWM duty cycle
                pwm_duty = pin_data.get('pwmDutyCycle', 0)
                self._pwm_duty_cycles[pin] = pwm_duty
                
                # Active-LOW: read from Firestore per-pin field
                if pin_data.get('active_low', False):
                    self._active_low_pins.add(pin)
            
            logger.info(f"📚 Loaded {len(self._pin_names)} pins from Firestore")
            if self._active_low_pins:
                logger.info(f"   Active-LOW pins: {sorted(self._active_low_pins)}")
                
        except Exception as e:
            logger.error(f"Failed to load pins from Firestore: {e}", exc_info=True)
    
    def _initialize_hardware_pins(self):
        """Setup all GPIO pins on the physical hardware.
        
        Uses pin definitions loaded from Firestore by _load_pins_from_firestore().
        SAFETY: Active-LOW relay pins are initialized to HIGH (relay OFF).
        All other pins are initialized to LOW (device OFF).
        """
        if not self._pin_names:
            logger.info("No pins defined yet — add pins from the webapp and they'll be initialized automatically.")
            return
        
        active_low = getattr(self, '_active_low_pins', set())
        
        logger.info(f"🔧 Initializing {len(self._pin_names)} GPIO pins on hardware...")
        if active_low:
            logger.info(f"   Active-LOW relay pins: {sorted(active_low)}")
        
        for pin, name in sorted(self._pin_names.items()):
            try:
                is_active_low = pin in active_low
                
                if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
                    if is_active_low:
                        # Active-LOW: initialize HIGH = relay OFF = device OFF
                        GPIO.setup(pin, GPIO.OUT, initial=GPIO.HIGH)
                    else:
                        # Active-HIGH: initialize LOW = device OFF
                        GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
                
                self._pins_initialized[pin] = 'output'
                self._desired_states[pin] = False  # All pins start as "desired OFF"
                self._hardware_states[pin] = False  # All pins start as "device OFF"
                
                init_level = "HIGH (active-LOW relay)" if is_active_low else "LOW"
                logger.debug(f"  ✓ GPIO{pin}: {name} → OUTPUT, {init_level}")
            except Exception as e:
                logger.warning(f"  ⚠️  GPIO{pin} ({name}) setup failed: {e}")
        
        logger.info(f"✓ {len(self._pins_initialized)} pins initialized on hardware")
    
    def _hot_initialize_pin(self, pin: int, pin_data: dict):
        """Dynamically initialize a NEW pin that just appeared in Firestore.
        
        Called by the real-time listener when the webapp adds a pin.
        Sets up GPIO hardware, starts tracking, and writes back hardwareState.
        """
        name = pin_data.get('name', f'GPIO{pin}')
        mode = pin_data.get('mode', 'output')
        active_low = pin_data.get('active_low', False)
        desired = pin_data.get('state', False)
        enabled = pin_data.get('enabled', True)
        
        logger.info(f"🔌 HOT-INIT: New pin GPIO{pin} ({name}) added from webapp")
        
        # Track active-LOW
        if not hasattr(self, '_active_low_pins'):
            self._active_low_pins = set()
        if active_low:
            self._active_low_pins.add(pin)
        else:
            self._active_low_pins.discard(pin)
        
        # Setup GPIO hardware
        self._setup_pin(pin, mode)
        
        # Track the pin
        self._pin_names[pin] = name
        self._desired_states[pin] = desired
        self._last_firestore_state[pin] = desired
        self._hardware_states[pin] = False  # starts OFF
        
        # Track PWM duty cycle
        pwm_duty = pin_data.get('pwmDutyCycle', 0)
        self._pwm_duty_cycles[pin] = pwm_duty
        
        # Apply desired state if enabled and state=True
        if enabled and desired:
            self._apply_to_hardware(pin, True)
            self._hardware_states[pin] = True
        
        # Apply PWM if set
        if pwm_duty > 0:
            self._set_pwm_duty_cycle(pin, pwm_duty)
        
        # Write back hardwareState so webapp gets immediate confirmation
        hw = self._hardware_states.get(pin, False)
        self._async_firestore_write({
            f'gpioState.{pin}.hardwareState': hw,
            f'gpioState.{pin}.mismatch': desired != hw,
            f'gpioState.{pin}.lastHardwareRead': firestore.SERVER_TIMESTAMP,
        })
        
        logger.info(f"   ✓ GPIO{pin} ({name}): initialized, hw={hw}, pwm={pwm_duty}%, active_low={active_low}")
    
    def _hot_remove_pin(self, pin: int):
        """Clean up a pin that was removed from Firestore (deleted from webapp).
        
        Turns off hardware, removes from all tracking dictionaries.
        """
        name = self._pin_names.get(pin, f'GPIO{pin}')
        logger.info(f"🔌 HOT-REMOVE: GPIO{pin} ({name}) deleted from webapp")
        
        # Turn off hardware first (safety)
        try:
            self._apply_to_hardware(pin, False)
        except Exception:
            pass
        
        # Clean GPIO
        if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
            try:
                GPIO.cleanup(pin)
            except Exception:
                pass
        
        # Remove from all tracking
        self._pins_initialized.pop(pin, None)
        self._pin_names.pop(pin, None)
        self._desired_states.pop(pin, None)
        self._hardware_states.pop(pin, None)
        self._last_firestore_state.pop(pin, None)
        self._simulated_output.pop(pin, None)
        if hasattr(self, '_active_low_pins'):
            self._active_low_pins.discard(pin)
        self._user_override_pins.discard(pin)
        
        logger.info(f"   ✓ GPIO{pin} ({name}): cleaned up")
    
    def _sync_initial_state_to_firestore(self):
        """SAFE boot sync: ALL pins start OFF. Report hardware state.
        
        SAFETY CRITICAL: After every boot, ALL pins are OFF. Stale Firestore
        `state = True` values from previous sessions are CLEARED.
        The user MUST manually turn devices back on from the webapp.
        
        This prevents the AUTO-FIX loop from re-activating devices that were
        left ON before a reboot/crash/power cycle.
        
        EXISTING pins: Reset state=False, update hardwareState, preserve names/config.
        NEW pins: Create with sensible defaults.
        """
        try:
            device_ref = self.firestore_db.collection('devices').document(self.hardware_serial)
            
            # Read current Firestore state
            doc = device_ref.get()
            existing_gpio = {}
            if doc.exists:
                existing_gpio = doc.to_dict().get('gpioState', {})
            
            updates = {}
            pins_existing = 0
            pins_created = 0
            pins_cleared = 0
            
            for pin, legacy_name in self._pin_names.items():
                pin_str = str(pin)
                existing_pin = existing_gpio.get(pin_str, {})
                
                # Read actual hardware state (all pins are LOW after _initialize_hardware_pins)
                hw_state = self._read_hardware_pin(pin)
                if hw_state is None:
                    hw_state = False
                
                if existing_pin:
                    # ── EXISTING PIN: update hardware fields ──
                    updates[f'gpioState.{pin}.hardwareState'] = hw_state
                    updates[f'gpioState.{pin}.lastHardwareRead'] = firestore.SERVER_TIMESTAMP
                    
                    # SAFETY: Always boot with desired = OFF
                    # Do NOT load stale Firestore `state` into _desired_states.
                    # This prevents AUTO-FIX from re-enabling devices after reboot.
                    self._desired_states[pin] = False
                    self._last_firestore_state[pin] = False
                    
                    # Clear stale `state = True` in Firestore so webapp matches reality
                    old_state = existing_pin.get('state', False)
                    if old_state:
                        updates[f'gpioState.{pin}.state'] = False
                        pins_cleared += 1
                        logger.warning(f"🛑 SAFETY: GPIO{pin} had stale state=True — cleared to False")
                    
                    # No mismatch: desired=False, hardware=False (just initialized)
                    updates[f'gpioState.{pin}.mismatch'] = False
                    
                    # Initialize PWM duty cycle if not set
                    if 'pwmDutyCycle' not in existing_pin:
                        updates[f'gpioState.{pin}.pwmDutyCycle'] = 0
                        self._pwm_duty_cycles[pin] = 0
                    
                    pins_existing += 1
                else:
                    # ── NEW PIN: create with full defaults ──────────────────
                    device_type = self._infer_device_type_from_pin(pin)
                    
                    updated_pin_entry = self._name_manager.update_pin_with_smart_name(
                        gpio_number=pin,
                        existing_pin_data=None,
                        device_type=device_type
                    )
                    
                    updates[f'gpioState.{pin}.hardwareState'] = hw_state
                    updates[f'gpioState.{pin}.mismatch'] = False
                    updates[f'gpioState.{pin}.lastHardwareRead'] = firestore.SERVER_TIMESTAMP
                    updates[f'gpioState.{pin}.name'] = updated_pin_entry.get('name', legacy_name)
                    updates[f'gpioState.{pin}.default_name'] = updated_pin_entry.get('default_name', legacy_name)
                    updates[f'gpioState.{pin}.name_customized'] = False
                    updates[f'gpioState.{pin}.pin'] = pin
                    updates[f'gpioState.{pin}.mode'] = 'output'
                    updates[f'gpioState.{pin}.state'] = False
                    updates[f'gpioState.{pin}.enabled'] = True
                    updates[f'gpioState.{pin}.pwmDutyCycle'] = 0
                    
                    # Initialize PWM tracking
                    self._pwm_duty_cycles[pin] = 0
                    
                    if device_type:
                        updates[f'gpioState.{pin}.device_type'] = device_type
                    
                    pins_created += 1
            
            # Always update heartbeat so webapp knows Pi is alive
            updates['lastHeartbeat'] = firestore.SERVER_TIMESTAMP
            updates['status'] = 'online'
            
            device_ref.update(updates)
            
            logger.info(f"✅ SAFE Boot sync: {len(self._pin_names)} pins — ALL OFF")
            logger.info(f"   ├─ Existing: {pins_existing}")
            logger.info(f"   ├─ Created:  {pins_created}")
            if pins_cleared:
                logger.warning(f"   └─ 🛑 CLEARED stale state=True: {pins_cleared} pins (safety)")
            else:
                logger.info(f"   └─ No stale states to clear")
            
        except Exception as e:
            logger.error(f"Failed to sync initial state: {e}")
    
    def _infer_device_type_from_pin(self, pin: int) -> Optional[str]:
        """Infer device type — not used for existing Firestore pins.
        
        For any NEW pin that somehow appears without Firestore metadata,
        default to 'motor' since it's the safest generic type.
        """
        return "motor"
    
    def _is_schedule_running_on_pin(self, pin: int) -> bool:
        """Check if ANY schedule is actively running on a GPIO pin."""
        if not self._schedule_cache:
            return False
        schedules = self._schedule_cache.get_pin_schedules(pin)
        for sched in schedules:
            if self._schedule_state_tracker.is_running(pin, sched.schedule_id):
                return True
        return False
    
    # ──────────────────────────────────────────────────────────────────
    # REAL-TIME STATE LISTENER (Firestore → GPIO)
    # Firestore `state` is the DESIRED state. When it changes, apply it.
    # ──────────────────────────────────────────────────────────────────
    
    def _start_state_listener(self):
        """Listen to gpioState changes on the device document in real-time.
        
        When webapp sets gpioState.{pin}.state = true/false,
        this listener fires INSTANTLY and applies it to hardware.
        """
        try:
            device_ref = self.firestore_db.collection('devices').document(self.hardware_serial)
            
            # Track if this is the initial snapshot (skip to avoid re-applying boot state)
            is_initial = [True]
            
            def on_device_snapshot(doc_snapshot, changes, read_time):
                """Fires whenever the device document changes"""
                try:
                    # Handle both list and single doc formats
                    docs = doc_snapshot if isinstance(doc_snapshot, list) else [doc_snapshot]
                    
                    for doc in docs:
                        if not doc.exists:
                            continue
                        
                        doc_data = doc.to_dict()
                        gpio_state = doc_data.get('gpioState', {})
                        
                        if not gpio_state:
                            continue
                        
                        # On initial snapshot, just record states (don't re-apply)
                        if is_initial[0]:
                            is_initial[0] = False
                            for pin_str, pin_data in gpio_state.items():
                                try:
                                    pin = int(pin_str)
                                    if isinstance(pin_data, dict):
                                        desired = pin_data.get('state', False)
                                        pwm_duty = pin_data.get('pwmDutyCycle', 0)
                                        self._desired_states[pin] = desired
                                        self._last_firestore_state[pin] = desired
                                        self._pwm_duty_cycles[pin] = pwm_duty
                                        # Hot-initialize any pins not yet set up on hardware
                                        if pin not in self._pins_initialized:
                                            self._hot_initialize_pin(pin, pin_data)
                                        # Apply PWM if set
                                        if pwm_duty > 0:
                                            self._set_pwm_duty_cycle(pin, pwm_duty)
                                except (ValueError, TypeError):
                                    pass
                            logger.info(f"📡 Initial GPIO state loaded from Firestore ({len(gpio_state)} pins)")
                            return
                        
                        # ── DYNAMIC PIN DETECTION ──────────────────────
                        # Detect NEW pins added from the webapp and hot-initialize them
                        for pin_str, pin_data in gpio_state.items():
                            try:
                                pin = int(pin_str)
                                if not isinstance(pin_data, dict):
                                    continue
                                if pin not in self._pins_initialized:
                                    self._hot_initialize_pin(pin, pin_data)
                            except (ValueError, TypeError):
                                continue
                        
                        # ── DETECT REMOVED PINS ────────────────────────
                        # If a pin was in our tracking but is gone from Firestore, clean it up
                        current_pins = set()
                        for pin_str in gpio_state:
                            try:
                                current_pins.add(int(pin_str))
                            except (ValueError, TypeError):
                                pass
                        removed = set(self._pins_initialized.keys()) - current_pins
                        for pin in removed:
                            self._hot_remove_pin(pin)
                        
                        # Process state changes — use _last_firestore_state for
                        # change detection so schedules don't corrupt tracking
                        for pin_str, pin_data in gpio_state.items():
                            try:
                                pin = int(pin_str)
                                if not isinstance(pin_data, dict):
                                    continue
                                
                                firestore_state = pin_data.get('state', False)
                                enabled = pin_data.get('enabled', True)
                                prev_firestore = self._last_firestore_state.get(pin)
                                
                                # ── TRACK PWM DUTY CYCLE CHANGES ──────────────────
                                pwm_duty_cycle = pin_data.get('pwmDutyCycle')
                                prev_pwm = self._pwm_duty_cycles.get(pin)
                                pwm_changed = (pwm_duty_cycle != prev_pwm) and (pwm_duty_cycle is not None)
                                
                                # ── TRACK active_low CHANGES ──────────────────
                                new_active_low = pin_data.get('active_low', False)
                                was_active_low = pin in self._active_low_pins
                                active_low_changed = (new_active_low != was_active_low)
                                if active_low_changed:
                                    if new_active_low:
                                        self._active_low_pins.add(pin)
                                    else:
                                        self._active_low_pins.discard(pin)
                                    logger.info(f"🔄 GPIO{pin} active_low changed: {was_active_low} → {new_active_low}")
                                
                                # Detect REAL Firestore `state` change (webapp action)
                                state_changed = (firestore_state != prev_firestore)
                                
                                # Re-apply hardware if state changed OR active_low polarity changed OR PWM changed
                                if state_changed or active_low_changed or pwm_changed:
                                    if state_changed:
                                        self._last_firestore_state[pin] = firestore_state
                                        self._desired_states[pin] = firestore_state
                                    
                                    if not enabled:
                                        logger.warning(f"⚠️  GPIO{pin} change ignored (enabled=false)")
                                        continue
                                    
                                    if state_changed:
                                        logger.info(f"📡 FIRESTORE → GPIO{pin}: {prev_firestore} → {firestore_state}")
                                    elif pwm_changed:
                                        logger.info(f"📡 PWM → GPIO{pin}: {prev_pwm}% → {pwm_duty_cycle}%")
                                    
                                    # If user turned pin OFF while a schedule is running, cancel the schedule
                                    if not firestore_state and self._is_schedule_running_on_pin(pin):
                                        logger.info(f"🛑 User override: stopping schedules on GPIO{pin}")
                                        self._user_override_pins.add(pin)
                                    
                                    # If user turned pin ON, clear any override
                                    if firestore_state:
                                        self._user_override_pins.discard(pin)
                                    
                                    # APPLY TO HARDWARE IMMEDIATELY
                                    if pwm_changed:
                                        self._set_pwm_duty_cycle(pin, pwm_duty_cycle)
                                        self._pwm_duty_cycles[pin] = pwm_duty_cycle
                                    else:
                                        self._apply_to_hardware(pin, firestore_state)
                                    
                                    # Write hardwareState IMMEDIATELY so webapp sees instant feedback
                                    # (don't wait for the 30s sync loop)
                                    if not pwm_changed:  # Only update hardwareState for digital changes
                                        self._hardware_states[pin] = firestore_state
                                        self._async_firestore_write({
                                            f'gpioState.{pin}.hardwareState': firestore_state,
                                            f'gpioState.{pin}.mismatch': False,
                                            f'gpioState.{pin}.lastHardwareRead': firestore.SERVER_TIMESTAMP,
                                        })
                                
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Invalid pin key '{pin_str}': {e}")
                
                except Exception as e:
                    logger.error(f"Error in state listener: {e}", exc_info=True)
            
            self._state_listener = device_ref.on_snapshot(on_device_snapshot)
            logger.info(f"✓ Real-time state listener ACTIVE on devices/{self.hardware_serial}")
            
        except Exception as e:
            logger.error(f"Failed to start state listener: {e}", exc_info=True)
    
    # ──────────────────────────────────────────────────────────────────
    # COMMAND LISTENER (for explicit commands like pin_control)
    # ──────────────────────────────────────────────────────────────────
    
    def _start_command_listener(self):
        """Listen for explicit commands in the commands subcollection"""
        try:
            commands_ref = (self.firestore_db
                           .collection('devices')
                           .document(self.hardware_serial)
                           .collection('commands'))
            
            def on_command_snapshot(doc_snapshot, changes, read_time):
                for change in changes:
                    try:
                        if change.type.name != 'ADDED':
                            if change.type.name == 'REMOVED':
                                self._processed_commands.discard(change.document.id)
                            continue
                        
                        command_id = change.document.id
                        if command_id in self._processed_commands:
                            continue
                        
                        self._processed_commands.add(command_id)
                        command_data = change.document.to_dict()
                        
                        if command_data:
                            self._process_command(command_id, command_data)
                            # Delete command after processing
                            try:
                                change.document.reference.delete()
                            except Exception:
                                pass
                    except Exception as e:
                        logger.error(f"Error processing command: {e}", exc_info=True)
            
            self._command_listener = commands_ref.on_snapshot(on_command_snapshot)
            logger.info(f"✓ Command listener ACTIVE on devices/{self.hardware_serial}/commands/")
            
        except Exception as e:
            logger.error(f"Failed to start command listener: {e}", exc_info=True)
    
    # ──────────────────────────────────────────────────────────────────
    # SCHEDULE LISTENER (real-time schedule execution)
    # ──────────────────────────────────────────────────────────────────
    
    def _start_schedule_listener(self):
        """Start real-time Firestore listener for GPIO schedules.
        
        Monitors gpioState.{pin}.schedules for real-time ADD/MODIFY/DELETE.
        Automatically creates executor threads for new schedules.
        Time windows are strictly enforced (optional, but if set, are STRICT).
        """
        try:
            from src.services.firestore_schedule_listener import create_firestore_schedule_listener
            
            self._schedule_listener = create_firestore_schedule_listener(
                firestore_db=self.firestore_db,
                hardware_serial=self.hardware_serial,
                schedule_cache=self._schedule_cache,
                schedule_executor=self._execute_schedule,
            )
            # Give the listener a reference back to clear user overrides
            self._schedule_listener._controller = self
            
            self._schedule_listener.start_listening()
            logger.info(f"✓ Real-time schedule listener ACTIVE (monitoring {self.hardware_serial})")
            
        except Exception as e:
            logger.error(f"Failed to start schedule listener: {e}", exc_info=True)
    
    def _start_schedule_checker(self):
        """Periodically check time windows and re-evaluate active schedules.
        
        Runs every 60 seconds to:
        - Check if any schedule has entered/exited its time window
        - Start eligible schedules that entered their window but aren't running
        - Schedules that exit their window will self-stop (executor checks window each cycle)
        """
        def check_schedule_windows():
            while True:
                try:
                    time.sleep(60)  # Check every minute
                    
                    if self._schedule_listener:
                        self._schedule_listener.check_and_update_time_windows()
                    
                    # Re-trigger any active schedules that aren't currently running
                    if self._schedule_cache:
                        all_schedules = self._schedule_cache.get_all_schedules()
                        for gpio_num, schedules in all_schedules.items():
                            for sched in schedules:
                                if sched.is_active and sched.enabled:
                                    # Clear stale user overrides — if an active schedule exists,
                                    # the user wants it to run. Overrides should be temporary.
                                    if gpio_num in self._user_override_pins:
                                        self._user_override_pins.discard(gpio_num)
                                        logger.info(f"✅ Cleared stale user override on GPIO{gpio_num} (active schedule found)")
                                    if not self._schedule_state_tracker.is_running(gpio_num, sched.schedule_id):
                                        logger.info(f"⏰ Re-triggering schedule GPIO{gpio_num}/{sched.schedule_id} (in window but not running)")
                                        # Build schedule_data from cached definition
                                        schedule_data = {
                                            'enabled': sched.enabled,
                                            'startTime': sched.start_time,
                                            'endTime': sched.end_time,
                                            'durationSeconds': sched.duration_seconds,
                                            'frequencySeconds': sched.interval_seconds,
                                            'name': sched.description,
                                        }
                                        threading.Thread(
                                            target=self._execute_schedule,
                                            args=(gpio_num, sched.schedule_id, schedule_data),
                                            daemon=True,
                                            name=f"Schedule-{gpio_num}-{sched.schedule_id}"
                                        ).start()
                    
                    logger.debug("✓ Time window check completed")
                    
                except Exception as e:
                    logger.error(f"Error in schedule checker: {e}", exc_info=True)
        
        self._schedule_checker_thread = threading.Thread(
            target=check_schedule_windows,
            daemon=True,
            name="ScheduleCheckerThread"
        )
        self._schedule_checker_thread.start()
        logger.info("✓ Schedule time window checker running (every 60s)")
    
    def _execute_schedule(self, pin: int, schedule_id: str, schedule_data: Dict[str, Any]):
        """Execute a schedule on the given GPIO pin.
        
        Handles webapp's schedule format:
        - startTime/endTime: Time window (HH:MM format) — schedule repeats within this window
        - durationSeconds: How long to keep pin ON per cycle
        - frequencySeconds: How long to PAUSE (OFF) between ON cycles
        
        Example: durationSeconds=2, frequencySeconds=2, startTime=12:25, endTime=12:30
          → Turn ON for 2s, OFF for 2s, ON for 2s, OFF for 2s... until 12:30
        
        Args:
            pin: GPIO pin number
            schedule_id: Schedule document ID
            schedule_data: Schedule configuration from Firestore
        """
        try:
            # Extract schedule parameters
            enabled = schedule_data.get('enabled', True)
            start_time = schedule_data.get('startTime', '')
            end_time = schedule_data.get('endTime', '')
            duration_seconds = schedule_data.get('durationSeconds', 10)
            frequency_seconds = schedule_data.get('frequencySeconds', 10)
            schedule_name = schedule_data.get('name', f'Schedule-{schedule_id}')
            
            if not enabled:
                logger.info(f"⏸️  Schedule {schedule_name} on GPIO{pin} is disabled, skipping")
                return
            
            def is_in_time_window():
                """Check if current time is within the schedule's time window"""
                from datetime import datetime
                now = datetime.now().strftime('%H:%M')
                if not start_time or not end_time:
                    return True  # No time restriction
                if start_time <= end_time:
                    return start_time <= now <= end_time
                else:
                    # Overnight window (e.g., 22:00 to 06:00)
                    return now >= start_time or now <= end_time
            
            # Initial time window check
            if not is_in_time_window():
                logger.info(f"⏭️  Schedule {schedule_name} on GPIO{pin} outside time window ({start_time}-{end_time}), skipping")
                return
            
            with self._schedule_execution_lock:
                # Don't start if already running
                if self._schedule_state_tracker.is_running(pin, schedule_id):
                    logger.debug(f"⏭️  Schedule {schedule_name} on GPIO{pin} already running, skipping")
                    return
                self._schedule_state_tracker.mark_running(pin, schedule_id)
            
            logger.info(f"▶️  Executing '{schedule_name}' on GPIO{pin}: ON for {duration_seconds}s, pause {frequency_seconds}s (window: {start_time}-{end_time})")
            
            # frequencySeconds = the PAUSE (OFF time) between runs
            # Minimum 0.5s to prevent GPIO chatter
            off_time = max(0.5, frequency_seconds)
            cycle_count = 0
            
            # Repeat ON/OFF cycles within the time window
            while is_in_time_window():
                # Re-check if schedule is still enabled (could be modified while running)
                cached = self._schedule_cache.get_schedule(pin, schedule_id)
                if cached and not cached.enabled:
                    logger.info(f"⏸️  Schedule {schedule_name} on GPIO{pin} disabled mid-execution, stopping")
                    break
                
                # Check if user manually overrode this pin (toggled OFF from webapp)
                if pin in self._user_override_pins:
                    logger.info(f"🛑 Schedule {schedule_name} on GPIO{pin} stopped by user override")
                    break
                
                cycle_count += 1
                
                # ON phase
                self._apply_to_hardware(pin, True)
                self._hardware_states[pin] = True
                self._desired_states[pin] = True  # Track schedule intent
                # Write hardwareState on first cycle for instant UI feedback
                if cycle_count == 1:
                    self._async_firestore_write({
                        f'gpioState.{pin}.hardwareState': True,
                        f'gpioState.{pin}.lastHardwareRead': firestore.SERVER_TIMESTAMP,
                    })
                logger.debug(f"   GPIO{pin}: ON (cycle {cycle_count}, {duration_seconds}s)")
                
                # Sleep for duration (ON time), checking time window periodically
                on_remaining = duration_seconds
                while on_remaining > 0 and is_in_time_window():
                    sleep_chunk = min(on_remaining, 1.0)  # Check every second
                    time.sleep(sleep_chunk)
                    on_remaining -= sleep_chunk
                
                if not is_in_time_window():
                    break
                
                # OFF phase
                self._apply_to_hardware(pin, False)
                self._desired_states[pin] = False  # Track schedule intent
                logger.debug(f"   GPIO{pin}: OFF (cycle {cycle_count}, {off_time}s)")
                
                # Sleep for off time, checking time window periodically
                off_remaining = off_time
                while off_remaining > 0 and is_in_time_window():
                    sleep_chunk = min(off_remaining, 1.0)
                    time.sleep(sleep_chunk)
                    off_remaining -= sleep_chunk
            
            # Ensure pin is OFF when schedule ends
            self._apply_to_hardware(pin, False)
            self._hardware_states[pin] = False
            self._desired_states[pin] = False  # Schedule done, desired=OFF
            logger.info(f"✓ Schedule '{schedule_name}' on GPIO{pin} completed ({cycle_count} cycles)")
            
            # Update Firestore with last run time + final hardwareState
            with self._schedule_execution_lock:
                self._schedule_state_tracker.update_last_run(pin, schedule_id, datetime.now())
            
            self._async_firestore_write({
                f'gpioState.{pin}.schedules.{schedule_id}.last_run_at': firestore.SERVER_TIMESTAMP,
                f'gpioState.{pin}.hardwareState': False,
                f'gpioState.{pin}.mismatch': False,
                f'gpioState.{pin}.lastHardwareRead': firestore.SERVER_TIMESTAMP,
            })
            
        except Exception as e:
            logger.error(f"Error executing schedule {schedule_id} on GPIO{pin}: {e}", exc_info=True)
        finally:
            # Always ensure pin is OFF and mark stopped
            try:
                self._apply_to_hardware(pin, False)
            except Exception:
                pass
            with self._schedule_execution_lock:
                self._schedule_state_tracker.mark_stopped(pin, schedule_id)
    
    def _process_command(self, command_id: str, data: Dict[str, Any]):
        """Process an explicit GPIO command"""
        cmd_type = data.get('type')
        pin = data.get('pin')
        action = data.get('action', '').lower()
        duration = data.get('duration')
        
        logger.info(f"⚡ COMMAND {command_id}: type={cmd_type}, pin={pin}, action={action}")
        
        # ── EMERGENCY STOP ──
        if cmd_type == 'emergency_stop':
            logger.critical("🚨🚨🚨 EMERGENCY STOP COMMAND RECEIVED 🚨🚨🚨")
            self.emergency_stop()
            return
        
        if cmd_type == 'pin_control' and pin and action in ('on', 'off'):
            state = action == 'on'
            
            # Update state tracking (commands are explicit user actions)
            self._desired_states[pin] = state
            self._last_firestore_state[pin] = state
            
            # If user is turning OFF while schedule is running, override it
            if not state and self._is_schedule_running_on_pin(pin):
                self._user_override_pins.add(pin)
                logger.info(f"🛑 Command: user override on GPIO{pin}, stopping schedules")
            if state:
                self._user_override_pins.discard(pin)
            
            # 1. Apply to hardware IMMEDIATELY
            self._apply_to_hardware(pin, state)
            self._hardware_states[pin] = state
            
            # 2. Update desired state AND hardwareState in Firestore (async)
            # Writing hardwareState immediately gives instant UI feedback
            self._async_firestore_write({
                f'gpioState.{pin}.state': state,
                f'gpioState.{pin}.hardwareState': state,
                f'gpioState.{pin}.mismatch': False,
                f'gpioState.{pin}.lastUpdated': firestore.SERVER_TIMESTAMP,
                f'gpioState.{pin}.lastHardwareRead': firestore.SERVER_TIMESTAMP,
            })
            
            # 3. Auto-off if duration specified
            if duration and state:
                def auto_off():
                    time.sleep(duration)
                    self._apply_to_hardware(pin, False)
                    self._hardware_states[pin] = False
                    self._async_firestore_write({
                        f'gpioState.{pin}.state': False,
                        f'gpioState.{pin}.hardwareState': False,
                        f'gpioState.{pin}.mismatch': False,
                        f'gpioState.{pin}.lastUpdated': firestore.SERVER_TIMESTAMP,
                        f'gpioState.{pin}.lastHardwareRead': firestore.SERVER_TIMESTAMP,
                    })
                    logger.info(f"✓ GPIO{pin} auto-OFF after {duration}s")
                threading.Thread(target=auto_off, daemon=True).start()
            
            logger.info(f"✓ GPIO{pin} → {action.upper()} (command: {command_id})")
        
        elif cmd_type == 'pwm_control':
            duty_cycle = data.get('duty_cycle', 0)
            self._set_pwm_duty_cycle(pin, duty_cycle)
            logger.info(f"✓ GPIO{pin} PWM → {duty_cycle}% (command: {command_id})")
        else:
            logger.warning(f"Unknown command type: {cmd_type}")
    
    # ──────────────────────────────────────────────────────────────────
    # HARDWARE CONTROL (GPIO reads/writes)
    # ──────────────────────────────────────────────────────────────────
    
    def _apply_to_hardware(self, bcm_pin: int, state: bool):
        """Set a GPIO pin HIGH or LOW on the PHYSICAL hardware.
        Then immediately read it back to verify.
        
        For active-LOW relay pins: the GPIO level is INVERTED.
          state=True  → GPIO LOW  → relay ON  → device ON
          state=False → GPIO HIGH → relay OFF → device OFF
        
        For active-HIGH pins (MOSFETs, LEDs, etc.): normal mapping.
          state=True  → GPIO HIGH → device ON
          state=False → GPIO LOW  → device OFF
        
        CRITICAL: This method does NOT modify _desired_states or _last_firestore_state.
        Those are ONLY set by the state listener (reflecting Firestore's `state` field).
        This prevents schedules from corrupting the change detection.
        
        NO FIRESTORE WRITE HERE. The sync loop handles all Firestore writes
        at the configured interval. This method only touches hardware + memory.
        """
        # Setup pin if not initialized
        if bcm_pin not in self._pins_initialized:
            self._setup_pin(bcm_pin, 'output')
        
        active_low = getattr(self, '_active_low_pins', set())
        is_active_low = bcm_pin in active_low
        
        # Compute actual GPIO level (invert for active-LOW)
        if is_active_low:
            gpio_level = GPIO.LOW if state else GPIO.HIGH
        else:
            gpio_level = GPIO.HIGH if state else GPIO.LOW
        
        # SET the pin
        if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
            GPIO.output(bcm_pin, gpio_level)
        else:
            self._simulated_output[bcm_pin] = state
        
        # READ it back immediately to verify (in-memory only)
        hw_state = self._read_hardware_pin(bcm_pin)
        
        self._hardware_states[bcm_pin] = hw_state
        
        # Check mismatch (log only, no Firestore write)
        mismatch = (state != hw_state) if hw_state is not None else False
        
        if mismatch:
            logger.error(f"🚨 MISMATCH GPIO{bcm_pin}: set={state} but hardware={hw_state}! (active_low={is_active_low})")
        else:
            level_str = "LOW→ON" if is_active_low and state else "HIGH→OFF" if is_active_low else str(state)
            logger.info(f"✓ GPIO{bcm_pin} → {state} (hw confirmed: {hw_state}, active_low={is_active_low})")
        
        # Fire callbacks
        if bcm_pin in self._state_callbacks:
            try:
                self._state_callbacks[bcm_pin](state)
            except Exception as e:
                logger.error(f"Callback error for GPIO{bcm_pin}: {e}")
    
    def _set_pwm_duty_cycle(self, bcm_pin: int, duty_cycle: float):
        """Set PWM duty cycle for a pin (0-100%).
        
        Initializes PWM if not already set up.
        Duty cycle of 0 stops PWM and sets pin LOW.
        """
        # Clamp duty cycle to valid range
        duty_cycle = max(0.0, min(100.0, duty_cycle))
        
        # Setup pin if not initialized
        if bcm_pin not in self._pins_initialized:
            self._setup_pin(bcm_pin, 'output')
        
        # Initialize PWM if not already done
        if bcm_pin not in self._pwm_objects:
            if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
                try:
                    self._pwm_objects[bcm_pin] = GPIO.PWM(bcm_pin, 1000)  # 1kHz frequency
                    self._pwm_objects[bcm_pin].start(0)  # Start with 0% duty cycle
                    logger.info(f"✓ PWM initialized on GPIO{bcm_pin}")
                except Exception as e:
                    logger.error(f"Failed to initialize PWM on GPIO{bcm_pin}: {e}")
                    return
            else:
                # Simulation mode
                self._pwm_objects[bcm_pin] = None
        
        # Set duty cycle
        if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE and self._pwm_objects[bcm_pin]:
            if duty_cycle == 0:
                # Stop PWM and set pin LOW
                self._pwm_objects[bcm_pin].stop()
                GPIO.output(bcm_pin, GPIO.LOW)
                logger.info(f"✓ GPIO{bcm_pin} PWM stopped (0% = OFF)")
            else:
                self._pwm_objects[bcm_pin].ChangeDutyCycle(duty_cycle)
                logger.info(f"✓ GPIO{bcm_pin} PWM → {duty_cycle}%")
        else:
            # Simulation
            logger.info(f"[SIMULATION] GPIO{bcm_pin} PWM → {duty_cycle}%")
        
        # Track current duty cycle
        self._pwm_duty_cycles[bcm_pin] = duty_cycle
    
    def _read_hardware_pin(self, bcm_pin: int) -> Optional[bool]:
        """Read the ACTUAL state of a GPIO pin from hardware.
        
        For active-LOW relay pins, the reading is INVERTED:
          GPIO LOW  → relay ON  → returns True  (device is ON)
          GPIO HIGH → relay OFF → returns False (device is OFF)
        
        For active-HIGH pins: normal mapping.
          GPIO HIGH → returns True  (device is ON)
          GPIO LOW  → returns False (device is OFF)
        """
        try:
            if not GPIO_AVAILABLE or config.SIMULATE_HARDWARE:
                # In simulation, return what we last set via _apply_to_hardware
                return self._simulated_output.get(bcm_pin, False)
            
            # For output pins: read the actual level
            # GPIO.input() works on output pins too on RPi - returns current output level
            val = GPIO.input(bcm_pin)
            
            active_low = getattr(self, '_active_low_pins', set())
            if bcm_pin in active_low:
                # Active-LOW: GPIO LOW = relay ON = True
                return val == GPIO.LOW
            else:
                return val == GPIO.HIGH
            
        except Exception as e:
            logger.error(f"Failed to read GPIO{bcm_pin} hardware state: {e}")
            return None
    
    def _setup_pin(self, bcm_pin: int, mode: str):
        """Setup a GPIO pin (respects active-LOW configuration)"""
        try:


            active_low = getattr(self, '_active_low_pins', set())
            
            if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
                if mode == 'output':
                    if bcm_pin in active_low:
                        GPIO.setup(bcm_pin, GPIO.OUT, initial=GPIO.HIGH)  # Relay OFF
                    else:
                        GPIO.setup(bcm_pin, GPIO.OUT, initial=GPIO.LOW)
                elif mode == 'input':
                    GPIO.setup(bcm_pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
            
            self._pins_initialized[bcm_pin] = mode
            logger.info(f"GPIO{bcm_pin} setup as {mode}")
        except Exception as e:
            logger.error(f"Failed to setup GPIO{bcm_pin}: {e}")
    
    # ──────────────────────────────────────────────────────────────────
    # HARDWARE SYNC LOOP (GPIO → Firestore hardwareState)
    # Reads REAL pin values and pushes them to Firestore periodically
    # ──────────────────────────────────────────────────────────────────
    
    def _get_firestore_sync_interval(self) -> float:
        """Get the Firestore hardwareState write interval from config.
        Falls back to 30s if config_manager not available."""
        if self._config_manager:
            return self._config_manager.get_hardware_state_sync_interval()
        return 30.0
    
    def _start_hardware_sync_loop(self):
        """Start background thread with TWO separate cadences:
        
        1. LOCAL READ (every 5s): Read all GPIO pins from hardware into memory.
           Fast. No network. Catches mismatches immediately.
        
        2. FIRESTORE WRITE (at YOUR configured interval): Batch-write all
           hardwareState values to Firestore. Interval is defined in:
           Firestore → devices/{serial}/config/intervals/hardware_state_sync_interval_s
        """
        def sync_loop():
            sync_interval = self._get_firestore_sync_interval()
            logger.info(f"🔄 Hardware sync loop started")
            logger.info(f"   Local read: every {LOCAL_HARDWARE_READ_INTERVAL}s")
            logger.info(f"   Firestore write: every {sync_interval}s (from config/intervals)")
            
            last_firestore_write = time.time()
            
            while self._running:
                try:
                    time.sleep(LOCAL_HARDWARE_READ_INTERVAL)
                    
                    if not self._running:
                        break
                    
                    # ── LOCAL READ (every 5s) ──────────────────────────
                    # Read ALL pins from hardware into memory. No Firestore.
                    mismatches = []
                    for pin in self._pins_initialized:
                        hw_state = self._read_hardware_pin(pin)
                        if hw_state is None:
                            continue
                        
                        self._hardware_states[pin] = hw_state
                        desired = self._desired_states.get(pin, False)
                        
                        if desired != hw_state:
                            mismatches.append((pin, desired, hw_state))
                    
                    if mismatches:
                        for pin, desired, actual in mismatches:
                            # Auto-fix: if no schedule is actively controlling this pin,
                            # re-apply the desired state. This resolves stuck pins.
                            if not self._is_schedule_running_on_pin(pin):
                                logger.warning(f"🔧 AUTO-FIX GPIO{pin}: desired={desired} but hardware={actual}, re-applying")
                                self._apply_to_hardware(pin, desired)
                                # IMMEDIATELY write to Firestore so webapp is never out of sync
                                hw_after = self._hardware_states.get(pin, desired)
                                self._async_firestore_write({
                                    f'gpioState.{pin}.hardwareState': hw_after,
                                    f'gpioState.{pin}.mismatch': desired != hw_after,
                                    f'gpioState.{pin}.lastHardwareRead': firestore.SERVER_TIMESTAMP,
                                })
                            else:
                                logger.debug(f"⏳ GPIO{pin}: mismatch (desired={desired}, hw={actual}) expected — schedule active")
                    else:
                        logger.debug(f"🔄 Local read: {len(self._pins_initialized)} pins OK")
                    
                    # ── FIRESTORE WRITE (at configured interval) ──────
                    # Re-read interval each cycle so config changes take effect live
                    sync_interval = self._get_firestore_sync_interval()
                    now = time.time()
                    
                    if now - last_firestore_write >= sync_interval:
                        last_firestore_write = now
                        
                        updates = {}
                        for pin in self._pins_initialized:
                            hw_state = self._hardware_states.get(pin)
                            if hw_state is None:
                                continue
                            desired = self._desired_states.get(pin, False)
                            # If a schedule is actively controlling this pin, there's no mismatch
                            is_schedule_controlled = self._is_schedule_running_on_pin(pin)
                            mismatch = (desired != hw_state) and not is_schedule_controlled
                            updates[f'gpioState.{pin}.hardwareState'] = hw_state
                            updates[f'gpioState.{pin}.mismatch'] = mismatch
                            updates[f'gpioState.{pin}.lastHardwareRead'] = firestore.SERVER_TIMESTAMP
                            
                            # Include PWM duty cycle if this pin has PWM active
                            if pin in self._pwm_duty_cycles:
                                updates[f'gpioState.{pin}.pwmDutyCycle'] = self._pwm_duty_cycles[pin]
                        
                        if updates:
                            # Include heartbeat in the same write — saves a separate Firestore call
                            updates['lastHeartbeat'] = firestore.SERVER_TIMESTAMP
                            updates['status'] = 'online'
                            try:
                                device_ref = self.firestore_db.collection('devices').document(self.hardware_serial)
                                device_ref.update(updates)
                                logger.info(f"📤 Firestore sync + heartbeat: {len(self._pins_initialized)} pins written (next in {sync_interval}s)")
                            except Exception as e:
                                logger.error(f"Hardware sync Firestore write failed: {e}")
                
                except Exception as e:
                    logger.error(f"Hardware sync error: {e}", exc_info=True)
            
            logger.info("🔄 Hardware sync loop stopped")
        
        self._hardware_sync_thread = threading.Thread(target=sync_loop, daemon=True, name="gpio-hw-sync")
        self._hardware_sync_thread.start()
    
    # ──────────────────────────────────────────────────────────────────
    # ASYNC FIRESTORE HELPERS (non-blocking writes)
    # ──────────────────────────────────────────────────────────────────
    
    def _async_firestore_write(self, updates: Dict[str, Any]):
        """Write to Firestore in background thread. NEVER blocks GPIO operations."""
        def _write():
            try:
                device_ref = self.firestore_db.collection('devices').document(self.hardware_serial)
                device_ref.update(updates)
            except Exception as e:
                logger.error(f"Async Firestore write failed: {e}")
        
        threading.Thread(target=_write, daemon=True).start()
    
    # ──────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────
    
    def emergency_stop(self):
        """🚨 EMERGENCY STOP: Turn ALL pins OFF immediately.
        
        SAFETY CRITICAL: This is the nuclear option. Every single GPIO pin
        is forced LOW, all schedules are cancelled, all desired states are
        set to False, and Firestore is updated immediately.
        
        Can be triggered by:
          - Firestore command: {type: 'emergency_stop'}
          - Direct API call: controller.emergency_stop()
        """
        logger.critical("🚨 EMERGENCY STOP — forcing ALL pins OFF")
        
        active_low = getattr(self, '_active_low_pins', set())
        updates = {}
        
        for pin in list(self._pins_initialized.keys()):
            try:
                # Force hardware OFF (respecting active-LOW polarity)
                if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
                    if pin in active_low:
                        GPIO.output(pin, GPIO.HIGH)  # Active-LOW: HIGH = relay OFF
                    else:
                        GPIO.output(pin, GPIO.LOW)    # Active-HIGH: LOW = device OFF
                else:
                    self._simulated_output[pin] = False
                
                # Force all tracking to OFF
                self._desired_states[pin] = False
                self._hardware_states[pin] = False
                self._last_firestore_state[pin] = False
                
                # Prepare Firestore batch
                updates[f'gpioState.{pin}.state'] = False
                updates[f'gpioState.{pin}.hardwareState'] = False
                updates[f'gpioState.{pin}.mismatch'] = False
                updates[f'gpioState.{pin}.lastHardwareRead'] = firestore.SERVER_TIMESTAMP
                
                logger.critical(f"  🚨 GPIO{pin} → OFF")
            except Exception as e:
                logger.error(f"  Emergency stop failed for GPIO{pin}: {e}")
        
        # Cancel all schedule overrides
        self._user_override_pins = set(self._pins_initialized.keys())
        
        # Write to Firestore IMMEDIATELY (blocking, not async — this is an emergency)
        try:
            updates['lastHeartbeat'] = firestore.SERVER_TIMESTAMP
            updates['status'] = 'online'
            updates['lastEmergencyStop'] = firestore.SERVER_TIMESTAMP
            device_ref = self.firestore_db.collection('devices').document(self.hardware_serial)
            device_ref.update(updates)
            logger.critical(f"🚨 EMERGENCY STOP COMPLETE — {len(self._pins_initialized)} pins forced OFF, Firestore updated")
        except Exception as e:
            logger.error(f"🚨 Emergency stop Firestore write failed: {e}")
    
    def register_callback(self, bcm_pin: int, callback: Callable[[bool], None]):
        """Register a callback for when a pin state changes"""
        self._state_callbacks[bcm_pin] = callback
    
    def read_pin(self, bcm_pin: int) -> Optional[bool]:
        """Read the current state of a pin from hardware"""
        return self._read_hardware_pin(bcm_pin)
    
    def set_pin(self, bcm_pin: int, state: bool):
        """Manually set a pin state and sync to Firestore"""
        self._desired_states[bcm_pin] = state
        self._last_firestore_state[bcm_pin] = state
        self._apply_to_hardware(bcm_pin, state)
        self._async_firestore_write({
            f'gpioState.{bcm_pin}.state': state,
            f'gpioState.{bcm_pin}.lastUpdated': firestore.SERVER_TIMESTAMP,
        })
    
    def get_pin_states(self) -> Dict[int, Dict[str, Any]]:
        """Get current state of all pins (desired + hardware)"""
        states = {}
        for pin, mode in self._pins_initialized.items():
            states[pin] = {
                'mode': mode,
                'name': self._pin_names.get(pin, 'Unknown'),
                'desired': self._desired_states.get(pin, False),
                'hardware': self._hardware_states.get(pin, False),
                'mismatch': self._desired_states.get(pin) != self._hardware_states.get(pin),
            }
        return states
    
    # ──────────────────────────────────────────────────────────────────
    # GPIO NAMING API (Safe customization)
    # ──────────────────────────────────────────────────────────────────
    
    def rename_gpio_pin(self, gpio_number: int, new_name: str) -> bool:
        """
        Safely rename a GPIO pin from the webapp or API.
        
        Marks the name as user-customized so it won't be overwritten on reboot.
        
        Args:
            gpio_number: GPIO number
            new_name: User-provided custom name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not new_name or not new_name.strip():
                logger.warning(f"Rename GPIO{gpio_number}: Name cannot be empty")
                return False
            
            device_ref = self.firestore_db.collection('devices').document(self.hardware_serial)
            
            # Get current pin data
            doc = device_ref.get()
            if not doc.exists:
                logger.error(f"Device document doesn't exist: {self.hardware_serial}")
                return False
            
            existing_gpio = doc.to_dict().get('gpioState', {})
            existing_pin = existing_gpio.get(str(gpio_number), {})
            
            # Use name manager to safely rename
            updated_entry = self._name_manager.rename_gpio_pin(
                gpio_number=gpio_number,
                new_name=new_name,
                existing_pin_data=existing_pin or {}
            )
            
            # Update Firestore
            updates = {
                f'gpioState.{gpio_number}.name': updated_entry['name'],
                f'gpioState.{gpio_number}.name_customized': updated_entry['name_customized'],
            }
            
            if 'customized_at' in updated_entry:
                updates[f'gpioState.{gpio_number}.customized_at'] = updated_entry['customized_at']
            
            device_ref.update(updates)
            
            # Update local memory
            self._pin_names[gpio_number] = new_name
            
            logger.info(f"✅ GPIO{gpio_number} renamed to '{new_name}' (user-customized)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rename GPIO{gpio_number}: {e}")
            return False
    
    def reset_gpio_name_to_default(self, gpio_number: int) -> bool:
        """
        Reset a GPIO pin name back to the smart default.
        
        Only works if the name was customized. Removes customization flag.
        
        Args:
            gpio_number: GPIO number
            
        Returns:
            True if successful, False otherwise
        """
        try:
            device_ref = self.firestore_db.collection('devices').document(self.hardware_serial)
            
            # Get current pin data
            doc = device_ref.get()
            if not doc.exists:
                logger.error(f"Device document doesn't exist: {self.hardware_serial}")
                return False
            
            existing_gpio = doc.to_dict().get('gpioState', {})
            existing_pin = existing_gpio.get(str(gpio_number), {})
            
            if not existing_pin:
                logger.warning(f"GPIO{gpio_number} not found in Firestore")
                return False
            
            # Use name manager to reset
            updated_entry = self._name_manager.reset_to_smart_default(
                gpio_number=gpio_number,
                existing_pin_data=existing_pin
            )
            
            # Update Firestore
            updates = {
                f'gpioState.{gpio_number}.name': updated_entry['name'],
                f'gpioState.{gpio_number}.default_name': updated_entry['default_name'],
                f'gpioState.{gpio_number}.name_customized': updated_entry.get('name_customized', False),
            }
            
            # Remove customization metadata
            device_ref.update(updates)
            
            # Update local memory
            self._pin_names[gpio_number] = updated_entry['name']
            
            logger.info(f"✅ GPIO{gpio_number} name reset to smart default")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset GPIO{gpio_number} name: {e}")
            return False
    
    def get_gpio_info(self, gpio_number: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed info about a GPIO pin including name and customization status.
        
        Args:
            gpio_number: GPIO number
            
        Returns:
            Dictionary with pin info or None if not found
        """
        try:
            device_ref = self.firestore_db.collection('devices').document(self.hardware_serial)
            doc = device_ref.get()
            
            if not doc.exists:
                return None
            
            existing_gpio = doc.to_dict().get('gpioState', {})
            pin_data = existing_gpio.get(str(gpio_number))
            
            if not pin_data:
                return None
            
            # Get info from naming system
            gpio_info = self._gpio_namer.get_gpio_info(gpio_number)
            
            return {
                **gpio_info,
                'firestore_state': pin_data,
                'current_name': pin_data.get('name'),
                'default_name': pin_data.get('default_name'),
                'name_customized': pin_data.get('name_customized', False),
                'customized_at': pin_data.get('customized_at'),
            }
            
        except Exception as e:
            logger.error(f"Failed to get GPIO{gpio_number} info: {e}")
            return None
    
    def disconnect(self):
        """Stop listeners and cleanup GPIO"""
        logger.info("Disconnecting GPIO controller...")
        self._running = False
        
        if self._state_listener:
            self._state_listener.unsubscribe()
            logger.info("  State listener stopped")
        
        if self._command_listener:
            self._command_listener.unsubscribe()
            logger.info("  Command listener stopped")
        
        if self._schedule_listener:
            self._schedule_listener.stop_listening()
            logger.info("  Schedule listener stopped")
        
        if self._hardware_sync_thread and self._hardware_sync_thread.is_alive():
            self._hardware_sync_thread.join(timeout=5)
            logger.info("  Hardware sync thread stopped")
        
        if self._schedule_checker_thread and self._schedule_checker_thread.is_alive():
            # Daemon thread will auto-exit when we set _running = False
            self._schedule_checker_thread.join(timeout=5)
            logger.info("  Schedule checker thread stopped")
        
        if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
            # Stop all PWM objects
            for pin, pwm_obj in self._pwm_objects.items():
                if pwm_obj:
                    try:
                        pwm_obj.stop()
                        logger.info(f"  PWM stopped on GPIO{pin}")
                    except Exception as e:
                        logger.error(f"Error stopping PWM on GPIO{pin}: {e}")
            GPIO.cleanup()
            logger.info("  GPIO cleanup complete")
        
        logger.info("✓ GPIO controller disconnected")


# ──────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────

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
