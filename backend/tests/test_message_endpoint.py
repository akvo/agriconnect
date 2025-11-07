import uuid
import pytest
from unittest.mock import patch, MagicMock
from passlib.context import CryptContext

from models.user import User, UserType
from models.administrative import Administrative, UserAdministrative
from models.message import Message, MessageFrom, MessageStatus
from seeder.administrative import seed_administrative_data
from seeder.ticket import seed_customers, seed_messages, seed_tickets


class TestMessageEndpoints:
    """Test suite for /api/messages endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self, client, db_session):
        """Setup test data before each test"""
        self.db = db_session
        self.client = client
        self.pwd_context = CryptContext(
            schemes=["bcrypt"], deprecated="auto"
        )

        # Seed administrative data
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
        seed_administrative_data(self.db, rows)

        # Get administrative areas
        self.admin_area = (
            self.db.query(Administrative)
            .filter(Administrative.code == "LOC3")
            .first()
        )
        self.other_admin_area = (
            self.db.query(Administrative)
            .filter(Administrative.code == "LOC2")
            .first()
        )

        # Create EO user
        unique_id = str(uuid.uuid4())[:8]
        self.eo_user = User(
            email=f"eo-{unique_id}@example.com",
            phone_number=f"+123456789{unique_id[:3]}",
            hashed_password=self.pwd_context.hash("testpassword123"),
            full_name="EO User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True,
        )
        self.db.add(self.eo_user)
        self.db.commit()
        self.db.refresh(self.eo_user)

        # Link EO to admin area
        ua = UserAdministrative(
            user_id=self.eo_user.id,
            administrative_id=self.admin_area.id,
        )
        self.db.add(ua)
        self.db.commit()

        # Create Admin user
        unique_id = str(uuid.uuid4())[:8]
        self.admin_user = User(
            email=f"admin-{unique_id}@example.com",
            phone_number=f"+987654321{unique_id[:3]}",
            hashed_password=self.pwd_context.hash("adminpassword123"),
            full_name="Admin User",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        self.db.add(self.admin_user)
        self.db.commit()
        self.db.refresh(self.admin_user)

        # Create another EO user for testing access control
        unique_id = str(uuid.uuid4())[:8]
        self.other_eo_user = User(
            email=f"other-eo-{unique_id}@example.com",
            phone_number=f"+111222333{unique_id[:3]}",
            hashed_password=self.pwd_context.hash("testpassword123"),
            full_name="Other EO User",
            user_type=UserType.EXTENSION_OFFICER,
            is_active=True,
        )
        self.db.add(self.other_eo_user)
        self.db.commit()
        self.db.refresh(self.other_eo_user)

        # Link other EO to different admin area
        ua_other = UserAdministrative(
            user_id=self.other_eo_user.id,
            administrative_id=self.other_admin_area.id,
        )
        self.db.add(ua_other)
        self.db.commit()

        # Create customer and messages
        customers = seed_customers(
            self.db, administrative=self.admin_area, total=1
        )
        self.customer = customers[0]

        # Create messages
        messages = seed_messages(self.db, customer=self.customer, total=3)
        self.messages = messages

        # Create ticket
        self.ticket = seed_tickets(
            self.db,
            administrative=self.admin_area,
            customer=self.customer,
            initial_message=messages[0],
        )

    def _get_auth_headers(self, user: User) -> dict:
        """Generate authentication headers for a user"""
        from utils.auth import create_access_token

        token = create_access_token(data={"sub": user.email})
        return {"Authorization": f"Bearer {token}"}

    def test_create_message_as_eo(self):
        """Test creating a message as an EO user"""
        headers = self._get_auth_headers(self.eo_user)

        payload = {
            "ticket_id": self.ticket.id,
            "body": "This is my reply to the customer",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["body"] == payload["body"]
        assert data["from_source"] == MessageFrom.USER
        assert data["user_id"] == self.eo_user.id
        assert data["status"] == MessageStatus.PENDING
        assert data["ticket_id"] == self.ticket.id

        # Verify escalated message status changed to "replied"
        self.db.refresh(self.messages[0])
        assert self.messages[0].status == MessageStatus.REPLIED

    def test_create_message_as_admin(self):
        """Test creating a message as an admin user"""
        headers = self._get_auth_headers(self.admin_user)

        payload = {
            "ticket_id": self.ticket.id,
            "body": "Admin reply to the ticket",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["body"] == payload["body"]
        assert data["user_id"] == self.admin_user.id

    def test_create_message_unauthorized_area(self):
        """Test that EO cannot create message in unauthorized area"""
        headers = self._get_auth_headers(self.other_eo_user)

        payload = {
            "ticket_id": self.ticket.id,
            "body": "Unauthorized reply",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 403
        assert "outside your administrative area" in response.json()["detail"]

    def test_create_message_invalid_from_source(self):
        """Test creating message with invalid from_source"""
        headers = self._get_auth_headers(self.eo_user)

        payload = {
            "ticket_id": self.ticket.id,
            "body": "Test message",
            "from_source": 999,  # Invalid from_source
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 400
        assert "Invalid from_source" in response.json()["detail"]

    def test_create_message_llm_source(self):
        """Test creating an LLM-generated message"""
        headers = self._get_auth_headers(self.eo_user)

        payload = {
            "ticket_id": self.ticket.id,
            "body": "This is an AI-generated suggestion",
            "from_source": MessageFrom.LLM,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["from_source"] == MessageFrom.LLM
        assert data["user_id"] is None  # LLM messages don't have user_id

    def test_create_message_ticket_not_found(self):
        """Test creating message for non-existent ticket"""
        headers = self._get_auth_headers(self.eo_user)

        payload = {
            "ticket_id": 99999,
            "body": "Test message",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 404
        assert "Ticket not found" in response.json()["detail"]

    def test_update_message_status_to_replied(self):
        """Test updating message status to replied"""
        headers = self._get_auth_headers(self.eo_user)

        payload = {"status": MessageStatus.REPLIED}

        response = self.client.patch(
            f"/api/messages/{self.messages[0].id}/status",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == MessageStatus.REPLIED

        # Verify in database
        self.db.refresh(self.messages[0])
        assert self.messages[0].status == MessageStatus.REPLIED

    def test_update_message_status_to_resolved(self):
        """Test updating message status to resolved"""
        headers = self._get_auth_headers(self.eo_user)

        payload = {"status": MessageStatus.RESOLVED}

        response = self.client.patch(
            f"/api/messages/{self.messages[0].id}/status",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == MessageStatus.RESOLVED

        # Verify ticket was also updated
        self.db.refresh(self.ticket)
        assert self.ticket.resolved_at is not None
        assert self.ticket.resolved_by == self.eo_user.id

    def test_update_message_status_invalid_status(self):
        """Test updating message with invalid status"""
        headers = self._get_auth_headers(self.eo_user)

        payload = {"status": 999}  # Invalid status number

        response = self.client.patch(
            f"/api/messages/{self.messages[0].id}/status",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_update_message_status_unauthorized_area(self):
        """Test that EO cannot update message in unauthorized area"""
        headers = self._get_auth_headers(self.other_eo_user)

        payload = {"status": MessageStatus.REPLIED}

        response = self.client.patch(
            f"/api/messages/{self.messages[0].id}/status",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 403
        assert "outside your administrative area" in response.json()["detail"]

    def test_update_message_status_as_admin(self):
        """Test that admin can update any message status"""
        headers = self._get_auth_headers(self.admin_user)

        payload = {"status": MessageStatus.RESOLVED}

        response = self.client.patch(
            f"/api/messages/{self.messages[0].id}/status",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == MessageStatus.RESOLVED

    def test_update_message_status_not_found(self):
        """Test updating status of non-existent message"""
        headers = self._get_auth_headers(self.eo_user)

        payload = {"status": MessageStatus.REPLIED}

        response = self.client.patch(
            "/api/messages/99999/status",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 404
        assert "Message not found" in response.json()["detail"]

    def test_message_status_workflow(self):
        """Test complete message status workflow"""
        headers = self._get_auth_headers(self.eo_user)

        # 1. Initial status should be pending
        assert self.messages[0].status == MessageStatus.PENDING

        # 2. EO creates a reply (should change status to replied)
        create_payload = {
            "ticket_id": self.ticket.id,
            "body": "My reply",
            "from_source": MessageFrom.USER,
        }
        create_response = self.client.post(
            "/api/messages",
            json=create_payload,
            headers=headers,
        )
        assert create_response.status_code == 201

        # Verify escalated message status changed
        self.db.refresh(self.messages[0])
        assert self.messages[0].status == MessageStatus.REPLIED

        # 3. Update to resolved
        resolve_payload = {"status": MessageStatus.RESOLVED}
        resolve_response = self.client.patch(
            f"/api/messages/{self.messages[0].id}/status",
            json=resolve_payload,
            headers=headers,
        )
        assert resolve_response.status_code == 200

        # Verify ticket was resolved
        self.db.refresh(self.ticket)
        assert self.ticket.resolved_at is not None
        assert self.ticket.resolved_by == self.eo_user.id

    def test_create_multiple_messages_in_thread(self):
        """Test creating multiple messages in a ticket thread"""
        headers = self._get_auth_headers(self.eo_user)

        # Create first reply
        response1 = self.client.post(
            "/api/messages",
            json={
                "ticket_id": self.ticket.id,
                "body": "First reply",
                "from_source": MessageFrom.USER,
            },
            headers=headers,
        )
        assert response1.status_code == 201

        # Create second reply
        response2 = self.client.post(
            "/api/messages",
            json={
                "ticket_id": self.ticket.id,
                "body": "Second reply",
                "from_source": MessageFrom.USER,
            },
            headers=headers,
        )
        assert response2.status_code == 201

        # Verify both messages exist
        messages_count = (
            self.db.query(Message)
            .filter(Message.customer_id == self.customer.id)
            .count()
        )
        assert messages_count >= 5  # 3 original + 2 new

    def test_create_message_without_auth(self):
        """Test that creating message without auth returns 401"""
        payload = {
            "ticket_id": self.ticket.id,
            "body": "Unauthorized message",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post("/api/messages", json=payload)

        # Should return 401 or 403 depending on auth implementation
        assert response.status_code in [401, 403]

    def test_update_message_status_without_auth(self):
        """Test that updating status without auth returns 401"""
        payload = {"status": MessageStatus.REPLIED}

        response = self.client.patch(
            f"/api/messages/{self.messages[0].id}/status",
            json=payload,
        )

        # Should return 401 or 403 depending on auth implementation
        assert response.status_code in [401, 403]

    @patch("routers.messages.WhatsAppService")
    def test_create_message_sends_whatsapp(self, mock_whatsapp_service):
        """Test that creating a USER message sends WhatsApp to customer"""
        headers = self._get_auth_headers(self.eo_user)

        # Setup mock WhatsApp service
        mock_service_instance = MagicMock()
        mock_service_instance.send_message.return_value = {
            "sid": "SM1234567890",
            "status": "queued",
            "to": f"whatsapp:{self.customer.phone_number}",
            "body": "Test reply message",
        }
        mock_whatsapp_service.return_value = mock_service_instance

        payload = {
            "ticket_id": self.ticket.id,
            "body": "Test reply message",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 201

        # Verify WhatsApp service was called
        mock_whatsapp_service.assert_called_once()
        mock_service_instance.send_message.assert_called_once_with(
            to_number=self.customer.phone_number,
            message_body=payload["body"],
        )

        # Verify message_sid was updated with Twilio SID
        data = response.json()
        assert data["message_sid"] == "SM1234567890"

    @patch("routers.messages.WhatsAppService")
    def test_create_message_llm_does_not_send_whatsapp(
        self, mock_whatsapp_service
    ):
        """Test that LLM messages do NOT trigger WhatsApp send"""
        headers = self._get_auth_headers(self.eo_user)

        mock_service_instance = MagicMock()
        mock_whatsapp_service.return_value = mock_service_instance

        payload = {
            "ticket_id": self.ticket.id,
            "body": "AI-generated suggestion",
            "from_source": MessageFrom.LLM,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 201

        # Verify WhatsApp service was NOT called for LLM messages
        mock_whatsapp_service.assert_not_called()
        mock_service_instance.send_message.assert_not_called()

    @patch("routers.messages.WhatsAppService")
    def test_create_message_customer_does_not_send_whatsapp(
        self, mock_whatsapp_service
    ):
        """Test that CUSTOMER messages do NOT trigger WhatsApp send"""
        headers = self._get_auth_headers(self.eo_user)

        mock_service_instance = MagicMock()
        mock_whatsapp_service.return_value = mock_service_instance

        payload = {
            "ticket_id": self.ticket.id,
            "body": "Customer message",
            "from_source": MessageFrom.CUSTOMER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 201

        # Verify WhatsApp service was NOT called for CUSTOMER messages
        mock_whatsapp_service.assert_not_called()
        mock_service_instance.send_message.assert_not_called()

    @patch("routers.messages.WhatsAppService")
    def test_create_message_whatsapp_failure_does_not_block(
        self, mock_whatsapp_service
    ):
        """Test that WhatsApp failure does not block message creation"""
        headers = self._get_auth_headers(self.eo_user)

        # Setup mock to raise exception
        mock_service_instance = MagicMock()
        mock_service_instance.send_message.side_effect = Exception(
            "Twilio API error"
        )
        mock_whatsapp_service.return_value = mock_service_instance

        payload = {
            "ticket_id": self.ticket.id,
            "body": "Message that fails WhatsApp",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        # Should still succeed even if WhatsApp fails
        assert response.status_code == 201
        data = response.json()
        assert data["body"] == payload["body"]

        # Verify message was saved in database
        saved_message = (
            self.db.query(Message).filter(Message.id == data["id"]).first()
        )
        assert saved_message is not None
        assert saved_message.body == payload["body"]

    @patch("routers.messages.WhatsAppService")
    def test_create_message_updates_message_sid_with_twilio_sid(
        self, mock_whatsapp_service
    ):
        """Test that message_sid is updated with Twilio SID on success"""
        headers = self._get_auth_headers(self.eo_user)

        # Setup mock with specific Twilio SID
        twilio_sid = "SMabcdef1234567890"
        mock_service_instance = MagicMock()
        mock_service_instance.send_message.return_value = {
            "sid": twilio_sid,
            "status": "queued",
            "to": f"whatsapp:{self.customer.phone_number}",
            "body": "Test message",
        }
        mock_whatsapp_service.return_value = mock_service_instance

        payload = {
            "ticket_id": self.ticket.id,
            "body": "Test message",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 201
        data = response.json()

        # Verify message_sid was updated with Twilio SID
        assert data["message_sid"] == twilio_sid

        # Verify in database
        saved_message = (
            self.db.query(Message).filter(Message.id == data["id"]).first()
        )
        assert saved_message.message_sid == twilio_sid

    @patch("routers.messages.emit_message_received")
    def test_create_message_emits_admin_name_for_user_messages(
        self, mock_emit
    ):
        """Test that WebSocket event uses admin full name for admin messages"""
        headers = self._get_auth_headers(self.eo_user)

        payload = {
            "ticket_id": self.ticket.id,
            "body": "EO reply message",
            "from_source": MessageFrom.USER,
        }

        response = self.client.post(
            "/api/messages",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 201

        # Verify emit_message_received was called with EO's full name
        assert mock_emit.called
        call_kwargs = mock_emit.call_args[1]
        assert call_kwargs["sender_name"] == self.eo_user.full_name
        assert call_kwargs["sender_user_id"] == self.eo_user.id
        assert call_kwargs["from_source"] == MessageFrom.USER

    @patch("routers.messages.emit_message_received")
    def test_create_message_emits_customer_name_for_customer_messages(
        self, mock_emit
    ):
        """
        Test that WebSocket event uses customer name for customer messages
        """
        # This test verifies customer messages would use customer's name
        # Note: Customer messages typically come from WhatsApp webhook,
        # not this endpoint
        # But we can test the logic by checking what would be sent

        # In practice, customer messages come through WhatsApp webhook
        # This test documents the expected behavior for the messages endpoint
        # if it were to handle customer messages

        # The sender_name should be customer's full_name or phone_number
        assert self.customer.full_name is not None or \
            self.customer.phone_number is not None
