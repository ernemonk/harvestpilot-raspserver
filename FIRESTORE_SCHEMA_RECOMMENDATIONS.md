# Enhanced Firestore Schema for Better Hardware Control & Observability

## Executive Summary

Your current schema handles **state changes** well but lacks **observability**, **PWM precision**, and **error tracking**. This doc provides field-by-field recommendations to give the web app full visibility into hardware state + advanced control capabilities.

---

## Part 1: Enhanced GPIO State Structure

### Current Structure
```json
devices/{serial}/gpioState/{pin}
├── state: boolean              // ✅ Good
├── enabled: boolean            // ✅ Good
├── name: string                // ✅ Good (from GPIO naming)
└── ... missing fields below
```

### RECOMMENDED: Enhanced Structure

```json
devices/{serial}/gpioState/{pin}
│
├─── STATE (What the Pi SHOULD do)
│    ├── state: boolean              // Desired state (HIGH/LOW)
│    ├── enabled: boolean            // Master enable/disable
│    └── updated_at: timestamp       // When desired state changed
│
├─── PWM CONTROL (For PWM pins)
│    ├── pwm_enabled: boolean        // Is PWM active vs digital?
│    ├── pwm_frequency: number       // Hz (e.g., 1000 for LED, 50 for servo)
│    ├── pwm_duty_cycle: number      // 0-100 (%)
│    ├── pwm_fade: {                 // Smooth transitions
│    │   ├── enabled: boolean
│    │   ├── target_duty: number     // Fade TO this %
│    │   ├── duration_ms: number     // Fade over this many ms
│    │   └── curve: string           // "linear", "ease_in", "ease_out", "ease_in_out"
│    │}
│    └── pwm_updated_at: timestamp
│
├─── HARDWARE STATE (What the Pi ACTUALLY sees)
│    ├── hardware_state: boolean     // Current GPIO pin state (from GPIO read)
│    ├── hardware_frequency: number  // Actual measured frequency (for PWM)
│    ├── hardware_duty_cycle: number // Actual duty cycle (0-100%)
│    ├── last_hardware_read: timestamp
│    └── mismatch: {                 // ⭐ CRITICAL: Detect real problems
│        ├── exists: boolean         // state !== hardware_state?
│        ├── duration_ms: number     // How long has mismatch existed?
│        ├── severity: string        // "warning" | "error" | "critical"
│        └── likely_cause: string    // "pin_disconnected" | "driver_error" | "hw_fault"
│    }
│
├─── PIN INFO (Read-only, set by Pi on boot)
│    ├── pin: number                 // GPIO number (GPIO17, etc.)
│    ├── physical_pin: number        // Header pin position
│    ├── mode: string                // "OUTPUT", "INPUT", "PWM", "ADC"
│    ├── capabilities: string[]      // ["DIGITAL", "PWM", "INTERRUPT"]
│    ├── name_customized: boolean    // Is this a user-set name?
│    ├── default_name: string        // Smart default (GPIO17 LED PWM)
│    └── initialized_at: timestamp
│
├─── OBSERVABILITY / DIAGNOSTICS
│    ├── error_status: {             // Current error state
│    │   ├── has_error: boolean
│    │   ├── error_code: string      // "TIMEOUT", "SHORT_CIRCUIT", "OVER_CURRENT"
│    │   ├── error_message: string   // Human-readable
│    │   └── error_timestamp: timestamp
│    │}
│    ├── performance: {
│    │   ├── response_time_ms: number // How fast does hardware respond?
│    │   ├── stability_score: number  // 0-100 (how stable is this pin?)
│    │   ├── state_changes: number    // Total changes since boot
│    │   └── last_state_change: timestamp
│    │}
│    ├── health_check: {
│    │   ├── last_check: timestamp
│    │   ├── status: string           // "healthy", "degraded", "failed"
│    │   └── pin_responsive: boolean  // Did hardware respond to command?
│    │}
│    └── audit: {
│        ├── created_at: timestamp
│        ├── created_by: string       // "system" | "user@app.com"
│        ├── last_modified_by: string
│        └── change_count: number
│    }
│
├─── CONSTRAINTS & SAFETY
│    ├── rate_limit: {                // Prevent GPIO thrashing
│    │   ├── enabled: boolean
│    │   ├── min_state_duration_ms: number  // Don't toggle faster than this
│    │   └── last_state_change: timestamp
│    │}
│    ├── soft_limits: {               // Safety bounds
│    │   ├── max_on_duration_ms: number    // Auto-OFF after this long
│    │   ├── max_on_temperature: number   // Stop if too hot
│    │   ├── min_off_duration_ms: number  // Rest period between cycles
│    │   └── enabled: boolean
│    │}
│    └── failsafe: {
│        ├── enabled: boolean
│        ├── default_state: boolean   // What state if connection lost?
│        ├── timeout_ms: number       // How long before failsafe triggers?
│        └── action: string           // "hold_state" | "emergency_off" | "pulse_alert"
│    }
│
├─── SCENES / GROUPS
│    ├── scene_membership: string[]   // ["scene-irrigation", "scene-evening"]
│    └── group_id: string             // For coordinated multi-pin actions
│
└─── SCHEDULES (existing, enhanced)
     ├── {scheduleId}: {...}          // (see section 2 below)
     └── _metadata: {                 // New: track schedule stats
         ├── total: number            // How many schedules?
         ├── active: number           // How many are currently running?
         └── last_execution: timestamp
```

