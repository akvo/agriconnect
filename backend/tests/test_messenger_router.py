import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from config import settings
from models.customer import Customer, OnboardingStatus
from models.message import Message, MessageFrom
from tests.test_messenger_service import generate_signed_request


class TestMessengerRouter:
    """Test suite for Facebook Messenger webhook and compliance endpoints."""

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
