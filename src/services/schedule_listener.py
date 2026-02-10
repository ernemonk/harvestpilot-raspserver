"""
GPIO Schedule Listener & Executor - Real-time Firestore-backed scheduling with strict time windows

CRITICAL ARCHITECTURE:
  - Real-time Firestore listener (like state listener)
  - Atomic cache synchronization with hardware
  - Thread-safe schedule tracking
  - Strict time window enforcement (start_time → end_time MUST be honored)
  - No polling - reactive only

SCHEDULE STRUCTURE:
  gpioState.{pin}.schedules = {
    "schedule-id": {
      "type": "pwm_cycle",
      "enabled": true,
      "start_time": "06:00",  # Optional - time window start
      "end_time": "22:00",    # Optional - time window end (STRICT)
      "pwm_duty_start": 80,
      "interval_seconds": 3600,
      "duration_seconds": 300,
      ...
    }
  }

TIME WINDOW RULES:
  - If no start_time/end_time: Schedule runs anytime (24/7)
  - If start_time AND end_time: Schedule ONLY runs between these times (STRICT)
  - Current time OUTSIDE window: Schedule NOT executed, cached but inactive
  - Time window change: Cache updates immediately, execution re-evaluated

CACHE SYNC CRITICAL:
  - Firestore change detected → Cache updated atomically
  - Schedule execution → Applied to hardware
  - Cache state → Always reflects Firestore truth
  - No stale schedules in cache
"""

import logging
import threading
import time
from typing import Dict, Optional, List, Any
from datetime import datetime, time as datetime_time
from dataclasses import dataclass, field
import firebase_admin
from firebase_admin import firestore

logger = logging.getLogger(__name__)


@dataclass
class ScheduleDefinition:
    """In-memory representation of a schedule"""
    schedule_id: str
    gpio_number: int
    schedule_type: str
    enabled: bool
    start_time: Optional[str] = None      # "HH:MM" or None
    end_time: Optional[str] = None        # "HH:MM" or None
    interval_seconds: Optional[int] = None
    duration_seconds: Optional[int] = None
    pwm_duty_start: Optional[int] = None
    pwm_duty_end: Optional[int] = None
    pwm_fade_duration: Optional[int] = None
    digital_state: Optional[bool] = None
    read_interval_seconds: Optional[int] = None
    store_readings: bool = True
    description: str = ""
    last_run_at: Optional[datetime] = None
    
    # Execution tracking
    is_active: bool = field(default=False)  # Currently executing?
    _execution_thread: Optional[threading.Thread] = field(default=None)
    _execution_lock = threading.Lock()


class TimeWindowValidator:
    """Validates if current time is within schedule's time window (if specified)"""
    
    @staticmethod
    def is_in_window(start_time: Optional[str], end_time: Optional[str]) -> bool:
        """
        Check if current time is within the time window.
        
        CRITICAL: This is STRICT time window enforcement.
        If times are specified, schedule ONLY runs within that window.
        
        Args:
            start_time: "HH:MM" format or None (no start limit)
            end_time: "HH:MM" format or None (no end limit)
            
        Returns:
            True if current time is within window, False otherwise
        """
        # No time restriction
        if not start_time and not end_time:
            return True
        
        now = datetime.now().time()
        
        try:
            # Parse times
            if start_time:
                start_parts = start_time.split(":")
                start = datetime_time(int(start_parts[0]), int(start_parts[1]))
            else:
                start = datetime_time(0, 0)  # Midnight
            
            if end_time:
                end_parts = end_time.split(":")
                end = datetime_time(int(end_parts[0]), int(end_parts[1]))
            else:
                end = datetime_time(23, 59)  # 23:59
            
            # Check if within window
            if start <= end:
                # Same day (e.g., 06:00 to 22:00)
                return start <= now <= end
            else:
                # Crosses midnight (e.g., 22:00 to 06:00 next day)
                return now >= start or now <= end
                
        except (ValueError, IndexError) as e:
            logger.error(f"Error parsing time window {start_time}-{end_time}: {e}")
            return False
    
    @staticmethod
    def should_skip_due_to_window(start_time: Optional[str], end_time: Optional[str]) -> bool:
        """
        Check if schedule should be SKIPPED due to time window constraint.
        
        Returns True if schedule would be outside window.
        """
        return not TimeWindowValidator.is_in_window(start_time, end_time)


