import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from services.akvo_rag_service import AkvoRagService, get_akvo_rag_service
from models.message import MessageType


@pytest.fixture
def akvo_rag_service():
    """Create AkvoRagService instance for testing"""
    service = AkvoRagService()
    # Clear credentials for most tests (individual tests can set them)
    service.access_token = None
    service.knowledge_base_id = None
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


class TestAkvoRagServiceConfiguration:
    """Tests for service configuration validation"""

    def test_is_configured_with_both_credentials(self, akvo_rag_service):
        """Test is_configured returns True when both token and KB ID are set"""
        akvo_rag_service.access_token = "tok_test123"
        akvo_rag_service.knowledge_base_id = 42

        assert akvo_rag_service.is_configured() is True

    def test_is_configured_missing_token(self, akvo_rag_service):
        """Test is_configured returns False when access_token is missing"""
        akvo_rag_service.access_token = None
        akvo_rag_service.knowledge_base_id = 42

        assert akvo_rag_service.is_configured() is False

    def test_is_configured_missing_kb_id(self, akvo_rag_service):
        """
        Test is_configured returns False when knowledge_base_id is missing
        """
        akvo_rag_service.access_token = "tok_test123"
        akvo_rag_service.knowledge_base_id = None

        assert akvo_rag_service.is_configured() is False

    def test_is_configured_both_missing(self, akvo_rag_service):
        """
        Test is_configured returns False when both credentials are missing
        """
        akvo_rag_service.access_token = None
        akvo_rag_service.knowledge_base_id = None

        assert akvo_rag_service.is_configured() is False


class TestAkvoRagServiceChatJobs:
    """Tests for creating chat jobs with Akvo RAG"""

    @pytest.mark.asyncio
    async def test_create_chat_job_not_configured(self, akvo_rag_service):
        """Test creating chat job fails when service not configured"""
        akvo_rag_service.access_token = None
        akvo_rag_service.knowledge_base_id = None

        result = await akvo_rag_service.create_chat_job(
            message_id=123,
            message_type=MessageType.REPLY.value,
            customer_id=456,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_create_chat_job_reply_mode_success(
        self, akvo_rag_service, mock_httpx_client
    ):
        """Test creating REPLY mode chat job successfully"""
        akvo_rag_service.access_token = "tok_test123"
        akvo_rag_service.knowledge_base_id = 42
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
        akvo_rag_service.knowledge_base_id = 42
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
                ticket_id=101,
                administrative_id=202,
            )

        assert result is not None
        assert result["job_id"] == "job_whisper_123"

        # Verify callback_params includes ticket and administrative info
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        form_data = call_args[1]["data"]
        payload = eval(form_data["payload"])  # Convert JSON string to dict
        callback_params = payload["callback_params"]
        assert callback_params["ticket_id"] == 101
        assert callback_params["administrative_id"] == 202

    @pytest.mark.asyncio
    async def test_create_chat_job_with_chats_history(
        self, akvo_rag_service, mock_httpx_client
    ):
        """Test creating chat job with chat history"""
        akvo_rag_service.access_token = "tok_test123"
        akvo_rag_service.knowledge_base_id = 42
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "job_history_123",
            "status": "queued",
        }
        mock_response.raise_for_status = MagicMock()

        chats = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await akvo_rag_service.create_chat_job(
                message_id=999,
                message_type=MessageType.REPLY.value,
                customer_id=456,
                chats=chats,
            )

        assert result is not None
        assert result["job_id"] == "job_history_123"

        # Verify chats are included in payload
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        form_data = call_args[1]["data"]
        payload = eval(form_data["payload"])
        assert payload["chats"] == chats

    @pytest.mark.asyncio
    async def test_create_chat_job_with_trace_id(
        self, akvo_rag_service, mock_httpx_client
    ):
        """Test creating chat job with trace ID for debugging"""
        akvo_rag_service.access_token = "tok_test123"
        akvo_rag_service.knowledge_base_id = 42
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "job_trace_123",
            "status": "queued",
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await akvo_rag_service.create_chat_job(
                message_id=888,
                message_type=MessageType.REPLY.value,
                customer_id=456,
                trace_id="trace_xyz789",
            )

        assert result is not None

        # Verify trace_id is included in payload
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        form_data = call_args[1]["data"]
        payload = eval(form_data["payload"])
        assert payload["trace_id"] == "trace_xyz789"

    @pytest.mark.asyncio
    async def test_create_chat_job_http_error(
        self, akvo_rag_service, mock_httpx_client
    ):
        """Test chat job creation handles HTTP errors gracefully"""
        akvo_rag_service.access_token = "tok_test123"
        akvo_rag_service.knowledge_base_id = 42
        mock_client, mock_response = mock_httpx_client
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request",
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
    async def test_create_chat_job_connection_error(
        self, akvo_rag_service, mock_httpx_client
    ):
        """Test chat job creation handles connection errors"""
        akvo_rag_service.access_token = "tok_test123"
        akvo_rag_service.knowledge_base_id = 42
        mock_client, _ = mock_httpx_client
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")

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
        """Test chat job creation handles timeout errors"""
        akvo_rag_service.access_token = "tok_test123"
        akvo_rag_service.knowledge_base_id = 42
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
    """Tests for global service instance management"""

    def test_get_akvo_rag_service_returns_same_instance(self):
        """Test get_akvo_rag_service returns the same instance"""
        service1 = get_akvo_rag_service()
        service2 = get_akvo_rag_service()

        assert service1 is service2
