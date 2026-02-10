#!/usr/bin/env python3
"""
Test script for GPIO Naming System

Tests:
  1. Smart name generation with GPIO + capabilities
  2. User customization tracking
  3. Preservation of customized names
  4. Resetting to smart defaults
  5. Backward compatibility with old naming
"""

import sys
import json
from pathlib import Path
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.gpio_naming import GPIONamer, GPIONameManager, GPIOCapability
from src.utils.pin_config import PinConfigManager, GPIOPin, GPIOConfiguration


def test_gpio_namer():
    """Test smart name generation"""
    print("\n" + "="*70)
    print("TEST 1: Smart Name Generation (GPIONamer)")
    print("="*70)
    
    namer = GPIONamer()
    
    test_cases = [
        (17, "pump", "Pump PWM"),
        (18, "light", "LED Strip"),
        (27, "sensor", "Water Level"),
        (4, "sensor", "DHT Sensor"),
        (2, "motor", "Motor Control"),
    ]
    
    for gpio_num, device_type, old_name in test_cases:
        smart_name = namer.generate_default_name(gpio_num, device_type)
        physical_pin = namer.get_physical_pin(gpio_num)
        
        print(f"\n  GPIO{gpio_num} ({device_type}):")
        print(f"    Old name:    {old_name}")
        print(f"    Smart name:  {smart_name}")
        print(f"    Physical PIN: {physical_pin}")
        
        # Verify format
        assert f"GPIO{gpio_num}" in smart_name, f"Missing GPIO number in {smart_name}"
        assert f"PIN{physical_pin}" in smart_name, f"Missing physical pin in {smart_name}"
        assert device_type.upper() in smart_name.upper(), f"Missing device type in {smart_name}"
        
        print(f"    ✅ PASS")
    
    return True


def test_name_manager():
    """Test customization tracking"""
    print("\n" + "="*70)
    print("TEST 2: Name Manager - Customization Tracking")
    print("="*70)
    
    manager = GPIONameManager()
    
    # Test 1: Create new pin with smart default
    print("\n  2.1: Create new pin with smart default")
    entry = manager.create_firestore_entry(
        gpio_number=17,
        device_type="pump",
        user_custom_name=None
    )
    
    assert entry['name_customized'] == False, "New pin should not be marked customized"
    assert entry['pin'] == 17
    assert "GPIO17" in entry['name']
    print(f"    Created: {entry['name']}")
    print(f"    Customized: {entry['name_customized']}")
    print(f"    ✅ PASS")
    
    # Test 2: Create pin with user custom name
    print("\n  2.2: Create pin with user custom name")
    entry2 = manager.create_firestore_entry(
        gpio_number=17,
        device_type="pump",
        user_custom_name="Primary Irrigation System"
    )
    
    assert entry2['name_customized'] == True, "Custom name should be marked customized"
    assert entry2['name'] == "Primary Irrigation System"
    assert 'customized_at' in entry2
    print(f"    Created: {entry2['name']}")
    print(f"    Customized: {entry2['name_customized']}")
    print(f"    ✅ PASS")
    
    # Test 3: Preserve customized name
    print("\n  2.3: Preserve user-customized names")
    preserve, reason = manager.should_preserve_name({
        'name': "Primary Irrigation System",
        'name_customized': True
    })
    
    assert preserve == True, "Should preserve customized names"
    print(f"    Preserve: {preserve}")
    print(f"    Reason: {reason}")
    print(f"    ✅ PASS")
    
    # Test 4: Update old default name
    print("\n  2.4: Update old default name to smart default")
    preserve, reason = manager.should_preserve_name({
        'name': "Pump PWM",
        'name_customized': False
    })
    
    assert preserve == False, "Should allow updating old defaults"
    print(f"    Preserve: {preserve}")
    print(f"    Reason: {reason}")
    print(f"    ✅ PASS")
    
    # Test 5: Rename operation
    print("\n  2.5: Rename GPIO and mark as customized")
    updated = manager.rename_gpio_pin(
        gpio_number=17,
        new_name="West Rack Pump - Main System",
        existing_pin_data=entry
    )
    
    assert updated['name_customized'] == True
    assert updated['name'] == "West Rack Pump - Main System"
    assert 'customized_at' in updated
    print(f"    New name: {updated['name']}")
    print(f"    Customized: {updated['name_customized']}")
    print(f"    ✅ PASS")
    
    # Test 6: Reset to default
    print("\n  2.6: Reset name to smart default")
    reset = manager.reset_to_smart_default(
        gpio_number=17,
        existing_pin_data=updated
    )
    
    assert reset['name_customized'] == False
    assert 'GPIO17' in reset['name']
    assert 'customized_at' not in reset or reset.get('customized_at') is None
    print(f"    Reset to: {reset['name']}")
    print(f"    Customized: {reset['name_customized']}")
    print(f"    ✅ PASS")
    
    return True


