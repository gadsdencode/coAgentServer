# my_copilotkit_remote_endpoint/checkpointer.py

import redis.asyncio as redis
import json
from typing import Any, Optional
import os
import logging
from langgraph.checkpoint.base import Checkpoint

logger = logging.getLogger(__name__)


class RedisCheckpointer(Checkpoint):
    def __init__(self):
        redis_host = os.getenv("REDISHOST", "localhost")
        redis_port = int(os.getenv("REDISPORT", "6379"))
        redis_db = int(os.getenv("REDIS_DB", "0"))
        redis_password = os.getenv("REDISPASSWORD", "")

        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password if redis_password else None,
            decode_responses=True
        )

    async def get_tuple(self, thread_id: str, checkpoint_id: Optional[str] = None) -> Optional[Any]:
        key = self._generate_key(thread_id, checkpoint_id)
        try:
            value = await self.redis_client.get(key)
            logger.debug(f"Retrieved value from Redis for key {key}: {value}")
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Error getting tuple from Redis: {e}")
            raise e

    async def set_tuple(self, thread_id: str, tuple_data: Any, checkpoint_id: Optional[str] = None) -> None:
        key = self._generate_key(thread_id, checkpoint_id)
        try:
            serialized_data = json.dumps(tuple_data)
            await self.redis_client.set(key, serialized_data)
            logger.debug(f"Set value in Redis for key {key}: {serialized_data}")
        except Exception as e:
            logger.error(f"Error setting tuple in Redis: {e}")

    async def clear(self, thread_id: str, checkpoint_id: Optional[str] = None) -> None:
        key = self._generate_key(thread_id, checkpoint_id)
        try:
            await self.redis_client.delete(key)
            logger.debug(f"Deleted key from Redis: {key}")
        except Exception as e:
            logger.error(f"Error clearing key in Redis: {e}")

    def _generate_key(self, thread_id: str, checkpoint_id: Optional[str] = None) -> str:
        if checkpoint_id:
            return f"checkpointer:{thread_id}:{checkpoint_id}"
        else:
            return f"checkpointer:{thread_id}"


# Instantiate the checkpointer
checkpointer = RedisCheckpointer()
