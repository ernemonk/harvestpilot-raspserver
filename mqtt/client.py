"""MQTT Client for RaspServer"""

import json
import logging
import paho.mqtt.client as mqtt
import config

logger = logging.getLogger(__name__)


class MQTTClient:
    """MQTT client for communication with cloud agent"""
    
    def __init__(self):
        self.client = mqtt.Client(client_id=config.MQTT_CLIENT_ID)
        self.connected = False
        self.callbacks = {}
        
        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        # Set credentials if provided
        if config.MQTT_USERNAME and config.MQTT_PASSWORD:
            self.client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
        
        logger.info("MQTT client initialized")
    
    async def connect(self):
        """Connect to MQTT broker"""
        try:
            self.client.connect(
                config.MQTT_BROKER,
                config.MQTT_PORT,
                config.MQTT_KEEPALIVE
            )
            self.client.loop_start()
            logger.info(f"Connecting to MQTT broker at {config.MQTT_BROKER}:{config.MQTT_PORT}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise
    
    async def disconnect(self):
        """Disconnect from MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("Disconnected from MQTT broker")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected"""
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker successfully")
            
            # Subscribe to command topics
            self.client.subscribe("harvestpilot/commands/#")
            logger.info("Subscribed to harvestpilot/commands/#")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection (rc: {rc})")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        topic = msg.topic
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
        except:
            payload = msg.payload.decode('utf-8')
        
        logger.debug(f"Received MQTT message - Topic: {topic}, Payload: {payload}")
        
        # Call registered callbacks
        for topic_pattern, callback in self.callbacks.items():
            if self._topic_matches(topic, topic_pattern):
                try:
                    callback(topic, payload)
                except Exception as e:
                    logger.error(f"Error in callback for {topic}: {e}")
    
    def publish(self, topic, payload):
        """Publish a message"""
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        
        if self.connected:
            self.client.publish(topic, payload)
            logger.debug(f"Published to {topic}: {payload}")
        else:
            logger.warning("Cannot publish - MQTT not connected")
    
    def register_callback(self, topic_pattern, callback):
        """Register callback for topic pattern"""
        self.callbacks[topic_pattern] = callback
        logger.info(f"Registered callback for {topic_pattern}")
    
    @staticmethod
    def _topic_matches(topic, pattern):
        """Check if topic matches pattern"""
        topic_parts = topic.split('/')
        pattern_parts = pattern.split('/')
        
        if len(pattern_parts) > len(topic_parts):
            return False
        
        for i, pattern_part in enumerate(pattern_parts):
            if pattern_part == '#':
                return True
            if i >= len(topic_parts):
                return False
            if pattern_part != '+' and pattern_part != topic_parts[i]:
                return False
        
        return len(topic_parts) == len(pattern_parts)