### Implementation Guide for Web App

**Tell the web app developers:**

```markdown
# GPIO State Sync Requirements

## WRITE (webapp → Pi)
Webapp ONLY sets these fields:
- state (boolean)
- enabled (boolean)
- pwm_duty_cycle (0-100) IF pin is PWM-capable
- pwm_fade {enabled, target_duty, duration_ms, curve}
- soft_limits (safety bounds)
- rate_limit settings
- enabled flag in schedules

⚠️ NEVER write to: hardware_state, last_hardware_read, mismatch, error_status
(These are Pi-OWNED, read-only for webapp)

## READ (Pi → Webapp)
Webapp reads ALL fields to display:
- Current desired state + actual hardware state (show MISMATCH if different!)
- PWM frequency, duty cycle (for dimmers/faders)
- Error status + health check (show red warning if mismatched)
- Performance metrics (response time, stability score)
- Audit trail (who made what change when)

## REAL-TIME SYNC
- Use on_snapshot() listener on full gpioState.{pin} document
- Don't just read state; show: desired vs actual, errors, PWM values
- Show mismatch indicator prominently (⚠️ red if hardware != desired for >2 seconds)
```

---

## Part 2: Enhanced Schedule Structure

### Current Structure
```json
devices/{serial}/gpioState/{pin}/schedules/{scheduleId}
├── type: string
├── enabled: boolean
├── cycles: number
├── on_duration: number
└── ... missing fields below
```

### RECOMMENDED: Enhanced Structure

