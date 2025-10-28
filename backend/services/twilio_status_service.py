"""
TwilioStatusService - Handles Twilio status callback webhooks

Receives real-time delivery status
updates from Twilio and updates message records.
This provides accurate, real-time tracking of message delivery status.

Status flow:
queued → sending → sent → delivered → read
                     ↓
                  failed/undelivered
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from models.message import Message, DeliveryStatus
from schemas.callback import TwilioMessageStatus, TwilioStatusCallback

logger = logging.getLogger(__name__)


class TwilioStatusService:
    """Handle Twilio status callback webhooks"""

    # Mapping from Twilio status to our DeliveryStatus enum
    STATUS_MAPPING = {
        TwilioMessageStatus.QUEUED: DeliveryStatus.QUEUED,
        TwilioMessageStatus.SENDING: DeliveryStatus.SENDING,
        TwilioMessageStatus.SENT: DeliveryStatus.SENT,
        TwilioMessageStatus.DELIVERED: DeliveryStatus.DELIVERED,
        TwilioMessageStatus.READ: DeliveryStatus.READ,
        TwilioMessageStatus.FAILED: DeliveryStatus.FAILED,
        TwilioMessageStatus.UNDELIVERED: DeliveryStatus.UNDELIVERED,
    }

    def __init__(self, db: Session):
        self.db = db

    def process_status_callback(self, callback: TwilioStatusCallback) -> dict:
        """
        Process Twilio status callback and update message record.

        Args:
            callback: Twilio status callback payload

        Returns:
            Dict with processing result
        """
        try:
            # Find message by SID
            message = (
                self.db.query(Message)
                .filter(Message.message_sid == callback.MessageSid)
                .first()
            )

            if not message:
                logger.warning(
                    f"Received status callback for unknown message: "
                    f"{callback.MessageSid}"
                )
                return {
                    "status": "ignored",
                    "message": "Message not found",
                    "sid": callback.MessageSid,
                }

            # Map Twilio status to our enum
            new_status = self.STATUS_MAPPING.get(callback.MessageStatus)
            if not new_status:
                logger.warning(
                    f"Unknown Twilio status: {callback.MessageStatus} "
                    f"for message {message.id}"
                )
                return {
                    "status": "ignored",
                    "message": "Unknown status",
                    "sid": callback.MessageSid,
                }

            # Store old status for logging
            old_status = message.delivery_status

            # Update message status
            message.delivery_status = new_status

            # Update delivered_at timestamp for DELIVERED status
            if (
                new_status == DeliveryStatus.DELIVERED and
                not message.delivered_at
            ):
                message.delivered_at = datetime.now(timezone.utc)

            # Update error information for failed messages
            if new_status in [
                DeliveryStatus.FAILED, DeliveryStatus.UNDELIVERED
            ]:
                if callback.ErrorCode:
                    message.twilio_error_code = str(callback.ErrorCode)
                if callback.ErrorMessage:
                    message.twilio_error_message = str(
                        callback.ErrorMessage
                    )[:500]

                logger.warning(
                    f"Message {message.id} failed: "
                    f"code={callback.ErrorCode}, msg={callback.ErrorMessage}"
                )

            self.db.commit()

            logger.info(
                f"✓ Message {message.id} status updated: "
                f"{old_status.value} → {new_status.value}"
            )

            return {
                "status": "success",
                "message_id": message.id,
                "old_status": old_status.value,
                "new_status": new_status.value,
                "sid": callback.MessageSid,
            }

        except Exception as e:
            logger.error(f"Error processing Twilio status callback: {e}")
            self.db.rollback()
            return {
                "status": "error",
                "message": str(e),
                "sid": callback.MessageSid,
            }

    def get_delivery_stats(self) -> dict:
        """
        Get overall delivery statistics.

        Returns:
            Dict with delivery statistics by status
        """
        try:
            stats = {}
            for status in DeliveryStatus:
                count = (
                    self.db.query(Message)
                    .filter(Message.delivery_status == status)
                    .count()
                )
                stats[status.value] = count

            return {
                "total_messages": sum(stats.values()),
                "by_status": stats,
                "success_rate": self._calculate_success_rate(stats),
            }

        except Exception as e:
            logger.error(f"Error getting delivery stats: {e}")
            return {
                "error": str(e)
            }

    def _calculate_success_rate(self, stats: dict) -> Optional[float]:
        """
        Calculate delivery success rate.

        Args:
            stats: Dictionary of status counts

        Returns:
            Success rate as percentage (0-100) or None
        """
        total = sum(stats.values())
        if total == 0:
            return None

        # Count delivered and read as successful
        successful = (
            stats.get(DeliveryStatus.DELIVERED.value, 0) +
            stats.get(DeliveryStatus.READ.value, 0)
        )

        return round((successful / total) * 100, 2)

    def get_message_delivery_history(self, message_id: int) -> Optional[dict]:
        """
        Get delivery tracking information for a specific message.

        Args:
            message_id: ID of message to check

        Returns:
            Dict with delivery history or None
        """
        message = self.db\
            .query(Message)\
            .filter(Message.id == message_id).first()

        if not message:
            return None

        return {
            "message_id": message.id,
            "message_sid": message.message_sid,
            "customer_phone": (
                message.customer.phone_number
                if message.customer else None
            ),
            "delivery_status": message.delivery_status.value,
            "created_at": (
                message.created_at.isoformat()
                if message.created_at else None
            ),
            "delivered_at": (
                message.delivered_at.isoformat()
                if message.delivered_at else None
            ),
            "retry_count": message.retry_count,
            "last_retry_at": (
                message.last_retry_at.isoformat()
                if message.last_retry_at else None
            ),
            "error_code": message.twilio_error_code,
            "error_message": message.twilio_error_message,
        }
