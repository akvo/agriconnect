import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from models.customer import Customer, CustomerLanguage
from models.message import Message, MessageFrom
from services.whatsapp_service import WhatsAppService


class TestWhatsAppWebhook:
    def test_webhook_new_customer_english(self, client: TestClient, db_session: Session):
        with patch('routers.whatsapp.WhatsAppService') as mock_whatsapp:
            mock_service = Mock()
            mock_whatsapp.return_value = mock_service
            
            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+255123456789",
                    "Body": "Hello, I need farming help",
                    "MessageSid": "SM12345678"
                }
            )
            
            assert response.status_code == 200
            assert response.json()["status"] == "success"
            
            # Check customer was created
            customer = db_session.query(Customer).filter(
                Customer.phone_number == "+255123456789"
            ).first()
            assert customer is not None
            assert customer.language == CustomerLanguage.EN
            
            # Check message was stored
            message = db_session.query(Message).filter(
                Message.message_sid == "SM12345678"
            ).first()
            assert message is not None
            assert message.body == "Hello, I need farming help"
            assert message.from_source == MessageFrom.CUSTOMER
            assert message.customer_id == customer.id
            
            # Check welcome message was sent
            mock_service.send_welcome_message.assert_called_once_with(
                "+255123456789", "en"
            )

    def test_webhook_new_customer_swahili(self, client: TestClient, db_session: Session):
        with patch('routers.whatsapp.WhatsAppService') as mock_whatsapp:
            mock_service = Mock()
            mock_whatsapp.return_value = mock_service
            
            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+255987654321",
                    "Body": "Hujambo, nahitaji msaada wa kilimo",
                    "MessageSid": "SM87654321"
                }
            )
            
            assert response.status_code == 200
            
            customer = db_session.query(Customer).filter(
                Customer.phone_number == "+255987654321"
            ).first()
            assert customer.language == CustomerLanguage.SW
            
            mock_service.send_welcome_message.assert_called_once_with(
                "+255987654321", "sw"
            )

    def test_webhook_existing_customer(self, client: TestClient, db_session: Session):
        # Create existing customer
        existing_customer = Customer(
            phone_number="+255111111111",
            full_name="John Farmer"
        )
        db_session.add(existing_customer)
        db_session.commit()
        
        # Add a previous message to make them not new
        previous_message = Message(
            message_sid="SM_OLD",
            customer_id=existing_customer.id,
            body="Previous message",
            from_source=MessageFrom.CUSTOMER
        )
        db_session.add(previous_message)
        db_session.commit()

        with patch('routers.whatsapp.WhatsAppService') as mock_whatsapp:
            mock_service = Mock()
            mock_whatsapp.return_value = mock_service
            
            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+255111111111",
                    "Body": "Another message",
                    "MessageSid": "SM_NEW"
                }
            )
            
            assert response.status_code == 200
            
            # Should not send welcome message for existing customer
            mock_service.send_welcome_message.assert_not_called()
            
            # Message should still be stored
            new_message = db_session.query(Message).filter(
                Message.message_sid == "SM_NEW"
            ).first()
            assert new_message is not None
            assert new_message.body == "Another message"

    def test_webhook_duplicate_message_sid(self, client: TestClient, db_session: Session):
        # Create customer and message first
        customer = Customer(phone_number="+255123456789")
        db_session.add(customer)
        db_session.commit()
        
        message = Message(
            message_sid="SM_DUPLICATE",
            customer_id=customer.id,
            body="Original message",
            from_source=MessageFrom.CUSTOMER
        )
        db_session.add(message)
        db_session.commit()

        # Try to send same message_sid again
        response = client.post(
            "/api/whatsapp/webhook",
            data={
                "From": "whatsapp:+255123456789",
                "Body": "Duplicate message",
                "MessageSid": "SM_DUPLICATE"
            }
        )
        
        assert response.status_code == 200
        assert response.json()["message"] == "Message already processed"
        
        # Should still only have one message with that SID
        messages = db_session.query(Message).filter(
            Message.message_sid == "SM_DUPLICATE"
        ).all()
        assert len(messages) == 1
        assert messages[0].body == "Original message"  # Original unchanged

    def test_webhook_welcome_message_failure(self, client: TestClient, db_session: Session):
        with patch('routers.whatsapp.WhatsAppService') as mock_whatsapp:
            mock_service = Mock()
            mock_service.send_welcome_message.side_effect = Exception("Twilio error")
            mock_whatsapp.return_value = mock_service
            
            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+255123456789",
                    "Body": "Hello",
                    "MessageSid": "SM12345678"
                }
            )
            
            # Should still succeed even if welcome message fails
            assert response.status_code == 200
            assert response.json()["status"] == "success"
            
            # Customer and message should still be created
            customer = db_session.query(Customer).first()
            assert customer is not None
            message = db_session.query(Message).first()
            assert message is not None

    def test_webhook_phone_number_normalization(self, client: TestClient, db_session: Session):
        with patch('routers.whatsapp.WhatsAppService') as mock_whatsapp:
            mock_service = Mock()
            mock_whatsapp.return_value = mock_service
            
            response = client.post(
                "/api/whatsapp/webhook",
                data={
                    "From": "whatsapp:+1234567890",  # Different format
                    "Body": "Test message",
                    "MessageSid": "SM_TEST"
                }
            )
            
            assert response.status_code == 200
            
            customer = db_session.query(Customer).first()
            assert customer.phone_number == "+1234567890"  # Prefix removed

    def test_webhook_missing_fields(self, client: TestClient):
        # Test missing From field
        response = client.post(
            "/api/whatsapp/webhook",
            data={
                "Body": "Test message",
                "MessageSid": "SM_TEST"
            }
        )
        assert response.status_code == 422  # Validation error

        # Test missing Body field
        response = client.post(
            "/api/whatsapp/webhook",
            data={
                "From": "whatsapp:+255123456789",
                "MessageSid": "SM_TEST"
            }
        )
        assert response.status_code == 422

        # Test missing MessageSid field
        response = client.post(
            "/api/whatsapp/webhook",
            data={
                "From": "whatsapp:+255123456789",
                "Body": "Test message"
            }
        )
        assert response.status_code == 422

    def test_webhook_status_endpoint(self, client: TestClient):
        response = client.get("/api/whatsapp/status")
        assert response.status_code == 200
        assert response.json()["status"] == "WhatsApp service is running"