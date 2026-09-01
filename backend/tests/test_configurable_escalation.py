"""
Tests for Configurable Escalation Feature (Issue #195).

Validates:
- settings.escalation_enabled default value and configuration overrides
- Confirmation template gating in AI callbacks
- Escalate button click handling when escalation is enabled vs disabled
- send_confirmation_template in WhatsAppService
"""

from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from config import settings
from models.administrative import Administrative, CustomerAdministrative
from models.customer import Customer, CustomerLanguage, OnboardingStatus
from models.message import Message, MessageFrom
from models.ticket import Ticket
from seeder.administrative import seed_administrative_data
from services.whatsapp_service import WhatsAppService


class TestConfigurableEscalation:
    """Test suite for configurable escalation toggle."""

    @pytest.fixture
    def test_customer(self, db_session: Session):
        """Create a test customer with completed onboarding and ward link."""
        customer = Customer(
            phone_number="+255111222333",
            language=CustomerLanguage.EN,
            full_name="Escalation Test Customer",
            onboarding_status=OnboardingStatus.COMPLETED,
            profile_data={
                "crop_type": "maize",
                "gender": "male",
                "birth_year": 1990,
            },
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        rows = [
            {
                "code": "TEST_ESC_WARD",
                "name": "Test Esc Ward",
                "level": "Ward",
                "parent_code": "",
            }
        ]
        seed_administrative_data(db_session, rows)

        admin = (
            db_session.query(Administrative)
            .filter(Administrative.code == "TEST_ESC_WARD")
            .first()
        )
        customer_admin = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=admin.id,
        )
        db_session.add(customer_admin)
        db_session.commit()

        return customer

    @pytest.fixture
    def test_message(self, db_session: Session, test_customer):
        """Create a test message."""
        message = Message(
            message_sid="reply_test_msg_001",
            customer_id=test_customer.id,
            body="How do I plant maize?",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)
        return message

    def test_settings_escalation_enabled_default(self):
        """Verify escalation_enabled is a boolean and defaults to True."""
        assert hasattr(settings, "escalation_enabled")
        assert isinstance(settings.escalation_enabled, bool)
        assert settings.escalation_enabled is True

    def test_whatsapp_service_send_confirmation_template_disabled(
        self, monkeypatch
    ):
        """Verify confirmation template skips when escalation is disabled."""
        service = WhatsAppService()
        monkeypatch.setattr(settings, "escalation_enabled", False)
        res = service.send_confirmation_template("+254700000000", "Answer")
        assert res == {
            "status": "skipped",
            "message": "Escalation feature is disabled",
        }

    def test_ai_callback_skips_confirmation_template_when_disabled(
        self,
        client: TestClient,
        test_message,
        db_session: Session,
        monkeypatch,
    ):
        """Verify AI callback skips confirmation template when disabled."""
        monkeypatch.setattr(settings, "escalation_enabled", False)

        payload = {
            "job_id": "job_escalation_disabled_test",
            "status": "completed",
            "output": {
                "answer": "Use copper-based fungicides.",
                "citations": [
                    {
                        "document": "Maize Rust Guide",
                        "chunk": "Use copper fungicides",
                        "page": "1",
                    }
                ],
            },
            "error": None,
            "callback_params": (
                f'{{"message_id": {test_message.id}, "message_type": 1, '
                f'"customer_id": {test_message.customer_id}}}'
            ),
            "trace_id": "trace_esc_001",
            "job": "chat",
        }

        with patch(
            "routers.callbacks.WhatsAppService.send_template_message"
        ) as mock_send_tpl:
            response = client.post("/api/callback/ai", json=payload)
            assert response.status_code == 200
            mock_send_tpl.assert_not_called()

    def test_whatsapp_webhook_escalate_button_ignored_when_disabled(
        self,
        client: TestClient,
        test_customer,
        db_session: Session,
        monkeypatch,
    ):
        """Verify escalate button returns ignored when disabled."""
        msg1 = Message(
            message_sid="SM_INITIAL_Q",
            customer_id=test_customer.id,
            body="I have an urgent pest problem",
            from_source=MessageFrom.CUSTOMER,
        )
        msg2 = Message(
            message_sid="SM_AI_RESP",
            customer_id=test_customer.id,
            body="Here is some AI advice",
            from_source=MessageFrom.LLM,
        )
        db_session.add_all([msg1, msg2])
        db_session.commit()

        webhook_data = {
            "From": f"whatsapp:{test_customer.phone_number}",
            "Body": "Yes",
            "ButtonPayload": "escalate",
            "MessageSid": "SM_BTN_CLICK_01",
        }

        monkeypatch.setattr(settings, "escalation_enabled", False)
        response = client.post("/api/whatsapp/webhook", data=webhook_data)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ignored"
        assert data["message"] == "Escalation feature is disabled"

        # Ensure no ticket was created
        ticket = (
            db_session.query(Ticket)
            .filter(Ticket.customer_id == test_customer.id)
            .first()
        )
        assert ticket is None
