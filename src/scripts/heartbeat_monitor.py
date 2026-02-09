#!/usr/bin/env python3

"""
Firestore Heartbeat Monitor - Check if heartbeats are being written to Firestore

Run this on your Raspberry Pi to verify heartbeat writes are happening.
Requires Firebase credentials to be available.
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    from google.cloud.firestore import SERVER_TIMESTAMP
except ImportError:
    print("❌ Firebase Admin SDK not installed. Install with:")
    print("   pip3 install firebase-admin")
    sys.exit(1)


def get_firebase_client():
    """Initialize Firebase and return Firestore client"""
    # Look for credentials in common locations
    possible_paths = [
        Path.home() / "harvestpilot-raspserver" / "firebase-key.json",
        Path.home() / "harvestpilot-raspserver" / "config" / "harvest-hub-2025-firebase-adminsdk-fbsvc-460b441782.json",
        Path("/home/pi/harvestpilot-raspserver/firebase-key.json"),
        Path("/home/pi/harvestpilot-raspserver/config/harvest-hub-2025-firebase-adminsdk-fbsvc-460b441782.json"),
        Path("./firebase-key.json"),
        Path("./config/firebase-key.json"),
    ]
    
    cred_path = None
    for path in possible_paths:
        if path.exists():
            cred_path = path
            print(f"✅ Found credentials at: {path}")
            break
    
    if not cred_path:
        print("❌ Firebase credentials not found in any expected location:")
        for path in possible_paths:
            print(f"   - {path}")
        sys.exit(1)
    
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(str(cred_path))
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        print(f"❌ Failed to initialize Firebase: {e}")
        sys.exit(1)


def check_heartbeat_frequency(db, hardware_serial):
    """Check how often the heartbeat is being updated"""
    doc = db.collection("devices").document(hardware_serial).get()
    
    if not doc.exists:
        print(f"❌ Device document not found: {hardware_serial}")
        return False
    
    data = doc.to_dict()
    last_heartbeat = data.get("lastHeartbeat")
    
    if not last_heartbeat:
        print("❌ No lastHeartbeat field found")
        return False
    
    # Convert timestamp to datetime if it's a datetime object
    if hasattr(last_heartbeat, 'timestamp'):
        # It's a datetime object
        dt = last_heartbeat
    else:
        # It might be a number (epoch milliseconds)
        try:
            dt = datetime.fromtimestamp(last_heartbeat / 1000)
        except:
            dt = last_heartbeat
    
    now = datetime.now()
    
    # Try to get UTC if it's timezone-aware
    if hasattr(dt, 'tzinfo') and dt.tzinfo:
        now = datetime.now(dt.tzinfo)
    
    age = now - dt if isinstance(dt, datetime) else now - datetime.now()
    age_seconds = age.total_seconds()
    
    print("\n📊 HEARTBEAT STATUS")
    print("=" * 60)
    print(f"Last Heartbeat: {dt}")
    print(f"Current Time:   {now}")
    print(f"Age:            {age_seconds:.1f} seconds ago")
    
    return age_seconds


def main():
    print("=" * 60)
    print("Firestore Heartbeat Monitor")
    print("=" * 60)
    print()
    
    # Try to get hardware serial from config
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from src import config
        hardware_serial = config.HARDWARE_SERIAL
        print(f"Using hardware serial: {hardware_serial}")
    except:
        # Fallback to hardcoded value
        hardware_serial = "100000002acfd839"
        print(f"Using default hardware serial: {hardware_serial}")
    
    print()
    
    # Initialize Firebase
    print("🔥 Connecting to Firebase...")
    db = get_firebase_client()
    print("✅ Connected to Firebase")
    print()
    
    # First check
    print("📍 FIRST CHECK (initial state)")
    print("-" * 60)
    age1 = check_heartbeat_frequency(db, hardware_serial)
    
    if age1 is False:
        sys.exit(1)
    
    if age1 > 60:
        print(f"⚠️  Heartbeat is stale! Last update was {age1:.0f} seconds ago")
        print("   Expected: < 30 seconds")
        print()
        print("This suggests:")
        print("  - Service is not running")
        print("  - Heartbeat loop is not executing")
        print("  - Firebase connection is broken")
        print()
        print("Troubleshooting:")
        print("  1. Check service: sudo systemctl status harvestpilot-autodeploy.service")
        print("  2. View logs: journalctl -u harvestpilot-autodeploy.service -f")
        print("  3. Restart: sudo systemctl restart harvestpilot-autodeploy.service")
    else:
        print(f"✅ Heartbeat is fresh! (last update {age1:.0f}s ago)")
    
    # Wait and check again
    print()
    print("⏱️  Waiting 35 seconds for next heartbeat...")
    import time
    time.sleep(35)
    
    print("\n📍 SECOND CHECK (after 35 seconds)")
    print("-" * 60)
    age2 = check_heartbeat_frequency(db, hardware_serial)
    
    if age2 is False:
        sys.exit(1)
    
    # Calculate update frequency
    if age1 is not False and age2 is not False:
        time_diff = age1 - age2  # Should be approximately -35 seconds (got newer)
        
        print()
        print("📈 ANALYSIS")
        print("=" * 60)
        if age2 < age1:
            print(f"✅ HEARTBEAT UPDATED!")
            print(f"   Previous age: {age1:.1f}s")
            print(f"   Current age:  {age2:.1f}s")
            print(f"   Update frequency: Working correctly!")
            print()
            print("If update happened within 30-35 seconds:")
            print("   ✅ Heartbeat is running every 30 seconds (expected)")
        else:
            print(f"❌ HEARTBEAT DID NOT UPDATE!")
            print(f"   Previous age: {age1:.1f}s")
            print(f"   Current age:  {age2:.1f}s")
            print()
            print("This means heartbeat loop is not running.")
            print("Restart the service and try again.")
    
    print()
    print("=" * 60)
    print("Monitor Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
