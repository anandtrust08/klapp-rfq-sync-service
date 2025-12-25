# =============================================================================
# FILE: src/models/events.py
# Event models for sync service
# =============================================================================

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class SyncDirection(str, Enum):
    EMAIL_TO_MEDUSA = "email_to_medusa"
    MEDUSA_TO_EMAIL = "medusa_to_email"


class SyncStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class LineItem(BaseModel):
    """Line item in RFQ."""
    description: str
    quantity: int = 1
    unit: str = "pcs"
    part_number: Optional[str] = None
    manufacturer: Optional[str] = None
    specifications: Dict[str, Any] = Field(default_factory=dict)
    unit_price: Optional[float] = None


class CustomerInfo(BaseModel):
    """Customer information."""
    email: str
    name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None


class DeliveryInfo(BaseModel):
    """Delivery information."""
    city: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    required_date: Optional[datetime] = None
    payment_terms: Optional[str] = None


class RFQSyncRequest(BaseModel):
    """Request to sync RFQ."""
    event_id: str
    event_type: str
    event_timestamp: datetime
    source_service: str
    idempotency_key: str
    correlation_id: Optional[str] = None

    email_rfq_id: str
    rfq_number: str
    rfq_data: Dict[str, Any]

    sync_direction: SyncDirection = SyncDirection.EMAIL_TO_MEDUSA
    retry_count: int = 0
    max_retries: int = 3


class RFQSyncResult(BaseModel):
    """Result of sync operation."""
    email_rfq_id: str
    medusa_rfq_id: Optional[str] = None
    rfq_number: str
    sync_direction: SyncDirection
    sync_status: SyncStatus
    sync_started_at: datetime
    sync_completed_at: datetime
    duration_ms: int
    error_message: Optional[str] = None


class MedusaRFQ(BaseModel):
    """RFQ in Medusa format."""
    rfq_number: str
    customer_email: str
    customer_name: Optional[str] = None
    customer_company: Optional[str] = None
    customer_id: Optional[str] = None
    company_id: Optional[str] = None
    description: Optional[str] = None
    line_items: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "received"
    priority: str = "medium"
    currency: str = "EUR"
    estimated_value: Optional[float] = None
    requirements: Optional[Dict[str, Any]] = None
    delivery_address: Optional[Dict[str, Any]] = None
    attachments: Optional[Dict[str, Any]] = None
    ai_confidence_score: Optional[float] = None
    ai_analysis: Optional[Dict[str, Any]] = None
    external_id: str  # email_rfq_id
    external_source: str = "email"
    sync_status: str = "synced"
