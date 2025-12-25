# =============================================================================
# FILE: src/services/redis_client.py
# Redis client for distributed locking and caching
# =============================================================================

import logging
from typing import Optional
import redis.asyncio as redis

from src.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """Get or create Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info(f"Connected to Redis at {settings.REDIS_URL}")
    return _redis_client


async def close_redis_client() -> None:
    """Close Redis connection."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")
