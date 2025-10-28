"""
Unit tests for RetryService (exponential backoff retry mechanism)

Tests the implementation of Phase 5:
- Exponential backoff retry scheduling (5min, 15min, 60min)
- Permanent vs temporary error handling
- Retry count tracking
- Message status updates
- Integration with WhatsApp service
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from models.customer import Customer
from models.message import Message, MessageFrom, DeliveryStatus
from services.retry_service import RetryService
from config import settings


class TestRetryDetection:
    """Test retry message detection logic"""

    def test_no_retry_for_successful_messages(self, db_session):
        """Test that successfully delivered messages are not retried"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        # Create successful message
        message = Message(
            message_sid="SM_SUCCESS",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.DELIVERED,
            retry_count=0,
        )
        db_session.add(message)
        db_session.commit()

        service = RetryService(db_session)
        messages = service.get_messages_needing_retry()

        assert len(messages) == 0

    def test_retry_for_failed_messages_basic_query(self, db_session):
        """
        Test that failed messages query works correctly
        (timing tested in backoff tests)
        """
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        # Create message that just failed
        # (not ready for retry yet due to 5min backoff)
        message = Message(
            message_sid="SM_FAILED",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=0,
            twilio_error_code="30007",  # Temporary error
        )
        db_session.add(message)
        db_session.commit()

        service = RetryService(db_session)
        messages = service.get_messages_needing_retry()

        # Should be empty since message was just created (needs 5min to pass)
        # Note: Actual retry timing is tested in TestExponentialBackoff tests
        assert len(messages) == 0

    def test_no_retry_for_permanent_errors(self, db_session):
        """Test that messages with permanent errors are not retried"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        # Create failed message with permanent error
        message = Message(
            message_sid="SM_PERMANENT",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=0,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            twilio_error_code="21211",  # Invalid phone number (permanent)
        )
        db_session.add(message)
        db_session.commit()

        service = RetryService(db_session)
        messages = service.get_messages_needing_retry()

        assert len(messages) == 0

    def test_no_retry_when_max_attempts_reached(self, db_session):
        """Test that messages with max retry attempts are not retried"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        # Create failed message with max retries
        message = Message(
            message_sid="SM_MAX_RETRIES",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=3,  # Max attempts
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db_session.add(message)
        db_session.commit()

        service = RetryService(db_session)
        messages = service.get_messages_needing_retry()

        assert len(messages) == 0

    def test_no_retry_when_disabled_in_config(self, db_session):
        """Test that retry is skipped when disabled in config"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        # Create failed message
        message = Message(
            message_sid="SM_FAILED",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=0,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db_session.add(message)
        db_session.commit()

        # Disable retry in config
        original_enabled = settings.retry_enabled
        settings.retry_enabled = False

        try:
            service = RetryService(db_session)
            messages = service.get_messages_needing_retry()

            assert len(messages) == 0

        finally:
            settings.retry_enabled = original_enabled


class TestExponentialBackoff:
    """Test exponential backoff timing"""

    def test_first_retry_after_5_minutes(self, db_session):
        """Test that first retry happens after 5 minutes"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        service = RetryService(db_session)

        # Message created 3 minutes ago (too recent for first retry)
        message_too_recent = Message(
            message_sid="SM_TOO_RECENT",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=0,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=3),
        )
        db_session.add(message_too_recent)

        # Message created 6 minutes ago (ready for first retry)
        message_ready = Message(
            message_sid="SM_READY",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=0,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=6),
        )
        db_session.add(message_ready)
        db_session.commit()

        assert not service._is_ready_for_retry(message_too_recent)
        assert service._is_ready_for_retry(message_ready)

    def test_second_retry_after_15_minutes(self, db_session):
        """Test that second retry happens after 15 minutes"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        service = RetryService(db_session)

        # Message with 1 retry, 10 minutes since last retry (too recent)
        message_too_recent = Message(
            message_sid="SM_TOO_RECENT",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=1,
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            last_retry_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db_session.add(message_too_recent)

        # Message with 1 retry, 20 minutes since last retry (ready)
        message_ready = Message(
            message_sid="SM_READY",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=1,
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            last_retry_at=datetime.now(timezone.utc) - timedelta(minutes=20),
        )
        db_session.add(message_ready)
        db_session.commit()

        assert not service._is_ready_for_retry(message_too_recent)
        assert service._is_ready_for_retry(message_ready)

    def test_third_retry_after_60_minutes(self, db_session):
        """Test that third retry happens after 60 minutes"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        service = RetryService(db_session)

        # Message with 2 retries, 30 minutes since last retry (too recent)
        message_too_recent = Message(
            message_sid="SM_TOO_RECENT",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=2,
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            last_retry_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
        db_session.add(message_too_recent)

        # Message with 2 retries, 65 minutes since last retry (ready)
        message_ready = Message(
            message_sid="SM_READY",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=2,
            created_at=datetime.now(timezone.utc) - timedelta(hours=2),
            last_retry_at=datetime.now(timezone.utc) - timedelta(minutes=65),
        )
        db_session.add(message_ready)
        db_session.commit()

        assert not service._is_ready_for_retry(message_too_recent)
        assert service._is_ready_for_retry(message_ready)


class TestRetryExecution:
    """Test retry execution logic"""

    def test_successful_retry_updates_status(self, db_session):
        """Test that successful retry updates message status"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        # Create failed message
        message = Message(
            message_sid="SM_FAILED",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=0,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            twilio_error_code="30007",
            twilio_error_message="Temporary error",
        )
        db_session.add(message)
        db_session.commit()

        service = RetryService(db_session)

        # Mock WhatsApp service
        with patch.object(
            service.whatsapp_service, "send_message_with_tracking"
        ) as mock_send:
            mock_send.return_value = {
                "sid": "SM_RETRY_SUCCESS",
                "status": "sent",
            }

            result = service.retry_message(message)

            assert result is True
            assert mock_send.called

            # Refresh message
            db_session.refresh(message)

            # Verify updates
            assert message.message_sid == "SM_RETRY_SUCCESS"
            assert message.delivery_status == DeliveryStatus.SENT
            assert message.retry_count == 1
            assert message.last_retry_at is not None
            assert message.twilio_error_code is None
            assert message.twilio_error_message is None

    def test_failed_retry_updates_error_info(self, db_session):
        """Test that failed retry updates error information"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        # Create failed message
        message = Message(
            message_sid="SM_FAILED",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=0,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db_session.add(message)
        db_session.commit()

        service = RetryService(db_session)

        # Mock WhatsApp service to raise exception
        from twilio.base.exceptions import TwilioRestException

        with patch.object(
            service.whatsapp_service, "send_message_with_tracking"
        ) as mock_send:
            mock_send.side_effect = TwilioRestException(
                status=400,
                uri="test",
                msg="Network error",
                code=30003,
            )

            result = service.retry_message(message)

            assert result is False

            # Refresh message
            db_session.refresh(message)

            # Verify updates
            assert message.delivery_status == DeliveryStatus.FAILED
            assert message.retry_count == 1
            assert message.last_retry_at is not None
            assert message.twilio_error_code == "30003"
            assert "Network error" in message.twilio_error_message


class TestRetryBatch:
    """Test batch retry operations"""

    def test_retry_all_pending_processes_multiple_messages(self, db_session):
        """Test that retry_all_pending processes multiple messages"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        # Create 3 failed messages (ready for retry)
        messages = []
        for i in range(3):
            message = Message(
                message_sid=f"SM_FAILED_{i}",
                customer_id=customer.id,
                body=f"Test message {i}",
                from_source=MessageFrom.LLM,
                delivery_status=DeliveryStatus.FAILED,
                retry_count=0,
            )
            db_session.add(message)
            messages.append(message)
        db_session.commit()

        # Update created_at to 10 minutes ago (after server_default is set)
        for message in messages:
            message.created_at = datetime.now(timezone.utc) - timedelta(
                minutes=10
            )
        db_session.commit()

        service = RetryService(db_session)

        # Mock WhatsApp service with unique SIDs
        call_count = [0]  # Use list to allow modification in nested function

        def mock_send_side_effect(*args, **kwargs):
            call_count[0] += 1
            return {
                "sid": f"SM_RETRY_SUCCESS_{call_count[0]}",
                "status": "sent",
            }

        with patch.object(
            service.whatsapp_service, "send_message_with_tracking"
        ) as mock_send:
            mock_send.side_effect = mock_send_side_effect

            stats = service.retry_all_pending()

            assert stats["total_attempted"] == 3
            assert stats["successful"] == 3
            assert stats["failed"] == 0

    def test_retry_all_pending_handles_mixed_results(self, db_session):
        """Test that retry_all_pending handles both successes and failures"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        # Create 2 failed messages
        msg1 = Message(
            message_sid="SM_FAILED_1",
            customer_id=customer.id,
            body="Test message 1",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=0,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        msg2 = Message(
            message_sid="SM_FAILED_2",
            customer_id=customer.id,
            body="Test message 2",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=0,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
        db_session.add_all([msg1, msg2])
        db_session.commit()

        service = RetryService(db_session)

        # Mock WhatsApp service to succeed for first, fail for second
        from twilio.base.exceptions import TwilioRestException

        with patch.object(
            service.whatsapp_service, "send_message_with_tracking"
        ) as mock_send:

            def side_effect(*args, **kwargs):
                if kwargs.get("message_id") == msg1.id:
                    return {"sid": "SM_SUCCESS", "status": "sent"}
                else:
                    raise TwilioRestException(
                        status=400,
                        uri="test",
                        msg="Network error",
                        code=30003,
                    )

            mock_send.side_effect = side_effect

            stats = service.retry_all_pending()

            assert stats["total_attempted"] == 2
            assert stats["successful"] == 1
            assert stats["failed"] == 1


class TestRetryStatus:
    """Test retry status retrieval"""

    def test_get_retry_status_for_retryable_message(self, db_session):
        """Test getting retry status for a retryable message"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        # Create failed message
        message = Message(
            message_sid="SM_FAILED",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=1,
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            last_retry_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            twilio_error_code="30003",
            twilio_error_message="Network error",
        )
        db_session.add(message)
        db_session.commit()

        service = RetryService(db_session)
        status = service.get_retry_status(message.id)

        assert status is not None
        assert status["message_id"] == message.id
        assert status["retry_count"] == 1
        assert status["max_attempts"] == 3
        assert status["can_retry"] is True
        assert status["is_permanent_error"] is False
        assert status["delivery_status"] == "FAILED"
        assert status["error_code"] == "30003"

    def test_get_retry_status_for_permanent_error(self, db_session):
        """Test getting retry status for a permanent error"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        # Create message with permanent error
        message = Message(
            message_sid="SM_PERMANENT",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=0,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            twilio_error_code="21211",  # Invalid phone number
            twilio_error_message="Invalid phone number",
        )
        db_session.add(message)
        db_session.commit()

        service = RetryService(db_session)
        status = service.get_retry_status(message.id)

        assert status is not None
        assert status["can_retry"] is False
        assert status["is_permanent_error"] is True

    def test_get_retry_status_for_nonexistent_message(self, db_session):
        """Test getting retry status for nonexistent message"""
        service = RetryService(db_session)
        status = service.get_retry_status(99999)

        assert status is None
