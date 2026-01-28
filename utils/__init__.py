"""DEPRECATED: Moved to src.utils

This shim maintains backward compatibility. Use src.utils instead.
"""
import warnings
warnings.warn("utils package moved to src.utils; please update imports", DeprecationWarning, stacklevel=2)

# Re-export everything from src.utils for compatibility
from src.utils import *  # noqa: F401, F403
