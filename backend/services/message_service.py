import logging
import re
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from models.message import Message, MessageFrom, DeliveryStatus
from schemas.callback import MessageType

logger = logging.getLogger(__name__)


class MessageService:
    def __init__(self, db: Session):
        self.db = db

    def get_message_by_id(self, message_id: int) -> Message:
        """Get message by ID."""
        return self.db.query(Message).filter(Message.id == message_id).first()

    def create_ai_response(
        self,
        original_message_id: int,
        ai_response: str,
        message_sid: str = None,
        message_type: MessageType = None,
    ) -> Message:
        """
        Create an AI response message linked to the original message.

        DEPRECATED: Use create_ai_response_pending + commit_message instead
        for transactional safety with Twilio delivery.
        """
        original_message = self.get_message_by_id(original_message_id)
        if not original_message:
            return None

        # Generate a unique message_sid if not provided
        if not message_sid:
            message_sid = f"ai_response_{original_message_id}"

        ai_message = Message(
            message_sid=message_sid,
            customer_id=original_message.customer_id,
            user_id=None,  # AI response has no user
            body=ai_response,
            from_source=MessageFrom.LLM,
            message_type=message_type,
        )

        self.db.add(ai_message)
        self.db.commit()
        self.db.refresh(ai_message)
        return ai_message

    def create_ai_response_pending(
        self,
        original_message_id: int,
        ai_response: str,
        message_sid: str = None,
        message_type: MessageType = None,
    ) -> Message:
        """
        Create AI response WITHOUT committing to database.
        Caller MUST commit after successful Twilio delivery.

        This prevents orphaned messages when Twilio delivery fails.

        Usage:
            ai_message = message_service.create_ai_response_pending(...)
            try:
                # Send to Twilio
                whatsapp_service.send_message(...)
                # Only commit if Twilio succeeds
                message_service.commit_message(ai_message)
            except TwilioException:
                # Rollback if Twilio fails
                message_service.rollback_message(ai_message)

        Args:
            original_message_id: ID of customer's original message
            ai_response: AI-generated response text
            message_sid:
            Temporary message SID (will be updated with real Twilio SID)
            message_type: REPLY or WHISPER

        Returns:
            Message object (NOT committed, NOT refreshed)
        """
        original_message = self.get_message_by_id(original_message_id)
        if not original_message:
            return None

        # Generate temporary message_sid (will be updated with real Twilio SID)
        if not message_sid:
            message_sid = f"pending_ai_{original_message_id}"

        # Remove [citation:{number}] patterns from ai_response
        ai_response = re.sub(r"\[citation:\d+\]", "", ai_response)

        ai_message = Message(
            message_sid=message_sid,
            customer_id=original_message.customer_id,
            user_id=None,
            body=ai_response,
            from_source=MessageFrom.LLM,
            message_type=message_type,
            delivery_status=DeliveryStatus.PENDING,
        )

        # Add to session but DO NOT COMMIT
        self.db.add(ai_message)
        self.db.flush()  # Get ID without committing

        logger.info(
            f"Created pending AI message {ai_message.id} (not committed)"
        )
        return ai_message

    def commit_message(self, message: Message):
        """
        Commit message after successful delivery.

        Args:
            message: Message object to commit
        """
        self.db.commit()
        self.db.refresh(message)
        logger.info(f"✓ Committed message {message.id} to database")
        return message

    def rollback_message(self, message: Message):
        """
        Rollback message if delivery failed.

        Args:
            message: Message object to rollback
        """
        self.db.rollback()
        logger.warning(f"✗ Rolled back message {message.id} - delivery failed")

    def update_delivery_status(
        self,
        message_id: int,
        delivery_status: DeliveryStatus,
        message_sid: str = None,
        error_code: str = None,
        error_message: str = None,
    ) -> Message:
        """
        Update message delivery status.

        Args:
            message_id: ID of message to update
            delivery_status: New delivery status
            message_sid: Real Twilio message SID (if available)
            error_code: Twilio error code (if failed)
            error_message: Error message (if failed)

        Returns:
            Updated message object
        """
        message = self.get_message_by_id(message_id)
        if not message:
            logger.warning(f"Message {message_id} not found for status update")
            return None

        message.delivery_status = delivery_status

        if message_sid:
            message.message_sid = message_sid
        if error_code:
            message.twilio_error_code = error_code
        if error_message:
            message.twilio_error_message = error_message

        if delivery_status == DeliveryStatus.DELIVERED:
            message.delivered_at = func.now()

        self.db.commit()
        self.db.refresh(message)

        logger.info(
            f"Updated message {message_id} status to {delivery_status.value}"
        )
        return message

    def create_message(
        self,
        message_sid: str,
        customer_id: int,
        body: str,
        from_source: int,
        user_id: int = None,
    ) -> Message:
        """Create a new message."""
        message = Message(
            message_sid=message_sid,
            customer_id=customer_id,
            user_id=user_id,
            body=body,
            from_source=from_source,
        )

        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def get_customer_messages(self, customer_id: int) -> list[Message]:
        """Get all messages for a customer ordered by creation time."""
        return (
            self.db.query(Message)
            .filter(Message.customer_id == customer_id)
            .order_by(Message.created_at.desc())
            .all()
        )
