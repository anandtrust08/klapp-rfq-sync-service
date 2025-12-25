# =============================================================================
# FILE: src/services/medusa_db.py
# Direct database client for MedusaJS PostgreSQL
# =============================================================================

import logging
from typing import Optional, Dict, Any
from datetime import datetime
import asyncpg
from asyncpg import Pool

from src.config import settings
from src.models.events import MedusaRFQ

logger = logging.getLogger(__name__)


class MedusaDBClient:
    """
    Direct database client for MedusaJS.
    Creates RFQs directly in the Medusa database.
    """

    def __init__(self):
        self._pool: Optional[Pool] = None

    async def connect(self) -> None:
        """Connect to Medusa database."""
        if self._pool:
            return

        self._pool = await asyncpg.create_pool(
            dsn=settings.MEDUSA_DATABASE_URL,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("Connected to Medusa database")

    async def disconnect(self) -> None:
        """Disconnect from database."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Disconnected from Medusa database")

    async def find_rfq_by_external_id(
        self,
        external_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Find existing RFQ by external_id (idempotency check)."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, rfq_number, status, external_id, sync_status
                FROM rfq
                WHERE external_id = $1
                LIMIT 1
                """,
                external_id,
            )
            return dict(row) if row else None

    async def create_rfq(self, rfq: MedusaRFQ) -> str:
        """
        Create RFQ in Medusa database.
        Returns the created RFQ ID.
        """
        import json
        from uuid import uuid4

        rfq_id = f"rfq_{uuid4().hex[:24]}"  # Medusa ID format

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO rfq (
                    id, rfq_number, customer_id, company_id,
                    customer_email, customer_company, customer_name,
                    description, line_items, status, priority,
                    estimated_value, currency, requirements,
                    delivery_address, attachments,
                    ai_confidence_score, ai_analysis,
                    external_id, external_source, sync_status, synced_at,
                    created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11,
                    $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24
                )
                """,
                rfq_id,
                rfq.rfq_number,
                rfq.customer_id,
                rfq.company_id,
                rfq.customer_email,
                rfq.customer_company,
                rfq.customer_name,
                rfq.description,
                json.dumps(rfq.line_items),
                rfq.status,
                rfq.priority,
                rfq.estimated_value,
                rfq.currency,
                json.dumps(rfq.requirements) if rfq.requirements else None,
                json.dumps(rfq.delivery_address) if rfq.delivery_address else None,
                json.dumps(rfq.attachments) if rfq.attachments else None,
                rfq.ai_confidence_score,
                json.dumps(rfq.ai_analysis) if rfq.ai_analysis else None,
                rfq.external_id,
                rfq.external_source,
                "synced",
                datetime.utcnow(),
                datetime.utcnow(),
                datetime.utcnow(),
            )

        logger.info(f"Created RFQ in Medusa: {rfq_id} ({rfq.rfq_number})")
        return rfq_id

    async def update_rfq_status(
        self,
        rfq_id: str,
        status: str,
        updated_by: Optional[str] = None,
    ) -> None:
        """Update RFQ status."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE rfq
                SET status = $1, updated_at = $2
                WHERE id = $3
                """,
                status,
                datetime.utcnow(),
                rfq_id,
            )
        logger.info(f"Updated RFQ {rfq_id} status to {status}")


# Singleton
_medusa_db: Optional[MedusaDBClient] = None


async def get_medusa_db() -> MedusaDBClient:
    """Get or create Medusa DB client."""
    global _medusa_db
    if _medusa_db is None:
        _medusa_db = MedusaDBClient()
        await _medusa_db.connect()
    return _medusa_db
