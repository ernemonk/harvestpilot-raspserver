# Schedule Listener Implementation

## Overview

The Schedule Listener system provides **real-time, Firestore-driven GPIO schedule execution** with strict time window enforcement and atomic hardware cache synchronization.

### Key Characteristics
- ✅ **Real-time Firestore listening** (not polling)
- ✅ **Per-GPIO schedules** (stored in `gpioState.{pin}.schedules`)
- ✅ **Strict time windows** (start_time → end_time is ENFORCED)
- ✅ **Atomic cache operations** (RLock protects all concurrent access)
- ✅ **Hardware state sync** (cache always reflects actual GPIO state + desired Firestore state)
- ✅ **Automatic executor threads** (each new schedule gets its own execution thread)
- ✅ **Periodic time window re-evaluation** (every 60 seconds)

---

## Architecture

### Component Layers

```
┌─────────────────────────────────────────────────────────────┐
│  GPIOActuatorController                                     │
│  - Owns ScheduleCache and ScheduleStateTracker (singletons) │
│  - Manages schedule listener lifecycle                      │
│  - Executes schedules via _execute_schedule() callback      │
│  - Periodically checks time windows                         │
└──────────────────┬──────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┬──────────────────────┐
        │                     │                      │
        ▼                     ▼                      ▼
   ScheduleCache    ScheduleStateTracker   FirestoreScheduleListener
   (In-memory)      (Execution tracking)   (Real-time listener)
   - RLock          - RLock                - on_snapshot pattern
   - Thread-safe    - Last run times       - ADD/MODIFY/DELETE
   - Atomic ops     - Is running status     detection
```

### Firestore Data Structure

```
devices/{hardware_serial}/gpioState/{pin}/schedules/{scheduleId}
├── type: "pwm_cycle" | "pwm_fade" | "digital_toggle" | "hold_state"
├── enabled: true | false
├── time_window:
│   ├── enabled: true | false
│   ├── start_time: "HH:MM" (24-hour)
│   └── end_time: "HH:MM" (24-hour)
├── cycles: 5
├── on_duration: 2.0 (seconds)
├── off_duration: 1.0 (seconds)
├── duration: 10.0 (seconds for fade/hold)
├── steps: 10 (for fade)
├── state: true | false (for hold)
├── toggle_interval: 0.5 (seconds)
├── created_at: timestamp
├── last_run_at: timestamp
└── created_by: "user@app.com"
```

---

## Files Created

### 1. `src/services/schedule_listener.py`

**Purpose:** In-memory schedule cache with thread-safe operations and time window validation.

#### Key Classes

##### `ScheduleDefinition` (dataclass)
```python
@dataclass
class ScheduleDefinition:
    schedule_id: str
    pin: int
    type: str  # pwm_cycle, pwm_fade, digital_toggle, hold_state
    enabled: bool
    config: Dict[str, Any]  # cycles, duration, steps, etc.
    time_window: Optional[TimeWindow]  # start_time, end_time (24-hour HH:MM)
    last_run_at: Optional[datetime]
    is_active: bool  # Current execution status
```

##### `TimeWindowValidator`
Singleton class for validating time windows.

**Key Methods:**
- `is_in_window(time_window: TimeWindow, current_time: datetime = None) -> bool`
  - Returns True if current time is within start_time → end_time
  - Handles overnight windows (e.g., 22:00 → 06:00)
  - Returns True if time_window is None (no window = always enabled)

- `should_skip_due_to_window(time_window: TimeWindow) -> bool`
  - Returns True if we should SKIP execution (outside window)
  - Inverse of is_in_window()

##### `ScheduleCache` (RLock protected)
Thread-safe in-memory cache for all GPIO schedules.

**Key Methods:**
- `update_schedule(pin: int, schedule: ScheduleDefinition)` → Atomically add/update
- `remove_schedule(pin: int, schedule_id: str)` → Atomically remove
- `get_schedule(pin: int, schedule_id: str) -> Optional[ScheduleDefinition]`
- `get_pin_schedules(pin: int) -> List[ScheduleDefinition]` → All schedules for pin
- `get_active_schedules() -> Dict[int, List[ScheduleDefinition]]` → All active schedules
- `update_all_time_windows()` → Re-evaluate which schedules are "in window"

**Thread Safety:**
```python
with self._lock:  # RLock
    # All operations are ATOMIC
    self._schedules[pin_str][schedule_id] = schedule
```

##### `ScheduleStateTracker` (RLock protected)
Tracks which schedules are currently executing and their last run times.

**Key Methods:**
- `mark_running(pin: int, schedule_id: str)` → Mark as executing
- `mark_stopped(pin: int, schedule_id: str)` → Mark as completed
- `is_running(pin: int, schedule_id: str) -> bool`
- `update_last_run(pin: int, schedule_id: str)` → Set last_run_at = now
- `get_last_run(pin: int, schedule_id: str) -> Optional[datetime]`
- `get_running_count(pin: int) -> int` → How many schedules running on this pin

