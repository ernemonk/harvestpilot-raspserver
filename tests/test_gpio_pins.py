#!/usr/bin/env python3
"""
GPIO Pin Test Script for HarvestPilot
Tests LED brightness control and pump MOSFET on actual pins
"""

import RPi.GPIO as GPIO
import time
import sys
import os

# Configuration
LED_PWM_PIN = 18  # GPIO 18 (Physical Pin 12) - LED strip MOSFET
PUMP_PWM_PIN = 17  # GPIO 17 (Physical Pin 11) - Pump MOSFET
LED_PWM_FREQUENCY = 1000  # Hz
PUMP_PWM_FREQUENCY = 1000  # Hz

def setup_gpio():
    """Initialize GPIO pins"""
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup LED pin
        GPIO.setup(LED_PWM_PIN, GPIO.OUT)
        print(f"✅ LED Pin {LED_PWM_PIN} (Physical Pin 12) configured")
        
        # Setup Pump pin
        GPIO.setup(PUMP_PWM_PIN, GPIO.OUT)
        print(f"✅ Pump Pin {PUMP_PWM_PIN} (Physical Pin 11) configured")
        
        return True
    except Exception as e:
        print(f"❌ GPIO Setup Error: {e}")
        return False

def test_led_brightness():
    """Test LED brightness control with PWM"""
    print("\n" + "="*50)
    print("🔆 LED BRIGHTNESS TEST (GPIO 18)")
    print("="*50)
    
    try:
        led_pwm = GPIO.PWM(LED_PWM_PIN, LED_PWM_FREQUENCY)
        led_pwm.start(0)
        
        brightness_levels = [0, 25, 50, 75, 100]
        
        for brightness in brightness_levels:
            led_pwm.ChangeDutyCycle(brightness)
            print(f"  💡 LED Brightness: {brightness}% - ", end="", flush=True)
            time.sleep(1)
            print("✅")
        
        # Fade in/out effect
        print("\n  Fading in...")
        for i in range(0, 101, 5):
            led_pwm.ChangeDutyCycle(i)
            time.sleep(0.05)
        
        print("  Fading out...")
        for i in range(100, -1, -5):
            led_pwm.ChangeDutyCycle(i)
            time.sleep(0.05)
        
        led_pwm.stop()
        print("✅ LED test complete!\n")
        return True
        
    except Exception as e:
        print(f"❌ LED Test Error: {e}\n")
        return False

def test_pump_control():
    """Test pump MOSFET control"""
    print("="*50)
    print("💧 PUMP MOSFET TEST (GPIO 17)")
    print("="*50)
    
    try:
        pump_pwm = GPIO.PWM(PUMP_PWM_PIN, PUMP_PWM_FREQUENCY)
        
        # Test ON/OFF
        print("  Testing pump ON...")
        GPIO.output(PUMP_PWM_PIN, GPIO.HIGH)
        time.sleep(2)
        print("  ✅ Pump ON for 2 seconds")
        
        print("  Testing pump OFF...")
        GPIO.output(PUMP_PWM_PIN, GPIO.LOW)
        time.sleep(1)
        print("  ✅ Pump OFF")
        
        # Test PWM speeds
        print("\n  Testing pump PWM speeds...")
        pump_pwm.start(0)
        
        speeds = [30, 60, 100]
        for speed in speeds:
            pump_pwm.ChangeDutyCycle(speed)
            print(f"  💧 Pump Speed: {speed}% - ", end="", flush=True)
            time.sleep(1.5)
            print("✅")
        
        pump_pwm.stop()
        GPIO.output(PUMP_PWM_PIN, GPIO.LOW)
        print("✅ Pump test complete!\n")
        return True
        
    except Exception as e:
        print(f"❌ Pump Test Error: {e}\n")
        return False

def test_simultaneous():
    """Test LED and Pump together"""
    print("="*50)
    print("⚡ SIMULTANEOUS CONTROL TEST")
    print("="*50)
    
    try:
        led_pwm = GPIO.PWM(LED_PWM_PIN, LED_PWM_FREQUENCY)
        pump_pwm = GPIO.PWM(PUMP_PWM_PIN, PUMP_PWM_FREQUENCY)
        
        led_pwm.start(0)
        pump_pwm.start(0)
        
        print("  Running LED and Pump together...")
        
        for i in range(0, 101, 20):
            led_pwm.ChangeDutyCycle(i)
            pump_pwm.ChangeDutyCycle(i)
            print(f"  LED: {i}% | Pump: {i}% - ", end="", flush=True)
            time.sleep(0.5)
            print("✅")
        
        print("  Turning off both...")
        led_pwm.ChangeDutyCycle(0)
        pump_pwm.ChangeDutyCycle(0)
        time.sleep(1)
        
        led_pwm.stop()
        pump_pwm.stop()
        print("✅ Simultaneous test complete!\n")
        return True
        
    except Exception as e:
        print(f"❌ Simultaneous Test Error: {e}\n")
        return False

def cleanup():
    """Cleanup GPIO"""
    try:
        GPIO.cleanup()
        print("✅ GPIO cleanup complete")
    except Exception as e:
        print(f"⚠️  Cleanup error: {e}")

def main():
    """Main test routine"""
    print("\n" + "="*50)
    print("🌾 HARVESTPILOT GPIO TEST SUITE")
    print("="*50)
    print(f"LED Pin: GPIO {LED_PWM_PIN} (Physical Pin 12)")
    print(f"Pump Pin: GPIO {PUMP_PWM_PIN} (Physical Pin 11)")
    print("="*50 + "\n")
    
    # Setup GPIO
    if not setup_gpio():
        print("Failed to setup GPIO. Exiting.")
        sys.exit(1)
    
    results = []
    
    try:
        # Run tests
        results.append(("LED Brightness", test_led_brightness()))
        results.append(("Pump Control", test_pump_control()))
        results.append(("Simultaneous", test_simultaneous()))
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        cleanup()
    
    # Summary
    print("="*50)
    print("📊 TEST SUMMARY")
    print("="*50)
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    print("="*50 + "\n")
    
    # Return exit code
    if all(result for _, result in results):
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
