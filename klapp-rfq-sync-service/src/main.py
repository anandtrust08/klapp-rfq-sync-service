# =============================================================================
# FILE: src/main.py
# Main entry point for RFQ Sync Service
# =============================================================================

import asyncio
import logging
import signal
import sys

import structlog

from src.config import settings
from src.consumers.sync_consumer import SyncConsumer
from src.services.medusa_db import get_medusa_db
from src.services.redis_client import get_redis_client, close_redis_client

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if settings.LOG_FORMAT == "json"
        else structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(message)s",
)

logger = structlog.get_logger()


async def main() -> None:
    """Main entry point."""
    logger.info(
        "Starting RFQ Sync Service",
        service=settings.SERVICE_NAME,
        version=settings.SERVICE_VERSION,
        environment=settings.ENVIRONMENT,
    )

    # Initialize connections
    logger.info("Initializing database connections...")
    await get_medusa_db()
    await get_redis_client()

    # Create and start consumer
    consumer = SyncConsumer()

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    async def shutdown():
        logger.info("Shutting down...")
        await consumer.stop()
        await close_redis_client()
        logger.info("Shutdown complete")

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(shutdown()),
        )

    try:
        await consumer.run()
    except Exception as e:
        logger.error("Fatal error", error=str(e))
        await shutdown()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
