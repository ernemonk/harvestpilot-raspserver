# Tools & Utilities

This directory contains utility scripts, backward-compatibility shims, and testing utilities.

## ⚠️ Deprecated Modules

The following modules are **DEPRECATED** and kept only for backward compatibility:

### `config.py`
**Status:** ⛔ DEPRECATED  
**Use instead:** `from src.config import *`

Provides backward-compatible access to configuration but shows a deprecation warning.

```python
# ❌ OLD (shows warning)
from config import DEVICE_ID, FIREBASE_DATABASE_URL

# ✅ NEW (recommended)
from src.config import DEVICE_ID, FIREBASE_DATABASE_URL
```

### `firebase_client.py`
**Status:** ⛔ DEPRECATED  
**Use instead:** `from src.services.firebase_listener import FirebaseDeviceListener`

Legacy Firebase client. Suggests using the new service-based architecture.

```python
# ❌ OLD
from firebase_client import FirebaseClient
client = FirebaseClient()

# ✅ NEW
from src.services.firebase_listener import FirebaseDeviceListener
listener = FirebaseDeviceListener()
```

### `clear_devices.py`
**Status:** ⛔ DEPRECATED  
**Use instead:** `python src/admin/clear_devices.py`

Admin utility for clearing device registrations.

```bash
# ❌ OLD
python clear_devices.py

# ✅ NEW
python src/admin/clear_devices.py
```

### `start_server.py`
**Status:** ⛔ DEPRECATED  
**Use instead:** `python main.py`

Legacy startup script. Use main.py entry point instead.

```bash
# ❌ OLD
python start_server.py

# ✅ NEW
python main.py
```

---

## 🛠️ Utility Modules

### `RPi_GPIO_mock.py`
Mock GPIO module for systems without `RPi.GPIO` installed.

**Purpose:** Allows testing on non-Raspberry Pi systems (laptops, servers)

**Used by:** `start_server.py` and core startup logic

**Features:**
- Mocks all RPi.GPIO functions
- Returns sensible defaults
- Logs GPIO operations for debugging
- Zero actual hardware interaction

**Enable manually:**
```python
import sys
sys.modules['RPi.GPIO'] = __import__('RPi_GPIO_mock')
```

---

## 📊 Migration Status

| Module | Status | Timeline |
|--------|--------|----------|
| `config.py` | Deprecated | Remove in v2.0 |
| `firebase_client.py` | Deprecated | Remove in v2.0 |
| `clear_devices.py` | Deprecated | Remove in v2.0 |
| `start_server.py` | Deprecated | Remove in v2.0 |
| `RPi_GPIO_mock.py` | Active | Keep indefinitely |

---

## 🔄 Migration Checklist

If you're migrating from old code:

- [ ] Update imports to use `src.` prefix
- [ ] Replace `start_server.py` calls with `main.py`
- [ ] Update any `config.py` imports to `src.config`
- [ ] Update `firebase_client.py` usage to `src.services`
- [ ] Update `clear_devices.py` calls to use `src/admin/`

---

## 📖 Documentation

See [../REPOSITORY_STRUCTURE.md](../REPOSITORY_STRUCTURE.md) for the complete project layout.  
See [../MIGRATION_GUIDE.md](../MIGRATION_GUIDE.md) for migration details.
