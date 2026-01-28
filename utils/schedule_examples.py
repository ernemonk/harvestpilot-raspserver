# This file has been moved to src/utils/
# This shim is kept for backward compatibility
import warnings
import sys
from pathlib import Path

_name = __file__.split('/')[-1]
warnings.warn(f"utils/{_name} moved to src/utils/{_name}; please update imports", DeprecationWarning, stacklevel=2)

# Import from new location
_module_name = _name[:-3]  # Remove .py
exec(f"from src.utils.{_module_name} import *")
