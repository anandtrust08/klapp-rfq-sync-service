# =============================================================================
# FILE: src/consumers/sync_consumer.py
# Main Kafka consumer for sync service
# =============================================================================

import json
import logging
import asyncio
from typing import Optional
from datetime import datetime

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError

from src.config import settings
from src.models.events import RFQSyncRequest, SyncDirection, SyncStatus
from src.services.sync_processor import sync_processor

logger = logging.getLogger(__name__)


class SyncConsumer:
    """
    Kafka consumer for RFQ sync service.
    Listens to sync topics and processes sync requests.
    """

    def __init__(self):
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._producer: Optional[AIOKafkaProducer] = None
        self._is_running = False

    async def start(self) -> None:
        """Start consumer and producer."""
        if self._is_running:
            return

        # Create consumer
        self._consumer = AIOKafkaConsumer(
            settings.TOPIC_RFQ_SYNC_TO_MEDUSA,
            settings.TOPIC_RFQ_STATUS_CHANGED,
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            group_id=settings.KAFKA_CONSUMER_GROUP,
            auto_offset_reset=settings.KAFKA_AUTO_OFFSET_RESET,
            enable_auto_commit=settings.KAFKA_ENABLE_AUTO_COMMIT,
            session_timeout_ms=settings.KAFKA_SESSION_TIMEOUT_MS,
            max_poll_records=settings.KAFKA_MAX_POLL_RECORDS,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            key_deserializer=lambda k: k.decode("utf-8") if k else None,
        )

        # Create producer for responses
        self._producer = AIOKafkaProducer(
            bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            acks="all",
            enable_idempotence=True,
        )

        await self._consumer.start()
        await self._producer.start()
        self._is_running = True

        logger.info(
            f"Sync consumer started, listening to: "
            f"{settings.TOPIC_RFQ_SYNC_TO_MEDUSA}, {settings.TOPIC_RFQ_STATUS_CHANGED}"
        )

    async def stop(self) -> None:
        """Stop consumer and producer."""
        self._is_running = False
        if self._consumer:
            await self._consumer.stop()
        if self._producer:
            await self._producer.stop()
        logger.info("Sync consumer stopped")

    async def run(self) -> None:
        """Main consumer loop."""
        if not self._is_running:
            await self.start()

        try:
            async for message in self._consumer:
                await self._process_message(message)
        except KafkaError as e:
            logger.error(f"Kafka error: {e}")
            raise

    async def _process_message(self, message) -> None:
        """Process a single message."""
        topic = message.topic
        value = message.value
        key = message.key

        logger.debug(f"Received message from {topic}: {key}")

        try:
            if topic == settings.TOPIC_RFQ_SYNC_TO_MEDUSA:
                await self._handle_sync_to_medusa(value)
            elif topic == settings.TOPIC_RFQ_STATUS_CHANGED:
                await self._handle_status_changed(value)
            else:
                logger.warning(f"Unknown topic: {topic}")

        except Exception as e:
            logger.error(f"Error processing message from {topic}: {e}")
            await self._send_to_dlq(topic, value, str(e))

    async def _handle_sync_to_medusa(self, event: dict) -> None:
        """Handle sync request to Medusa."""
        try:
            request = RFQSyncRequest(**event)
            result = await sync_processor.process_sync_to_medusa(request)

            # Publish result
            await self._producer.send_and_wait(
                topic=settings.TOPIC_RFQ_SYNC_COMPLETED,
                value={
                    "event_id": f"sync_completed_{result.email_rfq_id}",
                    "event_type": "rfq.sync.completed",
                    "event_timestamp": result.sync_completed_at.isoformat(),
                    "source_service": settings.SERVICE_NAME,
                    "idempotency_key": f"sync_completed_{result.email_rfq_id}",
                    "email_rfq_id": result.email_rfq_id,
                    "medusa_rfq_id": result.medusa_rfq_id,
                    "rfq_number": result.rfq_number,
                    "sync_direction": result.sync_direction.value,
                    "sync_status": result.sync_status.value,
                    "sync_started_at": result.sync_started_at.isoformat(),
                    "sync_completed_at": result.sync_completed_at.isoformat(),
                    "sync_duration_ms": result.duration_ms,
                    "error_message": result.error_message,
                },
                key=result.rfq_number,
            )

            logger.info(
                f"Sync {result.sync_status.value} for {result.rfq_number}: "
                f"medusa_id={result.medusa_rfq_id}"
            )

        except Exception as e:
            logger.error(f"Failed to process sync request: {e}")
            raise

    async def _handle_status_changed(self, event: dict) -> None:
        """Handle status change event."""
        # Only process events from Medusa
        if event.get("source_service") == settings.SERVICE_NAME:
            return

        logger.info(f"Status change: {event.get('rfq_number')}")
        # TODO: Implement status sync if needed

    async def _send_to_dlq(self, topic: str, event: dict, error: str) -> None:
        """Send failed message to DLQ."""
        try:
            await self._producer.send_and_wait(
                topic=settings.TOPIC_RFQ_DLQ,
                value={
                    "original_topic": topic,
                    "original_event": event,
                    "failure_reason": error,
                    "failure_timestamp": datetime.utcnow().isoformat(),
                },
                key=f"dlq_{datetime.utcnow().timestamp()}",
            )
        except Exception as e:
            logger.error(f"Failed to send to DLQ: {e}")
