"""
Unit tests for enhanced WhatsApp service features

Tests the new delivery tracking and phone validation features:
- Phone number validation
- send_message_with_tracking
- Twilio status mapping
- Error handling with TwilioRestException
- Message status updates in database
"""

import pytest
from unittest.mock import Mock, patch
from twilio.base.exceptions import TwilioRestException
from sqlalchemy.orm import Session

from services.whatsapp_service import WhatsAppService
from models.customer import Customer
from models.message import Message, MessageFrom, DeliveryStatus


class TestPhoneNumberValidation:
    """Test phone number validation"""

    def test_validate_valid_phone_e164(self):
        """Test validation of valid E.164 format phone"""
        valid_numbers = [
            ("+255712345678", "+255712345678"),
            ("+14155552671", "+14155552671"),
            ("+442071838750", "+442071838750"),
        ]

        for input_num, expected in valid_numbers:
            result = WhatsAppService.validate_and_format_phone_number(
                input_num
            )
            assert result == expected

    def test_validate_phone_without_plus(self):
        """Test validation of phone without + prefix"""
        result = WhatsAppService.validate_and_format_phone_number(
            "255712345678"
        )
        assert result == "+255712345678"

    def test_validate_phone_with_whatsapp_prefix(self):
        """Test validation removes whatsapp: prefix"""
        result = WhatsAppService.validate_and_format_phone_number(
            "whatsapp:+255712345678"
        )
        assert result == "+255712345678"
        assert "whatsapp:" not in result

    def test_validate_invalid_phone_too_short(self):
        """Test that too short numbers are rejected"""
        with pytest.raises(ValueError, match="Invalid phone number"):
            WhatsAppService.validate_and_format_phone_number("123")

    def test_validate_invalid_phone_not_numeric(self):
        """Test that non-numeric strings are rejected"""
        with pytest.raises(ValueError, match="Cannot parse phone number"):
            WhatsAppService.validate_and_format_phone_number("invalid")

    def test_validate_invalid_phone_all_zeros(self):
        """Test that all zeros are rejected"""
        with pytest.raises(ValueError):
            WhatsAppService.validate_and_format_phone_number("00000000000")


class TestTwilioStatusMapping:
    """Test Twilio status to DeliveryStatus mapping"""

    def test_map_twilio_status_queued(self):
        """Test mapping queued status"""
        service = WhatsAppService()
        result = service._map_twilio_status("queued")
        assert result == "QUEUED"

    def test_map_twilio_status_sent(self):
        """Test mapping sent status"""
        service = WhatsAppService()
        result = service._map_twilio_status("sent")
        assert result == "SENT"

    def test_map_twilio_status_delivered(self):
        """Test mapping delivered status"""
        service = WhatsAppService()
        result = service._map_twilio_status("delivered")
        assert result == "DELIVERED"

    def test_map_twilio_status_failed(self):
        """Test mapping failed status"""
        service = WhatsAppService()
        result = service._map_twilio_status("failed")
        assert result == "FAILED"

    def test_map_twilio_status_unknown(self):
        """Test mapping unknown status defaults to PENDING"""
        service = WhatsAppService()
        result = service._map_twilio_status("unknown_status")
        assert result == "PENDING"

    def test_map_twilio_status_case_insensitive(self):
        """Test that status mapping is case insensitive"""
        service = WhatsAppService()
        assert service._map_twilio_status("SENT") == "SENT"
        assert service._map_twilio_status("Sent") == "SENT"
        assert service._map_twilio_status("sent") == "SENT"


class TestSendMessageWithTracking:
    """Test send_message_with_tracking method"""

    def test_send_message_with_tracking_success(self, db_session: Session):
        """Test successful message sending with tracking"""
        # Create customer and message
        customer = Customer(phone_number="+255712345678")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="pending_123",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.PENDING,
        )
        db_session.add(message)
        db_session.commit()

        # Test with testing mode (mock)
        service = WhatsAppService()
        result = service.send_message_with_tracking(
            to_number="+255712345678",
            message_body="Test message",
            message_id=message.id,
            db=db_session,
        )

        assert result["sid"].startswith("MOCK_SID_")
        assert result["status"] == "sent"
        assert result["error_code"] is None

    def test_send_message_with_tracking_invalid_phone(
        self, db_session: Session
    ):
        """Test send message with invalid phone number"""
        # Create customer and message
        customer = Customer(phone_number="+255712345678")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="pending_123",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.PENDING,
        )
        db_session.add(message)
        db_session.commit()

        service = WhatsAppService()

        # Should raise ValueError for invalid phone
        with pytest.raises(ValueError, match="Invalid phone number"):
            service.send_message_with_tracking(
                to_number="123",
                message_body="Test message",
                message_id=message.id,
                db=db_session,
            )

        # Verify message status was updated to FAILED
        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.FAILED
        assert message.twilio_error_code == "INVALID"

    @patch.dict(
        "os.environ",
        {
            "TESTING": "false",
            "TWILIO_ACCOUNT_SID": "test_account_sid",
            "TWILIO_AUTH_TOKEN": "test_auth_token",
        },
    )
    @patch("services.whatsapp_service.Client")
    def test_send_message_with_tracking_twilio_error(
        self, mock_client_class, db_session: Session
    ):
        """Test handling of Twilio API errors"""
        # Setup mock to raise Twilio exception
        mock_client = Mock()
        mock_client.messages.create.side_effect = TwilioRestException(
            status=400,
            uri="/Messages/SM123",
            msg="Invalid To number",
            code=21211,
        )
        mock_client_class.return_value = mock_client

        # Create customer and message
        customer = Customer(phone_number="+255712345678")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="pending_123",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.PENDING,
        )
        db_session.add(message)
        db_session.commit()

        # Create service in production mode (mocked)
        service = WhatsAppService()

        # Should raise TwilioRestException
        with pytest.raises(TwilioRestException) as exc_info:
            service.send_message_with_tracking(
                to_number="+255712345678",
                message_body="Test message",
                message_id=message.id,
                db=db_session,
            )

        assert exc_info.value.code == 21211

        # Verify message status was updated
        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.FAILED
        assert message.twilio_error_code == "21211"
        assert "Invalid To number" in message.twilio_error_message

    def test_send_message_without_db_tracking(self):
        """Test sending message without database tracking"""
        service = WhatsAppService()

        # Should work without message_id and db
        result = service.send_message_with_tracking(
            to_number="+255712345678",
            message_body="Test message",
        )

        assert result["sid"].startswith("MOCK_SID_")
        assert result["status"] == "sent"