def test_backward_compatibility():
    """Test that old hardcoded names are recognized"""
    print("\n" + "="*70)
    print("TEST 3: Backward Compatibility - Old vs New Names")
    print("="*70)
    
    manager = GPIONameManager()
    
    old_names_map = {
        (17, "Pump PWM"): False,           # Can update (old default)
        (18, "LED PWM"): False,            # Can update (old default)
        (27, "Water Level Sensor"): False, # Can update (old default)
        (4, "DHT22 (Temp/Humidity)"): False, # Can update (old default)
        (17, "Irrigation System 1"): True, # Should preserve (custom)
    }
    
    for (gpio_num, name), should_preserve in old_names_map.items():
        preserve, reason = manager.should_preserve_name({
            'name': name,
            'name_customized': should_preserve
        })
        
        print(f"\n  GPIO{gpio_num}: '{name}'")
        print(f"    Preserve: {preserve} (expected: {should_preserve})")
        print(f"    Reason: {reason}")
        
        assert preserve == should_preserve, f"Mismatch for {name}"
        print(f"    ✅ PASS")
    
    return True


def test_pin_config_integration():
    """Test PinConfigManager integration with smart naming"""
    print("\n" + "="*70)
    print("TEST 4: PinConfigManager Integration")
    print("="*70)
    
    # Create temporary config directory
    import tempfile
    temp_dir = tempfile.mkdtemp()
    
    manager = PinConfigManager(config_dir=temp_dir)
    
    # Create default config
    print("\n  4.1: Create default config with smart naming")
    config = manager.create_default_config(
        pi_model="Raspberry Pi 4 Model B",
        module_id="test-module-001",
        description="Test configuration"
    )
    
    assert len(config.pins) > 0
    assert config.pi_model == "Raspberry Pi 4 Model B"
    print(f"    Created config with {len(config.pins)} pins")
    
    for pin in config.pins[:3]:  # Print first 3 pins
        print(f"    - GPIO{pin.gpio_number}: {pin.name}")
        assert "GPIO" in pin.name, f"Pin name missing GPIO number: {pin.name}"
        assert "PIN" in pin.name, f"Pin name missing physical PIN: {pin.name}"
    
    print(f"    ✅ PASS")
    
    # Test rename
    print("\n  4.2: Test rename_pin with customization tracking")
    result = manager.rename_pin(17, "Test Custom Name")
    
    assert result == True
    
    # Reload and verify
    loaded = manager.load_config()
    pump_pin = None
    for pin in loaded.pins:
        if pin.gpio_number == 17:
            pump_pin = pin
            break
    
    assert pump_pin is not None
    assert pump_pin.name == "Test Custom Name"
    assert pump_pin.name_customized == True
    assert pump_pin.customized_at is not None
    
    print(f"    Renamed to: {pump_pin.name}")
    print(f"    Customized: {pump_pin.name_customized}")
    print(f"    ✅ PASS")
    
    # Test reset
    print("\n  4.3: Test reset_pin_name")
    result = manager.reset_pin_name(17)
    
    assert result == True
    
    # Reload and verify
    loaded = manager.load_config()
    pump_pin = None
    for pin in loaded.pins:
        if pin.gpio_number == 17:
            pump_pin = pin
            break
    
    assert pump_pin is not None
    assert pump_pin.name_customized == False
    assert "GPIO17" in pump_pin.name
    
    print(f"    Reset to: {pump_pin.name}")
    print(f"    Customized: {pump_pin.name_customized}")
    print(f"    ✅ PASS")
    
    # Cleanup
    import shutil
    shutil.rmtree(temp_dir)
    
    return True


def main():
    """Run all tests"""
    print("\n" + "="*70)
    print("GPIO NAMING SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    tests = [
        ("Smart Name Generation", test_gpio_namer),
        ("Name Manager", test_name_manager),
        ("Backward Compatibility", test_backward_compatibility),
        ("PinConfig Integration", test_pin_config_integration),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✅ {test_name}: PASSED")
        except Exception as e:
            failed += 1
            print(f"\n❌ {test_name}: FAILED")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"  Total:  {len(tests)}")
    print(f"  Passed: {passed} ✅")
    print(f"  Failed: {failed} ❌")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