```json
devices/{serial}/gpioState/{pin}/schedules/{scheduleId}
│
├─── CORE (Existing, keep as-is)
│    ├── type: "pwm_cycle" | "pwm_fade" | "digital_toggle" | "hold_state"
│    ├── enabled: boolean
│    └── temp: number                // ↓ NEW: temperature-dependent
│
├─── TIMING & REPETITION (Enhanced)
│    ├── time_window: {              // When to run
│    │   ├── enabled: boolean
│    │   ├── start_time: "HH:MM"
│    │   ├── end_time: "HH:MM"
│    │   └── time_zone: string       // "UTC", "EST", "PST" (for multi-region)
│    │}
│    ├── recurrence: {               // NEW: Repeat patterns
│    │   ├── type: "once" | "daily" | "weekly" | "interval"
│    │   ├── days_of_week: number[]  // [1,3,5] = Mon,Wed,Fri
│    │   ├── interval_ms: number     // Repeat every 30 mins
│    │   ├── start_date: timestamp
│    │   └── end_date: timestamp     // Stop after this date
│    │}
│    └── time_metadata: {            // NEW: Track execution history
│        ├── last_run_at: timestamp
│        ├── next_run_at: timestamp
│        ├── total_runs: number
│        └── execution_time_ms: number
│
├─── CONTROL PARAMS (Type-specific, enhanced)
│    ├── cycles: number              // For cycle types
│    ├── on_duration_ms: number      // Milliseconds (more precise)
│    ├── off_duration_ms: number
│    ├── duration_ms: number         // For fade/hold
│    │
│    ├── pwm_params: {               // NEW: Dedicated PWM section
│    │   ├── frequency_hz: number    // 1000 for LED, 50 for servo
│    │   ├── start_duty: number      // 0-100%
│    │   ├── end_duty: number        // Fade to this duty
│    │   ├── curve: string           // "linear", "ease_in", "ease_out"
│    │   └── steps: number           // Resolution (how many steps)
│    │}
│    │
│    ├── fade_profile: {             // NEW: Advanced fading
│    │   ├── type: "linear" | "exponential" | "logarithmic" | "sigmoid"
│    │   ├── duration_ms: number
│    │   ├── easing_curve: "ease_in_out" | "ease_in" | "ease_out"
│    │   └── waypoints: [{           // Multi-point fade
│    │       ├── time_ms: 0,
│    │       ├── duty: 0
│    │     }, {
│    │       ├── time_ms: 5000,
│    │       ├── duty: 100
│    │     }, {
│    │       ├── time_ms: 10000,
│    │       ├── duty: 30
│    │     }]
│    │}
│    │
│    └── step_sequencer: {           // NEW: Complex sequences
│        ├── steps: [{
│        │   ├── duration_ms: 1000,
│        │   ├── action: "pwm_to_50",
│        │   └── next_on_condition: "always" | "if_sensor_high"
│        │ }],
│        └── loop: boolean           // Repeat sequence?
│    }
│
├─── CONDITIONS / TRIGGERS (NEW: Conditional execution)
│    ├── conditions: {
│    │   ├── type: "sensor_threshold" | "time_based" | "manual" | "combined"
│    │   ├── sensor_pin: number      // Which sensor to read?
│    │   ├── operator: "<" | ">" | "=" | "range"
│    │   ├── threshold_low: number
│    │   ├── threshold_high: number
│    │   └── enabled: boolean        // Can disable conditions without deleting
│    │}
│    └── trigger_behavior: string    // "execute_once" | "execute_each_cycle" | "execute_while_true"
│
├─── SEQUENCING & DEPENDENCIES (NEW: Multi-pin coordination)
│    ├── depends_on: {               // This schedule waits for another
│    │   ├── pin: number
│    │   ├── schedule_id: string
│    │   └── wait_for_completion: boolean
│    │}
│    ├── triggers_after: string[]    // Start these schedules when done
│    └── mutex_with: string[]        // Don't run same time as these
│
├─── PRIORITY & LIMITS (NEW: Resource management)
│    ├── priority: number            // 1-10 (10 = highest)
│    ├── cpu_limit: number           // % CPU allowed
│    ├── soft_limits: {              // Override pin defaults
│    │   ├── max_duration_ms: number
│    │   └── max_cycles: number
│    │}
│    ├── rate_limit_ms: number       // Min time between consecutive runs
│    └── timeout_ms: number          // Auto-stop if taking too long
│
├─── MONITORING & HEALTH (NEW: Execution tracking)
│    ├── execution_log: {
│    │   ├── status: "success" | "timeout" | "error" | "skipped"
│    │   ├── error_count: number     // How many failed runs?
│    │   ├── last_error: string
│    │   └── last_execution_ms: number  // How long did it take?
│    │}
│    ├── alerts: {                   // Notify if something goes wrong
│    │   ├── on_failure: boolean
│    │   ├── on_timeout: boolean
│    │   ├── on_condition_fail: boolean
│    │   └── notify_user: string     // Email/Slack/webhook
│    │}
│    └── metrics: {
│        ├── execution_count_today: number
│        ├── execution_count_week: number
│        ├── success_rate: number    // 0-100%
│        └── avg_execution_time_ms: number
│
├─── VERSION CONTROL (NEW: Audit trail)
│    ├── version: number             // Schema version (for migrations)
│    ├── created_at: timestamp
│    ├── created_by: string
│    ├── updated_at: timestamp
│    ├── updated_by: string
│    ├── revision_history: [{        // Track changes
│    │   ├── timestamp: timestamp,
│    │   ├── changed_by: string,
│    │   ├── changes: {old, new},
│    │   └── reason: string          // "user_edit", "condition_trigger"
│    │}]
│    └── rollback_to: string         // Revert to previous version?
│
└─── METADATA
     ├── description: string         // "Water plants 2x daily"
     ├── tags: string[]              // ["irrigation", "daily", "morning"]
     ├── scene_id: string            // Part of which scene?
     └── locked: boolean             // Prevent accidental edits?
```

