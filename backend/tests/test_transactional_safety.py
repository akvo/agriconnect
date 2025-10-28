"""
Unit tests for transactional safety in message delivery

Tests that messages are only persisted after successful Twilio delivery,
preventing orphaned messages when delivery fails.

CRITICAL: These tests verify the fix for the message persistence issue where
AI messages were saved to database BEFORE sending to Twilio, causing orphaned
messages when Twilio failed.
"""

from sqlalchemy.orm import Session

from models.customer import Customer
from models.message import Message, MessageFrom, MessageType, DeliveryStatus
from services.message_service import MessageService


class TestMessageServiceTransactional:
    """Test MessageService transactional methods"""

    def test_create_ai_response_pending_not_committed(
        self, db_session: Session
    ):
        """Test that create_ai_response_pending does NOT commit to database"""
        # Create customer and original message
        customer = Customer(phone_number="+255712345678")
        db_session.add(customer)
        db_session.commit()

        original_msg = Message(
            message_sid="SM_ORIGINAL",
            customer_id=customer.id,
            body="Customer question",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(original_msg)
        db_session.commit()

        # Create AI response WITHOUT committing
        msg_service = MessageService(db_session)
        ai_msg = msg_service.create_ai_response_pending(
            original_message_id=original_msg.id,
            ai_response="AI answer",
            message_type=MessageType.REPLY,
        )

        # Verify message has ID (from flush)
        assert ai_msg.id is not None
        assert ai_msg.delivery_status == DeliveryStatus.PENDING

        # CRITICAL:
        # Verify message is NOT visible in a new session (not committed)
        db_session.rollback()  # Simulate transaction rollback

        # Try to find the message in DB
        count = (
            db_session.query(Message)
            .filter(Message.from_source == MessageFrom.LLM)
            .count()
        )

        # Message should NOT exist in database
        assert count == 0

    def test_commit_message_persists_to_database(self, db_session: Session):
        """Test that commit_message successfully persists message"""
        # Create customer and original message
        customer = Customer(phone_number="+255712345678")
        db_session.add(customer)
        db_session.commit()

        original_msg = Message(
            message_sid="SM_ORIGINAL",
            customer_id=customer.id,
            body="Customer question",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(original_msg)
        db_session.commit()

        # Create and commit AI response
        msg_service = MessageService(db_session)
        ai_msg = msg_service.create_ai_response_pending(
            original_message_id=original_msg.id,
            ai_response="AI answer",
            message_type=MessageType.REPLY,
        )

        # Commit the message
        msg_service.commit_message(ai_msg)

        # Verify message persists in database
        persisted_msg = (
            db_session.query(Message).filter(Message.id == ai_msg.id).first()
        )

        assert persisted_msg is not None
        assert persisted_msg.body == "AI answer"
        assert persisted_msg.from_source == MessageFrom.LLM

    def test_rollback_message_removes_from_database(self, db_session: Session):
        """Test that rollback_message removes unpersisted message"""
        # Create customer and original message
        customer = Customer(phone_number="+255712345678")
        db_session.add(customer)
        db_session.commit()

        original_msg = Message(
            message_sid="SM_ORIGINAL",
            customer_id=customer.id,
            body="Customer question",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(original_msg)
        db_session.commit()

        # Create AI response
        msg_service = MessageService(db_session)
        ai_msg = msg_service.create_ai_response_pending(
            original_message_id=original_msg.id,
            ai_response="AI answer",
            message_type=MessageType.REPLY,
        )

        msg_id = ai_msg.id
        assert msg_id is not None

        # Rollback the message
        msg_service.rollback_message(ai_msg)

        # Verify message was rolled back
        rolled_back_msg = (
            db_session.query(Message).filter(Message.id == msg_id).first()
        )

        assert rolled_back_msg is None

    def test_update_delivery_status(self, db_session: Session):
        """Test updating delivery status of existing message"""
        # Create customer and message
        customer = Customer(phone_number="+255712345678")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM12345",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.PENDING,
        )
        db_session.add(message)
        db_session.commit()

        # Update status
        msg_service = MessageService(db_session)
        updated_msg = msg_service.update_delivery_status(
            message_id=message.id,
            delivery_status=DeliveryStatus.SENT,
            message_sid="SM_REAL_SID",
        )

        assert updated_msg.delivery_status == DeliveryStatus.SENT
        assert updated_msg.message_sid == "SM_REAL_SID"


class TestTransactionalSafetyIntegration:
    """Integration tests for transactional safety"""

    def test_message_not_persisted_on_failed_delivery(
        self, db_session: Session
    ):
        """Test that message is NOT in database if delivery fails"""
        # Create customer and original message
        customer = Customer(phone_number="+255712345678")
        db_session.add(customer)
        db_session.commit()

        original_msg = Message(
            message_sid="SM_ORIGINAL",
            customer_id=customer.id,
            body="Customer question",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(original_msg)
        db_session.commit()

        # Simulate the full flow with failed delivery
        msg_service = MessageService(db_session)

        # Step 1: Create pending message
        ai_msg = msg_service.create_ai_response_pending(
            original_message_id=original_msg.id,
            ai_response="AI answer",
            message_type=MessageType.REPLY,
        )

        # Step 2: Simulate Twilio delivery failure
        try:
            # Simulate delivery attempt
            raise ValueError("Twilio delivery failed")
        except ValueError:
            # Step 3: Rollback on failure
            msg_service.rollback_message(ai_msg)

        # CRITICAL: Verify message was NOT persisted to database
        llm_messages = (
            db_session.query(Message)
            .filter(Message.from_source == MessageFrom.LLM)
            .all()
        )

        assert len(llm_messages) == 0

    def test_message_persisted_only_on_successful_delivery(
        self, db_session: Session
    ):
        """Test that message IS in database only if delivery succeeds"""
        # Create customer and original message
        customer = Customer(phone_number="+255712345678")
        db_session.add(customer)
        db_session.commit()

        original_msg = Message(
            message_sid="SM_ORIGINAL",
            customer_id=customer.id,
            body="Customer question",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(original_msg)
        db_session.commit()

        # Simulate the full flow with successful delivery
        msg_service = MessageService(db_session)

        # Step 1: Create pending message
        ai_msg = msg_service.create_ai_response_pending(
            original_message_id=original_msg.id,
            ai_response="AI answer",
            message_type=MessageType.REPLY,
        )

        # Step 2: Simulate successful Twilio delivery
        twilio_sid = "SM_TWILIO_123"
        ai_msg.message_sid = twilio_sid
        ai_msg.delivery_status = DeliveryStatus.SENT

        # Step 3: Commit on success
        msg_service.commit_message(ai_msg)

        # CRITICAL: Verify message WAS persisted to database
        llm_messages = (
            db_session.query(Message)
            .filter(Message.from_source == MessageFrom.LLM)
            .all()
        )

        assert len(llm_messages) == 1
        assert llm_messages[0].message_sid == twilio_sid
        assert llm_messages[0].delivery_status == DeliveryStatus.SENT

    def test_no_orphaned_messages_after_multiple_failures(
        self, db_session: Session
    ):
        """
        Test that multiple failed deliveries don't create orphaned messages
        """
        # Create customer and original message
        customer = Customer(phone_number="+255712345678")
        db_session.add(customer)
        db_session.commit()

        original_msg = Message(
            message_sid="SM_ORIGINAL",
            customer_id=customer.id,
            body="Customer question",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(original_msg)
        db_session.commit()

        msg_service = MessageService(db_session)

        # Simulate 3 failed delivery attempts
        for i in range(3):
            # Create pending message
            ai_msg = msg_service.create_ai_response_pending(
                original_message_id=original_msg.id,
                ai_response=f"AI answer attempt {i+1}",
                message_type=MessageType.REPLY,
            )

            # Simulate delivery failure
            msg_service.rollback_message(ai_msg)

        # CRITICAL: Verify NO orphaned messages in database
        llm_messages = (
            db_session.query(Message)
            .filter(Message.from_source == MessageFrom.LLM)
            .all()
        )

        assert len(llm_messages) == 0


class TestDeprecatedMethod:
    """Test that deprecated create_ai_response still works"""

    def test_deprecated_create_ai_response_still_works(
        self, db_session: Session
    ):
        """
        Test that old create_ai_response method still works
        (for backward compatibility)
        """
        # Create customer and original message
        customer = Customer(phone_number="+255712345678")
        db_session.add(customer)
        db_session.commit()

        original_msg = Message(
            message_sid="SM_ORIGINAL",
            customer_id=customer.id,
            body="Customer question",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(original_msg)
        db_session.commit()

        # Use deprecated method
        msg_service = MessageService(db_session)
        ai_msg = msg_service.create_ai_response(
            original_message_id=original_msg.id,
            ai_response="AI answer",
            message_type=MessageType.REPLY,
        )

        # Should still work and commit immediately
        assert ai_msg is not None
        assert ai_msg.id is not None

        # Verify message is in database
        persisted_msg = (
            db_session.query(Message).filter(Message.id == ai_msg.id).first()
        )
        assert persisted_msg is not None
