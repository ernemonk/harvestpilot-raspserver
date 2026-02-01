# Tests & Examples

This directory contains all test files, unit tests, quick-start examples, and validation scripts.

## 📁 Contents

### Quick Start & Validation
- **`quick_test.py`** — Fast way to validate your Firebase GPIO setup works
  ```bash
  python quick_test.py
  ```

### Unit Tests
- **`test_*.py`** — Test various components (GPIO, Firebase, sensors, etc.)
  ```bash
  # Run all tests
  pytest tests/

  # Run specific test
  pytest tests/test_gpio_pins.py -v
  ```

### Examples
- **`examples_*.py`** — Example usage patterns and configurations

## 🚀 Quick Start Test

The quickest way to verify your setup:

```bash
python tests/quick_test.py
```

This validates:
- ✓ Server startup
- ✓ Device registration
- ✓ Firebase connection
- ✓ GPIO control
- ✓ Pump and light operation

## 📋 Test Requirements

Before running tests, ensure:
1. Python 3.8+ installed
2. Dependencies installed: `pip install -r ../requirements.txt`
3. Firebase credentials in `config/firebase-key.json` or `.env` set
4. Hardware available or GPIO mocking enabled

## 🔧 Running on Non-Raspberry Pi

Tests can run on any system with Python. GPIO operations use a mock when `RPi.GPIO` is unavailable.

Enable simulation mode:
```bash
export SIMULATE_HARDWARE=true
python tests/quick_test.py
```

## 📖 Documentation

See [../REPOSITORY_STRUCTURE.md](../REPOSITORY_STRUCTURE.md) for overall project layout.
