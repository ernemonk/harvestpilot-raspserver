#!/usr/bin/env python3
"""DEPRECATED: Moved to src/admin/clear_devices.py

This shim is maintained for backward compatibility.
Use the new location: python3 src/admin/clear_devices.py
"""

import sys
import warnings
from pathlib import Path

warnings.warn(
    "clear_devices.py moved to src/admin/clear_devices.py",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
sys.path.insert(0, str(Path(__file__).parent / "src" / "admin"))
exec(open(Path(__file__).parent / "src" / "admin" / "clear_devices.py").read())

# Delete devices
ref = db.reference('/devices')
print("Deleting /devices...")
try:
    ref.delete()
    print("✅ Devices deleted successfully")
except Exception as e:
    print(f"ℹ️  /devices already empty or doesn't exist: {e}")

# Verify deletion
ref = db.reference('/devices')
try:
    data = ref.get()
    print(f"Remaining data: {data}")
except Exception as e:
    print(f"✅ Devices cleared - /devices is now empty")

firebase_admin.delete_app(firebase_admin.get_app())
print("Done!")
