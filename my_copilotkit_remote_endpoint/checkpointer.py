# my_copilotkit_remote_endpoint/checkpointer.py

import redis
import json
from typing import Any, Optional, Dict
import os


class RedisCheckpointer:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=os.getenv("REDISHOST"),
            port=int(os.getenv("REDISPORT")),
            db=int(os.getenv("REDIS_DB")),
            password=os.getenv("REDISPASSWORD"),
            decode_responses=True
        )

    def get_state(self, key: str) -> Optional[Dict]:
        try:
            value = self.redis_client.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            print(f"Error getting state: {e}")
            raise e

    def set_state(self, key: str, state: Any) -> None:
        try:
            self.redis_client.set(key, json.dumps(state))
        except Exception as e:
            print(f"Error setting state: {e}")

    def clear(self, key: str) -> None:
        try:
            self.redis_client.delete(key)
        except Exception as e:
            print(f"Error clearing state: {e}")


# Create the checkpointer instance
checkpointer = RedisCheckpointer()
