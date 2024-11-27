# utils/redis_utils.py
import asyncio
import logging

logger = logging.getLogger(__name__)


async def safe_redis_operation(coroutine, timeout=5):
    try:
        return await asyncio.wait_for(coroutine, timeout=timeout)
    except asyncio.TimeoutError:
        logger.error("Redis operation timed out")
        raise
    except Exception as e:
        logger.error(f"Redis operation failed: {str(e)}")
        raise
