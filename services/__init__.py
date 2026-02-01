"""DEPRECATED: Moved to src.services

This shim maintains backward compatibility. Use src.services instead.
"""
import warnings
warnings.warn("services package moved to src.services; please update imports", DeprecationWarning, stacklevel=2)

# Re-export everything from src.services for compatibility
from src.services import *  # noqa: F401, F403
