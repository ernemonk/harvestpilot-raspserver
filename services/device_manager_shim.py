# This file has been moved to src/services/
# This shim is kept for backward compatibility
import warnings

_name = __file__.split('/')[-1]
warnings.warn(f"services/{_name} moved to src/services/{_name}; please update imports", DeprecationWarning, stacklevel=2)

# Import from new location
_module_name = _name[:-3]  # Remove .py
exec(f"from src.services.{_module_name} import *")
