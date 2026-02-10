"""
GPIO DEFAULT NAMING SYSTEM - Implementation Guide

OVERVIEW:
=========

The GPIO naming system has been completely redesigned to be:
1. INTELLIGENT: Smart names based on GPIO number + hardware capabilities
2. USER-FRIENDLY: Clear human-readable defaults that inform about the GPIO
3. SAFE: User customizations are NEVER overwritten - marked with flags
4. AUDITABLE: Tracks who customized what and when

---

CURRENT NAMING CONVENTION:
==========================

OLD (hardcoded):
  GPIO 17 → "Pump PWM"
  GPIO 18 → "LED PWM"
  GPIO 27 → "Water Level Sensor"

NEW (smart, informative):
  GPIO 17 (PIN11) - PUMP (PWM Speed/Intensity Control)
  GPIO 18 (PIN12) - LIGHT (PWM Speed/Intensity Control)
  GPIO 27 (PIN13) - SENSOR (Water Level Detection)

Benefits:
  ✓ GPIO number is prominent (easy to reference in schematics)
  ✓ Physical pin number included (helps with wiring verification)
  ✓ Device type is clear (PUMP, LIGHT, MOTOR, SENSOR)
  ✓ Capability is explicit (what this pin does)
  ✓ Self-documenting - the name tells you about the hardware

---

USER CUSTOMIZATION:
===================

When a user sets a custom name for a GPIO, the system:

1. Stores the custom name in Firestore
2. Marks it with: name_customized = true
3. Saves customization metadata:
   - customized_at: ISO timestamp when it was changed
   - original/default_name: Stores the smart default for reference

4. FUTURE INITIALIZATIONS PRESERVE IT:
   - On reboot, the Pi checks name_customized flag
   - If true, the custom name is NEVER overwritten
   - If false, can update to a better smart default

This is CRITICAL for business operations - users might have configured
integrations, dashboards, or automation rules based on GPIO names.

---

FIRESTORE SCHEMA:
=================

gpioState.17 (example pin):
{
  "pin": 17,
  "physical_pin": 11,
  "mode": "output",
  "device_type": "pump",
  
  // NAMING FIELDS (from Pi on boot)
  "name": "GPIO17 (PIN11) - PUMP (PWM Speed/Intensity Control)",
  "default_name": "GPIO17 (PIN11) - PUMP (PWM Speed/Intensity Control)",
  "name_customized": false,
  
  // CUSTOMIZATION AUDIT TRAIL (only if customized)
  "customized_at": "2025-02-09T14:32:00.123456",
  
  // STATE FIELDS (from Pi in real-time)
  "state": false,           ← WEBAPP sets desired state
  "hardwareState": false,   ← Pi reads actual state
  "mismatch": false,        ← Alert if state != hardwareState
  "lastHardwareRead": <timestamp>,
  
  // WEBAPP CONTROLS THESE (Pi never overwrites)
  "enabled": true           ← Webapp controls if pin is active
}

---

CODE CHANGES:
=============

1. NEW MODULE: src/utils/gpio_naming.py
   - GPIONamer: Generates smart default names
   - GPIONameManager: Safely handles name updates with customization tracking
   - GPIOCapability enum: Describes what each GPIO can do

2. UPDATED: src/services/gpio_actuator_controller.py
   - _sync_initial_state_to_firestore(): Now uses smart naming
   - rename_gpio_pin(): New method to safely rename from webapp
   - reset_gpio_name_to_default(): Revert customization
   - get_gpio_info(): Get detailed GPIO info including name status

3. UPDATED: src/utils/pin_config.py
   - create_default_config(): Uses smart naming
   - assign_pin_to_device(): Smart naming option
   - rename_pin(): Mark names as user-customized
   - reset_pin_name(): Revert to smart default

4. NEW MODULE: src/services/gpio_naming_api.py
   - REST API for name management
   - get_gpio_info(): Get GPIO details
   - rename_gpio(): Set custom name safely
   - reset_gpio_name_to_default(): Revert customization
   - batch_rename_gpios(): Rename multiple at once

---

API EXAMPLES:
=============

PYTHON (GPIO Controller):
-------

from src.services.gpio_actuator_controller import get_gpio_controller

controller = get_gpio_controller()

# Get GPIO info
info = controller.get_gpio_info(17)
print(info['current_name'])         # Current name
print(info['default_name'])         # Smart default
print(info['name_customized'])      # Is it custom or default?

# Rename a GPIO (marks as customized)
success = controller.rename_gpio_pin(17, "Primary Water Pump - West Rack")
# → Now name_customized = true, protecting the custom name

# Reset to smart default (removes customization flag)
success = controller.reset_gpio_name_to_default(17)
# → Now name_customized = false, can update on next boot

REST API (via gpio_naming_api.py):
---

GET /api/gpio/17/info
→ Returns full GPIO info including name status

POST /api/gpio/17/rename
Body: {"name": "Primary Water Pump - West Rack"}
→ Renames and marks as customized

POST /api/gpio/17/reset-name
→ Reverts to smart default, removes customization flag

POST /api/gpio/batch-rename
Body: {
  "17": "Pump 1",
  "18": "Lights - North",
  "27": "Water Level"
}
→ Renames multiple GPIOs at once

---

SAFETY GUARANTEES:
==================

✅ NEW PINS:
   - Get smart default name on first initialization
   - User can customize if desired

✅ EXISTING PINS (non-customized):
   - If old hardcoded default (e.g., "Pump PWM")
   - CAN be updated to smarter version
   - Example: "Pump PWM" → "GPIO17 (PIN11) - PUMP (PWM Speed/Intensity Control)"

✅ EXISTING PINS (user-customized):
   - marked with name_customized = true
   - NEVER overwritten on reboot
   - Protected even if firmware updates the smart default logic
   - Preserves business-critical naming

✅ AUDIT TRAIL:
   - Every customization has a timestamp
   - Know when and if a name changed
   - Helps debug if integrations break

✅ REVERSIBILITY:
   - Can always revert to smart default via reset_gpio_name_to_default()
   - Customization metadata kept for reference (default_name field)
   - User can go back and forth as needed

---

EXAMPLE WORKFLOW:
=================

1. Pi boots up first time:
   - No pins in Firestore
   - Creates: "GPIO17 (PIN11) - PUMP (PWM Speed/Intensity Control)"
   - Sets: name_customized = false

2. User customizes in webapp:
   - Changes name to "Irrigation Pump - Main System"
   - Calls rename_gpio_pin(17, "Irrigation Pump - Main System")
   - System sets: name_customized = true, customized_at = <timestamp>

3. Pi reboots:
   - Reads Firestore, sees name_customized = true
   - PRESERVES "Irrigation Pump - Main System"
   - Does NOT overwrite with smart default
   - Business operations unaffected ✓

4. User wants to clean up later:
   - Can call reset_gpio_name_to_default(17)
   - Sets: name_customized = false
   - Name reverts to smart default on next update

---

MIGRATION FROM OLD SYSTEM:
===========================

Old hardcoded names:
  17: "Pump PWM"
  18: "LED PWM"
  13: "LED Relay"
  4: "DHT22 (Temp/Humidity)"

Will be detected as old defaults and can be upgraded to:
  17: "GPIO17 (PIN11) - PUMP (PWM Speed/Intensity Control)"
  18: "GPIO18 (PIN12) - LIGHT (PWM Speed/Intensity Control)"
  13: "GPIO13 (PIN33) - LIGHT (Relay Control On/Off)"
  4: "GPIO4 (PIN7) - SENSOR (Temperature+Humidity Sensor)"

Smart detection prevents accidental overwrites - if your users have
set other custom names (that don't match old defaults), they're safe.

---

TESTING GUIDELINES:
===================

✓ Test 1: New GPIO initialization
  - Boot Pi with fresh Firestore
  - Verify pins get smart default names
  - Check all fields present (default_name, name_customized=false, etc)

✓ Test 2: User customization
  - Rename a GPIO via rename_gpio_pin()
  - Verify name_customized = true, customized_at is set
  - Reboot Pi and verify name is PRESERVED

✓ Test 3: Old pin with custom name
  - Have old pins in Firestore with custom names
  - Reboot Pi
  - Verify Pi respects the custom names (doesn't overwrite)

✓ Test 4: Revert customization
  - Customize a GPIO name
  - Call reset_gpio_name_to_default()
  - Verify name_customized = false
  - Verify name is the smart default

✓ Test 5: Batch rename
  - Call batch_rename_gpios() with multiple pins
  - Verify each one renamed and marked customized
  - Check error handling for invalid pins

---

MODULE DEPENDENCIES:
====================

gpio_naming.py → Uses:
  - Enum
  - typing
  - logging

gpio_actuator_controller.py → Uses:
  - gpio_naming.py (GPIONameManager, GPIONamer)

pin_config.py → Conditionally uses:
  - gpio_naming.py (GPIONamer, lazy imported)
  - fallback to _generate_fallback_name() if unavailable

gpio_naming_api.py → Uses:
  - gpio_actuator_controller.py

---

PERFORMANCE IMPACT:
===================

✓ Smart naming generation: < 1ms per pin (string formatting only)
✓ Customization checks: < 2ms (dict lookup check)
✓ No impact on real-time GPIO operations
✓ Firestore updates batched as before

---

BACKWARDS COMPATIBILITY:
=========================

✓ Old pins without new fields will still work
✓ System auto-fills missing fields on first boot
✓ Reading old pins: safe, will get existing names
✓ Writing to old pins: new fields added, old preserved
✓ No migration script needed - happens automatically

---

REFERENCES:
===========

Files Modified:
  - src/utils/gpio_naming.py (NEW)
  - src/services/gpio_actuator_controller.py
  - src/utils/pin_config.py
  - src/services/gpio_naming_api.py (NEW)

Key Classes:
  - GPIONamer: Smart name generation
  - GPIONameManager: Customization tracking
  - GPIOActuatorController: Enhanced with name management
  - PinConfigManager: Smart naming integration
  - GPIONamingAPI: REST/Python API for names

For questions or issues: Check the docstrings in each class
"""
