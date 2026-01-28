# Repository Organization Guide

**Last Updated**: January 27, 2026

## Root Directory (Entry Points & Config)

The root contains only essential project metadata and entry points:

- **main.py** - Application entry point (starts the server)
- **config.py** - Global configuration (shared across src/)
- **requirements.txt** - Python dependencies
- **README.md** - Project overview
- **.env.example** - Environment variables template
- **.github/** - CI/CD workflows (GitHub Actions)
- **docs/** - Documentation and examples

## `/src` - Canonical Source Code

All application code lives under `src/`:

```
src/
├── core/              # Server orchestration
│   ├── __init__.py
│   └── server.py      # Main RaspServer class
├── services/          # Business logic (Firebase, sensors, automation)
│   ├── __init__.py
│   ├── firebase_service.py     # Firebase integration
│   ├── sensor_service.py       # Sensor reading logic
│   ├── automation_service.py   # Scheduled automation
│   ├── database_service.py     # Local data storage
│   ├── diagnostics.py          # Health monitoring
│   └── gpio_actuator_controller.py  # GPIO Firestore listener
├── controllers/       # Hardware control (low-level GPIO)
│   ├── __init__.py
│   ├── irrigation.py  # Pump control
│   ├── lighting.py    # LED control
│   ├── harvest.py     # Belt motor control
│   └── sensors.py     # Sensor reading
├── models/            # Data structures
│   ├── __init__.py
│   ├── command.py
│   ├── sensor_data.py
│   └── device_status.py
├── storage/           # Local data persistence
│   ├── __init__.py
│   ├── database.py    # SQLite wrapper
│   └── schema.py      # DB schema
├── sync/              # Cloud synchronization
│   ├── __init__.py
│   └── command_poller.py
├── utils/             # Shared utilities
│   ├── __init__.py
│   ├── logger.py      # Logging setup
│   ├── gpio_manager.py
│   ├── gpio_scheduler.py
│   ├── config_loader.py
│   └── pin_config.py
├── scripts/           # Initialization & testing scripts
│   ├── server_init.py       # Device registration on startup
│   ├── setup-firebase.sh    # Firebase credential setup
│   ├── setup-gpio-automated.sh
│   ├── setup-init.sh
│   ├── run-init.sh
│   ├── test_gpio_pins.py
│   ├── test_led_brightness.py
│   └── test_pump_control.py
└── admin/             # Administrative utilities
    └── clear_devices.py    # Firebase cleanup
```

## `/docs` - Documentation

```
docs/
├── README.md                           # Docs index
├── ARCHITECTURE.md                     # System architecture
├── QUICK_REFERENCE.md                  # Quick start guide
├── DEPLOYMENT_SETUP.md                 # GitHub Actions setup
├── CHANGES.md                          # Changelog
├── TODO.md                             # Task list
└── examples/
    └── dynamic_config_example.py       # GPIO configuration examples
```

## Compatibility Layer

For backward compatibility, some files remain in the root or old locations:

- **controllers/** - Shims that re-export from `src/controllers/` (with deprecation warnings)
- **services/** - Shim that re-exports from `src/services/` (with deprecation warnings)
- **utils/** - Old top-level utilities (can be migrated to `src/utils/` incrementally)
- **scripts/** - Old scripts directory (scripts now in `src/scripts/`)
- **examples_dynamic_config.py** - Shim pointing to `docs/examples/`
- **clear_devices.py** - Shim pointing to `src/admin/`
- **firebase_client.py** - Marked deprecated (use `src.services.firebase_service`)

> **Migration Note**: These shims will be removed in a future release. Update imports to use `src.*` directly.

## How to Import

### ✅ Correct (use these)
```python
from src.core import RaspServer
from src.services import FirebaseService
from src.controllers import IrrigationController
from src.models import SensorReading
from src.utils import setup_logging
```

### ⚠️ Deprecated (will warn)
```python
from controllers.irrigation import IrrigationController  # ⚠️ Deprecated
from services.gpio_actuator_controller import GPIOActuatorController  # ⚠️ Deprecated
import firebase_client  # ⚠️ Deprecated
```

## Running the Application

### Start the server
```bash
python3 main.py
```

### Run admin utilities
```bash
python3 src/admin/clear_devices.py
```

### Run tests
```bash
python3 src/scripts/test_gpio_pins.py
python3 src/scripts/test_pump_control.py
```

### View setup examples
```bash
python3 docs/examples/dynamic_config_example.py all
```

## File Movement Summary

Recent changes moved files to their proper locations:

| Old Location | New Location | Status |
|---|---|---|
| `scripts/` → `src/scripts/` | ✅ Moved | Scripts centralized under src/ |
| `clear_devices.py` | `src/admin/` | ✅ Moved | Admin utilities organized |
| `examples_dynamic_config.py` | `docs/examples/` | ✅ Moved | Examples moved to docs/ |
| `CHANGES.md`, `TODO.md` | `docs/` | ✅ Moved | Changelog/tasks in docs/ |
| `run-init.sh` | `src/scripts/` | ✅ Moved | Startup scripts organized |
| `controllers/` → shim | Still at root (compat) | ⚠️ Keep for now | Will be removed after full migration |
| `services/` → shim | Still at root (compat) | ⚠️ Keep for now | Will be removed after full migration |
| `utils/` | Still at root | ⚠️ Partially moved | Incrementally moving to `src/utils/` |

## Next Steps

1. **Update all imports** to use `src.*` paths directly
2. **Test the application** to verify all imports work
3. **Remove compatibility shims** once all code is updated
4. **Add pyproject.toml** for proper package management
5. **Create tests** that verify package structure integrity

---

For more details, see:
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Common commands
- [DEPLOYMENT_SETUP.md](DEPLOYMENT_SETUP.md) - GitHub Actions setup
