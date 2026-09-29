import json
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from config import settings
from models.customer import Customer, OnboardingStatus
from models.message import Message, MessageFrom
from tests.test_messenger_service import generate_signed_request


class TestMessengerRouter:
    """Test suite for Facebook Messenger webhook and compliance endpoints."""

    @pytest.fixture(autouse=True)
    def setup_messenger_settings(self):
        """Isolate tests from ambient environment variables."""
        with (
            patch.object(settings, "messenger_app_secret", ""),
            patch.object(settings, "messenger_page_id", ""),
        ):
            yield

    def test_webhook_handshake_success(self, client: TestClient):
        response = client.get(
            "/api/messenger/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": settings.messenger_verify_token,
                "hub.challenge": "1158201244",
            },
        )
        assert response.status_code == 200
        assert response.text == "1158201244"

    def test_webhook_handshake_invalid_token(self, client: TestClient):
        response = client.get(
            "/api/messenger/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_verify_token",
                "hub.challenge": "1158201244",
            },
        )
        assert response.status_code == 403

    def test_webhook_handshake_invalid_mode(self, client: TestClient):
        response = client.get(
            "/api/messenger/webhook",
            params={
                "hub.mode": "publish",
                "hub.verify_token": settings.messenger_verify_token,
                "hub.challenge": "1158201244",
            },
        )
        assert response.status_code == 403

    def test_webhook_post_invalid_signature(self, client: TestClient):
        with patch.object(settings, "messenger_app_secret", "secret_123"):
            body = json.dumps({"object": "page", "entry": []}).encode("utf-8")
            response = client.post(
                "/api/messenger/webhook",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": "sha256=invalid_hash",
                },
            )
            assert response.status_code == 403

    def test_webhook_post_ignores_echo(
        self, client: TestClient, db_session: Session
    ):
        payload = {
            "object": "page",
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "psid_echo_1"},
                            "recipient": {"id": "page_id_1"},
                            "message": {
                                "mid": "mid.12345",
                                "is_echo": True,
                                "text": "Echo message",
                            },
                        }
                    ]
                }
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        with patch.object(settings, "messenger_app_secret", ""):
            response = client.post(
                "/api/messenger/webhook",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "ignored"

            # Verify no customer was created
            customer = (
                db_session.query(Customer)
                .filter(Customer.phone_number == "messenger:psid_echo_1")
                .first()
            )
            assert customer is None

    def test_webhook_post_ignores_delivery_receipt(
        self, client: TestClient, db_session: Session
    ):
        payload = {
            "object": "page",
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "psid_receipt_1"},
                            "recipient": {"id": "page_id_1"},
                            "delivery": {"mids": ["mid.12345"]},
                        }
                    ]
                }
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        with patch.object(settings, "messenger_app_secret", ""):
            response = client.post(
                "/api/messenger/webhook",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "ignored"

    def test_webhook_post_ignores_unconfigured_page_id(
        self, client: TestClient, db_session: Session
    ):
        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "other_page_id",
                    "messaging": [
                        {
                            "sender": {"id": "psid_other_page_1"},
                            "recipient": {"id": "other_page_id"},
                            "message": {
                                "mid": "mid.12345",
                                "text": "Hello other page",
                            },
                        }
                    ],
                }
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        with (
            patch.object(settings, "messenger_app_secret", ""),
            patch.object(
                settings, "messenger_page_id", "my_configured_page_id"
            ),
        ):
            response = client.post(
                "/api/messenger/webhook",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "ignored"

            customer = (
                db_session.query(Customer)
                .filter(Customer.phone_number == "messenger:psid_other_page_1")
                .first()
            )
            assert customer is None

    def test_webhook_post_accepts_configured_page_id(
        self, client: TestClient, db_session: Session
    ):
        psid = "psid_configured_page_1"
        payload = {
            "object": "page",
            "entry": [
                {
                    "id": "my_configured_page_id",
                    "messaging": [
                        {
                            "sender": {"id": psid},
                            "recipient": {"id": "my_configured_page_id"},
                            "message": {
                                "mid": "mid.configured.1",
                                "text": "Habari AgriConnect",
                            },
                        }
                    ],
                }
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        with (
            patch.object(settings, "messenger_app_secret", ""),
            patch.object(
                settings, "messenger_page_id", "my_configured_page_id"
            ),
        ):
            response = client.post(
                "/api/messenger/webhook",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200

            customer = (
                db_session.query(Customer)
                .filter(Customer.phone_number == f"messenger:{psid}")
                .first()
            )
            assert customer is not None

    def test_webhook_post_onboarding_message(
        self, client: TestClient, db_session: Session
    ):
        psid = "psid_farmer_1001"
        payload = {
            "object": "page",
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": psid},
                            "recipient": {"id": "page_id_1"},
                            "message": {
                                "mid": "mid.farmer.1",
                                "text": "Habari AgriConnect",
                            },
                        }
                    ]
                }
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        with patch.object(settings, "messenger_app_secret", ""):
            response = client.post(
                "/api/messenger/webhook",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200

            # Verify customer was created with messenger prefix
            customer = (
                db_session.query(Customer)
                .filter(Customer.phone_number == f"messenger:{psid}")
                .first()
            )
            assert customer is not None
            assert customer.onboarding_status == OnboardingStatus.IN_PROGRESS

    def test_webhook_post_ignores_duplicate_mid(
        self, client: TestClient, db_session: Session
    ):
        psid = "psid_farmer_dup"
        payload = {
            "object": "page",
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": psid},
                            "recipient": {"id": "page_id_1"},
                            "message": {
                                "mid": "mid.farmer.dup.1",
                                "text": "Habari",
                            },
                        }
                    ]
                }
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        with patch.object(settings, "messenger_app_secret", ""):
            # First delivery
            resp1 = client.post(
                "/api/messenger/webhook",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            assert resp1.status_code == 200

            # Second delivery (retry)
            resp2 = client.post(
                "/api/messenger/webhook",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            assert resp2.status_code == 200

            # Verify only 1 message recorded in database
            messages = (
                db_session.query(Message)
                .filter(Message.message_sid == "mid.farmer.dup.1")
                .all()
            )
            assert len(messages) == 1

    def test_webhook_post_in_chat_deletion_flow(
        self, client: TestClient, db_session: Session
    ):
        psid = "psid_del_user"
        # 1. Create customer first
        customer = Customer(
            phone_number=f"messenger:{psid}",
            full_name="Delete Farmer",
            language="sw",
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()
        customer_id = customer.id

        # 2. Send "futa" (delete request in Swahili)
        delete_payload = {
            "object": "page",
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": psid},
                            "recipient": {"id": "page_id_1"},
                            "message": {"mid": "mid.del.1", "text": "futa"},
                        }
                    ]
                }
            ],
        }
        with patch.object(settings, "messenger_app_secret", ""):
            resp1 = client.post(
                "/api/messenger/webhook",
                content=json.dumps(delete_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            assert resp1.status_code == 200

            db_session.refresh(customer)
            assert customer.delete_requested is True

            # 3. Send "ndio" (confirm in Swahili)
            confirm_payload = {
                "object": "page",
                "entry": [
                    {
                        "messaging": [
                            {
                                "sender": {"id": psid},
                                "recipient": {"id": "page_id_1"},
                                "message": {
                                    "mid": "mid.del.2",
                                    "text": "ndio",
                                },
                            }
                        ]
                    }
                ],
            }
            resp2 = client.post(
                "/api/messenger/webhook",
                content=json.dumps(confirm_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            assert resp2.status_code == 200

            # 4. Verify customer is completely deleted
            deleted_cust = (
                db_session.query(Customer)
                .filter(Customer.id == customer_id)
                .first()
            )
            assert deleted_cust is None

    def test_meta_data_deletion_callback_success(
        self, client: TestClient, db_session: Session
    ):
        secret = "test_meta_app_secret"
        user_psid = "meta_user_999"

        # Create customer to delete
        customer = Customer(
            phone_number=f"messenger:{user_psid}",
            full_name="Meta User",
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()
        customer_id = customer.id

        signed_request = generate_signed_request(
            {"user_id": user_psid, "algorithm": "HMAC-SHA256"}, secret
        )

        with patch.object(settings, "messenger_app_secret", secret):
            response = client.post(
                "/api/messenger/data-deletion",
                data={"signed_request": signed_request},
            )
            assert response.status_code == 200
            data = response.json()
            assert "url" in data
            assert "confirmation_code" in data
            assert "code=" in data["url"]

            # Verify customer was deleted
            deleted = (
                db_session.query(Customer)
                .filter(Customer.id == customer_id)
                .first()
            )
            assert deleted is None

    def test_meta_data_deletion_callback_invalid_signature(
        self, client: TestClient
    ):
        with patch.object(
            settings, "messenger_app_secret", "test_meta_app_secret"
        ):
            response = client.post(
                "/api/messenger/data-deletion",
                data={"signed_request": "invalid_sig.invalid_payload"},
            )
            assert response.status_code == 403

    def test_meta_data_deletion_status_endpoint(self, client: TestClient):
        response = client.get(
            "/api/messenger/data-deletion/status", params={"code": "CONF12345"}
        )
        assert response.status_code == 200
        assert "CONF12345" in response.text

    def test_callback_ai_dispatch_to_messenger(
        self, client: TestClient, db_session: Session
    ):
        psid = "psid_callback_123"
        customer = Customer(
            phone_number=f"messenger:{psid}",
            language="en",
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        farmer_msg = Message(
            message_sid="mid_initial_query",
            customer_id=customer.id,
            body="How to plant maize?",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(farmer_msg)
        db_session.commit()

        callback_params = json.dumps(
            {
                "message_id": farmer_msg.id,
                "message_type": 1,  # MessageType.REPLY
                "customer_id": customer.id,
            }
        )

        payload = {
            "job_id": "job_msgr_123",
            "status": "completed",
            "stage": "final",
            "job": "chat",
            "output": {
                "answer": "Plant maize with 75cm x 25cm spacing.",
                "citations": [],
            },
            "error": None,
            "callback_params": callback_params,
            "trace_id": "trace_msgr_001",
            "token_count": 50,
        }

        with patch("services.messenger_service.requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {
                "recipient_id": psid,
                "message_id": "mid.real.from.callback",
            }

            response = client.post("/api/callback/ai", json=payload)
            assert response.status_code == 200

            # Verify AI message was saved in DB
            ai_msg = (
                db_session.query(Message)
                .filter(
                    Message.customer_id == customer.id,
                    Message.from_source == MessageFrom.LLM,
                )
                .first()
            )
            assert ai_msg is not None
            assert "Plant maize" in ai_msg.body

    def test_ai_callback_sends_escalation_quick_reply_with_citations(
        self, client: TestClient, db_session: Session
    ):
        psid = "psid_citations_test"
        customer = Customer(
            phone_number=f"messenger:{psid}",
            full_name="Farmer Citations",
            language="en",
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        farmer_msg = Message(
            message_sid="mid_citations_query",
            customer_id=customer.id,
            body="How to treat avocado root rot?",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(farmer_msg)
        db_session.commit()

        callback_params = json.dumps(
            {
                "message_id": farmer_msg.id,
                "message_type": 1,
                "customer_id": customer.id,
            }
        )

        payload = {
            "job_id": "job_msgr_citations",
            "status": "completed",
            "stage": "final",
            "job": "chat",
            "output": {
                "answer": "Apply phosphonate fungicide.",
                "citations": [{"source": "Avocado Manual", "page": "12"}],
            },
            "error": None,
            "callback_params": callback_params,
            "trace_id": "trace_msgr_cit",
            "token_count": 60,
        }

        with (
            patch(
                "services.messenger_service.MessengerService.send_message"
            ) as mock_send_msg,
            patch(
                "services.messenger_service.MessengerService."
                "send_quick_replies"
            ) as mock_send_qr,
        ):
            mock_send_msg.return_value = {
                "recipient_id": psid,
                "message_id": "mid.msg.123",
            }
            mock_send_qr.return_value = {
                "recipient_id": psid,
                "message_id": "mid.qr.123",
            }

            response = client.post("/api/callback/ai", json=payload)
            assert response.status_code == 200

            assert mock_send_msg.called
            assert mock_send_qr.called
            qr_kwargs = mock_send_qr.call_args[1]
            assert qr_kwargs["recipient_psid"] == psid
            assert qr_kwargs["options"][0]["payload"] == "escalate"

    def test_messenger_webhook_escalate_creates_ticket(
        self, client: TestClient, db_session: Session
    ):
        from models.administrative import Administrative, AdministrativeLevel
        from models.message import MessageStatus
        from models.ticket import Ticket

        # Create root administrative area
        level = AdministrativeLevel(name="Country", level_index=1)
        db_session.add(level)
        db_session.commit()

        root_adm = Administrative(
            code="KEN",
            name="Kenya",
            level_id=level.id,
            path="Kenya",
            parent_id=None,
        )
        db_session.add(root_adm)
        db_session.commit()

        psid = "psid_escalate_test"
        customer = Customer(
            phone_number=f"messenger:{psid}",
            full_name="Escalating Farmer",
            language="en",
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        # Original farmer question
        prev_msg = Message(
            message_sid="mid_orig_q",
            customer_id=customer.id,
            body="My crop has yellow leaves",
            from_source=MessageFrom.CUSTOMER,
        )
        db_session.add(prev_msg)
        db_session.commit()

        payload = {
            "object": "page",
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": psid},
                            "recipient": {"id": "page_123"},
                            "message": {
                                "mid": "mid.btn.escalate",
                                "quick_reply": {"payload": "escalate"},
                                "text": "Talk to Officer",
                            },
                        }
                    ]
                }
            ],
        }

        with (
            patch(
                "services.messenger_service.MessengerService.send_message"
            ) as mock_send,
            patch("routers.messenger.emit_message_received") as mock_emit,
        ):
            mock_send.return_value = {
                "recipient_id": psid,
                "message_id": "mid.conf.123",
            }
            response = client.post(
                "/api/messenger/webhook",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200

            # Verify ticket created
            ticket = (
                db_session.query(Ticket)
                .filter(Ticket.customer_id == customer.id)
                .first()
            )
            assert ticket is not None

            # Verify message marked as ESCALATED
            assert prev_msg.status == MessageStatus.ESCALATED
            assert mock_emit.called

            # Verify confirmation sent
            assert mock_send.called
            confirmation_text = mock_send.call_args[1]["text"]
            assert (
                "transferred to extension service provider"
                in confirmation_text
            )

    def test_messenger_webhook_escalate_ignored_when_disabled(
        self, client: TestClient, db_session: Session
    ):
        psid = "psid_escalate_disabled"
        customer = Customer(
            phone_number=f"messenger:{psid}",
            full_name="Escalating Farmer Disabled",
            language="en",
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        payload = {
            "object": "page",
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": psid},
                            "recipient": {"id": "page_123"},
                            "message": {
                                "mid": "mid.btn.escalate.disabled",
                                "quick_reply": {"payload": "escalate"},
                                "text": "Talk to Officer",
                            },
                        }
                    ]
                }
            ],
        }

        with patch.object(settings, "escalation_enabled", False):
            response = client.post(
                "/api/messenger/webhook",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "ignored"

    def test_messenger_webhook_weather_intent(
        self, client: TestClient, db_session: Session
    ):
        from models.administrative import (
            Administrative,
            AdministrativeLevel,
            CustomerAdministrative,
        )
        from services.weather_intent_service import WeatherIntentResult

        # Create root and ward administrative area
        level = AdministrativeLevel(name="Ward", level_index=4)
        db_session.add(level)
        db_session.commit()

        ward_adm = Administrative(
            code="W1",
            name="Kiharu Ward",
            level_id=level.id,
            path="Kenya > Kiharu Ward",
            parent_id=None,
            lat=-0.71,
            long=37.15,
        )
        db_session.add(ward_adm)
        db_session.commit()

        psid = "psid_weather_user"
        customer = Customer(
            phone_number=f"messenger:{psid}",
            full_name="Weather Farmer",
            language="en",
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        cust_adm = CustomerAdministrative(
            customer_id=customer.id,
            administrative_id=ward_adm.id,
        )
        db_session.add(cust_adm)
        db_session.commit()

        payload = {
            "object": "page",
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": psid},
                            "recipient": {"id": "page_123"},
                            "message": {
                                "mid": "mid.weather.query",
                                "text": "weather today",
                            },
                        }
                    ]
                }
            ],
        }

        with patch(
            "services.weather_intent_service.WeatherIntentService."
            "handle_weather_intent"
        ) as mock_handle:
            mock_handle.return_value = WeatherIntentResult(
                handled=True,
                message="Weather intent handled",
                weather_message="Sunny, 25°C",
            )
            response = client.post(
                "/api/messenger/webhook",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200
            assert mock_handle.called

    def test_messenger_webhook_weather_subscription_response(
        self, client: TestClient, db_session: Session
    ):
        psid = "psid_sub_user"
        customer = Customer(
            phone_number=f"messenger:{psid}",
            full_name="Subscribing Farmer",
            language="en",
            weather_subscription_asked=True,
            weather_subscribed=None,
            onboarding_status=OnboardingStatus.COMPLETED,
        )
        db_session.add(customer)
        db_session.commit()

        payload = {
            "object": "page",
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": psid},
                            "recipient": {"id": "page_123"},
                            "message": {
                                "mid": "mid.sub.yes",
                                "quick_reply": {
                                    "payload": settings.weather_yes_payload
                                },
                                "text": "Yes",
                            },
                        }
                    ]
                }
            ],
        }

        with patch(
            "services.messenger_service.MessengerService.send_message"
        ) as mock_send:
            mock_send.return_value = {
                "recipient_id": psid,
                "message_id": "mid.conf.sub",
            }
            response = client.post(
                "/api/messenger/webhook",
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 200
            assert response.json()["status"] == "success"

            db_session.refresh(customer)
            assert customer.weather_subscribed is True
            assert mock_send.called
