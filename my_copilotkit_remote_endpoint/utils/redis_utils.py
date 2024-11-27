# utils/redis_utils.py
import asyncio
import logging
from fastapi import HTTPException
logger = logging.getLogger(__name__)


async def safe_redis_operation(coroutine, retries=3, timeout=5):
    for attempt in range(1, retries + 1):
        try:
            return await asyncio.wait_for(coroutine, timeout=timeout)
        except asyncio.TimeoutError:
            logger.error(f"Redis operation timed out on attempt {attempt}")
        except Exception as e:
            logger.error(f"Redis operation failed on attempt {attempt}: {str(e)}")
        await asyncio.sleep(0.5)
    raise HTTPException(
        status_code=503,
        detail="Unable to complete Redis operation after multiple attempts"
    )
