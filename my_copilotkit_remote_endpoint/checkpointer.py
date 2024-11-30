# my_copilotkit_remote_endpoint/checkpointer.py

import redis.asyncio as redis
import json
from typing import Any, Optional
import os
import logging
# from langgraph.checkpoint.base import Checkpoint
from langgraph.checkpoint.base import BaseCheckpointSaver

logger = logging.getLogger(__name__)


class RedisCheckpointer(BaseCheckpointSaver):
    def __init__(self):
        self.redis_client = redis.from_url(
            os.getenv("REDIS_URL", "redis://default:rYmCyqyBGrLhLYssKqlGzboYjmiaNZQj@redis.railway.internal:6379"),
            decode_responses=True
        )
        logger.info("Redis checkpointer initialized")

    async def get(self, key: str) -> Optional[Any]:
        try:
            value = await self.redis_client.get(f"checkpoint:{key}")
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Checkpoint get error: {str(e)}")
            return None

    async def set(self, key: str, value: Any) -> None:
        try:
            await self.redis_client.set(
                f"checkpoint:{key}",
                json.dumps(value),
                ex=3600  # 1 hour expiration
            )
        except Exception as e:
            logger.error(f"Checkpoint set error: {str(e)}")
            raise

    async def delete(self, key: str) -> None:
        try:
            await self.redis_client.delete(f"checkpoint:{key}")
        except Exception as e:
            logger.error(f"Checkpoint delete error: {str(e)}")
            raise

    def _generate_key(self, thread_id: str, checkpoint_id: Optional[str] = None) -> str:
        if checkpoint_id:
            return f"checkpointer:{thread_id}:{checkpoint_id}"
        else:
            return f"checkpointer:{thread_id}"


# Instantiate the checkpointer
checkpointer = RedisCheckpointer()
logger.info(f"Checkpointer instance created: {checkpointer}")
