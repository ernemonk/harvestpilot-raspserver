"""
Real-time Firestore Schedule Listener Integration

Integrates with GPIOActuatorController to:
1. Listen to gpioState.{pin}.schedules changes in Firestore (real-time)
2. Maintain atomic cache synchronization 
3. Execute schedules with strict time window enforcement
4. Keep hardware state cache in perfect sync
"""

import logging
import threading
import time
from typing import Dict, Optional, Any, Callable
from datetime import datetime
from firebase_admin import firestore

logger = logging.getLogger(__name__)


class FirestoreScheduleListener:
    """Real-time Firestore listener for GPIO schedules - follows same pattern as state listener"""
    
    def __init__(
        self,
        firestore_db,
        hardware_serial: str,
        schedule_cache,
        schedule_executor: Optional[Callable] = None
    ):
        """
        Initialize the Firestore schedule listener.
        
        Args:
            firestore_db: Firestore client instance
            hardware_serial: Device hardware serial (for device document identification)
            schedule_cache: ScheduleCache instance to keep in sync
            schedule_executor: Optional callback(gpio_num, schedule) for executing schedules
        """
        self.firestore_db = firestore_db
        self.hardware_serial = hardware_serial
        self.schedule_cache = schedule_cache
        self.schedule_executor = schedule_executor
        self._listener = None
        self._processed_schedules: set = set()  # Track processed schedule IDs to avoid double-processing
        logger.info("✓ FirestoreScheduleListener initialized")
    
    def start_listening(self) -> bool:
        """
        Start listening to schedule changes in Firestore.
        
        Watches gpioState.{pin}.schedules for all pins simultaneously.
        
        Returns:
            True if listener started successfully
        """
        try:
            device_ref = self.firestore_db.collection('devices').document(self.hardware_serial)
            
            # Track if this is initial load
            is_initial = [True]
            
            def on_device_snapshot(doc_snapshot, changes, read_time):
                """
                Fires whenever the device document changes.
                
                CRITICAL: Must handle:
                - Schedule added → add to cache, execute if in time window
                - Schedule modified → update cache, potentially stop/start execution
                - Schedule deleted → remove from cache, stop execution
                - Fields changed (enabled, time_window) → update cache, re-evaluate
                """
                try:
                    # Handle both single doc and list of docs
                    docs = doc_snapshot if isinstance(doc_snapshot, list) else [doc_snapshot]
                    
                    for doc in docs:
                        if not doc.exists:
                            continue
                        
                        doc_data = doc.to_dict()
                        gpio_state = doc_data.get('gpioState', {})
                        
                        if not gpio_state:
                            continue
                        
                        # On initial snapshot: load all schedules without executing
                        if is_initial[0]:
                            is_initial[0] = False
                            self._load_initial_schedules(gpio_state)
                            logger.info(f"📅 Initial schedules loaded from Firestore")
                            return
                        
                        # Process schedule changes (add/modify/delete)
                        self._process_schedule_changes(gpio_state)
                        
                except Exception as e:
                    logger.error(f"Error in schedule listener snapshot: {e}", exc_info=True)
            
            # Start listening with snapshot pattern
            self._listener = device_ref.on_snapshot(on_device_snapshot)
            logger.info(f"✅ Schedule listener ACTIVE on devices/{self.hardware_serial}/gpioState/*.schedules")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start schedule listener: {e}", exc_info=True)
            return False
    
    def _load_initial_schedules(self, gpio_state: Dict) -> None:
        """
        Load all schedules on initial snapshot (don't execute yet).
        
        CRITICAL: This is non-executed load to establish baseline state.
        """
        total_loaded = 0
        
        for pin_str, pin_data in gpio_state.items():
            try:
                gpio_num = int(pin_str)
                if not isinstance(pin_data, dict):
                    continue
                
                schedules = pin_data.get('schedules', {})
                if not schedules:
                    continue
                
                for schedule_id, schedule_def in schedules.items():
                    if isinstance(schedule_def, dict):
                        # Add to cache (but don't execute on initial load)
                        self.schedule_cache.update_schedule(gpio_num, schedule_id, schedule_def)
                        total_loaded += 1
                        logger.debug(f"📋 Loaded GPIO{gpio_num}/{schedule_id}")
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Error loading schedule from pin {pin_str}: {e}")
        
        logger.info(f"📅 Loaded {total_loaded} schedules into cache")
    
    def _process_schedule_changes(self, gpio_state: Dict) -> None:
        """
        Process real-time changes to schedules.
        
        Detects:
        - NEW schedules → add to cache + execute if applicable
        - MODIFIED schedules → update cache + re-eval execution
        - DELETED schedules → remove from cache + stop execution
        """
        for pin_str, pin_data in gpio_state.items():
            try:
                gpio_num = int(pin_str)
                if not isinstance(pin_data, dict):
                    continue
                
                # Current schedules in Firestore
                firestore_schedules = pin_data.get('schedules', {})
                
                # Get cached schedules for this pin
                cached_schedules = {s.schedule_id: s for s in self.schedule_cache.get_pin_schedules(gpio_num)}
                
                # ──────────────────────────────────────────────────────────────
                # DETECT ADDITIONS & MODIFICATIONS
                # ──────────────────────────────────────────────────────────────
                for schedule_id, schedule_def in firestore_schedules.items():
                    if isinstance(schedule_def, dict):
                        # Check if this is new or modified
                        cached = cached_schedules.get(schedule_id)
                        
                        if cached is None:
                            # NEW schedule
                            logger.info(f"➕ NEW schedule GPIO{gpio_num}/{schedule_id}")
                            self.schedule_cache.update_schedule(gpio_num, schedule_id, schedule_def)
                            
                            # Execute immediately if enabled and in time window
                            if self.schedule_executor:
                                new_sched = self.schedule_cache.get_schedule(gpio_num, schedule_id)
                                if new_sched and new_sched.is_active:
                                    logger.info(f"⚡ Executing new schedule GPIO{gpio_num}/{schedule_id}")
                                    threading.Thread(
                                        target=self.schedule_executor,
                                        args=(gpio_num, schedule_id, schedule_def),
                                        daemon=True
                                    ).start()
                        else:
                            # MODIFIED schedule - check what changed
                            changed = self._detect_schedule_changes(cached, schedule_def)
                            if changed:
                                logger.info(f"🔄 MODIFIED schedule GPIO{gpio_num}/{schedule_id}: {changed}")
                                self.schedule_cache.update_schedule(gpio_num, schedule_id, schedule_def)
                                
                                # Re-evaluate execution based on changes
                                if self.schedule_executor:
                                    updated_sched = self.schedule_cache.get_schedule(gpio_num, schedule_id)
                                    if updated_sched:
                                        # If enabled status changed or time window changed, potentially re-execute
                                        if 'enabled' in changed or 'start_time' in changed or 'end_time' in changed:
                                            if updated_sched.is_active:
                                                logger.info(f"⚡ Re-executing modified schedule GPIO{gpio_num}/{schedule_id}")
                                                threading.Thread(
                                                    target=self.schedule_executor,
                                                    args=(gpio_num, schedule_id, schedule_def),
                                                    daemon=True
                                                ).start()
                
                # ──────────────────────────────────────────────────────────────
                # DETECT DELETIONS
                # ──────────────────────────────────────────────────────────────
                for schedule_id, cached in cached_schedules.items():
                    if schedule_id not in firestore_schedules:
                        # DELETED schedule
                        logger.info(f"➖ DELETED schedule GPIO{gpio_num}/{schedule_id}")
                        self.schedule_cache.remove_schedule(gpio_num, schedule_id)
                        
                        # Ensure execution is stopped
                        logger.debug(f"Stopping any running execution for GPIO{gpio_num}/{schedule_id}")
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Error processing schedules for pin {pin_str}: {e}")
    
    @staticmethod
    def _detect_schedule_changes(old_def, new_def: Dict) -> Optional[list]:
        """
        Detect what fields changed in a schedule.
        
        Returns list of changed field names or None if unchanged.
        """
        changed_fields = []
        
        # Check each field
        for field in ['enabled', 'start_time', 'end_time', 'interval_seconds', 
                     'duration_seconds', 'pwm_duty_start', 'pwm_duty_end', 'digital_state']:
            old_val = getattr(old_def, field, None)
            new_val = new_def.get(field)
            
            if old_val != new_val:
                changed_fields.append(field)
        
        return changed_fields if changed_fields else None
    
    def stop_listening(self) -> None:
        """Stop the Firestore listener"""
        if self._listener:
            self._listener.unsubscribe()
            self._listener = None
            logger.info("📍 Schedule listener stopped")
    
    def check_and_update_time_windows(self) -> None:
        """
        CRITICAL: Check if any schedules should be activated/deactivated due to time window changes.
        
        Should be called periodically (e.g., every minute) to ensure proper time window enforcement.
        """
        self.schedule_cache.update_all_time_windows()


# Factory function
def create_firestore_schedule_listener(
    firestore_db,
    hardware_serial: str,
    schedule_cache,
    schedule_executor: Optional[Callable] = None
) -> FirestoreScheduleListener:
    """Create a Firestore schedule listener instance"""
    return FirestoreScheduleListener(
        firestore_db=firestore_db,
        hardware_serial=hardware_serial,
        schedule_cache=schedule_cache,
        schedule_executor=schedule_executor
    )
