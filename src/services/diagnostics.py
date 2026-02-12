"""Diagnostics service - track operational metrics"""

import logging
import os
import socket
from datetime import datetime

logger = logging.getLogger(__name__)


class DiagnosticsService:
    """Lightweight metrics collection for executive-level monitoring"""
    
    def __init__(self):
        """Initialize diagnostics tracker"""
        self.start_time = datetime.now()
        self.counters = {
            'heartbeats_sent': 0,
            'sensor_reads': 0,
            'sensor_errors': 0,
            'firebase_errors': 0,
            'total_errors': 0,
            'alerts_triggered': 0,
            'commands_processed': 0,
        }
        self.last_sensor_read = None
        self.firebase_connected = False
        logger.info("Diagnostics service initialized")
    
    def record_heartbeat(self):
        """Record heartbeat sent to Firebase"""
        self.counters['heartbeats_sent'] += 1
    
    def record_sensor_read(self):
        """Record successful sensor read"""
        self.counters['sensor_reads'] += 1
        self.last_sensor_read = datetime.now()
    
    def record_error(self, error_type: str):
        """Record an error
        
        Args:
            error_type: 'sensor', 'firebase', or 'general'
        """
        self.counters['total_errors'] += 1
        if error_type == 'sensor':
            self.counters['sensor_errors'] += 1
        elif error_type == 'firebase':
            self.counters['firebase_errors'] += 1
    
    def record_alert(self):
        """Record an alert trigger"""
        self.counters['alerts_triggered'] += 1
    
    def record_command(self):
        """Record a command processed"""
        self.counters['commands_processed'] += 1
    
    def set_firebase_status(self, connected: bool):
        """Update Firebase connection status"""
        self.firebase_connected = connected
    
    def get_uptime_seconds(self) -> int:
        """Get uptime in seconds"""
        return int((datetime.now() - self.start_time).total_seconds())
    
    def get_uptime_formatted(self) -> str:
        """Get uptime as formatted string"""
        seconds = self.get_uptime_seconds()
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    
    def get_error_rate(self) -> float:
        """Get error rate as percentage (of total operations)"""
        total_ops = self.counters['sensor_reads'] + self.counters['commands_processed']
        if total_ops == 0:
            return 0.0
        return (self.counters['total_errors'] / total_ops) * 100
    
    def get_health_summary(self) -> dict:
        """Get executive-level health summary with device access info
        
        Returns:
            dict with health status, key metrics, and device access details
        """
        uptime_seconds = self.get_uptime_seconds()
        error_rate = self.get_error_rate()
        
        # Determine health status
        if not self.firebase_connected:
            status = "offline"
        elif self.counters['total_errors'] > 50:
            status = "degraded"
        elif error_rate > 5.0:  # > 5% error rate
            status = "degraded"
        else:
            status = "healthy"
        
        # Device access info
        try:
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
        except Exception:
            hostname = "unknown"
            ip_address = "unknown"
        
        # SSH password from env or default
        ssh_password = os.getenv("PI_SSH_PASSWORD", "149246116")
        ssh_user = os.getenv("PI_SSH_USER", "pi")
        
        return {
            'status': status,
            'uptime_seconds': uptime_seconds,
            'uptime_formatted': self.get_uptime_formatted(),
            'firebase_connected': self.firebase_connected,
            'heartbeats_sent': self.counters['heartbeats_sent'],
            'sensor_reads': self.counters['sensor_reads'],
            'total_errors': self.counters['total_errors'],
            'error_rate_percent': round(error_rate, 2),
            'alerts_triggered': self.counters['alerts_triggered'],
            'commands_processed': self.counters['commands_processed'],
            'last_sensor_read': self.last_sensor_read.isoformat() if self.last_sensor_read else None,
            'timestamp': datetime.now().isoformat(),
            'device': {
                'hostname': hostname,
                'ip_address': ip_address,
                'ssh_user': ssh_user,
                'ssh_password': ssh_password,
                'ssh_command': f"ssh {ssh_user}@{ip_address}",
            },
        }
    
    def get_compact_summary(self) -> dict:
        """Get compact summary for Firebase (smaller payload)
        
        Returns:
            dict with minimal essential metrics
        """
        summary = self.get_health_summary()
        return {
            'status': summary['status'],
            'uptime_seconds': summary['uptime_seconds'],
            'total_errors': summary['total_errors'],
            'error_rate_percent': summary['error_rate_percent'],
            'firebase_connected': summary['firebase_connected'],
            'heartbeats_sent': summary['heartbeats_sent'],
            'timestamp': summary['timestamp'],
        }
    
    def log_summary(self):
        """Log current health summary to logger"""
        summary = self.get_health_summary()
        logger.info(
            f"Health Summary - Status: {summary['status']}, "
            f"Uptime: {summary['uptime_formatted']}, "
            f"Errors: {summary['total_errors']}, "
            f"Error Rate: {summary['error_rate_percent']}%, "
            f"Heartbeats: {summary['heartbeats_sent']}"
        )
