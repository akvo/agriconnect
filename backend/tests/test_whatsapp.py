from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.customer import Customer, CustomerLanguage
from models.message import Message, MessageFrom
from models.ticket import Ticket
from models.administrative import Administrative
from seeder.administrative import seed_administrative_data


class TestWhatsAppWebhook:
    def test_webhook_new_customer_english(
        self, client: TestClient, db_session: Session
    ):
        with patch("routers.whatsapp.WhatsAppService") as mock_whatsapp:
            mock_service = Mock()
            mock_whatsapp.return_value = mock_service

            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+255123456789",
                    "Body": "Hello, I need farming help",
                    "MessageSid": "SM12345678",
                },
            )

            assert response.status_code == 200
            assert response.json()["status"] == "success"

            # Check customer was created
            customer = (
                db_session.query(Customer)
                .filter(Customer.phone_number == "+255123456789")
                .first()
            )
            assert customer is not None
            assert customer.language == CustomerLanguage.EN

            # Check message was stored
            message = (
                db_session.query(Message)
                .filter(Message.message_sid == "SM12345678")
                .first()
            )
            assert message is not None
            assert message.body == "Hello, I need farming help"
            assert message.from_source == MessageFrom.CUSTOMER
            assert message.customer_id == customer.id

            # Check welcome message was sent
            mock_service.send_welcome_message.assert_called_once_with(
                "+255123456789", "en"
            )

    def test_webhook_new_customer_swahili(
        self, client: TestClient, db_session: Session
    ):
        with patch("routers.whatsapp.WhatsAppService") as mock_whatsapp:
            mock_service = Mock()
            mock_whatsapp.return_value = mock_service

            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+255987654321",
                    "Body": "Hujambo, nahitaji msaada wa kilimo",
                    "MessageSid": "SM87654321",
                },
            )

            assert response.status_code == 200

            customer = (
                db_session.query(Customer)
                .filter(Customer.phone_number == "+255987654321")
                .first()
            )
            assert customer.language == CustomerLanguage.SW

            mock_service.send_welcome_message.assert_called_once_with(
                "+255987654321", "sw"
            )

    def test_webhook_existing_customer(
        self, client: TestClient, db_session: Session
    ):
        # Create existing customer
        existing_customer = Customer(
            phone_number="+255111111111", full_name="John Farmer"
        )
        db_session.add(existing_customer)
        db_session.commit()

        # Add a previous message to make them not new
        previous_message = Message(
            message_sid="SM_OLD",
            customer_id=existing_customer.id,
            body="Previous message",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(previous_message)
        db_session.commit()

        with patch("routers.whatsapp.WhatsAppService") as mock_whatsapp:
            mock_service = Mock()
            mock_whatsapp.return_value = mock_service

            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+255111111111",
                    "Body": "Another message",
                    "MessageSid": "SM_NEW",
                },
            )

            assert response.status_code == 200

            # Should not send welcome message for existing customer
            mock_service.send_welcome_message.assert_not_called()

            # Message should still be stored
            new_message = (
                db_session.query(Message)
                .filter(Message.message_sid == "SM_NEW")
                .first()
            )
            assert new_message is not None
            assert new_message.body == "Another message"

    def test_webhook_duplicate_message_sid(
        self, client: TestClient, db_session: Session
    ):
        # Create customer and message first
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()

        message = Message(
            message_sid="SM_DUPLICATE",
            customer_id=customer.id,
            body="Original message",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(message)
        db_session.commit()

        # Try to send same message_sid again
        response = client.post(
            "/api/whatsapp/webhook",
            data={
                "From": "whatsapp:+255123456789",
                "Body": "Duplicate message",
                "MessageSid": "SM_DUPLICATE",
            },
        )

        assert response.status_code == 200
        assert response.json()["message"] == "Message already processed"

        # Should still only have one message with that SID
        messages = (
            db_session.query(Message)
            .filter(Message.message_sid == "SM_DUPLICATE")
            .all()
        )
        assert len(messages) == 1
        assert messages[0].body == "Original message"  # Original unchanged

    def test_webhook_welcome_message_failure(
        self, client: TestClient, db_session: Session
    ):
        with patch("routers.whatsapp.WhatsAppService") as mock_whatsapp:
            mock_service = Mock()
            mock_service.send_welcome_message.side_effect = Exception(
                "Twilio error"
            )
            mock_whatsapp.return_value = mock_service

            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+255123456789",
                    "Body": "Hello",
                    "MessageSid": "SM12345678",
                },
            )

            # Should still succeed even if welcome message fails
            assert response.status_code == 200
            assert response.json()["status"] == "success"

            # Customer and message should still be created
            customer = db_session.query(Customer).first()
            assert customer is not None
            message = db_session.query(Message).first()
            assert message is not None

    def test_webhook_phone_number_normalization(
        self, client: TestClient, db_session: Session
    ):
        with patch("routers.whatsapp.WhatsAppService") as mock_whatsapp:
            mock_service = Mock()
            mock_whatsapp.return_value = mock_service

            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+1234567890",  # Different format
                    "Body": "Test message",
                    "MessageSid": "SM_TEST",
                },
            )

            assert response.status_code == 200

            customer = db_session.query(Customer).first()
            assert customer.phone_number == "+1234567890"  # Prefix removed

    def test_webhook_missing_fields(self, client: TestClient):
        # Test missing From field
        response = client.post(
            "/api/whatsapp/webhook",
            data={"Body": "Test message", "MessageSid": "SM_TEST"},
        )
        assert response.status_code == 422  # Validation error

        # Test missing Body field
        response = client.post(
            "/api/whatsapp/webhook",
            data={"From": "whatsapp:+255123456789", "MessageSid": "SM_TEST"},
        )
        assert response.status_code == 422

        # Test missing MessageSid field
        response = client.post(
            "/api/whatsapp/webhook",
            data={"From": "whatsapp:+255123456789", "Body": "Test message"},
        )
        assert response.status_code == 422

    def test_webhook_status_endpoint(self, client: TestClient):
        response = client.get("/api/whatsapp/status")
        assert response.status_code == 200
        assert response.json()["status"] == "WhatsApp service is running"

    def test_webhook_with_open_ticket_emits_message_created(
        self, client: TestClient, db_session: Session
    ):
        """Test emit_message_created called when customer has ticket."""

        # Seed administrative data
        rows = [
            {
                "code": "WARD1",
                "name": "Test Ward",
                "level": "Ward",
                "parent_code": "",
            }
        ]
        seed_administrative_data(db_session, rows)

        admin = (
            db_session.query(Administrative).filter_by(code="WARD1").first()
        )

        # Create customer with existing message (not a new customer)
        customer = Customer(
            phone_number="+255123456789", full_name="Jane Farmer"
        )
        db_session.add(customer)
        db_session.commit()

        # Create existing message to make customer not new
        old_message = Message(
            message_sid="SM_OLD",
            customer_id=customer.id,
            body="Old message",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(old_message)
        db_session.commit()

        # Create open ticket for this customer
        ticket = Ticket(
            ticket_number="T001",
            administrative_id=admin.id,
            customer_id=customer.id,
            message_id=old_message.id,
            resolved_at=None,
        )
        db_session.add(ticket)
        db_session.commit()

        with patch("routers.whatsapp.WhatsAppService") as mock_whatsapp, patch(
            "routers.whatsapp.emit_message_created", new_callable=AsyncMock
        ) as mock_emit:
            mock_service = Mock()
            mock_whatsapp.return_value = mock_service

            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+255123456789",
                    "Body": "New message for open ticket",
                    "MessageSid": "SM_NEW_TICKET",
                },
            )

            assert response.status_code == 200
            assert response.json()["status"] == "success"

            # Verify emit_message_created was called
            mock_emit.assert_called_once()
            call_kwargs = mock_emit.call_args.kwargs
            assert call_kwargs["ticket_id"] == ticket.id
            assert call_kwargs["customer_id"] == customer.id
            assert (
                call_kwargs["body"] == "New message for open ticket"
            )
            assert call_kwargs["kind"] == "customer"
            assert call_kwargs["ward_id"] is None

            # Welcome message should not be sent for existing customer
            mock_service.send_welcome_message.assert_not_called()

    def test_webhook_with_resolved_ticket_no_emit(
        self, client: TestClient, db_session: Session
    ):
        """Test emit_message_created NOT called for resolved ticket."""

        # Seed administrative data
        rows = [
            {
                "code": "WARD2",
                "name": "Test Ward 2",
                "level": "Ward",
                "parent_code": "",
            }
        ]
        seed_administrative_data(db_session, rows)

        admin = (
            db_session.query(Administrative).filter_by(code="WARD2").first()
        )

        # Create customer with existing message
        customer = Customer(
            phone_number="+255999999999", full_name="Bob Farmer"
        )
        db_session.add(customer)
        db_session.commit()

        old_message = Message(
            message_sid="SM_OLD_BOB",
            customer_id=customer.id,
            body="Old message",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(old_message)
        db_session.commit()

        # Create resolved ticket
        ticket = Ticket(
            ticket_number="T002",
            administrative_id=admin.id,
            customer_id=customer.id,
            message_id=old_message.id,
            resolved_at=datetime(2025, 1, 1, 12, 0, 0),
        )
        db_session.add(ticket)
        db_session.commit()

        with patch("routers.whatsapp.WhatsAppService") as mock_whatsapp, patch(
            "routers.whatsapp.emit_message_created", new_callable=AsyncMock
        ) as mock_emit:
            mock_service = Mock()
            mock_whatsapp.return_value = mock_service

            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+255999999999",
                    "Body": "Message after ticket resolved",
                    "MessageSid": "SM_RESOLVED",
                },
            )

            assert response.status_code == 200

            # emit_message_created should NOT be called for resolved tickets
            mock_emit.assert_not_called()

    def test_webhook_without_ticket_no_emit(
        self, client: TestClient, db_session: Session
    ):
        """Test emit_message_created NOT called when no ticket."""
        # Create customer with existing message (not new)
        customer = Customer(
            phone_number="+255777777777", full_name="Alice Farmer"
        )
        db_session.add(customer)
        db_session.commit()

        old_message = Message(
            message_sid="SM_OLD_ALICE",
            customer_id=customer.id,
            body="Old message",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(old_message)
        db_session.commit()

        # No ticket created for this customer

        with patch("routers.whatsapp.WhatsAppService") as mock_whatsapp, patch(
            "routers.whatsapp.emit_message_created", new_callable=AsyncMock
        ) as mock_emit:
            mock_service = Mock()
            mock_whatsapp.return_value = mock_service

            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+255777777777",
                    "Body": "Message without ticket",
                    "MessageSid": "SM_NO_TICKET",
                },
            )

            assert response.status_code == 200

            # emit_message_created should NOT be called when no ticket exists
            mock_emit.assert_not_called()
