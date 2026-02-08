"""
Configuration Manager for HarvestPilot device.
Handles dynamic interval configuration with Firestore listening and local caching.
"""

import asyncio
import logging
from typing import Optional, Dict
from google.cloud.firestore import Client as FirestoreClient
from google.cloud import firestore
from src.storage.local_db import LocalDatabase

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages device configuration with Firestore sync and local persistence."""

    # Default intervals (seconds) - used if Firestore config unavailable
    DEFAULT_INTERVALS = {
        "heartbeat_interval_s": 30,
        "sync_interval_s": 1800,
    }

    # Min/max bounds to prevent invalid configurations
    INTERVAL_BOUNDS = {
        "heartbeat_interval_s": (5, 3600),        # 5s to 1 hour
        "metrics_interval_s": (30, 3600),         # 30s to 1 hour
        "sync_interval_s": (300, 86400),          # 5 min to 24 hours
        "aggregation_interval_s": (30, 3600),     # 30s to 1 hour
        "sensor_read_interval_s": (1, 300),       # 1s to 5 min
    }

    def __init__(
        self,
        hardware_serial: str,
        database: LocalDatabase,
        firestore_db: Optional[FirestoreClient] = None,
    ):
        """
        Initialize ConfigManager.

        Args:
            hardware_serial: Device's hardware serial number
            database: LocalDatabase instance for caching
            firestore_db: Firestore client (can be set later)
        """
        self.hardware_serial = hardware_serial
        self.database = database
        self.firestore_db = firestore_db
        self.intervals: Dict[str, float] = self.DEFAULT_INTERVALS.copy()
        self._listener_handle = None
        self._loading = False

    def set_firestore_client(self, firestore_db: FirestoreClient):
        """Set Firestore client after Firebase initialization."""
        self.firestore_db = firestore_db

    async def initialize(self):
        """
        Initialize configuration on startup.
        1. Check if device doc exists
        2. If not, create it with default intervals
        3. If it exists but missing intervals, update with missing ones
        4. Load from Firestore, fallback to cache, then defaults
        """
        if self._loading:
            return
        
        self._loading = True
        try:
            if self.firestore_db:
                # First, ensure device document exists
                device_doc_ref = (
                    self.firestore_db.collection("devices")
                    .document(self.hardware_serial)
                )
                device_doc = device_doc_ref.get()
                
                if not device_doc.exists:
                    # Create device doc with initial config
                    logger.info(f"Device doc doesn't exist, creating with defaults...")
                    device_doc_ref.set({
                        "hardware_serial": self.hardware_serial,
                        "initialized_at": firestore.datetime.datetime.utcnow(),
                        "status": "initializing"
                    })
                    logger.info(f"Created device doc {self.hardware_serial}")
                else:
                    logger.info(f"Device doc exists, checking for missing config...")
                
                # Now ensure config/intervals subcollection exists
                config_doc_ref = device_doc_ref.collection("config").document("intervals")
                config_doc = config_doc_ref.get()
                
                if not config_doc.exists:
                    # Create intervals doc with defaults
                    logger.info(f"Creating /config/intervals with defaults: {self.DEFAULT_INTERVALS}")
                    try:
                        config_doc_ref.set(self.DEFAULT_INTERVALS)
                        logger.info(f"✓ Created /config/intervals in Firestore: {self.intervals}")
                        
                        # Verify it was actually created
                        verify_doc = config_doc_ref.get()
                        if verify_doc.exists:
                            logger.info(f"✓ Verified /config/intervals exists in Firestore")
                            self.intervals = self.DEFAULT_INTERVALS.copy()
                            await self._cache_locally(self.intervals)
                            self._loading = False
                            return
                        else:
                            logger.error(f"✗ Failed to create /config/intervals - document doesn't exist after set()")
                    except Exception as e:
                        logger.error(f"✗ Error creating /config/intervals: {e}", exc_info=True)
                else:
                    # Document exists - clean up old fields and ensure only current ones exist
                    existing_config = config_doc.to_dict()
                    if existing_config:
                        # Identify extra keys that shouldn't exist
                        extra_keys = set(existing_config.keys()) - set(self.DEFAULT_INTERVALS.keys())
                        missing_keys = set(self.DEFAULT_INTERVALS.keys()) - set(existing_config.keys())
                        
                        # If there are extra keys or missing keys, replace document with clean version
                        if extra_keys or missing_keys:
                            logger.info(f"Cleaning up config - removing extra: {extra_keys}, adding missing: {missing_keys}")
                            # Replace document with only DEFAULT_INTERVALS
                            config_doc_ref.set(self.DEFAULT_INTERVALS)
                            logger.info(f"Replaced /config/intervals with clean defaults: {self.DEFAULT_INTERVALS}")
                            self.intervals = self.DEFAULT_INTERVALS.copy()
                        else:
                            # Document is clean, use as is
                            self.intervals = existing_config
                        
                        await self._cache_locally(self.intervals)
                        logger.info(f"Loaded intervals from Firestore: {self.intervals}")
                        self._loading = False
                        return

            # Fallback to local cache
            cached_config = self._load_from_cache()
            if cached_config:
                self.intervals = cached_config
                logger.info(f"Loaded intervals from local cache: {self.intervals}")
                self._loading = False
                return

            # Use defaults
            logger.info(f"Using default intervals: {self.intervals}")
            await self._cache_locally(self.intervals)
        finally:
            self._loading = False

    async def _load_from_firestore(self) -> Optional[Dict[str, float]]:
        """
        Load configuration from Firestore.
        Reads devices/{hardware_serial}/config/intervals subcollection.
        """
        try:
            doc = (
                self.firestore_db.collection("devices")
                .document(self.hardware_serial)
                .collection("config")
                .document("intervals")
                .get()
            )
            if doc.exists:
                config = doc.to_dict()
                return self._validate_config(config)
        except Exception as e:
            logger.warning(f"Failed to load config from Firestore: {e}")
        return None

    def _load_from_cache(self) -> Optional[Dict[str, float]]:
        """Load configuration from local SQLite cache."""
        try:
            with self.database._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT key, value FROM device_config")
                rows = cursor.fetchall()
                if rows:
                    config = {}
                    for row in rows:
                        key, value = row
                        try:
                            config[key] = float(value)
                        except (ValueError, TypeError):
                            logger.warning(
                                f"Invalid config value for {key}: {value}"
                            )
                    if config:
                        return self._validate_config(config)
        except Exception as e:
            logger.debug(f"Failed to load config from cache: {e}")
        return None

    async def _cache_locally(self, config: Dict[str, float]):
        """Cache configuration in local SQLite database (async version)."""
        try:
            with self.database._get_connection() as conn:
                cursor = conn.cursor()
                for key, value in config.items():
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO device_config 
                        (key, value, source) VALUES (?, ?, ?)
                        """,
                        (key, str(value), "firestore"),
                    )
            logger.debug(f"✓ Cached config locally: {config}")
        except Exception as e:
            logger.error(f"✗ Failed to cache config locally: {e}")

    def _update_local_cache_sync(self, config: Dict[str, float]):
        """Cache configuration in local SQLite database (sync version for listener context)."""
        try:
            with self.database._get_connection() as conn:
                cursor = conn.cursor()
                for key, value in config.items():
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO device_config 
                        (key, value, source) VALUES (?, ?, ?)
                        """,
                        (key, str(value), "firestore"),
                    )
            logger.info(f"✓ Synced config to local cache: {config}")
        except Exception as e:
            logger.error(f"✗ Failed to sync config to local cache: {e}")

    def _validate_config(self, config: Dict[str, float]) -> Optional[Dict[str, float]]:
        """
        Validate configuration values.
        Returns validated config or None if invalid.
        """
        validated = {}
        for key, value in config.items():
            if key not in self.INTERVAL_BOUNDS:
                logger.warning(f"Unknown config key: {key}")
                continue

            try:
                value = float(value)
            except (ValueError, TypeError):
                logger.warning(f"Invalid value for {key}: {value}")
                continue

            min_val, max_val = self.INTERVAL_BOUNDS[key]
            if value < min_val or value > max_val:
                logger.warning(
                    f"Value out of bounds for {key}: {value} "
                    f"(expected {min_val}-{max_val})"
                )
                continue

            validated[key] = value

        return validated if validated else None

    def listen_for_changes(self):
        """
        Set up Firestore listener for real-time config changes.
        Must be called after Firebase connection established.
        """
        if not self.firestore_db:
            logger.warning(
                "Cannot set up listener: Firestore client not initialized"
            )
            return

        try:
            config_ref = (
                self.firestore_db.collection("devices")
                .document(self.hardware_serial)
                .collection("config")
                .document("intervals")
            )
            
            logger.info(f"✓ Setting up Firestore listener on {self.hardware_serial}/config/intervals")

            def on_snapshot(doc_snapshot, changes, read_time):
                """Called when Firestore config changes."""
                logger.debug(f"📡 on_snapshot triggered - doc_snapshot type: {type(doc_snapshot)}, changes: {changes}")
                
                try:
                    # Handle both single doc and query snapshot
                    if hasattr(doc_snapshot, 'exists'):
                        # Single document snapshot
                        logger.debug(f"Single doc snapshot - exists: {doc_snapshot.exists}")
                        if doc_snapshot.exists:
                            new_config = doc_snapshot.to_dict()
                            logger.info(f"✓ Config change detected in Firestore: {new_config}")
                            
                            validated = self._validate_config(new_config)
                            if validated:
                                old_intervals = self.intervals.copy()
                                self.intervals = validated
                                logger.info(
                                    f"✓ Config UPDATED: {old_intervals} → {self.intervals}"
                                )
                                # Cache synchronously in listener context
                                import asyncio
                                try:
                                    loop = asyncio.get_event_loop()
                                    if loop.is_running():
                                        asyncio.create_task(self._cache_locally(self.intervals))
                                    else:
                                        # Run sync version if no loop
                                        self._update_local_cache_sync(self.intervals)
                                except RuntimeError:
                                    # No event loop, use sync cache
                                    self._update_local_cache_sync(self.intervals)
                            else:
                                logger.warning(f"✗ Config validation failed: {new_config}")
                        else:
                            logger.warning("✗ Config document doesn't exist")
                    else:
                        # Query snapshot (shouldn't happen for single doc)
                        logger.debug(f"Query snapshot - {len(doc_snapshot)} docs")
                        if len(doc_snapshot) > 0:
                            doc = doc_snapshot[0]
                            if doc.exists:
                                new_config = doc.to_dict()
                                logger.info(f"✓ Config change detected: {new_config}")
                                validated = self._validate_config(new_config)
                                if validated:
                                    old_intervals = self.intervals.copy()
                                    self.intervals = validated
                                    logger.info(
                                        f"✓ Config UPDATED: {old_intervals} → {self.intervals}"
                                    )
                except Exception as e:
                    logger.error(f"✗ Error in on_snapshot callback: {e}", exc_info=True)

            self._listener_handle = config_ref.on_snapshot(on_snapshot)
            logger.info("✓ Firestore listener initialized and ACTIVE for config changes")
        except Exception as e:
            logger.error(f"✗ Failed to set up Firestore listener: {e}", exc_info=True)

    def stop_listening(self):
        """Stop listening to Firestore changes."""
        if self._listener_handle:
            try:
                # Firestore listener returns a Watch object with .unsubscribe() method
                if hasattr(self._listener_handle, 'unsubscribe'):
                    self._listener_handle.unsubscribe()
                else:
                    # If it's callable (older API), call it directly
                    self._listener_handle()
            except Exception as e:
                logger.warning(f"Error stopping Firestore listener: {e}")
            finally:
                self._listener_handle = None
            logger.info("Firestore listener stopped")

    # Interval accessor methods
    def get_heartbeat_interval(self) -> float:
        """Get heartbeat interval in seconds - reads current value from self.intervals."""
        interval = self.intervals.get("heartbeat_interval_s", self.DEFAULT_INTERVALS["heartbeat_interval_s"])
        logger.debug(f"📍 Heartbeat interval = {interval}s (from config: {self.intervals})")
        return interval

    def get_metrics_interval(self) -> float:
        """Get metrics interval in seconds."""
        return self.intervals.get("metrics_interval_s", self.DEFAULT_INTERVALS["metrics_interval_s"])

    def get_sync_interval(self) -> float:
        """Get cloud sync interval in seconds."""
        return self.intervals.get("sync_interval_s", self.DEFAULT_INTERVALS["sync_interval_s"])

    def get_aggregation_interval(self) -> float:
        """Get aggregation interval in seconds."""
        return self.intervals.get("aggregation_interval_s", self.DEFAULT_INTERVALS["aggregation_interval_s"])

    def get_sensor_read_interval(self) -> float:
        """Get sensor read interval in seconds."""
        return self.intervals.get("sensor_read_interval_s", self.DEFAULT_INTERVALS["sensor_read_interval_s"])

    def get_all_intervals(self) -> Dict[str, float]:
        """Get all current intervals."""
        return self.intervals.copy()
