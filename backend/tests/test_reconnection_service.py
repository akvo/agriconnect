"""
Unit tests for ReconnectionService (24-hour reconnection logic)

Tests the implementation of issue #141 from rag-doll:
- Detecting 24+ hour inactivity
- Sending reconnection templates
- Updating last_message tracking
- Integration with customer and message models
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from sqlalchemy.orm import Session

from models.customer import Customer
from models.message import Message, MessageFrom
from services.reconnection_service import ReconnectionService
from config import settings


class TestReconnectionDetection:
    """Test reconnection template detection logic"""

    def test_no_reconnection_needed_for_recent_activity(
        self, db_session: Session
    ):
        """Test that recent activity doesn't trigger reconnection"""
        # Create customer with recent last message
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
            last_message_at=datetime.now(timezone.utc) - timedelta(hours=1),
            last_message_from=MessageFrom.LLM,
        )
        db_session.add(customer)
        db_session.commit()

        service = ReconnectionService(db_session)
        result = service.check_and_send_reconnection(customer, "Hello")

        # Should NOT send reconnection (too recent)
        assert result is False

    def test_reconnection_needed_after_24_hours(self, db_session: Session):
        """Test that 24+ hour inactivity triggers reconnection"""
        # Create customer with old last message
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
            last_message_at=datetime.now(timezone.utc) - timedelta(hours=25),
            last_message_from=MessageFrom.LLM,  # Last message FROM us
        )
        db_session.add(customer)
        db_session.commit()

        service = ReconnectionService(db_session)

        # Mock WhatsAppService to avoid real API calls
        with patch.object(
            service.whatsapp_service, "send_template_message"
        ) as mock_send:
            mock_send.return_value = {
                "sid": "SM_RECONNECT_123",
                "status": "sent",
            }

            # Template SID must be configured for reconnection to work
            original_sid = settings.whatsapp_reconnection_template_sid
            settings.whatsapp_reconnection_template_sid = (
                "HX_RECONNECT_TEMPLATE"
            )

            try:
                result = service.check_and_send_reconnection(
                    customer, "I have a question"
                )

                # Should send reconnection
                assert result is True
                assert mock_send.called

                # Verify template was sent with message preview
                call_args = mock_send.call_args
                assert call_args[1]["to"] == "+255712345678"
                assert (
                    "I have a question"
                    in call_args[1]["content_variables"]["1"]
                )

            finally:
                settings.whatsapp_reconnection_template_sid = original_sid

    def test_no_reconnection_when_customer_sent_last(
        self, db_session: Session
    ):
        """Test that reconnection NOT needed when customer sent last message"""
        # Create customer where CUSTOMER sent last message
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
            last_message_at=datetime.now(timezone.utc) - timedelta(hours=30),
            last_message_from=MessageFrom.CUSTOMER,  # Customer sent last
        )
        db_session.add(customer)
        db_session.commit()

        service = ReconnectionService(db_session)
        result = service.check_and_send_reconnection(customer, "Hello")

        # Should NOT send reconnection
        # (customer sent last, we're waiting for them)
        assert result is False

    def test_no_reconnection_when_template_sid_not_configured(
        self, db_session: Session
    ):
        """Test that reconnection fails gracefully when template SID not set"""
        # Create customer needing reconnection
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
            last_message_at=datetime.now(timezone.utc) - timedelta(hours=30),
            last_message_from=MessageFrom.LLM,
        )
        db_session.add(customer)
        db_session.commit()

        service = ReconnectionService(db_session)

        # Ensure template SID is empty
        original_sid = settings.whatsapp_reconnection_template_sid
        settings.whatsapp_reconnection_template_sid = ""

        try:
            result = service.check_and_send_reconnection(customer, "Hello")

            # Should NOT send (template not configured)
            assert result is False

        finally:
            settings.whatsapp_reconnection_template_sid = original_sid


class TestReconnectionMessageCreation:
    """Test reconnection message creation and tracking"""

    def test_reconnection_not_creates_message_in_database(
        self, db_session: Session
    ):
        """Test that reconnection template does NOT create a message record"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
            last_message_at=datetime.now(timezone.utc) - timedelta(hours=30),
            last_message_from=MessageFrom.LLM,
        )
        db_session.add(customer)
        db_session.commit()

        service = ReconnectionService(db_session)

        with patch.object(
            service.whatsapp_service, "send_template_message"
        ) as mock_send:
            mock_send.return_value = {
                "sid": "SM_RECONNECT_456",
                "status": "sent",
            }

            original_sid = settings.whatsapp_reconnection_template_sid
            settings.whatsapp_reconnection_template_sid = "HX_RECONNECT"

            try:
                result = service.check_and_send_reconnection(
                    customer, "Need help"
                )

                assert result is True

                # Verify message was created
                messages = (
                    db_session.query(Message)
                    .filter(
                        Message.customer_id == customer.id,
                        Message.from_source == MessageFrom.USER,
                    )
                    .all()
                )

                assert len(messages) == 0

            finally:
                settings.whatsapp_reconnection_template_sid = original_sid

    def test_reconnection_updates_customer_last_message(
        self, db_session: Session
    ):
        """Test that reconnection updates customer's last_message tracking"""
        old_time = datetime.now(timezone.utc) - timedelta(hours=30)
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
            last_message_at=old_time,
            last_message_from=MessageFrom.LLM,
        )
        db_session.add(customer)
        db_session.commit()

        service = ReconnectionService(db_session)

        with patch.object(
            service.whatsapp_service, "send_template_message"
        ) as mock_send:
            mock_send.return_value = {
                "sid": "SM_RECONNECT_789",
                "status": "sent",
            }

            original_sid = settings.whatsapp_reconnection_template_sid
            settings.whatsapp_reconnection_template_sid = "HX_RECONNECT"

            try:
                service.check_and_send_reconnection(customer, "Question here")

                # Refresh customer
                db_session.refresh(customer)

                # Verify last_message was updated
                assert customer.last_message_at > old_time
                assert customer.last_message_from == MessageFrom.USER

            finally:
                settings.whatsapp_reconnection_template_sid = original_sid


