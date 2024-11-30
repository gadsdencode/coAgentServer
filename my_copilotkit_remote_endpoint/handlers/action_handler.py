# action_handler.py

from typing import Any, Dict
from fastapi import HTTPException
import asyncio
import logging
import uuid

logger = logging.getLogger(__name__)


class ActionHandler:
    def __init__(self):
        self.pending_approvals: Dict[str, asyncio.Event] = {}
        self.approval_results: Dict[str, bool] = {}
        # Lock to manage concurrency safely
        self.lock = asyncio.Lock()

    async def execute_action(self, action: str, context: Dict[str, Any]):
        try:
            logger.info(f"Executing action: {action}", extra={"context": context})

            # Check if action requires approval
            if self.requires_approval(action):
                approval_id = str(uuid.uuid4())
                approval_event = asyncio.Event()
                async with self.lock:
                    self.pending_approvals[approval_id] = approval_event

                # Notify external system or user for approval
                # For example, publish approval request to Redis or send a WebSocket message
                await self.notify_for_approval(approval_id, action, context)

                # Wait for approval
                try:
                    await asyncio.wait_for(approval_event.wait(), timeout=300)
                    approved = self.approval_results.get(approval_id, False)
                    if not approved:
                        raise HTTPException(status_code=403, detail="Action rejected")
                except asyncio.TimeoutError:
                    raise HTTPException(status_code=408, detail="Approval timeout")
                finally:
                    async with self.lock:
                        self.pending_approvals.pop(approval_id, None)
                        self.approval_results.pop(approval_id, None)

            # Execute the action
            result = await self._execute_action_internal(action, context)
            logger.info(f"Action completed: {action}", extra={"result": result})
            return result

        except Exception as e:
            logger.error(f"Action failed: {action}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    def requires_approval(self, action: str) -> bool:
        # Define actions that require approval
        return action in ['delete', 'update', 'critical_operation']

    async def _execute_action_internal(self, action: str, context: Dict[str, Any]):
        # Implement actual action execution logic here
        # Example implementation:
        logger.info(f"Performing action: {action} with context: {context}")
        # Placeholder for actual action logic
        return {"status": "success", "action": action}

    async def update_approval(self, approval_id: str, approved: bool):
        """Method to be called when approval status is updated."""
        async with self.lock:
            if approval_id in self.pending_approvals:
                self.approval_results[approval_id] = approved
                self.pending_approvals[approval_id].set()
                logger.info(f"Approval status updated for {approval_id}: {'approved' if approved else 'rejected'}")
            else:
                logger.warning(f"Approval ID {approval_id} not found among pending approvals.")

    async def notify_for_approval(self, approval_id: str, action: str, context: Dict[str, Any]):
        """Notify external systems or users for approval."""
        # Implement the notification logic here
        # For example, publish to Redis or send a message via a WebSocket
        logger.info(f"Approval required for action {action} with ID {approval_id}")
        # Placeholder for notification logic
        pass
