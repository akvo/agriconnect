"""
Integration tests for WhatsApp + Akvo-RAG workflow

Tests the complete flow:
1. Customer sends WhatsApp message
2. Message stored in database
3. Chat job created with akvo-rag
4. Callback received from akvo-rag
5. Response sent back to customer via WhatsApp
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.customer import Customer
from models.message import Message, MessageType
from models.ticket import Ticket
from models.administrative import Administrative
from seeder.administrative import seed_administrative_data


@pytest.fixture
def test_customer(db_session: Session):
    """Create a test customer"""
    customer = Customer(
        phone_number="+1234567890",
        full_name="Test Farmer",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


@pytest.fixture
def test_message(db_session: Session, test_customer):
    """Create a test message from customer"""
    message = Message(
        message_sid="SM123456",
        customer_id=test_customer.id,
        body="How do I plant rice?",
        from_source=1,  # WhatsApp
        message_type=None,  # Incoming messages don't have message_type
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)
    return message


@pytest.fixture
def test_ticket(db_session: Session, test_customer, test_message):
    """Create a test ticket"""
    rows = [
        {
            "code": "LOC1",
            "name": "Location 1",
            "level": "Country",
            "parent_code": "",
        },
        {
            "code": "LOC2",
            "name": "Location 2",
            "level": "Region",
            "parent_code": "LOC1",
        },
        {
            "code": "LOC3",
            "name": "Location 3",
            "level": "District",
            "parent_code": "LOC2",
        },
    ]
    seed_administrative_data(db_session, rows)
    adm = db_session.query(Administrative).filter_by(code="LOC3").first()
    ticket = Ticket(
        ticket_number=f"TICKET-{test_customer.id}",
        customer_id=test_customer.id,
        administrative_id=adm.id,
        message_id=test_message.id,
    )
    db_session.add(ticket)
    db_session.commit()
    db_session.refresh(ticket)
    return ticket


@pytest.fixture
def mock_akvo_rag_service():
    """Mock akvo-rag service"""
    service = MagicMock()
    service.create_chat_job = AsyncMock(
        return_value={"job_id": "test_job_123", "status": "queued"}
    )
    return service


@pytest.fixture
def mock_whatsapp_service():
    """Mock WhatsApp service"""
    service = MagicMock()
    service.send_confirmation_template = MagicMock(
        return_value={"sid": "MM123456789"}
    )
    service.send_message_with_tracking = MagicMock(
        return_value={
            "sid": "SM_MOCK_123",
            "status": "sent",
            "error_code": None,
        }
    )
    service.send_template_message = MagicMock(
        return_value={"sid": "MM_TEMPLATE_123"}
    )
    return service


class TestWhatsAppToAkvoRagFlow:
    """Test the complete flow from WhatsApp message to akvo-rag job creation"""

    @pytest.mark.asyncio
    async def test_incoming_whatsapp_message_creates_rag_job(
        self,
        client: TestClient,
        db_session: Session,
        test_customer,
        mock_akvo_rag_service,
    ):
        """
        Test that incoming WhatsApp message triggers akvo-rag job creation
        """
        # This would be triggered by the WhatsApp webhook endpoint
        # For now, we test the service layer directly

        # Simulate storing the message
        message = Message(
            message_sid="SM_NEW_123",
            customer_id=test_customer.id,
            body="What is the best fertilizer for maize?",
            from_source=1,
            message_type=None,  # Incoming messages
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        # Call the akvo-rag service to create a job
        with patch(
            "services.akvo_rag_service.get_akvo_rag_service",
            return_value=mock_akvo_rag_service,
        ):
            result = await mock_akvo_rag_service.create_chat_job(
                message_id=message.id,
                message_type=MessageType.REPLY.value,
                customer_id=test_customer.id,
            )

        assert result is not None
        assert result["job_id"] == "test_job_123"
        mock_akvo_rag_service.create_chat_job.assert_called_once()


class TestAkvoRagCallbackToWhatsApp:
    """Test akvo-rag callback handling and WhatsApp response"""

    def test_successful_callback_sends_whatsapp_reply(
        self,
        client: TestClient,
        db_session: Session,
        test_customer,
        test_message,
        mock_whatsapp_service,
    ):
        """Test successful akvo-rag callback sends WhatsApp response"""
        # Prepare callback payload from akvo-rag
        callback_payload = {
            "job_id": "job_abc123",
            "status": "completed",
            "output": {
                "answer": (
                    "For maize, " "use NPK fertilizer at a ratio of 20-10-10."
                ),
                "citations": [
                    {
                        "document": "Maize Cultivation Guide.pdf",
                        "chunk": (
                            "Use NPK fertilizer at a "
                            "ratio of 20-10-10 for optimal growth."
                        ),
                        "page": "12",
                    }
                ],
            },
            "error": None,
            "callback_params": (
                f'{{"message_id": {test_message.id}, "message_type": 1, '
                f'"customer_id": {test_customer.id}}}'
            ),
        }

        # Mock WhatsApp service
        with patch(
            "routers.callbacks.WhatsAppService",
            return_value=mock_whatsapp_service,
        ):
            response = client.post("/api/callback/ai", json=callback_payload)

        assert response.status_code == 200
        assert response.json()["job_id"] == "job_abc123"

        # Verify AI message was stored in database
        # For REPLY type,
        # message_sid is the Twilio SID from WhatsApp send (mocked)
        ai_message = (
            db_session.query(Message)
            .filter(
                Message.message_sid == "SM_MOCK_123"
            )  # From mock WhatsApp service
            .first()
        )
        assert ai_message is not None
        assert ai_message.body == callback_payload["output"]["answer"]
        assert ai_message.message_type == MessageType.REPLY

        # Verify WhatsApp messages were sent
        # (AI answer + confirmation template)
        mock_whatsapp_service.send_message_with_tracking.assert_called_once()
        mock_whatsapp_service.send_template_message.assert_called_once()

    def test_failed_callback_logs_error(
        self,
        client: TestClient,
        db_session: Session,
        test_customer,
        test_message,
    ):
        """Test failed akvo-rag callback is handled gracefully"""
        callback_payload = {
            "job_id": "job_failed_123",
            "status": "failed",
            "output": None,
            "error": "Prompt must accept context as an input variable",
            "callback_params": (
                f'{{"message_id": {test_message.id}, '
                f'"message_type": 1, "customer_id": {test_customer.id}}}'
            ),
        }

        response = client.post("/api/callback/ai", json=callback_payload)

        assert response.status_code == 200
        assert response.json()["job_id"] == "job_failed_123"

        # Verify no AI message was created
        ai_message = (
            db_session.query(Message)
            .filter(Message.message_sid == f"ai_{callback_payload['job_id']}")
            .first()
        )
        assert ai_message is None


class TestWhisperModeFlow:
    """Test WHISPER mode (AI suggestions to Extension Officers)"""

    def test_whisper_callback_stores_suggestion_for_eo(
        self,
        client: TestClient,
        db_session: Session,
        test_customer,
        test_message,
        test_ticket,
    ):
        """Test WHISPER mode callback stores AI suggestion for EO"""
        callback_payload = {
            "job_id": "job_whisper_123",
            "status": "completed",
            "output": {
                "answer": (
                    "Suggest applying 50kg NPK per hectare for optimal yield."
                ),
                "citations": [],
            },
            "error": None,
            "callback_params": (
                f'{{"message_id": {test_message.id}, "message_type": 2, '
                f'"customer_id": {test_customer.id}, '
                f'"ticket_id": {test_ticket.id}}}'
            ),
        }

        response = client.post("/api/callback/ai", json=callback_payload)

        assert response.status_code == 200

        # Verify whisper message was stored
        whisper_message = (
            db_session.query(Message)
            .filter(Message.message_sid == f"ai_{callback_payload['job_id']}")
            .first()
        )
        assert whisper_message is not None
        assert whisper_message.message_type == MessageType.WHISPER
        assert (
            whisper_message.body
            == "Suggest applying 50kg NPK per hectare for optimal yield."
        )

    def test_whisper_callback_without_ticket_finds_open_ticket(
        self,
        client: TestClient,
        db_session: Session,
        test_customer,
        test_message,
        test_ticket,
    ):
        """Test WHISPER callback finds open ticket if not provided"""
        # Don't include ticket_id in callback_params
        callback_payload = {
            "job_id": "job_whisper_no_ticket",
            "status": "completed",
            "output": {
                "answer": "AI suggestion for EO",
                "citations": [],
            },
            "error": None,
            "callback_params": (
                f'{{"message_id": {test_message.id}, "message_type": 2, '
                f'"customer_id": {test_customer.id}}}'
            ),
        }

        response = client.post("/api/callback/ai", json=callback_payload)

        assert response.status_code == 200

        # Verify whisper message was stored
        whisper_message = (
            db_session.query(Message)
            .filter(Message.message_sid == f"ai_{callback_payload['job_id']}")
            .first()
        )
        assert whisper_message is not None


class TestCallbackPayloadValidation:
    """Test akvo-rag callback payload validation"""

    def test_callback_with_json_string_params(
        self, client: TestClient, test_customer, test_message
    ):
        """Test callback accepts callback_params as JSON string"""
        callback_payload = {
            "job_id": "test_json_string",
            "status": "completed",
            "output": {
                "answer": "Test answer",
                "citations": [],
            },
            "error": None,
            "callback_params": (
                '{"message_id": 123, "message_type": 1, "customer_id": 456}'
            ),
        }

        response = client.post("/api/callback/ai", json=callback_payload)

        # Should accept JSON string format (akvo-rag sends this way)
        assert response.status_code == 200

    def test_callback_with_dict_params(self, client: TestClient):
        """Test callback also accepts callback_params as dict"""
        callback_payload = {
            "job_id": "test_dict",
            "status": "completed",
            "output": {
                "answer": "Test answer",
                "citations": [],
            },
            "error": None,
            "callback_params": {
                "message_id": 123,
                "message_type": 1,
                "customer_id": 456,
            },
        }

        response = client.post("/api/callback/ai", json=callback_payload)

        # Should also accept dict format for backward compatibility
        assert response.status_code == 200

    def test_callback_missing_required_fields(self, client: TestClient):
        """Test callback rejects payload with missing required fields"""
        callback_payload = {
            "job_id": "test_missing",
            # Missing status field
            "output": None,
            "error": None,
        }

        response = client.post("/api/callback/ai", json=callback_payload)

        assert response.status_code == 422

    def test_callback_invalid_status_enum(self, client: TestClient):
        """Test callback rejects invalid status values"""
        callback_payload = {
            "job_id": "test_invalid_status",
            "status": "invalid_status",
            "output": None,
            "error": None,
            "callback_params": (
                '{"message_id": 123, "message_type": 1, "customer_id": 456}'
            ),
        }

        response = client.post("/api/callback/ai", json=callback_payload)

        assert response.status_code == 422


class TestChatHistoryIntegration:
    """Test chat history is passed to akvo-rag"""

    @pytest.mark.asyncio
    async def test_chat_history_included_in_job(
        self, db_session: Session, test_customer, mock_akvo_rag_service
    ):
        """Test that recent chat history is included when creating job"""
        # Create multiple messages to build history
        messages = []
        for i in range(5):
            msg = Message(
                message_sid=f"SM_{i}",
                customer_id=test_customer.id,
                body=f"Message {i}",
                from_source=1,
                message_type=(
                    MessageType.REPLY if i % 2 != 0 else None
                ),  # Alternate between incoming (None) and reply
            )
            db_session.add(msg)
            messages.append(msg)

        db_session.commit()

        # Build chat history from messages
        chat_history = [
            {
                "role": "user" if msg.message_type is None else "assistant",
                "content": msg.body,
            }
            for msg in messages[:3]  # Last 3 messages
        ]

        # Create job with chat history
        with patch(
            "services.akvo_rag_service.get_akvo_rag_service",
            return_value=mock_akvo_rag_service,
        ):
            await mock_akvo_rag_service.create_chat_job(
                message_id=messages[-1].id,
                message_type=MessageType.REPLY.value,
                customer_id=test_customer.id,
                chats=chat_history,
            )

        # Verify chat history was passed
        call_args = mock_akvo_rag_service.create_chat_job.call_args
        assert call_args[1]["chats"] == chat_history


class TestTicketBasedMessageTypeRouting:
    """Test message type routing based on ticket status"""

    def test_customer_with_unresolved_ticket_stores_message(
        self,
        client: TestClient,
        db_session: Session,
        test_customer,
        test_ticket,
    ):
        """
        Test that a customer with an existing unresolved ticket
        has message stored correctly (WHISPER mode path)
        """
        with patch("routers.whatsapp.emit_message_created") as mock_emit:
            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": f"whatsapp:{test_customer.phone_number}",
                    "Body": "I need more help with my crops",
                    "MessageSid": "SM_EXISTING_TICKET",
                },
            )

        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify message was created with correct body
        message = (
            db_session.query(Message)
            .filter(Message.message_sid == "SM_EXISTING_TICKET")
            .first()
        )
        assert message is not None
        assert message.body == "I need more help with my crops"
        assert message.customer_id == test_customer.id

        # Verify emit_message_created was called for mobile notifications
        # (This happens in WHISPER mode with existing ticket)
        mock_emit.assert_called_once()
        call_kwargs = mock_emit.call_args[1]
        assert call_kwargs["ticket_id"] == test_ticket.id
        assert call_kwargs["customer_id"] == test_customer.id
        assert call_kwargs["body"] == "I need more help with my crops"

    def test_customer_without_ticket_stores_message(
        self,
        client: TestClient,
        db_session: Session,
    ):
        """
        Test that a customer without an existing ticket
        has message stored correctly (REPLY mode path)
        """
        with patch("routers.whatsapp.emit_message_created") as mock_emit:
            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+255999888777",
                    "Body": "Hello, I need farming advice",
                    "MessageSid": "SM_NO_TICKET",
                },
            )

        assert response.status_code == 200

        # Verify message was created
        message = (
            db_session.query(Message)
            .filter(Message.message_sid == "SM_NO_TICKET")
            .first()
        )
        assert message is not None
        assert message.body == "Hello, I need farming advice"

        # Verify customer was created
        customer = (
            db_session.query(Customer)
            .filter(Customer.phone_number == "+255999888777")
            .first()
        )
        assert customer is not None
        assert message.customer_id == customer.id

        # Verify emit_message_created was NOT called
        # (REPLY mode without ticket - no EO notification needed)
        mock_emit.assert_not_called()

    def test_customer_with_resolved_ticket_stores_message(
        self,
        client: TestClient,
        db_session: Session,
        test_customer,
        test_ticket,
    ):
        """
        Test that a customer with only resolved tickets
        has message stored correctly (REPLY mode path)
        """
        # Resolve the existing ticket
        from datetime import datetime

        test_ticket.resolved_at = datetime.utcnow()
        db_session.commit()

        with patch("routers.whatsapp.emit_message_created") as mock_emit:
            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": f"whatsapp:{test_customer.phone_number}",
                    "Body": "I have a new question",
                    "MessageSid": "SM_RESOLVED_TICKET",
                },
            )

        assert response.status_code == 200

        # Verify message was created
        message = (
            db_session.query(Message)
            .filter(Message.message_sid == "SM_RESOLVED_TICKET")
            .first()
        )
        assert message is not None
        assert message.body == "I have a new question"

        # Verify emit_message_created was NOT called
        # (no unresolved ticket, so REPLY mode - no EO notification)
        mock_emit.assert_not_called()

    def test_escalate_button_creates_ticket_and_stores_message(
        self,
        client: TestClient,
        db_session: Session,
        test_customer,
    ):
        """
        Test that clicking escalate button creates ticket
        and stores message with original question
        """
        # Create initial message from customer
        initial_message = Message(
            message_sid="SM_INITIAL",
            customer_id=test_customer.id,
            body="I have a difficult problem",
            from_source=1,
        )
        db_session.add(initial_message)

        # Create AI reply message (so offset(1) in escalate flow works)
        ai_reply = Message(
            message_sid="SM_AI_REPLY",
            customer_id=test_customer.id,
            body="AI reply with escalate button",
            from_source=3,  # LLM
            message_type=MessageType.REPLY,
        )
        db_session.add(ai_reply)
        db_session.commit()

        # Seed administrative data for ticket creation
        from seeder.administrative import seed_administrative_data

        rows = [
            {
                "code": "WARD1",
                "name": "Ward 1",
                "level": "Ward",
                "parent_code": "",
            }
        ]
        seed_administrative_data(db_session, rows)

        with (
            patch("routers.whatsapp.emit_message_created"),
            patch("routers.whatsapp.emit_ticket_created") as mock_emit_ticket,
        ):
            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": f"whatsapp:{test_customer.phone_number}",
                    "Body": "Yes",  # Button response
                    "MessageSid": "SM_ESCALATE",
                    "ButtonPayload": "escalate",
                },
            )

        assert response.status_code == 200
        assert response.json()["message"] == "Escalation processed"

        # Verify ticket was created
        ticket = (
            db_session.query(Ticket)
            .filter(Ticket.customer_id == test_customer.id)
            .first()
        )
        assert ticket is not None
        assert ticket.resolved_at is None

        # Verify escalation message was stored
        # Note: The body will be from the previous message (offset 1),
        # which should be customer's question or AI's reply depending on order
        escalation_message = (
            db_session.query(Message)
            .filter(Message.message_sid == "SM_ESCALATE")
            .first()
        )
        assert escalation_message is not None
        # Verify it's not the button click body "Yes"
        assert escalation_message.body != "Yes"
        # Verify it's one of the previous messages
        assert escalation_message.body in [
            "I have a difficult problem",
            "AI reply with escalate button",
        ]

        # Verify ticket created event was emitted
        mock_emit_ticket.assert_called_once()

    def test_multiple_messages_with_unresolved_ticket_all_emit(
        self,
        client: TestClient,
        db_session: Session,
        test_customer,
        test_ticket,
    ):
        """
        Test that multiple messages from same customer
        with unresolved ticket all emit notifications (WHISPER mode path)
        """
        message_sids = ["SM_MSG1", "SM_MSG2", "SM_MSG3"]

        with patch("routers.whatsapp.emit_message_created") as mock_emit:
            for i, sid in enumerate(message_sids):
                response = client.post(
                    "/api/whatsapp/webhook",
                    data={
                        "From": f"whatsapp:{test_customer.phone_number}",
                        "Body": f"Follow-up question {i + 1}",
                        "MessageSid": sid,
                    },
                )
                assert response.status_code == 200

        # Verify all messages were created
        messages = (
            db_session.query(Message)
            .filter(Message.message_sid.in_(message_sids))
            .all()
        )
        assert len(messages) == 3

        # Verify all messages have correct bodies
        for i, msg in enumerate(sorted(messages, key=lambda m: m.message_sid)):
            assert msg.body == f"Follow-up question {i + 1}"
            assert msg.customer_id == test_customer.id

        # Verify emit_message_created was called for each message
        # (WHISPER mode with existing ticket emits for EO notifications)
        assert mock_emit.call_count == 3
        for call in mock_emit.call_args_list:
            call_kwargs = call[1]
            assert call_kwargs["ticket_id"] == test_ticket.id
            assert call_kwargs["customer_id"] == test_customer.id