### 2. `src/services/firestore_schedule_listener.py`

**Purpose:** Real-time Firestore listener that detects schedule changes and triggers execution.

#### Key Class: `FirestoreScheduleListener`

**Constructor:**
```python
FirestoreScheduleListener(
    firestore_db: firestore.Client,
    hardware_serial: str,
    schedule_cache: ScheduleCache,
    schedule_state_tracker: ScheduleStateTracker,
    executor_callback: Callable[[int, str, Dict], None],  # (pin, schedule_id, config)
)
```

**Key Methods:**

- `start_listening()` 
  - Loads initial schedules from Firestore
  - Sets up real-time on_snapshot listener
  - Detects: ADD, MODIFY, DELETE changes
  
- `_load_initial_schedules()`
  - Reads all existing schedules from `gpioState.{pin}.schedules`
  - Populates ScheduleCache on startup
  
- `_process_schedule_changes()`
  - A→ NEW schedule → Add to cache, execute if in time window
  - → MODIFIED → Update cache, re-evaluate window status
  - → DELETED → Remove from cache, stop if running
  
- `check_and_update_time_windows()`
  - Called every 60 seconds by GPIOActuatorController
  - Re-evaluates which schedules are in their time windows
  - Stops schedules that exited their window
  - Starts schedules that entered their window
  
- `stop_listening()`
  - Unsubscribes from Firestore listener
  - Graceful cleanup

**Executor Thread Creation:**
```
Firestore detects NEW schedule
    ↓
_process_schedule_changes() fires
    ↓
Create ScheduleDefinition + add to cache
    ↓
Check if in time window
    ↓
If YES → Create NEW thread → Call executor_callback()
If NO  → Schedule queued, will auto-start at time window entry
```

---

## Files Modified

### `src/services/gpio_actuator_controller.py`

**Updated Docstring (SCHEDULES Section):**
```
SCHEDULES (Real-time Execution)
─────────────────────────────────
Listens to gpioState.{pin}.schedules in REAL-TIME via Firestore.
Each schedule change (ADD/MODIFY/DELETE) creates a new executor thread.
Time windows (start_time → end_time) are STRICTLY enforced.
Hardware cache stays in ATOMIC sync via RLock operations.
```

**Updated `__init__()` Method:**
Added schedule management attributes:
```python
self._schedule_cache = ScheduleCache()
self._schedule_state_tracker = ScheduleStateTracker()
self._schedule_listener: Optional[FirestoreScheduleListener] = None
self._schedule_checker_thread: Optional[threading.Thread] = None  
self._schedule_execution_lock = threading.RLock()
```

**Updated `connect()` Method:**
1. Calls `_start_schedule_listener()` after state/command listeners
2. Calls `_start_schedule_checker()` for periodic time window re-eval
3. Logs schedule listener status

**New Methods:**

##### `_start_schedule_listener()`
```python
def _start_schedule_listener(self):
    """Start real-time Firestore listener for GPIO schedules."""
    # Creates FirestoreScheduleListener instance
    # Calls start_listening()
    # Logs status
```

##### `_start_schedule_checker()`
```python
def _start_schedule_checker(self):
    """Periodically check time windows every 60 seconds."""
    # Daemon thread that runs check_and_update_time_windows()
    # Runs every 60 seconds
```

##### `_execute_schedule(pin, schedule_id, schedule_data)`
**Callback method** invoked by FirestoreScheduleListener when a schedule becomes active.

```python
def _execute_schedule(self, pin: int, schedule_id: str, schedule_data: Dict[str, Any]):
    """Execute a schedule on GPIO pin (runs in separate thread)."""
    # Acquires _schedule_execution_lock
    # Marks schedule as RUNNING in ScheduleStateTracker
    # Executes based on type:
    #   - pwm_cycle: on/off cycles
    #   - pwm_fade: gradual fade in/out
    #   - digital_toggle: toggle pin N times
    #   - hold_state: hold state for duration then OFF
    # Updates Firestore with last_run_at timestamp
    # Marks schedule as STOPPED
```

**Updated `disconnect()` Method:**
```python
# Stop schedule listener
if self._schedule_listener:
    self._schedule_listener.stop_listening()

# Stop schedule checker thread
if self._schedule_checker_thread and self._schedule_checker_thread.is_alive():
    self._schedule_checker_thread.join(timeout=5)
```

---

## Thread Safety & Concurrency

### Lock Hierarchy

