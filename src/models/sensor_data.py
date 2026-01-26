"""Sensor data models and schemas"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional


@dataclass
class SensorReading:
    """Sensor reading data"""
    timestamp: str
    temperature: float  # Fahrenheit
    humidity: float  # Percentage
    soil_moisture: float  # Percentage
    water_level: bool
    simulation: bool = False
    
    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)
    
    def to_json(self):
        """Convert to JSON-serializable dict"""
        return self.to_dict()


@dataclass
class ThresholdAlert:
    """Alert when sensor reading exceeds thresholds"""
    severity: str  # "warning" or "critical"
    sensor_type: str
    current_value: float
    threshold: float
    timestamp: str
    
    def to_dict(self):
        """Convert to dictionary"""
        return asdict(self)
