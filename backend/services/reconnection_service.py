"""
ReconnectionService - Handles 24-hour reconnection template logic

WhatsApp Business Policy requires using approved templates when initiating
conversations after 24 hours of inactivity. This service:
1. Detects when customer returns after 24+ hours
2. Sends reconnection template before processing their message
3. Updates last_message tracking for customers
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from config import settings
from models.customer import Customer
from models.message import MessageFrom
from services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)


class ReconnectionService:
    """Handle 24-hour reconnection template logic"""

    def __init__(self, db: Session):
        self.db = db
        self.whatsapp_service = WhatsAppService()
        self.threshold_hours = settings.whatsapp_reconnection_threshold_hours

    def check_and_send_reconnection(
        self, customer: Customer, pending_message_count: int
    ) -> bool:
        """
        Check if reconnection template is needed and send it.

        Args:
            customer: Customer who sent message
            incoming_message_body: Preview of customer's message

        Returns:
            True if reconnection template was sent, False otherwise
        """
        if not customer.needs_reconnection_template(self.threshold_hours):
            logger.debug(
                f"Customer {customer.id} does not need reconnection template"
            )
            return False

        if pending_message_count <= 0:
            logger.debug(
                f"Customer {customer.id} has no pending messages; "
                f"skipping reconnection template"
            )
            return False

        template_sid = settings.whatsapp_reconnection_template_sid
        if not template_sid:
            logger.warning(
                f"Reconnection template needed for customer {customer.id} "
                f"but SID not configured"
            )
            return False

        try:
            # Send reconnection template
            logger.info(
                f"Sending reconnection template to customer {customer.id} "
                f"(inactive for {self.threshold_hours}+ hours)"
            )

            response = self.whatsapp_service.send_template_message(
                to=customer.phone_number,
                content_sid=template_sid,
                content_variables={
                    "1": f"{pending_message_count}"
                },
            )

            # Update customer last_message tracking
            customer.last_message_at = datetime.now(timezone.utc)
            customer.last_message_from = MessageFrom.USER

            self.db.commit()

            logger.info(
                f"✓ Sent reconnection template to customer {customer.id}: "
                f"{response['sid']}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to send reconnection template: {e}")
            self.db.rollback()
            return False

    def update_customer_last_message(
        self, customer_id: int, from_source: int
    ):
        """
        Update customer's last message timestamp.

        Args:
            customer_id: ID of customer
            from_source: Who sent the message (MessageFrom.CUSTOMER/USER/LLM)
        """
        customer = self.db.query(Customer).filter(
            Customer.id == customer_id
        ).first()

        if customer:
            customer.last_message_at = datetime.now(timezone.utc)
            customer.last_message_from = from_source
            self.db.commit()
            logger.debug(
                f"Updated last_message for customer {customer_id} "
                f"(from_source={from_source})"
            )
        else:
            logger.warning(
                f"Customer {customer_id} not found for last_message update"
            )
