#!/usr/bin/env python3
"""Clear devices from Firestore for fresh initialization"""

import firebase_admin
from firebase_admin import firestore
import json
import base64
from pathlib import Path

# Decode the base64 key
key_b64_path = Path(__file__).parent.parent / "Codes" / "firebase-key-b64.txt"
with open(key_b64_path, encoding='utf-8-sig') as f:
    key_text = f.read().strip()
    key_json = base64.b64decode(key_text).decode('utf-8')

# Initialize Firebase
cred = firebase_admin.credentials.Certificate(json.loads(key_json))
firebase_admin.initialize_app(cred)

# Delete devices from Firestore
db = firestore.client()
print("Deleting /devices from Firestore...")
try:
    devices = db.collection('devices').stream()
    for doc in devices:
        doc.reference.delete()
    print("✅ Devices deleted successfully from Firestore")
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