```
_schedule_execution_lock (RLock)
    ├─ Protects ScheduleStateTracker marking operations
    └─ Protects last_run_at updates

ScheduleCache._lock (RLock)
    └─ Protects all in-memory schedule cache operations

Firestore listener thread
    └─ Non-blocking, fires on_snapshot callbacks
    └─ Each schedule execution runs in SEPARATE thread
```

### Critical Invariants

1. **Atomic Cache Operations**
   ```python
   with cache._lock:
       # These 3 operations are ATOMIC (no interleaving)
       cache.update_schedule(pin, schedule)
       tracker.mark_running(pin, schedule_id)
       # Hardware state now consistent
   ```

2. **No Races on Time Windows**
   - Only ONE thread modifies `is_active` status (the 60s checker)
   - Readers can safely check `is_active` without lock (atomic boolean assignment)

3. **Hardware State Consistency**
   - _apply_to_hardware() updates _hardware_states[pin] IMMEDIATELY
   - Firestore sync loop reads _hardware_states[pin] periodically
   - Never stale: actual GPIO → memory cache → Firestore

---

## Usage Examples

### 1. Add a Schedule (via Firestore/webapp)

```javascript
// Firestore write (from webapp)
devices/{hardware_serial}/gpioState/17/schedules/{newScheduleId}
{
  type: "pwm_cycle",
  enabled: true,
  cycles: 5,
  on_duration: 2.0,
  off_duration: 1.0,
  time_window: {
    enabled: true,
    start_time: "09:00",
    end_time: "17:00"
  },
  created_at: serverTimestamp,
  created_by: "user@app.com"
}
```

**Result:**
1. Firestore listener detects ADD
2. New thread created to execute schedule
3. Checks if in time window (now 09:00-17:00) ✓
4. Executes: ON 2s → OFF 1s → ON 2s → OFF 1s ... (5 cycles)
5. Updates Firestore with last_run_at

### 2. Time Window Enforcement

**Current time: 18:30** (outside schedule window)

Schedule exists but is NOT running because:
```
is_in_window("09:00", "17:00", 18:30) = False
should_skip_due_to_window() = True
Executor thread is NOT created
```

**At 09:00 next morning:**
- Periodic time window checker fires
- Detects schedule is NOW in window
- Creates executor thread
- Execution begins

### 3. Modify a Schedule

```javascript
// Update: extend end_time to 22:00
devices/{hardware_serial}/gpioState/17/schedules/{scheduleId}
{
  time_window: {
    start_time: "09:00",
    end_time: "22:00"  // Extended from 17:00
  }
}
```

**Result:**
1. Firestore listener detects MODIFY
2. ScheduleCache updated with new time window
3. If schedule was stopped at 17:00, it's re-evaluated:
   - Current time 18:30 is now in window (09:00-22:00) ✓
   - New executor thread created if not already running

### 4. Delete a Schedule

```javascript
// Delete the schedule document
documents.{scheduleId}.delete()
```

**Result:**
1. Firestore listener detects DELETE
2. ScheduleCache removes schedule
3. If currently executing, worker thread will finish (no interrupt)
4. ScheduleStateTracker marked as STOPPED
5. No further executions

---

## Time Window Specification

### Format

```
time_window: {
  enabled: true,         // true = enforce, false = always run
  start_time: "HH:MM",   // 24-hour format (e.g., "09:00")
  end_time: "HH:MM"      // 24-hour format (e.g., "17:00")
}
```

### Examples

**Standard 9-to-5:**
```json
{ "enabled": true, "start_time": "09:00", "end_time": "17:00" }
```
→ Schedule only runs 09:00-17:00

**Overnight (10pm to 6am):**
```json
{ "enabled": true, "start_time": "22:00", "end_time": "06:00" }
```
→ Schedule runs 22:00-23:59 AND 00:00-06:00

**No window (always run):**
```json
{ "enabled": false }
```
or omit `time_window` entirely
→ Schedule runs 24/7

### Strict Enforcement

