"""
Tests for Admin Playground Feature

Tests the following components:
1. Admin playground API endpoints
2. Playground message model
3. Playground callback handler
4. WebSocket playground room management
"""

import uuid
from unittest.mock import patch, Mock

import pytest
from fastapi import status

from models.user import User, UserType
from models.service_token import ServiceToken
from models.playground_message import (
    PlaygroundMessage,
    PlaygroundMessageRole,
    PlaygroundMessageStatus,
)
from passlib.context import CryptContext


@pytest.fixture
def admin_user(db_session):
    """Create an admin user for testing"""
    unique_id = str(uuid.uuid4())[:8]
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    user = User(
        email=f"playground-admin-{unique_id}@example.com",
        phone_number=f"+123456789{unique_id[:3]}",
        hashed_password=pwd_context.hash("testpassword123"),
        full_name="Playground Admin",
        user_type=UserType.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_token(client, admin_user):
    """Get authentication token for admin user"""
    login_response = client.post(
        "/api/auth/login/",
        json={"email": admin_user.email, "password": "testpassword123"},
    )
    assert login_response.status_code == status.HTTP_200_OK
    return login_response.json()["access_token"]


@pytest.fixture
def admin_headers(admin_token):
    """Get authorization headers for admin user"""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def service_token(db_session):
    """Create active service token for testing"""
    token = ServiceToken(
        service_name="Test AI Service",
        access_token="test_access_token_123",
        chat_url="http://test.example.com/chat",
        upload_url="http://test.example.com/upload",
        default_prompt="You are a helpful agricultural assistant.",
        active=1,
    )
    db_session.add(token)
    db_session.commit()
    db_session.refresh(token)
    return token


class TestPlaygroundMessageModel:
    """Test PlaygroundMessage database model"""

    def test_create_user_message(self, db_session, admin_user):
        """Test creating a user message"""
        session_id = str(uuid.uuid4())

        message = PlaygroundMessage(
            admin_user_id=admin_user.id,
            session_id=session_id,
            role=PlaygroundMessageRole.USER,
            content="Test user message",
            service_used="Test AI Service",
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        assert message.id is not None
        assert message.role == PlaygroundMessageRole.USER
        assert message.content == "Test user message"
        assert message.session_id == session_id
        assert message.created_at is not None

    def test_create_assistant_message(self, db_session, admin_user):
        """Test creating an assistant message"""
        session_id = str(uuid.uuid4())

        message = PlaygroundMessage(
            admin_user_id=admin_user.id,
            session_id=session_id,
            role=PlaygroundMessageRole.ASSISTANT,
            content="Test assistant response",
            job_id="test_job_123",
            status=PlaygroundMessageStatus.PENDING,
            service_used="Test AI Service",
            response_time_ms=1500,
        )
        db_session.add(message)
        db_session.commit()
        db_session.refresh(message)

        assert message.id is not None
        assert message.role == PlaygroundMessageRole.ASSISTANT
        assert message.status == PlaygroundMessageStatus.PENDING
        assert message.job_id == "test_job_123"
        assert message.response_time_ms == 1500

    def test_cascade_delete_on_admin_delete(self, db_session, admin_user):
        """Test playground messages deleted when admin user deleted"""
        session_id = str(uuid.uuid4())

        # Create some messages
        for i in range(3):
            role = (
                PlaygroundMessageRole.USER if i % 2 == 0
                else PlaygroundMessageRole.ASSISTANT
            )
            message = PlaygroundMessage(
                admin_user_id=admin_user.id,
                session_id=session_id,
                role=role,
                content=f"Test message {i}",
            )
            db_session.add(message)
        db_session.commit()

        # Verify messages exist
        messages = db_session.query(PlaygroundMessage).filter(
            PlaygroundMessage.admin_user_id == admin_user.id
        ).all()
        assert len(messages) == 3

        # Delete admin user
        db_session.delete(admin_user)
        db_session.commit()

        # Verify messages are deleted (cascade)
        messages = db_session.query(PlaygroundMessage).filter(
            PlaygroundMessage.admin_user_id == admin_user.id
        ).all()
        assert len(messages) == 0


class TestPlaygroundEndpoints:
    """Test Admin Playground API endpoints"""

    def test_get_active_service_success(
        self, client, admin_headers, service_token
    ):
        """Test getting active service configuration"""
        response = client.get(
            "/api/admin/playground/active-service",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["service_name"] == "Test AI Service"
        assert data["chat_url"] == "http://test.example.com/chat"
        assert data["is_active"] is True
        assert data["has_valid_token"] is True

    def test_get_active_service_not_found(self, client, admin_headers):
        """Test getting active service when none configured"""
        response = client.get(
            "/api/admin/playground/active-service",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "No active service configured" in response.json()["detail"]

    def test_get_active_service_unauthorized(self, client, service_token):
        """Test getting active service without authentication"""
        response = client.get("/api/admin/playground/active-service")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_default_prompt_success(
        self, client, admin_headers, service_token
    ):
        """Test getting default prompt from service configuration"""
        response = client.get(
            "/api/admin/playground/default-prompt",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        expected = "You are a helpful agricultural assistant."
        assert data["default_prompt"] == expected

    def test_get_default_prompt_not_found(self, client, admin_headers):
        """Test getting default prompt when no service configured"""
        response = client.get(
            "/api/admin/playground/default-prompt",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @patch('routers.admin_playground.ExternalAIService')
    def test_send_chat_message_success(
        self, mock_service_class, client, admin_headers,
        service_token, db_session
    ):
        """Test sending a chat message successfully"""
        # Create mock instance
        mock_service = Mock()
        mock_service.is_configured = Mock(return_value=True)
        mock_service.token = service_token
        # Make create_chat_job an async mock that returns a value

        async def mock_create_chat(**kwargs):
            return {'job_id': 'test_job_123', 'status': 'pending'}
        mock_service.create_chat_job = mock_create_chat

        # Set the class to return our mock instance
        mock_service_class.return_value = mock_service

        # Send message
        response = client.post(
            "/api/admin/playground/chat",
            headers=admin_headers,
            json={
                "message": "Test message to AI",
                "custom_prompt": None,
            }
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response structure
        assert "session_id" in data
        assert "user_message" in data
        assert "assistant_message" in data
        assert "job_id" in data
        assert data["status"] == "pending"

        # Verify user message (role is lowercase in serialization)
        assert data["user_message"]["role"].lower() == "user"
        assert data["user_message"]["content"] == "Test message to AI"

        # Verify assistant message
        assert data["assistant_message"]["role"].lower() == "assistant"
        assert data["assistant_message"]["status"] == "pending"
        assert data["assistant_message"]["job_id"] == "test_job_123"

        # Verify messages in database
        session_id = data["session_id"]
        messages = db_session.query(PlaygroundMessage).filter(
            PlaygroundMessage.session_id == session_id
        ).order_by(PlaygroundMessage.created_at).all()

        assert len(messages) == 2
        assert messages[0].role == PlaygroundMessageRole.USER
        assert messages[1].role == PlaygroundMessageRole.ASSISTANT
        assert messages[1].status == PlaygroundMessageStatus.PENDING

    @patch('routers.admin_playground.ExternalAIService')
    def test_send_chat_message_with_custom_prompt(
        self, mock_service_class, client, admin_headers, service_token
    ):
        """Test sending a chat message with custom prompt override"""
        # Create mock instance
        mock_service = Mock()
        mock_service.is_configured = Mock(return_value=True)
        mock_service.token = service_token

        async def mock_create_chat(**kwargs):
            return {'job_id': 'test_job_456', 'status': 'pending'}
        mock_service.create_chat_job = mock_create_chat
        mock_service_class.return_value = mock_service

        custom_prompt = (
            "You are a specialized farming expert in dairy production."
        )

        response = client.post(
            "/api/admin/playground/chat",
            headers=admin_headers,
            json={
                "message": "Tell me about dairy farming",
                "custom_prompt": custom_prompt,
            }
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify custom prompt is stored
        assert data["user_message"]["custom_prompt"] == custom_prompt
        assert data["assistant_message"]["custom_prompt"] == custom_prompt

    @patch('routers.admin_playground.ExternalAIService')
    def test_send_chat_message_existing_session(
        self, mock_service_class, client, admin_headers,
        service_token, db_session
    ):
        """Test sending message to existing session"""
        # Create mock instance
        mock_service = Mock()
        mock_service.is_configured = Mock(return_value=True)
        mock_service.token = service_token

        async def mock_create_chat(**kwargs):
            return {'job_id': 'test_job_789', 'status': 'pending'}
        mock_service.create_chat_job = mock_create_chat
        mock_service_class.return_value = mock_service

        # First message
        response1 = client.post(
            "/api/admin/playground/chat",
            headers=admin_headers,
            json={"message": "First message"}
        )
        session_id = response1.json()["session_id"]

        # Second message with same session
        response2 = client.post(
            "/api/admin/playground/chat",
            headers=admin_headers,
            json={
                "message": "Second message",
                "session_id": session_id
            }
        )

        assert response2.status_code == status.HTTP_200_OK
        assert response2.json()["session_id"] == session_id

        # Verify 4 messages in database (2 user + 2 assistant)
        messages = db_session.query(PlaygroundMessage).filter(
            PlaygroundMessage.session_id == session_id
        ).all()
        assert len(messages) == 4

    @patch('routers.admin_playground.ExternalAIService')
    def test_send_chat_message_no_service_configured(
        self, mock_service_class, client, admin_headers
    ):
        """Test sending message when no AI service is configured"""
        # Create mock instance that returns False for is_configured
        mock_service = Mock()
        mock_service.is_configured = Mock(return_value=False)
        mock_service_class.return_value = mock_service

        response = client.post(
            "/api/admin/playground/chat",
            headers=admin_headers,
            json={"message": "Test message"}
        )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "No active AI service configured" in response.json()["detail"]

    def test_send_chat_message_unauthorized(self, client, service_token):
        """Test sending message without authentication"""
        response = client.post(
            "/api/admin/playground/chat",
            json={"message": "Test message"}
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_send_chat_message_validation_errors(
        self, client, admin_headers, service_token
    ):
        """Test input validation for chat messages"""
        # Empty message
        response = client.post(
            "/api/admin/playground/chat",
            headers=admin_headers,
            json={"message": ""}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Message too long
        response = client.post(
            "/api/admin/playground/chat",
            headers=admin_headers,
            json={"message": "x" * 5001}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

        # Invalid session_id format
        response = client.post(
            "/api/admin/playground/chat",
            headers=admin_headers,
            json={
                "message": "Test",
                "session_id": "invalid-uuid"
            }
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_get_chat_history_success(
        self, client, admin_headers, admin_user, db_session
    ):
        """Test getting chat history for a session"""
        session_id = str(uuid.uuid4())

        # Create some messages
        for i in range(6):
            role = (
                PlaygroundMessageRole.USER if i % 2 == 0
                else PlaygroundMessageRole.ASSISTANT
            )
            message = PlaygroundMessage(
                admin_user_id=admin_user.id,
                session_id=session_id,
                role=role,
                content=f"Message {i}",
            )
            db_session.add(message)
        db_session.commit()

        # Get history
        response = client.get(
            f"/api/admin/playground/history?session_id={session_id}",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session_id"] == session_id
        assert data["total_count"] == 6
        assert len(data["messages"]) == 6

    def test_get_chat_history_with_pagination(
        self, client, admin_headers, admin_user, db_session
    ):
        """Test getting chat history with pagination"""
        session_id = str(uuid.uuid4())

        # Create 10 messages
        for i in range(10):
            message = PlaygroundMessage(
                admin_user_id=admin_user.id,
                session_id=session_id,
                role=PlaygroundMessageRole.USER,
                content=f"Message {i}",
            )
            db_session.add(message)
        db_session.commit()

        # Get first page (5 messages)
        url = (
            f"/api/admin/playground/history?"
            f"session_id={session_id}&limit=5&offset=0"
        )
        response = client.get(url, headers=admin_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == 10
        assert len(data["messages"]) == 5

        # Get second page
        url = (
            f"/api/admin/playground/history?"
            f"session_id={session_id}&limit=5&offset=5"
        )
        response = client.get(url, headers=admin_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["messages"]) == 5

    def test_get_chat_history_only_own_messages(
        self, client, admin_headers, admin_user, db_session
    ):
        """Test that admin can only see their own messages"""
        session_id = str(uuid.uuid4())

        # Create another admin
        other_admin = User(
            email="other-admin@example.com",
            phone_number="+9999999999",
            hashed_password="hashed",
            full_name="Other Admin",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(other_admin)
        db_session.commit()

        # Create messages for both admins in same session
        for admin_id in [admin_user.id, other_admin.id]:
            message = PlaygroundMessage(
                admin_user_id=admin_id,
                session_id=session_id,
                role=PlaygroundMessageRole.USER,
                content=f"Message from admin {admin_id}",
            )
            db_session.add(message)
        db_session.commit()

        # Current admin should only see their message
        response = client.get(
            f"/api/admin/playground/history?session_id={session_id}",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == 1

    def test_get_sessions_success(
        self, client, admin_headers, admin_user, db_session
    ):
        """Test getting list of playground sessions"""
        # Create messages in 3 different sessions
        for i in range(3):
            session_id = str(uuid.uuid4())
            for j in range(2):
                message = PlaygroundMessage(
                    admin_user_id=admin_user.id,
                    session_id=session_id,
                    role=PlaygroundMessageRole.USER,
                    content=f"Session {i} Message {j}",
                )
                db_session.add(message)
        db_session.commit()

        # Get sessions list
        response = client.get(
            "/api/admin/playground/sessions",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_count"] == 3
        assert len(data["sessions"]) == 3

        # Verify session summary structure
        session = data["sessions"][0]
        assert "session_id" in session
        assert "message_count" in session
        assert "created_at" in session
        assert "last_message_at" in session

    def test_delete_session_success(
        self, client, admin_headers, admin_user, db_session
    ):
        """Test deleting a playground session"""
        session_id = str(uuid.uuid4())

        # Create messages
        for i in range(5):
            message = PlaygroundMessage(
                admin_user_id=admin_user.id,
                session_id=session_id,
                role=PlaygroundMessageRole.USER,
                content=f"Message {i}",
            )
            db_session.add(message)
        db_session.commit()

        # Verify messages exist
        messages = db_session.query(PlaygroundMessage).filter(
            PlaygroundMessage.session_id == session_id
        ).all()
        assert len(messages) == 5

        # Delete session
        response = client.delete(
            f"/api/admin/playground/session/{session_id}",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Verify messages are deleted
        messages = db_session.query(PlaygroundMessage).filter(
            PlaygroundMessage.session_id == session_id
        ).all()
        assert len(messages) == 0

    def test_delete_session_not_found(self, client, admin_headers):
        """Test deleting non-existent session"""
        fake_session_id = str(uuid.uuid4())

        response = client.delete(
            f"/api/admin/playground/session/{fake_session_id}",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "Session not found" in response.json()["detail"]

    def test_delete_session_only_own(
        self, client, admin_headers, admin_user, db_session
    ):
        """Test that admin can only delete their own sessions"""
        session_id = str(uuid.uuid4())

        # Create another admin
        other_admin = User(
            email="other-delete-admin@example.com",
            phone_number="+8888888888",
            hashed_password="hashed",
            full_name="Other Delete Admin",
            user_type=UserType.ADMIN,
            is_active=True,
        )
        db_session.add(other_admin)
        db_session.commit()

        # Create message for other admin
        message = PlaygroundMessage(
            admin_user_id=other_admin.id,
            session_id=session_id,
            role=PlaygroundMessageRole.USER,
            content="Other admin's message",
        )
        db_session.add(message)
        db_session.commit()

        # Try to delete other admin's session
        response = client.delete(
            f"/api/admin/playground/session/{session_id}",
            headers=admin_headers
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestPlaygroundCallbackHandler:
    """Test playground callback handler"""

    @pytest.mark.asyncio
    @patch('routers.ws.emit_playground_response')
    async def test_handle_playground_callback_success(
        self, mock_emit, db_session, admin_user
    ):
        """Test successful playground callback handling"""
        from routers.callbacks import handle_playground_callback
        from schemas.callback import (
            AIWebhookCallback,
            CallbackStage,
            AICallbackParams,
            CallbackResult
        )

        session_id = str(uuid.uuid4())

        # Create pending assistant message
        assistant_message = PlaygroundMessage(
            admin_user_id=admin_user.id,
            session_id=session_id,
            role=PlaygroundMessageRole.ASSISTANT,
            content="",
            job_id="test_job_123",
            status=PlaygroundMessageStatus.PENDING,
        )
        db_session.add(assistant_message)
        db_session.commit()
        db_session.refresh(assistant_message)

        # Create callback payload
        payload = AIWebhookCallback(
            job_id="test_job_123",
            job="chat",
            status=CallbackStage.COMPLETED,
            stage=CallbackStage.COMPLETED,
            output=CallbackResult(
                answer="AI response content",
                citations=[]
            ),
            callback_params=AICallbackParams(
                source="playground",
                session_id=session_id,
                admin_user_id=admin_user.id,
                message_id=assistant_message.id
            )
        )

        # Handle callback
        result = await handle_playground_callback(payload, db_session)

        # Verify result
        assert result["status"] == "received"
        assert result["job_id"] == "test_job_123"

        # Verify message updated
        db_session.refresh(assistant_message)
        assert assistant_message.content == "AI response content"
        assert assistant_message.status == PlaygroundMessageStatus.COMPLETED
        assert assistant_message.response_time_ms is not None

    @pytest.mark.asyncio
    async def test_handle_playground_callback_message_not_found(
        self, db_session, admin_user
    ):
        """Test playground callback with non-existent message"""
        from routers.callbacks import handle_playground_callback
        from schemas.callback import (
            AIWebhookCallback,
            CallbackStage,
            AICallbackParams,
            CallbackResult
        )

        session_id = str(uuid.uuid4())

        # Create callback payload for non-existent job
        payload = AIWebhookCallback(
            job_id="test_job_nonexistent",
            job="chat",
            status=CallbackStage.COMPLETED,
            stage=CallbackStage.COMPLETED,
            output=CallbackResult(
                answer="AI response",
                citations=[]
            ),
            callback_params=AICallbackParams(
                source="playground",
                session_id=session_id,
                admin_user_id=admin_user.id,
                message_id=99999  # Non-existent
            )
        )

        # Should not raise exception, just log warning
        result = await handle_playground_callback(payload, db_session)

        # Should still acknowledge callback
        assert result["status"] == "received"
        assert result["job_id"] == "test_job_nonexistent"


class TestWebSocketPlaygroundEvents:
    """Test WebSocket playground room management"""

    def test_join_playground_event_exists(self):
        """Test that join_playground event handler exists"""
        from routers.ws import sio

        # Check event is registered
        handlers = sio.handlers
        assert "/" in handlers  # Default namespace
        assert "join_playground" in handlers["/"]

    @pytest.mark.asyncio
    async def test_join_playground_authentication_required(self):
        """Test that join_playground requires authentication"""
        from routers.ws import join_playground

        # Unknown SID should fail
        result = await join_playground("unknown_sid", {"session_id": "test"})

        assert result["success"] is False
        assert "error" in result
