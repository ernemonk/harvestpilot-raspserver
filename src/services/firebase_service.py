"""Firebase service - abstracts Firebase operations"""

import json
import logging
import asyncio
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db, firestore
import config
from ..models import SensorReading, Command, DeviceStatus

logger = logging.getLogger(__name__)


class FirebaseService:
    """High-level Firebase service for data sync and commands"""
    
    def __init__(self):
        self.db = None
        self.firestore_db = None
        self.connected = False
        self.device_id = config.DEVICE_ID
        self.callbacks = {}
        
        logger.info("Firebase service initialized")
    
    def connect(self):
        """Initialize Firebase connection"""
        try:
            if not firebase_admin._apps:
                cred_path = config.FIREBASE_CREDENTIALS_PATH
                
                logger.info(f"Loading Firebase credentials from: {cred_path}")
                
                import os
                if not os.path.exists(cred_path):
                    if not os.path.isabs(cred_path):
                        abs_path = os.path.expanduser(f"~/{cred_path}")
                        if os.path.exists(abs_path):
                            cred_path = abs_path
                        else:
                            raise FileNotFoundError(f"Firebase credentials not found")
                    else:
                        raise FileNotFoundError(f"Firebase credentials not found at {cred_path}")
                
                if not os.access(cred_path, os.R_OK):
                    raise PermissionError(f"No read permission for Firebase credentials")
                
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': config.FIREBASE_DATABASE_URL
                })
            
            self.db = db.reference()
            self.firestore_db = firestore.client()
            self.connected = True
            
            logger.info("Connected to Firebase successfully")
            
            self.set_device_online()
            self._listen_for_commands()
            
        except Exception as e:
            logger.error(f"Failed to connect to Firebase: {e}", exc_info=True)
            raise
    
    def disconnect(self):
        """Disconnect from Firebase"""
        if self.connected:
            self.set_device_offline()
            self.connected = False
            logger.info("Disconnected from Firebase")
    
    def set_device_online(self):
        """Mark device as online"""
        self._update_device_status("online")
    
    def set_device_offline(self):
        """Mark device as offline"""
        self._update_device_status("offline")
    
    def _update_device_status(self, status):
        """Update device status"""
        try:
            path = f"devices/{self.device_id}"
            now = datetime.now()
            update_data = {
                "status": status,
                "lastSeen": now.isoformat(),
                "lastHeartbeat": int(now.timestamp() * 1000),  # milliseconds for JavaScript
                "lastSyncAt": now.isoformat(),
            }
            # Use set() to create or overwrite
            db.reference(path).set(update_data)
            logger.info(f"Device status updated to: {status}")
        except Exception as e:
            logger.error(f"Failed to update device status: {e}")
    
    def publish_sensor_data(self, sensor_reading: SensorReading):
        """Publish sensor reading to Firebase"""
        try:
            if not self.connected:
                logger.warning("Cannot publish - Firebase not connected")
                return
            
            # Realtime DB for live data
            path = f"devices/{self.device_id}/sensors/latest"
            db.reference(path).set(sensor_reading.to_dict())
            
            # Firestore for historical analytics
            self.firestore_db.collection("devices").document(
                self.device_id
            ).collection("sensor_history").add(sensor_reading.to_dict())
            
            logger.debug(f"Published sensor data")
            
        except Exception as e:
            logger.error(f"Failed to publish sensor data: {e}")
    
    def publish_status_update(self, status_data: dict):
        """Publish operational status (pump, lights, etc)"""
        try:
            if not self.connected:
                return
            
            path = f"devices/{self.device_id}/status"
            db.reference(path).update(status_data)
            
            logger.debug(f"Published status update")
            
        except Exception as e:
            logger.error(f"Failed to publish status update: {e}")
    
    def _listen_for_commands(self):
        """Listen for commands from cloud agent - not implemented for firebase_admin"""
        # Note: firebase_admin doesn't support streaming listeners like Pyrebase
        # Commands will be checked periodically or via webhook instead
        logger.info("Command listening not fully implemented for firebase_admin")
        pass
    
    def _route_command(self, cmd_id: str, cmd_data: dict):
        """Route command to appropriate handler"""
        try:
            cmd_type = cmd_data.get("type")
            action = cmd_data.get("action")
            params = cmd_data.get("params", {})
            
            callback_key = f"{cmd_type}/{action}"
            
            if callback_key in self.callbacks:
                self.callbacks[callback_key](params)
            else:
                logger.warning(f"No handler for: {callback_key}")
                
        except Exception as e:
            logger.error(f"Error routing command: {e}")
    
    def _mark_command_processed(self, cmd_id: str):
        """Mark command as processed"""
        try:
            path = f"devices/{self.device_id}/commands/{cmd_id}/processed"
            db.reference(path).set(True)
        except Exception as e:
            logger.error(f"Failed to mark command processed: {e}")
    
    def publish_heartbeat(self):
        """Publish periodic heartbeat to show device is alive"""
        try:
            if not self.connected:
                return
            
            now = datetime.now()
            path = f"devices/{self.device_id}"
            db.reference(path).update({
                "status": "online",
                "lastHeartbeat": int(now.timestamp() * 1000),
                "lastSyncAt": now.isoformat(),
            })
            logger.debug(f"Heartbeat published")
        except Exception as e:
            logger.error(f"Failed to publish heartbeat: {e}")
    
    def register_command_handler(self, cmd_type: str, action: str, callback):
        """Register handler for command type/action"""
        key = f"{cmd_type}/{action}"
        self.callbacks[key] = callback
        logger.info(f"Registered handler for {key}")