### Implementation Guide for Web App

**Tell the web app developers:**

```markdown
# Enhanced Schedule Capabilities

## Core Improvements

### 1. FADING & SMOOTH TRANSITIONS
Instead of hard ON/OFF, support PWM fading:
```json
{
  "type": "pwm_fade",
  "fade_profile": {
    "type": "linear",
    "duration_ms": 5000,
    "waypoints": [
      {"time_ms": 0, "duty": 0},      // Start at 0%
      {"time_ms": 2500, "duty": 100}, // Peak at 50%
      {"time_ms": 5000, "duty": 30}   // End at 30%
    ]
  }
}
```

### 2. ADVANCED SCHEDULES (Beyond simple cycles)
Support step sequencing:
```json
{
  "type": "step_sequencer",
  "step_sequencer": {
    "steps": [
      {"duration_ms": 2000, "action": "pwm_to_50"},
      {"duration_ms": 1000, "action": "pwm_to_100"},
      {"duration_ms": 3000, "action": "pwm_fade_to_0"}
    ],
    "loop": true  // Repeat forever
  }
}
```

### 3. CONDITIONAL EXECUTION
"Run only if humidity > 60%":
```json
{
  "conditions": {
    "type": "sensor_threshold",
    "sensor_pin": 18,        // Read GPIO18 (DHT sensor)
    "operator": ">",
    "threshold_high": 60     // Humidity threshold
  }
}
```

### 4. DEPENDENCIES & COORDINATION
"Run this after irrigation completes, but not within 30min of another pump":
```json
{
  "depends_on": {
    "pin": 17,
    "schedule_id": "irrigation-main",
    "wait_for_completion": true
  },
  "mutex_with": ["pump-secondary"]
}
```

### 5. REPETITION PATTERNS
Skip "frequency" - use real recurrence:
```json
{
  "recurrence": {
    "type": "weekly",
    "days_of_week": [1, 3, 5],  // Mon, Wed, Fri
    "start_date": "2026-02-10",
    "end_date": "2026-12-31"
  }
}
```

### 6. OBSERVABILITY
Every schedule execution logs:
```json
{
  "execution_log": {
    "status": "success",
    "last_execution_ms": 2150,
    "error_count": 0
  },
  "time_metadata": {
    "last_run_at": "2026-02-09T14:32:15Z",
    "next_run_at": "2026-02-09T17:00:00Z",
    "total_runs": 147
  }
}
```

## UI/UX Recommendations

1. **Visual Schedule Builder**
   - Drag-drop builder for step sequences
   - Preview: "This schedule will run Mon/Wed/Fri at 09:00, fade from 0→100→30"

2. **Conflict Detection**
   - Warn if 2 schedules conflict on same pin
   - Show estimated execution time

3. **Execution Monitor**
   - Real-time countdown to next execution
   - Last execution time + status
   - Success rate % for reliability tracking

4. **Testing**
   - "Dry run" button - simulate without hardware
   - "Run now" button - execute immediately
```