class ScheduleCache:
    """Thread-safe cache of GPIO schedules synchronized with Firestore"""
    
    def __init__(self):
        self._cache: Dict[int, Dict[str, ScheduleDefinition]] = {}  # {pin: {schedule_id: def}}
        self._lock = threading.RLock()
        logger.info("✓ Schedule cache initialized")
    
    def update_schedule(self, gpio_number: int, schedule_id: str, schedule_data: Dict) -> ScheduleDefinition:
        """
        Update or create a schedule in cache.
        
        ATOMIC OPERATION: All-or-nothing update to maintain consistency.
        """
        with self._lock:
            if gpio_number not in self._cache:
                self._cache[gpio_number] = {}
            
            # Create schedule definition
            # Support both camelCase (webapp) and snake_case field names
            sched = ScheduleDefinition(
                schedule_id=schedule_id,
                gpio_number=gpio_number,
                schedule_type=schedule_data.get('type', 'unknown'),
                enabled=schedule_data.get('enabled', True),
                start_time=schedule_data.get('startTime') or schedule_data.get('start_time'),
                end_time=schedule_data.get('endTime') or schedule_data.get('end_time'),
                interval_seconds=schedule_data.get('frequencySeconds') or schedule_data.get('interval_seconds'),
                duration_seconds=schedule_data.get('durationSeconds') or schedule_data.get('duration_seconds'),
                pwm_duty_start=schedule_data.get('pwm_duty_start'),
                pwm_duty_end=schedule_data.get('pwm_duty_end'),
                pwm_fade_duration=schedule_data.get('pwm_fade_duration'),
                digital_state=schedule_data.get('digital_state'),
                read_interval_seconds=schedule_data.get('read_interval_seconds'),
                store_readings=schedule_data.get('store_readings', True),
                description=schedule_data.get('name') or schedule_data.get('description', ''),
                last_run_at=None,
                is_active=False
            )
            
            self._cache[gpio_number][schedule_id] = sched
            
            # Determine if active based on time window
            if sched.enabled and not TimeWindowValidator.should_skip_due_to_window(sched.start_time, sched.end_time):
                sched.is_active = True
                logger.info(f"✅ Schedule GPIO{gpio_number}/{schedule_id} - ACTIVE (within time window)")
            else:
                sched.is_active = False
                if not sched.enabled:
                    logger.info(f"⏸️  Schedule GPIO{gpio_number}/{schedule_id} - disabled")
                else:
                    logger.info(f"⏳ Schedule GPIO{gpio_number}/{schedule_id} - inactive (outside time window)")
            
            return sched
    
    def remove_schedule(self, gpio_number: int, schedule_id: str) -> bool:
        """Remove a schedule from cache (atomic)"""
        with self._lock:
            if gpio_number in self._cache and schedule_id in self._cache[gpio_number]:
                del self._cache[gpio_number][schedule_id]
                logger.info(f"❌ Schedule GPIO{gpio_number}/{schedule_id} - REMOVED")
                return True
            return False
    
    def get_schedule(self, gpio_number: int, schedule_id: str) -> Optional[ScheduleDefinition]:
        """Get a specific schedule from cache"""
        with self._lock:
            return self._cache.get(gpio_number, {}).get(schedule_id)
    
    def get_pin_schedules(self, gpio_number: int) -> List[ScheduleDefinition]:
        """Get all schedules for a GPIO pin"""
        with self._lock:
            return list(self._cache.get(gpio_number, {}).values())
    
    def get_active_schedules(self, gpio_number: int) -> List[ScheduleDefinition]:
        """Get only active schedules for a GPIO pin (time window respected)"""
        with self._lock:
            schedules = self._cache.get(gpio_number, {}).values()
            return [s for s in schedules if s.is_active]
    
    def update_all_time_windows(self) -> None:
        """
        CRITICAL: Re-evaluate all schedules' time windows.
        
        Call this when system time changes or periodically to ensure
        schedules activate/deactivate based on current time.
        """
        with self._lock:
            changed_count = 0
            for gpio_num, schedules in self._cache.items():
                for schedule_id, sched in schedules.items():
                    if sched.enabled:
                        was_active = sched.is_active
                        should_skip = TimeWindowValidator.should_skip_due_to_window(sched.start_time, sched.end_time)
                        is_now_active = not should_skip
                        
                        if is_now_active != was_active:
                            sched.is_active = is_now_active
                            changed_count += 1
                            
                            if is_now_active:
                                logger.info(f"✅ GPIO{gpio_num}/{schedule_id} - NOW ACTIVE (entered time window)")
                            else:
                                logger.info(f"⏳ GPIO{gpio_num}/{schedule_id} - NOW INACTIVE (exited time window)")
            
            if changed_count > 0:
                logger.info(f"⏱️  Time window check: {changed_count} schedule(s) changed activation status")
    
    def get_all_schedules(self) -> Dict[int, List[ScheduleDefinition]]:
        """Get all cached schedules"""
        with self._lock:
            return {
                gpio_num: list(schedules.values())
                for gpio_num, schedules in self._cache.items()
            }


