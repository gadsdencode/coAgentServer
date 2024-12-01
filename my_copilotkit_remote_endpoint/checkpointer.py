# my_copilotkit_remote_endpoint/checkpointer.py

import redis.asyncio as redis
import json
from typing import Any, Optional
import os
import logging
from langgraph.checkpoint.base import BaseCheckpointSaver

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://default:rYmCyqyBGrLhLYssKqlGzboYjmiaNZQj@redis.railway.internal:6379"
)


class RedisCheckpointer(BaseCheckpointSaver):
    """Redis-based implementation of BaseCheckpointSaver."""

    def __init__(self):
        self.redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True
        )
        logger.info("Redis checkpointer initialized")

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from Redis by key."""
        try:
            value = await self.redis_client.get(f"checkpoint:{key}")
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Checkpoint get error: {str(e)}")
            return None

    async def set(self, key: str, value: Any) -> None:
        """Set a value in Redis with key."""
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
        """Delete a value from Redis by key."""
        try:
            await self.redis_client.delete(f"checkpoint:{key}")
        except Exception as e:
            logger.error(f"Checkpoint delete error: {str(e)}")
            raise

    async def exists(self, key: str) -> bool:
        """Check if a key exists in Redis."""
        try:
            return bool(await self.redis_client.exists(f"checkpoint:{key}"))
        except Exception as e:
            logger.error(f"Checkpoint exists error: {str(e)}")
            return False

    async def setup(self) -> None:
        """Initialize the checkpointer."""
        try:
            await self.redis_client.ping()
            logger.info("Redis checkpointer setup complete")
        except Exception as e:
            logger.error(f"Checkpointer setup failed: {str(e)}")
            raise

    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            await self.redis_client.close()
            logger.info("Redis checkpointer cleanup complete")
        except Exception as e:
            logger.error(f"Checkpointer cleanup failed: {str(e)}")
            raise


# Instantiate the checkpointer
checkpointer = RedisCheckpointer()
logger.info(f"Checkpointer instance created: {checkpointer}")
