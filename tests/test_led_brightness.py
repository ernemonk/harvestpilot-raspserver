#!/usr/bin/env python3
"""
LED Brightness Control Test
Comprehensive test for LED strip MOSFET on GPIO 18
"""

import RPi.GPIO as GPIO
import time
import sys

LED_PIN = 18  # GPIO 18 (Physical Pin 12)
PWM_FREQUENCY = 1000  # Hz

def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(LED_PIN, GPIO.OUT)
    print(f"✅ GPIO {LED_PIN} configured for output")

def brightness_test():
    """Test different brightness levels"""
    print("\n" + "="*50)
    print("💡 LED BRIGHTNESS LEVELS TEST")
    print("="*50 + "\n")
    
    pwm = GPIO.PWM(LED_PIN, PWM_FREQUENCY)
    pwm.start(0)
    
    try:
        # Test specific brightness levels
        levels = [
            (0, "Off"),
            (10, "Very Dim (10%)"),
            (25, "Dim (25%)"),
            (50, "Medium (50%)"),
            (75, "Bright (75%)"),
            (100, "Full Brightness (100%)")
        ]
        
        for level, description in levels:
            pwm.ChangeDutyCycle(level)
            print(f"  Setting to {description}... ", end="", flush=True)
            time.sleep(2)
            print("✅")
        
        pwm.stop()
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        pwm.stop()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        pwm.stop()
        return False
    
    return True

def fade_effect_test():
    """Test smooth fade in/out effect"""
    print("\n" + "="*50)
    print("🌅 FADE IN/OUT EFFECT TEST")
    print("="*50 + "\n")
    
    pwm = GPIO.PWM(LED_PIN, PWM_FREQUENCY)
    pwm.start(0)
    
    try:
        # Fade in
        print("  Fading in (0% → 100%)...")
        for brightness in range(0, 101, 2):
            pwm.ChangeDutyCycle(brightness)
            time.sleep(0.02)
        print("  ✅ Complete")
        
        time.sleep(1)
        
        # Fade out
        print("  Fading out (100% → 0%)...")
        for brightness in range(100, -1, -2):
            pwm.ChangeDutyCycle(brightness)
            time.sleep(0.02)
        print("  ✅ Complete")
        
        pwm.stop()
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        pwm.stop()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        pwm.stop()
        return False
    
    return True

def rapid_pulse_test():
    """Test rapid on/off pulsing"""
    print("\n" + "="*50)
    print("⚡ RAPID PULSE TEST")
    print("="*50 + "\n")
    
    pwm = GPIO.PWM(LED_PIN, PWM_FREQUENCY)
    pwm.start(0)
    
    try:
        print("  Pulsing LED rapidly...")
        for _ in range(10):
            pwm.ChangeDutyCycle(100)
            time.sleep(0.2)
            pwm.ChangeDutyCycle(0)
            time.sleep(0.2)
        
        print("  ✅ Complete")
        pwm.stop()
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        pwm.stop()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        pwm.stop()
        return False
    
    return True

def breathing_effect_test():
    """Test breathing effect (slow fade in/out)"""
    print("\n" + "="*50)
    print("🫁 BREATHING EFFECT TEST")
    print("="*50 + "\n")
    
    pwm = GPIO.PWM(LED_PIN, PWM_FREQUENCY)
    pwm.start(0)
    
    try:
        print("  Creating breathing effect...")
        for cycle in range(3):
            # Breathe in
            for brightness in range(0, 101, 3):
                pwm.ChangeDutyCycle(brightness)
                time.sleep(0.03)
            
            # Breathe out
            for brightness in range(100, -1, -3):
                pwm.ChangeDutyCycle(brightness)
                time.sleep(0.03)
        
        print("  ✅ Complete (3 cycles)")
        pwm.stop()
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted")
        pwm.stop()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        pwm.stop()
        return False
    
    return True

def cleanup():
    GPIO.cleanup()
    print("✅ GPIO cleanup complete")

def main():
    print("\n" + "="*50)
    print("🌾 LED BRIGHTNESS CONTROL TEST")
    print("="*50)
    print(f"GPIO Pin: {LED_PIN} (Physical Pin 12)")
    print(f"PWM Frequency: {PWM_FREQUENCY} Hz")
    print("="*50)
    
    try:
        setup()
        
        results = []
        results.append(("Brightness Levels", brightness_test()))
        results.append(("Fade Effect", fade_effect_test()))
        results.append(("Rapid Pulse", rapid_pulse_test()))
        results.append(("Breathing Effect", breathing_effect_test()))
        
        # Summary
        print("\n" + "="*50)
        print("📊 TEST SUMMARY")
        print("="*50)
        for test_name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{test_name}: {status}")
        print("="*50 + "\n")
        
        if all(result for _, result in results):
            print("✅ All LED tests passed!")
            sys.exit(0)
        else:
            print("❌ Some tests failed")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
    finally:
        cleanup()

if __name__ == "__main__":
    main()
