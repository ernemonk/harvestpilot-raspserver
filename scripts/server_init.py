"""
Server Initialization Script - Auto-register Pi to Firestore

Runs on service startup to:
1. Get unique Raspberry Pi hardware ID
2. Detect network/system info
3. Register device in Firestore with unique ID
4. Store mapping between hardware ID and config ID

This script runs BEFORE the main service starts, ensuring device is registered.
"""

import os
import sys
import json
import subprocess
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PiInitializer:
    """Initialize and register Pi with Firestore"""
    
    def __init__(self):
        self.pi_id = None
        self.pi_serial = None
        self.pi_mac = None
        self.pi_hostname = None
        self.config_device_id = None
        self.organization_id = None
        self.firestore = None
        
    def get_pi_serial(self) -> str:
        """Get Raspberry Pi serial from /proc/cpuinfo"""
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('Serial'):
                        serial = line.split(':')[1].strip()
                        logger.info(f"✅ Got Pi Serial: {serial}")
                        return serial
        except Exception as e:
            logger.error(f"❌ Could not read Pi serial: {e}")
        return "unknown"
    
    def get_pi_mac(self) -> str:
        """Get Raspberry Pi MAC address"""
        try:
            # Try ethernet first, then WiFi
            try:
                mac = subprocess.check_output(
                    "cat /sys/class/net/eth0/address 2>/dev/null || cat /sys/class/net/wlan0/address",
                    shell=True
                ).decode().strip()
                logger.info(f"✅ Got Pi MAC: {mac}")
                return mac
            except Exception:
                return "unknown"
        except Exception as e:
            logger.error(f"❌ Could not read Pi MAC: {e}")
            return "unknown"
    
    def get_hostname(self) -> str:
        """Get system hostname"""
        try:
            hostname = subprocess.check_output("hostname", shell=True).decode().strip()
            logger.info(f"✅ Got hostname: {hostname}")
            return hostname
        except Exception as e:
            logger.error(f"❌ Could not get hostname: {e}")
            return "unknown"
    
    def get_ip_address(self) -> str:
        """Get primary IP address"""
        try:
            ip = subprocess.check_output(
                "hostname -I | awk '{print $1}'",
                shell=True
            ).decode().strip()
            logger.info(f"✅ Got IP: {ip}")
            return ip
        except Exception as e:
            logger.error(f"❌ Could not get IP: {e}")
            return "unknown"
    
    def get_config_device_id(self) -> str:
        """Get device ID and organization ID from config"""
        try:
            # Add raspserver directory to path if needed
            sys.path.insert(0, str(Path(__file__).parent.parent))
            import config
            device_id = getattr(config, 'DEVICE_ID', 'raspserver-001')
            self.organization_id = getattr(config, 'ORGANIZATION_ID', 'default-org')
            logger.info(f"✅ Got config DEVICE_ID: {device_id}, ORG_ID: {self.organization_id}")
            return device_id
        except Exception as e:
            logger.warning(f"⚠️  Could not load config: {e}, using defaults")
            self.organization_id = 'default-org'
            return os.getenv('DEVICE_ID', 'raspserver-001')
    
    def initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore
            
            # Get credentials path
            creds_path = os.getenv(
                'FIREBASE_CREDENTIALS_PATH',
                '/home/monkphx/harvestpilot-raspserver/firebase-key.json'
            )
            
            if not os.path.exists(creds_path):
                logger.error(f"❌ Firebase credentials not found at {creds_path}")
                return False
            
            # Initialize if not already done
            if not firebase_admin._apps:
                cred = credentials.Certificate(creds_path)
                firebase_admin.initialize_app(cred)
                logger.info("✅ Firebase initialized")
            
            self.firestore = firestore.client()
            return True
            
        except Exception as e:
            logger.error(f"❌ Firebase initialization failed: {e}")
            return False
    
    def register_in_firestore(self) -> bool:
        """Register Pi in Firestore using config device ID as document ID"""
        try:
            if not self.firestore:
                logger.error("❌ Firestore not initialized")
                return False
            
            # Create device document using config device ID as Firestore document ID
            device_data = {
                # Identifiers - use config_device_id as primary
                "deviceId": self.config_device_id,
                "deviceName": self.config_device_id,
                "hardware_serial": self.pi_serial,
                "mac_address": self.pi_mac,
                "hostname": self.pi_hostname,
                "ip_address": self.get_ip_address(),
                
                # Organization
                "organizationId": self.organization_id,
                
                # Status
                "status": "online",
                "lastHeartbeat": datetime.now().isoformat(),
                "registered_at": datetime.now().isoformat(),
                "initialized_at": datetime.now().isoformat(),
                
                # System info
                "platform": "raspberry_pi",
                "os": "linux",
                
                # Device mapping
                "mapping": {
                    "hardware_serial": self.pi_serial,
                    "config_id": self.config_device_id,
                    "mac": self.pi_mac,
                    "hostname": self.pi_hostname,
                }
            }
            
            # Write to Firestore using config device ID
            # Path: devices/{config_device_id}
            self.firestore.collection('devices').document(self.config_device_id).set(device_data)
            
            logger.info(f"✅ Registered in Firestore: devices/{self.config_device_id} (org: {self.organization_id})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Firestore registration failed: {e}")
            return False
    
    def save_device_info(self):
        """Save device info to local file for reference"""
        try:
            device_info = {
                "pi_serial": self.pi_serial,
                "pi_mac": self.pi_mac,
                "hostname": self.pi_hostname,
                "ip_address": self.get_ip_address(),
                "config_device_id": self.config_device_id,
                "registered_at": datetime.now().isoformat(),
            }
            
            # Save to local file
            info_path = Path(__file__).parent.parent / '.device_info.json'
            with open(info_path, 'w') as f:
                json.dump(device_info, f, indent=2)
            
            logger.info(f"✅ Device info saved to {info_path}")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️  Could not save device info: {e}")
            return False
    
    def run(self) -> bool:
        """Execute initialization sequence"""
        logger.info("=" * 80)
        logger.info("🚀 HARVESTPILOT SERVER INITIALIZATION")
        logger.info("=" * 80)
        
        try:
            # 1. Collect system info
            logger.info("\n📋 Collecting system information...")
            self.pi_serial = self.get_pi_serial()
            self.pi_mac = self.get_pi_mac()
            self.pi_hostname = self.get_hostname()
            self.config_device_id = self.get_config_device_id()
            
            if self.pi_serial == "unknown":
                logger.error("❌ Could not determine Pi serial - aborting")
                return False
            
            # 2. Initialize Firebase
            logger.info("\n🔐 Initializing Firebase...")
            if not self.initialize_firebase():
                logger.error("❌ Firebase initialization failed - continuing without Firestore")
                # Don't fail, service can still run locally
            
            # 3. Register in Firestore (if available)
            if self.firestore:
                logger.info("\n📝 Registering in Firestore...")
                if not self.register_in_firestore():
                    logger.warning("⚠️  Firestore registration failed - service will continue")
            
            # 4. Save local device info
            logger.info("\n💾 Saving device info...")
            self.save_device_info()
            
            # 5. Summary
            logger.info("\n" + "=" * 80)
            logger.info("✅ INITIALIZATION COMPLETE")
            logger.info("=" * 80)
            logger.info(f"   Pi Serial:      {self.pi_serial}")
            logger.info(f"   MAC Address:    {self.pi_mac}")
            logger.info(f"   Hostname:       {self.pi_hostname}")
            logger.info(f"   Config Device:  {self.config_device_id}")
            logger.info("=" * 80)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}", exc_info=True)
            return False


def main():
    """Entry point"""
    initializer = PiInitializer()
    success = initializer.run()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