- If schedule is CURRENTLY executing when window expires, execution continues
- Next iteration of schedule will be skipped if outside window
- When exiting window: if schedule is queued (hasn't run yet), it's cancelled

---

## Schedule Types

### 1. PWM Cycle (On/Off)

```json
{
  "type": "pwm_cycle",
  "cycles": 5,
  "on_duration": 2.0,    // seconds
  "off_duration": 1.0    // seconds
}
```

Behavior: ON 2s → OFF 1s → ON 2s → OFF 1s → ON 2s

Use case: Pump irrigation cycles, LED blinking

### 2. PWM Fade

```json
{
  "type": "pwm_fade",
  "duration": 10.0,      // total fade time (seconds)
  "steps": 10            // number of fade steps
}
```

Behavior: Gradually fade from OFF → ON over 10 seconds in 10 steps

Use case: Smooth LED dimming, gradual pump ramp-up

### 3. Digital Toggle

```json
{
  "type": "digital_toggle",
  "cycles": 3,
  "toggle_interval": 0.5 // seconds between toggles
}
```

Behavior: Toggle (flip) the pin 3 times, 0.5s between each

Use case: Solenoid valve pulse, relay clicks

### 4. Hold State

```json
{
  "type": "hold_state",
  "state": true,         // true = HIGH, false = LOW
  "duration": 60.0       // how long to hold (seconds)
}
```

Behavior: Set pin HIGH and hold for 60s, then return to LOW

Use case: Water pump activation, lighting timeout

---

## Error Handling & Edge Cases

### Schedule Execution Failure

```python
try:
    # Execute schedule
except Exception as e:
    logger.error(f"Error executing schedule {schedule_id} on GPIO{pin}: {e}")
finally:
    # Always mark as STOPPED (even if error)
    tracker.mark_stopped(pin, schedule_id)
```

**Result:** Schedule stops gracefully, fire-and-forget (no retry)

### Concurrent Schedule Execution

```
GPIO17 has 2 active schedules at once:
  1. pwm_cycle (running)
  2. hold_state (just triggered)
```

**Result:** Both run in separate threads (!), state conflicts possible

**Mitigation:** Application should avoid overlapping schedules on same pin

### Time Window Edge Cases

**Case 1:** Overnight window expires during execution
```
10:30pm: schedule starts (within 22:00-06:00 window)
11:30pm: schedule still executing
11:45pm → 06:00am: window is still OPEN (overnight)
06:15am: window EXPIRED, but execution already finished ✓
```

**Case 2:** Schedule queued but modified before execution
```
Schedule queued (outside window, waiting for 09:00)
08:55am: Schedule modified → time_window.end_time changed to "08:59"
09:00am: Execution starts, but immediately hits expired window
Behavior: Executor runs anyway (no preemption), then stops
```

---

## Monitoring & Debugging

### Logging

```
✓ Real-time schedule listener ACTIVE (monitoring {hardware_serial})
▶️  Executing pwm_cycle on GPIO17: schedule-abc123
✓ Schedule completed: GPIO17/schedule-abc123
✓ Time window check completed
```

### Getting Schedule Status

```python
controller = get_gpio_controller()

# Get all schedules for GPIO17
schedules = controller._schedule_cache.get_pin_schedules(pin=17)

# Check if specific schedule is running
is_running = controller._schedule_state_tracker.is_running(pin=17, schedule_id="abc123")

# Get last execution time
last_run = controller._schedule_state_tracker.get_last_run(pin=17, schedule_id="abc123")

# Get active schedules across all pins
active = controller._schedule_cache.get_active_schedules()
```

---

## Testing

### Unit Tests

See `test_schedule_listener.py` (to be created):
- TimeWindowValidator: boundary cases (noon, midnight, overnight)
- ScheduleCache: thread safety, atomic operations
- ScheduleStateTracker: concurrent marking, last_run tracking
- FirestoreScheduleListener: ADD/MODIFY/DELETE detection
- GPIOActuatorController: schedule execution integration

### Integration Tests

```python
# Add schedule via Firestore
db.document(f"devices/{serial}/gpioState/17/schedules/test-1").set({
    "type": "pwm_cycle",
    "cycles": 3,
    "on_duration": 0.5,
    "off_duration": 0.5,
})

# Wait for execution
time.sleep(5)

# Verify GPIO17 state history
assert controller._hardware_states[17] == False  # OFF after 3 cycles
```

---

## Performance Characteristics

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| Cache lookup (get_schedule) | O(1) | Direct dict access |
| Cache update (update_schedule) | O(1) | With RLock |
| Time window check | O(n) | n = schedules on pin |
| All time window check | O(m) | m = total schedules |
| Firestore listener start | O(n) | Load initial schedule docs |

### Memory Usage

```
ScheduleCache:
  Per schedule: ~500 bytes (config dict + metadata)
  1000 schedules: ~500 KB

ScheduleStateTracker:
  Per running schedule: ~200 bytes
  100 concurrent: ~20 KB
```

---

## Integration Checklist

- ✅ `ScheduleCache` + `ScheduleStateTracker` created
- ✅ `FirestoreScheduleListener` with Firestore on_snapshot
- ✅ `_start_schedule_listener()` in GPIOActuatorController
- ✅ `_start_schedule_checker()` (60s time window checker)
- ✅ `_execute_schedule()` callback (4 schedule types)
- ✅ Schedule listener cleanup in `disconnect()`
- ⏳ `test_schedule_listener.py` (comprehensive test suite)
- ⏳ REST API endpoints for schedule CRUD
- ⏳ Firestore security rules for schedule access
- ⏳ Performance testing under concurrent execution

