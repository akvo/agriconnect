"""
Unit tests for Twilio Status Callbacks (Phase 6)

Tests the implementation of real-time delivery status tracking:
- Status callback processing
- Message status updates
- Delivery timestamp tracking
- Error information capture
- Delivery statistics
"""

from datetime import datetime, timezone, timedelta

from models.customer import Customer
from models.message import Message, MessageFrom, DeliveryStatus
from services.twilio_status_service import TwilioStatusService
from schemas.callback import TwilioStatusCallback, TwilioMessageStatus


class TestStatusCallbackProcessing:
    """Test Twilio status callback processing"""

    def test_process_queued_status(self, db_session):
        """Test processing queued status callback"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        # Create message
        message = Message(
            message_sid="SM_TEST_123",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.PENDING,
        )
        db_session.add(message)
        db_session.commit()

        # Create callback payload
        callback = TwilioStatusCallback(
            MessageSid="SM_TEST_123",
            MessageStatus=TwilioMessageStatus.QUEUED,
            To="whatsapp:+255712345678",
            From="whatsapp:+123456789",
        )

        service = TwilioStatusService(db_session)
        result = service.process_status_callback(callback)

        assert result["status"] == "success"
        assert result["message_id"] == message.id
        assert result["new_status"] == "QUEUED"

        # Verify message updated
        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.QUEUED

    def test_process_sent_status(self, db_session):
        """Test processing sent status callback"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM_TEST_456",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.QUEUED,
        )
        db_session.add(message)
        db_session.commit()

        callback = TwilioStatusCallback(
            MessageSid="SM_TEST_456",
            MessageStatus=TwilioMessageStatus.SENT,
            To="whatsapp:+255712345678",
            From="whatsapp:+123456789",
        )

        service = TwilioStatusService(db_session)
        result = service.process_status_callback(callback)

        assert result["status"] == "success"
        assert result["old_status"] == "QUEUED"
        assert result["new_status"] == "SENT"

        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.SENT

    def test_process_delivered_status_sets_timestamp(self, db_session):
        """Test that delivered status sets delivered_at timestamp"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM_TEST_789",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.SENT,
        )
        db_session.add(message)
        db_session.commit()

        assert message.delivered_at is None

        callback = TwilioStatusCallback(
            MessageSid="SM_TEST_789",
            MessageStatus=TwilioMessageStatus.DELIVERED,
            To="whatsapp:+255712345678",
            From="whatsapp:+123456789",
        )

        service = TwilioStatusService(db_session)
        service.process_status_callback(callback)

        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.DELIVERED
        assert message.delivered_at is not None
        assert isinstance(message.delivered_at, datetime)

    def test_process_read_status(self, db_session):
        """Test processing read status callback"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM_TEST_READ",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.DELIVERED,
        )
        db_session.add(message)
        db_session.commit()

        callback = TwilioStatusCallback(
            MessageSid="SM_TEST_READ",
            MessageStatus=TwilioMessageStatus.READ,
            To="whatsapp:+255712345678",
            From="whatsapp:+123456789",
        )

        service = TwilioStatusService(db_session)
        result = service.process_status_callback(callback)

        assert result["status"] == "success"
        assert result["new_status"] == "READ"

        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.READ

    def test_process_failed_status_captures_error(self, db_session):
        """Test that failed status captures error information"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM_TEST_FAIL",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.SENT,
        )
        db_session.add(message)
        db_session.commit()

        callback = TwilioStatusCallback(
            MessageSid="SM_TEST_FAIL",
            MessageStatus=TwilioMessageStatus.FAILED,
            ErrorCode="30007",
            ErrorMessage="Message blocked by carrier",
            To="whatsapp:+255712345678",
            From="whatsapp:+123456789",
        )

        service = TwilioStatusService(db_session)
        service.process_status_callback(callback)

        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.FAILED
        assert message.twilio_error_code == "30007"
        assert message.twilio_error_message == "Message blocked by carrier"

    def test_process_undelivered_status(self, db_session):
        """Test processing undelivered status callback"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM_TEST_UNDELIVERED",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.SENT,
        )
        db_session.add(message)
        db_session.commit()

        callback = TwilioStatusCallback(
            MessageSid="SM_TEST_UNDELIVERED",
            MessageStatus=TwilioMessageStatus.UNDELIVERED,
            ErrorCode="30003",
            ErrorMessage="Unreachable destination",
            To="whatsapp:+255712345678",
            From="whatsapp:+123456789",
        )

        service = TwilioStatusService(db_session)
        service.process_status_callback(callback)

        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.UNDELIVERED
        assert message.twilio_error_code == "30003"

    def test_callback_for_unknown_message(self, db_session):
        """Test callback for message that doesn't exist"""
        callback = TwilioStatusCallback(
            MessageSid="SM_UNKNOWN",
            MessageStatus=TwilioMessageStatus.DELIVERED,
            To="whatsapp:+255712345678",
            From="whatsapp:+123456789",
        )

        service = TwilioStatusService(db_session)
        result = service.process_status_callback(callback)

        assert result["status"] == "ignored"
        assert result["message"] == "Message not found"
        assert result["sid"] == "SM_UNKNOWN"