class TestUpdateLastMessage:
    """Test update_customer_last_message method"""

    def test_update_last_message_from_customer(self, db_session: Session):
        """Test updating last_message when customer sends message"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        assert customer.last_message_at is None
        assert customer.last_message_from is None

        service = ReconnectionService(db_session)
        service.update_customer_last_message(
            customer_id=customer.id, from_source=MessageFrom.CUSTOMER
        )

        db_session.refresh(customer)

        assert customer.last_message_at is not None
        assert customer.last_message_from == MessageFrom.CUSTOMER

    def test_update_last_message_from_llm(self, db_session: Session):
        """Test updating last_message when LLM sends message"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
        )
        db_session.add(customer)
        db_session.commit()

        service = ReconnectionService(db_session)
        service.update_customer_last_message(
            customer_id=customer.id, from_source=MessageFrom.LLM
        )

        db_session.refresh(customer)

        assert customer.last_message_at is not None
        assert customer.last_message_from == MessageFrom.LLM

    def test_update_last_message_for_nonexistent_customer(
        self, db_session: Session
    ):
        """Test that updating non-existent customer doesn't crash"""
        service = ReconnectionService(db_session)

        # Should not raise error
        service.update_customer_last_message(
            customer_id=99999, from_source=MessageFrom.CUSTOMER
        )


class TestReconnectionThreshold:
    """Test custom reconnection threshold settings"""

    def test_custom_threshold_from_config(self, db_session: Session):
        """Test that threshold can be configured"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
            last_message_at=datetime.now(timezone.utc) - timedelta(hours=10),
            last_message_from=MessageFrom.LLM,
        )
        db_session.add(customer)
        db_session.commit()

        # With default 24h threshold, should NOT need reconnection
        service = ReconnectionService(db_session)
        assert service.threshold_hours == 24
        result = service.check_and_send_reconnection(customer, "Hello")
        assert result is False

        # Change threshold to 8 hours
        original_threshold = settings.whatsapp_reconnection_threshold_hours
        settings.whatsapp_reconnection_threshold_hours = 8

        try:
            service = ReconnectionService(db_session)
            assert service.threshold_hours == 8

            with patch.object(
                service.whatsapp_service, "send_template_message"
            ) as mock_send:
                mock_send.return_value = {"sid": "SM_TEST", "status": "sent"}

                original_sid = settings.whatsapp_reconnection_template_sid
                settings.whatsapp_reconnection_template_sid = "HX_TEST"

                try:
                    # With 8h threshold, should need reconnection
                    result = service.check_and_send_reconnection(
                        customer, "Hello"
                    )
                    assert result is True

                finally:
                    settings.whatsapp_reconnection_template_sid = original_sid

        finally:
            settings.whatsapp_reconnection_threshold_hours = original_threshold


class TestReconnectionErrorHandling:
    """Test error handling in reconnection service"""

    def test_reconnection_rollback_on_twilio_error(self, db_session: Session):
        """Test that reconnection rolls back on Twilio error"""
        customer = Customer(
            phone_number="+255712345678",
            full_name="Test Farmer",
            last_message_at=datetime.now(timezone.utc) - timedelta(hours=30),
            last_message_from=MessageFrom.LLM,
        )
        db_session.add(customer)
        db_session.commit()

        original_last_message = customer.last_message_at

        service = ReconnectionService(db_session)

        # Mock Twilio to raise exception
        with patch.object(
            service.whatsapp_service, "send_template_message"
        ) as mock_send:
            mock_send.side_effect = Exception("Twilio API error")

            original_sid = settings.whatsapp_reconnection_template_sid
            settings.whatsapp_reconnection_template_sid = "HX_TEST"

            try:
                result = service.check_and_send_reconnection(customer, "Hello")

                # Should return False on error
                assert result is False

                # Verify no message was created
                messages = (
                    db_session.query(Message)
                    .filter(Message.customer_id == customer.id)
                    .count()
                )
                assert messages == 0

                # Verify customer last_message was NOT updated
                db_session.refresh(customer)
                assert customer.last_message_at == original_last_message

            finally:
                settings.whatsapp_reconnection_template_sid = original_sid
