#!/usr/bin/env python3
"""
Pump Control Test
Test pump MOSFET on GPIO 17 (Physical Pin 11)
"""

import RPi.GPIO as GPIO
import time
import sys

PUMP_PIN = 17  # GPIO 17 (Physical Pin 11)
PWM_FREQUENCY = 1000  # Hz

def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(PUMP_PIN, GPIO.OUT)
    GPIO.output(PUMP_PIN, GPIO.LOW)  # Start with pump off
    print(f"✅ GPIO {PUMP_PIN} configured for pump control")

def on_off_test():
    """Test basic pump ON/OFF"""
    print("\n" + "="*50)
    print("💧 PUMP ON/OFF TEST")
    print("="*50 + "\n")
    
    try:
        for cycle in range(3):
            print(f"  Cycle {cycle + 1}:")
            
            print("    Turning pump ON... ", end="", flush=True)
            GPIO.output(PUMP_PIN, GPIO.HIGH)
            time.sleep(2)
            print("✅")
            
            print("    Turning pump OFF... ", end="", flush=True)
            GPIO.output(PUMP_PIN, GPIO.LOW)
            time.sleep(1)
            print("✅")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        GPIO.output(PUMP_PIN, GPIO.LOW)
        return False

def pwm_speed_test():
    """Test pump speed control via PWM"""
    print("\n" + "="*50)
    print("⚡ PUMP PWM SPEED TEST")
    print("="*50 + "\n")
    
    pwm = GPIO.PWM(PUMP_PIN, PWM_FREQUENCY)
    pwm.start(0)
    
    try:
        speeds = [30, 50, 75, 100]
        
        for speed in speeds:
            pwm.ChangeDutyCycle(speed)
            print(f"  Pump Speed: {speed}% - ", end="", flush=True)
            time.sleep(2)
            print("✅")
        
        pwm.stop()
        GPIO.output(PUMP_PIN, GPIO.LOW)
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        pwm.stop()
        GPIO.output(PUMP_PIN, GPIO.LOW)
        return False

def gradual_ramp_test():
    """Test gradual speed increase and decrease"""
    print("\n" + "="*50)
    print("📈 PUMP GRADUAL RAMP TEST")
    print("="*50 + "\n")
    
    pwm = GPIO.PWM(PUMP_PIN, PWM_FREQUENCY)
    pwm.start(0)
    
    try:
        print("  Ramping up (0% → 100%)...")
        for speed in range(0, 101, 10):
            pwm.ChangeDutyCycle(speed)
            print(f"    Speed: {speed}% - ", end="", flush=True)
            time.sleep(0.3)
            print("✅")
        
        time.sleep(1)
        
        print("\n  Ramping down (100% → 0%)...")
        for speed in range(100, -1, -10):
            pwm.ChangeDutyCycle(speed)
            print(f"    Speed: {speed}% - ", end="", flush=True)
            time.sleep(0.3)
            print("✅")
        
        pwm.stop()
        GPIO.output(PUMP_PIN, GPIO.LOW)
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        pwm.stop()
        GPIO.output(PUMP_PIN, GPIO.LOW)
        return False

def irrigation_cycle_test():
    """Test realistic irrigation cycle"""
    print("\n" + "="*50)
    print("🌱 IRRIGATION CYCLE TEST (30 seconds)")
    print("="*50 + "\n")
    
    pwm = GPIO.PWM(PUMP_PIN, PWM_FREQUENCY)
    pwm.start(0)
    
    try:
        # Ramp up
        print("  Ramping up pump (2 seconds)...")
        for speed in range(0, 81, 10):
            pwm.ChangeDutyCycle(speed)
            time.sleep(0.2)
        print("  ✅")
        
        # Run at 80%
        print("  Running irrigation at 80% for 10 seconds...")
        pwm.ChangeDutyCycle(80)
        time.sleep(10)
        print("  ✅")
        
        # Ramp down
        print("  Ramping down pump (2 seconds)...")
        for speed in range(80, -1, -10):
            pwm.ChangeDutyCycle(speed)
            time.sleep(0.2)
        print("  ✅")
        
        print("  Irrigation cycle complete!")
        
        pwm.stop()
        GPIO.output(PUMP_PIN, GPIO.LOW)
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        pwm.stop()
        GPIO.output(PUMP_PIN, GPIO.LOW)
        return False

def long_run_test():
    """Test pump stability over extended run"""
    print("\n" + "="*50)
    print("🔄 PUMP LONG-RUN STABILITY TEST (30 seconds)")
    print("="*50 + "\n")
    
    pwm = GPIO.PWM(PUMP_PIN, PWM_FREQUENCY)
    pwm.start(70)
    
    try:
        print("  Running pump at 70% for 30 seconds...")
        for i in range(30):
            print(f"    {i+1}s... ", end="", flush=True)
            time.sleep(1)
            if (i + 1) % 5 == 0:
                print("✅")
            else:
                print("")
        
        print("  ✅ Pump ran stably for 30 seconds")
        pwm.stop()
        GPIO.output(PUMP_PIN, GPIO.LOW)
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        pwm.stop()
        GPIO.output(PUMP_PIN, GPIO.LOW)
        return False

def cleanup():
    GPIO.output(PUMP_PIN, GPIO.LOW)
    GPIO.cleanup()
    print("✅ GPIO cleanup complete")

def main():
    print("\n" + "="*50)
    print("🌾 PUMP CONTROL TEST SUITE")
    print("="*50)
    print(f"GPIO Pin: {PUMP_PIN} (Physical Pin 11)")
    print(f"PWM Frequency: {PWM_FREQUENCY} Hz")
    print("="*50)
    
    try:
        setup()
        
        results = []
        results.append(("On/Off Control", on_off_test()))
        results.append(("PWM Speed Control", pwm_speed_test()))
        results.append(("Gradual Ramp", gradual_ramp_test()))
        results.append(("Irrigation Cycle", irrigation_cycle_test()))
        results.append(("Long-Run Stability", long_run_test()))
        
        # Summary
        print("\n" + "="*50)
        print("📊 TEST SUMMARY")
        print("="*50)
        for test_name, result in results:
            status = "✅ PASSED" if result else "❌ FAILED"
            print(f"{test_name}: {status}")
        print("="*50 + "\n")
        
        if all(result for _, result in results):
            print("✅ All pump tests passed!")
            sys.exit(0)
        else:
            print("❌ Some tests failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
    finally:
        cleanup()

if __name__ == "__main__":
    main()
