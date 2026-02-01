"""Logger setup for RaspServer"""

import logging
import sys
from .. import config


def setup_logging():
    """Setup logging configuration"""
    
    # Create logger
    logger = logging.getLogger()
    logger.setLevel(config.LOG_LEVEL)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(config.LOG_LEVEL)
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    try:
        import os
        os.makedirs('logs', exist_ok=True)
        file_handler = logging.FileHandler(config.LOG_FILE)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not create file handler: {e}")
    
    logger.info("Logging configured")
