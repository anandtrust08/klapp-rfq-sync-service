# =============================================================================
# FILE: src/services/transformer.py
# Data transformation between email service and Medusa formats
# =============================================================================

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from src.models.events import MedusaRFQ, LineItem, CustomerInfo, DeliveryInfo

logger = logging.getLogger(__name__)


class RFQTransformer:
    """
    Transforms RFQ data between email service and Medusa formats.
    Handles field mapping, status translation, and data normalization.
    """

    # Status mapping: Email Service -> Medusa
    EMAIL_TO_MEDUSA_STATUS = {
        "received": "received",
        "parsing": "processing",
        "classified": "processing",
        "validated": "processing",
        "pending_review": "processing",
        "approved": "processing",
        "quote_requested": "quoted",
        "quoted": "quoted",
        "proposal_sent": "sent",
        "accepted": "approved",
        "rejected": "rejected",
        "cancelled": "rejected",
        "completed": "approved",
    }

    # Status mapping: Medusa -> Email Service
    MEDUSA_TO_EMAIL_STATUS = {
        "received": "received",
        "processing": "validated",
        "quoted": "quoted",
        "sent": "proposal_sent",
        "approved": "accepted",
        "rejected": "rejected",
    }

    # Priority mapping
    PRIORITY_MAP = {
        "low": "low",
        "medium": "medium",
        "high": "high",
        "urgent": "urgent",
        "critical": "urgent",
    }

    def transform_email_to_medusa(
        self,
        email_rfq_data: Dict[str, Any],
    ) -> MedusaRFQ:
        """
        Transform RFQ data from email service format to Medusa format.
        """
        # Extract customer info
        customer = email_rfq_data.get("customer", {})

        # Extract line items
        raw_line_items = email_rfq_data.get("line_items", [])
        line_items = [
            self._transform_line_item(item)
            for item in raw_line_items
        ]

        # Extract delivery info
        delivery = email_rfq_data.get("delivery", {})
        delivery_address = None
        if delivery:
            delivery_address = {
                "city": delivery.get("city"),
                "country": delivery.get("country"),
                "address": delivery.get("address"),
                "required_date": delivery.get("required_date"),
                "payment_terms": delivery.get("payment_terms"),
                "special_instructions": delivery.get("special_instructions"),
            }

        # Build description from line items if not provided
        description = email_rfq_data.get("description") or email_rfq_data.get("title")
        if not description and line_items:
            description = "; ".join(
                item.get("description", "") for item in raw_line_items[:3]
            )
            if len(raw_line_items) > 3:
                description += f" (+{len(raw_line_items) - 3} more items)"

        # Map status
        email_status = email_rfq_data.get("status", "received")
        medusa_status = self.EMAIL_TO_MEDUSA_STATUS.get(email_status, "received")

        # Map priority
        email_priority = email_rfq_data.get("priority", "medium")
        medusa_priority = self.PRIORITY_MAP.get(email_priority, "medium")

        return MedusaRFQ(
            rfq_number=email_rfq_data.get("rfq_number", ""),
            customer_email=customer.get("email", ""),
            customer_name=customer.get("name"),
            customer_company=customer.get("company"),
            description=description,
            line_items=line_items,
            status=medusa_status,
            priority=medusa_priority,
            currency=email_rfq_data.get("currency", "EUR"),
            estimated_value=email_rfq_data.get("estimated_value"),
            delivery_address=delivery_address,
            ai_confidence_score=email_rfq_data.get("ai_confidence_score"),
            ai_analysis={
                "source": "email",
                "email_rfq_id": email_rfq_data.get("email_rfq_id"),
                "confidence": email_rfq_data.get("ai_confidence_score"),
                "language": email_rfq_data.get("language"),
            },
            external_id=str(email_rfq_data.get("email_rfq_id", "")),
            external_source="email",
        )

    def transform_medusa_to_email(
        self,
        medusa_rfq_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Transform RFQ data from Medusa format to email service format.
        Used for syncing updates back to email service.
        """
        medusa_status = medusa_rfq_data.get("status", "received")
        email_status = self.MEDUSA_TO_EMAIL_STATUS.get(medusa_status, "validated")

        return {
            "status": email_status,
            "priority": medusa_rfq_data.get("priority", "medium"),
            "assigned_to": medusa_rfq_data.get("assigned_to"),
            "internal_notes": medusa_rfq_data.get("internal_notes"),
            "medusa_rfq_id": medusa_rfq_data.get("id"),
            "medusa_synced_at": datetime.utcnow().isoformat(),
        }

    def _transform_line_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Transform a single line item."""
        return {
            "description": item.get("description", ""),
            "quantity": item.get("quantity", 1),
            "unit": item.get("unit", "pcs"),
            "part_number": item.get("part_number"),
            "manufacturer": item.get("manufacturer"),
            "specifications": item.get("specifications", {}),
            "unit_price": item.get("unit_price"),
            "total_price": item.get("total_price"),
        }

    def validate_for_sync(
        self,
        rfq_data: Dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """
        Validate RFQ data before sync.
        Returns (is_valid, list of error messages).
        """
        errors = []

        # Required fields
        if not rfq_data.get("rfq_number"):
            errors.append("Missing rfq_number")

        customer = rfq_data.get("customer", {})
        if not customer.get("email"):
            errors.append("Missing customer email")

        line_items = rfq_data.get("line_items", [])
        if not line_items:
            errors.append("No line items found")

        for i, item in enumerate(line_items):
            if not item.get("description"):
                errors.append(f"Line item {i+1} missing description")

        return len(errors) == 0, errors


# Singleton instance
transformer = RFQTransformer()
