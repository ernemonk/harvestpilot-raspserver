"""
Sync Service - Handles hourly batch sync to Firestore.
Local-first: collect data locally, sync periodically for cost-effectiveness.
"""

import asyncio
import logging
import time
from typing import Optional

from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncClient

from ..storage.local_db import LocalDatabase
from ..storage.models import (
    HourlySummary,
    DeviceState,
    DeviceStatus,
    SYNC_INTERVAL_MS,
)

logger = logging.getLogger(__name__)


class SyncService:
    """
    Handles periodic sync of local data to Firestore.
    
    Sync strategy:
    - Hourly summaries: Batch upload every hour
    - Device state: Update on every heartbeat (every 5 min)
    - Alerts/Events: Sync when created and on hourly batch
    """

    def __init__(
        self,
        device_id: str,
        db: LocalDatabase,
        firestore_client: Optional[AsyncClient] = None,
    ):
        self.device_id = device_id
        self.db = db
        self.firestore = firestore_client or firestore.AsyncClient()
        self._running = False
        self._last_sync_at: Optional[int] = None

    async def start(self):
        """Start the sync service loop."""
        self._running = True
        logger.info("SyncService started")
        
        while self._running:
            try:
                await self.sync_all()
                self._last_sync_at = int(time.time() * 1000)
            except Exception as e:
                logger.error(f"Sync failed: {e}")
            
            # Wait for next sync interval
            await asyncio.sleep(SYNC_INTERVAL_MS / 1000)

    async def stop(self):
        """Stop the sync service."""
        self._running = False
        logger.info("SyncService stopped")

    async def sync_all(self):
        """Perform full sync of all pending data."""
        logger.info("Starting sync...")
        
        # Sync hourly summaries
        await self._sync_hourly_summaries()
        
        # Sync alerts
        await self._sync_alerts()
        
        # Sync events
        await self._sync_events()
        
        # Update device state document
        await self._update_device_state()
        
        logger.info("Sync completed")

    async def _sync_hourly_summaries(self):
        """Sync unsynced hourly summaries to Firestore."""
        summaries = self.db.get_unsynced_summaries()
        
        if not summaries:
            logger.debug("No hourly summaries to sync")
            return
        
        logger.info(f"Syncing {len(summaries)} hourly summaries")
        
        # Batch write for efficiency
        batch = self.firestore.batch()
        hours_synced = []
        
        for summary in summaries:
            doc_ref = self.firestore.collection('devices').document(self.device_id) \
                .collection('hourly').document(str(summary.hour))
            
            batch.set(doc_ref, summary.model_dump(by_alias=True))
            hours_synced.append(summary.hour)
        
        await batch.commit()
        
        # Mark as synced locally
        self.db.mark_summaries_synced(hours_synced)
        logger.info(f"Synced {len(hours_synced)} hourly summaries")

    async def _sync_alerts(self):
        """Sync unsynced alerts to Firestore."""
        # Get alerts that need syncing from local DB
        # For simplicity, we sync all active alerts
        alerts = self.db.get_active_alerts()
        
        if not alerts:
            return
        
        batch = self.firestore.batch()
        
        for alert in alerts:
            doc_ref = self.firestore.collection('devices').document(self.device_id) \
                .collection('alerts').document(alert.id)
            
            data = alert.model_dump(by_alias=True)
            # Convert reading snapshot to dict if present
            if alert.reading_snapshot:
                data['readingSnapshot'] = alert.reading_snapshot.model_dump(by_alias=True)
            
            batch.set(doc_ref, data, merge=True)
        
        await batch.commit()
        logger.info(f"Synced {len(alerts)} alerts")

    async def _sync_events(self):
        """Sync unsynced events to Firestore."""
        events = self.db.get_unsynced_events()
        
        if not events:
            return
        
        batch = self.firestore.batch()
        event_ids = []
        
        for event in events:
            doc_ref = self.firestore.collection('devices').document(self.device_id) \
                .collection('events').document(event.id)
            
            batch.set(doc_ref, event.model_dump(by_alias=True))
            event_ids.append(event.id)
        
        await batch.commit()
        
        self.db.mark_events_synced(event_ids)
        logger.info(f"Synced {len(event_ids)} events")

    async def _update_device_state(self):
        """Update the main device state document in Firestore."""
        # Get current state from local DB
        latest_reading = self.db.get_latest_reading()
        crop_config = self.db.get_crop_config()
        schedule_state = self.db.get_schedule_state()
        
        # Build device state
        state_data = {
            'deviceId': self.device_id,
            'status': DeviceStatus.ONLINE.value,
            'autopilotMode': schedule_state.get('autopilot_mode', 'on'),
            'lastHeartbeat': int(time.time() * 1000),
            'lastSyncAt': self._last_sync_at,
            'failsafeTriggered': schedule_state.get('failsafe_triggered', False),
            'failsafeReason': schedule_state.get('failsafe_reason'),
            'lastIrrigationAt': schedule_state.get('last_irrigation_at'),
            'nextIrrigationAt': schedule_state.get('next_irrigation_at'),
        }
        
        if latest_reading:
            state_data['currentReading'] = latest_reading.model_dump(by_alias=True)
        
        if crop_config:
            state_data['cropConfig'] = crop_config.model_dump(by_alias=True)
        
        # Update Firestore
        doc_ref = self.firestore.collection('devices').document(self.device_id)
        await doc_ref.set(state_data, merge=True)
        
        logger.debug("Device state updated")

    async def force_sync(self):
        """Force an immediate sync (used after critical events)."""
        logger.info("Force sync triggered")
        await self.sync_all()

    async def send_heartbeat(self):
        """Send a lightweight heartbeat to Firestore."""
        doc_ref = self.firestore.collection('devices').document(self.device_id)
        await doc_ref.update({
            'lastHeartbeat': int(time.time() * 1000),
            'status': DeviceStatus.ONLINE.value,
        })
        logger.debug("Heartbeat sent")
