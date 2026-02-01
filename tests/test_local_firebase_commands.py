#!/usr/bin/env python3
"""
Test Script: Local Firebase Command Simulation

This script allows you to test the Firebase listener and GPIO control locally
by simulating Firestore commands being sent to your device.

Usage:
    python test_local_firebase_commands.py

This will:
1. Setup logging to see all Firebase listener activity
2. Start the RaspServer locally
3. Provide a menu to send test commands
4. Show real-time responses from the device

Requirements:
- Firebase credentials should be set up in your environment
- Run with SIMULATE_HARDWARE=true if not on a Raspberry Pi
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from datetime import datetime
from typing import Dict, Any
import json

# Configure logging BEFORE importing anything else
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

# Set SIMULATE_HARDWARE before importing config
os.environ['SIMULATE_HARDWARE'] = 'true'

from src import config
from src.core import RaspServer
from src.services.firebase_listener import FirebaseDeviceListener
from src.services.device_manager import DeviceManager


class LocalTestHarness:
    """Harness for testing Firebase commands locally"""
    
    def __init__(self):
        self.server = None
        self.device_manager = None
        self.firebase_listener = None
        self.command_counter = 0
        
    async def setup(self):
        """Setup test environment"""
        logger.info("=" * 80)
        logger.info("🧪 LOCAL FIREBASE TEST HARNESS - INITIALIZING")
        logger.info("=" * 80)
        
        try:
            logger.info(f"Configuration:")
            logger.info(f"  - Device ID: {config.DEVICE_ID}")
            logger.info(f"  - Simulate Hardware: {config.SIMULATE_HARDWARE}")
            logger.info(f"  - Platform: {config.HARDWARE_PLATFORM}")
            
            logger.info("🚀 Starting RaspServer...")
            self.server = RaspServer()
            await self.server.start()
            
            logger.info("✅ RaspServer started successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup test harness: {e}", exc_info=True)
            raise
    
    async def send_pin_control_command(self, pin: int, action: str, duration: int = None):
        """Send a pin control command"""
        self.command_counter += 1
        command_id = f"test_{self.command_counter}"
        
        command = {
            "id": command_id,
            "type": "pin_control",
            "pin": pin,
            "action": action.lower(),
        }
        
        if duration:
            command["duration"] = duration
        
        logger.info("=" * 80)
        logger.info(f"📤 SENDING TEST COMMAND #{self.command_counter}")
        logger.info("=" * 80)
        logger.info(f"Command: {json.dumps(command, indent=2)}")
        logger.info("-" * 80)
        
        # Simulate command being received by the listener
        if self.firebase_listener:
            logger.info("🎬 Simulating Firebase command reception...")
            await self.firebase_listener._process_command(command)
        
        logger.info("=" * 80)
        await asyncio.sleep(1)  # Give time for logging to finish
    
    async def send_pump_command(self, action: str, speed: int = 80, duration: int = None):
        """Send a pump control command"""
        self.command_counter += 1
        command_id = f"test_{self.command_counter}"
        
        command = {
            "id": command_id,
            "type": "pump",
            "action": action.lower(),
            "speed": speed,
        }
        
        if duration:
            command["duration"] = duration
        
        logger.info("=" * 80)
        logger.info(f"📤 SENDING TEST COMMAND #{self.command_counter} - PUMP CONTROL")
        logger.info("=" * 80)
        logger.info(f"Command: {json.dumps(command, indent=2)}")
        logger.info("-" * 80)
        
        if self.firebase_listener:
            logger.info("🎬 Simulating Firebase command reception...")
            await self.firebase_listener._process_command(command)
        
        logger.info("=" * 80)
        await asyncio.sleep(1)
    
    async def send_lights_command(self, action: str, brightness: int = 100):
        """Send a lights control command"""
        self.command_counter += 1
        command_id = f"test_{self.command_counter}"
        
        command = {
            "id": command_id,
            "type": "lights",
            "action": action.lower(),
            "brightness": brightness,
        }
        
        logger.info("=" * 80)
        logger.info(f"📤 SENDING TEST COMMAND #{self.command_counter} - LIGHTS CONTROL")
        logger.info("=" * 80)
        logger.info(f"Command: {json.dumps(command, indent=2)}")
        logger.info("-" * 80)
        
        if self.firebase_listener:
            logger.info("🎬 Simulating Firebase command reception...")
            await self.firebase_listener._process_command(command)
        
        logger.info("=" * 80)
        await asyncio.sleep(1)
    
    def show_menu(self):
        """Show test menu"""
        print("\n" + "=" * 80)
        print("🧪 LOCAL FIREBASE TEST MENU")
        print("=" * 80)
        print("1. GPIO Pin ON (GPIO 17)")
        print("2. GPIO Pin OFF (GPIO 17)")
        print("3. GPIO Pin ON with 5s duration (GPIO 27)")
        print("4. Pump START (80% speed)")
        print("5. Pump STOP")
        print("6. Pump PULSE (5s)")
        print("7. Lights ON (100% brightness)")
        print("8. Lights OFF")
        print("9. Lights ON (50% brightness)")
        print("0. Exit")
        print("=" * 80)
    
    async def run_interactive(self):
        """Run interactive test menu"""
        logger.info("\n🎬 Entering interactive test mode...")
        logger.info("Follow prompts to send Firebase commands and observe device responses")
        
        while True:
            self.show_menu()
            choice = input("Enter choice (0-9): ").strip()
            
            try:
                if choice == "1":
                    logger.info("🔌 Testing GPIO 17 ON")
                    await self.send_pin_control_command(17, "on")
                    
                elif choice == "2":
                    logger.info("🔌 Testing GPIO 17 OFF")
                    await self.send_pin_control_command(17, "off")
                    
                elif choice == "3":
                    logger.info("🔌 Testing GPIO 27 ON with 5s auto-off")
                    await self.send_pin_control_command(27, "on", duration=5)
                    logger.info("⏳ Waiting 6 seconds to see auto-off...")
                    await asyncio.sleep(6)
                    
                elif choice == "4":
                    logger.info("💧 Testing Pump START")
                    await self.send_pump_command("start", speed=80)
                    
                elif choice == "5":
                    logger.info("💧 Testing Pump STOP")
                    await self.send_pump_command("stop")
                    
                elif choice == "6":
                    logger.info("💧 Testing Pump PULSE")
                    await self.send_pump_command("pulse", duration=5)
                    logger.info("⏳ Waiting for pulse to complete...")
                    await asyncio.sleep(6)
                    
                elif choice == "7":
                    logger.info("💡 Testing Lights ON (100%)")
                    await self.send_lights_command("on", brightness=100)
                    
                elif choice == "8":
                    logger.info("💡 Testing Lights OFF")
                    await self.send_lights_command("off")
                    
                elif choice == "9":
                    logger.info("💡 Testing Lights ON (50%)")
                    await self.send_lights_command("on", brightness=50)
                    
                elif choice == "0":
                    logger.info("👋 Exiting interactive mode...")
                    break
                    
                else:
                    print("Invalid choice. Please try again.")
                    
            except Exception as e:
                logger.error(f"❌ Error processing command: {e}", exc_info=True)
    
    async def run_automated_test_sequence(self):
        """Run a pre-programmed test sequence"""
        logger.info("\n" + "=" * 80)
        logger.info("🤖 RUNNING AUTOMATED TEST SEQUENCE")
        logger.info("=" * 80)
        
        try:
            # Test 1: GPIO Pin Control
            logger.info("\n[TEST 1/6] Testing GPIO Pin Control - ON")
            await self.send_pin_control_command(17, "on")
            await asyncio.sleep(2)
            
            logger.info("[TEST 2/6] Testing GPIO Pin Control - OFF")
            await self.send_pin_control_command(17, "off")
            await asyncio.sleep(2)
            
            # Test 2: GPIO with duration
            logger.info("[TEST 3/6] Testing GPIO Pin Control with auto-off (5s)")
            await self.send_pin_control_command(27, "on", duration=5)
            await asyncio.sleep(7)
            
            # Test 3: Pump control
            logger.info("[TEST 4/6] Testing Pump START")
            await self.send_pump_command("start", speed=80)
            await asyncio.sleep(2)
            
            logger.info("[TEST 5/6] Testing Pump STOP")
            await self.send_pump_command("stop")
            await asyncio.sleep(2)
            
            # Test 4: Lights control
            logger.info("[TEST 6/6] Testing Lights ON/OFF")
            await self.send_lights_command("on", brightness=100)
            await asyncio.sleep(2)
            await self.send_lights_command("off")
            
            logger.info("\n" + "=" * 80)
            logger.info("✅ AUTOMATED TEST SEQUENCE COMPLETE")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"❌ Error running automated tests: {e}", exc_info=True)
    
    async def cleanup(self):
        """Cleanup resources"""
        logger.info("🔌 Cleaning up test harness...")
        if self.server:
            await self.server.stop()
        logger.info("✅ Cleanup complete")


async def main():
    """Main test runner"""
    harness = LocalTestHarness()
    
    try:
        await harness.setup()
        
        # Run automated tests first
        await harness.run_automated_test_sequence()
        
        # Then interactive mode
        print("\n")
        response = input("Continue to interactive mode? (y/n): ").strip().lower()
        if response == 'y':
            await harness.run_interactive()
        
    except KeyboardInterrupt:
        logger.info("⏹️  Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
    finally:
        await harness.cleanup()


if __name__ == "__main__":
    logger.info(f"Starting test harness at {datetime.now()}")
    asyncio.run(main())
