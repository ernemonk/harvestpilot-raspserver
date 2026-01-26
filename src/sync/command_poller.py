"""
Command Poller - Polls Firestore for remote commands.
Runs every 30 seconds to check for pending commands from webapp.
"""

import asyncio
import logging
import time
from typing import Callable, Optional

from google.cloud import firestore
from google.cloud.firestore_v1 import AsyncClient

from ..storage.local_db import LocalDatabase
from ..storage.models import (
    Command,
    CommandType,
    CommandStatus,
)

logger = logging.getLogger(__name__)

COMMAND_POLL_INTERVAL_SECONDS = 30


class CommandPoller:
    """
    Polls Firestore for pending commands and executes them.
    
    Command flow:
    1. Webapp writes command to Firestore with status='pending'
    2. Device polls every 30 seconds
    3. Device executes command and updates status to 'executed' or 'failed'
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
        self._handlers: dict[CommandType, Callable] = {}

    def register_handler(self, command_type: CommandType, handler: Callable):
        """Register a handler for a command type."""
        self._handlers[command_type] = handler
        logger.info(f"Registered handler for {command_type.value}")

    async def start(self):
        """Start the command polling loop."""
        self._running = True
        logger.info("CommandPoller started")
        
        while self._running:
            try:
                await self._poll_and_execute()
            except Exception as e:
                logger.error(f"Command poll failed: {e}")
            
            await asyncio.sleep(COMMAND_POLL_INTERVAL_SECONDS)

    async def stop(self):
        """Stop the command poller."""
        self._running = False
        logger.info("CommandPoller stopped")

    async def _poll_and_execute(self):
        """Poll for pending commands and execute them."""
        # Query pending commands
        commands_ref = self.firestore.collection('devices').document(self.device_id) \
            .collection('commands')
        
        query = commands_ref.where('status', '==', 'pending').order_by('issuedAt')
        docs = await query.get()
        
        for doc in docs:
            data = doc.to_dict()
            command = Command(
                id=doc.id,
                type=data['type'],
                payload=data.get('payload', {}),
                issuedAt=data['issuedAt'],
                status=CommandStatus.PENDING,
                executedAt=None,
                errorMessage=None,
            )
            
            await self._execute_command(command, doc.reference)

    async def _execute_command(self, command: Command, doc_ref):
        """Execute a single command."""
        logger.info(f"Executing command: {command.type.value}")
        
        executed_at = int(time.time() * 1000)
        error_message = None
        status = CommandStatus.EXECUTED
        
        try:
            # Get handler for this command type
            handler = self._handlers.get(command.type)
            
            if handler is None:
                raise ValueError(f"No handler for command type: {command.type.value}")
            
            # Execute the handler
            if asyncio.iscoroutinefunction(handler):
                await handler(command.payload)
            else:
                handler(command.payload)
            
            logger.info(f"Command {command.id} executed successfully")
            
        except Exception as e:
            logger.error(f"Command {command.id} failed: {e}")
            status = CommandStatus.FAILED
            error_message = str(e)
        
        # Update command status in Firestore
        await doc_ref.update({
            'status': status.value,
            'executedAt': executed_at,
            'errorMessage': error_message,
        })
        
        # Also save to local DB for history
        command.status = status
        command.executed_at = executed_at
        command.error_message = error_message
        self.db.update_command_status(
            command.id,
            status,
            executed_at,
            error_message
        )


class CommandHandlers:
    """
    Default command handlers.
    These should be connected to actual hardware controllers.
    """

    def __init__(self, gpio_controller=None, scheduler=None):
        self.gpio = gpio_controller
        self.scheduler = scheduler

    async def handle_pump_on(self, payload: dict):
        """Handle pump_on command."""
        duration = payload.get('duration_seconds', 30)
        logger.info(f"Pump ON for {duration} seconds")
        
        if self.gpio:
            await self.gpio.pump_on(duration)
        else:
            # Simulation mode
            logger.warning("GPIO not available, simulating pump on")
            await asyncio.sleep(min(duration, 5))

    async def handle_pump_off(self, payload: dict):
        """Handle pump_off command."""
        logger.info("Pump OFF")
        
        if self.gpio:
            await self.gpio.pump_off()

    async def handle_lights_on(self, payload: dict):
        """Handle lights_on command."""
        logger.info("Lights ON")
        
        if self.gpio:
            await self.gpio.lights_on()

    async def handle_lights_off(self, payload: dict):
        """Handle lights_off command."""
        logger.info("Lights OFF")
        
        if self.gpio:
            await self.gpio.lights_off()

    async def handle_lights_brightness(self, payload: dict):
        """Handle lights_brightness command."""
        brightness = payload.get('brightness', 100)
        logger.info(f"Lights brightness: {brightness}%")
        
        if self.gpio:
            await self.gpio.set_brightness(brightness)

    async def handle_set_autopilot_mode(self, payload: dict):
        """Handle set_autopilot_mode command."""
        mode = payload.get('mode', 'on')
        logger.info(f"Autopilot mode: {mode}")
        
        if self.scheduler:
            self.scheduler.set_autopilot_mode(mode)

    async def handle_emergency_stop(self, payload: dict):
        """Handle emergency_stop command."""
        logger.warning("EMERGENCY STOP triggered")
        
        if self.gpio:
            await self.gpio.emergency_stop()
        
        if self.scheduler:
            self.scheduler.set_autopilot_mode('paused')

    async def handle_update_crop_config(self, payload: dict):
        """Handle update_crop_config command."""
        logger.info(f"Updating crop config: {payload}")
        
        if self.scheduler:
            self.scheduler.update_crop_config(payload)

    async def handle_reboot(self, payload: dict):
        """Handle reboot command."""
        logger.warning("Reboot requested")
        # In production, this would trigger a system reboot
        # For safety, we just log it here


def setup_command_handlers(poller: CommandPoller, gpio_controller=None, scheduler=None):
    """Register all command handlers with the poller."""
    handlers = CommandHandlers(gpio_controller, scheduler)
    
    poller.register_handler(CommandType.PUMP_ON, handlers.handle_pump_on)
    poller.register_handler(CommandType.PUMP_OFF, handlers.handle_pump_off)
    poller.register_handler(CommandType.LIGHTS_ON, handlers.handle_lights_on)
    poller.register_handler(CommandType.LIGHTS_OFF, handlers.handle_lights_off)
    poller.register_handler(CommandType.LIGHTS_BRIGHTNESS, handlers.handle_lights_brightness)
    poller.register_handler(CommandType.SET_AUTOPILOT_MODE, handlers.handle_set_autopilot_mode)
    poller.register_handler(CommandType.EMERGENCY_STOP, handlers.handle_emergency_stop)
    poller.register_handler(CommandType.UPDATE_CROP_CONFIG, handlers.handle_update_crop_config)
    poller.register_handler(CommandType.REBOOT, handlers.handle_reboot)
    
    return handlers
