#!/usr/bin/env python3
"""
QUICK START: Test Your Firebase GPIO Control

This file shows you the fastest way to test your setup.
"""

import subprocess
import sys
import os
from pathlib import Path

print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                  HARVEST PILOT - QUICK START TEST                          ║
╚════════════════════════════════════════════════════════════════════════════╝

This script will help you test your Firebase GPIO control system.

WHAT YOU NEED:
✓ Python 3.8+
✓ Firebase credentials set in environment or .env
✓ Requirements installed: pip install -r requirements.txt

WHAT YOU'LL TEST:
✓ Server startup and device registration
✓ Firebase listener initialization  
✓ GPIO pin control (on/off)
✓ GPIO auto-off timer
✓ Pump and light control
✓ Real-time response from Firebase

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OPTIONS:
""")

print("1. Run server only (manual testing via Firebase console)")
print("2. Run automated test suite (full end-to-end test)")
print("3. Run interactive test menu (send commands manually)")
print("4. View detailed testing guide")
print("0. Exit")
print()

choice = input("Select option (0-4): ").strip()

def run_server():
    """Run the server locally"""
    print("\n" + "="*80)
    print("Starting RaspServer in SIMULATION MODE...")
    print("="*80)
    print("\nThe server will:")
    print("  ✓ Initialize Firebase connection")
    print("  ✓ Register device")
    print("  ✓ Start listening for commands")
    print("  ✓ Log all activity to console and logs/raspserver.log")
    print("\nPress Ctrl+C to stop the server")
    print("="*80 + "\n")
    
    env = os.environ.copy()
    env['SIMULATE_HARDWARE'] = 'true'
    subprocess.run([sys.executable, 'main.py'], env=env)

def run_tests():
    """Run test suite"""
    print("\n" + "="*80)
    print("Running Automated Test Suite...")
    print("="*80 + "\n")
    
    if not Path('test_local_firebase_commands.py').exists():
        print("❌ Error: test_local_firebase_commands.py not found")
        print("Make sure you're in the harvestpilot-raspserver directory")
        sys.exit(1)
    
    env = os.environ.copy()
    env['SIMULATE_HARDWARE'] = 'true'
    
    # Run non-interactively
    subprocess.run([
        sys.executable, 
        'test_local_firebase_commands.py'
    ], env=env, input=b'n\n')

def show_guide():
    """Show testing guide"""
    guide_file = Path('FIREBASE_GPIO_TESTING_GUIDE.md')
    if guide_file.exists():
        with open(guide_file) as f:
            print(f.read())
    else:
        print("❌ Testing guide not found")

if choice == '1':
    run_server()
    
elif choice == '2':
    run_tests()
    
elif choice == '3':
    print("\n" + "="*80)
    print("Starting Interactive Test Mode...")
    print("="*80 + "\n")
    
    if not Path('test_local_firebase_commands.py').exists():
        print("❌ Error: test_local_firebase_commands.py not found")
        sys.exit(1)
    
    env = os.environ.copy()
    env['SIMULATE_HARDWARE'] = 'true'
    
    subprocess.run([sys.executable, 'test_local_firebase_commands.py'], env=env)
    
elif choice == '4':
    show_guide()
    
elif choice == '0':
    print("Goodbye!")
    sys.exit(0)
    
else:
    print("Invalid choice")
    sys.exit(1)
