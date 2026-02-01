"""Firebase service - abstracts Firebase operations"""

import json
import logging
import asyncio
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import SERVER_TIMESTAMP
from .. import config
from ..models import SensorReading, Command, DeviceStatus

logger = logging.getLogger(__name__)


class FirebaseService:
    """High-level Firebase service for data sync and commands"""
    
    def __init__(self):
        self.firestore_db = None
        self.connected = False
        self.hardware_serial = config.HARDWARE_SERIAL  # Primary identifier
        self.device_id = config.DEVICE_ID  # Human-readable alias (stored in document)
        self.callbacks = {}
        
        logger.info(f"Firebase service initialized (hardware_serial: {self.hardware_serial}, device_id: {self.device_id})")
    
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
                firebase_admin.initialize_app(cred)
            
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
        """Update device status in Firestore (using hardware_serial as primary key)"""
        try:
            update_data = {
                "status": status,
                "device_id": self.device_id,  # Store human-readable alias
                "hardware_serial": self.hardware_serial,  # Primary identifier
                "lastHeartbeat": SERVER_TIMESTAMP,
                "lastSyncAt": SERVER_TIMESTAMP,
            }
            # Use hardware_serial as Firestore document key
            self.firestore_db.collection("devices").document(
                self.hardware_serial
            ).set(update_data, merge=True)
            logger.info(f"Device status updated to: {status} (serial: {self.hardware_serial})")
        except Exception as e:
            logger.error(f"Failed to update device status: {e}")
    
    def publish_sensor_data(self, sensor_reading: SensorReading):
        """Publish sensor reading to Firestore"""
        try:
            if not self.connected:
                logger.warning("Cannot publish - Firebase not connected")
                return
            
            # Firestore for live data and historical analytics (using hardware_serial as key)
            self.firestore_db.collection("devices").document(
                self.hardware_serial
            ).collection("sensor_readings").add({
                **sensor_reading.to_dict(),
                "timestamp": SERVER_TIMESTAMP
            })
            
            logger.debug(f"Published sensor data")
            
        except Exception as e:
            logger.error(f"Failed to publish sensor data: {e}")
    
    def publish_status_update(self, status_data: dict):
        """Publish operational status (pump, lights, etc) to Firestore"""
        try:
            if not self.connected:
                return
            
            # Update device document with current status (using hardware_serial as key)
            self.firestore_db.collection("devices").document(
                self.hardware_serial
            ).set({
                "status_data": status_data,
                "device_id": self.device_id,
                "hardware_serial": self.hardware_serial,
                "lastUpdated": SERVER_TIMESTAMP
            }, merge=True)
            
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
        """Mark command as processed in Firestore"""
        try:
            self.firestore_db.collection("devices").document(
                self.hardware_serial
            ).collection("commands").document(cmd_id).set({
                "processed": True,
                "processedAt": SERVER_TIMESTAMP
            }, merge=True)
        except Exception as e:
            logger.error(f"Failed to mark command processed: {e}")
    
    def publish_heartbeat(self):
        """Publish periodic heartbeat to Firestore to show device is alive"""
        try:
            if not self.connected:
                return
            
            self.firestore_db.collection("devices").document(
                self.hardware_serial
            ).set({
                "status": "online",
                "device_id": self.device_id,
                "hardware_serial": self.hardware_serial,
                "lastHeartbeat": SERVER_TIMESTAMP,
                "lastSyncAt": SERVER_TIMESTAMP,
            }, merge=True)
            logger.debug(f"Heartbeat published")
        except Exception as e:
            logger.error(f"Failed to publish heartbeat: {e}")
    
    def register_command_handler(self, cmd_type: str, action: str, callback):
        """Register handler for command type/action"""
        key = f"{cmd_type}/{action}"
        self.callbacks[key] = callback
        logger.info(f"Registered handler for {key}")