class ScheduleStateTracker:
    """Track the current execution state of schedules"""
    
    def __init__(self):
        self._lock = threading.RLock()
        self._running_schedules: Dict[str, datetime] = {}  # {pin-schedule_id: start_time}
        self._last_interval_run: Dict[str, datetime] = {}  # Track interval-based last runs
    
    def mark_running(self, gpio_number: int, schedule_id: str) -> None:
        """Mark schedule as currently running"""
        with self._lock:
            key = f"{gpio_number}-{schedule_id}"
            self._running_schedules[key] = datetime.now()
            logger.debug(f"▶️  Schedule {key} marked as running")
    
    def mark_stopped(self, gpio_number: int, schedule_id: str) -> None:
        """Mark schedule as stopped"""
        with self._lock:
            key = f"{gpio_number}-{schedule_id}"
            self._running_schedules.pop(key, None)
            logger.debug(f"⏹️  Schedule {key} marked as stopped")
    
    def is_running(self, gpio_number: int, schedule_id: str) -> bool:
        """Check if schedule is currently running"""
        with self._lock:
            key = f"{gpio_number}-{schedule_id}"
            return key in self._running_schedules
    
    def update_last_run(self, gpio_number: int, schedule_id: str, last_run: datetime) -> None:
        """Update last run time for interval-based schedules"""
        with self._lock:
            key = f"{gpio_number}-{schedule_id}"
            self._last_interval_run[key] = last_run
    
    def get_last_run(self, gpio_number: int, schedule_id: str) -> Optional[datetime]:
        """Get last run time for interval-based schedules"""
        with self._lock:
            key = f"{gpio_number}-{schedule_id}"
            return self._last_interval_run.get(key)
    
    def get_running_count(self) -> int:
        """Get count of currently running schedules"""
        with self._lock:
            return len(self._running_schedules)


# Global instances (singleton pattern)
_schedule_cache = ScheduleCache()
_schedule_state_tracker = ScheduleStateTracker()


def get_schedule_cache() -> ScheduleCache:
    """Get the global schedule cache instance"""
    return _schedule_cache


def get_schedule_state_tracker() -> ScheduleStateTracker:
    """Get the global schedule state tracker"""
    return _schedule_state_tracker
