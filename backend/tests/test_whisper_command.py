"""
Unit tests for the whisper command module.

Tests the whisper.py command functions for:
- Getting customer/ticket information
- Sending AI callback webhooks
- Creating service tokens for testing
"""

import pytest
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from models.customer import Customer, CustomerLanguage
from models.message import Message, MessageFrom
from models.ticket import Ticket
from models.administrative import Administrative, AdministrativeLevel
from scripts.whisper import (
    get_customer_ticket_info,
    send_callback,
    suggestions,
)


@pytest.fixture
def test_administrative(db_session: Session):
    """Create a test administrative area"""
    # Create administrative level first
    level = AdministrativeLevel(name="District")
    db_session.add(level)
    db_session.commit()
    db_session.refresh(level)

    # Create administrative area
    admin = Administrative(
        code="TST001",
        name="Test District",
        level_id=level.id,
        path="/TST001",
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def test_customer(db_session: Session, test_administrative):
    """Create a test customer"""
    from models.administrative import CustomerAdministrative

    customer = Customer(
        phone_number="+255123456789",
        language=CustomerLanguage.EN,
        full_name="Test Customer",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    # Link customer to administrative area
    customer_admin = CustomerAdministrative(
        customer_id=customer.id,
        administrative_id=test_administrative.id,
    )
    db_session.add(customer_admin)
    db_session.commit()

    return customer


@pytest.fixture
def test_ticket(db_session: Session, test_customer, test_administrative):
    """Create a test ticket with an initial message"""
    # Create initial message
    message = Message(
        message_sid="test_msg_001",
        customer_id=test_customer.id,
        body="Hello, I need help with my maize crop",
        from_source=MessageFrom.CUSTOMER,
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)

    # Create ticket
    ticket = Ticket(
        ticket_number="20251022001",
        customer_id=test_customer.id,
        administrative_id=test_administrative.id,
        message_id=message.id,
    )
    db_session.add(ticket)
    db_session.commit()
    db_session.refresh(ticket)

    return ticket, message


class TestGetCustomerTicketInfo:
    """Tests for get_customer_ticket_info function"""

    def test_get_customer_ticket_info_success(
        self, db_session: Session, test_customer, test_ticket
    ):
        """Test retrieving customer, ticket, and message info successfully"""
        ticket, message = test_ticket

        result = get_customer_ticket_info(
            db_session, test_customer.phone_number
        )

        assert result is not None
        assert result["customer"].id == test_customer.id
        assert result["ticket"].id == ticket.id
        assert result["message"].id == message.id
        assert result["customer"].phone_number == test_customer.phone_number

    def test_get_customer_ticket_info_customer_not_found(
        self, db_session: Session
    ):
        """Test with non-existent customer phone number"""
        result = get_customer_ticket_info(db_session, "+999999999999")

        assert result is None

    def test_get_customer_ticket_info_no_open_ticket(
        self, db_session: Session, test_customer, test_ticket
    ):
        """Test customer with resolved ticket (no open ticket)"""
        ticket, _ = test_ticket

        # Resolve the ticket
        from datetime import datetime, timezone
        ticket.resolved_at = datetime.now(timezone.utc)
        db_session.commit()

        result = get_customer_ticket_info(
            db_session, test_customer.phone_number
        )

        assert result is not None
        assert result["customer"].id == test_customer.id
        assert result["ticket"] is None
        assert result["message"] is None

    def test_get_customer_ticket_info_multiple_tickets(
        self,
        db_session: Session,
        test_customer,
        test_ticket,
        test_administrative,
    ):
        """Test returns most recent open ticket when multiple exist"""
        ticket1, message1 = test_ticket

        # Create a second, newer message and ticket
        message2 = Message(
            message_sid="test_msg_002",
            customer_id=test_customer.id,
            body="Another question about rice",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(message2)
        db_session.commit()
        db_session.refresh(message2)

        ticket2 = Ticket(
            ticket_number="20251022002",
            customer_id=test_customer.id,
            administrative_id=test_administrative.id,
            message_id=message2.id,
        )
        db_session.add(ticket2)
        db_session.commit()
        db_session.refresh(ticket2)

        result = get_customer_ticket_info(
            db_session, test_customer.phone_number
        )

        # Should return the most recent ticket (ticket2)
        assert result is not None
        assert result["ticket"].id == ticket2.id
        assert result["message"].id == message2.id


class TestSendCallback:
    """Tests for send_callback function"""

    @patch("scripts.whisper.requests.post")
    def test_send_callback_success_done_stage(
        self, mock_post, test_ticket
    ):
        """Test successful callback with 'done' stage"""
        ticket, message = test_ticket
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "received",
            "job_id": "test_job_123"
        }
        mock_post.return_value = mock_response

        result = send_callback(
            ticket_id=ticket.id,
            message_id=message.id,
            status="completed",
            suggestion_key="maize",
            base_url="http://localhost:8000",
        )

        assert result is True
        mock_post.assert_called_once()

        # Verify the call arguments
        # requests.post(url, json=payload, headers=headers)
        # url is positional (args[0]), json and headers are kwargs
        call_args = mock_post.call_args
        expected_url = "http://localhost:8000/api/callback/ai"
        assert call_args.args[0] == expected_url
        content_type = call_args.kwargs["headers"]["Content-Type"]
        assert content_type == "application/json"

        # Verify payload structure
        payload = call_args.kwargs["json"]
        assert payload["status"] == "completed"
        assert payload["job"] == "chat"
        assert payload["callback_params"]["ticket_id"] == ticket.id
        assert payload["callback_params"]["message_id"] == message.id
        assert payload["callback_params"]["message_type"] == 2  # WHISPER
        assert "output" in payload
        assert "answer" in payload["output"]
        assert "citations" in payload["output"]

    @patch("scripts.whisper.requests.post")
    def test_send_callback_success_failed_stage(
        self, mock_post, test_ticket
    ):
        """Test callback with 'failed' stage (no result)"""
        ticket, message = test_ticket
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "received",
            "job_id": "test_job_456"
        }
        mock_post.return_value = mock_response

        result = send_callback(
            ticket_id=ticket.id,
            message_id=message.id,
            status="failed",
            suggestion_key="rice",
            base_url="http://localhost:8000",
        )

        assert result is True

        # Verify payload doesn't include result for failed stage
        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        assert payload["status"] == "failed"
        assert "output" not in payload

    @patch("scripts.whisper.requests.post")
    def test_send_callback_with_different_suggestions(
        self, mock_post, test_ticket
    ):
        """Test callback with different crop suggestion types"""
        ticket, message = test_ticket
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "received"}
        mock_post.return_value = mock_response

        # Test with each crop type
        for crop_type in suggestions.keys():
            result = send_callback(
                ticket_id=ticket.id,
                message_id=message.id,
                status="completed",
                suggestion_key=crop_type,
                base_url="http://localhost:8000",
            )
            assert result is True

            # Verify suggestion text is from the correct crop type
            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]
            assert payload["output"]["answer"] in suggestions[crop_type]

    @patch("scripts.whisper.requests.post")
    def test_send_callback_request_failure(self, mock_post, test_ticket):
        """Test callback when request fails"""
        from requests.exceptions import RequestException

        ticket, message = test_ticket
        mock_post.side_effect = RequestException("Connection error")

        result = send_callback(
            ticket_id=ticket.id,
            message_id=message.id,
            status="completed",
            suggestion_key="chilli",
            base_url="http://localhost:8000",
        )

        assert result is False

    @patch("scripts.whisper.requests.post")
    def test_send_callback_http_error(self, mock_post, test_ticket):
        """Test callback when HTTP error occurs"""
        from requests.exceptions import HTTPError

        ticket, message = test_ticket
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = HTTPError()

        mock_post.return_value = mock_response

        result = send_callback(
            ticket_id=ticket.id,
            message_id=message.id,
            status="completed",
            suggestion_key="coffee",
            base_url="http://localhost:8000",
        )

        assert result is False

    @patch("scripts.whisper.requests.post")
    def test_send_callback_with_unknown_crop_type(
        self, mock_post, test_ticket
    ):
        """Test callback with unknown crop type (should fallback to maize)"""
        ticket, message = test_ticket
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "received"}
        mock_post.return_value = mock_response

        result = send_callback(
            ticket_id=ticket.id,
            message_id=message.id,
            status="completed",
            suggestion_key="unknown_crop",
            base_url="http://localhost:8000",
        )

        assert result is True

        # Verify suggestion falls back to maize
        call_args = mock_post.call_args
        payload = call_args.kwargs["json"]
        assert payload["output"]["answer"] in suggestions["maize"]


class TestSuggestions:
    """Tests for the suggestions dictionary"""

    def test_suggestions_structure(self):
        """Test that suggestions dictionary has correct structure"""
        assert isinstance(suggestions, dict)
        assert len(suggestions) > 0

        for crop_type, suggestion_list in suggestions.items():
            assert isinstance(crop_type, str)
            assert isinstance(suggestion_list, list)
            assert len(suggestion_list) > 0
            for suggestion in suggestion_list:
                assert isinstance(suggestion, str)
                assert len(suggestion) > 0

    def test_all_crop_types_present(self):
        """Test that all expected crop types are present"""
        expected_crops = ["rice", "chilli", "coffee", "maize", "tomato"]

        for crop in expected_crops:
            assert crop in suggestions
            assert len(suggestions[crop]) >= 1
