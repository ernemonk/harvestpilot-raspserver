#!/usr/bin/env python3
"""
Quick GPIO Status Checker for HarvestPilot
Shows which pins are ON/OFF with visual indicators
"""

import sys
import os
sys.path.insert(0, '/home/monkphx/harvestpilot-raspserver')

from datetime import datetime

# Validate environment setup
if 'PYTHONPATH' not in os.environ:
    os.environ['PYTHONPATH'] = '/home/monkphx/harvestpilot-raspserver'

try:
    from src import config
except ImportError as e:
    print(f"❌ FATAL: Cannot import config module: {e}")
    print(f"   PYTHONPATH: {os.environ.get('PYTHONPATH', 'NOT SET')}")
    print(f"   Current dir: {os.getcwd()}")
    print(f"   sys.path: {sys.path}")
    sys.exit(1)

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
except ImportError as e:
    print(f"❌ FATAL: Firebase not installed: {e}")
    print(f"   Run: pip install firebase-admin")
    sys.exit(1)

# Colors for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def get_gpio_states_from_firestore():
    """Get GPIO states from Firestore"""
    try:
        # Check if credentials file exists
        if not os.path.exists(config.FIREBASE_CREDENTIALS_PATH):
            print(f"{Colors.RED}[!] Firebase credentials not found at: {config.FIREBASE_CREDENTIALS_PATH}{Colors.END}")
            return None
        
        cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        
        db = firestore.client()
        
        # Validate hardware serial
        hardware_serial = config.HARDWARE_SERIAL
        if not hardware_serial or hardware_serial == "unknown-device":
            print(f"{Colors.RED}[!] Cannot determine hardware serial: {hardware_serial}{Colors.END}")
            return None
        
        doc = db.collection('devices').document(hardware_serial).get()
        
        if not doc.exists:
            print(f"{Colors.RED}[!] Device not found in Firestore: {hardware_serial}{Colors.END}")
            return None
        
        data = doc.to_dict()
        return data.get('gpioState', {})
    
    except Exception as e:
        print(f"{Colors.RED}[!] Error connecting to Firestore: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        return None

def get_gpio_states_from_hardware():
    """Get actual GPIO states from hardware (requires RPi)"""
    try:
        from src.utils.gpio_import import GPIO, GPIO_AVAILABLE
        from src import config
        
        if not GPIO_AVAILABLE or config.SIMULATE_HARDWARE:
            return None
        
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # All pins we're monitoring
        pins = [2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27]
        states = {}
        
        for pin in pins:
            try:
                GPIO.setup(pin, GPIO.IN)
                state = GPIO.input(pin)
                states[str(pin)] = {'state': state == 1}
            except:
                pass
        
        GPIO.cleanup()
        return states
    
    except Exception as e:
        print(f"{Colors.YELLOW}[~] Hardware GPIO check unavailable: {e}{Colors.END}")
        return None

def print_header():
    """Print header"""
    print(f"\n{Colors.CYAN}{'='*60}")
    print(f"          🔌 HarvestPilot GPIO Status Report")
    print(f"{'='*60}{Colors.END}")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Device ID: {config.HARDWARE_SERIAL}")
    print()

def print_pin_group(group_name, pins_dict):
    """Print a group of pins"""
    print(f"{Colors.BOLD}{group_name}{Colors.END}")
    print("-" * 60)
    
    for pin_str in sorted(pins_dict.keys(), key=lambda x: int(x)):
        pin_data = pins_dict[pin_str]
        
        if isinstance(pin_data, dict):
            state = pin_data.get('state', False)
            name = pin_data.get('name', 'Unknown Device')
            
            # Visual indicator
            if state:
                indicator = f"{Colors.GREEN}🟢 ON {Colors.END}"
            else:
                indicator = f"{Colors.RED}⚫ OFF{Colors.END}"
            
            print(f"  GPIO{pin_str:2s}: {indicator}  {name}")

def main():
    """Main function"""
    try:
        print_header()
        
        # Try Firestore first (most reliable)
        gpio_states = get_gpio_states_from_firestore()
        
        if gpio_states:
            print(f"{Colors.BLUE}📡 Source: Firestore (Cloud State){Colors.END}\n")
            
            # Group pins by function
            actuators = {}
            motors = {}
            other = {}
            
            for pin, data in gpio_states.items():
                if isinstance(data, dict):
                    name = data.get('name', '')
                    
                    if 'Motor' in name:
                        motors[pin] = data
                    elif 'Pump' in name or 'LED' in name:
                        actuators[pin] = data
                    else:
                        other[pin] = data
            
            if actuators:
                print_pin_group("🔧 Main Actuators", actuators)
                print()
            
            if motors:
                print_pin_group("🎛️ Harvest Motors", motors)
                print()
            
            if other:
                print_pin_group("📌 Other Pins", other)
                print()
        else:
            print(f"{Colors.YELLOW}[!] Could not retrieve Firestore data{Colors.END}\n")
            
            # Try hardware
            hw_states = get_gpio_states_from_hardware()
            if hw_states:
                print(f"{Colors.BLUE}🔌 Source: Hardware GPIO (Direct Read){Colors.END}\n")
                print_pin_group("GPIO Pins", hw_states)
            else:
                print(f"{Colors.RED}[!] Could not retrieve GPIO states from either source{Colors.END}")
                return 1
        
        # Summary statistics
        print()
        print(f"{Colors.CYAN}{'='*60}")
        print(f"Tip: Check Firestore console for more detailed state info")
        print(f"Path: devices/{config.HARDWARE_SERIAL}/gpioState")
        print(f"{'='*60}{Colors.END}\n")
        
        return 0
    
    except Exception as e:
        print(f"{Colors.RED}[!] Unexpected error in main: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}[!] Interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"{Colors.RED}[!] FATAL: Unexpected error: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
