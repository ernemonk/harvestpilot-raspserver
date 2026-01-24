"""Firebase Client for RaspServer - Real-time sync with cloud agent"""

import json
import logging
import asyncio
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db, firestore
import config

logger = logging.getLogger(__name__)


class FirebaseClient:
    """Firebase Realtime Database and Firestore client for RaspServer"""
    
    def __init__(self):
        self.db = None
        self.firestore_db = None
        self.connected = False
        self.device_id = config.DEVICE_ID
        self.callbacks = {}
        
        logger.info("Firebase client initialized")
    
    def connect(self):
        """Initialize Firebase connection"""
        try:
            # Initialize Firebase Admin SDK with service account
            if not firebase_admin._apps:
                cred_path = config.FIREBASE_CREDENTIALS_PATH
                
                # Debug: Log the path being used
                logger.info(f"Loading Firebase credentials from: {cred_path}")
                
                # Check if file exists
                import os
                if not os.path.exists(cred_path):
                    # Try absolute path if relative path fails
                    if not os.path.isabs(cred_path):
                        abs_path = os.path.expanduser(f"~/{cred_path}")
                        if os.path.exists(abs_path):
                            cred_path = abs_path
                            logger.info(f"Using absolute path: {cred_path}")
                        else:
                            raise FileNotFoundError(f"Firebase credentials not found at {cred_path} or {abs_path}")
                    else:
                        raise FileNotFoundError(f"Firebase credentials not found at {cred_path}")
                
                # Verify file is readable
                if not os.access(cred_path, os.R_OK):
                    raise PermissionError(f"No read permission for Firebase credentials at {cred_path}")
                
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred, {
                    'databaseURL': config.FIREBASE_DATABASE_URL
                })
            
            self.db = db.reference()
            self.firestore_db = firestore.client()
            self.connected = True
            
            logger.info("Connected to Firebase successfully")
            
            # Set device online status
            self.set_device_status("online")
            
            # Listen for commands
            self._listen_for_commands()
            
        except Exception as e:
            logger.error(f"Failed to connect to Firebase: {e}", exc_info=True)
            raise
    
    def disconnect(self):
        """Disconnect from Firebase"""
        if self.connected:
            self.set_device_status("offline")
            self.connected = False
            logger.info("Disconnected from Firebase")
    
    def set_device_status(self, status):
        """Set device online/offline status"""
        try:
            self.db.child(f"devices/{self.device_id}").update({
                "status": status,
                "lastSeen": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to update device status: {e}")
    
    def publish_sensor_data(self, sensor_data):
        """Publish sensor readings to Firebase"""
        try:
            if not self.connected:
                logger.warning("Cannot publish - Firebase not connected")
                return
            
            # Path: /devices/{device_id}/sensors/latest
            sensor_path = f"devices/{self.device_id}/sensors/latest"
            self.db.child(sensor_path).set({
                "temperature": sensor_data.get("temperature"),
                "humidity": sensor_data.get("humidity"),
                "soil_moisture": sensor_data.get("soil_moisture"),
                "water_level": sensor_data.get("water_level"),
                "timestamp": datetime.now().isoformat()
            })
            
            # Also write to Firestore for analytics
            self.firestore_db.collection("devices").document(self.device_id).collection(
                "sensor_history"
            ).add({
                "temperature": sensor_data.get("temperature"),
                "humidity": sensor_data.get("humidity"),
                "soil_moisture": sensor_data.get("soil_moisture"),
                "water_level": sensor_data.get("water_level"),
                "timestamp": datetime.now()
            })
            
            logger.debug(f"Published sensor data: {sensor_data}")
            
        except Exception as e:
            logger.error(f"Failed to publish sensor data: {e}")
    
    def publish_status_update(self, status_data):
        """Publish status updates (pump, light, harvest state)"""
        try:
            if not self.connected:
                return
            
            status_path = f"devices/{self.device_id}/status"
            self.db.child(status_path).update(status_data)
            
            logger.debug(f"Published status update: {status_data}")
            
        except Exception as e:
            logger.error(f"Failed to publish status update: {e}")
    
    def _listen_for_commands(self):
        """Listen for commands from agent/webapp on Firebase"""
        try:
            commands_path = f"devices/{self.device_id}/commands"
            
            def on_command_update(message):
                """Callback when command is posted"""
                if message.data:
                    try:
                        for cmd_id, cmd_data in message.data.items():
                            if callable(cmd_data) or cmd_data is None:
                                continue
                            
                            logger.info(f"Received command: {cmd_id} = {cmd_data}")
                            
                            # Route to registered callback
                            self._handle_command(cmd_id, cmd_data)
                            
                            # Mark command as processed
                            self.db.child(commands_path).child(cmd_id).child("processed").set(True)
                    except Exception as e:
                        logger.error(f"Error processing command update: {e}")
            
            # Set up listener
            self.db.child(commands_path).stream(on_command_update)
            
        except Exception as e:
            logger.error(f"Failed to listen for commands: {e}")
    
    def _handle_command(self, command_id, command_data):
        """Route command to appropriate handler"""
        try:
            command_type = command_data.get("type")
            action = command_data.get("action")
            params = command_data.get("params", {})
            
            # Build callback key
            callback_key = f"{command_type}/{action}"
            
            # Call registered callback if exists
            if callback_key in self.callbacks:
                self.callbacks[callback_key](params)
            else:
                logger.warning(f"No handler for command: {callback_key}")
                
        except Exception as e:
            logger.error(f"Error handling command: {e}")
    
    def register_command_handler(self, command_type, action, callback):
        """Register callback for specific command type/action"""
        callback_key = f"{command_type}/{action}"
        self.callbacks[callback_key] = callback
        logger.info(f"Registered handler for {callback_key}")
    
    def get_command(self, command_id):
        """Get a specific command from Firebase"""
        try:
            cmd_path = f"devices/{self.device_id}/commands/{command_id}"
            result = self.db.child(cmd_path).get()
            return result.val() if result.val() else None
        except Exception as e:
            logger.error(f"Failed to get command: {e}")
            return None