---

## Part 3: System-Level Fields (at device root)

### Add These to the Device Document Itself

```json
devices/{serial}
│
├─── EXISTING FIELDS (keep all)
│    └── gpioState, commands, etc.
│
├─── NEW: SYNC & HEARTBEAT
│    ├── heartbeat: {
│    │   ├── last_seen: timestamp    // When did Pi last check in?
│    │   ├── status: "online" | "offline" | "degraded"
│    │   ├── response_time_ms: number
│    │   ├── sync_error: string      // If offline, why?
│    │   └── firmware_version: string
│    │}
│    ├── sync_state: {
│    │   ├── local_clock_offset_ms: number  // Pi vs Firestore time diff
│    │   ├── last_sync: timestamp
│    │   ├── pending_changes: number // How many updates waiting?
│    │   └── sync_quality: number    // 0-100 (connection quality)
│    │}
│    └── connection_metadata: {
│        ├── ip_address: string
│        ├── signal_strength: number // WiFi signal %
│        └── latency_ms: number
│
├─── NEW: PERFORMANCE METRICS
│    ├── performance: {
│    │   ├── uptime_hours: number
│    │   ├── cpu_usage_percent: number
│    │   ├── memory_usage_percent: number
│    │   ├── disk_usage_percent: number
│    │   └── temperature_c: number   // Pi temperature
│    │}
│    ├── scheduler_state: {
│    │   ├── total_schedules: number
│    │   ├── active_schedules: number
│    │   ├── failed_schedules: number
│    │   └── last_schedule_run: timestamp
│    │}
│    └── hardware_health: {
│        ├── pins_initialized: number
│        ├── pins_with_errors: number
│        ├── pin_failures: [         // Track bad pins
│        │   {
│        │     "pin": 17,
│        │     "error": "TIMEOUT",
│        │     "last_failed": timestamp,
│        │     "fail_count": 5
│        │   }
│        │]
│        └── avg_response_time_ms: number
│
├─── NEW: SYSTEM COMMANDS (webapp → Pi)
│    ├── system_commands: {
│    │   ├── requested_action: "reboot" | "resync" | "test_all_pins" | "none"
│    │   ├── action_params: {}
│    │   └── requested_at: timestamp
│    │}
│    └── system_response: {
│        ├── last_action: string
│        ├── last_action_status: "pending" | "in_progress" | "success" | "failed"
│        ├── action_output: string
│        └── completed_at: timestamp
│
└─── NEW: WEBHOOKS & NOTIFICATIONS (for alerting)
     ├── webhooks: [{
     │   ├── url: string
     │   ├── events: ["pin_mismatch", "offline", "error", "schedule_failed"]
     │   └── enabled: boolean
     │}]
     └── alert_rules: [{
         ├── condition: "pin_error | offline_for_5min | mismatch_for_10s"
         ├── action: "email | slack | webhook"
         ├── recipient: string
         └── enabled: boolean
     }]
```

---

## Part 4: Data Types & Precision Recommendations

### Use Consistent Units Across All Fields

| Field | Type | Range | Example | Notes |
|-------|------|-------|---------|-------|
| Duration | Number (ms) | 1-3600000 | 5000 | Always milliseconds |
| Frequency | Number (Hz) | 1-100000 | 1000 | PWM frequency |
| Duty Cycle | Number (%) | 0-100 | 75.5 | Float for precision |
| Temperature | Number (°C) | -40 to 120 | 45.3 | Float sensors |
| Time Window | String (24-hr) | "HH:MM" | "14:30" | Always UTC/specified TZ |
| Timestamp | Timestamp | ISO8601 | 2026-02-09T... | Firestore.SERVER_TIMESTAMP |
| Response Time | Number (ms) | 1-10000 | 125 | Latency tracking |
| Percentage | Number (%) | 0-100 | 85.5 | Use for ratios |

---

## Part 5: Security & Access Control

