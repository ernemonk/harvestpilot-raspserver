"""
Configuration Manager for HarvestPilot device.
Handles dynamic interval configuration with Firestore listening and local caching.
"""

import asyncio
import logging
from typing import Optional, Dict
from google.cloud.firestore import Client as FirestoreClient
from src.storage.local_db import LocalDatabase

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manages device configuration with Firestore sync and local persistence."""

    # Default intervals (seconds) - used if Firestore config unavailable
    DEFAULT_INTERVALS = {
        "heartbeat_interval_s": 30,
        "metrics_interval_s": 300,
        "sync_interval_s": 1800,
        "aggregation_interval_s": 60,
        "sensor_read_interval_s": 5,
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
        Load from Firestore, fallback to local cache, then defaults.
        """
        if self._loading:
            return
        
        self._loading = True
        try:
            # Try loading from Firestore first
            if self.firestore_db:
                firestore_config = await self._load_from_firestore()
                if firestore_config:
                    self.intervals = firestore_config
                    await self._cache_locally(self.intervals)
                    logger.info(
                        f"Loaded intervals from Firestore: {self.intervals}"
                    )
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
        """Cache configuration in local SQLite database."""
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
            logger.debug(f"Cached config locally: {config}")
        except Exception as e:
            logger.error(f"Failed to cache config locally: {e}")

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

            def on_snapshot(doc_snapshot, changes, read_time):
                """Called when Firestore config changes."""
                if doc_snapshot:
                    for doc in doc_snapshot:
                        if doc.exists:
                            new_config = doc.to_dict()
                            validated = self._validate_config(new_config)
                            if validated:
                                old_intervals = self.intervals.copy()
                                self.intervals = validated
                                asyncio.create_task(
                                    self._cache_locally(self.intervals)
                                )
                                logger.info(
                                    f"Config updated from Firestore: "
                                    f"{old_intervals} → {self.intervals}"
                                )

            self._listener_handle = config_ref.on_snapshot(on_snapshot)
            logger.info("Firestore listener initialized for config changes")
        except Exception as e:
            logger.error(f"Failed to set up Firestore listener: {e}")

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
        """Get heartbeat interval in seconds."""
        return self.intervals.get("heartbeat_interval_s", self.DEFAULT_INTERVALS["heartbeat_interval_s"])

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
