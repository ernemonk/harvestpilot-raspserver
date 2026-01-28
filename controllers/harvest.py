"""Compatibility shim: use `src.controllers.harvest` instead.

This module is kept for backward compatibility and will re-export the
implementation from `src.controllers.harvest`.
"""

import warnings
from src.controllers.harvest import HarvestController  # type: ignore

warnings.warn("controllers.harvest moved to src.controllers.harvest; please update imports.", DeprecationWarning)

__all__ = ["HarvestController"]