class TestDeliveryStatistics:
    """Test delivery statistics functionality"""

    def test_get_delivery_stats(self, db_session):
        """Test getting delivery statistics"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        # Create messages with different statuses
        statuses = [
            DeliveryStatus.PENDING,
            DeliveryStatus.SENT,
            DeliveryStatus.DELIVERED,
            DeliveryStatus.DELIVERED,
            DeliveryStatus.FAILED,
        ]

        for i, status in enumerate(statuses):
            message = Message(
                message_sid=f"SM_TEST_{i}",
                customer_id=customer.id,
                body=f"Test message {i}",
                from_source=MessageFrom.LLM,
                delivery_status=status,
            )
            db_session.add(message)
        db_session.commit()

        service = TwilioStatusService(db_session)
        stats = service.get_delivery_stats()

        assert stats["total_messages"] == 5
        assert stats["by_status"]["PENDING"] == 1
        assert stats["by_status"]["SENT"] == 1
        assert stats["by_status"]["DELIVERED"] == 2
        assert stats["by_status"]["FAILED"] == 1
        # Success rate: 2 delivered out of 5 total = 40%
        assert stats["success_rate"] == 40.0

    def test_success_rate_calculation(self, db_session):
        """Test success rate calculation"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        # Create 7 delivered, 2 read, 1 failed (10 total)
        # Success rate should be 90% (9 successful out of 10)
        for i in range(7):
            message = Message(
                message_sid=f"SM_DELIVERED_{i}",
                customer_id=customer.id,
                body=f"Test {i}",
                from_source=MessageFrom.LLM,
                delivery_status=DeliveryStatus.DELIVERED,
            )
            db_session.add(message)

        for i in range(2):
            message = Message(
                message_sid=f"SM_READ_{i}",
                customer_id=customer.id,
                body=f"Test {i}",
                from_source=MessageFrom.LLM,
                delivery_status=DeliveryStatus.READ,
            )
            db_session.add(message)

        message = Message(
            message_sid="SM_FAILED",
            customer_id=customer.id,
            body="Test",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
        )
        db_session.add(message)
        db_session.commit()

        service = TwilioStatusService(db_session)
        stats = service.get_delivery_stats()

        assert stats["total_messages"] == 10
        assert stats["success_rate"] == 90.0

    def test_success_rate_with_no_messages(self, db_session):
        """Test success rate calculation with no messages"""
        service = TwilioStatusService(db_session)
        stats = service.get_delivery_stats()

        assert stats["total_messages"] == 0
        assert stats["success_rate"] is None


class TestMessageDeliveryHistory:
    """Test message delivery history retrieval"""

    def test_get_message_delivery_history(self, db_session):
        """Test getting delivery history for a message"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        delivered_at = datetime.now(timezone.utc) - timedelta(minutes=30)

        message = Message(
            message_sid="SM_HISTORY_TEST",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.DELIVERED,
            created_at=created_at,
            delivered_at=delivered_at,
            retry_count=1,
            last_retry_at=datetime.now(timezone.utc) - timedelta(minutes=45),
        )
        db_session.add(message)
        db_session.commit()

        service = TwilioStatusService(db_session)
        history = service.get_message_delivery_history(message.id)

        assert history is not None
        assert history["message_id"] == message.id
        assert history["message_sid"] == "SM_HISTORY_TEST"
        assert history["customer_phone"] == "+255712345678"
        assert history["delivery_status"] == "DELIVERED"
        assert history["retry_count"] == 1
        assert history["created_at"] is not None
        assert history["delivered_at"] is not None
        assert history["last_retry_at"] is not None

    def test_get_delivery_history_with_errors(self, db_session):
        """Test getting delivery history for failed message"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM_ERROR_TEST",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            twilio_error_code="30007",
            twilio_error_message="Message blocked",
        )
        db_session.add(message)
        db_session.commit()

        service = TwilioStatusService(db_session)
        history = service.get_message_delivery_history(message.id)

        assert history["error_code"] == "30007"
        assert history["error_message"] == "Message blocked"

    def test_get_delivery_history_for_nonexistent_message(self, db_session):
        """Test getting delivery history for non-existent message"""
        service = TwilioStatusService(db_session)
        history = service.get_message_delivery_history(99999)

        assert history is None


class TestStatusTransitions:
    """Test message status transitions via callbacks"""

    def test_complete_delivery_flow(self, db_session):
        """
        Test complete message delivery flow:
        pending → queued → sent → delivered
        """
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM_FLOW_TEST",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.PENDING,
        )
        db_session.add(message)
        db_session.commit()

        service = TwilioStatusService(db_session)

        # Step 1: queued
        callback1 = TwilioStatusCallback(
            MessageSid="SM_FLOW_TEST",
            MessageStatus=TwilioMessageStatus.QUEUED,
            To="whatsapp:+255712345678",
            From="whatsapp:+123456789",
        )
        service.process_status_callback(callback1)
        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.QUEUED

        # Step 2: sent
        callback2 = TwilioStatusCallback(
            MessageSid="SM_FLOW_TEST",
            MessageStatus=TwilioMessageStatus.SENT,
            To="whatsapp:+255712345678",
            From="whatsapp:+123456789",
        )
        service.process_status_callback(callback2)
        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.SENT

        # Step 3: delivered
        callback3 = TwilioStatusCallback(
            MessageSid="SM_FLOW_TEST",
            MessageStatus=TwilioMessageStatus.DELIVERED,
            To="whatsapp:+255712345678",
            From="whatsapp:+123456789",
        )
        service.process_status_callback(callback3)
        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.DELIVERED
        assert message.delivered_at is not None

    def test_failure_after_sent(self, db_session):
        """Test failure transition after sent status"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM_FAIL_FLOW",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.SENT,
        )
        db_session.add(message)
        db_session.commit()

        service = TwilioStatusService(db_session)

        # Receive failed callback
        callback = TwilioStatusCallback(
            MessageSid="SM_FAIL_FLOW",
            MessageStatus=TwilioMessageStatus.FAILED,
            ErrorCode="30007",
            ErrorMessage="Carrier blocked",
            To="whatsapp:+255712345678",
            From="whatsapp:+123456789",
        )
        service.process_status_callback(callback)

        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.FAILED
        assert message.twilio_error_code == "30007"
        assert message.delivered_at is None
