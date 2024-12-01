# action_handler.py

from typing import Any, Dict
import asyncio
import logging
import uuid
from datetime import datetime
import json

from ..utils.redis_client import redis_client
from ..utils.redis_utils import safe_redis_operation

logger = logging.getLogger(__name__)

APPROVAL_CHANNEL = "action_approvals"
APPROVAL_KEY_PREFIX = "approval:"


class ActionApprovalHandler:
    """Handles approval flow for sensitive LangGraph actions"""

    def __init__(self):
        self.pending_approvals: Dict[str, asyncio.Event] = {}
        self.approval_results: Dict[str, bool] = {}
        self.lock = asyncio.Lock()

    def requires_approval(self, action_name: str) -> bool:
        """Determine if an action requires approval based on its name/type"""
        sensitive_actions = {'delete', 'update', 'critical_operation'}
        return any(
            sensitive in action_name.lower()
            for sensitive in sensitive_actions
        )

    async def request_approval(
        self,
        action_name: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Request approval for a sensitive action"""
        if not self.requires_approval(action_name):
            return True

        approval_id = str(uuid.uuid4())
        approval_event = asyncio.Event()

        async with self.lock:
            self.pending_approvals[approval_id] = approval_event

        try:
            await self._notify_approval_system(
                approval_id=approval_id,
                action_name=action_name,
                metadata=metadata,
                timestamp=datetime.utcnow().isoformat()
            )

            # Wait for approval response
            await asyncio.wait_for(approval_event.wait(), timeout=300)
            return self.approval_results.get(approval_id, False)

        except asyncio.TimeoutError:
            logger.warning(f"Approval timeout for action: {action_name}")
            return False

        finally:
            async with self.lock:
                self.pending_approvals.pop(approval_id, None)
                self.approval_results.pop(approval_id, None)
                # Cleanup Redis
                await safe_redis_operation(
                    redis_client.delete(f"{APPROVAL_KEY_PREFIX}{approval_id}")
                )

    async def update_approval(self, approval_id: str, approved: bool):
        """Update approval status from external approval system"""
        async with self.lock:
            if approval_id in self.pending_approvals:
                self.approval_results[approval_id] = approved
                self.pending_approvals[approval_id].set()
                logger.info(
                    f"Approval status: {approval_id} - "
                    f"{'approved' if approved else 'rejected'}"
                )
            else:
                logger.warning(f"Unknown approval ID: {approval_id}")

    async def _notify_approval_system(
        self,
        approval_id: str,
        action_name: str,
        metadata: Dict[str, Any],
        timestamp: str
    ):
        """Notify external approval system via Redis"""
        approval_data = {
            "approval_id": approval_id,
            "action_name": action_name,
            "metadata": metadata,
            "timestamp": timestamp,
            "status": "pending"
        }

        # Store approval request details in Redis
        await safe_redis_operation(
            redis_client.set(
                f"{APPROVAL_KEY_PREFIX}{approval_id}",
                json.dumps(approval_data),
                ex=300  # Expire after 5 minutes
            )
        )

        # Publish notification to approval channel
        await safe_redis_operation(
            redis_client.publish(
                APPROVAL_CHANNEL,
                json.dumps({
                    "type": "approval_request",
                    "data": approval_data
                })
            )
        )

        logger.info(
            f"Approval requested - ID: {approval_id}, Action: {action_name}"
        )
