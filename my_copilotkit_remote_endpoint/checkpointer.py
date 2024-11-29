# /my_copilotkit_remote_endpoint/checkpointer.py

import redis
import json
from typing import Any, Optional


class RedisCheckpointer:
    """
    A simple Redis-based checkpointer for CopilotKit.
    """

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379, redis_db: int = 0, redis_password: Optional[str] = None):
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=True  # Ensures responses are in string format
        )

    def get_state(self, key: str) -> Optional[Any]:
        try:
            state = self.redis_client.get(key)
            return json.loads(state) if state else None
        except Exception as e:
            raise Exception(f"Failed to get state from Redis: {e}")

    def set_state(self, key: str, state: Any) -> None:
        try:
            self.redis_client.set(key, json.dumps(state))
        except Exception as e:
            raise Exception(f"Failed to set state in Redis: {e}")

    def delete_state(self, key: str) -> None:
        """
        Delete the state from Redis.
        """
        try:
            self.redis_client.delete(key)
        except Exception as e:
            raise Exception(f"Failed to delete state from Redis: {e}")
