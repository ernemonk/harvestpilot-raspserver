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
        
        # Firestore state tracking (CRITICAL: separate from _desired_states)
        # _last_firestore_state ONLY tracks what Firestore's `state` field says.
        # Used by the state listener for REAL change detection.
        # _desired_states gets clobbered by schedules; this dict does NOT.
        self._last_firestore_state: Dict[int, bool] = {}
        
        # User override tracking — when user explicitly toggles a pin OFF
        # while a schedule is running, the schedule should stop.
        self._user_override_pins: set = set()
        
        # Simulation output tracking (for non-hardware environments)
        self._simulated_output: Dict[int, bool] = {}
        
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
            
            # 1. Initialize GPIO pins on hardware
            self._initialize_hardware_pins()
            
            # 2. Sync initial state TO Firestore (all pins LOW on boot)
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
    
    def _initialize_hardware_pins(self):
        """Setup all GPIO pins on the physical hardware"""
        all_pins = self._get_all_pin_definitions()
        
        logger.info(f"🔧 Initializing {len(all_pins)} GPIO pins on hardware...")
        
        for pin, name in sorted(all_pins.items()):
            try:
                if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
                    GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
                
                self._pins_initialized[pin] = 'output'
                self._desired_states[pin] = False
                self._hardware_states[pin] = False
                self._pin_names[pin] = name
                logger.debug(f"  ✓ GPIO{pin}: {name} → OUTPUT, LOW")
            except Exception as e:
                logger.warning(f"  ⚠️  GPIO{pin} ({name}) setup failed: {e}")
        
        logger.info(f"✓ {len(self._pins_initialized)} pins initialized on hardware")
    
    def _get_all_pin_definitions(self) -> Dict[int, str]:
        """Build complete pin list from config"""
        pins = {
            config.PUMP_PWM_PIN: "Pump PWM",
            config.PUMP_RELAY_PIN: "Pump Relay",
            config.LED_PWM_PIN: "LED PWM",
            config.LED_RELAY_PIN: "LED Relay",
        }
        for motor in config.MOTOR_PINS:
            pins[motor['pwm']] = f"Motor {motor['tray']} PWM"
            pins[motor['dir']] = f"Motor {motor['tray']} Direction"
            pins[motor['home']] = f"Motor {motor['tray']} Home Sensor"
            pins[motor['end']] = f"Motor {motor['tray']} End Sensor"
        return pins
    
    def _sync_initial_state_to_firestore(self):
        """Register pins in Firestore on boot with smart naming.
        
        CRITICAL: NEVER overwrites user-customized names!
        
        PI-OWNED fields (written every boot):
          hardwareState, mismatch, lastHardwareRead, name, pin, mode
          (but ONLY updates name if not user-customized)
        
        WEBAPP-OWNED fields (NEVER overwritten by Pi):
          state, enabled
        
        SAFE PIN NAMING:
          NEW pins:              Create with smart default name (GPIO + capabilities)
          OLD user-customized:   PRESERVE (name_customized flag = true)
          OLD default names:     CAN UPDATE to smarter default
        """
        try:
            device_ref = self.firestore_db.collection('devices').document(self.hardware_serial)
            
            # Read current Firestore state to avoid overwriting webapp fields
            doc = device_ref.get()
            existing_gpio = {}
            if doc.exists:
                existing_gpio = doc.to_dict().get('gpioState', {})
            
            updates = {}
            pins_preserved = 0
            pins_created = 0
            pins_updated = 0
            
            for pin, legacy_name in self._pin_names.items():
                pin_str = str(pin)
                existing_pin = existing_gpio.get(pin_str, {})
                
                # ──────────────────────────────────────────────────────────────
                # SAFELY UPDATE PIN NAME (NON-DESTRUCTIVE)
                # ──────────────────────────────────────────────────────────────
                
                # Try to get device type from config
                device_type = self._infer_device_type_from_pin(pin)
                
                # Use name manager to determine what to do with the name
                updated_pin_entry = self._name_manager.update_pin_with_smart_name(
                    gpio_number=pin,
                    existing_pin_data=existing_pin if existing_pin else None,
                    device_type=device_type
                )
                
                # Track what happened
                if existing_pin and existing_pin.get('name_customized'):
                    pins_preserved += 1
                elif not existing_pin:
                    pins_created += 1
                else:
                    pins_updated += 1
                
                # Update ALL pi-owned fields
                updates[f'gpioState.{pin}.hardwareState'] = False
                updates[f'gpioState.{pin}.mismatch'] = False
                updates[f'gpioState.{pin}.lastHardwareRead'] = firestore.SERVER_TIMESTAMP
                updates[f'gpioState.{pin}.name'] = updated_pin_entry.get('name')
                updates[f'gpioState.{pin}.default_name'] = updated_pin_entry.get('default_name')
                updates[f'gpioState.{pin}.name_customized'] = updated_pin_entry.get('name_customized', False)
                updates[f'gpioState.{pin}.pin'] = pin
                updates[f'gpioState.{pin}.mode'] = 'output'
                
                # Copy over device_type if present
                if 'device_type' in updated_pin_entry:
                    updates[f'gpioState.{pin}.device_type'] = updated_pin_entry.get('device_type')
                
                # Copy over customization metadata if present
                if 'customized_at' in updated_pin_entry:
                    updates[f'gpioState.{pin}.customized_at'] = updated_pin_entry.get('customized_at')
                
                # Webapp-owned: only set defaults if pin doesn't exist yet
                if not existing_pin:
                    updates[f'gpioState.{pin}.state'] = False
                    updates[f'gpioState.{pin}.enabled'] = True
                else:
                    # Load webapp's desired state into memory
                    webapp_state = existing_pin.get('state', False)
                    self._desired_states[pin] = webapp_state
                    self._last_firestore_state[pin] = webapp_state
            
            device_ref.update(updates)
            
            # Log summary
            logger.info(f"✅ Registered {len(self._pins_initialized)} pins in Firestore")
            logger.info(f"   ├─ Created (new): {pins_created}")
            logger.info(f"   ├─ Updated (improved naming): {pins_updated}")
            logger.info(f"   └─ Preserved (user-customized): {pins_preserved}")
            logger.info(f"   Webapp fields (state, enabled) preserved")
            
        except Exception as e:
            logger.error(f"Failed to sync initial state: {e}")
    
    def _infer_device_type_from_pin(self, pin: int) -> Optional[str]:
        """Try to infer device type from pin number"""
        # Map from hardcoded pins to device types
        device_type_map = {
            17: "pump",    # Pump PWM
            19: "pump",    # Pump Relay
            18: "light",   # LED PWM
            13: "light",   # LED Relay
            4: "sensor",   # DHT
            27: "sensor",  # Water level
            # Motors (2, 3, 5, 6, 12, 13...)
        }
        
        device_type = device_type_map.get(pin)
        if not device_type:
            # Assume it's a motor if it's in the motor pins list
            for motor in config.MOTOR_PINS:
                if pin in [motor.get('pwm'), motor.get('dir'), motor.get('home'), motor.get('end')]:
                    device_type = "motor"
                    break
        
        return device_type
    
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
                                        self._desired_states[pin] = desired
                                        self._last_firestore_state[pin] = desired
                                except (ValueError, TypeError):
                                    pass
                            logger.info(f"📡 Initial GPIO state loaded from Firestore ({len(gpio_state)} pins)")
                            return
                        
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
                                
                                # Detect REAL Firestore `state` change (webapp action)
                                state_changed = (firestore_state != prev_firestore)
                                
                                if state_changed:
                                    self._last_firestore_state[pin] = firestore_state
                                    self._desired_states[pin] = firestore_state
                                    
                                    if not enabled:
                                        logger.warning(f"⚠️  GPIO{pin} state change ignored (enabled=false)")
                                        continue
                                    
                                    logger.info(f"📡 FIRESTORE → GPIO{pin}: {prev_firestore} → {firestore_state}")
                                    
                                    # If user turned pin OFF while a schedule is running, cancel the schedule
                                    if not firestore_state and self._is_schedule_running_on_pin(pin):
                                        logger.info(f"🛑 User override: stopping schedules on GPIO{pin}")
                                        self._user_override_pins.add(pin)
                                    
                                    # If user turned pin ON, clear any override
                                    if firestore_state:
                                        self._user_override_pins.discard(pin)
                                    
                                    # APPLY TO HARDWARE IMMEDIATELY
                                    self._apply_to_hardware(pin, firestore_state)
                                
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
                                    # Don't re-trigger if user overrode this pin
                                    if gpio_num in self._user_override_pins:
                                        continue
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
        - frequencySeconds: Total cycle length (ON + OFF time)
        
        Example: durationSeconds=2, frequencySeconds=3, startTime=00:48, endTime=00:54
          → Turn ON for 2s, OFF for 1s, repeat until 00:54
        
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
            
            logger.info(f"▶️  Executing '{schedule_name}' on GPIO{pin}: ON for {duration_seconds}s every {frequency_seconds}s (window: {start_time}-{end_time})")
            
            # Ensure OFF time exists (frequency must be > duration)
            off_time = max(0, frequency_seconds - duration_seconds)
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
                logger.debug(f"   GPIO{pin}: OFF (cycle {cycle_count}, {off_time}s)")
                
                # Sleep for off time, checking time window periodically
                off_remaining = off_time
                while off_remaining > 0 and is_in_time_window():
                    sleep_chunk = min(off_remaining, 1.0)
                    time.sleep(sleep_chunk)
                    off_remaining -= sleep_chunk
            
            # Ensure pin is OFF when schedule ends
            self._apply_to_hardware(pin, False)
            logger.info(f"✓ Schedule '{schedule_name}' on GPIO{pin} completed ({cycle_count} cycles)")
            
            # Update Firestore with last run time
            with self._schedule_execution_lock:
                self._schedule_state_tracker.update_last_run(pin, schedule_id, datetime.now())
            
            self._async_firestore_write({
                f'gpioState.{pin}.schedules.{schedule_id}.last_run_at': firestore.SERVER_TIMESTAMP,
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
            
            # 2. Update desired state in Firestore (async)
            self._async_firestore_write({
                f'gpioState.{pin}.state': state,
                f'gpioState.{pin}.lastUpdated': firestore.SERVER_TIMESTAMP,
            })
            
            # 3. Auto-off if duration specified
            if duration and state:
                def auto_off():
                    time.sleep(duration)
                    self._apply_to_hardware(pin, False)
                    self._async_firestore_write({
                        f'gpioState.{pin}.state': False,
                        f'gpioState.{pin}.lastUpdated': firestore.SERVER_TIMESTAMP,
                    })
                    logger.info(f"✓ GPIO{pin} auto-OFF after {duration}s")
                threading.Thread(target=auto_off, daemon=True).start()
            
            logger.info(f"✓ GPIO{pin} → {action.upper()} (command: {command_id})")
        
        elif cmd_type == 'pwm_control':
            logger.info(f"PWM command: pin={pin}, duty={data.get('duty_cycle')}%")
        else:
            logger.warning(f"Unknown command type: {cmd_type}")
    
    # ──────────────────────────────────────────────────────────────────
    # HARDWARE CONTROL (GPIO reads/writes)
    # ──────────────────────────────────────────────────────────────────
    
    def _apply_to_hardware(self, bcm_pin: int, state: bool):
        """Set a GPIO pin HIGH or LOW on the PHYSICAL hardware.
        Then immediately read it back to verify.
        
        CRITICAL: This method does NOT modify _desired_states or _last_firestore_state.
        Those are ONLY set by the state listener (reflecting Firestore's `state` field).
        This prevents schedules from corrupting the change detection.
        
        NO FIRESTORE WRITE HERE. The sync loop handles all Firestore writes
        at the configured interval. This method only touches hardware + memory.
        """
        # Setup pin if not initialized
        if bcm_pin not in self._pins_initialized:
            self._setup_pin(bcm_pin, 'output')
        
        # SET the pin
        if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
            GPIO.output(bcm_pin, GPIO.HIGH if state else GPIO.LOW)
        else:
            self._simulated_output[bcm_pin] = state
        
        # READ it back immediately to verify (in-memory only)
        hw_state = self._read_hardware_pin(bcm_pin)
        
        self._hardware_states[bcm_pin] = hw_state
        
        # Check mismatch (log only, no Firestore write)
        mismatch = (state != hw_state) if hw_state is not None else False
        
        if mismatch:
            logger.error(f"🚨 MISMATCH GPIO{bcm_pin}: set={state} but hardware={hw_state}!")
        else:
            logger.info(f"✓ GPIO{bcm_pin} → {state} (hardware confirmed: {hw_state})")
        
        # Fire callbacks
        if bcm_pin in self._state_callbacks:
            try:
                self._state_callbacks[bcm_pin](state)
            except Exception as e:
                logger.error(f"Callback error for GPIO{bcm_pin}: {e}")
    
    def _read_hardware_pin(self, bcm_pin: int) -> Optional[bool]:
        """Read the ACTUAL state of a GPIO pin from hardware.
        
        For output pins, we temporarily switch to input to read,
        then switch back to output. This gives the REAL value.
        """
        try:
            if not GPIO_AVAILABLE or config.SIMULATE_HARDWARE:
                # In simulation, return what we last set via _apply_to_hardware
                return self._simulated_output.get(bcm_pin, False)
            
            # For output pins: read the actual level
            # GPIO.input() works on output pins too on RPi - returns current output level
            val = GPIO.input(bcm_pin)
            return val == GPIO.HIGH
            
        except Exception as e:
            logger.error(f"Failed to read GPIO{bcm_pin} hardware state: {e}")
            return None
    
    def _setup_pin(self, bcm_pin: int, mode: str):
        """Setup a GPIO pin"""
        try:
            if GPIO_AVAILABLE and not config.SIMULATE_HARDWARE:
                if mode == 'output':
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
                            updates[f'gpioState.{pin}.hardwareState'] = hw_state
                            updates[f'gpioState.{pin}.mismatch'] = desired != hw_state
                            updates[f'gpioState.{pin}.lastHardwareRead'] = firestore.SERVER_TIMESTAMP
                        
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