### Firestore Rules to Enforce Safety

```javascript
// Allow webapp to ONLY update specific fields
match /devices/{serial}/gpioState/{pin} {
  allow read: if request.auth.uid in resource.data.allowed_users;
  
  allow update: if request.auth.uid in resource.data.allowed_users
    && request.resource.data.keys().hasOnly([
      'state',           // ✅ Allowed
      'enabled',         // ✅ Allowed
      'pwm_duty_cycle',  // ✅ Allowed
      'pwm_fade',        // ✅ Allowed
      'soft_limits',     // ✅ Allowed
      'rate_limit'       // ✅ Allowed
    ])
    && request.resource.data.state in [true, false]
    && request.resource.data.pwm_duty_cycle >= 0 
    && request.resource.data.pwm_duty_cycle <= 100;
}

// Pi directly controls hardware_state, errors, metrics
match /devices/{serial}/gpioState/{pin} {
  allow write: if request.auth.uid == 'pi-service-account'
    && request.resource.data.keys().hasOnly([
      'hardware_state',
      'hardware_duty_cycle',
      'mismatch',
      'error_status',
      'performance',
      'health_check',
      'last_hardware_read'
    ]);
}
```

---

## Part 6: Migration Path & Rollout

### Phase 1 (Week 1): Non-Breaking Additions
Add fields WITHOUT removing old ones:
- ✅ Add `pwm_fade` object (alongside existing `on_duration`)
- ✅ Add `hardware_state` field (new, read-only)
- ✅ Add `mismatch` detector (new, read-only)

### Phase 2 (Week 2-3): Observability
- ✅ Add `error_status`, `health_check`, `performance`
- ✅ Start logging `last_hardware_read`, response times
- ✅ Add `execution_log` to schedules

### Phase 3 (Week 4+): Advanced Features
- ✅ Upgrade schedules with `fade_profile`, `step_sequencer`, `conditions`
- ✅ Add `recurrence` with calendar logic
- ✅ Add `dependencies` for multi-pin orchestration

### Phase 4 (Future): System-Level Features
- ✅ Add device-level metrics
- ✅ Add webhooks & alerting
- ✅ Add version control & rollback

---

## Part 7: What to Tell the Web App Team

### Minimal Viable Update (Month 1)

```markdown
## Firebase Schema Changes - Web App Integration

### Fields We're Adding (READ access required)
- **gpio_state.{pin}.hardware_state** - Actual GPIO state (what Pi sees)
- **gpio_state.{pin}.mismatch.exists** - True if desired ≠ actual
- **gpio_state.{pin}.error_status** - Error codes/messages
- **gpio_state.{pin}.performance.response_time_ms** - Hardware responsiveness

### New Fields Web App Can WRITE
- **gpio_state.{pin}.pwm_duty_cycle** (0-100) - For dimmers
- **gpio_state.{pin}.pwm_fade** - Smooth transitions
  ```json
  {
    "enabled": true,
    "target_duty": 80,
    "duration_ms": 5000,
    "curve": "ease_in_out"
  }
  ```

### Display Requirements
1. Show **MISMATCH WARNING** (red ⚠️) if hardware_state ≠ desired state for >2s
2. Show **response_time_ms** in UI (helps diagnose slow pins)
3. Show **error_status** with human-readable messages
4. For PWM pins, show **duty_cycle** slider instead of just ON/OFF

### Recommended UI Changes
- Replace ON/OFF toggle with **Slider (0-100%)** for PWM pins
- Add **"Fade to 80% over 5s"** button for smooth transitions
- Add **Hardware Status Indicator** showing desired vs actual state
- Add **Last Hardware Sync** timestamp

### No Breaking Changes
- Old `state` field still works
- Old `enabled` field still works
- Old schedule fields still work
- Backward compatible ✅
```

### Full Enhancement (Month 2+)