class TestUpdateMessageStatus:
    """Test _update_message_status helper method"""

    def test_update_message_status_to_sent(self, db_session: Session):
        """Test updating message status to SENT"""
        # Create customer and message
        customer = Customer(phone_number="+255712345678")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="pending_123",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.PENDING,
        )
        db_session.add(message)
        db_session.commit()

        service = WhatsAppService()
        service._update_message_status(
            db=db_session,
            message_id=message.id,
            delivery_status="SENT",
            message_sid="SM12345678",
        )

        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.SENT
        assert message.message_sid == "SM12345678"

    def test_update_message_status_with_error(self, db_session: Session):
        """Test updating message status with error details"""
        # Create customer and message
        customer = Customer(phone_number="+255712345678")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="pending_123",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.PENDING,
        )
        db_session.add(message)
        db_session.commit()

        service = WhatsAppService()
        service._update_message_status(
            db=db_session,
            message_id=message.id,
            delivery_status="FAILED",
            error_code="21211",
            error_message="Invalid phone number",
        )

        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.FAILED
        assert message.twilio_error_code == "21211"
        assert message.twilio_error_message == "Invalid phone number"

    def test_update_nonexistent_message(self, db_session: Session):
        """Test updating non-existent message doesn't crash"""
        service = WhatsAppService()

        # Should not raise error for non-existent message
        service._update_message_status(
            db=db_session,
            message_id=99999,
            delivery_status="SENT",
        )

    def test_update_message_status_with_delivered_timestamp(
        self, db_session: Session
    ):
        """Test that delivered status sets delivered_at timestamp"""
        # Create customer and message
        customer = Customer(phone_number="+255712345678")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="pending_123",
            customer_id=customer.id,
            body="Test message",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.SENT,
        )
        db_session.add(message)
        db_session.commit()

        assert message.delivered_at is None

        service = WhatsAppService()
        service._update_message_status(
            db=db_session,
            message_id=message.id,
            delivery_status="DELIVERED",
        )

        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.DELIVERED
        assert message.delivered_at is not None


class TestWhatsAppServiceIntegration:
    """Integration tests for enhanced WhatsApp service"""

    def test_full_message_send_flow(self, db_session: Session):
        """Test complete message sending flow with tracking"""
        # Create customer
        customer = Customer(phone_number="+255712345678")
        db_session.add(customer)
        db_session.commit()

        # Create pending message
        message = Message(
            message_sid="pending_ai_123",
            customer_id=customer.id,
            body="AI response here",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.PENDING,
            retry_count=0,
        )
        db_session.add(message)
        db_session.commit()

        # Send with tracking
        service = WhatsAppService()
        result = service.send_message_with_tracking(
            to_number=customer.phone_number,
            message_body=message.body,
            message_id=message.id,
            db=db_session,
        )

        # Verify result
        assert result["sid"] is not None
        assert result["status"] == "sent"
        assert result["error_code"] is None

        # Verify message was updated in database
        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.SENT
        assert message.message_sid != "pending_ai_123"

    def test_phone_validation_prevents_invalid_send(self, db_session: Session):
        """Test that phone validation prevents sending to invalid numbers"""
        # Create customer with INVALID phone
        customer = Customer(phone_number="invalid")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="pending_123",
            customer_id=customer.id,
            body="Test",
            from_source=MessageFrom.LLM,
            delivery_status=DeliveryStatus.PENDING,
        )
        db_session.add(message)
        db_session.commit()

        service = WhatsAppService()

        # Should raise ValueError before attempting Twilio send
        with pytest.raises(ValueError):
            service.send_message_with_tracking(
                to_number="invalid",
                message_body="Test",
                message_id=message.id,
                db=db_session,
            )

        # Message should be marked as FAILED
        db_session.refresh(message)
        assert message.delivery_status == DeliveryStatus.FAILED
        assert message.twilio_error_code == "INVALID"
