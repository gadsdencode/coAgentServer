# my_copilotkit_remote_endpoint/checkpointer.py

import redis.asyncio as redis
import json
from typing import Any, Optional, Dict
import os
import logging
from langgraph.graph import Checkpointer  # Import Checkpointer base class

logger = logging.getLogger(__name__)


class RedisCheckpointer(Checkpointer):
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv("REDISHOST"),
            port=int(os.getenv("REDISPORT")),
            db=int(os.getenv("REDIS_DB")),
            password=os.getenv("REDISPASSWORD"),
            decode_responses=True
        )

    async def get_tuple(self, key: str) -> Optional[Any]:
        try:
            value = await self.redis_client.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Error getting tuple: {e}")
            raise e

    async def set_tuple(self, key: str, tuple_data: Any) -> None:
        try:
            await self.redis_client.set(key, json.dumps(tuple_data))
        except Exception as e:
            logger.error(f"Error setting tuple: {e}")

    async def clear(self, key: str) -> None:
        try:
            await self.redis_client.delete(key)
        except Exception as e:
            logger.error(f"Error clearing state: {e}")

    def get_state(self, key: str) -> Optional[Dict]:
        try:
            value = self.redis_client.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Error getting state: {e}")
            raise e

    def set_state(self, key: str, state: Any) -> None:
        try:
            self.redis_client.set(key, json.dumps(state))
        except Exception as e:
            logger.error(f"Error setting state: {e}")


# Create the checkpointer instance
checkpointer = RedisCheckpointer()
