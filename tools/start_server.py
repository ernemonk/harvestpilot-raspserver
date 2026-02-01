#!/usr/bin/env python3
"""
Startup script for HarvestPilot RaspServer
Handles RPi.GPIO import fallback for non-Raspberry Pi systems
"""

import sys
import os

# Setup RPi.GPIO mock if not available
try:
    import RPi.GPIO
except ImportError:
    print("⚠️  RPi.GPIO not available, using mock GPIO for simulation mode")
    # Import our mock GPIO and add it to sys.modules
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import RPi_GPIO_mock
    sys.modules['RPi'] = type(sys)('RPi')
    sys.modules['RPi.GPIO'] = RPi_GPIO_mock
    print("✅ Mock GPIO loaded successfully")

# Now we can import the main module
from main import main
import asyncio

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Server stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
