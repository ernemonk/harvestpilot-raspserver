"""
HarvestPilot RaspServer - Modular Entry Point

Raspberry Pi Hardware Control Server with Firestore
communication and local automation capabilities.
"""

import asyncio
import logging
import signal
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from src.core import RaspServer
from src.utils.logger import setup_logging
from src import config

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)


def initialize_device():
    """Initialize Pi and register to Firestore (runs once on startup)"""
    try:
        logger.info("=" * 70)
        logger.info("🚀 DEVICE INITIALIZATION PHASE STARTING...")
        logger.info("=" * 70)
        
        init_script = Path(__file__).parent / "src" / "scripts" / "server_init.py"
        
        if init_script.exists():
            logger.info(f"📍 Found init script at: {init_script}")
            logger.info("🔧 Running initialization script...")
            result = subprocess.run(
                [sys.executable, str(init_script)],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info("✅ Device initialization completed successfully")
                if result.stdout:
                    logger.debug(f"Init script output:\n{result.stdout}")
            else:
                logger.warning(f"⚠️  Device initialization had issues: {result.stderr}")
                # Non-fatal, continue startup
        else:
            logger.warning(f"⚠️  Init script not found at {init_script}")
            
        logger.info("=" * 70)
        logger.info("✅ DEVICE INITIALIZATION PHASE COMPLETE")
        logger.info("=" * 70)
            
    except subprocess.TimeoutExpired:
        logger.warning("⚠️  Device initialization timed out, continuing startup")
    except Exception as e:
        logger.warning(f"⚠️  Device initialization failed: {e}, continuing startup")


async def main():
    """Main entry point - initialize and run server"""
    logger.info("=" * 70)
    logger.info("🎬 HARVEST PILOT RASPSERVER - STARTING UP")
    logger.info("=" * 70)
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Current time: {datetime.now().isoformat()}")
    
    # First, run device initialization
    initialize_device()
    
    logger.info("=" * 70)
    logger.info("🚀 STARTING RASP SERVER CORE...")
    logger.info("=" * 70)
    
    server = RaspServer()
    
    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.warning(f"⚠️  Received signal {sig} - shutting down gracefully...")
        asyncio.create_task(server.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("⏹️  Keyboard interrupt received")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
    finally:
        logger.info("🔌 Performing cleanup...")
        await server.stop()
        logger.info("=" * 70)
        logger.info("✅ SERVER SHUTDOWN COMPLETE")
        logger.info("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Server crashed: {e}", exc_info=True)
        sys.exit(1)
