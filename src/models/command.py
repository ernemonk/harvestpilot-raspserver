"""Command and device models"""

from dataclasses import dataclass, asdict
from typing import Any, Dict


@dataclass
class Command:
    """Command from cloud agent"""
    category: str  # "irrigation", "lighting", "harvest"
    action: str  # "start", "stop", "on", "off"
    params: Dict[str, Any]
    timestamp: str
    
    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)


@dataclass
class DeviceStatus:
    """Device status snapshot"""
    device_id: str
    status: str  # "online", "offline"
    last_seen: str
    current_operation: str = None
    
    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)
