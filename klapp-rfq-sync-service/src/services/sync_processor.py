# =============================================================================
# FILE: src/services/sync_processor.py
# Main sync processing logic with circuit breaker and retry
# =============================================================================

import logging
from datetime import datetime
from typing import Optional, Dict, Any
import asyncio

from circuitbreaker import circuit
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from src.config import settings
from src.models.events import (
    RFQSyncRequest,
    RFQSyncResult,
    SyncDirection,
    SyncStatus,
)
from src.services.transformer import transformer
from src.services.medusa_db import get_medusa_db
from src.services.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class SyncProcessor:
    """
    Main sync processor with circuit breaker and retry logic.
    """

    def __init__(self):
        self._metrics = {
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "retries": 0,
        }

    @circuit(
        failure_threshold=settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
        recovery_timeout=settings.CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
    )
    @retry(
        stop=stop_after_attempt(settings.RETRY_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=settings.RETRY_WAIT_EXPONENTIAL_MULTIPLIER,
            max=settings.RETRY_WAIT_EXPONENTIAL_MAX,
        ),
        retry=retry_if_exception_type(Exception),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying sync (attempt {retry_state.attempt_number})"
        ),
    )
    async def process_sync_to_medusa(
        self,
        request: RFQSyncRequest,
    ) -> RFQSyncResult:
        """
        Process sync request from email service to MedusaJS.
        """
        sync_started = datetime.utcnow()
        self._metrics["total_syncs"] += 1

        try:
            # Acquire distributed lock
            redis = await get_redis_client()
            lock_key = f"{settings.REDIS_KEY_PREFIX}lock:{request.email_rfq_id}"

            lock_acquired = await redis.set(
                lock_key,
                "1",
                ex=settings.REDIS_LOCK_TIMEOUT,
                nx=True,
            )

            if not lock_acquired:
                logger.warning(f"Lock not acquired for {request.rfq_number}, skipping")
                return RFQSyncResult(
                    email_rfq_id=request.email_rfq_id,
                    rfq_number=request.rfq_number,
                    sync_direction=SyncDirection.EMAIL_TO_MEDUSA,
                    sync_status=SyncStatus.PENDING,
                    sync_started_at=sync_started,
                    sync_completed_at=datetime.utcnow(),
                    duration_ms=0,
                    error_message="Lock not acquired, will retry",
                )

            try:
                # Check idempotency
                medusa_db = await get_medusa_db()
                existing = await medusa_db.find_rfq_by_external_id(request.email_rfq_id)

                if existing:
                    logger.info(
                        f"RFQ {request.rfq_number} already exists in Medusa ({existing['id']})"
                    )
                    return RFQSyncResult(
                        email_rfq_id=request.email_rfq_id,
                        medusa_rfq_id=existing["id"],
                        rfq_number=request.rfq_number,
                        sync_direction=SyncDirection.EMAIL_TO_MEDUSA,
                        sync_status=SyncStatus.COMPLETED,
                        sync_started_at=sync_started,
                        sync_completed_at=datetime.utcnow(),
                        duration_ms=int((datetime.utcnow() - sync_started).total_seconds() * 1000),
                    )

                # Validate data
                is_valid, errors = transformer.validate_for_sync(request.rfq_data)
                if not is_valid:
                    raise ValueError(f"Validation failed: {', '.join(errors)}")

                # Transform data
                medusa_rfq = transformer.transform_email_to_medusa(request.rfq_data)

                # Create in Medusa
                medusa_rfq_id = await medusa_db.create_rfq(medusa_rfq)

                # Cache the mapping
                await redis.set(
                    f"{settings.REDIS_KEY_PREFIX}map:{request.email_rfq_id}",
                    medusa_rfq_id,
                    ex=86400 * 30,  # 30 days
                )

                self._metrics["successful_syncs"] += 1

                sync_completed = datetime.utcnow()
                return RFQSyncResult(
                    email_rfq_id=request.email_rfq_id,
                    medusa_rfq_id=medusa_rfq_id,
                    rfq_number=request.rfq_number,
                    sync_direction=SyncDirection.EMAIL_TO_MEDUSA,
                    sync_status=SyncStatus.COMPLETED,
                    sync_started_at=sync_started,
                    sync_completed_at=sync_completed,
                    duration_ms=int((sync_completed - sync_started).total_seconds() * 1000),
                )

            finally:
                # Release lock
                await redis.delete(lock_key)

        except Exception as e:
            self._metrics["failed_syncs"] += 1
            logger.error(f"Sync failed for {request.rfq_number}: {e}")

            return RFQSyncResult(
                email_rfq_id=request.email_rfq_id,
                rfq_number=request.rfq_number,
                sync_direction=SyncDirection.EMAIL_TO_MEDUSA,
                sync_status=SyncStatus.FAILED,
                sync_started_at=sync_started,
                sync_completed_at=datetime.utcnow(),
                duration_ms=int((datetime.utcnow() - sync_started).total_seconds() * 1000),
                error_message=str(e),
            )

    def get_metrics(self) -> Dict[str, int]:
        """Get sync metrics."""
        return self._metrics.copy()


# Singleton
sync_processor = SyncProcessor()
