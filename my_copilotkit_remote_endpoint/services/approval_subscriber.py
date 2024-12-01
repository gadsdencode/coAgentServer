import asyncio
import json
import logging
from typing import Optional
from ..utils.redis_client import redis_client
from ..handlers.action_handler import APPROVAL_CHANNEL

logger = logging.getLogger(__name__)

class ApprovalSubscriber:
    def __init__(self, approval_handler):
        self.approval_handler = approval_handler
        self.pubsub = redis_client.pubsub()
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start listening for approval requests"""
        await self.pubsub.subscribe(APPROVAL_CHANNEL)
        self._task = asyncio.create_task(self._listen())
        logger.info(f"Started listening on channel: {APPROVAL_CHANNEL}")

    async def stop(self):
        """Stop listening for approval requests"""
        if self._task:
            self._task.cancel()
            await self.pubsub.unsubscribe(APPROVAL_CHANNEL)
            self._task = None

    async def _listen(self):
        """Listen for messages on the approval channel"""
        try:
            async for message in self.pubsub.listen():
                if message["type"] == "message":
                    await self._handle_message(message)
        except asyncio.CancelledError:
            logger.info("Approval subscriber stopped")
        except Exception as e:
            logger.error(f"Error in approval subscriber: {e}")

    async def _handle_message(self, message):
        """Handle incoming approval messages"""
        try:
            data = json.loads(message["data"])
            if data["type"] == "approval_request":
                # Process approval request
                # You can implement your approval logic here
                logger.info(f"Received approval request: {data}")
        except Exception as e:
            logger.error(f"Error handling message: {e}") 