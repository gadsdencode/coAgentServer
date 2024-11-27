# utils/redis_client.py

import redis.asyncio as redis
from pydantic import Field
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: Optional[str] = Field(default=None)
    REDIS_URL: str = Field(default="redis://default:rYmCyqyBGrLhLYssKqlGzboYjmiaNZQj@redis.railway.internal:6379")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

redis_client = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=10,
    socket_timeout=10,
)


# Add close method to properly cleanup connections
async def close():
    await redis_client.aclose()
