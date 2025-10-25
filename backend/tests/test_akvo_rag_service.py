import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import os

from services.akvo_rag_service import AkvoRagService, get_akvo_rag_service
from models.message import MessageType


@pytest.fixture
def akvo_rag_service():
    """Create AkvoRagService instance for testing"""
    # Reset class-level registration state before each test
    AkvoRagService._is_registered = False
    service = AkvoRagService()
    # Clear access_token for most tests (individual tests can set it)
    service.access_token = None
    return service


@pytest.fixture
def mock_httpx_client():
    """Mock httpx AsyncClient"""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client, mock_response


class TestAkvoRagServiceRegistration:
    """Tests for app registration with akvo-rag"""

    @pytest.mark.asyncio
    async def test_register_app_in_testing_mode(self, akvo_rag_service):
        """Test that registration is skipped in TESTING mode"""
        # TESTING env var is set by default in pytest
        assert os.getenv("TESTING") is not None

        result = await akvo_rag_service.register_app()

        # Should return True and mark as registered without HTTP calls
        assert result is True
        assert AkvoRagService._is_registered is True

    @pytest.mark.asyncio
    async def test_register_app_success(
        self, akvo_rag_service, mock_httpx_client
    ):
        """Test successful app registration (non-testing mode)"""
        # Temporarily disable testing mode
        original_testing = os.environ.get("TESTING")
        if "TESTING" in os.environ:
            del os.environ["TESTING"]

        try:
            mock_client, mock_response = mock_httpx_client
            mock_response.status_code = 201
            mock_response.json.return_value = {
                "app_id": "app_123",
                "access_token": "tok_abc123",
                "knowledge_base_id": 42,
            }
            mock_response.raise_for_status = MagicMock()

            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await akvo_rag_service.register_app()

            assert result is True
            assert akvo_rag_service.access_token == "tok_abc123"
            assert akvo_rag_service.knowledge_base_id == 42

            # Verify the request was made
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert "/api/apps/register" in call_args[0][0]
            assert call_args[1]["json"]["app_name"]
            assert call_args[1]["timeout"] == 30.0
        finally:
            # Restore original TESTING env var
            if original_testing:
                os.environ["TESTING"] = original_testing
            AkvoRagService._is_registered = False

    @pytest.mark.asyncio
    async def test_register_app_already_has_token(self, akvo_rag_service):
        """Test registration skips when access_token already exists"""
        # Temporarily disable testing mode
        original_testing = os.environ.get("TESTING")
        if "TESTING" in os.environ:
            del os.environ["TESTING"]

        try:
            # Set existing token
            akvo_rag_service.access_token = "existing_token"
            akvo_rag_service.knowledge_base_id = 99

            result = await akvo_rag_service.register_app()

            # Should return True without making HTTP calls
            assert result is True
            assert AkvoRagService._is_registered is True
            assert akvo_rag_service.access_token == "existing_token"
        finally:
            if original_testing:
                os.environ["TESTING"] = original_testing
            AkvoRagService._is_registered = False

    @pytest.mark.asyncio
    async def test_register_app_no_base_url(self, akvo_rag_service):
        """Test registration fails when base_url is not configured"""
        # Temporarily disable testing mode
        original_testing = os.environ.get("TESTING")
        if "TESTING" in os.environ:
            del os.environ["TESTING"]

        try:
            akvo_rag_service.base_url = None

            result = await akvo_rag_service.register_app()

            assert result is False
        finally:
            if original_testing:
                os.environ["TESTING"] = original_testing

    @pytest.mark.asyncio
    async def test_register_app_http_error(
        self, akvo_rag_service, mock_httpx_client
    ):
        """Test registration handles HTTP errors gracefully"""
        # Temporarily disable testing mode
        original_testing = os.environ.get("TESTING")
        if "TESTING" in os.environ:
            del os.environ["TESTING"]

        try:
            mock_client, mock_response = mock_httpx_client
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Bad Request",
                request=MagicMock(),
                response=mock_response,
            )

            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await akvo_rag_service.register_app()

            assert result is False
        finally:
            if original_testing:
                os.environ["TESTING"] = original_testing

    @pytest.mark.asyncio
    async def test_register_app_connection_error(
        self, akvo_rag_service, mock_httpx_client
    ):
        """Test registration handles connection errors"""
        # Temporarily disable testing mode
        original_testing = os.environ.get("TESTING")
        if "TESTING" in os.environ:
            del os.environ["TESTING"]

        try:
            mock_client, _ = mock_httpx_client
            mock_client.post.side_effect = httpx.ConnectError(
                "Connection refused"
            )

            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await akvo_rag_service.register_app()

            assert result is False
        finally:
            if original_testing:
                os.environ["TESTING"] = original_testing

    @pytest.mark.asyncio
    async def test_register_app_timeout(
        self, akvo_rag_service, mock_httpx_client
    ):
        """Test registration handles timeout errors"""
        # Temporarily disable testing mode
        original_testing = os.environ.get("TESTING")
        if "TESTING" in os.environ:
            del os.environ["TESTING"]

        try:
            mock_client, _ = mock_httpx_client
            mock_client.post.side_effect = httpx.TimeoutException(
                "Request timeout"
            )

            with patch("httpx.AsyncClient", return_value=mock_client):
                result = await akvo_rag_service.register_app()

            assert result is False
        finally:
            if original_testing:
                os.environ["TESTING"] = original_testing


