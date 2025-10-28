"""
RetryService - Handles automatic retry of failed WhatsApp messages

Implements exponential backoff retry mechanism for failed message delivery:
- Retry 1: After 5 minutes
- Retry 2: After 15 minutes
- Retry 3: After 60 minutes (1 hour)

Only retries messages that failed due to temporary/retryable errors.
Permanent errors (invalid number, blocked customer) are not retried.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session
from twilio.base.exceptions import TwilioRestException

from config import settings
from models.message import Message, DeliveryStatus, MessageFrom
from services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)


class RetryService:
    """Handle automatic retry of failed WhatsApp messages"""

    # Twilio error codes that should NOT be retried (permanent failures)
    PERMANENT_ERROR_CODES = {
        "21211",  # Invalid 'To' phone number
        "21408",  # Permission to send SMS/MMS not enabled
        "21610",  # Message blocked (profanity/spam)
        "21614",  # 'To' number is not a valid mobile number
        "63007",  # Message blocked - US A2P compliance
        "63016",  # Message blocked - spam detected
        "30007",  # Message filtered (carrier block)
    }

    def __init__(self, db: Session):
        self.db = db
        self.whatsapp_service = WhatsAppService()
        self.max_attempts = settings.retry_max_attempts
        self.backoff_minutes = settings.retry_backoff_minutes

    def get_messages_needing_retry(self) -> List[Message]:
        """
        Get messages that need retry based on:
        1. Status is FAILED or UNDELIVERED
        2. retry_count < max_attempts
        3. Enough time has passed based on exponential backoff
        4. Not a permanent error

        Returns:
            List of messages ready for retry
        """
        if not settings.retry_enabled:
            logger.debug("Retry mechanism is disabled in config")
            return []

        messages = (
            self.db.query(Message)
            .filter(
                Message.delivery_status.in_(
                    [DeliveryStatus.FAILED, DeliveryStatus.UNDELIVERED]
                ),
                Message.retry_count < self.max_attempts,
                Message.from_source.in_([MessageFrom.LLM, MessageFrom.USER]),
            )
            .all()
        )

        # Filter out permanent errors and messages not ready for retry
        ready_messages = []
        for msg in messages:
            # Skip permanent errors
            if msg.twilio_error_code in self.PERMANENT_ERROR_CODES:
                logger.debug(
                    f"Message {msg.id} has permanent error code "
                    f"{msg.twilio_error_code}, skipping retry"
                )
                continue

            # Check if enough time has passed
            if self._is_ready_for_retry(msg):
                ready_messages.append(msg)

        return ready_messages

    def _is_ready_for_retry(self, message: Message) -> bool:
        """
        Check if message is ready for retry based on exponential backoff.

        Args:
            message: Message to check

        Returns:
            True if enough time has passed for retry
        """
        # First retry: use created_at as base time
        base_time = message.last_retry_at or message.created_at

        if not base_time:
            # Should not happen, but handle gracefully
            return True

        # Get backoff time for this retry attempt
        retry_index = min(message.retry_count, len(self.backoff_minutes) - 1)
        backoff_minutes = self.backoff_minutes[retry_index]

        time_since_last = datetime.now(timezone.utc) - base_time
        backoff_delta = timedelta(minutes=backoff_minutes)

        return time_since_last >= backoff_delta

    def retry_message(self, message: Message) -> bool:
        """
        Retry sending a failed message.

        Args:
            message: Message to retry

        Returns:
            True if retry succeeded, False otherwise
        """
        try:
            logger.info(
                f"Retrying message {message.id} "
                f"(attempt {message.retry_count + 1}/{self.max_attempts})"
            )

            # Send message via WhatsApp
            response = self.whatsapp_service.send_message_with_tracking(
                to_number=message.customer.phone_number,
                message_body=message.body,
                message_id=message.id,
                db=self.db,
            )

            # Update message with new SID and status
            message.message_sid = response['sid']
            message.delivery_status = DeliveryStatus.SENT
            message.retry_count += 1
            message.last_retry_at = datetime.now(timezone.utc)
            message.twilio_error_code = None
            message.twilio_error_message = None

            self.db.commit()

            logger.info(
                f"✓ Message {message.id} "
                f"retried successfully: {response['sid']}"
            )
            return True

        except TwilioRestException as e:
            # Update retry tracking
            message.retry_count += 1
            message.last_retry_at = datetime.now(timezone.utc)
            message.delivery_status = DeliveryStatus.FAILED
            message.twilio_error_code = str(e.code)
            message.twilio_error_message = str(e.msg)[:500]

            self.db.commit()

            # Check if this is a permanent error
            if str(e.code) in self.PERMANENT_ERROR_CODES:
                logger.warning(
                    f"✗ Message {message.id} failed with permanent error "
                    f"{e.code}: {e.msg}"
                )
            else:
                logger.warning(
                    f"✗ Message {message.id} retry failed "
                    f"(attempt {message.retry_count}/{self.max_attempts}): {e}"
                )

            return False

        except Exception as e:
            logger.error(
                f"✗ Unexpected error retrying message {message.id}: {e}"
            )
            self.db.rollback()
            return False

    def retry_all_pending(self) -> dict:
        """
        Retry all messages that are ready for retry.

        Returns:
            Dict with retry statistics
        """
        messages = self.get_messages_needing_retry()

        stats = {
            "total_attempted": len(messages),
            "successful": 0,
            "failed": 0,
            "permanent_errors": 0,
        }

        for message in messages:
            success = self.retry_message(message)
            if success:
                stats["successful"] += 1
            else:
                stats["failed"] += 1
                # Check if permanent error after retry
                if message.twilio_error_code in self.PERMANENT_ERROR_CODES:
                    stats["permanent_errors"] += 1

        logger.info(
            f"Retry batch complete: {stats['successful']} succeeded, "
            f"{stats['failed']} failed, "
            f"{stats['permanent_errors']} permanent errors"
        )

        return stats

    def get_retry_status(self, message_id: int) -> Optional[dict]:
        """
        Get retry status for a specific message.

        Args:
            message_id: ID of message to check

        Returns:
            Dict with retry status information
        """
        message = self.db.query(Message).filter(
            Message.id == message_id
        ).first()

        if not message:
            return None

        can_retry = (
            message.retry_count < self.max_attempts
            and message.twilio_error_code not in self.PERMANENT_ERROR_CODES
            and message.delivery_status in [
                DeliveryStatus.FAILED, DeliveryStatus.PENDING
            ]
        )

        next_retry_time = None
        if can_retry and message.retry_count < len(self.backoff_minutes):
            base_time = message.last_retry_at or message.created_at
            backoff_minutes = self.backoff_minutes[message.retry_count]
            next_retry_time = base_time + timedelta(minutes=backoff_minutes)

        return {
            "message_id": message.id,
            "retry_count": message.retry_count,
            "max_attempts": self.max_attempts,
            "can_retry": can_retry,
            "is_permanent_error": (
                message.twilio_error_code in self.PERMANENT_ERROR_CODES
            ),
            "delivery_status": message.delivery_status.value,
            "last_retry_at": (
                message.last_retry_at.isoformat()
                if message.last_retry_at else None
            ),
            "next_retry_at": (
                next_retry_time.isoformat() if next_retry_time else None
            ),
            "error_code": message.twilio_error_code,
            "error_message": message.twilio_error_message,
        }
