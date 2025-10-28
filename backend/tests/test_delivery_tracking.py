"""
Unit tests for delivery tracking functionality

Tests the new delivery status tracking features
added to Message and Customer models:
- DeliveryStatus enum
- Delivery tracking fields (delivery_status, retry_count, etc.)
- Last message tracking for 24-hour reconnection logic
- Helper methods for delivery status checking
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session

from models.customer import Customer
from models.message import Message, MessageFrom, DeliveryStatus


class TestDeliveryStatusEnum:
    """Test DeliveryStatus enum values and behavior"""

    def test_delivery_status_values(self):
        """Test that all delivery status enum values are defined"""
        assert DeliveryStatus.PENDING.value == "PENDING"
        assert DeliveryStatus.QUEUED.value == "QUEUED"
        assert DeliveryStatus.SENDING.value == "SENDING"
        assert DeliveryStatus.SENT.value == "SENT"
        assert DeliveryStatus.DELIVERED.value == "DELIVERED"
        assert DeliveryStatus.READ.value == "READ"
        assert DeliveryStatus.FAILED.value == "FAILED"
        assert DeliveryStatus.UNDELIVERED.value == "UNDELIVERED"

    def test_delivery_status_enum_members(self):
        """Test that all expected enum members exist"""
        expected_members = [
            "PENDING",
            "QUEUED",
            "SENDING",
            "SENT",
            "DELIVERED",
            "READ",
            "FAILED",
            "UNDELIVERED",
        ]
        actual_members = [status.name for status in DeliveryStatus]
        assert set(actual_members) == set(expected_members)


class TestMessageDeliveryTracking:
    """Test message delivery tracking fields and methods"""

    def test_create_message_with_default_delivery_status(
        self, db_session: Session
    ):
        """Test that new messages default to PENDING delivery status"""
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        assert message.delivery_status == DeliveryStatus.PENDING
        assert message.retry_count == 0
        assert message.twilio_error_code is None
        assert message.twilio_error_message is None
        assert message.last_retry_at is None
        assert message.delivered_at is None

    def test_message_with_sent_status(self, db_session: Session):
        """Test creating message with SENT delivery status"""
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.SENT,
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        assert message.delivery_status == DeliveryStatus.SENT

    def test_message_with_delivered_status_and_timestamp(
        self, db_session: Session
    ):
        """Test message with DELIVERED status and delivered_at timestamp"""
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        delivered_time = datetime.now(timezone.utc)
        message = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.DELIVERED,
            delivered_at=delivered_time,
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        assert message.delivery_status == DeliveryStatus.DELIVERED
        assert message.delivered_at is not None
        assert abs((message.delivered_at - delivered_time).total_seconds()) < 1

    def test_message_with_twilio_error(self, db_session: Session):
        """Test message with Twilio error information"""
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            twilio_error_code="21211",
            twilio_error_message="Invalid phone number",
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        assert message.delivery_status == DeliveryStatus.FAILED
        assert message.twilio_error_code == "21211"
        assert message.twilio_error_message == "Invalid phone number"

    def test_message_with_retry_tracking(self, db_session: Session):
        """Test message with retry count and timestamp"""
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        retry_time = datetime.now(timezone.utc)
        message = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.PENDING,
            retry_count=2,
            last_retry_at=retry_time,
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        assert message.retry_count == 2
        assert message.last_retry_at is not None
        assert abs((message.last_retry_at - retry_time).total_seconds()) < 1


class TestMessageDeliveryHelperMethods:
    """Test helper methods for checking delivery status"""

    def test_is_delivery_failed_with_failed_status(self, db_session: Session):
        """Test is_delivery_failed returns True for FAILED status"""
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
        )
        db_session.add(message)
        db_session.commit()

        assert message.is_delivery_failed() is True

    def test_is_delivery_failed_with_undelivered_status(
        self, db_session: Session
    ):
        """Test is_delivery_failed returns True for UNDELIVERED status"""
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.UNDELIVERED,
        )
        db_session.add(message)
        db_session.commit()

        assert message.is_delivery_failed() is True

    def test_is_delivery_failed_with_success_status(self, db_session: Session):
        """Test is_delivery_failed returns False for successful delivery"""
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.DELIVERED,
        )
        db_session.add(message)
        db_session.commit()

        assert message.is_delivery_failed() is False

    def test_can_retry_with_pending_status_and_low_retry_count(
        self, db_session: Session
    ):
        """
        Test can_retry returns True for PENDING status with low retry count
        """
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.PENDING,
            retry_count=1,
        )
        db_session.add(message)
        db_session.commit()

        assert message.can_retry(max_retries=3) is True

    def test_can_retry_with_failed_status_and_low_retry_count(
        self, db_session: Session
    ):
        """
        Test can_retry returns True for FAILED status with low retry count
        """
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=2,
        )
        db_session.add(message)
        db_session.commit()

        assert message.can_retry(max_retries=3) is True

    def test_can_retry_with_max_retries_exceeded(self, db_session: Session):
        """Test can_retry returns False when max retries exceeded"""
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=3,
        )
        db_session.add(message)
        db_session.commit()

        assert message.can_retry(max_retries=3) is False

    def test_can_retry_with_delivered_status(self, db_session: Session):
        """Test can_retry returns False for already delivered message"""
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.DELIVERED,
            retry_count=0,
        )
        db_session.add(message)
        db_session.commit()

        assert message.can_retry(max_retries=3) is False


class TestCustomerLastMessageTracking:
    """Test customer last_message tracking for 24-hour reconnection logic"""

    def test_customer_with_no_last_message(self, db_session: Session):
        """Test customer with no last_message tracking"""
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        assert customer.last_message_at is None
        assert customer.last_message_from is None

    def test_customer_with_last_message_from_llm(self, db_session: Session):
        """Test customer with last message from LLM"""
        customer = Customer(
            phone_number="+255123456789",
            last_message_at=datetime.now(timezone.utc),
            last_message_from=MessageFrom.LLM,
        )
        db_session.add(customer)
        db_session.commit()

        assert customer.last_message_from == MessageFrom.LLM
        assert customer.last_message_at is not None

    def test_customer_with_last_message_from_customer(
        self, db_session: Session
    ):
        """Test customer with last message from customer"""
        customer = Customer(
            phone_number="+255123456789",
            last_message_at=datetime.now(timezone.utc),
            last_message_from=MessageFrom.CUSTOMER,
        )
        db_session.add(customer)
        db_session.commit()

        assert customer.last_message_from == MessageFrom.CUSTOMER


class TestCustomerReconnectionLogic:
    """Test customer needs_reconnection_template method"""

    def test_needs_reconnection_with_old_outgoing_message(
        self, db_session: Session
    ):
        """
        Test reconnection needed when last message from us is > 24 hours old
        """
        customer = Customer(
            phone_number="+255123456789",
            last_message_at=datetime.now(timezone.utc) - timedelta(hours=25),
            last_message_from=MessageFrom.LLM,
        )
        db_session.add(customer)
        db_session.commit()

        assert customer.needs_reconnection_template(threshold_hours=24) is True

    def test_needs_reconnection_with_old_user_message(
        self, db_session: Session
    ):
        """
        Test reconnection needed when last message from USER is > 24 hours old
        """
        customer = Customer(
            phone_number="+255123456789",
            last_message_at=datetime.now(timezone.utc) - timedelta(hours=30),
            last_message_from=MessageFrom.USER,
        )
        db_session.add(customer)
        db_session.commit()

        assert customer.needs_reconnection_template(threshold_hours=24) is True

    def test_no_reconnection_with_recent_message(self, db_session: Session):
        """Test reconnection NOT needed when last message is recent"""
        customer = Customer(
            phone_number="+255123456789",
            last_message_at=datetime.now(timezone.utc) - timedelta(hours=1),
            last_message_from=MessageFrom.LLM,
        )
        db_session.add(customer)
        db_session.commit()

        assert (
            customer.needs_reconnection_template(threshold_hours=24) is False
        )

    def test_no_reconnection_when_customer_sent_last(
        self, db_session: Session
    ):
        """Test reconnection NOT needed when customer sent last message"""
        customer = Customer(
            phone_number="+255123456789",
            last_message_at=datetime.now(timezone.utc) - timedelta(hours=30),
            last_message_from=MessageFrom.CUSTOMER,
        )
        db_session.add(customer)
        db_session.commit()

        # No reconnection needed because customer sent the last message
        # (we're waiting for their response, not them for ours)
        assert (
            customer.needs_reconnection_template(threshold_hours=24) is False
        )

    def test_no_reconnection_with_no_tracking_data(self, db_session: Session):
        """Test reconnection NOT needed when no tracking data exists"""
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        assert (
            customer.needs_reconnection_template(threshold_hours=24) is False
        )

    def test_reconnection_with_custom_threshold(self, db_session: Session):
        """Test reconnection logic with custom threshold"""
        customer = Customer(
            phone_number="+255123456789",
            last_message_at=datetime.now(timezone.utc) - timedelta(hours=10),
            last_message_from=MessageFrom.LLM,
        )
        db_session.add(customer)
        db_session.commit()

        # Should need reconnection with 8-hour threshold
        assert customer.needs_reconnection_template(threshold_hours=8) is True

        # Should NOT need reconnection with 12-hour threshold
        assert (
            customer.needs_reconnection_template(threshold_hours=12) is False
        )

    def test_reconnection_at_exact_threshold(self, db_session: Session):
        """Test reconnection logic at exact threshold boundary"""
        customer = Customer(
            phone_number="+255123456789",
            last_message_at=datetime.now(timezone.utc)
            - timedelta(hours=24, seconds=1),
            last_message_from=MessageFrom.LLM,
        )
        db_session.add(customer)
        db_session.commit()

        # Should need reconnection when just over threshold
        assert customer.needs_reconnection_template(threshold_hours=24) is True


class TestDeliveryTrackingIntegration:
    """Integration tests for delivery tracking with messages and customers"""

    def test_message_and_customer_tracking_together(self, db_session: Session):
        """Test that message delivery and customer tracking work together"""
        customer = Customer(
            phone_number="+255123456789",
            last_message_at=datetime.now(timezone.utc),
            last_message_from=MessageFrom.LLM,
        )
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM12345678",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.DELIVERED,
            delivered_at=datetime.now(timezone.utc),
        )
        db_session.add(message)
        db_session.commit()

        # Verify both customer and message have tracking data
        assert customer.last_message_at is not None
        assert customer.last_message_from == MessageFrom.LLM
        assert message.delivery_status == DeliveryStatus.DELIVERED
        assert message.delivered_at is not None

    def test_query_messages_by_delivery_status(self, db_session: Session):
        """Test querying messages by delivery status"""
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        # Create messages with different statuses
        msg1 = Message(
            message_sid="SM1",
            customer_id=customer.id,
            body="Message 1",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.PENDING,
        )
        msg2 = Message(
            message_sid="SM2",
            customer_id=customer.id,
            body="Message 2",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.DELIVERED,
        )
        msg3 = Message(
            message_sid="SM3",
            customer_id=customer.id,
            body="Message 3",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
        )
        db_session.add_all([msg1, msg2, msg3])
        db_session.commit()

        # Query messages by status
        pending = (
            db_session.query(Message)
            .filter(Message.delivery_status == DeliveryStatus.PENDING)
            .all()
        )
        delivered = (
            db_session.query(Message)
            .filter(Message.delivery_status == DeliveryStatus.DELIVERED)
            .all()
        )
        failed = (
            db_session.query(Message)
            .filter(Message.delivery_status == DeliveryStatus.FAILED)
            .all()
        )

        assert len(pending) == 1
        assert len(delivered) == 1
        assert len(failed) == 1
        assert pending[0].message_sid == "SM1"
        assert delivered[0].message_sid == "SM2"
        assert failed[0].message_sid == "SM3"

    def test_query_retryable_messages(self, db_session: Session):
        """Test querying messages that can be retried"""
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        # Create messages with different retry counts
        msg1 = Message(
            message_sid="SM1",
            customer_id=customer.id,
            body="Message 1",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=1,
        )
        msg2 = Message(
            message_sid="SM2",
            customer_id=customer.id,
            body="Message 2",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.FAILED,
            retry_count=3,  # Max retries reached
        )
        msg3 = Message(
            message_sid="SM3",
            customer_id=customer.id,
            body="Message 3",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.DELIVERED,
            retry_count=0,
        )
        db_session.add_all([msg1, msg2, msg3])
        db_session.commit()

        # Find retryable messages (FAILED or PENDING with retry_count < 3)
        retryable = (
            db_session.query(Message)
            .filter(
                Message.delivery_status.in_(
                    [DeliveryStatus.FAILED, DeliveryStatus.PENDING]
                ),
                Message.retry_count < 3,
            )
            .all()
        )

        assert len(retryable) == 1
        assert retryable[0].message_sid == "SM1"
        assert retryable[0].can_retry(max_retries=3) is True