class TestAkvoRagServiceChatJobs:
    """Tests for creating chat jobs with akvo-rag"""

    @pytest.mark.asyncio
    async def test_create_chat_job_reply_mode_success(
        self, akvo_rag_service, mock_httpx_client
    ):
        """Test creating REPLY mode chat job successfully"""
        akvo_rag_service.access_token = "tok_test123"
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "job_abc123",
            "status": "queued",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await akvo_rag_service.create_chat_job(
                message_id=123,
                message_type=MessageType.REPLY.value,
                customer_id=456,
            )

        assert result is not None
        assert result["job_id"] == "job_abc123"
        assert result["status"] == "queued"

        # Verify request details
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/api/apps/jobs" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "Bearer tok_test123"

    @pytest.mark.asyncio
    async def test_create_chat_job_whisper_mode_with_ticket(
        self, akvo_rag_service, mock_httpx_client
    ):
        """Test creating WHISPER mode chat job with ticket ID"""
        akvo_rag_service.access_token = "tok_test123"
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "job_whisper_123",
            "status": "queued",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await akvo_rag_service.create_chat_job(
                message_id=789,
                message_type=MessageType.WHISPER.value,
                customer_id=456,
                ticket_id=999,
                administrative_id=12,
            )

        assert result is not None
        assert result["job_id"] == "job_whisper_123"

        # Verify callback_params includes ticket_id and administrative_id
        call_args = mock_client.post.call_args
        form_data = call_args[1]["data"]
        import json

        payload = json.loads(form_data["payload"])
        assert payload["callback_params"]["ticket_id"] == 999
        assert payload["callback_params"]["administrative_id"] == 12

    @pytest.mark.asyncio
    async def test_create_chat_job_with_chat_history(
        self, akvo_rag_service, mock_httpx_client
    ):
        """Test creating chat job with chat history"""
        akvo_rag_service.access_token = "tok_test123"
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "job_456",
            "status": "queued"
        }
        mock_response.raise_for_status = MagicMock()

        chat_history = [
            {"role": "user", "content": "What is rice?"},
            {"role": "assistant", "content": "Rice is a grain..."},
        ]

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await akvo_rag_service.create_chat_job(
                message_id=123,
                message_type=MessageType.REPLY.value,
                customer_id=456,
                chats=chat_history,
                trace_id="trace_001",
            )

        assert result is not None

        # Verify chat history and trace_id are included
        call_args = mock_client.post.call_args
        form_data = call_args[1]["data"]
        import json

        payload = json.loads(form_data["payload"])
        assert payload["chats"] == chat_history
        assert payload["trace_id"] == "trace_001"

    @pytest.mark.asyncio
    async def test_create_chat_job_no_access_token(self, akvo_rag_service):
        """Test creating chat job fails without access token"""
        akvo_rag_service.access_token = None

        result = await akvo_rag_service.create_chat_job(
            message_id=123,
            message_type=MessageType.REPLY.value,
            customer_id=456,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_create_chat_job_http_error(
        self, akvo_rag_service, mock_httpx_client
    ):
        """Test creating chat job handles HTTP errors"""
        akvo_rag_service.access_token = "tok_test123"
        mock_client, mock_response = mock_httpx_client
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await akvo_rag_service.create_chat_job(
                message_id=123,
                message_type=MessageType.REPLY.value,
                customer_id=456,
            )

        assert result is None

    @pytest.mark.asyncio
    async def test_create_chat_job_timeout(
        self, akvo_rag_service, mock_httpx_client
    ):
        """Test creating chat job handles timeout"""
        akvo_rag_service.access_token = "tok_test123"
        mock_client, _ = mock_httpx_client
        mock_client.post.side_effect = httpx.TimeoutException(
            "Request timeout"
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await akvo_rag_service.create_chat_job(
                message_id=123,
                message_type=MessageType.REPLY.value,
                customer_id=456,
            )

        assert result is None


class TestAkvoRagServiceSingleton:
    """Tests for service singleton pattern"""

    def test_get_akvo_rag_service_returns_singleton(self):
        """Test that get_akvo_rag_service returns the same instance"""
        # Reset global instance
        import services.akvo_rag_service

        services.akvo_rag_service._akvo_rag_service = None

        service1 = get_akvo_rag_service()
        service2 = get_akvo_rag_service()

        assert service1 is service2

    def test_get_akvo_rag_service_initializes_with_config(self):
        """Test that service is initialized with config values"""
        # Reset global instance
        import services.akvo_rag_service

        services.akvo_rag_service._akvo_rag_service = None

        service = get_akvo_rag_service()

        # base_url should be set from config
        assert service.base_url is not None
        # knowledge_base_id and access_token can be None in fresh test env
        # (they get populated after registration or from existing config)
        assert hasattr(service, 'knowledge_base_id')
        assert hasattr(service, 'access_token')