```markdown
## Advanced Schedule Capabilities

### New Schedule Types
1. **Step Sequencer** - Execute multiple actions in sequence
   ```json
   {
     "type": "step_sequencer",
     "steps": [
       {"duration_ms": 1000, "action": "pwm_to_25"},
       {"duration_ms": 2000, "action": "pwm_to_100"},
       {"duration_ms": 1000, "action": "pwm_to_0"}
     ]
   }
   ```

2. **Conditional Schedule** - Run if sensor value meets threshold
   ```json
   {
     "conditions": {
       "type": "sensor_threshold",
       "sensor_pin": 18,
       "operator": ">",
       "threshold": 60  // e.g., humidity > 60%
     }
   }
   ```

3. **Weekly Schedule** - Better repetition
   ```json
   {
     "recurrence": {
       "type": "weekly",
       "days_of_week": [1, 3, 5]  // Mon, Wed, Fri
     }
   }
   ```

### UI Features
- **Visual Schedule Builder** - Drag-drop to build sequences
- **Dry Run** - Test without hardware
- **Conflict Detection** - Warn if overlapping schedules
- **Execution Monitor** - Show countdown to next run
- **Success Tracking** - Display reliability percentage

### Alerting System
When schedule fails or pin goes offline:
- ✅ Email notification
- ✅ Slack integration
- ✅ In-app alert
- ✅ Webhook to external systems

### Device Health Dashboard
Show:
- **Connection Status** - Online/Offline
- **CPU & Memory Usage** - System health
- **Pin Health** - Failed pins, response times
- **Schedule Success Rate** - How reliable?
- **GPIO Mismatch Log** - Debug hardware issues
```

---

## Part 8: Backend Implementation Checklist

### For Your Python Server

**High Priority (implement now):**
- ✅ Read `hardware_state` from GPIO, write to `gpioState.{pin}.hardware_state`
- ✅ Detect mismatches: `state !== hardware_state`, track duration
- ✅ Log response times for each GPIO operation
- ✅ Add error_status tracking (timeout, disconnect, fault)
- ✅ Track last_hardware_read timestamp
- ⏳ Support `pwm_fade` with smooth interpolation
- ⏳ Publish metrics (response_time, stability) periodically

**Medium Priority (next 2-4 weeks):**
- ⏳ Add device heartbeat (last_seen, status, firmware_version)
- ⏳ Track system metrics (CPU, memory, temp, uptime)
- ⏳ Implement schedule execution_log (status, duration, error_count)
- ⏳ Add soft_limits enforcement (max_on_duration, timeouts)

**Nice-to-Have (after MVP):**
- ⏳ Sensor-based conditions (read GPIO18 for humidity, conditionally trigger)
- ⏳ Schedule dependencies (wait for another schedule to finish)
- ⏳ Multi-pin scenes (coordinated actions)
- ⏳ Webhook notifications on errors

---

## Summary: 3 Must-Have Additions

If you implement ONLY 3 things, these will give the most value:

### 1️⃣ Mismatch Detection
```json
gpioState.{pin}.mismatch: {
  exists: true/false,
  duration_ms: 2500,
  severity: "warning"
}
```
**Why:** Tells web app if hardware is truly responding to commands

### 2️⃣ PWM Fade Support
```json
gpioState.{pin}.pwm_fade: {
  enabled: true,
  target_duty: 80,
  duration_ms: 5000,
  curve: "ease_in_out"
}
```
**Why:** Enables smooth dimming, better UX, less hardware stress

### 3️⃣ Heartbeat & Health
```json
devices.{serial}.heartbeat: {
  last_seen: timestamp,
  status: "online",
  connection_quality: 95
}
```
**Why:** Web app knows if Pi is alive, can show offline warning immediately

---

## Next Steps

1. **Review with your web app team** - Show them this doc
2. **Prioritize** - Pick Phase 1 fields to add first (non-breaking)
3. **Implement** - Update your Python server to read/write these fields
4. **Test** - Verify mismatch detection, fading, heartbeat work
5. **Monitor** - Add logging to track execution times, errors
6. **Iterate** - Add features based on what the web app team needs

