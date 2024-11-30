# my_copilotkit_remote_endpoint/checkpointer.py

import redis
import json
from typing import Any, Optional, Dict


class RedisCheckpointer:
    def __init__(self, redis_host: str, redis_port: int, redis_db: int, redis_password: str):
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=True
        )

    def get_state(self, key: str) -> Optional[Dict]:
        try:
            value = self.redis_client.get(key)
            return json.loads(value) if value else None
        except Exception as e:
            print(f"Error getting state: {e}")
            return None

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
checkpointer = RedisCheckpointer(
    redis_host="redis.railway.internal",
    redis_port=6379,
    redis_db=0,
    redis_password="rYmCyqyBGrLhLYssKqlGzboYjmiaNZQj"
)
