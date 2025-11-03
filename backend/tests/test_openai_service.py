"""
Unit tests for OpenAI service.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from services.openai_service import OpenAIService, get_openai_service
from schemas.openai_schemas import (
    ChatCompletionResponse,
    ChatCompletionUsage,
    TranscriptionResponse,
    ModerationResponse,
    ModerationCategory,
    ModerationCategoryScores,
    EmbeddingResponse,
    StructuredOutputResponse,
)


class TestOpenAIService:
    """Test suite for OpenAIService"""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with OpenAI enabled"""
        with patch("services.openai_service.settings") as mock:
            mock.openai_enabled = True
            mock.openai_api_key = "sk-test-key-123"
            mock.openai_timeout = 30
            mock.openai_max_retries = 3
            mock.openai_chat_model = "gpt-4o-mini"
            mock.openai_temperature = 0.7
            mock.openai_max_tokens = 1000
            mock.openai_transcription_model = "whisper-1"
            mock.openai_embedding_model = "text-embedding-3-small"
            mock.openai_moderation_model = "text-moderation-latest"
            mock.openai_speech_to_text_enabled = True
            mock.openai_speech_to_text_language = "en"
            mock.openai_content_moderation_enabled = True
            mock.openai_cost_tracking_enabled = False
            yield mock

    @pytest.fixture
    def mock_openai_client(self):
        """Mock AsyncOpenAI client"""
        with patch("services.openai_service.AsyncOpenAI") as mock:
            yield mock

    @pytest.fixture
    def openai_service(self, mock_settings, mock_openai_client):
        """Create OpenAI service with mocked dependencies"""
        service = OpenAIService()
        return service

    def test_init_with_valid_config(
        self, mock_settings, mock_openai_client
    ):
        """Test OpenAIService initialization with valid configuration"""
        service = OpenAIService()

        assert service.is_configured() is True
        mock_openai_client.assert_called_once_with(
            api_key="sk-test-key-123",
            timeout=30,
            max_retries=3,
        )

    def test_init_with_disabled_config(self, mock_openai_client):
        """Test OpenAIService initialization when disabled"""
        with patch("services.openai_service.settings") as mock_settings:
            mock_settings.openai_enabled = False
            mock_settings.openai_api_key = ""

            service = OpenAIService()

            assert service.is_configured() is False

    def test_is_configured_missing_api_key(self, mock_openai_client):
        """Test is_configured returns False when API key is missing"""
        with patch("services.openai_service.settings") as mock_settings:
            mock_settings.openai_enabled = True
            mock_settings.openai_api_key = ""

            service = OpenAIService()

            assert service.is_configured() is False

    def test_count_tokens(self, openai_service):
        """Test token counting"""
        with patch("services.openai_service.tiktoken") as mock_tiktoken:
            mock_encoding = MagicMock()
            mock_encoding.encode.return_value = [1, 2, 3, 4, 5]
            mock_tiktoken.encoding_for_model.return_value = mock_encoding

            tokens = openai_service.count_tokens("Hello world")

            assert tokens == 5
            mock_tiktoken.encoding_for_model.assert_called_once()

    def test_count_tokens_fallback_on_error(self, openai_service):
        """Test token counting fallback when tiktoken fails"""
        with patch("services.openai_service.tiktoken") as mock_tiktoken:
            mock_tiktoken.encoding_for_model.side_effect = Exception(
                "Model not found"
            )

            text = "Hello world test"  # 16 chars
            tokens = openai_service.count_tokens(text)

            # Should fallback to estimate (16 / 4 = 4)
            assert tokens == 4

    @pytest.mark.asyncio
    async def test_chat_completion_success(self, openai_service):
        """Test successful chat completion"""
        # Mock response
        mock_choice = MagicMock()
        mock_choice.message.content = "Test response"
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 10
        mock_usage.completion_tokens = 20
        mock_usage.total_tokens = 30

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = mock_usage

        openai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        # Test
        result = await openai_service.chat_completion(
            messages=[{"role": "user", "content": "Hello"}]
        )

        # Assertions
        assert result is not None
        assert isinstance(result, ChatCompletionResponse)
        assert result.content == "Test response"
        assert result.model == "gpt-4o-mini"
        assert result.finish_reason == "stop"
        assert result.usage.total_tokens == 30

    @pytest.mark.asyncio
    async def test_chat_completion_not_configured(
        self, mock_openai_client
    ):
        """Test chat completion when not configured"""
        with patch("services.openai_service.settings") as mock_settings:
            mock_settings.openai_enabled = False
            mock_settings.openai_api_key = ""

            service = OpenAIService()
            result = await service.chat_completion(
                messages=[{"role": "user", "content": "Hello"}]
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_chat_completion_with_custom_params(
        self, openai_service
    ):
        """Test chat completion with custom parameters"""
        mock_choice = MagicMock()
        mock_choice.message.content = "Custom response"
        mock_choice.finish_reason = "stop"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o"
        mock_response.usage = None

        openai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        result = await openai_service.chat_completion(
            messages=[{"role": "user", "content": "Hello"}],
            model="gpt-4o",
            temperature=0.9,
            max_tokens=2000,
        )

        assert result is not None
        assert result.model == "gpt-4o"

        # Verify custom params were passed
        call_kwargs = (
            openai_service.client.chat.completions.create.call_args.kwargs
        )
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["temperature"] == 0.9
        assert call_kwargs["max_tokens"] == 2000

    @pytest.mark.asyncio
    async def test_chat_completion_api_error(self, openai_service):
        """Test chat completion with OpenAI API error"""
        from openai import OpenAIError

        openai_service.client.chat.completions.create = AsyncMock(
            side_effect=OpenAIError("API rate limit exceeded")
        )

        result = await openai_service.chat_completion(
            messages=[{"role": "user", "content": "Hello"}]
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_chat_completion_stream(self, openai_service):
        """Test streaming chat completion"""
        # Mock streaming response
        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock()]
        mock_chunk1.choices[0].delta.content = "Hello"

        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock()]
        mock_chunk2.choices[0].delta.content = " world"

        async def mock_stream():
            yield mock_chunk1
            yield mock_chunk2

        openai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_stream()
        )

        # Test
        chunks = []
        async for chunk in openai_service.chat_completion_stream(
            messages=[{"role": "user", "content": "Hello"}]
        ):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert chunks[0] == "Hello"
        assert chunks[1] == " world"

    @pytest.mark.asyncio
    async def test_transcribe_audio_with_url(self, openai_service):
        """Test audio transcription from URL"""
        # Mock HTTP download
        with patch("services.openai_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.content = b"fake audio data"
            mock_response.raise_for_status = MagicMock()

            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value = mock_context

            # Mock transcription response
            mock_transcript = MagicMock()
            mock_transcript.text = "Test transcription"
            mock_transcript.language = "en"

            openai_service.client.audio.transcriptions.create = AsyncMock(
                return_value=mock_transcript
            )

            # Test
            result = await openai_service.transcribe_audio(
                audio_url="https://example.com/audio.mp3"
            )

            # Assertions
            assert result is not None
            assert isinstance(result, TranscriptionResponse)
            assert result.text == "Test transcription"
            assert result.language == "en"

    @pytest.mark.asyncio
    async def test_transcribe_audio_with_bytes(self, openai_service):
        """Test audio transcription from bytes"""
        mock_transcript = MagicMock()
        mock_transcript.text = "Transcribed from bytes"
        mock_transcript.language = "en"

        openai_service.client.audio.transcriptions.create = AsyncMock(
            return_value=mock_transcript
        )

        audio_bytes = b"fake audio data"
        result = await openai_service.transcribe_audio(
            audio_file=audio_bytes
        )

        assert result is not None
        assert result.text == "Transcribed from bytes"

    @pytest.mark.asyncio
    async def test_transcribe_audio_not_configured(
        self, openai_service
    ):
        """Test transcription when not configured"""
        with patch("services.openai_service.settings") as mock_settings:
            mock_settings.openai_enabled = False

            service = OpenAIService()
            result = await service.transcribe_audio(
                audio_file=b"test audio"
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_transcribe_audio_disabled_feature(
        self, openai_service
    ):
        """Test transcription when feature is disabled"""
        with patch("services.openai_service.settings") as mock_settings:
            mock_settings.openai_enabled = True
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_speech_to_text_enabled = False

            service = OpenAIService()
            result = await service.transcribe_audio(
                audio_file=b"test audio"
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_transcribe_audio_no_input(self, openai_service):
        """Test transcription with no audio input"""
        result = await openai_service.transcribe_audio()

        assert result is None

    @pytest.mark.asyncio
    async def test_transcribe_audio_download_failure(
        self, openai_service
    ):
        """Test transcription when audio download fails"""
        with patch("services.openai_service.httpx.AsyncClient") as mock_client:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Network error")
            )
            mock_client.return_value = mock_context

            result = await openai_service.transcribe_audio(
                audio_url="https://example.com/audio.mp3"
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_moderate_content_success(self, openai_service):
        """Test successful content moderation"""
        # Mock moderation response
        mock_categories = MagicMock()
        mock_categories.model_dump.return_value = {
            "hate": True,
            "violence": False,
            "sexual": False,
            "self_harm": False,
            "hate_threatening": False,
            "harassment": False,
            "harassment_threatening": False,
            "self_harm_intent": False,
            "self_harm_instructions": False,
            "sexual_minors": False,
            "violence_graphic": False,
        }

        mock_scores = MagicMock()
        mock_scores.model_dump.return_value = {
            "hate": 0.95,
            "violence": 0.01,
            "sexual": 0.0,
            "self_harm": 0.0,
            "hate_threatening": 0.0,
            "harassment": 0.0,
            "harassment_threatening": 0.0,
            "self_harm_intent": 0.0,
            "self_harm_instructions": 0.0,
            "sexual_minors": 0.0,
            "violence_graphic": 0.0,
        }

        mock_result = MagicMock()
        mock_result.flagged = True
        mock_result.categories = mock_categories
        mock_result.category_scores = mock_scores

        mock_response = MagicMock()
        mock_response.results = [mock_result]

        openai_service.client.moderations.create = AsyncMock(
            return_value=mock_response
        )

        # Test
        result = await openai_service.moderate_content("Test content")

        # Assertions
        assert result is not None
        assert isinstance(result, ModerationResponse)
        assert result.flagged is True
        assert result.categories.hate is True
        assert result.category_scores.hate == 0.95

    @pytest.mark.asyncio
    async def test_moderate_content_not_flagged(self, openai_service):
        """Test moderation with safe content"""
        mock_categories = MagicMock()
        mock_categories.model_dump.return_value = {
            "hate": False,
            "violence": False,
            "sexual": False,
            "self_harm": False,
            "hate_threatening": False,
            "harassment": False,
            "harassment_threatening": False,
            "self_harm_intent": False,
            "self_harm_instructions": False,
            "sexual_minors": False,
            "violence_graphic": False,
        }

        mock_scores = MagicMock()
        mock_scores.model_dump.return_value = {
            "hate": 0.0,
            "violence": 0.0,
            "sexual": 0.0,
            "self_harm": 0.0,
            "hate_threatening": 0.0,
            "harassment": 0.0,
            "harassment_threatening": 0.0,
            "self_harm_intent": 0.0,
            "self_harm_instructions": 0.0,
            "sexual_minors": 0.0,
            "violence_graphic": 0.0,
        }

        mock_result = MagicMock()
        mock_result.flagged = False
        mock_result.categories = mock_categories
        mock_result.category_scores = mock_scores

        mock_response = MagicMock()
        mock_response.results = [mock_result]

        openai_service.client.moderations.create = AsyncMock(
            return_value=mock_response
        )

        result = await openai_service.moderate_content("Safe content")

        assert result is not None
        assert result.flagged is False

    @pytest.mark.asyncio
    async def test_moderate_content_disabled(self, openai_service):
        """Test moderation when feature is disabled"""
        with patch("services.openai_service.settings") as mock_settings:
            mock_settings.openai_enabled = True
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_content_moderation_enabled = False

            service = OpenAIService()
            result = await service.moderate_content("Test content")

            assert result is None

    @pytest.mark.asyncio
    async def test_create_embedding_success(self, openai_service):
        """Test successful embedding creation"""
        mock_data = MagicMock()
        mock_data.embedding = [0.1, 0.2, 0.3, 0.4]

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 5
        mock_usage.total_tokens = 5

        mock_response = MagicMock()
        mock_response.data = [mock_data]
        mock_response.model = "text-embedding-3-small"
        mock_response.usage = mock_usage

        openai_service.client.embeddings.create = AsyncMock(
            return_value=mock_response
        )

        # Test
        result = await openai_service.create_embedding("Test text")

        # Assertions
        assert result is not None
        assert isinstance(result, EmbeddingResponse)
        assert len(result.embedding) == 4
        assert result.model == "text-embedding-3-small"
        assert result.usage["prompt_tokens"] == 5

    @pytest.mark.asyncio
    async def test_create_embedding_not_configured(
        self, mock_openai_client
    ):
        """Test embedding when not configured"""
        with patch("services.openai_service.settings") as mock_settings:
            mock_settings.openai_enabled = False
            mock_settings.openai_api_key = ""

            service = OpenAIService()
            result = await service.create_embedding("Test text")

            assert result is None

    @pytest.mark.asyncio
    async def test_structured_output_success(self, openai_service):
        """Test structured output with JSON mode"""
        mock_choice = MagicMock()
        mock_choice.message.content = '{"name": "John", "age": 30}'
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 15
        mock_usage.completion_tokens = 10
        mock_usage.total_tokens = 25

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = mock_usage

        openai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        # Test
        result = await openai_service.structured_output(
            messages=[
                {"role": "user", "content": "Extract name and age"}
            ],
            response_format={"type": "json_object"},
        )

        # Assertions
        assert result is not None
        assert isinstance(result, StructuredOutputResponse)
        assert result.data["name"] == "John"
        assert result.data["age"] == 30
        assert result.usage.total_tokens == 25

    @pytest.mark.asyncio
    async def test_structured_output_invalid_json(
        self, openai_service
    ):
        """Test structured output with invalid JSON"""
        mock_choice = MagicMock()
        mock_choice.message.content = "Invalid JSON"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = None

        openai_service.client.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        result = await openai_service.structured_output(
            messages=[{"role": "user", "content": "Test"}],
            response_format={"type": "json_object"},
        )

        # Should handle JSON parse error gracefully
        assert result is None

    def test_get_usage_stats(self, openai_service):
        """Test getting usage statistics"""
        stats = openai_service.get_usage_stats()

        assert isinstance(stats, dict)
        assert "total_requests" in stats
        assert "total_tokens" in stats
        assert "prompt_tokens" in stats
        assert "completion_tokens" in stats

    def test_reset_usage_stats(self, openai_service):
        """Test resetting usage statistics"""
        # Set some usage
        openai_service.usage_stats["total_requests"] = 10
        openai_service.usage_stats["total_tokens"] = 100

        # Reset
        openai_service.reset_usage_stats()

        # Verify reset
        stats = openai_service.get_usage_stats()
        assert stats["total_requests"] == 0
        assert stats["total_tokens"] == 0

    def test_track_usage(self, openai_service):
        """Test usage tracking"""
        with patch("services.openai_service.settings") as mock_settings:
            mock_settings.openai_cost_tracking_enabled = True

            openai_service._track_usage(
                prompt_tokens=10, completion_tokens=20
            )

            stats = openai_service.get_usage_stats()
            assert stats["total_requests"] == 1
            assert stats["prompt_tokens"] == 10
            assert stats["completion_tokens"] == 20
            assert stats["total_tokens"] == 30

    def test_singleton_pattern(
        self, mock_settings, mock_openai_client
    ):
        """Test that get_openai_service returns singleton"""
        # Reset singleton
        import services.openai_service

        services.openai_service._openai_service = None

        service1 = get_openai_service()
        service2 = get_openai_service()

        assert service1 is service2
